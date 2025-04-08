from flask import Blueprint, redirect, request, render_template, flash, url_for, jsonify, current_app
import json
from flask_login import login_required, current_user
import geoip2.database
from datetime import datetime, timedelta
from sqlalchemy import desc
from ..models.link_tracking import GlobalRedirect, LinkClick
from ..models.user import User
from ..models.company import Company
from ..decorators import admin_required, referral_required
from .. import db
from ..forms import RedirectUrlForm
from ..services.email import EmailService
from ..services.teams import TeamsService

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Initialize GeoIP reader
try:
    geo_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
except:
    geo_reader = None

bp = Blueprint('referrals', __name__)

@bp.route('/referrals')
@login_required
@referral_required
def index():
    """Display user's referral dashboard"""
    if not current_user.unique_link:
        current_user.generate_unique_link()
        db.session.commit()
    
    referral_link = f"{request.host_url}r/{current_user.unique_link}"
    stats = LinkClick.get_stats_for_user(current_user.id)
    
    return render_template('referrals/index.html',
                          referral_link=referral_link,
                          stats=stats)

@bp.route('/r/<unique_link>')
def redirect_link(unique_link):
    """Handle referral link clicks and redirects"""
    user = User.query.filter_by(unique_link=unique_link).first()
    if not user:
        flash('Invalid referral link.', 'error')
        return redirect(url_for('main.index'))
    
    # Record the click
    click = LinkClick(
        user_id=user.id,
        visitor_ip=request.remote_addr,
        user_agent=request.user_agent.string
    )
    
    # Set device type
    click.set_device_type()
    
    db.session.add(click)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error recording click: {str(e)}")
    
    # Redirect to the landing page with the partner ID
    return redirect(url_for('referrals.landing_page', partner_id=user.id))

@bp.route('/landing')
def landing_page():
    """Display the landing page with the lead form"""
    partner_id = request.args.get('partner_id')
    partner_name = None
    
    if partner_id:
        partner = User.query.get(partner_id)
        if partner:
            partner_name = partner.name or partner.username
    
    return render_template('landing/lead_form.html', 
                          partner_id=partner_id,
                          partner_name=partner_name,
                          form_submitted=False)

@bp.route('/landing/submit', methods=['POST'])
def submit_lead_form():
    """Handle lead form submission"""
    partner_id = request.form.get('partner_id')
    
    if not partner_id:
        flash('Error: Missing partner information', 'danger')
        return redirect(url_for('referrals.landing_page'))
    
    # Get partner
    partner = User.query.get(partner_id)
    if not partner:
        flash('Error: Invalid partner information', 'danger')
        return redirect(url_for('referrals.landing_page'))
    
    current_app.logger.info(f"Processing form submission for partner ID: {partner_id}")
    
    # Create new company from form data
    company = Company(
        name=request.form.get('company_name'),
        user_id=partner_id,
        status='lead',
        contact_name=request.form.get('contact_name'),
        email=request.form.get('email'),
        phone=request.form.get('phone'),
        service_type=request.form.get('service_interest'),
        preferred_contact_time=request.form.get('preferred_contact_time'),
        additional_info=request.form.get('message'),
        metadata={
            'form_submission_date': datetime.utcnow().isoformat(),
            'form_submission_ip': request.remote_addr,
            'user_agent': request.user_agent.string,
            'status_history': [{
                'from': None,
                'to': 'lead',
                'timestamp': datetime.utcnow().isoformat()
            }]
        }
    )
    
    try:
        db.session.add(company)
        db.session.commit()
        current_app.logger.info(f"Successfully created company record: {company.name}")
        
        # Prepare data for notifications
        company_data = {
            'name': company.name,
            'contact_name': company.contact_name,
            'email': company.email,
            'phone': company.phone,
            'service_type': company.service_type,
            'preferred_contact_time': company.preferred_contact_time,
            'additional_info': company.additional_info
        }
        
        partner_data = {
            'name': partner.name or partner.username,
            'email': partner.email
        }
        
        # Send email notification
        current_app.logger.info("Attempting to send email notification...")
        email_sent = EmailService.send_lead_notification(company_data, partner_data)
        
        if email_sent:
            current_app.logger.info("Email notification sent successfully")
        else:
            current_app.logger.warning("Failed to send email notification")
            
        # Send Teams notification
        current_app.logger.info("Attempting to send Teams notification...")
        teams_sent = TeamsService.send_lead_notification(company_data, partner_data)
        
        if teams_sent:
            current_app.logger.info("Teams notification sent successfully")
        else:
            current_app.logger.warning("Failed to send Teams notification")
        
        # Show success page
        return render_template('landing/lead_form.html',
                              partner_id=partner_id,
                              partner_name=partner.name or partner.username,
                              form_submitted=True)
    except Exception as e:
        current_app.logger.error(f"Error in form submission: {str(e)}")
        db.session.rollback()
        flash(f'Error: Could not save your information. {str(e)}', 'danger')
        return redirect(url_for('referrals.landing_page', partner_id=partner_id))

