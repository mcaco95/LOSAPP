from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Reward(db.Model):
    """Model for configurable rewards that users can earn with points"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    points_required = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reward_metadata = db.Column(JSONB)

    def __init__(self, name, points_required, description=None, metadata=None):
        self.name = name
        self.points_required = points_required
        self.description = description
        self.reward_metadata = metadata or {}

    @classmethod
    def get_available_rewards(cls, user_points):
        """Get rewards available for the given point amount"""
        return cls.query.filter(
            cls.points_required <= user_points,
            cls.is_active == True
        ).order_by(cls.points_required.asc()).all()

    @classmethod
    def initialize_defaults(cls):
        """Initialize default rewards"""
        defaults = [
            {
                'name': 'Bronze Badge',
                'description': 'Digital badge for reaching bronze tier',
                'points_required': 100
            },
            {
                'name': 'Silver Badge',
                'description': 'Digital badge for reaching silver tier',
                'points_required': 500
            },
            {
                'name': 'Gold Badge',
                'description': 'Digital badge for reaching gold tier',
                'points_required': 1000
            }
        ]
        
        for reward_data in defaults:
            if not cls.query.filter_by(name=reward_data['name']).first():
                reward = cls(**reward_data)
                db.session.add(reward)
        
        db.session.commit()

    def to_dict(self):
        """Convert reward to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'points_required': self.points_required,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.reward_metadata
        }

class UserReward(db.Model):
    """Model for tracking rewards earned by users"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reward_id = db.Column(db.Integer, db.ForeignKey('reward.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    redemption_metadata = db.Column(JSONB)

    # Relationships
    user = db.relationship('User', backref=db.backref('rewards_earned', lazy='dynamic'))
    reward = db.relationship('Reward')

    def __init__(self, user_id, reward_id, metadata=None):
        self.user_id = user_id
        self.reward_id = reward_id
        self.redemption_metadata = metadata or {}

    @classmethod
    def get_user_rewards(cls, user_id):
        """Get all rewards earned by a user"""
        return cls.query.filter_by(user_id=user_id).order_by(cls.earned_at.desc()).all()

    def to_dict(self):
        """Convert user reward to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'reward_id': self.reward_id,
            'reward': self.reward.to_dict() if self.reward else None,
            'earned_at': self.earned_at.isoformat() if self.earned_at else None,
            'metadata': self.redemption_metadata
        }
