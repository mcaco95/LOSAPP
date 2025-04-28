import requests
import logging
from datetime import datetime
from flask import current_app
from app import db
from app.models.samsara import (
    SamsaraVehicle,
    SamsaraWebhookEvent,
    SamsaraAlert,
    SamsaraVehicleLocation,
    SamsaraClient
)
import json
import os

logger = logging.getLogger(__name__)

class SamsaraService:
    def __init__(self):
        self.api_key = current_app.config['SAMSARA_API_KEY']
        self.base_url = current_app.config['SAMSARA_API_BASE_URL']
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        logger.info("SamsaraService initialized")
        
        # Create logs directory if it doesn't exist
        self.logs_dir = os.path.join(current_app.root_path, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)

    def get_vehicles(self):
        """Fetch all vehicles from Samsara"""
        try:
            logger.info("Fetching vehicles from Samsara")
            response = requests.get(
                f"{self.base_url}/fleet/vehicles",
                headers=self.headers
            )
            response.raise_for_status()
            vehicles = response.json()
            logger.info(f"Successfully fetched {len(vehicles)} vehicles")
            return vehicles
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching vehicles from Samsara: {str(e)}", exc_info=True)
            return None

    def _log_webhook_error(self, event_data, error, traceback=None):
        """Log webhook errors to a daily file"""
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(self.logs_dir, f'webhook_errors_{today}.log')
        
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_data.get('eventType'),
            'event_id': event_data.get('eventId'),
            'error': str(error),
            'raw_data': event_data,
            'traceback': traceback
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(error_entry) + '\n')
            
        logger.error(f"Webhook error logged to {log_file}")

    def process_webhook_event(self, event_data):
        try:
            logger.info(f"Processing Samsara webhook event: {event_data}")
            
            if event_data.get('eventType') == 'Ping':
                logger.info("Received Ping event from Samsara - webhook is working")
                return True
                
            if event_data.get('eventType') == 'AlertIncident':
                return self._process_alert_event(event_data)
                
            if event_data.get('eventType') in ['SevereSpeedingStarted', 'SevereSpeedingEnded']:
                try:
                    return self._process_speeding_event(event_data)
                except AttributeError:
                    self._log_webhook_error(
                        event_data,
                        "Missing _process_speeding_event handler",
                        "This event type is not yet implemented"
                    )
                    return False
                    
            logger.warning(f"Unhandled event type: {event_data.get('eventType')}")
            return False
            
        except Exception as e:
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            logger.error(f"Error processing webhook event: {str(e)}")
            return False

    def _process_alert_event(self, event_data):
        """Process alert type events"""
        try:
            alert_data = event_data.get('data', {})
            logger.info(f"Processing alert event: {alert_data}")
            
            # Get the client from the org_id
            client = SamsaraClient.query.filter_by(org_id=event_data.get('orgId')).first()
            if not client:
                logger.error(f"No client found for org_id: {event_data.get('orgId')}")
                return False
            
            # Process each condition in the alert
            for condition in alert_data.get('conditions', []):
                trigger_id = condition.get('triggerId')
                description = condition.get('description')
                details = condition.get('details', {})
                
                # Get vehicle from details
                vehicle_data = None
                if details:
                    # Handle DVIR alerts - check both dvir.vehicle and dvir.trailer
                    if 'dvirSubmittedDevice' in details:
                        dvir_data = details['dvirSubmittedDevice']
                        if 'vehicle' in dvir_data:
                            vehicle_data = dvir_data['vehicle']
                        elif 'dvir' in dvir_data:
                            if 'vehicle' in dvir_data['dvir']:
                                vehicle_data = dvir_data['dvir']['vehicle']
                            elif 'trailer' in dvir_data['dvir']:
                                vehicle_data = dvir_data['dvir']['trailer']

                    # Handle severe speeding alerts
                    elif 'severeSpeeding' in details:
                        speed_data = details['severeSpeeding'].get('data', {})
                        if 'vehicle' in speed_data:
                            vehicle_data = speed_data['vehicle']

                    # Handle any other alert types
                    else:
                        # First check for direct vehicle data
                        for key, value in details.items():
                            if isinstance(value, dict):
                                # Check direct vehicle data
                                if 'vehicle' in value:
                                    vehicle_data = value['vehicle']
                                    break
                                # Check nested data structure
                                elif 'data' in value and isinstance(value['data'], dict):
                                    if 'vehicle' in value['data']:
                                        vehicle_data = value['data']['vehicle']
                                        break

                if not vehicle_data:
                    logger.warning(f"No vehicle data found in alert details: {details}")
                    continue

                vehicle_id = vehicle_data.get('id')
                if not vehicle_id:
                    logger.warning(f"No vehicle ID found in vehicle data: {vehicle_data}")
                    continue

                # Get or create vehicle
                vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
                if not vehicle:
                    vehicle = SamsaraVehicle(
                        vehicle_id=vehicle_id,
                        name=vehicle_data.get('name', 'Unknown'),
                        serial=vehicle_data.get('serial') or vehicle_data.get('externalIds', {}).get('samsara.serial'),
                        vin=vehicle_data.get('vin'),
                        external_ids=vehicle_data.get('externalIds', {}),
                        data=vehicle_data,
                        company_id=None
                    )
                    db.session.add(vehicle)
                    db.session.commit()
                
                # Parse timestamp
                timestamp = datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00'))
                
                # Create alert
                alert = SamsaraAlert(
                    alert_id=f"{event_data.get('eventId')}-{trigger_id}",
                    vehicle_id=vehicle.id,
                    alert_type=description,
                    severity='medium',  # Default severity
                    status='active',
                    description=description,
                    data=alert_data,
                    timestamp=timestamp,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    client_id=client.id  # Set the client_id for the alert
                )
                
                db.session.add(alert)
                db.session.commit()
                
                logger.info(f"Created alert for vehicle {vehicle_id}: {description}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing alert event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            db.session.rollback()
            return False

    def _process_location_event(self, event_data, webhook_event):
        """Process location type events"""
        try:
            location_data = event_data.get('data', {})
            logger.info(f"Processing location event: {location_data}")
            
            # Get vehicle
            vehicle = SamsaraVehicle.query.filter_by(
                vehicle_id=location_data.get('vehicleId')
            ).first()
            
            if vehicle:
                # Parse timestamp - handle both string and numeric formats
                location_time = location_data.get('timestamp')
                if isinstance(location_time, (int, float)):
                    timestamp = datetime.fromtimestamp(location_time / 1000)  # Convert milliseconds to seconds
                else:
                    timestamp = datetime.fromisoformat(location_time.replace('Z', '+00:00'))
                
                location = SamsaraVehicleLocation(
                    vehicle_id=vehicle.id,
                    latitude=location_data.get('latitude'),
                    longitude=location_data.get('longitude'),
                    heading=location_data.get('heading'),
                    speed=location_data.get('speed'),
                    timestamp=timestamp,
                    created_at=datetime.utcnow()
                )
                db.session.add(location)
                db.session.commit()
                logger.info(f"Stored location for vehicle: {vehicle.id}")
            else:
                logger.warning(f"Vehicle not found: {location_data.get('vehicleId')}")
        except Exception as e:
            logger.error(f"Error processing location event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            raise

    def _process_vehicle_event(self, event_data, webhook_event):
        """Process vehicle type events (updates, etc.)"""
        try:
            vehicle_data = event_data.get('data', {})
            logger.info(f"Processing vehicle event: {vehicle_data}")
            
            vehicle = SamsaraVehicle.query.filter_by(
                vehicle_id=vehicle_data.get('id')
            ).first()
            
            if vehicle:
                # Update vehicle information
                vehicle.name = vehicle_data.get('name', vehicle.name)
                vehicle.license_plate = vehicle_data.get('licensePlate', vehicle.license_plate)
                vehicle.vin = vehicle_data.get('vin', vehicle.vin)
                vehicle.make = vehicle_data.get('make', vehicle.make)
                vehicle.model = vehicle_data.get('model', vehicle.model)
                vehicle.year = vehicle_data.get('year', vehicle.year)
                vehicle.updated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Updated vehicle: {vehicle.id}")
            else:
                logger.warning(f"Vehicle not found: {vehicle_data.get('id')}")
        except Exception as e:
            logger.error(f"Error processing vehicle event: {str(e)}", exc_info=True)
            raise

    def _process_speeding_event(self, event_data):
        """Process speeding-related events from Samsara"""
        try:
            logger.info(f"Processing speeding event: {event_data}")
            
            # Get the client from the org_id
            client = SamsaraClient.query.filter_by(org_id=event_data.get('orgId')).first()
            if not client:
                logger.error(f"No client found for org_id: {event_data.get('orgId')}")
                return False
            
            # Extract vehicle ID from the event data
            vehicle_id = event_data.get('data', {}).get('data', {}).get('vehicle', {}).get('id')
            if not vehicle_id:
                logger.warning("No vehicle ID found in speeding event")
                return False
                
            # Get or create vehicle record
            vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
            if not vehicle:
                vehicle_data = event_data.get('data', {}).get('data', {}).get('vehicle', {})
                logger.info(f"Creating new vehicle record for ID: {vehicle_id}")
                vehicle = SamsaraVehicle(
                    vehicle_id=vehicle_id,
                    name=vehicle_data.get('name', 'Unknown'),
                    data=vehicle_data,
                    company_id=client.id  # Use company_id instead of client_id
                )
                db.session.add(vehicle)
                db.session.commit()
            
            # Parse timestamp - handle both string and numeric formats
            event_time = event_data.get('eventTime')
            if isinstance(event_time, (int, float)):
                timestamp = datetime.fromtimestamp(event_time / 1000)  # Convert milliseconds to seconds
            else:
                timestamp = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            
            # Create alert record
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=vehicle.id,  # Use our internal vehicle ID
                alert_type=event_data.get('eventType'),
                severity='high',
                status='active' if event_data.get('eventType') == 'SevereSpeedingStarted' else 'resolved',
                description=f"Severe Speeding {'Started' if event_data.get('eventType') == 'SevereSpeedingStarted' else 'Ended'}",
                data=event_data,
                timestamp=timestamp,
                client_id=client.id  # Set the client_id for the alert
            )
            
            db.session.add(alert)
            db.session.commit()
            
            logger.info(f"Created speeding alert for vehicle {vehicle_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing speeding event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            db.session.rollback()
            return False 