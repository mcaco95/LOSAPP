"""Add SamsaraDriver model and improve DOT infractions

Revision ID: add_samsara_driver_dot
Revises: add_dot_infractions
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_samsara_driver_dot'
down_revision = 'add_dot_infractions'
branch_labels = None
depends_on = None


def upgrade():
    # Create samsara_drivers table
    op.create_table('samsara_drivers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('driver_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('license_number', sa.String(length=50), nullable=True),
    sa.Column('license_state', sa.String(length=5), nullable=True),
    sa.Column('license_class', sa.String(length=10), nullable=True),
    sa.Column('company_id', sa.Integer(), nullable=True),
    sa.Column('external_ids', sa.JSON(), nullable=True),
    sa.Column('data', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('driver_id')
    )

    # Add new columns to dot_infractions table
    op.add_column('dot_infractions', sa.Column('company_id', sa.Integer(), nullable=True))
    op.add_column('dot_infractions', sa.Column('primary_driver_id', sa.Integer(), nullable=True))
    op.add_column('dot_infractions', sa.Column('linked_vehicles', sa.JSON(), nullable=True))
    
    # Create foreign key constraints
    op.create_foreign_key('fk_dot_infractions_company', 'dot_infractions', 'company', ['company_id'], ['id'])
    op.create_foreign_key('fk_dot_infractions_driver', 'dot_infractions', 'samsara_drivers', ['primary_driver_id'], ['id'])


def downgrade():
    # Remove foreign key constraints
    op.drop_constraint('fk_dot_infractions_driver', 'dot_infractions', type_='foreignkey')
    op.drop_constraint('fk_dot_infractions_company', 'dot_infractions', type_='foreignkey')
    
    # Remove columns from dot_infractions
    op.drop_column('dot_infractions', 'linked_vehicles')
    op.drop_column('dot_infractions', 'primary_driver_id')
    op.drop_column('dot_infractions', 'company_id')
    
    # Drop samsara_drivers table
    op.drop_table('samsara_drivers') 