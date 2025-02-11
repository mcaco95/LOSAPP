from datetime import datetime
from ..models.point_config import PointConfig
from ..models.user import User
from .. import db

class PointService:
    """Service for handling point-related operations"""

    @staticmethod
    def award_points_for_click(user_id, is_unique=False):
        """Award points for a click action"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get point value from configuration
        points = PointConfig.get_value('unique_click' if is_unique else 'click')
        
        if points > 0:
            reason = f"{'Unique ' if is_unique else ''}Click reward"
            user.add_points(points, reason)
            db.session.commit()
            return points
        return 0

    @staticmethod
    def award_points_for_status(company_id, new_status):
        """Award points for company status change"""
        from ..models.company import Company
        
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        # Get point value from configuration
        points = PointConfig.get_status_points(new_status)
        
        if points > 0:
            reason = f"Company status changed to {new_status}"
            company.user.add_points(points, reason)
            db.session.commit()
            return points
        return 0

    @staticmethod
    def get_user_points_summary(user_id):
        """Get summary of user's points"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        history = user.get_points_history()
        
        # Calculate points by category
        summary = {
            'total_points': user.points,
            'points_by_category': {},
            'recent_activity': history[-5:] if history else [],  # Last 5 activities
            'available_rewards': [r.to_dict() for r in user.get_available_rewards()]
        }

        # Group points by reason
        for entry in history:
            category = entry.get('reason', 'Other')
            if category not in summary['points_by_category']:
                summary['points_by_category'][category] = 0
            summary['points_by_category'][category] += entry['amount']

        return summary

    @staticmethod
    def initialize_point_system():
        """Initialize or update point system configurations"""
        try:
            PointConfig.initialize_defaults()
            return True
        except Exception as e:
            print(f"Error initializing point system: {str(e)}")
            return False

    @staticmethod
    def update_point_value(key, value):
        """Update point value for a specific action"""
        try:
            config = PointConfig.set_value(key, value)
            return config.to_dict()
        except Exception as e:
            print(f"Error updating point value: {str(e)}")
            return None

    @staticmethod
    def get_all_point_configs():
        """Get all point configurations"""
        return PointConfig.get_all_configs()
