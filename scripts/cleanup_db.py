import os
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import app
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

from app import create_app, db
from app.models.user import User
from app.models.company import Company
from app.models.link_tracking import LinkClick, GlobalRedirect
from app.models.point_config import PointConfig

def cleanup_database():
    """Clean up all activity data while preserving users"""
    app = create_app()
    with app.app_context():
        try:
            # Start transaction
            db.session.begin()

            # Delete all companies
            Company.query.delete()
            print("✓ Deleted all companies")

            # Delete all link clicks and redirects
            LinkClick.query.delete()
            GlobalRedirect.query.delete()
            print("✓ Deleted all link tracking data")

            # Reset user points and clear history
            users = User.query.all()
            for user in users:
                user.points = 0
                user.points_history = {'transactions': []}
            print("✓ Reset all user points and history")

            # Reset point configurations
            PointConfig.query.delete()
            print("✓ Deleted all point configurations")

            # Commit all changes
            db.session.commit()
            print("\nDatabase cleanup completed successfully!")
            print("\nRemaining users:")
            users = User.query.all()
            for user in users:
                print(f"- {user.email} (ID: {user.id})")

        except Exception as e:
            db.session.rollback()
            print(f"Error during cleanup: {str(e)}")
            raise

if __name__ == '__main__':
    cleanup_database() 