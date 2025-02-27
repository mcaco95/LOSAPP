"""add commission partner and commission models

Revision ID: add_commission_models
Revises: 948b19bed1c0
Create Date: 2024-02-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'add_commission_models'
down_revision = '948b19bed1c0'
branch_labels = None
depends_on = None


def upgrade():
    # Create commission_partner table
    op.create_table('commission_partner',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('commission_tier', sa.String(length=20), nullable=True),
        sa.Column('custom_rates', sa.Boolean(), nullable=True),
        sa.Column('partner_metadata', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['referrer_id'], ['commission_partner.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create commission table
    op.create_table('commission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('partner_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('service_type', sa.String(length=20), nullable=False),
        sa.Column('is_initial_month', sa.Boolean(), nullable=True),
        sa.Column('month_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('commission_metadata', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['partner_id'], ['commission_partner.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('commission')
    op.drop_table('commission_partner') 