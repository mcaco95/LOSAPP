"""Ensure all vehicle_id columns are BIGINT

Revision ID: vehicle_ids_bigint
Revises: add_samsara_data
Create Date: 2024-04-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'vehicle_ids_bigint'
down_revision = 'add_samsara_data'
branch_labels = None
depends_on = None

def upgrade():
    # First, ensure samsara_vehicles.vehicle_id is BIGINT
    op.alter_column('samsara_vehicles', 'vehicle_id',
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using='vehicle_id::bigint'
    )
    
    # Then, ensure samsara_alerts.vehicle_id is BIGINT
    op.alter_column('samsara_alerts', 'vehicle_id',
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using='vehicle_id::bigint'
    )
    
    # Finally, ensure samsara_vehicle_locations.vehicle_id is BIGINT
    op.alter_column('samsara_vehicle_locations', 'vehicle_id',
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using='vehicle_id::bigint'
    )

def downgrade():
    # Note: This downgrade may fail if there are values too large for INTEGER
    op.alter_column('samsara_vehicle_locations', 'vehicle_id',
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using='vehicle_id::integer'
    )
    
    op.alter_column('samsara_alerts', 'vehicle_id',
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using='vehicle_id::integer'
    )
    
    op.alter_column('samsara_vehicles', 'vehicle_id',
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using='vehicle_id::integer'
    ) 