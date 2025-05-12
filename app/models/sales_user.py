from datetime import datetime
from .. import db
from .user import User
# Assuming CallLog model exists, might need adjustment if name differs
# from .call_log import CallLog 

class SalesUser(db.Model):
    """Model for sales team members with CRM and call handling capabilities"""
    __tablename__ = 'sales_user'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    # Phone system integration fields
    phone_number = db.Column(db.String(20), nullable=True) 
    extension = db.Column(db.String(10), unique=True, nullable=True) 
    role = db.Column(db.String(50), nullable=False, default='sales_rep') # Example role
    # Add other sales-specific fields here if needed in the future
    # e.g., region = db.Column(db.String(50))
    # e.g., quota = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('sales_profile', uselist=False))
    # Enable this relationship once CallLog model is confirmed/created
    call_logs = db.relationship('CallLog', backref='sales_rep', lazy='dynamic') 

    def __init__(self, user_id, phone_number=None, extension=None, role='sales_rep'):
        self.user_id = user_id
        self.phone_number = phone_number
        self.extension = extension
        self.role = role

    @property
    def full_name(self):
        return self.user.name if self.user else None

    @property
    def email(self):
        return self.user.email if self.user else None

    def to_dict(self):
        """Convert sales user details to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.full_name,
            'email': self.email,
            'phone_number': self.phone_number,
            'extension': self.extension,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 