from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
from app.services.samsara_client import SamsaraService
from app.models.samsara import SamsaraClient, SamsaraAlert, SamsaraAlertAssignment, SamsaraAlertActivity, SamsaraVehicle, SamsaraDriver
from app import db
import logging
from flask_login import login_required, current_user
from app.decorators import operations_required
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import or_

logger = logging.getLogger(__name__)
bp = Blueprint('samsara', __name__, url_prefix='/samsara')
samsara_service = SamsaraService()

def webhook():
    """Endpoint for receiving Samsara webhook events"""
    try:
        # Get the event data from the request
        event_data = request.get_json()
        
        # Log only essential webhook information
        if event_data:
            logger.info("=== Samsara Webhook Event ===")
            logger.info(f"Event Type: {event_data.get('eventType')}")
            if 'conditions' in event_data and event_data['conditions']:
                condition = event_data['conditions'][0]
                logger.info(f"Description: {condition.get('description')}")
                logger.info(f"Details Type: {next(iter(condition.get('details', {})), 'Unknown')}")
        
        # Process the webhook event
        success = samsara_service.process_webhook_event(event_data)
        
        if success:
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
def get_all_vehicles():
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

@bp.route('/alerts')
@login_required
@operations_required
def alerts():
    """Get list of alerts with filters and sorting"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)  # Changed default to 20
        status = request.args.get('status')
        assigned_user_id = request.args.get('assigned_user_id')
        client_id = request.args.get('client_id', type=int)
        date = request.args.get('date')
        search = request.args.get('search')
        
        # New sorting parameters
        sort_by = request.args.get('sort_by', 'timestamp')  # Default sort by timestamp
        sort_order = request.args.get('sort_order', 'desc')  # Default descending

        # Start with base query
        query = SamsaraAlert.query.options(
            db.joinedload(SamsaraAlert.vehicle),
            db.joinedload(SamsaraAlert.client),
            db.joinedload(SamsaraAlert.assigned_user),
            db.joinedload(SamsaraAlert.activities).joinedload(SamsaraAlertActivity.user)
        )

        # Apply filters
        if status:
            query = query.filter(SamsaraAlert.status == status)
        
        if assigned_user_id == 'none':
            query = query.filter(SamsaraAlert.assigned_user_id.is_(None))
        elif assigned_user_id and assigned_user_id.isdigit():
            query = query.filter(SamsaraAlert.assigned_user_id == int(assigned_user_id))

        if client_id:
            query = query.filter(SamsaraAlert.client_id == client_id)

        if date:
            try:
                filter_date = datetime.strptime(date, '%Y-%m-%d')
                next_date = filter_date + timedelta(days=1)
                query = query.filter(
                    SamsaraAlert.timestamp >= filter_date,
                    SamsaraAlert.timestamp < next_date
                )
            except ValueError:
                pass

        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(
                SamsaraAlert.alert_id.ilike(search_term),
                SamsaraAlert.description.ilike(search_term),
                SamsaraAlert.alert_type.ilike(search_term)
            ))

        # Apply sorting
        valid_sort_fields = {
            'timestamp': SamsaraAlert.timestamp,
            'created_at': SamsaraAlert.created_at,
            'updated_at': SamsaraAlert.updated_at,
            'alert_type': SamsaraAlert.alert_type,
            'severity': SamsaraAlert.severity,
            'status': SamsaraAlert.status,
            'client_name': SamsaraClient.name,
            'vehicle_name': SamsaraVehicle.name
        }
        
        if sort_by in valid_sort_fields:
            sort_field = valid_sort_fields[sort_by]
            if sort_by in ['client_name']:
                query = query.join(SamsaraClient)
            elif sort_by in ['vehicle_name']:
                query = query.join(SamsaraVehicle)
                
            if sort_order.lower() == 'asc':
                query = query.order_by(sort_field.asc())
            else:
                query = query.order_by(sort_field.desc())
        else:
            # Default sorting
            query = query.order_by(SamsaraAlert.timestamp.desc())

        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page)
        
        # Enhanced alert data with new fields
        alerts_data = []
        for alert in pagination.items:
            # Get latest note from activities
            latest_note = None
            latest_note_activity = None
            for activity in alert.activities:
                if activity.activity_type == 'note' and activity.notes:
                    latest_note = activity.notes
                    latest_note_activity = activity
                    break
            
            # Get last edited by from most recent activity
            last_edited_by = None
            if alert.activities:
                last_activity = alert.activities[0]  # Most recent (ordered desc)
                last_edited_by = {
                    'id': last_activity.user.id if last_activity.user else None,
                    'name': last_activity.user.name if last_activity.user else 'System'
                }
            
            alert_data = {
                'id': alert.id,
                'alert_id': alert.alert_id,
                'timestamp': alert.timestamp.replace(tzinfo=timezone.utc).isoformat() if alert.timestamp else None,
                'created_at': alert.created_at.replace(tzinfo=timezone.utc).isoformat() if alert.created_at else None,
                'updated_at': alert.updated_at.replace(tzinfo=timezone.utc).isoformat() if alert.updated_at else None,
                'vehicle_name': alert.vehicle.name if alert.vehicle else 'Unknown',
                'vehicle_id': alert.vehicle_id,
                'driver_name': alert.driver.name if alert.driver else (_extract_driver_info(alert.data) or 'Unknown'),
                'driver_id': alert.driver_id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'status': alert.status,
                'client_name': alert.client.name if alert.client else 'Unknown',
                'assigned_to': {
                    'id': alert.assigned_user.id,
                    'name': alert.assigned_user.name
                } if alert.assigned_user else None,
                'location': _format_location(alert.data) if alert.data else None,
                'latest_note': latest_note,
                'latest_note_truncated': latest_note[:50] + '...' if latest_note and len(latest_note) > 50 else latest_note,
                'last_edited_by': last_edited_by
            }
            alerts_data.append(alert_data)
        
        return jsonify({
            'status': 'success',
            'alerts': alerts_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page,
            'sort_by': sort_by,
            'sort_order': sort_order
        })
    except Exception as e:
        logger.error(f"Error fetching alerts: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch alerts'
        }), 500

@bp.route('/alerts/<int:alert_id>', methods=['GET'])
@login_required
def get_alert_details(alert_id):
    """Get detailed information for a specific alert"""
    try:
        alert = SamsaraAlert.query.options(
            db.joinedload(SamsaraAlert.vehicle),
            db.joinedload(SamsaraAlert.client),
            db.joinedload(SamsaraAlert.resolver),
            db.joinedload(SamsaraAlert.activities).joinedload(SamsaraAlertActivity.user)
        ).get_or_404(alert_id)
        
        # Get activities in chronological order (newest first)
        activities = []
        for activity in alert.activities:
            activities.append({
                'id': activity.id,
                'activity_type': activity.activity_type,
                'description': activity.description,
                'user_name': activity.user.name if activity.user else 'System',
                'old_value': activity.old_value,
                'new_value': activity.new_value,
                'notes': activity.notes,
                'metadata': activity.activity_metadata,
                'created_at': activity.formatted_timestamp
            })
        
        alert_data = {
            'id': alert.id,
            'alert_id': alert.alert_id,
            'vehicle_id': alert.vehicle_id,
            'vehicle_name': alert.vehicle.name if alert.vehicle else 'Unknown',
            'client_id': alert.client_id,
            'client_name': alert.client.name if alert.client else 'Unknown',
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'status': alert.status,
            'description': alert.description,
            'timestamp': alert.timestamp.replace(tzinfo=timezone.utc).isoformat() if alert.timestamp else None,
            'created_at': alert.created_at.replace(tzinfo=timezone.utc).isoformat() if alert.created_at else None,
            'driver_id': alert.driver_id,
            'driver_name': alert.driver.name if alert.driver else (_extract_driver_info(alert.data) or 'Unknown'),
            'driver_phone': alert.driver.phone if alert.driver else None,
            'location': _format_location(alert.data) if alert.data else None,
            'resolution': alert.resolution,
            'resolved_at': alert.resolved_at.replace(tzinfo=timezone.utc).isoformat() if alert.resolved_at else None,
            'resolved_by': alert.resolver.username if alert.resolver else None,
            'assigned_to': {
                'id': alert.assigned_user.id,
                'name': alert.assigned_user.name
            } if alert.assigned_user else None,
            'tags': alert.tags or [],
            'data': alert.data,
            'activities': activities
        }
        
        return jsonify({
            'status': 'success',
            'alert': alert_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching alert details: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch alert details'
        }), 500

@bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    """Resolve an alert"""
    try:
        data = request.get_json()
        resolution = data.get('resolution')
        
        if not resolution:
            return jsonify({
                'status': 'error',
                'message': 'Resolution notes are required'
            }), 400
            
        alert = SamsaraAlert.query.get_or_404(alert_id)
        
        if alert.status == 'resolved':
            return jsonify({
                'status': 'error',
                'message': 'Alert is already resolved'
            }), 400
            
        alert.status = 'resolved'
        alert.resolution = resolution
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = current_user.id
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Alert resolved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to resolve alert'
        }), 500

@bp.route('/alerts/<int:alert_id>/assign', methods=['POST'])
@login_required
@operations_required
def assign_alert(alert_id):
    """Assign or unassign an alert to/from a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        alert = SamsaraAlert.query.get_or_404(alert_id)
        old_assignee = alert.assigned_user.name if alert.assigned_user else None
        
        # Handle unassignment
        if not user_id or user_id == '':
            alert.assigned_user_id = None
            alert.status = 'unassigned'
            alert.updated_at = datetime.utcnow()
            
            # Add activity record
            alert.add_activity(
                activity_type='assignment',
                description=f'Alert unassigned from {old_assignee}' if old_assignee else 'Alert unassigned',
                user_id=current_user.id,
                old_value=old_assignee,
                new_value=None
            )
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Alert unassigned successfully'
            })
        
        # Get new assignee info
        from app.models.user import User
        new_assignee = User.query.get(int(user_id))
        if not new_assignee:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 400
        
        # Update alert assignment
        alert.assigned_user_id = int(user_id)
        alert.status = 'in_progress'
        alert.updated_at = datetime.utcnow()
        
        # Add activity record
        alert.add_activity(
            activity_type='assignment',
            description=f'Alert assigned to {new_assignee.name}',
            user_id=current_user.id,
            old_value=old_assignee,
            new_value=new_assignee.name
        )
        
        # Create assignment record
        assignment = SamsaraAlertAssignment(
            alert_id=alert.id,
            assigned_to=int(user_id),
            assigned_by=current_user.id,
            status='assigned',
            priority=alert.priority
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Alert assigned successfully'
        })
        
    except Exception as e:
        logger.error(f"Error assigning alert: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to assign alert'
        }), 500

