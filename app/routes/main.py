from flask import Blueprint, render_template, redirect, request, url_for, jsonify, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from app.services.points import PointService
from app.services.company import CompanyService
from app.services.reward import RewardService
from app.decorators import admin_required
from app.models.company import Company
from app.models.user import User
from .. import db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.email == 'simon@logisticsonesource.com':
        return redirect(url_for('main.admin_dashboard'))
    return redirect(url_for('main.user_dashboard'))

@main.route('/dashboard/user')
@login_required
def user_dashboard():
    point_service = PointService()
    company_service = CompanyService()
    reward_service = RewardService()

    # Get user's points summary
    points_summary = point_service.get_user_points_summary(current_user.id)
    
    # Get user's rank and percentile
    rank_info = point_service.get_user_rank(current_user.id)
    
    # Get next reward info
    next_reward = reward_service.get_next_reward(current_user.id)
    
    # Handle case where there's no next reward
    next_reward_data = next_reward or {
        'reward': {'points_required': 0},
        'progress_percentage': 0
    }
    
    # Get user's companies
    companies = company_service.get_user_companies(current_user.id)
    
    # Get top performers
    top_users = point_service.get_top_users(limit=5)

    return render_template('dashboard/user/index.html',
        total_points=points_summary['total_points'],
        points_change=points_summary['monthly_change'],
        rank=rank_info['rank'],
        rank_percentile=rank_info['percentile'],
        next_reward_points=next_reward_data['reward']['points_required'],
        next_reward_progress=next_reward_data['progress_percentage'],
        companies=companies,
        top_users=top_users
    )

@main.route('/dashboard/admin')
@login_required
@admin_required
def admin_dashboard():
    point_service = PointService()
    
    # Get system-wide metrics
    metrics = point_service.get_system_metrics()
    
    # Get recent activity
    recent_activity = point_service.get_recent_activity(limit=10)
    
    # Get top performers for the dashboard
    top_performers = point_service.get_top_users(limit=5)

    return render_template('dashboard/admin/index.html',
        total_users=metrics['total_users'],
        user_growth=metrics['user_growth'],
        total_points=metrics['total_points'],
        points_growth=metrics['points_growth'],
        recent_activity=recent_activity,
        top_performers=top_performers
    )

@main.route('/dashboard/admin/points')
@login_required
@admin_required
def admin_points():
    point_service = PointService()
    
    # Get point rules
    point_rules = point_service.get_point_rules()
    
    # Get points distribution data
    distribution_data = point_service.get_points_distribution()
    
    # Get top earners
    top_earners = point_service.get_top_users(limit=5)

    return render_template('dashboard/admin/points.html',
        point_rules=point_rules,
        distribution_data=distribution_data,
        top_earners=top_earners
    )

@main.route('/dashboard/admin/rewards')
@login_required
@admin_required
def admin_rewards():
    reward_service = RewardService()
    
    # Get all rewards
    rewards = reward_service.get_all_rewards()
    
    # Get recent redemptions
    recent_redemptions = reward_service.get_recent_redemptions(limit=10)

    return render_template('dashboard/admin/rewards.html',
        rewards=rewards,
        recent_redemptions=recent_redemptions
    )

@main.route('/dashboard/points/history')
@login_required
def points_history():
    period = request.args.get('period', 'month')
    point_service = PointService()
    history = point_service.get_points_history(current_user.id, period)
    return jsonify(history)

@main.route('/settings')
@login_required
def settings():
    return render_template('dashboard/user/index.html')  # Temporarily redirect to user dashboard until settings page is created

@main.route('/dashboard/user/rewards')
@login_required
def user_rewards():
    reward_service = RewardService()
    
    # Get available rewards
    available_rewards = reward_service.get_available_rewards(current_user.id)
    
    # Get user's reward history
    reward_history = reward_service.get_user_rewards(current_user.id)
    
    # Get next reward info
    next_reward = reward_service.get_next_reward(current_user.id)
    next_reward_data = next_reward or {
        'reward': {'points_required': 0},
        'progress_percentage': 0
    }
    
    return render_template('dashboard/user/rewards.html',
        available_rewards=available_rewards,
        reward_history=reward_history,
        next_reward_points=next_reward_data['reward']['points_required'],
        next_reward_progress=next_reward_data['progress_percentage']
    )

@main.route('/dashboard/user/companies')
@login_required
def user_companies():
    company_service = CompanyService()
    
    # Get user's companies
    companies = company_service.get_user_companies(current_user.id)
    
    # Get company statistics
    stats = company_service.get_company_statistics()
    
    return render_template('dashboard/user/companies.html',
        companies=companies,
        statistics=stats
    )

@main.route('/dashboard/clients')
@login_required
def clients():
    """Display clients page with proper access control"""
    try:
        company_service = CompanyService()
        # Get only client companies (status: client_signed, renewed, upgraded)
        client_statuses = ['client_signed', 'renewed', 'upgraded']
        companies = company_service.get_user_companies(
            user_id=current_user.id,
            status=client_statuses
        )
        
        # Get statistics for clients
        stats = {
            'total_clients': len(companies),
            'active_clients': len([c for c in companies if c['status'] in ['client_signed', 'renewed']]),
            'upgraded_clients': len([c for c in companies if c['status'] == 'upgraded'])
        }
        
        return render_template(
            'dashboard/clients.html',
            companies=companies,
            statistics=stats
        )
    except Exception as e:
        flash(f'Error accessing clients: {str(e)}', 'danger')
        return redirect(url_for('main.dashboard'))

@main.route('/dashboard/admin/companies')
@login_required
@admin_required
def admin_companies():
    # Get filter parameters
    status = request.args.get('status')
    partner_id = request.args.get('partner_id')
    search = request.args.get('search')
    
    # Get companies based on filters
    companies = CompanyService.search_companies(
        user_id=partner_id, 
        status=status,
        query_string=search
    )
    
    # Get company statistics
    statistics = CompanyService.get_company_statistics()
    
    # Get all partners for dropdown
    partners = User.query.all()
    
    # Check if we need to show a specific view
    view = request.args.get('view')
    company_id = request.args.get('company_id')
    
    selected_company = None
    if view and company_id:
        # Get the specific company details
        selected_company = CompanyService.get_company_details(company_id)
    
    return render_template(
        'dashboard/admin/companies.html',
        companies=companies,
        statistics=statistics,
        partners=partners,
        current_status=status,
        current_partner=int(partner_id) if partner_id and partner_id.isdigit() else None,
        current_search=search,
        view=view,
        selected_company=selected_company
    )

@main.route('/dashboard/admin/companies/update-status', methods=['POST'])
@login_required
@admin_required
def update_company_status():
    company_id = request.form.get('company_id')
    new_status = request.form.get('status')
    
    if not company_id or not new_status:
        flash('Missing required information', 'error')
        return redirect(url_for('main.admin_companies'))
    
    try:
        CompanyService.update_status(company_id, new_status)
        flash(f'Company status updated successfully', 'success')
    except Exception as e:
        flash(f'Error updating company status: {str(e)}', 'error')
    
    return redirect(url_for('main.admin_companies'))

@main.route('/dashboard/admin/companies/delete/<int:company_id>', methods=['POST'])
@login_required
@admin_required
def delete_company(company_id):
    """Delete a company"""
    try:
        company = Company.query.get_or_404(company_id)
        company_name = company.name
        
        db.session.delete(company)
        db.session.commit()
        
        flash(f'Company "{company_name}" has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting company: {str(e)}', 'danger')
    
    return redirect(url_for('main.admin_companies'))
