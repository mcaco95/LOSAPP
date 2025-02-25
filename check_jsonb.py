from app import create_app, db
from app.models.user import User

app = create_app()
with app.app_context():
    users = User.query.all()
    
    print("\nChecking points_history JSONB data for all users:")
    print("-" * 50)
    
    for user in users:
        print(f"\nUser: {user.name or user.email}")
        print(f"Total Points: {user.points}")
        if user.points_history and 'transactions' in user.points_history:
            print("\nTransactions:")
            for tx in user.points_history['transactions']:
                print("\n  Amount:", tx.get('amount'))
                print("  Reason:", tx.get('reason'))
                print("  Timestamp:", tx.get('timestamp'))
                print("  Balance After:", tx.get('balance_after'))
                if 'metadata' in tx:
                    print("  Metadata:", tx['metadata'])
                print("  " + "-" * 30)
        else:
            print("No points history found") 