@bp.route('/alerts/<int:alert_id>/status', methods=['PUT'])
@login_required
@operations_required
def update_alert_status(alert_id):
    """Update the status or severity of an alert"""
    try:
        data = request.get_json()
        logger.info(f"Received update request for alert {alert_id}: {data}")
        
        new_status = data.get('status')
        new_severity = data.get('severity')
        notes = data.get('notes')
        
        # Clean up notes - convert None to empty string and strip whitespace
        if notes is None:
            notes = ''
        elif isinstance(notes, str):
            notes = notes.strip()
        else:
            notes = str(notes).strip() if notes else ''
        
        if not new_status and not new_severity:
            logger.warning("Neither status nor severity provided in request")
            return jsonify({
                'status': 'error',
                'message': 'Either status or severity is required'
            }), 400
            
        alert = SamsaraAlert.query.get_or_404(alert_id)
        logger.info(f"Current alert state - Status: {alert.status}, Severity: {alert.severity}")
        
        # Track if any changes were made
        changes_made = False
        
        if new_status:
            # Validate status value
            valid_statuses = ['unassigned', 'in_progress', 'resolved', 'escalated']
            if new_status.lower() not in valid_statuses:
                logger.warning(f"Invalid status value provided: {new_status}")
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                }), 400
                
            # Update alert status
            if alert.status != new_status.lower():
                old_status = alert.status
                alert.status = new_status.lower()
                changes_made = True
                logger.info(f"Setting status to: {new_status.lower()}")
                
                # Add activity record for status change
                alert.add_activity(
                    activity_type='status_change',
                    description=f'Status changed from {old_status} to {new_status.lower()}',
                    user_id=current_user.id,
                    old_value=old_status,
                    new_value=new_status.lower(),
                    notes=notes
                )
                
                # Handle assignment based on status
                if new_status.lower() == 'unassigned':
                    if alert.assigned_user_id:
                        old_assignee = alert.assigned_user.name if alert.assigned_user else None
                        alert.assigned_user_id = None
                        alert.add_activity(
                            activity_type='assignment',
                            description=f'Alert unassigned from {old_assignee} due to status change',
                            user_id=current_user.id,
                            old_value=old_assignee,
                            new_value=None
                        )
                        logger.info("Removing assignment due to unassigned status")
                elif new_status.lower() == 'in_progress' and not alert.assigned_user_id:
                    # If moving to in_progress and no assignee, assign to current user
                    alert.assigned_user_id = current_user.id
                    alert.add_activity(
                        activity_type='assignment',
                        description=f'Alert auto-assigned to {current_user.name}',
                        user_id=current_user.id,
                        old_value=None,
                        new_value=current_user.name
                    )
                    logger.info(f"Auto-assigning to current user: {current_user.id}")
                
                # Handle resolution
                if new_status.lower() == 'resolved':
                    alert.resolved_at = datetime.utcnow()
                    alert.resolved_by = current_user.id
                    if notes:
                        alert.add_activity(
                            activity_type='resolution',
                            description='Alert resolved',
                            user_id=current_user.id,
                            notes=notes
                        )
                    logger.info("Setting resolved timestamp and user")
        
        if new_severity:
            # Validate severity value
            valid_severities = ['critical', 'high', 'medium', 'low']
            if new_severity.lower() not in valid_severities:
                logger.warning(f"Invalid severity value provided: {new_severity}")
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid severity. Must be one of: {", ".join(valid_severities)}'
                }), 400
                
            # Update alert severity
            if alert.severity != new_severity.lower():
                old_severity = alert.severity
                alert.severity = new_severity.lower()
                changes_made = True
                logger.info(f"Setting severity to: {new_severity.lower()}")
                
                # Add activity record for severity change
                alert.add_activity(
                    activity_type='severity_change',
                    description=f'Severity changed from {old_severity} to {new_severity.lower()}',
                    user_id=current_user.id,
                    old_value=old_severity,
                    new_value=new_severity.lower(),
                    notes=notes
                )
        
        if changes_made:
            alert.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info("Successfully updated alert")
            
            return jsonify({
                'status': 'success',
                'message': 'Alert updated successfully',
                'changes': {
                    'status': new_status.lower() if new_status else None,
                    'severity': new_severity.lower() if new_severity else None
                }
            })
        else:
            logger.info("No changes needed - values already set")
            return jsonify({
                'status': 'success',
                'message': 'No changes needed'
            })
        
    except Exception as e:
        logger.error(f"Error updating alert: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/alerts/<int:alert_id>/notes', methods=['POST'])
@login_required
def add_alert_note(alert_id):
    """Add a note/comment to an alert"""
    try:
        data = request.get_json()
        notes = data.get('notes')
        
        if not notes or not notes.strip():
            return jsonify({
                'status': 'error',
                'message': 'Notes cannot be empty'
            }), 400
            
        alert = SamsaraAlert.query.get_or_404(alert_id)
        
        # Add activity record for the note
        alert.add_activity(
            activity_type='note',
            description='Note added',
            user_id=current_user.id,
            notes=notes.strip()
        )
        
        alert.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Note added successfully'
        })
        
    except Exception as e:
        logger.error(f"Error adding note to alert: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to add note'
        }), 500

