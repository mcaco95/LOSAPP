"""Add alert activities table

Revision ID: add_alert_activities
Revises: 941d3e955202
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_alert_activities'
down_revision = '941d3e955202'
branch_labels = None
depends_on = None


def upgrade():
    # Create samsara_alert_activities table
    op.create_table('samsara_alert_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('old_value', sa.String(length=255), nullable=True),
        sa.Column('new_value', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('activity_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['samsara_alerts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for better query performance
    op.create_index('idx_alert_activities_alert_id', 'samsara_alert_activities', ['alert_id'])
    op.create_index('idx_alert_activities_created_at', 'samsara_alert_activities', ['created_at'])
    op.create_index('idx_alert_activities_type', 'samsara_alert_activities', ['activity_type'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_alert_activities_type', table_name='samsara_alert_activities')
    op.drop_index('idx_alert_activities_created_at', table_name='samsara_alert_activities')
    op.drop_index('idx_alert_activities_alert_id', table_name='samsara_alert_activities')
    
    # Drop table
    op.drop_table('samsara_alert_activities') 