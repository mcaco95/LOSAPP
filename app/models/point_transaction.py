from datetime import datetime
from .. import db
from sqlalchemy.dialects.postgresql import JSONB

class PointTransaction(db.Model):
    """Model for tracking point transactions"""
    __tablename__ = 'point_transaction'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    balance_after = db.Column(db.Integer, nullable=False)
    activity_type = db.Column(db.String(50), index=True)
    reference_id = db.Column(db.Integer)
    transaction_metadata = db.Column(JSONB)

    # Relationship
    user = db.relationship('User', backref=db.backref('point_transactions', lazy=True))

    def __repr__(self):
        return f'<PointTransaction {self.id}: {self.amount} points for user {self.user_id}>'

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