@bp.route('/alerts/<int:alert_id>/activities', methods=['GET'])
@login_required
def get_alert_activities(alert_id):
    """Get all activities for an alert"""
    try:
        alert = SamsaraAlert.query.get_or_404(alert_id)
        
        activities = SamsaraAlertActivity.query.filter_by(alert_id=alert_id)\
            .options(db.joinedload(SamsaraAlertActivity.user))\
            .order_by(SamsaraAlertActivity.created_at.desc())\
            .all()
        
        activities_data = []
        for activity in activities:
            activities_data.append({
                'id': activity.id,
                'activity_type': activity.activity_type,
                'description': activity.description,
                'user_name': activity.user.name if activity.user else 'System',
                'old_value': activity.old_value,
                'new_value': activity.new_value,
                'notes': activity.notes,
                'metadata': activity.activity_metadata,
                'created_at': activity.formatted_timestamp
            })
        
        return jsonify({
            'status': 'success',
            'activities': activities_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching alert activities: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch activities'
        }), 500

@bp.route('/alerts/<int:alert_id>/call-activity', methods=['POST'])
@login_required
def add_call_activity(alert_id):
    """Add a call activity to an alert"""
    try:
        data = request.get_json()
        activity_type = data.get('activity_type')
        description = data.get('description')
        notes = data.get('notes')
        
        if not activity_type or not description:
            return jsonify({
                'status': 'error',
                'message': 'Activity type and description are required'
            }), 400
            
        # Validate activity type
        valid_call_types = ['call_initiated', 'call_completed']
        if activity_type not in valid_call_types:
            return jsonify({
                'status': 'error',
                'message': f'Invalid call activity type. Must be one of: {", ".join(valid_call_types)}'
            }), 400
            
        alert = SamsaraAlert.query.get_or_404(alert_id)
        
        # Add activity record for the call
        alert.add_activity(
            activity_type=activity_type,
            description=description,
            user_id=current_user.id,
            notes=notes
        )
        
        alert.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Call activity added successfully'
        })
        
    except Exception as e:
        logger.error(f"Error adding call activity to alert: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to add call activity'
        }), 500

