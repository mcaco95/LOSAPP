from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.decorators import operations_required
from app.models.samsara import DOTInfraction, DOTViolation, DOTInfractionAlert, SamsaraAlert, SamsaraDriver, SamsaraVehicle
from app.models.company import Company
from app import db
import logging
from datetime import datetime, date
import json
from werkzeug.utils import secure_filename
import os

logger = logging.getLogger(__name__)
bp = Blueprint('dot_infractions', __name__, url_prefix='/dot-infractions')

@bp.route('/')
@login_required
@operations_required
def index():
    """DOT Infractions management page"""
    return render_template('dot_infractions/index.html')

@bp.route('/api/companies')
@login_required
@operations_required
def get_companies():
    """Get list of companies with Samsara clients for dropdown"""
    try:
        # Get companies that have active Samsara clients
        companies = Company.query.join(Company.samsara_clients).filter(
            Company.samsara_clients.any(is_active=True)
        ).all()
        
        companies_data = []
        for company in companies:
            companies_data.append({
                'id': company.id,
                'name': company.name,
                'driver_count': company.samsara_drivers.filter_by(is_active=True).count(),
                'vehicle_count': SamsaraVehicle.query.filter_by(company_id=company.id).count()
            })
        
        return jsonify({
            'status': 'success',
            'companies': companies_data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/companies/<int:company_id>/drivers')
@login_required
@operations_required
def get_company_drivers(company_id):
    """Get drivers for a specific company"""
    try:
        drivers = SamsaraDriver.query.filter_by(
            company_id=company_id,
            is_active=True
        ).order_by(SamsaraDriver.name).all()
        
        drivers_data = []
        for driver in drivers:
            drivers_data.append({
                'id': driver.id,
                'driver_id': driver.driver_id,
                'name': driver.name,
                'display_name': driver.display_name,
                'phone': driver.phone,
                'license_state': driver.license_state
            })
        
        return jsonify({
            'status': 'success',
            'drivers': drivers_data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/companies/<int:company_id>/vehicles')
@login_required
@operations_required
def get_company_vehicles(company_id):
    """Get vehicles for a specific company"""
    try:
        vehicles = SamsaraVehicle.query.filter_by(
            company_id=company_id
        ).order_by(SamsaraVehicle.name).all()
        
        vehicles_data = []
        for vehicle in vehicles:
            vehicles_data.append({
                'id': vehicle.id,
                'vehicle_id': vehicle.vehicle_id,
                'name': vehicle.name,
                'vin': vehicle.vin,
                'license_plate': vehicle.license_plate,
                'make': vehicle.make,
                'model': vehicle.model,
                'year': vehicle.year
            })
        
        return jsonify({
            'status': 'success',
            'vehicles': vehicles_data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/api/infractions')
@login_required
@operations_required
def get_infractions():
    """Get list of DOT infractions with filters"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Start with base query
        query = DOTInfraction.query.options(
            db.joinedload(DOTInfraction.violations),
            db.joinedload(DOTInfraction.creator),
            db.joinedload(DOTInfraction.linked_alerts)
        )
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(db.or_(
                DOTInfraction.report_number.ilike(search_term),
                DOTInfraction.carrier_name.ilike(search_term),
                DOTInfraction.driver_name.ilike(search_term),
                DOTInfraction.us_dot.ilike(search_term)
            ))
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(DOTInfraction.inspection_date >= from_date)
            except ValueError:
                pass
                
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(DOTInfraction.inspection_date <= to_date)
            except ValueError:
                pass
        
        # Order by inspection date descending
        query = query.order_by(DOTInfraction.inspection_date.desc())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page)
        
        # Format infractions data
        infractions_data = []
        for infraction in pagination.items:
            infractions_data.append({
                'id': infraction.id,
                'report_number': infraction.report_number,
                'carrier_name': infraction.carrier_name,
                'us_dot': infraction.us_dot,
                'driver_name': infraction.driver_name,
                'inspection_date': infraction.inspection_date.isoformat() if infraction.inspection_date else None,
                'inspection_location': infraction.inspection_location,
                'violation_count': infraction.violation_count,
                'severity_summary': infraction.severity_summary,
                'linked_alerts_count': len(infraction.linked_alerts),
                'created_by': infraction.creator.name if infraction.creator else 'Unknown',
                'created_at': infraction.created_at.isoformat() if infraction.created_at else None
            })
        
        return jsonify({
            'status': 'success',
            'infractions': infractions_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error fetching infractions: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch infractions'
        }), 500

@bp.route('/api/infractions/<int:infraction_id>')
@login_required
@operations_required
def get_infraction_details(infraction_id):
    """Get detailed information for a specific infraction"""
    try:
        infraction = DOTInfraction.query.options(
            db.joinedload(DOTInfraction.violations),
            db.joinedload(DOTInfraction.creator),
            db.joinedload(DOTInfraction.linked_alerts).joinedload(DOTInfractionAlert.alert)
        ).get_or_404(infraction_id)
        
        # Format violations
        violations_data = []
        for violation in infraction.violations:
            violations_data.append({
                'id': violation.id,
                'unit_type': violation.unit_type,
                'oos_indicator': violation.oos_indicator,
                'section_code': violation.section_code,
                'violation_description': violation.violation_description,
                'violation_category': violation.violation_category,
                'emergency_equipment': violation.emergency_equipment,
                'citation': violation.citation
            })
        
        # Format linked alerts
        linked_alerts_data = []
        for link in infraction.linked_alerts:
            linked_alerts_data.append({
                'id': link.id,
                'alert_id': link.alert.id,
                'alert_type': link.alert.alert_type,
                'alert_timestamp': link.alert.timestamp.isoformat() if link.alert.timestamp else None,
                'vehicle_name': link.alert.vehicle.name if link.alert.vehicle else 'Unknown',
                'link_reason': link.link_reason,
                'linked_by': link.linker.name if link.linker else 'Unknown',
                'linked_at': link.created_at.isoformat() if link.created_at else None
            })
        
        infraction_data = {
            'id': infraction.id,
            'carrier_name': infraction.carrier_name,
            'carrier_address': infraction.carrier_address,
            'us_dot': infraction.us_dot,
            'mc_number': infraction.mc_number,
            'state_id': infraction.state_id,
            'report_number': infraction.report_number,
            'report_state': infraction.report_state,
            'inspection_state': infraction.inspection_state,
            'inspection_date': infraction.inspection_date.isoformat() if infraction.inspection_date else None,
            'start_end_time': infraction.start_end_time,
            'inspection_level': infraction.inspection_level,
            'inspection_facility': infraction.inspection_facility,
            'post_crash': infraction.post_crash,
            'inspection_location': infraction.inspection_location,
            'hazmat_placard_required': infraction.hazmat_placard_required,
            'inspection_county': infraction.inspection_county,
            'driver_name': infraction.driver_name,
            'driver_age': infraction.driver_age,
            'driver_license_state': infraction.driver_license_state,
            'shipper_info_available': infraction.shipper_info_available,
            'vehicles_data': infraction.vehicles_data,
            'pdf_file_path': infraction.pdf_file_path,
            'violations': violations_data,
            'linked_alerts': linked_alerts_data,
            'created_by': infraction.creator.name if infraction.creator else 'Unknown',
            'created_at': infraction.created_at.isoformat() if infraction.created_at else None
        }
        
        return jsonify({
            'status': 'success',
            'infraction': infraction_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching infraction details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch infraction details'
        }), 500

@bp.route('/api/infractions', methods=['POST'])
@login_required
@operations_required
def create_infraction():
    """Create a new DOT infraction"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('report_number'):
            return jsonify({
                'status': 'error',
                'message': 'Report number is required'
            }), 400
            
        if not data.get('inspection_date'):
            return jsonify({
                'status': 'error',
                'message': 'Inspection date is required'
            }), 400
        
        # Parse inspection date
        try:
            inspection_date = datetime.strptime(data['inspection_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'Invalid inspection date format'
            }), 400
        
        # Create infraction
        infraction = DOTInfraction(
            company_id=data.get('company_id'),
            carrier_name=data.get('carrier_name'),
            carrier_address=data.get('carrier_address'),
            us_dot=data.get('us_dot'),
            mc_number=data.get('mc_number'),
            state_id=data.get('state_id'),
            report_number=data['report_number'],
            report_state=data.get('report_state'),
            inspection_state=data.get('inspection_state'),
            inspection_date=inspection_date,
            start_end_time=data.get('start_end_time'),
            inspection_level=data.get('inspection_level'),
            inspection_facility=data.get('inspection_facility'),
            post_crash=data.get('post_crash'),
            inspection_location=data.get('inspection_location'),
            hazmat_placard_required=data.get('hazmat_placard_required'),
            inspection_county=data.get('inspection_county'),
            primary_driver_id=data.get('primary_driver_id'),
            driver_name=data.get('driver_name'),  # Fallback for manual entry
            driver_age=data.get('driver_age'),
            driver_license_state=data.get('driver_license_state'),
            shipper_info_available=data.get('shipper_info_available', False),
            linked_vehicles=data.get('linked_vehicles', []),  # Array of vehicle IDs
            vehicles_data=data.get('vehicles_data', []),  # Manual vehicle data
            created_by=current_user.id
        )
        
        db.session.add(infraction)
        db.session.flush()  # Get the ID
        
        # Create violations
        violations_data = data.get('violations', [])
        for violation_data in violations_data:
            if not violation_data.get('section_code') or not violation_data.get('violation_description'):
                continue  # Skip incomplete violations
                
            violation = DOTViolation(
                infraction_id=infraction.id,
                unit_type=violation_data.get('unit_type'),
                oos_indicator=violation_data.get('oos_indicator'),
                section_code=violation_data['section_code'],
                violation_description=violation_data['violation_description'],
                violation_category=violation_data.get('violation_category'),
                emergency_equipment=violation_data.get('emergency_equipment'),
                citation=violation_data.get('citation')
            )
            db.session.add(violation)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Infraction created successfully',
            'infraction_id': infraction.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating infraction: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to create infraction'
        }), 500

@bp.route('/api/infractions/<int:infraction_id>/link-alert', methods=['POST'])
@login_required
@operations_required
def link_alert_to_infraction(infraction_id):
    """Link a Samsara alert to a DOT infraction"""
    try:
        data = request.get_json()
        alert_id = data.get('alert_id')
        link_reason = data.get('link_reason', '')
        
        if not alert_id:
            return jsonify({
                'status': 'error',
                'message': 'Alert ID is required'
            }), 400
        
        # Verify infraction exists
        infraction = DOTInfraction.query.get_or_404(infraction_id)
        
        # Verify alert exists
        alert = SamsaraAlert.query.get_or_404(alert_id)
        
        # Check if link already exists
        existing_link = DOTInfractionAlert.query.filter_by(
            infraction_id=infraction_id,
            alert_id=alert_id
        ).first()
        
        if existing_link:
            return jsonify({
                'status': 'error',
                'message': 'This alert is already linked to this infraction'
            }), 400
        
        # Create link
        link = DOTInfractionAlert(
            infraction_id=infraction_id,
            alert_id=alert_id,
            linked_by=current_user.id,
            link_reason=link_reason
        )
        
        db.session.add(link)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Alert linked to infraction successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error linking alert to infraction: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to link alert to infraction'
        }), 500

@bp.route('/api/search-alerts')
@login_required
@operations_required
def search_alerts():
    """Search for alerts to link to infractions"""
    try:
        search = request.args.get('search', '')
        limit = request.args.get('limit', 10, type=int)
        
        query = SamsaraAlert.query.options(
            db.joinedload(SamsaraAlert.vehicle),
            db.joinedload(SamsaraAlert.client)
        )
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(db.or_(
                SamsaraAlert.alert_id.ilike(search_term),
                SamsaraAlert.alert_type.ilike(search_term),
                SamsaraAlert.description.ilike(search_term)
            ))
        
        alerts = query.order_by(SamsaraAlert.timestamp.desc()).limit(limit).all()
        
        alerts_data = []
        for alert in alerts:
            alerts_data.append({
                'id': alert.id,
                'alert_id': alert.alert_id,
                'alert_type': alert.alert_type,
                'timestamp': alert.timestamp.isoformat() if alert.timestamp else None,
                'vehicle_name': alert.vehicle.name if alert.vehicle else 'Unknown',
                'client_name': alert.client.name if alert.client else 'Unknown',
                'status': alert.status
            })
        
        return jsonify({
            'status': 'success',
            'alerts': alerts_data
        })
        
    except Exception as e:
        logger.error(f"Error searching alerts: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to search alerts'
        }), 500 