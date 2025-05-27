from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app.models.samsara import SamsaraAlert
from .. import db

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/alerts')
@login_required
def alerts_dashboard():
    """User's alert dashboard showing their assigned alerts and metrics"""
    try:
        # Get user's assigned alerts
        alerts = SamsaraAlert.query.filter_by(assigned_user_id=current_user.id)\
            .order_by(SamsaraAlert.created_at.desc())\
            .limit(10)\
            .all()
            
        # Calculate metrics
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        
        # Total active alerts
        active_alerts = SamsaraAlert.query.filter(
            SamsaraAlert.assigned_user_id == current_user.id,
            SamsaraAlert.status.in_(['in_progress', 'escalated'])
        ).count()
        
        # Alerts resolved in last 30 days
        resolved_30d = SamsaraAlert.query.filter(
            SamsaraAlert.assigned_user_id == current_user.id,
            SamsaraAlert.status == 'resolved',
            SamsaraAlert.resolved_at >= thirty_days_ago
        ).count()
        
        # Average resolution time for resolved alerts
        resolution_times = db.session.query(
            func.avg(SamsaraAlert.resolved_at - SamsaraAlert.created_at)
        ).filter(
            SamsaraAlert.assigned_user_id == current_user.id,
            SamsaraAlert.status == 'resolved',
            SamsaraAlert.resolved_at >= thirty_days_ago
        ).scalar()
        
        avg_resolution_hours = round(resolution_times.total_seconds() / 3600, 1) if resolution_times else 0
        
        # Alerts by status
        status_counts = db.session.query(
            SamsaraAlert.status,
            func.count(SamsaraAlert.id)
        ).filter(
            SamsaraAlert.assigned_user_id == current_user.id
        ).group_by(SamsaraAlert.status).all()
        
        status_data = {status: count for status, count in status_counts}
        
        return render_template(
            'dashboard/user_alerts.html',
            alerts=alerts,
            active_alerts=active_alerts,
            resolved_30d=resolved_30d,
            avg_resolution_hours=avg_resolution_hours,
            status_data=status_data,
            timezone=timezone
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in alerts dashboard: {str(e)}")
        flash("An error occurred while loading the dashboard", "error")
        return redirect(url_for('main.index')) 