def _extract_driver_info(data):
    """
    Helper function to recursively extract driver information from any nested structure.
    Returns the first found driver name or None if not found.
    """
    def find_driver(obj):
        if not obj or not isinstance(obj, (dict, list)):
            return None
            
        # If it's a dictionary
        if isinstance(obj, dict):
            # Direct driver object check
            if 'driver' in obj and isinstance(obj['driver'], dict):
                driver = obj['driver']
                if 'name' in driver:
                    return driver['name']
            
            # Special case for unassigned driving
            if 'unassignedDriving' in obj:
                return 'Unassigned'
                
            # Check geofence events
            if 'geofenceEntry' in obj or 'geofenceExit' in obj:
                event_data = obj.get('geofenceEntry') or obj.get('geofenceExit')
                if event_data and 'vehicle' in event_data:
                    vehicle = event_data['vehicle']
                    if 'driver' in vehicle and isinstance(vehicle['driver'], dict):
                        return vehicle['driver'].get('name')
            
            # Recursively search all values
            for key, value in obj.items():
                result = find_driver(value)
                if result:
                    return result
                    
        # If it's a list
        elif isinstance(obj, list):
            for item in obj:
                result = find_driver(item)
                if result:
                    return result
                    
        return None
        
    try:
        return find_driver(data)
    except Exception as e:
        logger.error(f"Error extracting driver info: {str(e)}")
        return None

def _format_location(data):
    """
    Helper function to recursively extract and format location data from any nested structure.
    Returns the first found valid location in order of preference:
    1. Address
    2. Geofence
    3. Coordinates
    4. Vehicle location (if available)
    """
    def find_location(obj):
        if not obj or not isinstance(obj, (dict, list)):
            return None
            
        # If it's a dictionary
        if isinstance(obj, dict):
            # Check for geofence events first (they have the most complete location data)
            if 'geofenceEntry' in obj or 'geofenceExit' in obj:
                event_data = obj.get('geofenceEntry') or obj.get('geofenceExit')
                if event_data and 'address' in event_data:
                    address = event_data['address']
                    if 'formattedAddress' in address:
                        return address['formattedAddress']
                    elif 'name' in address:
                        return f"Geofence: {address['name']}"
            
            # Check for location object
            if 'location' in obj:
                loc = obj['location']
                if isinstance(loc, dict):
                    # Prefer address if available
                    if 'address' in loc:
                        return loc['address']
                    # Fall back to coordinates
                    if 'latitude' in loc and 'longitude' in loc:
                        return f"{loc['latitude']:.6f}, {loc['longitude']:.6f}"
            
            # Check for geofence
            if 'geofence' in obj and isinstance(obj['geofence'], dict):
                if 'name' in obj['geofence']:
                    return f"Geofence: {obj['geofence']['name']}"
                elif 'polygon' in obj['geofence']:
                    vertices = obj['geofence']['polygon'].get('vertices', [])
                    if vertices:
                        first_vertex = vertices[0]
                        return f"{first_vertex['latitude']:.6f}, {first_vertex['longitude']:.6f}"
                elif 'circle' in obj['geofence']:
                    circle = obj['geofence']['circle']
                    return f"{circle['latitude']:.6f}, {circle['longitude']:.6f}"
                
            # Check for direct lat/long
            if all(k in obj for k in ['latitude', 'longitude']):
                return f"{obj['latitude']:.6f}, {obj['longitude']:.6f}"
                
            # Check for vehicle location in various structures
            if 'vehicle' in obj and isinstance(obj['vehicle'], dict):
                vehicle = obj['vehicle']
                if 'location' in vehicle:
                    loc = vehicle['location']
                    if isinstance(loc, dict):
                        if 'address' in loc:
                            return loc['address']
                        if 'latitude' in loc and 'longitude' in loc:
                            return f"{loc['latitude']:.6f}, {loc['longitude']:.6f}"
            
            # Recursively search all values
            for key, value in obj.items():
                result = find_location(value)
                if result:
                    return result
                    
        # If it's a list
        elif isinstance(obj, list):
            for item in obj:
                result = find_location(item)
                if result:
                    return result
                    
        return None
        
    try:
        location = find_location(data)
        if not location:
            # Try to get vehicle name as fallback
            if isinstance(data, dict) and 'conditions' in data and data['conditions']:
                for condition in data['conditions']:
                    if isinstance(condition, dict) and 'details' in condition:
                        details = condition['details']
                        for key, value in details.items():
                            if isinstance(value, dict) and 'vehicle' in value:
                                vehicle = value['vehicle']
                                if isinstance(vehicle, dict) and 'name' in vehicle:
                                    return f"Vehicle: {vehicle['name']}"
        return location
    except Exception as e:
        logger.error(f"Error formatting location: {str(e)}")
        return None

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

