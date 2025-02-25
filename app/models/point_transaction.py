from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class PointTransaction(db.Model):
    """Model for tracking all point transactions"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    balance_after = db.Column(db.Integer, nullable=False)
    activity_type = db.Column(db.String(50))  # click, status_change, etc.
    reference_id = db.Column(db.Integer)  # company_id, click_id, etc.
    transaction_metadata = db.Column(JSONB)

    # Relationships
    user = db.relationship('User', backref=db.backref('point_transactions', lazy='dynamic'))

    def __init__(self, user_id, amount, reason=None, activity_type=None, reference_id=None, metadata=None):
        self.user_id = user_id
        self.amount = amount
        self.reason = reason
        self.activity_type = activity_type
        self.reference_id = reference_id
        self.transaction_metadata = metadata or {}

    @classmethod
    def create_transaction(cls, user, amount, reason=None, activity_type=None, reference_id=None, metadata=None):
        """Create a new point transaction"""
        transaction = cls(
            user_id=user.id,
            amount=amount,
            reason=reason,
            activity_type=activity_type,
            reference_id=reference_id,
            metadata=metadata
        )
        # Calculate balance after transaction
        transaction.balance_after = user.points + amount
        
        # Add and commit transaction
        db.session.add(transaction)
        
        # Update user's points
        user.points += amount
        
        db.session.commit()
        return transaction

    @classmethod
    def get_user_transactions(cls, user_id, limit=None):
        """Get all transactions for a user"""
        query = cls.query.filter_by(user_id=user_id).order_by(cls.timestamp.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def get_transactions_by_type(cls, activity_type, start_date=None, end_date=None):
        """Get transactions by activity type with optional date range"""
        query = cls.query.filter_by(activity_type=activity_type)
        
        if start_date:
            query = query.filter(cls.timestamp >= start_date)
        if end_date:
            query = query.filter(cls.timestamp <= end_date)
            
        return query.order_by(cls.timestamp.desc()).all()

    def to_dict(self):
        """Convert transaction to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'balance_after': self.balance_after,
            'activity_type': self.activity_type,
            'reference_id': self.reference_id,
            'metadata': self.transaction_metadata
        } 