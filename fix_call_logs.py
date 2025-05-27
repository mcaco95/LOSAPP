#!/usr/bin/env python3
"""
Script to fix call logs that don't have operator_id assigned.
This will analyze recent calls and assign them to the appropriate operator.
"""

from app import create_app, db
from app.models.call_log import CallLog
from app.models.operations_user import OperationsUser
from datetime import datetime, timedelta

def fix_call_logs():
    app = create_app()
    with app.app_context():
        print("=== Fixing Call Logs ===")
        
        # Get all operations users
        ops_users = OperationsUser.query.all()
        print(f"Found {len(ops_users)} operations users:")
        for user in ops_users:
            print(f"  - {user.user.name} (ID: {user.id})")
        
        # Get calls without operator_id from the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        unassigned_calls = CallLog.query.filter(
            CallLog.operator_id.is_(None),
            CallLog.sales_rep_id.is_(None),
            CallLog.created_at >= week_ago
        ).order_by(CallLog.created_at.desc()).all()
        
        print(f"\nFound {len(unassigned_calls)} unassigned calls from the last 7 days:")
        
        # For now, assign all recent unassigned calls to the first operations user
        # In a real scenario, you might want to analyze call patterns or ask the user
        if ops_users and unassigned_calls:
            default_operator = ops_users[0]  # Assign to first operator (Sebastian Morales)
            print(f"\nAssigning all unassigned calls to: {default_operator.user.name} (ID: {default_operator.id})")
            
            updated_count = 0
            for call in unassigned_calls:
                print(f"  - Call {call.id} (SID: {call.call_sid}) to {call.to_number} on {call.created_at}")
                call.operator_id = default_operator.id
                updated_count += 1
            
            # Commit changes
            try:
                db.session.commit()
                print(f"\n✅ Successfully updated {updated_count} call logs!")
            except Exception as e:
                db.session.rollback()
                print(f"\n❌ Error updating call logs: {e}")
        else:
            print("No operations users or unassigned calls found.")
        
        # Show summary
        total_ops_calls = CallLog.query.filter(CallLog.operator_id.isnot(None)).count()
        print(f"\nSummary:")
        print(f"  - Total operations calls: {total_ops_calls}")
        print(f"  - Calls updated: {updated_count if 'updated_count' in locals() else 0}")

if __name__ == "__main__":
    fix_call_logs() 