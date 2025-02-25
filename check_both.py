from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Get the user with ID 2 (from the transaction we saw)
    user_query = text('SELECT points, points_history FROM "user" WHERE id = 2')
    user_result = db.session.execute(user_query).first()
    
    print("\nUser Points History (from JSONB):")
    print("-" * 50)
    if user_result and user_result.points_history:
        print(f"Total Points: {user_result.points}")
        print("\nTransactions:")
        for transaction in user_result.points_history.get('transactions', []):
            print(f"\nAmount: {transaction.get('amount')}")
            print(f"Reason: {transaction.get('reason')}")
            print(f"Timestamp: {transaction.get('timestamp')}")
            print(f"Balance After: {transaction.get('balance_after')}")
            if 'metadata' in transaction:
                print(f"Metadata: {transaction['metadata']}")
            print("-" * 30)
    else:
        print("No points history found in User JSONB")
    
    print("\n\nPoint Transaction Table Contents:")
    print("-" * 50)
    transactions = db.session.execute(text('SELECT * FROM point_transaction ORDER BY timestamp')).fetchall()
    if transactions:
        for tx in transactions:
            print(f"\nTransaction ID: {tx.id}")
            print(f"Amount: {tx.amount}")
            print(f"Reason: {tx.reason}")
            print(f"Timestamp: {tx.timestamp}")
            print(f"Balance After: {tx.balance_after}")
            print(f"Activity Type: {tx.activity_type}")
            print(f"Metadata: {tx.transaction_metadata}")
            print("-" * 30)
    else:
        print("No records in point_transaction table") 