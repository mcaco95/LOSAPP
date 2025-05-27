"""Add DOT infractions and violations tables

Revision ID: add_dot_infractions
Revises: add_alert_activities
Create Date: 2025-01-27 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_dot_infractions'
down_revision = 'add_alert_activities'
branch_labels = None
depends_on = None


def upgrade():
    # Create dot_infractions table
    op.create_table('dot_infractions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('carrier_name', sa.String(length=200), nullable=True),
        sa.Column('carrier_address', sa.Text(), nullable=True),
        sa.Column('us_dot', sa.String(length=20), nullable=True),
        sa.Column('mc_number', sa.String(length=20), nullable=True),
        sa.Column('state_id', sa.String(length=20), nullable=True),
        sa.Column('report_number', sa.String(length=50), nullable=False),
        sa.Column('report_state', sa.String(length=5), nullable=True),
        sa.Column('inspection_state', sa.String(length=5), nullable=True),
        sa.Column('inspection_date', sa.Date(), nullable=False),
        sa.Column('start_end_time', sa.String(length=20), nullable=True),
        sa.Column('inspection_level', sa.String(length=50), nullable=True),
        sa.Column('inspection_facility', sa.String(length=100), nullable=True),
        sa.Column('post_crash', sa.String(length=10), nullable=True),
        sa.Column('inspection_location', sa.String(length=200), nullable=True),
        sa.Column('hazmat_placard_required', sa.String(length=10), nullable=True),
        sa.Column('inspection_county', sa.String(length=100), nullable=True),
        sa.Column('driver_name', sa.String(length=100), nullable=True),
        sa.Column('driver_age', sa.Integer(), nullable=True),
        sa.Column('driver_license_state', sa.String(length=5), nullable=True),
        sa.Column('shipper_info_available', sa.Boolean(), nullable=True),
        sa.Column('vehicles_data', sa.JSON(), nullable=True),
        sa.Column('pdf_file_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_number')
    )

    # Create dot_violations table
    op.create_table('dot_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('infraction_id', sa.Integer(), nullable=False),
        sa.Column('unit_type', sa.String(length=20), nullable=True),
        sa.Column('oos_indicator', sa.String(length=5), nullable=True),
        sa.Column('section_code', sa.String(length=20), nullable=False),
        sa.Column('violation_description', sa.Text(), nullable=False),
        sa.Column('violation_category', sa.String(length=50), nullable=True),
        sa.Column('emergency_equipment', sa.String(length=10), nullable=True),
        sa.Column('citation', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['infraction_id'], ['dot_infractions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create dot_infraction_alerts table (linking table)
    op.create_table('dot_infraction_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('infraction_id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('linked_by', sa.Integer(), nullable=False),
        sa.Column('link_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['samsara_alerts.id'], ),
        sa.ForeignKeyConstraint(['infraction_id'], ['dot_infractions.id'], ),
        sa.ForeignKeyConstraint(['linked_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('dot_infraction_alerts')
    op.drop_table('dot_violations')
    op.drop_table('dot_infractions') 