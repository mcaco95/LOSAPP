from flask import Blueprint, redirect, request, render_template, flash, url_for
from flask_login import login_required, current_user
from ..models.link_tracking import GlobalRedirect, LinkClick
from ..models.user import User
from ..decorators import admin_required
from .. import db
from ..forms import RedirectUrlForm

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
    
    # Get stats for all users
    users = User.query.all()
    user_stats = []
    for user in users:
        stats = LinkClick.get_stats_for_user(user.id)
        user_stats.append({
            'name': user.name or user.email,
            'email': user.email,
            'unique_link': f"{request.host_url}r/{user.unique_link}",
            'stats': stats
        })
    
    return render_template('referrals/admin.html', form=form, user_stats=user_stats)
