"""make_vehicle_id_nullable_in_samsara_alerts

Revision ID: nullable_vid
Revises: 20240415_add_samsara_clients
Create Date: 2024-05-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'nullable_vid'
down_revision = '20240415_add_samsara_clients'
branch_labels = None
depends_on = None

def upgrade():
    # Make vehicle_id nullable in samsara_alerts table
    op.alter_column('samsara_alerts', 'vehicle_id',
                    existing_type=sa.BigInteger(),
                    nullable=True)

def downgrade():
    # Make vehicle_id non-nullable again in samsara_alerts table
    # Note: This could fail if there are records with null vehicle_id
    op.alter_column('samsara_alerts', 'vehicle_id',
                    existing_type=sa.BigInteger(),
                    nullable=False) 