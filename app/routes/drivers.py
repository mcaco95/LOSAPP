from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from app.decorators import operations_required
from app.models.samsara import SamsaraDriver, SamsaraAlert, SamsaraVehicle
from app.models.company import Company
from app import db
import logging
from datetime import datetime, timedelta
from sqlalchemy import or_, func

logger = logging.getLogger(__name__)
bp = Blueprint('drivers', __name__, url_prefix='/drivers')

@bp.route('/')
@login_required
@operations_required
def index():
    """Driver management page"""
    return render_template('drivers/index.html')

@bp.route('/api/drivers')
@login_required
@operations_required
def get_drivers():
    """Get list of drivers with filters and pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search')
        company_id = request.args.get('company_id', type=int)
        status = request.args.get('status')  # active, inactive
        sort_by = request.args.get('sort_by', 'name')
        sort_order = request.args.get('sort_order', 'asc')

        # Start with base query
        query = SamsaraDriver.query.options(
            db.joinedload(SamsaraDriver.company)
        )

        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(
                SamsaraDriver.name.ilike(search_term),
                SamsaraDriver.username.ilike(search_term),
                SamsaraDriver.phone.ilike(search_term),
                SamsaraDriver.email.ilike(search_term)
            ))

        if company_id:
            query = query.filter(SamsaraDriver.company_id == company_id)

        if status:
            if status == 'active':
                query = query.filter(SamsaraDriver.is_active == True)
            elif status == 'inactive':
                query = query.filter(SamsaraDriver.is_active == False)

        # Apply sorting
        valid_sort_fields = {
            'name': SamsaraDriver.name,
            'created_at': SamsaraDriver.created_at,
            'updated_at': SamsaraDriver.updated_at,
            'company_name': Company.name
        }
        
        if sort_by in valid_sort_fields:
            sort_field = valid_sort_fields[sort_by]
            if sort_by == 'company_name':
                query = query.join(Company)
                
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(SamsaraDriver.name.asc())

        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format driver data
        drivers_data = []
        for driver in pagination.items:
            try:
                # Get alert statistics safely
                total_alerts = SamsaraAlert.query.filter_by(driver_id=driver.id).count()
                recent_alerts = SamsaraAlert.query.filter(
                    SamsaraAlert.driver_id == driver.id,
                    SamsaraAlert.created_at >= datetime.utcnow() - timedelta(days=30)
                ).count()
                
                drivers_data.append({
                    'id': driver.id,
                    'driver_id': driver.driver_id,
                    'name': driver.name,
                    'username': driver.username,
                    'phone': driver.phone,
                    'email': driver.email,
                    'license_number': driver.license_number,
                    'license_state': driver.license_state,
                    'license_class': driver.license_class,
                    'company_name': driver.company.name if driver.company else 'No Company',
                    'company_id': driver.company_id,
                    'is_active': driver.is_active,
                    'created_at': driver.created_at.isoformat() if driver.created_at else None,
                    'updated_at': driver.updated_at.isoformat() if driver.updated_at else None,
                    'total_alerts': total_alerts,
                    'recent_alerts': recent_alerts
                })
            except Exception as driver_error:
                logger.error(f"Error processing driver {driver.id}: {str(driver_error)}")
                # Add driver with minimal data if there's an error
                drivers_data.append({
                    'id': driver.id,
                    'driver_id': driver.driver_id,
                    'name': driver.name or 'Unknown',
                    'username': driver.username,
                    'phone': driver.phone,
                    'email': driver.email,
                    'license_number': driver.license_number,
                    'license_state': driver.license_state,
                    'license_class': driver.license_class,
                    'company_name': driver.company.name if driver.company else 'No Company',
                    'company_id': driver.company_id,
                    'is_active': driver.is_active,
                    'created_at': driver.created_at.isoformat() if driver.created_at else None,
                    'updated_at': driver.updated_at.isoformat() if driver.updated_at else None,
                    'total_alerts': 0,
                    'recent_alerts': 0
                })
        
        return jsonify({
            'status': 'success',
            'drivers': drivers_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error fetching drivers: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch drivers: {str(e)}'
        }), 500

@bp.route('/api/drivers/<int:driver_id>')
@login_required
@operations_required
def get_driver_details(driver_id):
    """Get detailed information for a specific driver"""
    try:
        driver = SamsaraDriver.query.options(
            db.joinedload(SamsaraDriver.company)
        ).get_or_404(driver_id)
        
        # Get alert statistics safely
        alerts_query = SamsaraAlert.query.filter_by(driver_id=driver.id)
        total_alerts = alerts_query.count()
        
        # Alert counts by status
        alert_stats = {
            'total': total_alerts,
            'unassigned': alerts_query.filter(SamsaraAlert.status == 'unassigned').count(),
            'in_progress': alerts_query.filter(SamsaraAlert.status == 'in_progress').count(),
            'resolved': alerts_query.filter(SamsaraAlert.status == 'resolved').count(),
            'escalated': alerts_query.filter(SamsaraAlert.status == 'escalated').count()
        }
        
        # Recent alerts (last 10)
        recent_alerts = alerts_query.order_by(SamsaraAlert.created_at.desc()).limit(10).all()
        recent_alerts_data = []
        for alert in recent_alerts:
            try:
                recent_alerts_data.append({
                    'id': alert.id,
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'status': alert.status,
                    'vehicle_name': alert.vehicle.name if alert.vehicle else 'Unknown',
                    'timestamp': alert.timestamp.isoformat() if alert.timestamp else None,
                    'created_at': alert.created_at.isoformat() if alert.created_at else None
                })
            except Exception as alert_error:
                logger.error(f"Error processing alert {alert.id}: {str(alert_error)}")
                # Add alert with minimal data
                recent_alerts_data.append({
                    'id': alert.id,
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'status': alert.status,
                    'vehicle_name': 'Unknown',
                    'timestamp': alert.timestamp.isoformat() if alert.timestamp else None,
                    'created_at': alert.created_at.isoformat() if alert.created_at else None
                })
        
        driver_data = {
            'id': driver.id,
            'driver_id': driver.driver_id,
            'name': driver.name,
            'username': driver.username,
            'phone': driver.phone,
            'email': driver.email,
            'license_number': driver.license_number,
            'license_state': driver.license_state,
            'license_class': driver.license_class,
            'company': {
                'id': driver.company.id,
                'name': driver.company.name
            } if driver.company else None,
            'external_ids': driver.external_ids,
            'is_active': driver.is_active,
            'created_at': driver.created_at.isoformat() if driver.created_at else None,
            'updated_at': driver.updated_at.isoformat() if driver.updated_at else None,
            'alert_stats': alert_stats,
            'recent_alerts': recent_alerts_data,
            'samsara_data': driver.data  # Full Samsara data
        }
        
        return jsonify({
            'status': 'success',
            'driver': driver_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching driver details: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch driver details: {str(e)}'
        }), 500

@bp.route('/api/companies')
@login_required
@operations_required
def get_companies():
    """Get list of companies for filter dropdown"""
    try:
        # Get companies that have drivers
        companies = Company.query.filter(
            Company.id.in_(
                db.session.query(SamsaraDriver.company_id).filter(
                    SamsaraDriver.company_id.isnot(None)
                ).distinct()
            )
        ).all()
        
        companies_data = []
        for company in companies:
            try:
                driver_count = SamsaraDriver.query.filter_by(
                    company_id=company.id, 
                    is_active=True
                ).count()
                companies_data.append({
                    'id': company.id,
                    'name': company.name,
                    'driver_count': driver_count
                })
            except Exception as company_error:
                logger.error(f"Error processing company {company.id}: {str(company_error)}")
                # Add company with minimal data
                companies_data.append({
                    'id': company.id,
                    'name': company.name,
                    'driver_count': 0
                })
        
        return jsonify({
            'status': 'success',
            'companies': companies_data
        })
    except Exception as e:
        logger.error(f"Error fetching companies: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to fetch companies: {str(e)}'
        }), 500

@bp.route('/<int:driver_id>')
@login_required
@operations_required
def driver_details(driver_id):
    """Driver details page"""
    try:
        driver = SamsaraDriver.query.get_or_404(driver_id)
        return render_template('drivers/details.html', driver=driver)
    except Exception as e:
        logger.error(f"Error loading driver details page: {str(e)}")
        flash('Driver not found', 'error')
        return redirect(url_for('drivers.index')) 