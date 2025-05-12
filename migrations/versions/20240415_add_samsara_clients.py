"""Add Samsara clients support

Revision ID: 20240415_add_samsara_clients
Revises: vehicle_ids_bigint
Create Date: 2024-04-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20240415_add_samsara_clients'
down_revision = 'vehicle_ids_bigint'
branch_labels = None
depends_on = None

def upgrade():
    # Create samsara_clients table
    op.create_table('samsara_clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('org_id', sa.BigInteger(), nullable=False),
        sa.Column('api_key', sa.String(length=100), nullable=False),
        sa.Column('webhook_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id')
    )

    # Add client_id to samsara_webhook_events (nullable initially)
    op.add_column('samsara_webhook_events', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_webhook_events_client_id',
        'samsara_webhook_events', 'samsara_clients',
        ['client_id'], ['id']
    )

    # Add client_id to samsara_alerts (nullable initially)
    op.add_column('samsara_alerts', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_alerts_client_id',
        'samsara_alerts', 'samsara_clients',
        ['client_id'], ['id']
    )

    # Create default client for existing data
    op.execute("""
        INSERT INTO samsara_clients (name, org_id, api_key, created_at, updated_at)
        VALUES ('Default Client', 7000073, 'samsara_api_key', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """)

    # Associate existing records with default client
    op.execute("""
        UPDATE samsara_webhook_events
        SET client_id = (SELECT id FROM samsara_clients WHERE name = 'Default Client')
    """)

    op.execute("""
        UPDATE samsara_alerts
        SET client_id = (SELECT id FROM samsara_clients WHERE name = 'Default Client')
    """)

    # Now make client_id non-nullable after setting default values
    op.alter_column('samsara_webhook_events', 'client_id', nullable=False)
    op.alter_column('samsara_alerts', 'client_id', nullable=False)

def downgrade():
    # Remove client_id from samsara_alerts
    op.drop_constraint('fk_alerts_client_id', 'samsara_alerts', type_='foreignkey')
    op.drop_column('samsara_alerts', 'client_id')

    # Remove client_id from samsara_webhook_events
    op.drop_constraint('fk_webhook_events_client_id', 'samsara_webhook_events', type_='foreignkey')
    op.drop_column('samsara_webhook_events', 'client_id')

    # Drop samsara_clients table
    op.drop_table('samsara_clients') 