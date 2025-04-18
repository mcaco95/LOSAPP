"""add_samsara_integration

Revision ID: add_samsara_integration
Revises: 8f30eb0ed5dd
Create Date: 2025-04-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_samsara_integration'
down_revision = '8f30eb0ed5dd'
branch_labels = None
depends_on = None


def upgrade():
    # Create Samsara vehicles table
    op.create_table('samsara_vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('license_plate', sa.String(length=20), nullable=True),
        sa.Column('vin', sa.String(length=17), nullable=True),
        sa.Column('make', sa.String(length=50), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vehicle_id')
    )

    # Create Samsara webhook events table
    op.create_table('samsara_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('webhook_id', sa.String(length=100), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create Samsara vehicle locations table
    op.create_table('samsara_vehicle_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['vehicle_id'], ['samsara_vehicles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create Samsara alerts table
    op.create_table('samsara_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.String(length=100), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['vehicle_id'], ['samsara_vehicles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alert_id')
    )

    # Create Samsara alert assignments table
    op.create_table('samsara_alert_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['samsara_alerts.id'], ),
        sa.ForeignKeyConstraint(['assigned_to'], ['user.id'], ),
        sa.ForeignKeyConstraint(['assigned_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('samsara_alert_assignments')
    op.drop_table('samsara_alerts')
    op.drop_table('samsara_vehicle_locations')
    op.drop_table('samsara_webhook_events')
    op.drop_table('samsara_vehicles') 