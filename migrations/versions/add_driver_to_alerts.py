"""Add driver relationship to SamsaraAlert

Revision ID: add_driver_to_alerts
Revises: add_samsara_driver_dot
Create Date: 2025-01-27 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json

# revision identifiers, used by Alembic.
revision = 'add_driver_to_alerts'
down_revision = 'add_samsara_driver_dot'
branch_labels = None
depends_on = None


def upgrade():
    # Add driver_id column to samsara_alerts
    op.add_column('samsara_alerts', sa.Column('driver_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_samsara_alerts_driver', 'samsara_alerts', 'samsara_drivers', ['driver_id'], ['id'])
    
    # Data migration: Link existing alerts to drivers where possible
    connection = op.get_bind()
    
    # Get all alerts with driver data in JSON
    alerts_result = connection.execute(sa.text("""
        SELECT id, data FROM samsara_alerts WHERE data IS NOT NULL
    """))
    
    for alert_row in alerts_result:
        alert_id = alert_row[0]
        alert_data = alert_row[1]
        
        if not alert_data:
            continue
            
        # Extract driver info from JSON data (similar to _extract_driver_info function)
        driver_name = extract_driver_name_from_json(alert_data)
        
        if driver_name and driver_name != 'Unassigned':
            # Try to find matching driver by name
            driver_result = connection.execute(sa.text("""
                SELECT id FROM samsara_drivers 
                WHERE name ILIKE :driver_name 
                LIMIT 1
            """), {'driver_name': f'%{driver_name}%'})
            
            driver_row = driver_result.fetchone()
            if driver_row:
                driver_id = driver_row[0]
                # Update alert with driver_id
                connection.execute(sa.text("""
                    UPDATE samsara_alerts 
                    SET driver_id = :driver_id 
                    WHERE id = :alert_id
                """), {'driver_id': driver_id, 'alert_id': alert_id})


def downgrade():
    # Remove foreign key and column
    op.drop_constraint('fk_samsara_alerts_driver', 'samsara_alerts', type_='foreignkey')
    op.drop_column('samsara_alerts', 'driver_id')


def extract_driver_name_from_json(data):
    """Extract driver name from nested JSON structure"""
    def find_driver(obj):
        if not obj or not isinstance(obj, (dict, list)):
            return None
        
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
                
        elif isinstance(obj, list):
            for item in obj:
                result = find_driver(item)
                if result:
                    return result
                
        return None
    
    try:
        return find_driver(data)
    except Exception:
        return None 