@bp.route('/admin/referrals', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_referrals():
    """Admin interface for managing referrals"""
    form = RedirectUrlForm()
    
    if form.validate_on_submit():
        # Deactivate all existing redirects
        GlobalRedirect.query.update({GlobalRedirect.is_active: False})
        
        # Create new active redirect
        redirect_url = GlobalRedirect(redirect_url=form.url.data)
        db.session.add(redirect_url)
        db.session.commit()
        flash('Redirect URL has been updated.')
        return redirect(url_for('referrals.admin_referrals'))
    
    # Get current redirect URL
    current_redirect = GlobalRedirect.query.filter_by(is_active=True).first()
    if current_redirect:
        form.url.data = current_redirect.redirect_url
    
    try:
        # Get stats for all users
        users = User.query.all()
        user_stats = []
        for user in users:
            if user and user.id:  # Ensure we have a valid user
                try:
                    stats = LinkClick.get_stats_for_user(user.id)
                    # Ensure all required fields are present with defaults
                    user_stats.append({
                        'name': user.name or user.email or 'Unknown User',
                        'email': user.email or 'No Email',
                        'unique_link': f"{request.host_url}r/{user.unique_link}" if user.unique_link else '',
                        'stats': stats
                    })
                except Exception as e:
                    # Log the error but continue processing other users
                    print(f"Error processing stats for user {user.id}: {str(e)}")
                    continue
    except Exception as e:
        print(f"Error fetching user stats: {str(e)}")
        user_stats = []
    
    # Pre-encode user_stats using our CustomJSONEncoder
    encoded_stats = json.dumps(user_stats, cls=CustomJSONEncoder)
    
    return render_template('referrals/admin.html', 
                         form=form, 
                         user_stats=user_stats,
                         user_stats_json=encoded_stats)

@bp.route('/admin/click-history')
@login_required
@admin_required
def click_history():
    """Show detailed history of all clicks"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Base query
    query = LinkClick.query.join(User).order_by(desc(LinkClick.timestamp))
    
    # Apply filters if present
    filters = {
        'user_id': request.args.get('user_id', type=int),
        'device_type': request.args.get('device_type'),
        'country': request.args.get('country'),
        'days': request.args.get('days', type=int)
    }
    
    if filters['user_id']:
        query = query.filter(LinkClick.user_id == filters['user_id'])
    if filters['device_type']:
        query = query.filter(LinkClick.device_type == filters['device_type'])
    if filters['country']:
        query = query.filter(LinkClick.country == filters['country'])
    if filters['days']:
        cutoff_date = datetime.utcnow() - timedelta(days=filters['days'])
        query = query.filter(LinkClick.timestamp >= cutoff_date)
    
    # Execute paginated query
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    clicks = pagination.items
    
    # Get filter options
    users = User.query.all()
    countries = db.session.query(LinkClick.country).distinct().all()
    device_types = ['desktop', 'mobile', 'tablet']
    
    return render_template('referrals/click_history.html',
                         clicks=clicks,
                         pagination=pagination,
                         filters=filters,
                         users=users,
                         countries=[c[0] for c in countries if c[0]],
                         device_types=device_types)
