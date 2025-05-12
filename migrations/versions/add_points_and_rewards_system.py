"""add points and rewards system

Revision ID: add_points_and_rewards
Revises: b40c6db21d43
Create Date: 2025-02-11 08:34:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_points_and_rewards'
down_revision = 'b40c6db21d43'
branch_labels = None
depends_on = None

def upgrade():
    # Add points fields to user table
    op.add_column('user', sa.Column('points', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('points_history', JSONB(), nullable=True))

    # Create company table
    op.create_table('company',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='new'),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('company_metadata', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create point_config table
    op.create_table('point_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('config_metadata', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )

    # Create reward table
    op.create_table('reward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('points_required', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reward_metadata', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create user_reward table
    op.create_table('user_reward',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reward_id', sa.Integer(), nullable=False),
        sa.Column('earned_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('redemption_metadata', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['reward_id'], ['reward.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_company_status'), 'company', ['status'], unique=False)
    op.create_index(op.f('ix_company_user_id'), 'company', ['user_id'], unique=False)
    op.create_index(op.f('ix_point_config_key'), 'point_config', ['key'], unique=True)
    op.create_index(op.f('ix_reward_points_required'), 'reward', ['points_required'], unique=False)
    op.create_index(op.f('ix_user_reward_user_id'), 'user_reward', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_reward_reward_id'), 'user_reward', ['reward_id'], unique=False)

def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_user_reward_reward_id'), table_name='user_reward')
    op.drop_index(op.f('ix_user_reward_user_id'), table_name='user_reward')
    op.drop_index(op.f('ix_reward_points_required'), table_name='reward')
    op.drop_index(op.f('ix_point_config_key'), table_name='point_config')
    op.drop_index(op.f('ix_company_user_id'), table_name='company')
    op.drop_index(op.f('ix_company_status'), table_name='company')

    # Drop tables
    op.drop_table('user_reward')
    op.drop_table('reward')
    op.drop_table('point_config')
    op.drop_table('company')

    # Drop user columns
    op.drop_column('user', 'points_history')
    op.drop_column('user', 'points')
