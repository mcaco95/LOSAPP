#!/usr/bin/env python3
"""
Script to populate SamsaraDriver table from existing alert data
"""

from app import create_app, db
from app.models.samsara import SamsaraAlert, SamsaraDriver, SamsaraClient
from app.models.company import Company
import json
import re
from datetime import datetime

def extract_driver_info(alert_data):
    """Extract driver information from alert JSON data"""
    if not alert_data:
        return None
    
    driver_info = {}
    
    def search_nested(obj, path=""):
        """Recursively search for driver information in nested JSON"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Look for driver-related keys
                if 'driver' in key.lower():
                    if isinstance(value, dict):
                        # Found a driver object
                        if 'id' in value:
                            driver_info['driver_id'] = value.get('id')
                        if 'name' in value:
                            driver_info['name'] = value.get('name')
                        if 'username' in value:
                            driver_info['username'] = value.get('username')
                        if 'phone' in value:
                            driver_info['phone'] = value.get('phone')
                        if 'email' in value:
                            driver_info['email'] = value.get('email')
                    elif isinstance(value, str) and value != 'Unassigned':
                        # Driver name as string
                        driver_info['name'] = value
                
                # Recursively search nested objects
                if isinstance(value, (dict, list)):
                    search_nested(value, current_path)
            
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                search_nested(item, f"{path}[{i}]")
    
    search_nested(alert_data)
    return driver_info if driver_info else None

def populate_drivers():
    """Populate SamsaraDriver table from existing alerts"""
    app = create_app()
    
    with app.app_context():
        print("Starting driver population from alerts...")
        
        # Get all alerts
        alerts = SamsaraAlert.query.all()
        print(f"Processing {len(alerts)} alerts...")
        
        drivers_found = {}
        drivers_created = 0
        alerts_updated = 0
        
        for i, alert in enumerate(alerts):
            if i % 100 == 0:
                print(f"Processed {i}/{len(alerts)} alerts...")
            
            try:
                # Extract driver info from alert data
                driver_info = extract_driver_info(alert.data)
                
                if driver_info and driver_info.get('driver_id'):
                    driver_id = driver_info['driver_id']
                    
                    # Check if we've already processed this driver
                    if driver_id not in drivers_found:
                        # Check if driver already exists in database
                        existing_driver = SamsaraDriver.query.filter_by(driver_id=driver_id).first()
                        
                        if not existing_driver:
                            # Get company from alert's client
                            company = None
                            if alert.client and alert.client.company:
                                company = alert.client.company
                            
                            # Create new driver
                            new_driver = SamsaraDriver(
                                driver_id=driver_id,
                                name=driver_info.get('name', f'Driver {driver_id}'),
                                username=driver_info.get('username'),
                                phone=driver_info.get('phone'),
                                email=driver_info.get('email'),
                                company_id=company.id if company else None,
                                data=driver_info,  # Store full extracted data
                                is_active=True,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            
                            db.session.add(new_driver)
                            drivers_found[driver_id] = new_driver
                            drivers_created += 1
                            
                            print(f"Created driver: {new_driver.name} (ID: {driver_id})")
                        else:
                            drivers_found[driver_id] = existing_driver
                    
                    # Link alert to driver
                    driver = drivers_found[driver_id]
                    if alert.driver_id != driver.id:
                        alert.driver_id = driver.id
                        alerts_updated += 1
                
            except Exception as e:
                print(f"Error processing alert {alert.id}: {str(e)}")
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\nSuccess!")
            print(f"- Created {drivers_created} new drivers")
            print(f"- Updated {alerts_updated} alerts with driver links")
            print(f"- Total unique drivers found: {len(drivers_found)}")
            
            # Show some statistics
            total_drivers = SamsaraDriver.query.count()
            linked_alerts = SamsaraAlert.query.filter(SamsaraAlert.driver_id.isnot(None)).count()
            print(f"- Total drivers in database: {total_drivers}")
            print(f"- Total alerts linked to drivers: {linked_alerts}")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error committing changes: {str(e)}")
            return False
        
        return True

if __name__ == "__main__":
    success = populate_drivers()
    if success:
        print("\nDriver population completed successfully!")
    else:
        print("\nDriver population failed!") 