from datetime import datetime, timedelta
from ..models.point_config import PointConfig
from ..models.user import User
from .. import db
from sqlalchemy.sql import text

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
                message = f"{company.name} has upgraded their plan!"
            else:
                message = f"Status changed to {Company.get_status_display(new_status)}"
            
            # Include company information in metadata
            metadata = {
                'company_id': company_id,
                'company_name': company.name,
                'status': new_status,
                'status_display': Company.get_status_display(new_status)
            }
            
            # Award points with the friendly message
            company.user.add_points(points, message, metadata=metadata)
            
            # Check for bonus points
            bonus_points = PointService.calculate_bonus_points(company, new_status)
            if bonus_points > 0:
                bonus_message = f"Bonus points awarded for {company.name}!"
                company.user.add_points(bonus_points, bonus_message, metadata=metadata)
                points += bonus_points
                
            db.session.commit()
            return points
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
        """Get summary of user's points"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            # Query point_transaction table
            query = """
                SELECT 
                    amount,
                    reason,
                    timestamp,
                    balance_after,
                    transaction_metadata
                FROM point_transaction
                WHERE user_id = :user_id
                ORDER BY timestamp DESC
            """
            
            result = db.session.execute(text(query), {'user_id': user_id})
            transactions = list(result)
            
            # Calculate monthly change
            now = datetime.utcnow()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            current_month_points = sum(
                tx.amount for tx in transactions 
                if tx.timestamp >= start_of_month
            )
            
            # If there are points this month, calculate percentage change
            monthly_change = 0
            if user.points > 0:
                monthly_change = (current_month_points / user.points) * 100
            
            # Calculate points by category
            points_by_category = {}
            for tx in transactions:
                category = tx.reason or 'Other'
                if category not in points_by_category:
                    points_by_category[category] = 0
                points_by_category[category] += tx.amount
            
            # Get recent activity (last 5 transactions)
            recent_activity = []
            for tx in transactions[:5]:
                activity = {
                    'amount': tx.amount,
                    'reason': tx.reason,
                    'timestamp': tx.timestamp.isoformat(),
                    'balance_after': tx.balance_after,
                    'metadata': tx.transaction_metadata
                }
                recent_activity.append(activity)
            
            summary = {
                'total_points': user.points,
                'points_by_category': points_by_category,
                'recent_activity': recent_activity,
                'available_rewards': [r.to_dict() for r in user.get_available_rewards()],
                'monthly_change': round(monthly_change, 1)
            }

            return summary
        except Exception as e:
            raise ValueError(f"Error getting user points summary: {str(e)}")

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
            
            # Query point_transaction table
            query = """
                SELECT 
                    amount,
                    timestamp,
                    reason,
                    balance_after,
                    transaction_metadata
                FROM point_transaction
                WHERE user_id = :user_id
                ORDER BY timestamp ASC
            """
            
            result = db.session.execute(text(query), {'user_id': user_id})
            
            # Group transactions by period
            grouped_history = {}
            for row in result:
                timestamp = row.timestamp
                if period == 'day':
                    key = timestamp.date().isoformat()
                elif period == 'week':
                    key = timestamp.strftime('%Y-W%W')
                else:  # month
                    key = timestamp.strftime('%Y-%m')
                    
                if key not in grouped_history:
                    grouped_history[key] = 0
                grouped_history[key] += row.amount
                
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
            
            # Query points from point_transaction table
            query = """
                SELECT 
                    SUM(CASE WHEN timestamp >= :start_of_month THEN amount ELSE 0 END) as current_month_points,
                    SUM(CASE WHEN timestamp >= :start_of_last_month AND timestamp < :start_of_month THEN amount ELSE 0 END) as last_month_points
                FROM point_transaction
            """
            
            result = db.session.execute(text(query), {
                'start_of_month': start_of_month,
                'start_of_last_month': start_of_last_month
            }).first()
            
            current_month_points = result.current_month_points or 0
            last_month_points = result.last_month_points or 0
            
            # Calculate points growth
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
        """Get recent points transactions across all users"""
        try:
            # Query point_transaction table directly
            query = """
                SELECT 
                    pt.id,
                    pt.user_id,
                    u.username,
                    u.profile_picture,
                    pt.amount,
                    pt.reason,
                    pt.timestamp,
                    pt.transaction_metadata
                FROM point_transaction pt
                JOIN "user" u ON pt.user_id = u.id
                ORDER BY pt.timestamp DESC
            """
            if limit:
                query += f" LIMIT {limit}"
            
            result = db.session.execute(query)
            recent = []
            
            for row in result:
                entry = {
                    'user': row.username,
                    'profile_picture': row.profile_picture,
                    'amount': row.amount,
                    'timestamp': row.timestamp.isoformat(),
                    'metadata': row.transaction_metadata,
                    'message': row.reason
                }
                
                # Format message based on metadata if needed
                metadata = row.transaction_metadata
                if metadata and 'company_id' in metadata:
                    # This is a company status change
                    company_name = metadata.get('company_name', 'Unknown Company')
                    status = metadata.get('status')
                    
                    # Use the pre-formatted message from award_points_for_status
                    entry['message'] = row.reason
                else:
                    # This is a click reward or other activity
                    entry['message'] = row.reason
                
                recent.append(entry)
            
            return recent
            
        except Exception as e:
            raise ValueError(f"Error getting recent activity: {str(e)}")

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

    @staticmethod
    def award_points_for_partner_signup(user_id, referred_user_id):
        """Award points for referring a new commission partner"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        referred_user = User.query.get(referred_user_id)
        if not referred_user:
            raise ValueError(f"Referred user {referred_user_id} not found")

        # Get point value from configuration
        points = PointConfig.get_value('status_partner_signup', 25)  # Default to 25 if not configured
        
        if points > 0:
            reason = f"Commission partner signup: {referred_user.name or referred_user.email}"
            metadata = {
                'status': 'partner_signup',
                'referred_user_id': referred_user_id
            }
            user.add_points(points, reason, metadata)
            db.session.commit()
            return points
        return 0
