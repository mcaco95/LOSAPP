from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Company(db.Model):
    """Company model for tracking referrals and their statuses"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='lead')  # lead, demo_scheduled, demo_completed, client_signed, renewed, upgraded
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_date = db.Column(db.DateTime)
    company_metadata = db.Column(JSONB)
    
    # New fields for enhanced tracking
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    service_type = db.Column(db.String(20))  # professional, standard
    preferred_contact_time = db.Column(db.String(20))
    additional_info = db.Column(db.Text)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('companies', lazy='dynamic'))

    def __init__(self, name, user_id, status='lead', metadata=None, **kwargs):
        self.name = name
        self.user_id = user_id
        self.status = status
        self.company_metadata = metadata or {}
        
        # Initialize status history for new companies
        if 'status_history' not in self.company_metadata:
            self.company_metadata['status_history'] = [{
                'from': None,
                'to': status,
                'timestamp': datetime.utcnow().isoformat(),
                'points_awarded': 0  # Initial status doesn't award points
            }]
        
        # Set additional fields if provided
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def update_status(self, new_status, points_awarded=0):
        """Update company status and record in metadata"""
        if new_status == self.status:
            return False
            
        old_status = self.status
        self.status = new_status
        
        # Initialize metadata if not exists
        if not self.company_metadata:
            self.company_metadata = {}
        
        # Initialize status_history if not exists
        if 'status_history' not in self.company_metadata:
            self.company_metadata['status_history'] = []
        
        # Record status change in metadata with points
        status_history = self.company_metadata['status_history']
        status_history.append({
            'from': old_status,
            'to': new_status,
            'timestamp': datetime.utcnow().isoformat(),
            'points_awarded': points_awarded  # Store the actual points awarded
        })
        self.company_metadata['status_history'] = status_history

        if new_status == 'client_signed' and not self.payment_date:
            self.payment_date = datetime.utcnow()

        db.session.commit()
        return True

    @property
    def status_display(self):
        """Human readable status"""
        return Company.get_status_display(self.status)
        
    @staticmethod
    def get_status_display(status):
        """Get human readable status from status code"""
        return {
            'lead': 'Lead Generated',
            'demo_scheduled': 'Demo Scheduled',
            'demo_completed': 'Demo Completed',
            'client_signed': 'Client Signed',
            'renewed': 'Client Renewed',
            'upgraded': 'Client Upgraded',
            'partner_signup': 'Partner Signup'
        }.get(status, status)
        
    @property
    def service_display(self):
        """Human readable service type"""
        return {
            'professional': 'Professional Service ($3,000/month)',
            'standard': 'Standard Service ($500/month)'
        }.get(self.service_type, 'Unknown')

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
            'contact_name': self.contact_name,
            'email': self.email,
            'phone': self.phone,
            'service_type': self.service_type,
            'service_display': self.service_display,
            'status': self.status,
            'status_display': self.status_display,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'preferred_contact_time': self.preferred_contact_time,
            'additional_info': self.additional_info,
            'metadata': self.company_metadata
        }
