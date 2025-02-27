from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta
import secrets
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from .. import db, login_manager
import json
from sqlalchemy import text

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    unique_link = db.Column(db.String(100), unique=True, default=lambda: str(uuid.uuid4()))
    points = db.Column(db.Integer, default=0)
    points_history = db.Column(JSONB)  # Renamed from points_metadata to be more specific
    profile_picture = db.Column(db.String(255))  # Store path/url to profile picture

    # Relationships are added by backref in other models:
    # companies = relationship from Company model
    # rewards_earned = relationship from UserReward model
    # link_clicks = relationship from LinkClick model

    @property
    def username(self):
        return self.name or self.email.split('@')[0]

    def set_password(self, password):
        """Set password using sha256 method which is compatible with newer Python versions"""
        self.password_hash = generate_password_hash(password, method='sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()
        return self.reset_token
    
    def verify_reset_token(self, token):
        if token != self.reset_token:
            return False
        if datetime.utcnow() > self.reset_token_expiry:
            return False
        return True
    
    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None
        db.session.commit()

    def add_points(self, amount, reason=None, metadata=None):
        """Add points to user's balance and record in both JSONB and point_transaction table"""
        if not self.points_history:
            self.points_history = {'transactions': []}
        
        # Record point transaction in JSONB
        transaction = {
            'amount': amount,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
            'balance_after': self.points + amount
        }
        
        # Add metadata if provided
        if metadata:
            transaction['metadata'] = metadata
        
        self.points_history['transactions'].append(transaction)
        
        # Add points to user's balance
        self.points += amount

        # Record in point_transaction table
        timestamp = datetime.utcnow()
        activity_type = metadata.get('status', 'other') if metadata else 'other'
        reference_id = metadata.get('company_id', None) if metadata else None

        insert_query = text("""
            INSERT INTO point_transaction 
            (user_id, amount, reason, timestamp, activity_type, reference_id, balance_after, transaction_metadata)
            VALUES 
            (:user_id, :amount, :reason, :timestamp, :activity_type, :reference_id, :balance_after, cast(:metadata as jsonb))
        """)
        
        db.session.execute(insert_query, {
            'user_id': self.id,
            'amount': amount,
            'reason': reason,
            'timestamp': timestamp,
            'activity_type': activity_type,
            'reference_id': reference_id,
            'balance_after': self.points,
            'metadata': json.dumps(metadata) if metadata else '{}'
        })
        
        db.session.commit()
        return self.points

    def get_points_history(self):
        """Get user's points history"""
        if not self.points_history:
            return []
        return self.points_history.get('transactions', [])

    def get_available_rewards(self):
        """Get rewards available to user based on points"""
        from .reward import Reward
        return Reward.get_available_rewards(self.points)

    def get_stats(self):
        """Get user's comprehensive statistics"""
        from .company import Company
        from .link_tracking import LinkClick
        
        stats = {
            'points': self.points,
            'companies': Company.get_stats_for_user(self.id),
            'clicks': LinkClick.get_stats_for_user(self.id),
            'rewards_earned': len(self.rewards_earned.all())
        }
        return stats

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
