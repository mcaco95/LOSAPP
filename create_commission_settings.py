from app import create_app, db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, text

app = create_app()

with app.app_context():
    # Check if the table already exists
    result = db.session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'commission_settings'
        )
    """)).scalar()
    
    if result:
        print("commission_settings table already exists")
    else:
        # Create the table
        db.session.execute(text("""
            CREATE TABLE commission_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(50) NOT NULL UNIQUE,
                value FLOAT NOT NULL,
                description VARCHAR(255),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Insert default values
        db.session.execute(text("""
            INSERT INTO commission_settings (key, value, description, created_at, updated_at)
            VALUES 
            ('first_2_years_rate', 0.10, 'Commission rate for the first 2 years (24 months)', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('after_2_years_rate', 0.025, 'Commission rate after 2 years (month 25+)', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('network_commission_rate', 0.025, 'Commission rate for partners on their network''s sales', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        
        db.session.commit()
        print("commission_settings table created and populated with default values")
        
    # Verify the table contents
    settings = db.session.execute(text("SELECT * FROM commission_settings")).fetchall()
    print("\nCurrent commission settings:")
    for setting in settings:
        print(f"- {setting.key}: {setting.value} ({setting.description})") 