@bp.route('/clients/list')
@login_required
@operations_required
def get_clients_list():
    """Get list of Samsara clients in JSON format"""
    try:
        clients = SamsaraClient.query.filter_by(is_active=True).all()
        return jsonify({
            'status': 'success',
            'clients': [{
                'id': client.id,
                'name': client.name
            } for client in clients]
        })
    except Exception as e:
        logger.error(f"Error fetching clients list: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch clients list'
        }), 500

@bp.route('/fleet/drivers/<int:client_id>')
@login_required
@operations_required
def get_drivers(client_id):
    """Get list of drivers for a specific client and sync with database"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        if not client.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Client is not active'
            }), 400

        # Initialize Samsara client with client-specific API key
        samsara_client = SamsaraService(api_key=client.api_key)
        drivers_data = samsara_client.get_drivers()
        
        # Sync drivers with database
        synced_count = 0
        created_count = 0
        updated_count = 0
        
        for driver_data in drivers_data:
            driver_id = driver_data.get('id')
            if not driver_id:
                continue
                
            # Check if driver exists in database
            existing_driver = SamsaraDriver.query.filter_by(driver_id=driver_id).first()
            
            if existing_driver:
                # Update existing driver with latest data
                existing_driver.name = driver_data.get('name', existing_driver.name)
                existing_driver.username = driver_data.get('username', existing_driver.username)
                existing_driver.phone = driver_data.get('phone', existing_driver.phone)
                existing_driver.email = driver_data.get('email', existing_driver.email)
                existing_driver.license_number = driver_data.get('licenseNumber', existing_driver.license_number)
                existing_driver.license_state = driver_data.get('licenseState', existing_driver.license_state)
                existing_driver.license_class = driver_data.get('licenseClass', existing_driver.license_class)
                existing_driver.external_ids = driver_data.get('externalIds', existing_driver.external_ids)
                existing_driver.data = driver_data  # Store full API response
                existing_driver.updated_at = datetime.utcnow()
                
                # Update company association if needed
                if client.company and existing_driver.company_id != client.company.id:
                    existing_driver.company_id = client.company.id
                    
                updated_count += 1
            else:
                # Create new driver record
                new_driver = SamsaraDriver(
                    driver_id=driver_id,
                    name=driver_data.get('name', f'Driver {driver_id}'),
                    username=driver_data.get('username'),
                    phone=driver_data.get('phone'),
                    email=driver_data.get('email'),
                    license_number=driver_data.get('licenseNumber'),
                    license_state=driver_data.get('licenseState'),
                    license_class=driver_data.get('licenseClass'),
                    company_id=client.company.id if client.company else None,
                    external_ids=driver_data.get('externalIds'),
                    data=driver_data,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_driver)
                created_count += 1
            
            synced_count += 1
        
        # Commit all changes
        try:
            db.session.commit()
            logger.info(f"Driver sync completed for client {client_id}: {created_count} created, {updated_count} updated, {synced_count} total")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error committing driver sync for client {client_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to sync drivers with database'
            }), 500
        
        return jsonify({
            'status': 'success',
            'client_name': client.name,
            'drivers': drivers_data,
            'sync_stats': {
                'total_synced': synced_count,
                'created': created_count,
                'updated': updated_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching drivers for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch drivers'
        }), 500

@bp.route('/fleet/vehicles/<int:client_id>')
@login_required
@operations_required
def get_vehicles(client_id):
    """Get list of vehicles for a specific client and sync with database"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        if not client.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Client is not active'
            }), 400

        # Initialize Samsara client with client-specific API key
        samsara_client = SamsaraService(api_key=client.api_key)
        vehicles_data = samsara_client.get_vehicles()
        
        # Sync vehicles with database
        synced_count = 0
        created_count = 0
        updated_count = 0
        
        for vehicle_data in vehicles_data:
            vehicle_id = vehicle_data.get('id')
            if not vehicle_id:
                continue
                
            # Check if vehicle exists in database
            existing_vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
            
            if existing_vehicle:
                # Update existing vehicle with latest data
                existing_vehicle.name = vehicle_data.get('name', existing_vehicle.name)
                existing_vehicle.serial = vehicle_data.get('serial', existing_vehicle.serial)
                existing_vehicle.license_plate = vehicle_data.get('licensePlate', existing_vehicle.license_plate)
                existing_vehicle.vin = vehicle_data.get('vin', existing_vehicle.vin)
                existing_vehicle.make = vehicle_data.get('make', existing_vehicle.make)
                existing_vehicle.model = vehicle_data.get('model', existing_vehicle.model)
                existing_vehicle.year = vehicle_data.get('year', existing_vehicle.year)
                existing_vehicle.external_ids = vehicle_data.get('externalIds', existing_vehicle.external_ids)
                existing_vehicle.data = vehicle_data  # Store full API response
                existing_vehicle.updated_at = datetime.utcnow()
                
                # Update company association if needed
                if client.company and existing_vehicle.company_id != client.company.id:
                    existing_vehicle.company_id = client.company.id
                    
                updated_count += 1
            else:
                # Create new vehicle record
                new_vehicle = SamsaraVehicle(
                    vehicle_id=vehicle_id,
                    name=vehicle_data.get('name', f'Vehicle {vehicle_id}'),
                    serial=vehicle_data.get('serial'),
                    license_plate=vehicle_data.get('licensePlate'),
                    vin=vehicle_data.get('vin'),
                    make=vehicle_data.get('make'),
                    model=vehicle_data.get('model'),
                    year=vehicle_data.get('year'),
                    company_id=client.company.id if client.company else None,
                    external_ids=vehicle_data.get('externalIds'),
                    data=vehicle_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_vehicle)
                created_count += 1
            
            synced_count += 1
        
        # Commit all changes
        try:
            db.session.commit()
            logger.info(f"Vehicle sync completed for client {client_id}: {created_count} created, {updated_count} updated, {synced_count} total")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error committing vehicle sync for client {client_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to sync vehicles with database'
            }), 500
        
        return jsonify({
            'status': 'success',
            'client_name': client.name,
            'vehicles': vehicles_data,
            'sync_stats': {
                'total_synced': synced_count,
                'created': created_count,
                'updated': updated_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching vehicles for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch vehicles'
        }), 500

@bp.route('/fleet/trailers/<int:client_id>')
@login_required
@operations_required
def get_trailers(client_id):
    """Get list of trailers for a specific client"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        if not client.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Client is not active'
            }), 400

        # Initialize Samsara client with client-specific API key
        samsara_client = SamsaraService(api_key=client.api_key)
        trailers = samsara_client.get_trailers()
        
        return jsonify({
            'status': 'success',
            'client_name': client.name,
            'trailers': trailers
        })
        
    except Exception as e:
        logger.error(f"Error fetching trailers for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch trailers'
        }), 500

@bp.route('/fleet/<int:client_id>')
@login_required
@operations_required
def fleet_dashboard(client_id):
    """Display fleet management dashboard for a specific client"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        if not client.is_active:
            flash('Client is not active', 'error')
            return redirect(url_for('samsara.clients'))
            
        return render_template(
            'samsara/fleet/dashboard.html',
            client=client
        )
        
    except Exception as e:
        logger.error(f"Error loading fleet dashboard for client {client_id}: {str(e)}", exc_info=True)
        flash('Failed to load fleet dashboard', 'error')
        return redirect(url_for('samsara.clients'))

@bp.route('/fleet/vehicles/locations/<int:client_id>', methods=['GET'])
@operations_required
def get_vehicle_locations(client_id):
    """Get real-time location data for vehicles using the Stats API (types=gps)."""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
        
        vehicle_id_param = request.args.get('vehicleId')
        # The service method get_vehicle_locations now expects 'vehicle_ids'
        # and can handle None (for all) or a single ID string.
        
        samsara = SamsaraService(client.api_key)
        locations = samsara.get_vehicle_locations(vehicle_ids=vehicle_id_param) # Pass as vehicle_ids
        
        # The service now returns a list of processed location_info objects.
        # If vehicle_id_param was provided, 'locations' should contain one item or be empty.
        # If vehicle_id_param was None, it might contain many.
        # The frontend fetchVehicleLocation expects a single location object or null.
        
        # If a specific vehicleId was requested, return its location or null/empty if not found.
        if vehicle_id_param:
            final_location_data = locations[0] if locations else None
        else:
            # If no specific vehicleId was requested (fetch all), return the whole list.
            # This might need adjustment based on how fetchVehicleLocation on frontend handles it.
            # For now, let's assume if vehicleId is in query, we want one, otherwise potentially many.
            final_location_data = locations 

        return jsonify({
            'status': 'success',
            # Adjust the key if frontend expects something different, e.g., 'location' for a single one
            'locations': final_location_data 
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_vehicle_locations route: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/vehicles/stats/<int:client_id>', methods=['GET'])
@operations_required
def get_vehicle_stats(client_id):
    """Get vehicle statistics including fuel, engine hours, etc."""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
            
        vehicle_id = request.args.get('vehicleId')
        if not vehicle_id:
            return jsonify({'status': 'error', 'message': 'Vehicle ID is required'}), 400
            
        samsara = SamsaraService(client.api_key)
        stats = samsara.get_vehicle_stats(vehicle_id)
        
        if not stats:
            return jsonify({
                'status': 'success',
                'stats': []
            })
            
        return jsonify({
            'status': 'success',
            'stats': stats
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_vehicle_stats: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/fleet/drivers/hos/<int:client_id>/<string:driver_id>', methods=['GET'])
@operations_required
def get_driver_hos_logs(client_id, driver_id):
    """Get Hours of Service logs for a driver"""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
            
        # Get optional date range parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        
        # Convert string dates to datetime if provided
        if start_time:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        samsara = SamsaraService(client.api_key)
        logs = samsara.get_driver_hos_logs(driver_id, start_time, end_time)
        
        return jsonify({
            'status': 'success',
            'hos_logs': logs
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_driver_hos_logs: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/drivers/hos/violations/<int:client_id>/<string:driver_id>', methods=['GET'])
@operations_required
def get_driver_hos_violations(client_id, driver_id):
    """Get Hours of Service violations for a driver"""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
            
        # Get optional date range parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        
        # Convert string dates to datetime if provided
        if start_time:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        samsara = SamsaraService(client.api_key)
        violations = samsara.get_driver_hos_violations(driver_id, start_time, end_time)
        
        return jsonify({
            'status': 'success',
            'violations': violations
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_driver_hos_violations: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/drivers/hos/daily/<int:client_id>/<string:driver_id>', methods=['GET'])
@operations_required
def get_driver_hos_daily_logs(client_id, driver_id):
    """Get daily Hours of Service logs for a driver"""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
            
        # Get optional date range parameters
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        
        # Convert string dates to datetime if provided
        if start_time:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
        samsara = SamsaraService(client.api_key)
        daily_logs = samsara.get_driver_hos_daily_logs(driver_id, start_time, end_time)
        
        return jsonify({
            'status': 'success',
            'daily_logs': daily_logs
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_driver_hos_daily_logs: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/vehicles/assignments/<int:client_id>', methods=['GET'])
@operations_required
def get_vehicle_assignments(client_id):
    """Get current driver assignments for vehicles"""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
        
        vehicle_id_param = request.args.get('vehicleId')
            
        samsara = SamsaraService(client.api_key)
        assignments = samsara.get_vehicle_assignments(vehicle_ids=vehicle_id_param)
        
        return jsonify({
            'status': 'success',
            'assignments': assignments
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_vehicle_assignments route: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/trailers/locations/<int:client_id>', methods=['GET'])
@operations_required
def get_trailer_locations(client_id):
    """Get real-time location data for trailers"""
    try:
        client = SamsaraClient.query.get(client_id)
        if not client:
            return jsonify({'status': 'error', 'message': 'Client not found'}), 404
            
        trailer_id = request.args.get('trailerId')
        if not trailer_id:
            return jsonify({'status': 'error', 'message': 'Trailer ID is required'}), 400
            
        samsara = SamsaraService(client.api_key)
        locations = samsara.get_trailer_locations(trailer_id)
        
        return jsonify({
            'status': 'success',
            'locations': locations
        })
    except Exception as e:
        current_app.logger.error(f"Error in get_trailer_locations: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/fleet/sync/<int:client_id>', methods=['POST'])
@login_required
@operations_required
def sync_fleet_data(client_id):
    """Manually sync all drivers and vehicles for a client with Samsara API"""
    try:
        client = SamsaraClient.query.get_or_404(client_id)
        if not client.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Client is not active'
            }), 400

        # Initialize Samsara client with client-specific API key
        samsara_client = SamsaraService(api_key=client.api_key)
        
        # Sync drivers
        drivers_data = samsara_client.get_drivers()
        driver_synced = 0
        driver_created = 0
        driver_updated = 0
        
        for driver_data in drivers_data:
            driver_id = driver_data.get('id')
            if not driver_id:
                continue
                
            existing_driver = SamsaraDriver.query.filter_by(driver_id=driver_id).first()
            
            if existing_driver:
                # Update existing driver
                existing_driver.name = driver_data.get('name', existing_driver.name)
                existing_driver.username = driver_data.get('username', existing_driver.username)
                existing_driver.phone = driver_data.get('phone', existing_driver.phone)
                existing_driver.email = driver_data.get('email', existing_driver.email)
                existing_driver.license_number = driver_data.get('licenseNumber', existing_driver.license_number)
                existing_driver.license_state = driver_data.get('licenseState', existing_driver.license_state)
                existing_driver.license_class = driver_data.get('licenseClass', existing_driver.license_class)
                existing_driver.external_ids = driver_data.get('externalIds', existing_driver.external_ids)
                existing_driver.data = driver_data
                existing_driver.updated_at = datetime.utcnow()
                
                if client.company and existing_driver.company_id != client.company.id:
                    existing_driver.company_id = client.company.id
                    
                driver_updated += 1
            else:
                # Create new driver
                new_driver = SamsaraDriver(
                    driver_id=driver_id,
                    name=driver_data.get('name', f'Driver {driver_id}'),
                    username=driver_data.get('username'),
                    phone=driver_data.get('phone'),
                    email=driver_data.get('email'),
                    license_number=driver_data.get('licenseNumber'),
                    license_state=driver_data.get('licenseState'),
                    license_class=driver_data.get('licenseClass'),
                    company_id=client.company.id if client.company else None,
                    external_ids=driver_data.get('externalIds'),
                    data=driver_data,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_driver)
                driver_created += 1
            
            driver_synced += 1
        
        # Sync vehicles
        vehicles_data = samsara_client.get_vehicles()
        vehicle_synced = 0
        vehicle_created = 0
        vehicle_updated = 0
        
        for vehicle_data in vehicles_data:
            vehicle_id = vehicle_data.get('id')
            if not vehicle_id:
                continue
                
            existing_vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
            
            if existing_vehicle:
                # Update existing vehicle
                existing_vehicle.name = vehicle_data.get('name', existing_vehicle.name)
                existing_vehicle.serial = vehicle_data.get('serial', existing_vehicle.serial)
                existing_vehicle.license_plate = vehicle_data.get('licensePlate', existing_vehicle.license_plate)
                existing_vehicle.vin = vehicle_data.get('vin', existing_vehicle.vin)
                existing_vehicle.make = vehicle_data.get('make', existing_vehicle.make)
                existing_vehicle.model = vehicle_data.get('model', existing_vehicle.model)
                existing_vehicle.year = vehicle_data.get('year', existing_vehicle.year)
                existing_vehicle.external_ids = vehicle_data.get('externalIds', existing_vehicle.external_ids)
                existing_vehicle.data = vehicle_data
                existing_vehicle.updated_at = datetime.utcnow()
                
                if client.company and existing_vehicle.company_id != client.company.id:
                    existing_vehicle.company_id = client.company.id
                    
                vehicle_updated += 1
            else:
                # Create new vehicle
                new_vehicle = SamsaraVehicle(
                    vehicle_id=vehicle_id,
                    name=vehicle_data.get('name', f'Vehicle {vehicle_id}'),
                    serial=vehicle_data.get('serial'),
                    license_plate=vehicle_data.get('licensePlate'),
                    vin=vehicle_data.get('vin'),
                    make=vehicle_data.get('make'),
                    model=vehicle_data.get('model'),
                    year=vehicle_data.get('year'),
                    company_id=client.company.id if client.company else None,
                    external_ids=vehicle_data.get('externalIds'),
                    data=vehicle_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.session.add(new_vehicle)
                vehicle_created += 1
            
            vehicle_synced += 1
        
        # Commit all changes
        try:
            db.session.commit()
            logger.info(f"Fleet sync completed for client {client_id}: Drivers({driver_created} created, {driver_updated} updated), Vehicles({vehicle_created} created, {vehicle_updated} updated)")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error committing fleet sync for client {client_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to sync fleet data with database'
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': 'Fleet data synchronized successfully',
            'client_name': client.name,
            'sync_stats': {
                'drivers': {
                    'total_synced': driver_synced,
                    'created': driver_created,
                    'updated': driver_updated
                },
                'vehicles': {
                    'total_synced': vehicle_synced,
                    'created': vehicle_created,
                    'updated': vehicle_updated
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error syncing fleet data for client {client_id}: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Failed to sync fleet data'
        }), 500

@bp.route('/alerts/<int:alert_id>/assignment', methods=['PUT'])
@login_required
@operations_required
def update_alert_assignment(alert_id):
    """Update alert driver/vehicle assignment"""
    try:
        alert = SamsaraAlert.query.get_or_404(alert_id)
        data = request.get_json()
        
        driver_id = data.get('driver_id')
        vehicle_id = data.get('vehicle_id')
        
        changes_made = []
        
        # Update driver assignment
        if driver_id:
            old_driver = alert.driver.name if alert.driver else None
            new_driver = SamsaraDriver.query.filter_by(driver_id=driver_id).first()
            
            if new_driver:
                alert.driver_id = driver_id
                alert.driver_name = new_driver.name
                
                # Log driver assignment activity
                alert.add_activity(
                    activity_type='assignment',
                    description=f'Driver assignment updated',
                    old_value=old_driver,
                    new_value=new_driver.name,
                    user_id=current_user.id
                )
                changes_made.append(f'Driver changed to {new_driver.name}')
        
        # Update vehicle assignment
        if vehicle_id:
            old_vehicle = alert.vehicle.name if alert.vehicle else None
            new_vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
            
            if new_vehicle:
                alert.vehicle_id = vehicle_id
                alert.vehicle_name = new_vehicle.name
                
                # Log vehicle assignment activity
                alert.add_activity(
                    activity_type='assignment',
                    description=f'Vehicle assignment updated',
                    old_value=old_vehicle,
                    new_value=new_vehicle.name,
                    user_id=current_user.id
                )
                changes_made.append(f'Vehicle changed to {new_vehicle.name}')
        
        if changes_made:
            alert.updated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': f'Assignment updated: {", ".join(changes_made)}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No valid assignments provided'
            }), 400
            
    except Exception as e:
        db.session.rollback()
        print(f"Error updating alert assignment: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to update assignment'
        }), 500

# Register the routes
bp.add_url_rule('/webhook', 'webhook', webhook, methods=['POST'])
bp.add_url_rule('/test-webhook', 'test_webhook', test_webhook, methods=['POST']) 