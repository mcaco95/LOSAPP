from flask import Blueprint, request, jsonify, render_template
from app.services.samsara_client import SamsaraService
from app.models.samsara import SamsaraClient, SamsaraAlert
from app import db
import logging
from flask_login import login_required, current_user
from app.decorators import operations_required
from datetime import datetime

logger = logging.getLogger(__name__)
bp = Blueprint('samsara', __name__, url_prefix='/samsara')
samsara_service = SamsaraService()

def webhook():
    """Endpoint for receiving Samsara webhook events"""
    try:
        # Log the incoming request
        logger.info("Received Samsara webhook request")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Get the event data from the request
        event_data = request.get_json()
        logger.info(f"Event data: {event_data}")
        
        # Process the webhook event
        success = samsara_service.process_webhook_event(event_data)
        
        if success:
            logger.info("Successfully processed webhook event")
            return jsonify({'status': 'success'}), 200
        else:
            logger.error("Failed to process webhook event")
            return jsonify({'status': 'error', 'message': 'Failed to process webhook event'}), 500
            
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def test_webhook():
    """Test endpoint for simulating Samsara webhook events"""
    try:
        # Sample alert event
        test_event = {
            "eventType": "alert",
            "webhookId": "test-webhook-123",
            "timestamp": "2025-04-15T12:00:00Z",
            "data": {
                "alertId": "test-alert-123",
                "vehicleId": "test-vehicle-123",
                "vehicleName": "Test Vehicle",
                "alertType": "test_alert",
                "severity": "high",
                "description": "This is a test alert",
                "timestamp": "2025-04-15T12:00:00Z"
            }
        }
        
        logger.info("Processing test webhook event")
        success = samsara_service.process_webhook_event(test_event)
        
        if success:
            logger.info("Successfully processed test webhook event")
            return jsonify({
                'status': 'success',
                'message': 'Test webhook processed successfully'
            }), 200
        else:
            logger.error("Failed to process test webhook event")
            return jsonify({
                'status': 'error',
                'message': 'Failed to process test webhook event'
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing test webhook: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/vehicles', methods=['GET'])
def get_vehicles():
    """Endpoint for fetching vehicles from Samsara"""
    try:
        vehicles = samsara_service.get_vehicles()
        if vehicles:
            return jsonify({'status': 'success', 'data': vehicles}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Failed to fetch vehicles'}), 500
    except Exception as e:
        logger.error(f"Error fetching vehicles: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/alerts', methods=['GET'])
@login_required
def get_alerts():
    """Get alerts with pagination"""
    try:
        per_page = request.args.get('per_page', 20, type=int)
        page = request.args.get('page', 1, type=int)
        
        # Query alerts with vehicle and client relationships
        alerts = SamsaraAlert.query.options(
            db.joinedload(SamsaraAlert.vehicle),
            db.joinedload(SamsaraAlert.client)
        ).order_by(
            SamsaraAlert.timestamp.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Format alerts with vehicle name and client name
        formatted_alerts = [{
            'id': alert.id,
            'alert_id': alert.alert_id,
            'vehicle_id': alert.vehicle_id,
            'vehicle_name': alert.vehicle.name if alert.vehicle else 'Unknown',
            'client_name': alert.client.name if alert.client else 'Unknown',
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'status': alert.status,
            'description': alert.description,
            'timestamp': alert.timestamp.isoformat(),
            'created_at': alert.created_at.isoformat()
        } for alert in alerts.items]
        
        return jsonify({
            'status': 'success',
            'alerts': formatted_alerts,
            'total': alerts.total,
            'pages': alerts.pages,
            'current_page': alerts.page
        })
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch alerts'
        }), 500

@bp.route('/clients')
@login_required
@operations_required
def clients():
    """Display Samsara clients management page"""
    clients = SamsaraClient.query.all()
    return render_template('samsara/clients.html', clients=clients)

@bp.route('/clients', methods=['POST'])
@login_required
@operations_required
def create_client():
    """Create a new Samsara client"""
    data = request.get_json()
    
    # Check if org_id already exists
    existing = SamsaraClient.query.filter_by(org_id=data['org_id']).first()
    if existing:
        return jsonify({
            'success': False,
            'message': 'A client with this Organization ID already exists'
        }), 400
    
    try:
        client = SamsaraClient(
            name=data['name'],
            org_id=data['org_id'],
            api_key=data['api_key'],
            webhook_id=data.get('webhook_id'),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(client)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client added successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@bp.route('/clients/<int:client_id>')
@login_required
@operations_required
def get_client(client_id):
    """Get a specific Samsara client"""
    client = SamsaraClient.query.get_or_404(client_id)
    return jsonify({
        'id': client.id,
        'name': client.name,
        'org_id': client.org_id,
        'api_key': client.api_key,
        'webhook_id': client.webhook_id,
        'is_active': client.is_active
    })

@bp.route('/clients/<int:client_id>', methods=['PUT'])
@login_required
@operations_required
def update_client(client_id):
    """Update a Samsara client"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        data = request.get_json()
        
        # Log the incoming data
        logger.info(f"Updating client {client_id} with data: {data}")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['name', 'org_id', 'api_key']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Check if org_id is being changed and if it conflicts
        if str(client.org_id) != str(data['org_id']):
            existing = SamsaraClient.query.filter_by(org_id=data['org_id']).first()
            if existing and existing.id != client_id:
                return jsonify({
                    'success': False,
                    'message': 'A client with this Organization ID already exists'
                }), 400
        
        # Update fields
        client.name = data['name']
        client.org_id = data['org_id']
        client.api_key = data['api_key']
        client.webhook_id = data.get('webhook_id', '')
        client.is_active = data.get('is_active', True)
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating client {client_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@bp.route('/clients/<int:client_id>', methods=['DELETE'])
@login_required
@operations_required
def delete_client(client_id):
    """Delete a Samsara client"""
    client = SamsaraClient.query.get_or_404(client_id)
    
    try:
        db.session.delete(client)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Register the routes
bp.add_url_rule('/webhook', 'webhook', webhook, methods=['POST'])
bp.add_url_rule('/test-webhook', 'test_webhook', test_webhook, methods=['POST']) 