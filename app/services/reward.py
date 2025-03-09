from datetime import datetime
from ..models.reward import Reward, UserReward
from ..models.user import User
from .. import db

class RewardService:
    """Service for handling reward-related operations"""

    @staticmethod
    def create_reward(name, points_required, description=None, metadata=None):
        """Create a new reward"""
        reward = Reward(
            name=name,
            points_required=points_required,
            description=description,
            reward_metadata=metadata or {}
        )
        
        try:
            db.session.add(reward)
            db.session.commit()
            return reward.to_dict()
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error creating reward: {str(e)}")

    @staticmethod
    def update_reward(reward_id, **kwargs):
        """Update reward details"""
        reward = Reward.query.get(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        try:
            for key, value in kwargs.items():
                if hasattr(reward, key):
                    setattr(reward, key, value)
            
            db.session.commit()
            return reward.to_dict()
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error updating reward: {str(e)}")

    @staticmethod
    def get_available_rewards(user_id=None):
        """Get all available rewards, optionally filtered by user's points"""
        if user_id:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            return [r.to_dict() for r in user.get_available_rewards()]
        
        rewards = Reward.query.filter_by(is_active=True).order_by(Reward.points_required.asc()).all()
        return [reward.to_dict() for reward in rewards]

    @staticmethod
    def award_reward(user_id, reward_id, metadata=None):
        """Award a reward to a user"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        reward = Reward.query.get(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        if not reward.is_active:
            raise ValueError("This reward is no longer active")

        if user.points < reward.points_required:
            raise ValueError("Insufficient points for this reward")

        try:
            # Create user reward record
            user_reward = UserReward(
                user_id=user_id,
                reward_id=reward_id,
                redemption_metadata=metadata or {}
            )
            db.session.add(user_reward)
            
            # Deduct points from user
            user.add_points(
                -reward.points_required,
                f"Redeemed reward: {reward.name}"
            )
            
            db.session.commit()
            return user_reward.to_dict()
        except Exception as e:
            db.session.rollback()
            raise ValueError(f"Error awarding reward: {str(e)}")

    @staticmethod
    def get_user_rewards(user_id):
        """Get all rewards earned by a user"""
        user_rewards = UserReward.get_user_rewards(user_id)
        return [reward.to_dict() for reward in user_rewards]

    @staticmethod
    def initialize_reward_system():
        """Initialize or update reward system"""
        try:
            Reward.initialize_defaults()
            return True
        except Exception as e:
            print(f"Error initializing reward system: {str(e)}")
            return False

    @staticmethod
    def get_reward_statistics():
        """Get overall reward statistics"""
        total_rewards = Reward.query.count()
        active_rewards = Reward.query.filter_by(is_active=True).count()
        
        # Get most awarded rewards
        top_rewards = db.session.query(
            Reward.id,
            Reward.name,
            db.func.count(UserReward.id).label('award_count')
        ).join(UserReward).group_by(Reward.id, Reward.name)\
         .order_by(db.func.count(UserReward.id).desc())\
         .limit(5).all()
        
        return {
            'total_rewards': total_rewards,
            'active_rewards': active_rewards,
            'top_rewards': [
                {
                    'reward_id': reward_id,
                    'name': name,
                    'times_awarded': count
                }
                for reward_id, name, count in top_rewards
            ]
        }

    @staticmethod
    def get_all_rewards():
        """Get all rewards for admin view"""
        try:
            rewards = Reward.query.order_by(Reward.points_required.asc()).all()
            return [{
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'points_required': reward.points_required,
                'is_active': reward.is_active,
                'stock': reward.reward_metadata.get('stock') if reward.reward_metadata else None,
                'color': reward.reward_metadata.get('color', 'primary') if reward.reward_metadata else 'primary'
            } for reward in rewards]
        except Exception as e:
            raise ValueError(f"Error getting all rewards: {str(e)}")

    @staticmethod
    def get_recent_redemptions(limit=10):
        """Get recent reward redemptions with detailed information"""
        try:
            redemptions = UserReward.query.join(
                User, UserReward.user_id == User.id
            ).join(
                Reward, UserReward.reward_id == Reward.id
            ).order_by(
                UserReward.earned_at.desc()
            ).limit(limit).all()

            return [{
                'user_name': redemption.user.username,
                'user_initials': ''.join(word[0].upper() for word in redemption.user.username.split() if word),
                'reward_name': redemption.reward.name,
                'points_used': redemption.reward.points_required,
                'date': redemption.earned_at.strftime('%Y-%m-%d %H:%M'),
                'status': redemption.redemption_metadata.get('status', 'Pending') if redemption.redemption_metadata else 'Pending',
                'status_color': {
                    'Pending': 'warning',
                    'Fulfilled': 'success',
                    'Cancelled': 'danger'
                }.get(redemption.redemption_metadata.get('status', 'Pending') if redemption.redemption_metadata else 'Pending', 'warning')
            } for redemption in redemptions]
        except Exception as e:
            raise ValueError(f"Error getting recent redemptions: {str(e)}")

    @staticmethod
    def get_next_reward(user_id):
        """Get next available reward for user"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
                
            # Get next reward above user's points
            next_reward = Reward.query.filter(
                Reward.points_required > user.points,
                Reward.is_active == True
            ).order_by(Reward.points_required.asc()).first()
            
            if not next_reward:
                return None
                
            # Calculate progress
            points_needed = next_reward.points_required - user.points
            progress = (user.points / next_reward.points_required) * 100
            
            # Estimate time to achieve based on point history
            history = user.get_points_history()
            if history:
                recent_points = sum(
                    t['amount'] for t in history[-7:]  # Last 7 transactions
                )
                points_per_day = recent_points / 7
                days_to_achieve = points_needed / points_per_day if points_per_day > 0 else None
            else:
                days_to_achieve = None
                
            return {
                'reward': next_reward.to_dict(),
                'points_needed': points_needed,
                'progress_percentage': round(progress, 2),
                'estimated_days': round(days_to_achieve, 1) if days_to_achieve else None
            }
        except Exception as e:
            raise ValueError(f"Error getting next reward: {str(e)}")

    @staticmethod
    def get_next_rewards(user_id, limit=3):
        """Get the next rewards that the user can achieve"""
        try:
            # Get user's current points
            user = User.query.get(user_id)
            if not user:
                return []
            
            # Get rewards with higher point requirements than user's current points
            rewards = Reward.query.filter(
                Reward.points_required > user.points
            ).order_by(
                Reward.points_required.asc()
            ).limit(limit).all()
            
            # If we don't have enough rewards, add some available rewards
            if len(rewards) < limit:
                available_rewards = Reward.query.filter(
                    Reward.points_required <= user.points
                ).order_by(
                    Reward.points_required.desc()
                ).limit(limit - len(rewards)).all()
                rewards.extend(available_rewards)
            
            return [{
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'points_required': reward.points_required,
                'is_available': reward.points_required <= user.points
            } for reward in rewards]
        except Exception as e:
            print(f"Error getting next rewards: {str(e)}")
            return []
