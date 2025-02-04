from flask import Blueprint, redirect, request, render_template, flash, url_for
import json
from flask_login import login_required, current_user
import geoip2.database
from datetime import datetime
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
        click = LinkClick(
            user_id=user.id,
            visitor_ip=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        # Set device type
        click.set_device_type()
        
        # Add geographic data if GeoIP reader is available
        if geo_reader and request.remote_addr:
            try:
                geo_data = geo_reader.city(request.remote_addr)
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
