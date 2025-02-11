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
            metadata=metadata or {}
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
                metadata=metadata or {}
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
