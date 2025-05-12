"""Change vehicle_id to BigInteger

Revision ID: e8e224f9f173
Revises: add_samsara_integration
Create Date: 2024-03-19 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e8e224f9f173'
down_revision = 'add_samsara_integration'
branch_labels = None
depends_on = None


def upgrade():
    # First, delete any alerts associated with invalid vehicles
    op.execute("""
        DELETE FROM samsara_alerts 
        WHERE vehicle_id IN (
            SELECT id FROM samsara_vehicles 
            WHERE vehicle_id ~ '[^0-9]' OR vehicle_id IS NULL
        )
    """)
    
    # Then delete the invalid vehicles
    op.execute("""
        DELETE FROM samsara_vehicles 
        WHERE vehicle_id ~ '[^0-9]' OR vehicle_id IS NULL
    """)
    
    # Now alter the column type with explicit casting
    op.execute("""
        ALTER TABLE samsara_vehicles 
        ALTER COLUMN vehicle_id TYPE BIGINT 
        USING vehicle_id::BIGINT
    """)


def downgrade():
    # Convert back to string type
    op.execute("""
        ALTER TABLE samsara_vehicles 
        ALTER COLUMN vehicle_id TYPE VARCHAR(100) 
        USING vehicle_id::VARCHAR(100)
    """)

    op.create_table('contacts',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('phone', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('email', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('role', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('company_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('is_primary', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.Column('contact_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('notes', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], name='contacts_company_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='contacts_pkey')
    )
