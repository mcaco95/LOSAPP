from app import create_app, db
from app.models.user import User
from datetime import datetime
from sqlalchemy import text
import json

app = create_app()

def reconstruct_point_transactions():
    with app.app_context():
        # First, get all users
        users = User.query.all()
        total_transactions = 0
        
        print("Starting point transaction reconstruction...")
        
        for user in users:
            print(f"\nProcessing user: {user.email} (Points: {user.points})")
            
            # Case 1: User has transaction history in JSONB
            if user.points_history and 'transactions' in user.points_history and user.points_history['transactions']:
                print(f"Found existing transactions for {user.email}")
                for tx in user.points_history['transactions']:
                    # Convert timestamp string to datetime
                    try:
                        timestamp = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.utcnow()
                    
                    # Extract metadata if it exists
                    metadata = tx.get('metadata', {})
                    activity_type = metadata.get('status', 'other') if metadata else 'other'
                    reference_id = metadata.get('company_id') if metadata else None
                    
                    # Insert into point_transaction table
                    insert_query = text("""
                        INSERT INTO point_transaction 
                        (user_id, amount, reason, timestamp, activity_type, reference_id, balance_after, transaction_metadata)
                        VALUES 
                        (:user_id, :amount, :reason, :timestamp, :activity_type, :reference_id, :balance_after, cast(:metadata as jsonb))
                    """)
                    
                    try:
                        db.session.execute(insert_query, {
                            'user_id': user.id,
                            'amount': tx['amount'],
                            'reason': tx['reason'],
                            'timestamp': timestamp,
                            'activity_type': activity_type,
                            'reference_id': reference_id,
                            'balance_after': tx['balance_after'],
                            'metadata': json.dumps(metadata) if metadata else '{}'
                        })
                        total_transactions += 1
                    except Exception as e:
                        print(f"Error inserting transaction: {str(e)}")
                        continue
            
            # Case 2: User has points but no transaction history
            elif user.points > 0:
                print(f"Creating initial transaction for {user.email} with {user.points} points")
                insert_query = text("""
                    INSERT INTO point_transaction 
                    (user_id, amount, reason, timestamp, activity_type, reference_id, balance_after, transaction_metadata)
                    VALUES 
                    (:user_id, :amount, :reason, :timestamp, :activity_type, :reference_id, :balance_after, cast(:metadata as jsonb))
                """)
                
                try:
                    db.session.execute(insert_query, {
                        'user_id': user.id,
                        'amount': user.points,
                        'reason': 'Initial points balance',
                        'timestamp': datetime.utcnow(),
                        'activity_type': 'initial_balance',
                        'reference_id': None,
                        'balance_after': user.points,
                        'metadata': '{}'
                    })
                    total_transactions += 1
                except Exception as e:
                    print(f"Error creating initial transaction: {str(e)}")
            
            # Commit after each user
            try:
                db.session.commit()
            except Exception as e:
                print(f"Error committing transactions: {str(e)}")
                db.session.rollback()
        
        print(f"\nReconstruction complete! Total transactions restored: {total_transactions}")

if __name__ == '__main__':
    reconstruct_point_transactions() 