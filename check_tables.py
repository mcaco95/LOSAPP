from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Check if the commission_partner table exists
    result = db.session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'commission_partner'
        )
    """)).scalar()
    
    print(f"commission_partner table exists: {result}")
    
    # Check if the commission table exists
    result = db.session.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'commission'
        )
    """)).scalar()
    
    print(f"commission table exists: {result}")
    
    # List all tables in the database
    tables = db.session.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)).fetchall()
    
    print("\nAll tables in the database:")
    for table in tables:
        print(f"- {table[0]}") 