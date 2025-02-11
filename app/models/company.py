from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Company(db.Model):
    """Company model for tracking referrals and their statuses"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='new')  # new, completed_form, meeting_scheduled, sold, paid
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_date = db.Column(db.DateTime)
    company_metadata = db.Column(JSONB)

    # Relationships
    user = db.relationship('User', backref=db.backref('companies', lazy='dynamic'))

    def __init__(self, name, user_id, status='new', metadata=None):
        self.name = name
        self.user_id = user_id
        self.status = status
        self.company_metadata = metadata or {}

    def update_status(self, new_status):
        """Update company status and record in metadata"""
        old_status = self.status
        self.status = new_status
        
        # Record status change in metadata
        status_history = self.company_metadata.get('status_history', [])
        status_history.append({
            'from': old_status,
            'to': new_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.company_metadata['status_history'] = status_history

        if new_status == 'paid' and not self.payment_date:
            self.payment_date = datetime.utcnow()

        db.session.commit()
        return True

    @property
    def status_display(self):
        """Human readable status"""
        return {
            'new': 'New Lead',
            'completed_form': 'Form Completed',
            'meeting_scheduled': 'Meeting Scheduled',
            'sold': 'Deal Closed',
            'paid': 'Commission Paid'
        }.get(self.status, self.status)

    @classmethod
    def get_stats_for_user(cls, user_id):
        """Get company statistics for a user"""
        stats = {
            'total': cls.query.filter_by(user_id=user_id).count(),
            'by_status': {}
        }
        
        # Get counts by status
        status_counts = db.session.query(
            cls.status, 
            db.func.count(cls.id)
        ).filter_by(user_id=user_id).group_by(cls.status).all()
        
        for status, count in status_counts:
            stats['by_status'][status] = count
            
        return stats

    def to_dict(self):
        """Convert company to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'status_display': self.status_display,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'metadata': self.company_metadata
        }
