"""alter samsara alerts vehicle id

Revision ID: alter_samsara_alerts_vehicle_id
Revises: ce7fb773ca5f
Create Date: 2024-04-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'alter_samsara_alerts_vehicle_id'
down_revision = 'ce7fb773ca5f'
branch_labels = None
depends_on = None


def upgrade():
    # Change vehicle_id column type from Integer to BigInteger
    op.alter_column('samsara_alerts', 'vehicle_id',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False)


def downgrade():
    # Note: This downgrade may fail if there are values too large for Integer
    op.alter_column('samsara_alerts', 'vehicle_id',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False) 