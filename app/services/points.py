from datetime import datetime, timedelta
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
        
        # Calculate monthly change
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        current_month_points = sum(
            entry['amount'] for entry in history 
            if datetime.fromisoformat(entry['timestamp']) >= start_of_month
        )
        
        # If there are points this month, calculate percentage change
        monthly_change = 0
        if user.points > 0:
            monthly_change = (current_month_points / user.points) * 100
        
        # Calculate points by category
        summary = {
            'total_points': user.points,
            'points_by_category': {},
            'recent_activity': history[-5:] if history else [],  # Last 5 activities
            'available_rewards': [r.to_dict() for r in user.get_available_rewards()],
            'monthly_change': round(monthly_change, 1)
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

    @staticmethod
    def get_user_rank(user_id):
        """Get user's rank and percentile"""
        try:
            # Query all users ordered by points
            ranked_users = User.query.order_by(User.points.desc()).all()
            total_users = len(ranked_users)
            
            # Find user's position
            user_position = next(
                (i for i, u in enumerate(ranked_users) if u.id == user_id),
                None
            )
            
            if user_position is None:
                raise ValueError(f"User {user_id} not found")
                
            # Calculate percentile and next rank
            percentile = ((total_users - user_position) / total_users) * 100
            next_rank_user = ranked_users[user_position - 1] if user_position > 0 else None
            
            return {
                'rank': user_position + 1,
                'total_users': total_users,
                'percentile': round(percentile, 2),
                'points_to_next_rank': (
                    next_rank_user.points - ranked_users[user_position].points
                    if next_rank_user else 0
                )
            }
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error calculating rank: {str(e)}")

    @staticmethod
    def get_points_history(user_id, period='week'):
        """Get points history grouped by period"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
                
            history = user.get_points_history()
            
            # Group transactions by period
            grouped_history = {}
            for entry in history:
                timestamp = datetime.fromisoformat(entry['timestamp'])
                if period == 'day':
                    key = timestamp.date().isoformat()
                elif period == 'week':
                    key = timestamp.strftime('%Y-W%W')
                else:  # month
                    key = timestamp.strftime('%Y-%m')
                    
                if key not in grouped_history:
                    grouped_history[key] = 0
                grouped_history[key] += entry['amount']
                
            return {
                'period': period,
                'data': grouped_history,
                'total_points': user.points
            }
        except Exception as e:
            raise ValueError(f"Error getting points history: {str(e)}")

    @staticmethod
    def get_top_users(limit=10):
        """Get top users by points"""
        try:
            top_users = User.query.order_by(User.points.desc()).limit(limit).all()
            return [{
                'id': user.id,
                'username': user.username,
                'points': user.points,
                'rank': idx + 1,
                'stats': user.get_stats(),
                'profile_picture': user.profile_picture
            } for idx, user in enumerate(top_users)]
        except Exception as e:
            raise ValueError(f"Error getting top users: {str(e)}")

    @staticmethod
    def get_total_users():
        """Get total number of users in the system"""
        return User.query.count()

    @staticmethod
    def get_system_metrics():
        """Get system-wide metrics including growth rates"""
        try:
            # Get all users and calculate totals
            users = User.query.all()
            total_users = len(users)
            total_points = sum(user.points for user in users)
            
            # Calculate growth rates
            now = datetime.utcnow()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_of_last_month = (start_of_month.replace(day=1) - timedelta(days=1)).replace(day=1)
            
            # Points growth
            current_month_points = 0
            last_month_points = 0
            
            for user in users:
                history = user.get_points_history()
                for entry in history:
                    entry_date = datetime.fromisoformat(entry['timestamp'])
                    if entry_date >= start_of_month:
                        current_month_points += entry['amount']
                    elif start_of_last_month <= entry_date < start_of_month:
                        last_month_points += entry['amount']
            
            points_growth = (
                ((current_month_points - last_month_points) / last_month_points * 100)
                if last_month_points > 0 else 0
            )
            
            # User growth (simplified - just compare current vs last month)
            last_month_users = User.query.filter(
                User.created_at < start_of_month
            ).count()
            
            user_growth = (
                ((total_users - last_month_users) / last_month_users * 100)
                if last_month_users > 0 else 0
            )
            
            return {
                'total_users': total_users,
                'total_points': total_points,
                'user_growth': round(user_growth, 1),
                'points_growth': round(points_growth, 1)
            }
        except Exception as e:
            raise ValueError(f"Error getting system metrics: {str(e)}")

    @staticmethod
    def get_recent_activity(limit=10):
        """Get recent points transactions across all users"""
        try:
            recent = []
            users = User.query.all()
            
            for user in users:
                history = user.get_points_history()
                if history:
                    for entry in history[-limit:]:
                        entry['user'] = user.username
                        recent.append(entry)
            
            # Sort by timestamp and get the most recent entries
            return sorted(
                recent,
                key=lambda x: datetime.fromisoformat(x['timestamp']),
                reverse=True
            )[:limit]
        except Exception as e:
            raise ValueError(f"Error getting recent activity: {str(e)}")

    @staticmethod
    def get_points_distribution():
        """Get points distribution data for visualization"""
        try:
            users = User.query.all()
            distribution = {}
            
            # Create point ranges (0-100, 101-500, 501-1000, 1001-5000, 5000+)
            ranges = [
                (0, 100, '0-100'),
                (101, 500, '101-500'),
                (501, 1000, '501-1000'),
                (1001, 5000, '1001-5000'),
                (5001, float('inf'), '5000+')
            ]
            
            # Initialize ranges
            for _, _, label in ranges:
                distribution[label] = 0
                
            # Count users in each range
            for user in users:
                for start, end, label in ranges:
                    if start <= user.points <= end:
                        distribution[label] += 1
                        break
            
            return {
                'labels': list(distribution.keys()),
                'data': list(distribution.values())
            }
        except Exception as e:
            raise ValueError(f"Error getting points distribution: {str(e)}")

    @staticmethod
    def get_point_rules():
        """Get all point rules with their configurations"""
        try:
            configs = PointConfig.get_all_configs()
            rules = []

            # Define friendly names and descriptions for default actions
            action_info = {
                'click': {
                    'name': 'Regular Click',
                    'description': 'Points awarded for referral link clicks'
                },
                'unique_click': {
                    'name': 'Unique Click',
                    'description': 'Points awarded for first-time visitor clicks'
                },
                'status_completed_form': {
                    'name': 'Form Completion',
                    'description': 'Points awarded when a company completes the form'
                },
                'status_meeting_scheduled': {
                    'name': 'Meeting Scheduled',
                    'description': 'Points awarded when a meeting is scheduled'
                },
                'status_sold': {
                    'name': 'Deal Closed',
                    'description': 'Points awarded when a deal is closed'
                },
                'status_paid': {
                    'name': 'Commission Paid',
                    'description': 'Points awarded when commission is paid'
                }
            }

            for key, points in configs.items():
                # Get config object to access metadata
                config = PointConfig.query.filter_by(key=key).first()
                if not config:
                    continue

                # Get action info or generate defaults
                info = action_info.get(key, {
                    'name': key.replace('_', ' ').title(),
                    'description': f'Points awarded for {key.replace("_", " ")}'
                })

                # Extract frequency limits from metadata if they exist
                metadata = config.config_metadata or {}
                frequency_limit = metadata.get('frequency_limit')
                frequency_period = metadata.get('frequency_period')

                rule = {
                    'id': config.id,
                    'action_name': info['name'],
                    'description': info['description'],
                    'points': points,
                    'frequency_limit': frequency_limit,
                    'frequency_period': frequency_period,
                    'is_active': metadata.get('is_active', True)
                }
                rules.append(rule)

            return rules
        except Exception as e:
            raise ValueError(f"Error getting point rules: {str(e)}")
