import requests
import logging
from datetime import datetime, timedelta, timezone
from flask import current_app
from app import db
from app.models.samsara import (
    SamsaraVehicle,
    SamsaraWebhookEvent,
    SamsaraAlert,
    SamsaraVehicleLocation,
    SamsaraClient,
    SamsaraDriver
)
from app.models.company import Company
import json
import os
import time

logger = logging.getLogger(__name__)

class SamsaraService:
    def __init__(self, api_key=None):
        # Use provided API key or fall back to config
        self.api_key = api_key or current_app.config['SAMSARA_API_KEY']
        self.base_url = 'https://api.samsara.com'  # Remove /v1 prefix for new REST API
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        logger.info("SamsaraService initialized")
        
        # Create logs directory if it doesn't exist
        self.logs_dir = os.path.join(current_app.root_path, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)

    def get_drivers(self):
        """Get list of drivers from Samsara"""
        try:
            response = requests.get(
                f'{self.base_url}/fleet/drivers',
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            # Enhanced logging
            if data:
                logger.info("=== Complete Driver Data Sample ===")
                logger.info(json.dumps(data[0], indent=2))
                logger.info(f"Total drivers received: {len(data)}")
                logger.info("Available fields: %s", list(data[0].keys()))
            return data
        except Exception as e:
            logger.error(f"Error fetching drivers: {str(e)}")
            return []

    def get_vehicles(self):
        """Get list of vehicles from Samsara"""
        try:
            response = requests.get(
                f'{self.base_url}/fleet/vehicles',
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            # Enhanced logging
            if data:
                logger.info("=== Complete Vehicle Data Sample ===")
                logger.info(json.dumps(data[0], indent=2))
                logger.info(f"Total vehicles received: {len(data)}")
                logger.info("Available fields: %s", list(data[0].keys()))
            return data
        except Exception as e:
            logger.error(f"Error fetching vehicles: {str(e)}")
            return []

    def get_trailers(self):
        """Get list of trailers from Samsara"""
        try:
            response = requests.get(
                f'{self.base_url}/fleet/trailers',
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            # Enhanced logging
            if data:
                logger.info("=== Complete Trailer Data Sample ===")
                logger.info(json.dumps(data[0], indent=2))
                logger.info(f"Total trailers received: {len(data)}")
                logger.info("Available fields: %s", list(data[0].keys()))
            return data
        except Exception as e:
            logger.error(f"Error fetching trailers: {str(e)}")
            return []

    def _log_webhook_error(self, event_data, error, error_type="Unknown Error"):
        """Log webhook errors to a daily file with improved formatting"""
        try:
            # Ensure logs directory exists first
            os.makedirs(self.logs_dir, exist_ok=True)
            
            today = datetime.now().strftime('%Y-%m-%d')
            log_file = os.path.join(self.logs_dir, f'webhook_errors_{today}.log')
            
            # Format the error entry with more details
            error_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_data.get('eventType', 'UnknownEventType'),
                'event_id': event_data.get('eventId', 'UnknownEventID'),
                'org_id': event_data.get('orgId', 'UnknownOrgID'),
                'error_type': error_type,
                'error_message': str(error),
                'vehicle_info': {
                    'id': event_data.get('data', {}).get('vehicle', {}).get('id'),
                    'name': event_data.get('data', {}).get('vehicle', {}).get('name')
                },
                'trailer_info': {
                    'id': event_data.get('data', {}).get('conditions', [{}])[0].get('details', {}).get('reeferTemperature', {}).get('trailer', {}).get('id'),
                    'name': event_data.get('data', {}).get('conditions', [{}])[0].get('details', {}).get('reeferTemperature', {}).get('trailer', {}).get('name')
                },
                'conditions': event_data.get('data', {}).get('conditions', []),
                'raw_data': event_data
            }
            
            # Write the error entry with proper formatting
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_entry, indent=2) + '\n\n')  # Add newline between entries for readability
                
            logger.error(f"Webhook error logged to {log_file} - Type: {error_type}, Event ID: {event_data.get('eventId', 'UnknownEventID')}")
            
        except Exception as logging_error:
            logger.critical(f"Failed to log webhook error: {str(logging_error)}")
            logger.critical(f"Original error was: {str(error)}")
            logger.critical(f"Event data: {event_data}")

    def _log_webhook_success(self, event_data, details=None):
        """Log successful webhook processing to a daily file"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            log_file = os.path.join(self.logs_dir, f'webhook_success_{today}.log')
            
            # Format the success entry
            success_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_data.get('eventType', 'UnknownEventType'),
                'event_id': event_data.get('eventId', 'UnknownEventID'),
                'org_id': event_data.get('orgId', 'UnknownOrgID'),
                'vehicle_info': {
                    'id': event_data.get('data', {}).get('vehicle', {}).get('id'),
                    'name': event_data.get('data', {}).get('vehicle', {}).get('name')
                },
                'trailer_info': {
                    'id': event_data.get('data', {}).get('conditions', [{}])[0].get('details', {}).get('reeferTemperature', {}).get('trailer', {}).get('id'),
                    'name': event_data.get('data', {}).get('conditions', [{}])[0].get('details', {}).get('reeferTemperature', {}).get('trailer', {}).get('name')
                },
                'conditions': event_data.get('data', {}).get('conditions', []),
                'processing_details': details or {},
                'raw_data': event_data
            }
            
            # Ensure the logs directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # Write the success entry with proper formatting
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(success_entry, indent=2) + '\n\n')
                
            logger.info(f"Webhook success logged to {log_file} - Type: {event_data.get('eventType')}, Event ID: {event_data.get('eventId', 'UnknownEventID')}")
            
        except Exception as logging_error:
            logger.error(f"Failed to log webhook success: {str(logging_error)}")

    def process_webhook_event(self, event_data):
        if not event_data:
            logger.error("Received empty webhook event data")
            self._log_webhook_error({}, "Empty webhook data", "Invalid Request")
            return False
            
        try:
            logger.info(f"Processing Samsara webhook event: {event_data}")
            
            if event_data.get('eventType') == 'Ping':
                logger.info("Received Ping event from Samsara - webhook is working")
                self._log_webhook_success(event_data, {"message": "Ping received successfully"})
                return True
                
            if event_data.get('eventType') == 'AlertIncident':
                result = self._process_alert_event(event_data)
                if result:
                    self._log_webhook_success(event_data, {"message": "Alert processed successfully"})
                return result
                
            if event_data.get('eventType') in ['SevereSpeedingStarted', 'SevereSpeedingEnded']:
                try:
                    result = self._process_speeding_event(event_data)
                    if result:
                        self._log_webhook_success(event_data, {"message": "Speeding event processed successfully"})
                    return result
                except AttributeError:
                    self._log_webhook_error(
                        event_data,
                        "Missing _process_speeding_event handler",
                        "Unimplemented Event Type"
                    )
                    return False
                    
            if event_data.get('eventType') == 'DvirSubmitted':
                result = self._process_dvir_submitted_event(event_data)
                if result:
                    self._log_webhook_success(event_data, {"message": "DVIR submission processed successfully"})
                return result

            if event_data.get('eventType') == 'RouteStopDeparture':
                result = self._process_route_stop_departure_event(event_data)
                if result:
                    self._log_webhook_success(event_data, {"message": "Route stop departure processed successfully"})
                return result

            if event_data.get('eventType') == 'RouteStopArrival':
                result = self._process_route_stop_arrival_event(event_data)
                if result:
                    self._log_webhook_success(event_data, {"message": "Route stop arrival processed successfully"})
                return result

            if event_data.get('eventType') == 'GeofenceExit':
                result = self._process_geofence_exit_event(event_data)
                if result:
                    self._log_webhook_success(event_data, {"message": "Geofence exit processed successfully"})
                return result

            logger.warning(f"Unhandled event type: {event_data.get('eventType')}")
            self._log_webhook_error(event_data, f"Unhandled event type: {event_data.get('eventType')}", "Unsupported Event Type")
            return False
            
        except Exception as e:
            self._log_webhook_error(event_data, str(e), "Processing Error")
            logger.error(f"Error processing webhook event: {str(e)}", exc_info=True)
            return False

    def _extract_vehicle_id_from_alert(self, event_data):
        """
        Tries to extract a vehicle or trailer ID from an alert event payload
        by checking common paths.
        """
        data = event_data.get('data', {})
        conditions = data.get('conditions', [])
        event_description = conditions[0].get('description', '').lower() if conditions else ''
        event_id_for_log = event_data.get('eventId', 'UnknownEventID')

        # Attempt 1: Standard vehicle in details (e.g., severeSpeeding as AlertIncident)
        if conditions and conditions[0].get('details'):
            details = conditions[0].get('details')
            if 'severeSpeeding' in details and details['severeSpeeding'].get('data', {}).get('vehicle', {}).get('id'):
                logger.info(f"Attempt 1: Extracted vehicle ID from severeSpeeding details for event {event_id_for_log}")
                return details['severeSpeeding']['data']['vehicle']['id']
            # Check for vehicle directly under details (if applicable for other alerts)
            if details.get('vehicle', {}).get('id'):
                 logger.info(f"Attempt 1.1: Extracted vehicle ID directly from details.vehicle for event {event_id_for_log}")
                 return details['vehicle']['id']


        # Attempt 2: Reefer Temperature (trailer ID)
        if 'reefer temperature' in event_description:
            if conditions and conditions[0].get('details', {}).get('reeferTemperature', {}).get('trailer', {}).get('id'):
                logger.info(f"Attempt 2: Extracted trailer ID for reeferTemperature for event {event_id_for_log}")
                return conditions[0]['details']['reeferTemperature']['trailer']['id']

        # Attempt 3: Check common vehicle path if not found yet (e.g. from a generic alert structure)
        # This is a common path seen in some webhook structures
        if data.get('vehicle', {}).get('id'):
            logger.info(f"Attempt 3: Extracted vehicle ID from data.vehicle for event {event_id_for_log}")
            return data['vehicle']['id']
            
        # Attempt 4: Path for some speeding incidents (if they come as AlertIncident)
        # event_data.data.data.vehicle.id (less common for AlertIncident, more for direct speeding events)
        if data.get('data', {}).get('vehicle', {}).get('id'):
            logger.info(f"Attempt 4: Extracted vehicle ID from data.data.vehicle for event {event_id_for_log}")
            return data['data']['vehicle']['id']

        # If it's an HOS Violation, vehicle ID is often not directly in the payload.
        # The driver ID is primary. Vehicle might be linked via driver.
        if 'driver hos violation' in event_description:
            logger.warning(f"Vehicle ID not directly found for 'Driver HOS Violation' event {event_id_for_log}. This is often expected. Driver ID should be present.")
            # No vehicle ID to return here from typical HOS violation payloads.
            # Further logic might involve looking up vehicle by driver if necessary.
            return None

        logger.warning(f"Could not extract vehicle/trailer ID from alert payload for event {event_id_for_log} with description '{event_description}' using known paths.")
        return None

    def _process_alert_event(self, event_data):
        """Process alert type events"""
        try:
            alert_data = event_data.get('data', {})
            event_id_for_log = event_data.get('eventId', 'UnknownEventID')
            org_id_for_log = event_data.get('orgId', 'UnknownOrgID')
            logger.info(f"Processing alert event: {alert_data} for eventId: {event_id_for_log}, orgId: {org_id_for_log}")

            # 1. Get the SamsaraClient
            samsara_client_instance = SamsaraClient.query.filter_by(org_id=org_id_for_log).first()
            if not samsara_client_instance:
                logger.error(f"No SamsaraClient found for org_id: {org_id_for_log} (Event ID: {event_id_for_log})")
                self._log_webhook_error(event_data, f"SamsaraClient not found for org_id {org_id_for_log}", "SamsaraClient lookup failed")
                return False
            logger.info(f"Found SamsaraClient (DB ID: {samsara_client_instance.id}, Name: {samsara_client_instance.name}) for org_id: {org_id_for_log}")

            # 2. Get or create company
            company = Company.query.filter_by(samsara_client_id=samsara_client_instance.id).first()
            if not company:
                logger.warning(f"No Company found linked to SamsaraClient ID {samsara_client_instance.id}. Attempting to use/create company based on SamsaraClient name. (Event ID: {event_id_for_log})")
                # Try to find company by name, or create a new one
                company_name = samsara_client_instance.name  # Or a default name if name is not reliable
                company = Company.query.filter_by(name=company_name).first()
                if not company:
                    logger.info(f"Creating new Company: {company_name} for SamsaraClient ID {samsara_client_instance.id} (Event ID: {event_id_for_log})")
                    company = Company(name=company_name, samsara_client_id=samsara_client_instance.id)
                    db.session.add(company)
                    try:
                        db.session.commit()
                        logger.info(f"Successfully created new Company (DB ID: {company.id}) (Event ID: {event_id_for_log})")
                    except Exception as e_commit_company:
                        db.session.rollback()
                        logger.error(f"Failed to create Company '{company_name}': {str(e_commit_company)} (Event ID: {event_id_for_log})")
                        self._log_webhook_error(event_data, e_commit_company, f"Company creation failed for {company_name}")
                        return False
                else:
                    logger.info(f"Found existing Company (DB ID: {company.id}) by name '{company_name}'. Linking to SamsaraClient ID {samsara_client_instance.id}. (Event ID: {event_id_for_log})")
                    if not company.samsara_client_id: # Link if not already linked
                        company.samsara_client_id = samsara_client_instance.id 
                        try:
                            db.session.commit()
                        except Exception as e_link_company:
                            db.session.rollback()
                            logger.error(f"Failed to link Company '{company_name}' to SamsaraClient ID {samsara_client_instance.id}: {str(e_link_company)}")
                            # Continue processing, but this is a warning state
            else:
                logger.info(f"Using existing Company (DB ID: {company.id}, Name: {company.name}) linked to SamsaraClient (DB ID: {samsara_client_instance.id}) (Alert Event ID: {event_id_for_log})")


            # 3. Extract Vehicle ID from payload
            samsara_vehicle_id_from_payload = self._extract_vehicle_id_from_alert(event_data)
            
            conditions = alert_data.get('conditions', [])
            specific_event_type = conditions[0].get('description') if conditions else event_data.get('eventType')
            is_hos_violation = 'driver hos violation' in (specific_event_type.lower() if specific_event_type else '')


            if not samsara_vehicle_id_from_payload and not is_hos_violation:
                logger.warning(f"No vehicle/trailer ID found in event payload (Event ID: {event_id_for_log}, Type: {specific_event_type}). Cannot process vehicle/alert.")
                self._log_webhook_error(event_data, "No vehicle/trailer ID found in payload", "Vehicle/Trailer ID extraction failed")
                return False
            
            if samsara_vehicle_id_from_payload:
                logger.info(f"Extracted Samsara Vehicle/Trailer ID from payload: {samsara_vehicle_id_from_payload} (Event ID: {event_id_for_log})")
            elif is_hos_violation:
                logger.info(f"Proceeding to create HOS Violation alert without direct vehicle ID. Driver ID will be primary. (Event ID: {event_id_for_log})")


            # 4. Get or create vehicle record
            vehicle_in_db = None
            db_vehicle_id_for_alert = None

            if samsara_vehicle_id_from_payload: # Only process vehicle if ID was found
                vehicle_in_db = SamsaraVehicle.query.filter_by(samsara_id=samsara_vehicle_id_from_payload, company_id=company.id).first()
                if not vehicle_in_db: # Check with just samsara_id if not found with company_id
                    vehicle_in_db = SamsaraVehicle.query.filter_by(samsara_id=samsara_vehicle_id_from_payload).first()
                    if vehicle_in_db and vehicle_in_db.company_id != company.id:
                        logger.warning(f"SamsaraVehicle (Samsara ID: {samsara_vehicle_id_from_payload}) found but linked to different company (DB Company ID: {vehicle_in_db.company_id}, Current Company ID: {company.id}). This might be an issue or require re-association.")
                        # Depending on business logic, you might re-associate or flag this. For now, we'll use the found vehicle.
                    elif not vehicle_in_db:
                         logger.info(f"SamsaraVehicle with Samsara ID: {samsara_vehicle_id_from_payload} not found in DB. Creating new one. (Event ID: {event_id_for_log})")
                         # Extract vehicle data from the appropriate path based on event type
                         vehicle_payload_for_creation = {}
                         # Default name
                         default_vehicle_name = f"Vehicle {samsara_vehicle_id_from_payload}"

                         if specific_event_type and 'reefer temperature' in specific_event_type.lower():
                             if conditions and conditions[0].get('details', {}).get('reeferTemperature', {}).get('trailer'):
                                 trailer_details = conditions[0]['details']['reeferTemperature']['trailer']
                                 vehicle_payload_for_creation['name'] = trailer_details.get('name', default_vehicle_name)
                                 # Assuming 'samsara.serial' might be VIN or a unique identifier
                                 vehicle_payload_for_creation['vin'] = trailer_details.get('externalIds', {}).get('samsara.serial')
                                 vehicle_payload_for_creation['license_plate'] = trailer_details.get('trailerSerialNumber') # Or another relevant field for license plate
                                 logger.info(f"Populated vehicle_payload_for_creation from reeferTemperature details: {vehicle_payload_for_creation}")
                         elif specific_event_type and 'severe speeding' in specific_event_type.lower(): # Example for severe speeding if it comes as AlertIncident
                             if conditions and conditions[0].get('details', {}).get('severeSpeeding', {}).get('data', {}).get('vehicle'):
                                 speeding_vehicle_details = conditions[0]['details']['severeSpeeding']['data']['vehicle']
                                 vehicle_payload_for_creation['name'] = speeding_vehicle_details.get('name', default_vehicle_name)
                                 # VIN/license plate might not be in this specific payload snippet, add if available
                                 logger.info(f"Populated vehicle_payload_for_creation from severeSpeeding (AlertIncident) details: {vehicle_payload_for_creation}")
                         else: # Fallback or for other alert types that might contain vehicle info
                            # Try a generic path if available in data.vehicle
                            webhook_data_prop = event_data.get('data', {})
                            if webhook_data_prop.get('vehicle'):
                                vehicle_payload_for_creation['name'] = webhook_data_prop['vehicle'].get('name', default_vehicle_name)
                                vehicle_payload_for_creation['vin'] = webhook_data_prop['vehicle'].get('vin')
                                vehicle_payload_for_creation['license_plate'] = webhook_data_prop['vehicle'].get('licensePlate')
                                logger.info(f"Populated vehicle_payload_for_creation from generic data.vehicle path: {vehicle_payload_for_creation}")
                            elif conditions and conditions[0].get('details', {}).get('vehicle'): # another generic path
                                vehicle_detail_node = conditions[0]['details']['vehicle']
                                vehicle_payload_for_creation['name'] = vehicle_detail_node.get('name', default_vehicle_name)
                                vehicle_payload_for_creation['vin'] = vehicle_detail_node.get('vin')
                                vehicle_payload_for_creation['license_plate'] = vehicle_detail_node.get('licensePlate')      
                                logger.info(f"Populated vehicle_payload_for_creation from generic conditions[0].details.vehicle path: {vehicle_payload_for_creation}")


                         if not vehicle_payload_for_creation.get('name'): # Ensure at least a name if nothing else found
                            vehicle_payload_for_creation['name'] = default_vehicle_name
                            logger.warning(f"Could not extract detailed vehicle data for creation for event {event_id_for_log}, type {specific_event_type}. Using default name.")
                            # self._log_webhook_error(event_data, "Could not extract vehicle data for creation from payload", "Vehicle Creation Data Missing")
                            # return False # Decide if this is a fatal error

                         new_vehicle_in_db = SamsaraVehicle(
                            samsara_id=samsara_vehicle_id_from_payload,
                            company_id=company.id,
                            name=vehicle_payload_for_creation.get('name'),
                            vin=vehicle_payload_for_creation.get('vin'),
                            license_plate=vehicle_payload_for_creation.get('license_plate'),
                            # Ensure other required fields for your SamsaraVehicle model are present or have defaults
                            # e.g. make, model, year, etc. if they are not nullable
                         )
                         db.session.add(new_vehicle_in_db)
                         try:
                             db.session.commit()
                             db_vehicle_id_for_alert = new_vehicle_in_db.id
                             logger.info(f"Successfully created new SamsaraVehicle (DB ID: {db_vehicle_id_for_alert}) for Samsara ID: {samsara_vehicle_id_from_payload}")
                         except Exception as e_commit_vehicle:
                             db.session.rollback()
                             logger.error(f"Failed to create SamsaraVehicle for Samsara ID {samsara_vehicle_id_from_payload}: {str(e_commit_vehicle)} (Event ID: {event_id_for_log})")
                             self._log_webhook_error(event_data, e_commit_vehicle, f"Vehicle creation failed. Company: {company.id}, VehicleSamsaraId: {samsara_vehicle_id_from_payload}")
                             return False
                else: # Vehicle was found
                    db_vehicle_id_for_alert = vehicle_in_db.id
                    logger.info(f"Found existing SamsaraVehicle (DB ID: {vehicle_in_db.id}) for Samsara ID: {samsara_vehicle_id_from_payload} (Event ID: {event_id_for_log})")
                    if vehicle_in_db.company_id != company.id:
                        logger.warning(f"Existing SamsaraVehicle (DB ID: {vehicle_in_db.id}) for Samsara ID {samsara_vehicle_id_from_payload} is linked to Company ID {vehicle_in_db.company_id}, but current event context is for Company ID {company.id}. Updating vehicle's company link.")
                        vehicle_in_db.company_id = company.id
                        # Potentially update other vehicle details if they can change and payload has them
                        db.session.add(vehicle_in_db) # Add to session before commit
                        try:
                            db.session.commit()
                            logger.info(f"Successfully updated company link for SamsaraVehicle (DB ID: {vehicle_in_db.id})")
                        except Exception as e_update_vehicle_company:
                            db.session.rollback()
                            logger.error(f"Failed to update company link for SamsaraVehicle (DB ID: {vehicle_in_db.id}): {str(e_update_vehicle_company)}")
                            # This might not be a fatal error, depends on requirements.


            # 5. Extract Driver Info & Get/Create Driver Record
            driver_samsara_id = None
            driver_name = None
            driver_record = None

            if conditions and conditions[0].get('details'):
                details = conditions[0]['details']
                if 'hosViolation' in details and details['hosViolation'].get('driver'):
                    driver_samsara_id = details['hosViolation']['driver'].get('id')
                    driver_name = details['hosViolation']['driver'].get('name')
                # Add other alert types that might contain driver info directly
                # elif 'other_alert_type_with_driver' in details ...

            if driver_samsara_id:
                logger.info(f"Extracted driver ID {driver_samsara_id} and name '{driver_name}' from HOS Violation payload (Event ID: {event_id_for_log})")
                driver_record = SamsaraDriver.query.filter_by(samsara_id=driver_samsara_id, company_id=company.id).first()
                if not driver_record:
                    logger.info(f"Driver with Samsara ID {driver_samsara_id} not found for Company ID {company.id}. Creating new driver. (Event ID: {event_id_for_log})")
                    new_driver = SamsaraDriver(
                        samsara_id=driver_samsara_id,
                        name=driver_name or f"Driver {driver_samsara_id}",
                        company_id=company.id
                        # Populate other fields like username, license_number if available and needed
                    )
                    db.session.add(new_driver)
                    try:
                        db.session.commit()
                        driver_record = new_driver
                        logger.info(f"Successfully created new SamsaraDriver (DB ID: {driver_record.id}) for Samsara ID {driver_samsara_id} (Event ID: {event_id_for_log})")
                    except Exception as e_commit_driver:
                        db.session.rollback()
                        logger.error(f"Failed to create SamsaraDriver for Samsara ID {driver_samsara_id}: {str(e_commit_driver)} (Event ID: {event_id_for_log})")
                        self._log_webhook_error(event_data, e_commit_driver, f"Driver creation failed for {driver_samsara_id}")
                        # Decide if this is fatal; an HOS alert might still be created without a driver_record if allowed
                else:
                    logger.info(f"Found existing SamsaraDriver (DB ID: {driver_record.id}) for Samsara ID {driver_samsara_id} (Event ID: {event_id_for_log})")
            
            # 6. Parse timestamp
            event_time_str = alert_data.get('happenedAtTime') or event_data.get('eventTime') # Prefer happenedAtTime
            if not event_time_str:
                logger.error(f"Missing 'eventTime' in event (Event ID: {event_id_for_log}). Using current UTC time.")
                timestamp = datetime.utcnow()
            else:
                try:
                    if isinstance(event_time_str, (int, float)):
                        timestamp = datetime.fromtimestamp(event_time_str / 1000, timezone.utc)
                    else:
                        timestamp = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                except ValueError as e_ts:
                    logger.error(f"Invalid 'eventTime' format '{event_time_str}' for event (Event ID: {event_id_for_log}): {e_ts}. Using current UTC time.")
                    timestamp = datetime.utcnow()
            
            # Create alert record
            existing_alert = SamsaraAlert.query.filter_by(alert_id=event_id_for_log).first()
            if existing_alert:
                logger.info(f"Alert with ID {event_id_for_log} already exists. Skipping creation.")
                return True

            logger.info(f"Attempting to create SamsaraAlert for event (Alert ID: {event_id_for_log}), vehicle_id (DB): {db_vehicle_id_for_alert}, client_id: {samsara_client_instance.id}")
            
            # Get the specific event type from conditions if available
            specific_event_type = None
            if conditions and len(conditions) > 0:
                specific_event_type = conditions[0].get('description')
            
            alert = SamsaraAlert(
                alert_id=event_id_for_log,
                vehicle_id=db_vehicle_id_for_alert,
                driver_id=driver_record.id if driver_record else None,
                alert_type=specific_event_type or event_data.get('eventType', 'UnknownEventType'),
                severity='high',
                status='unassigned',
                description=conditions[0].get('description', 'No description available') if conditions else 'No description available',
                data=event_data,
                timestamp=timestamp,
                client_id=samsara_client_instance.id
            )
            
            db.session.add(alert)
            try:
                db.session.commit()
                
                # Add initial activity record
                alert.add_activity(
                    activity_type='created',
                    description=f'Alert created: {alert.alert_type}',
                    user_id=None,  # System created
                    metadata={
                        'source': 'samsara_webhook',
                        'event_type': event_data.get('eventType'),
                        'vehicle_id': samsara_vehicle_id_from_payload,
                        'client_id': samsara_client_instance.id
                    }
                )
                db.session.commit()
                
                logger.info(f"Successfully created SamsaraAlert (DB ID: {alert.id}) for alert_id {event_id_for_log}")
            except Exception as e_commit_alert:
                db.session.rollback()
                logger.error(f"Failed to commit SamsaraAlert for alert_id {event_id_for_log}: {str(e_commit_alert)}")
                self._log_webhook_error(event_data, e_commit_alert, f"Alert commit failed for {event_id_for_log}")
                return False
            
            return True
            
        except Exception as e:
            event_id_for_outer_log = event_data.get('eventId', 'UnknownEventIDInOuterException') if event_data else 'NoEventDataInOuterException'
            logger.error(f"Outer error in _process_alert_event for eventId {event_id_for_outer_log}: {str(e)}", exc_info=True)
            if event_data:
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

    def _process_dvir_submitted_event(self, event_data):
        """Process DvirSubmitted events"""
        try:
            logger.info(f"Processing DvirSubmitted event: {event_data}")
            # Extract specific event type from conditions if available
            conditions = event_data.get('data', {}).get('conditions', [])
            specific_event_type = conditions[0].get('description') if conditions and len(conditions) > 0 else 'DVIR Submitted'
            
            # Create alert with specific type
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=event_data.get('data', {}).get('vehicle', {}).get('id'),
                alert_type=specific_event_type,
                severity='medium',
                status='unassigned',
                description=specific_event_type,
                data=event_data,
                timestamp=datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00')),
                client_id=event_data.get('orgId')
            )
            db.session.add(alert)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error processing DvirSubmitted event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            return False

    def _process_route_stop_departure_event(self, event_data):
        """Process RouteStopDeparture events"""
        try:
            logger.info(f"Processing RouteStopDeparture event: {event_data}")
            # Extract specific event type from conditions if available
            conditions = event_data.get('data', {}).get('conditions', [])
            specific_event_type = conditions[0].get('description') if conditions and len(conditions) > 0 else 'Route Stop Departure'
            
            # Create alert with specific type
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=event_data.get('data', {}).get('vehicle', {}).get('id'),
                alert_type=specific_event_type,
                severity='medium',
                status='unassigned',
                description=specific_event_type,
                data=event_data,
                timestamp=datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00')),
                client_id=event_data.get('orgId')
            )
            db.session.add(alert)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error processing RouteStopDeparture event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            return False

    def _process_route_stop_arrival_event(self, event_data):
        """Process RouteStopArrival events"""
        try:
            logger.info(f"Processing RouteStopArrival event: {event_data}")
            # Extract specific event type from conditions if available
            conditions = event_data.get('data', {}).get('conditions', [])
            specific_event_type = conditions[0].get('description') if conditions and len(conditions) > 0 else 'Route Stop Arrival'
            
            # Create alert with specific type
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=event_data.get('data', {}).get('vehicle', {}).get('id'),
                alert_type=specific_event_type,
                severity='medium',
                status='unassigned',
                description=specific_event_type,
                data=event_data,
                timestamp=datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00')),
                client_id=event_data.get('orgId')
            )
            db.session.add(alert)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error processing RouteStopArrival event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            return False

    def _process_geofence_exit_event(self, event_data):
        """Process GeofenceExit events"""
        try:
            logger.info(f"Processing GeofenceExit event: {event_data}")
            # Extract specific event type from conditions if available
            conditions = event_data.get('data', {}).get('conditions', [])
            specific_event_type = conditions[0].get('description') if conditions and len(conditions) > 0 else 'Geofence Exit'
            
            # Create alert with specific type
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=event_data.get('data', {}).get('vehicle', {}).get('id'),
                alert_type=specific_event_type,
                severity='medium',
                status='unassigned',
                description=specific_event_type,
                data=event_data,
                timestamp=datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00')),
                client_id=event_data.get('orgId')
            )
            db.session.add(alert)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error processing GeofenceExit event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, e, str(e.__traceback__))
            return False

    def _process_speeding_event(self, event_data):
        """Process SevereSpeedingStarted and SevereSpeedingEnded events"""
        try:
            logger.info(f"Processing speeding event: {event_data}")
            
            # Extract org ID and find SamsaraClient
            org_id = event_data.get('orgId')
            samsara_client_instance = SamsaraClient.query.filter_by(org_id=org_id).first()
            if not samsara_client_instance:
                logger.error(f"No SamsaraClient found for org_id: {org_id}")
                self._log_webhook_error(event_data, f"SamsaraClient not found for org_id {org_id}", "SamsaraClient lookup failed")
                return False
                
            # Get company
            company = None
            if samsara_client_instance.company:
                company = samsara_client_instance.company
                logger.info(f"Using existing Company (DB ID: {company.id}, Name: {company.name}) linked to SamsaraClient (DB ID: {samsara_client_instance.id}) (speeding event).")
            
            if not company:
                logger.error(f"No Company found for SamsaraClient (DB ID: {samsara_client_instance.id})")
                self._log_webhook_error(event_data, "Company not found", "Company lookup failed")
                return False
                
            # Extract vehicle ID
            vehicle_data = event_data.get('data', {}).get('data', {}).get('vehicle', {})
            vehicle_id = vehicle_data.get('id')
            if not vehicle_id:
                logger.error("No vehicle ID found in speeding event payload")
                self._log_webhook_error(event_data, "No vehicle ID in payload", "Vehicle ID extraction failed")
                return False
                
            # Get or create vehicle
            vehicle = SamsaraVehicle.query.filter_by(vehicle_id=vehicle_id).first()
            if not vehicle:
                # Set a default name for the vehicle if not provided
                vehicle_name = vehicle_data.get('name', f'Vehicle {vehicle_id}')
                vehicle = SamsaraVehicle(
                    vehicle_id=vehicle_id,
                    name=vehicle_name,  # Add name field
                    company_id=company.id
                )
                db.session.add(vehicle)
                try:
                    db.session.commit()
                    logger.info(f"Created new vehicle record for Samsara ID: {vehicle_id}")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Failed to create vehicle record: {str(e)}")
                    self._log_webhook_error(event_data, str(e), "Vehicle creation failed")
                    return False
            elif vehicle.company_id != company.id:
                vehicle.company_id = company.id
                logger.info(f"Updated vehicle company ID to {company.id}")
                
            # Create alert
            event_type = event_data.get('eventType')
            description = f"Vehicle {event_type}"
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(event_data.get('eventTime').replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
                logger.warning("Could not parse event timestamp, using current time")
            
            alert = SamsaraAlert(
                alert_id=event_data.get('eventId'),
                vehicle_id=vehicle.id,
                alert_type=event_type,
                severity='high',
                status='unassigned',
                description=description,
                data=event_data,
                timestamp=timestamp,
                client_id=samsara_client_instance.id
            )
            
            db.session.add(alert)
            try:
                db.session.commit()
                logger.info(f"Created alert for {event_type} event")
                return True
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to create alert: {str(e)}")
                self._log_webhook_error(event_data, str(e), "Alert creation failed")
                return False
                
        except Exception as e:
            logger.error(f"Error processing speeding event: {str(e)}", exc_info=True)
            self._log_webhook_error(event_data, str(e), "Speeding event processing failed")
            return False

    def _extract_driver_info(self, data):
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
                
                # Recursively search all values
                for value in obj.values():
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
            driver = find_driver(data)
            if driver:
                logger.info(f"Found driver: {driver}")
            return driver
        except Exception as e:
            logger.error(f"Error extracting driver info: {str(e)}")
            return None

    def _extract_driver_data(self, data):
        """
        Helper function to recursively extract full driver data from any nested structure.
        Returns the first found driver object or None if not found.
        """
        def find_driver_data(obj):
            if not obj or not isinstance(obj, (dict, list)):
                return None
                
            # If it's a dictionary
            if isinstance(obj, dict):
                # Direct driver object check
                if 'driver' in obj and isinstance(obj['driver'], dict):
                    driver = obj['driver']
                    if 'id' in driver:  # Must have an ID to be valid
                        return driver
                
                # Check geofence events
                if 'geofenceEntry' in obj or 'geofenceExit' in obj:
                    event_data = obj.get('geofenceEntry') or obj.get('geofenceExit')
                    if event_data and 'vehicle' in event_data:
                        vehicle = event_data['vehicle']
                        if 'driver' in vehicle and isinstance(vehicle['driver'], dict):
                            driver = vehicle['driver']
                            if 'id' in driver:
                                return driver
                
                # Recursively search all values
                for key, value in obj.items():
                    result = find_driver_data(value)
                    if result:
                        return result
                        
            # If it's a list
            elif isinstance(obj, list):
                for item in obj:
                    result = find_driver_data(item)
                    if result:
                        return result
                        
            return None
            
        try:
            return find_driver_data(data)
        except Exception as e:
            logger.error(f"Error extracting driver data: {str(e)}")
            return None

    def _format_location(self, data):
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
                if 'geofence' in obj and isinstance(obj['geofence'], dict) and 'name' in obj['geofence']:
                    return f"Geofence: {obj['geofence']['name']}"
                
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
                for value in obj.values():
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
            if location:
                logger.info(f"Found location: {location}")
            return location
        except Exception as e:
            logger.error(f"Error formatting location: {str(e)}")
            return None

    def get_vehicle_locations(self, vehicle_ids=None):
        """Get real-time location data for vehicles using the /fleet/vehicles/stats?types=gps endpoint."""
        try:
            params = {
                'types': 'gps' # Requesting only GPS data
            }
            if vehicle_ids:
                if isinstance(vehicle_ids, list):
                    params['vehicleIds'] = ','.join(map(str, vehicle_ids))
                else:
                    params['vehicleIds'] = str(vehicle_ids)
            else:
                # If no specific vehicle_ids, this would fetch for all vehicles.
                # Depending on use case, might want to prevent this or handle it.
                logger.info("Fetching GPS locations for all vehicles as no specific IDs were provided.")

            logger.info(f"Fetching vehicle GPS locations with params: {params} from endpoint {self.base_url}/fleet/vehicles/stats")
            response = requests.get(
                f'{self.base_url}/fleet/vehicles/stats',
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            stats_data = response.json().get('data', [])
            
            locations = []
            if stats_data:
                logger.info("=== Vehicle GPS Locations Sample (from Stats API) ===")
                for item in stats_data:
                    if 'gps' in item and item['gps']:
                        # Construct a location object similar to what the old endpoint might have provided
                        # or what the frontend expects. Adjust as needed.
                        location_info = {
                            'vehicleId': item.get('id'),
                            'name': item.get('name'), # Vehicle name might be useful context
                            'time': item['gps'].get('time'),
                            'latitude': item['gps'].get('latitude'),
                            'longitude': item['gps'].get('longitude'),
                            'heading': item['gps'].get('headingDegrees'),
                            'speed': item['gps'].get('speedMilesPerHour'), # Or speedMetersPerSecond
                            'address': item['gps'].get('reverseGeo', {}).get('formattedLocation'),
                            # Include the full gps object if frontend needs more details
                            '_raw_gps': item['gps'] 
                        }
                        locations.append(location_info)
                    else:
                        logger.warning(f"No GPS data in stats item for vehicleId {item.get('id')}")
                
                if locations:
                    logger.info(json.dumps(locations[0], indent=2)) # Log first processed location
                    logger.info(f"Total location records processed: {len(locations)}")
                else:
                    logger.info("No GPS data found in the stats response for the given vehicle(s).")
            return locations
        except Exception as e:
            logger.error(f"Error fetching vehicle locations via stats API: {str(e)}")
            raise

    def get_vehicle_stats(self, vehicle_id=None):
        """Get vehicle stats from Samsara"""
        try:
            # Format parameters correctly for v1 API based on documentation
            # 'types' should be a comma-separated string.
            # 'vehicleIds' should be used for filtering by vehicle.
            params = {
                'types': ','.join(['engineStates', 'fuelPercents', 'obdOdometerMeters', 'obdEngineSeconds']),
            }
            if vehicle_id:
                params['vehicleIds'] = str(vehicle_id) # API expects comma-separated list or single ID string
            
            logger.info(f"Fetching vehicle stats with params: {params} from endpoint {self.base_url}/fleet/vehicles/stats")
            response = requests.get(
                f'{self.base_url}/fleet/vehicles/stats',
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            if data:
                logger.info("=== Vehicle Stats Sample From Snapshot API ===")
                # The data is a list, even for a single vehicleId, containing stats for that vehicle.
                logger.info(json.dumps(data[0] if data else {}, indent=2))
                logger.info(f"Total stats records received: {len(data)}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching vehicle stats: {str(e)}")
            # Re-raise the exception so the route can handle it and return a proper JSON error
            raise

    def get_driver_hos_logs(self, driver_id, start_time=None, end_time=None):
        """Get driver HOS logs from Samsara"""
        try:
            # If no time range provided, default to last 24 hours
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(days=1)

            # Convert to RFC 3339 format
            start_time_str = start_time.isoformat() + 'Z'
            end_time_str = end_time.isoformat() + 'Z'
            
            params = {
                'driverIds': [driver_id],
                'startTime': start_time_str,
                'endTime': end_time_str
            }
            
            logger.info(f"Fetching HOS logs with params: {params}")
            response = requests.get(
                f'{self.base_url}/fleet/hos/logs',
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            if data:
                logger.info("=== HOS Logs Sample ===")
                logger.info(json.dumps(data[0], indent=2))
                logger.info(f"Total HOS records: {len(data)}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching HOS logs: {str(e)}")
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                logger.error("HOS logs access unauthorized. Please check API permissions.")
            raise

    def get_driver_hos_violations(self, driver_id, start_time=None, end_time=None):
        """Get HOS violations for a driver"""
        try:
            # If no time range provided, default to last 7 days
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(days=7)

            # Convert to RFC 3339 format
            start_time_str = start_time.isoformat() + 'Z'
            end_time_str = end_time.isoformat() + 'Z'
            
            params = {
                'driverIds': [driver_id],
                'startTime': start_time_str,
                'endTime': end_time_str
            }
            
            logger.info(f"Fetching HOS violations with params: {params}")
            response = requests.get(
                f'{self.base_url}/fleet/hos/violations',
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            if data:
                logger.info("=== HOS Violations Sample ===")
                logger.info(json.dumps(data[0], indent=2))
                logger.info(f"Total violations: {len(data)}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching HOS violations: {str(e)}")
            raise

    def get_driver_hos_daily_logs(self, driver_id, start_time=None, end_time=None):
        """Get daily HOS logs summary for a driver"""
        try:
            # If no time range provided, default to last 7 days
            if not end_time:
                end_time = datetime.now(timezone.utc)
            if not start_time:
                start_time = end_time - timedelta(days=7)

            # Ensure we're not querying future dates
            current_time = datetime.now(timezone.utc)
            if end_time > current_time:
                end_time = current_time
            if start_time > current_time:
                start_time = current_time - timedelta(days=7)

            # Convert to RFC 3339 format with Z suffix
            # Remove microseconds and convert to UTC
            start_time_utc = start_time.replace(microsecond=0)
            end_time_utc = end_time.replace(microsecond=0)
            
            # Format as YYYY-MM-DDTHH:mm:ssZ
            start_time_str = start_time_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
            end_time_str = end_time_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            params = {
                'driverIds': [driver_id],  # API expects array of strings
                'startTime': start_time_str,
                'endTime': end_time_str
            }
            
            logger.info(f"Fetching HOS daily logs with params: {params}")
            response = requests.get(
                f'{self.base_url}/fleet/hos/logs',  # Updated endpoint URL
                headers=self.headers,
                params=params
            )
            
            # Log the raw response for debugging
            logger.debug(f"Raw HOS daily logs response: {response.text}")
            
            # Handle different error cases
            if response.status_code == 401:
                logger.error("Unauthorized access to HOS daily logs. Check API key.")
                raise Exception("Unauthorized access. Please check API credentials.")
            elif response.status_code == 403:
                logger.error("Forbidden access to HOS daily logs. Check permissions.")
                raise Exception("Access forbidden. Please check API permissions.")
            elif response.status_code == 404:
                logger.error(f"HOS daily logs not found for driver {driver_id}")
                return []  # Return empty list instead of raising exception for 404
            
            response.raise_for_status()
            data = response.json()
            
            # Process the logs to create daily summaries
            daily_logs = {}
            
            # Group logs by day and calculate totals
            # The 'data' field from the API response is a list of objects,
            # each containing 'driver' info and an 'hosLogs' array.
            for driver_log_group in data.get('data', []):
                # We need to iterate through the 'hosLogs' array for each driver group
                for log in driver_log_group.get('hosLogs', []):
                    log_start = datetime.fromisoformat(log['logStartTime'].replace('Z', '+00:00'))
                    log_end = datetime.fromisoformat(log['logEndTime'].replace('Z', '+00:00'))
                    duration = (log_end - log_start).total_seconds() / 60  # Convert to minutes
                    
                    # Get the day key (YYYY-MM-DD)
                    day_key = log_start.strftime('%Y-%m-%d')
                    
                    if day_key not in daily_logs:
                        daily_logs[day_key] = {
                            'date': day_key,
                            'driveTime': 0,
                            'onDutyTime': 0,
                            'offDutyTime': 0,
                            'sleeperTime': 0, # Added sleeperTime
                            'violations': [] # Assuming you might want to add violations later
                        }
                    
                    # Update durations based on status
                    status = log.get('hosStatusType', '').lower()
                    if status == 'driving':
                        daily_logs[day_key]['driveTime'] += duration
                    elif status == 'onduty':
                        daily_logs[day_key]['onDutyTime'] += duration
                    elif status == 'offduty':
                        daily_logs[day_key]['offDutyTime'] += duration
                    elif status == 'sleeper': # Added handling for sleeper status
                        daily_logs[day_key]['sleeperTime'] += duration
            
            # Convert to list and sort by date
            result = list(daily_logs.values())
            result.sort(key=lambda x: x['date'], reverse=True)
            
            if result:
                logger.info("=== HOS Daily Logs Sample ===")
                logger.info(json.dumps(result[0], indent=2))
                logger.info(f"Total daily logs: {len(result)}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching HOS daily logs: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            return []  # Return empty list on error
        except Exception as e:
            logger.error(f"Unexpected error in get_driver_hos_daily_logs: {str(e)}")
            return []  # Return empty list on error

    def get_vehicle_assignments(self, vehicle_ids=None):
        """Get current driver assignments for vehicles using the new endpoint"""
        try:
            params = {
                'filterBy': 'vehicles'  # Required by the new endpoint
            }
            if vehicle_ids:
                # The API expects a comma-separated string for multiple IDs or a single ID string.
                if isinstance(vehicle_ids, list):
                    params['vehicleIds'] = ','.join(map(str, vehicle_ids))
                else:
                    params['vehicleIds'] = str(vehicle_ids) # Single ID string
            
            # No explicit time range needed for current assignments, API defaults should be fine.
            # If historical assignments were needed, startTime and endTime would be added.

            logger.info(f"Fetching vehicle assignments with params: {params} from endpoint {self.base_url}/fleet/driver-vehicle-assignments")
            response = requests.get(
                f'{self.base_url}/fleet/driver-vehicle-assignments', # New endpoint
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json().get('data', []) # Assuming response structure provides 'data'
            
            if data:
                logger.info("=== Vehicle Assignments Sample (New Endpoint) ===")
                logger.info(json.dumps(data[0] if data else {}, indent=2))
                logger.info(f"Total assignment records received: {len(data)}")
            return data
        except Exception as e:
            logger.error(f"Error fetching vehicle assignments: {str(e)}")
            # Re-raise so the route can handle it and return JSON error
            raise

    def get_trailer_locations(self, trailer_id=None):
        """Get trailer locations from Samsara"""
        try:
            # Format parameters correctly for API
            params = {}
            if trailer_id:
                params['trailerId'] = trailer_id
            
            # The API endpoint might be /fleet/trailers/locations for all, 
            # or /fleet/trailers/{trailer_id}/locations for a specific one.
            # Given the function signature and common patterns, we aim for specific if ID is provided.
            # However, the docs are not super clear. Let's try with /fleet/trailers/locations and trailerId as param.
            # If this specific endpoint doesn't support filtering by a single trailerId in query params,
            # we might need to adjust to fetch all and filter, or change the endpoint path structure.

            endpoint = f'{self.base_url}/fleet/trailers/locations'
            # If a specific trailer_id is provided, and the API supports a path parameter for it:
            # endpoint = f'{self.base_url}/fleet/trailers/{trailer_id}/locations'
            # For now, using query parameter as per the general structure of other similar calls.

            logger.info(f"Fetching trailer locations from {endpoint} with params: {params}")
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params # Pass trailerId as a query param
            )
            response.raise_for_status()
            data = response.json().get('data', [])
            
            if data:
                logger.info("=== Trailer Locations Sample ===")
                # If multiple trailers are returned and we only want one, we might need to filter here.
                # For now, assume API returns data for the specified trailerId if param is effective.
                logger.info(json.dumps(data[0] if isinstance(data, list) and data else data, indent=2))
                logger.info(f"Total location records: {len(data) if isinstance(data, list) else 1}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching trailer locations: {str(e)}")
            raise

    def create_or_update_driver(self, driver_data, company_id=None):
        """Create or update a driver record from Samsara data"""
        try:
            driver_id = driver_data.get('id')
            if not driver_id:
                logger.warning("No driver ID found in driver data")
                return None

            # Check if driver already exists
            driver = SamsaraDriver.query.filter_by(driver_id=driver_id).first()
            
            if driver:
                # Update existing driver
                driver.name = driver_data.get('name', driver.name)
                driver.username = driver_data.get('username', driver.username)
                driver.phone = driver_data.get('phone', driver.phone)
                driver.email = driver_data.get('email', driver.email)
                driver.data = driver_data
                driver.updated_at = datetime.utcnow()
                
                # Update company if provided and different
                if company_id and driver.company_id != company_id:
                    driver.company_id = company_id
                    
                logger.info(f"Updated existing driver: {driver.name} (ID: {driver_id})")
            else:
                # Create new driver
                driver = SamsaraDriver(
                    driver_id=driver_id,
                    name=driver_data.get('name', f'Driver {driver_id}'),
                    username=driver_data.get('username'),
                    phone=driver_data.get('phone'),
                    email=driver_data.get('email'),
                    company_id=company_id,
                    external_ids=driver_data.get('externalIds', {}),
                    data=driver_data,
                    is_active=driver_data.get('isDeactivated', False) == False
                )
                db.session.add(driver)
                logger.info(f"Created new driver: {driver.name} (ID: {driver_id})")
            
            db.session.commit()
            return driver
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating/updating driver: {str(e)}")
            return None

    def sync_drivers_for_company(self, company_id):
        """Sync all drivers from Samsara API for a specific company"""
        try:
            # Get company's Samsara client
            company = Company.query.get(company_id)
            if not company:
                logger.error(f"Company {company_id} not found")
                return False
                
            samsara_client = company.samsara_clients.filter_by(is_active=True).first()
            if not samsara_client:
                logger.error(f"No active Samsara client found for company {company_id}")
                return False
            
            # Use the company's API key to fetch drivers
            temp_service = SamsaraService(api_key=samsara_client.api_key)
            drivers_data = temp_service.get_drivers()
            
            if not drivers_data:
                logger.warning(f"No drivers found for company {company_id}")
                return True
            
            # Create/update driver records
            created_count = 0
            updated_count = 0
            
            for driver_data in drivers_data:
                existing_driver = SamsaraDriver.query.filter_by(driver_id=driver_data.get('id')).first()
                if existing_driver:
                    self.create_or_update_driver(driver_data, company_id)
                    updated_count += 1
                else:
                    self.create_or_update_driver(driver_data, company_id)
                    created_count += 1
            
            logger.info(f"Driver sync complete for company {company_id}: {created_count} created, {updated_count} updated")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing drivers for company {company_id}: {str(e)}")
            return False

# Example usage (for testing or other modules)
if __name__ == '__main__':
    # This part is for direct execution testing and might need a Flask app context
    # For now, it will just demonstrate class instantiation if run directly
    # To fully test, you would need to mock Flask current_app and db
    pass 