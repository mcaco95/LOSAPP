from flask import Blueprint, redirect, request, render_template, flash, url_for
import json
from flask_login import login_required, current_user
import geoip2.database
from datetime import datetime, timedelta
from sqlalchemy import desc
from ..models.link_tracking import GlobalRedirect, LinkClick
from ..models.user import User
from ..decorators import admin_required
from .. import db
from ..forms import RedirectUrlForm

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

@bp.route('/r/<unique_link>')
def handle_referral(unique_link):
    """Handle referral links and track clicks"""
    # Get the global redirect URL first
    redirect_url = GlobalRedirect.get_active_url()
    
    # If we have a valid user, record the click
    user = User.query.filter_by(unique_link=unique_link).first()
    if user:
        # Get real IP address, checking X-Forwarded-For header first (for proxy scenarios like Ngrok)
        visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if visitor_ip and ',' in visitor_ip:
            # If multiple IPs in X-Forwarded-For, take the first one (original client)
            visitor_ip = visitor_ip.split(',')[0].strip()
            
        # Prepare tracking metadata
        tracking_metadata = {
            'headers': dict(request.headers),
            'platform': request.user_agent.platform,
            'browser': request.user_agent.browser,
            'version': request.user_agent.version,
            'language': request.accept_languages.best,
            'referrer': request.referrer,
            'timestamp_utc': datetime.utcnow().isoformat()
        }

        click = LinkClick(
            user_id=user.id,
            visitor_ip=visitor_ip,
            user_agent=request.user_agent.string,
            tracking_metadata=tracking_metadata
        )
        
        # Set device type
        click.set_device_type()
        
        # Add geographic data if GeoIP reader is available
        if geo_reader and visitor_ip:
            try:
                geo_data = geo_reader.city(visitor_ip)
                click.country = geo_data.country.iso_code
                click.city = geo_data.city.name
                click.region = geo_data.subdivisions.most_specific.name
            except:
                # If IP lookup fails, continue without geo data
                pass
        
        db.session.add(click)
        db.session.commit()
    
    # Always redirect to the global redirect URL
    return redirect(redirect_url)

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
