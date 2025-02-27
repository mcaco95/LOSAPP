from datetime import datetime, timedelta
from app import db, create_app
from app.models.user import User
from app.models.company import Company
from app.models.commission_partner import CommissionPartner
from app.models.commission import Commission
from app.models.point_config import PointConfig
from app.models.link_tracking import LinkClick
from app.models.reward import Reward

def cleanup_test_data():
    """Safely remove test data while preserving real data"""
    app = create_app()
    with app.app_context():
        print("Starting cleanup of test data...")
        
        # Store counts before cleanup
        before_counts = {
            'users': User.query.count(),
            'companies': Company.query.count(),
            'partners': CommissionPartner.query.count(),
            'commissions': Commission.query.count(),
            'link_clicks': LinkClick.query.count()
        }
        
        # Remove test users (and their related data due to cascade)
        # We identify test users by their password being 'test123'
        test_users = User.query.filter_by(password='test123').all()
        test_user_ids = [user.id for user in test_users]
        
        # Remove related data first
        if test_user_ids:
            # Remove commissions for test partners
            test_partners = CommissionPartner.query.filter(
                CommissionPartner.user_id.in_(test_user_ids)
            ).all()
            test_partner_ids = [p.id for p in test_partners]
            
            if test_partner_ids:
                Commission.query.filter(
                    Commission.partner_id.in_(test_partner_ids)
                ).delete(synchronize_session=False)
                
                LinkClick.query.filter(
                    LinkClick.partner_id.in_(test_partner_ids)
                ).delete(synchronize_session=False)
                
                # Remove test partners
                CommissionPartner.query.filter(
                    CommissionPartner.id.in_(test_partner_ids)
                ).delete(synchronize_session=False)
        
            # Remove test users
            User.query.filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
        
        # Commit the changes
        db.session.commit()
        
        # Get counts after cleanup
        after_counts = {
            'users': User.query.count(),
            'companies': Company.query.count(),
            'partners': CommissionPartner.query.count(),
            'commissions': Commission.query.count(),
            'link_clicks': LinkClick.query.count()
        }
        
        # Print cleanup report
        print("\nCleanup Report:")
        print("--------------")
        for key in before_counts:
            removed = before_counts[key] - after_counts[key]
            print(f"{key.title()}:")
            print(f"  Before: {before_counts[key]}")
            print(f"  After:  {after_counts[key]}")
            print(f"  Removed: {removed}")
            print()
        
        print("Cleanup complete!")

if __name__ == '__main__':
    cleanup_test_data() 