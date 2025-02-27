from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Check commission_partner table structure
    partner_columns = db.session.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'commission_partner'
        ORDER BY ordinal_position
    """)).fetchall()
    
    print("Commission Partner Table Structure:")
    for col in partner_columns:
        print(f"- {col[0]}: {col[1]} (Nullable: {col[2]})")
    
    print("\nCommission Table Structure:")
    commission_columns = db.session.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'commission'
        ORDER BY ordinal_position
    """)).fetchall()
    
    for col in commission_columns:
        print(f"- {col[0]}: {col[1]} (Nullable: {col[2]})")
        
    # Check foreign keys
    print("\nForeign Keys:")
    foreign_keys = db.session.execute(text("""
        SELECT
            tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND (tc.table_name = 'commission_partner' OR tc.table_name = 'commission')
    """)).fetchall()
    
    for fk in foreign_keys:
        print(f"- {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}") 