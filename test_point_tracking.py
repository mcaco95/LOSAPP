from app import create_app, db
from sqlalchemy import text
from datetime import datetime
import json

app = create_app()
with app.app_context():
    # First, let's clear existing test data
    db.session.execute(text('DELETE FROM point_transaction WHERE user_id = 999'))
    
    # Test transactions to insert
    test_transactions = [
        # Click reward
        {
            'user_id': 999,
            'amount': 1,
            'reason': 'Click reward',
            'activity_type': 'click',
            'reference_id': 1,
            'balance_after': 1,
            'metadata': {
                'ip': '127.0.0.1',
                'is_unique': True
            }
        },
        # Unique click reward
        {
            'user_id': 999,
            'amount': 5,
            'reason': 'Unique click reward',
            'activity_type': 'unique_click',
            'reference_id': 2,
            'balance_after': 6,
            'metadata': {
                'ip': '127.0.0.2',
                'visitor_id': 'abc123'
            }
        },
        # Lead status change
        {
            'user_id': 999,
            'amount': 2,
            'reason': 'Test Company has become a lead!',
            'activity_type': 'status_change',
            'reference_id': 3,
            'balance_after': 8,
            'metadata': {
                'company_id': '1',
                'company_name': 'Test Company',
                'old_status': None,
                'new_status': 'lead',
                'base_points': 2,
                'bonus_points': 0
            }
        },
        # Demo scheduled
        {
            'user_id': 999,
            'amount': 5,
            'reason': 'Test Company has scheduled a demo!',
            'activity_type': 'status_change',
            'reference_id': 4,
            'balance_after': 13,
            'metadata': {
                'company_id': '1',
                'company_name': 'Test Company',
                'old_status': 'lead',
                'new_status': 'demo_scheduled',
                'base_points': 5,
                'bonus_points': 0
            }
        }
    ]
    
    # Insert test transactions
    for tx in test_transactions:
        insert_query = text("""
            INSERT INTO point_transaction 
            (user_id, amount, reason, timestamp, activity_type, reference_id, balance_after, transaction_metadata)
            VALUES 
            (:user_id, :amount, :reason, :timestamp, :activity_type, :reference_id, :balance_after, cast(:metadata as jsonb))
        """)
        
        db.session.execute(insert_query, {
            'user_id': tx['user_id'],
            'amount': tx['amount'],
            'reason': tx['reason'],
            'timestamp': datetime.utcnow(),
            'activity_type': tx['activity_type'],
            'reference_id': tx['reference_id'],
            'balance_after': tx['balance_after'],
            'metadata': json.dumps(tx['metadata'])
        })
    
    db.session.commit()
    
    # Verify the insertions
    print("\nVerifying point transactions:")
    print("-" * 50)
    
    verify_query = text('SELECT * FROM point_transaction WHERE user_id = 999 ORDER BY timestamp')
    results = db.session.execute(verify_query).fetchall()
    
    for row in results:
        print(f"\nTransaction ID: {row.id}")
        print(f"Activity Type: {row.activity_type}")
        print(f"Amount: {row.amount}")
        print(f"Reason: {row.reason}")
        print(f"Balance After: {row.balance_after}")
        print(f"Metadata: {row.transaction_metadata}")
        print("-" * 30)
    
    # Clean up test data
    db.session.execute(text('DELETE FROM point_transaction WHERE user_id = 999'))
    db.session.commit() 