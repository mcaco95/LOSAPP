from datetime import datetime, timedelta
from ..models.point_config import PointConfig
from ..models.user import User
from ..models.point_transaction import PointTransaction
from .. import db

class PointService:
    """Service for handling point-related operations"""

    @staticmethod
    def award_points_for_click(user_id, is_unique=False, click_id=None):
        """Award points for a click action"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get point value from configuration
        points = PointConfig.get_value('unique_click' if is_unique else 'click')
        
        if points > 0:
            reason = f"{'Unique ' if is_unique else ''}Click reward"
            
            # Create transaction with click details
            transaction = PointTransaction.create_transaction(
                user=user,
                amount=points,
                reason=reason,
                activity_type='click',
                reference_id=click_id,
                metadata={
                    'is_unique': is_unique,
                    'click_id': click_id
                }
            )
            
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
            # Create user-friendly message
            if new_status == 'lead':
                message = f"{company.name} has completed a lead form!"
            elif new_status == 'demo_scheduled':
                message = f"{company.name} has booked a demo!"
            elif new_status == 'demo_completed':
                message = f"{company.name} has completed their demo!"
            elif new_status == 'client_signed':
                message = f"{company.name} has signed up as a client!"
            elif new_status == 'renewed':
                message = f"{company.name} has renewed their service!"
            elif new_status == 'upgraded':
                message = f"{company.name} has upgraded their service!"
            else:
                message = f"{company.name} status changed to {new_status}"

            # Calculate any bonus points
            bonus_points = PointService.calculate_bonus_points(company, new_status)
            total_points = points + bonus_points

            # Create transaction for status change
            transaction = PointTransaction.create_transaction(
                user=company.user,
                amount=points,
                reason=message,
                activity_type='status_change',
                reference_id=company_id,
                metadata={
                    'company_id': company_id,
                    'company_name': company.name,
                    'old_status': company.status,
                    'new_status': new_status,
                    'base_points': points,
                    'bonus_points': bonus_points
                }
            )

            # If there are bonus points, create a separate transaction
            if bonus_points > 0:
                bonus_message = f"Bonus points for {company.name} status change to {new_status}"
                bonus_transaction = PointTransaction.create_transaction(
                    user=company.user,
                    amount=bonus_points,
                    reason=bonus_message,
                    activity_type='status_bonus',
                    reference_id=company_id,
                    metadata={
                        'company_id': company_id,
                        'company_name': company.name,
                        'status': new_status,
                        'bonus_type': 'status_change'
                    }
                )

            return total_points
        return 0

    @staticmethod
    def calculate_bonus_points(company, new_status):
        """Calculate bonus points based on various criteria"""
        total_bonus = 0
        
        # Fast-Track Bonus - Double points if client signs up within 30 days of demo
        if new_status == 'client_signed':
            # Check if there's a demo_completed status in history
            status_history = company.company_metadata.get('status_history', [])
            demo_completed_entry = next((entry for entry in status_history if entry.get('to') == 'demo_completed'), None)
            
            if demo_completed_entry:
                demo_date = datetime.fromisoformat(demo_completed_entry.get('timestamp'))
                days_since_demo = (datetime.utcnow() - demo_date).days
                
                if days_since_demo <= 30:
                    # Get the base points for client_signed
                    base_points = PointConfig.get_status_points('client_signed')
                    # Get the multiplier from config (default to 2x if not set)
                    multiplier = PointConfig.get_value('bonus_fast_track', 1)
                    fast_track_bonus = base_points * multiplier
                    total_bonus += fast_track_bonus
        
        # High-Value Client Bonus - Extra points for Professional Plan
        if new_status == 'client_signed' and company.service_type == 'professional':
            high_value_bonus = PointConfig.get_value('bonus_high_value', 30)
            total_bonus += high_value_bonus
        
        # Consistent Closer Bonus - Extra points for 3+ clients in a quarter
        if new_status == 'client_signed':
            # Get the user
            user = company.user
            
            # Calculate the start of the current quarter
            now = datetime.utcnow()
            current_quarter_start = datetime(now.year, ((now.month - 1) // 3) * 3 + 1, 1)
            
            # Count client signups in this quarter
            from ..models.company import Company
            quarter_signups = Company.query.filter(
                Company.user_id == user.id,
                Company.status == 'client_signed',
                Company.updated_at >= current_quarter_start
            ).count()
            
            # If this is the 3rd or more signup this quarter, award bonus
            if quarter_signups >= 3:
                consistent_closer_bonus = PointConfig.get_value('bonus_consistent_closer', 50)
                total_bonus += consistent_closer_bonus
        
        return total_bonus

    @staticmethod
    def get_user_points_summary(user_id):
        """Get summary of user's points and recent activity"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get recent transactions
        recent_transactions = PointTransaction.get_user_transactions(user_id, limit=5)
        
        # Group points by activity type
        points_by_type = {}
        for transaction in PointTransaction.get_user_transactions(user_id):
            activity_type = transaction.activity_type
            if activity_type not in points_by_type:
                points_by_type[activity_type] = 0
            points_by_type[activity_type] += transaction.amount

        return {
            'total_points': user.points,
            'points_by_type': points_by_type,
            'recent_activity': [t.to_dict() for t in recent_transactions]
        }

    @staticmethod
    def initialize_point_system():
        """Initialize the points system with default values"""
        try:
            PointConfig.initialize_defaults()
            return True
        except Exception as e:
            print(f"Error initializing point system: {str(e)}")
            return False

    @staticmethod
    def update_point_value(key, value, metadata=None):
        """Update point value for a specific action"""
        try:
            config = PointConfig.query.filter_by(key=key).first()
            if config:
                config.value = value
                if metadata:
                    if not config.config_metadata:
                        config.config_metadata = {}
                    config.config_metadata.update(metadata)
            else:
                config = PointConfig(key=key, value=value, metadata=metadata)
                db.session.add(config)
            
            db.session.commit()
            return config.to_dict()
        except Exception as e:
            db.session.rollback()
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
    def get_recent_activity(limit=None):
        """Get recent point transactions across all users"""
        query = PointTransaction.query.order_by(PointTransaction.timestamp.desc())
        if limit:
            query = query.limit(limit)
        
        transactions = query.all()
        activities = []
        
        for transaction in transactions:
            activity = {
                'user': {
                    'id': transaction.user_id,
                    'name': transaction.user.name or transaction.user.email,
                    'profile_picture': transaction.user.profile_picture
                },
                'points': transaction.amount,
                'timestamp': transaction.timestamp,
                'message': transaction.reason
            }
            activities.append(activity)
            
        return activities

    @staticmethod
    def get_points_distribution(period='all'):
        """Get points distribution data for charts"""
        try:
            # Get all point configurations
            configs = PointConfig.get_all_configs()
            
            # Get action names for better labels
            action_names = {}
            for key in configs.keys():
                config = PointConfig.query.filter_by(key=key).first()
                if config:
                    # Try to get a friendly name from metadata
                    metadata = config.config_metadata or {}
                    action_names[key] = metadata.get('name', key.replace('_', ' ').title())
            
            # Format data for chart
            labels = []
            series = []
            
            # If period is not 'all', filter data by period
            if period != 'all':
                # Get points awarded in the specified period
                now = datetime.utcnow()
                
                if period == 'week':
                    start_date = now - timedelta(days=7)
                elif period == 'month':
                    start_date = now - timedelta(days=30)
                elif period == 'year':
                    start_date = now - timedelta(days=365)
                else:
                    # Default to all time
                    start_date = None
                
                # Get points awarded by action type in the period
                if start_date:
                    # This would require a more complex query to get points by action type
                    # For now, we'll use a simplified approach with mock data
                    # In a real implementation, you would query the database for actual point transactions
                    
                    # Mock data for demonstration - ensure we have data for each period
                    period_data = {
                        'status_lead': 25,
                        'status_demo_scheduled': 15,
                        'status_demo_completed': 30,
                        'status_client_signed': 20,
                        'status_renewed': 5,
                        'status_upgraded': 3,
                        'status_partner_signup': 2,
                        'unique_click': 40,
                        'bonus_high_value': 10,
                        'bonus_consistent_closer': 8
                    }
                    
                    # Adjust mock data based on period for demonstration
                    multiplier = 1
                    if period == 'week':
                        multiplier = 0.2
                    elif period == 'month':
                        multiplier = 1
                    elif period == 'year':
                        multiplier = 12
                    
                    for key, value in period_data.items():
                        if key in configs:
                            # Use friendly name if available
                            label = action_names.get(key, key.replace('_', ' ').title())
                            
                            # Truncate long labels
                            if len(label) > 15:
                                label = label[:12] + '...'
                                
                            labels.append(label)
                            series.append(int(value * multiplier))
                    
                    return {
                        'labels': labels,
                        'series': series
                    }
            
            # Default behavior for 'all' period - show point values from config
            for key, points in configs.items():
                # Skip zero-value configs
                if points <= 0:
                    continue
                    
                # Use friendly name if available
                label = action_names.get(key, key.replace('_', ' ').title())
                
                # Truncate long labels
                if len(label) > 15:
                    label = label[:12] + '...'
                    
                labels.append(label)
                series.append(points)
            
            return {
                'labels': labels,
                'series': series
            }
        except Exception as e:
            print(f"Error getting points distribution: {str(e)}")
            # Return some default data instead of empty arrays
            return {
                'labels': ['Lead Gen', 'Demo Sched', 'Demo Comp', 'Client Sign', 'Renewed'],
                'series': [2, 5, 15, 50, 25]
            }

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
                'status_lead': {
                    'name': 'Lead Generation',
                    'description': 'Referral form completed'
                },
                'status_demo_scheduled': {
                    'name': 'Engagement',
                    'description': 'Demo scheduled'
                },
                'status_demo_completed': {
                    'name': 'Completed',
                    'description': 'Demo completed'
                },
                'status_client_signed': {
                    'name': 'Conversion',
                    'description': 'Client signed up'
                },
                'status_renewed': {
                    'name': 'Retention',
                    'description': 'Client renewed'
                },
                'status_upgraded': {
                    'name': 'Upsell',
                    'description': 'Referral client upgrades plan'
                },
                'status_partner_signup': {
                    'name': 'Partner Network',
                    'description': 'Referral partners have a client sign up'
                },
                'bonus_fast_track': {
                    'name': 'Fast-Track Bonus Multiplier',
                    'description': 'Multiplier for client signing within 30 days of demo (0 = disabled)'
                },
                'bonus_high_value': {
                    'name': 'High-Value Client Bonus',
                    'description': 'Extra points for Professional Plan clients'
                },
                'bonus_consistent_closer': {
                    'name': 'Consistent Closer Bonus',
                    'description': 'Extra points for 3+ clients in a quarter'
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
                    'key': key,
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

    @staticmethod
    def delete_point_config(config_id):
        """Delete a point configuration"""
        try:
            config = PointConfig.query.get(config_id)
            if not config:
                return False
                
            db.session.delete(config)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting point config: {str(e)}")
            return False
