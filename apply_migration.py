from app import create_app, db
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

app = create_app()
with app.app_context():
    # Create commission_partner table
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS commission_partner (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES "user" (id),
            referrer_id INTEGER REFERENCES commission_partner (id),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            commission_tier VARCHAR(20) DEFAULT 'standard',
            custom_rates BOOLEAN DEFAULT FALSE,
            partner_metadata JSONB
        )
    """))
    
    # Create commission table
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS commission (
            id SERIAL PRIMARY KEY,
            partner_id INTEGER NOT NULL REFERENCES commission_partner (id),
            company_id INTEGER NOT NULL REFERENCES company (id),
            amount FLOAT NOT NULL,
            service_type VARCHAR(20) NOT NULL,
            is_initial_month BOOLEAN DEFAULT TRUE,
            month_number INTEGER DEFAULT 1,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP WITHOUT TIME ZONE,
            commission_metadata JSONB
        )
    """))
    
    db.session.commit()
    print("Tables created successfully")
    
    # Verify tables were created
    partner_exists = db.session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'commission_partner'
        )
    """)).scalar()
    
    commission_exists = db.session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'commission'
        )
    """)).scalar()
    
    print(f"commission_partner table exists: {partner_exists}")
    print(f"commission table exists: {commission_exists}") 