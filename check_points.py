from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Query all records from point_transaction table
    result = db.session.execute(text('SELECT * FROM point_transaction')).fetchall()
    
    if not result:
        print("\nNo records found in point_transaction table.")
    else:
        print(f"\nFound {len(result)} records in point_transaction table:")
        print("-" * 50)
        for row in result:
            print(f"\nTransaction ID: {row.id}")
            print(f"User ID: {row.user_id}")
            print(f"Amount: {row.amount}")
            print(f"Reason: {row.reason}")
            print(f"Timestamp: {row.timestamp}")
            print(f"Balance After: {row.balance_after}")
            print(f"Activity Type: {row.activity_type}")
            print(f"Reference ID: {row.reference_id}")
            print(f"Metadata: {row.transaction_metadata}")
            print("-" * 30) 