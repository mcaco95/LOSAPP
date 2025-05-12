from datetime import datetime
from .. import db
from .user import User

class OperationsUser(db.Model):
    """Model for operations team members with additional attributes for call handling"""
    __tablename__ = 'operations_user'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    phone_number = db.Column(db.String(20))
    extension = db.Column(db.String(10), unique=True)
    role = db.Column(db.String(50), nullable=False, default='operator')
    is_available = db.Column(db.Boolean, default=True)
    last_active = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('operations_profile', uselist=False))
    call_logs = db.relationship('CallLog', backref='operator', lazy='dynamic')

    def __init__(self, user_id, phone_number=None, extension=None, role='operator'):
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

    def update_availability(self, status):
        """Update operator availability status"""
        self.is_available = status
        self.last_active = datetime.utcnow()
        db.session.commit()

    @classmethod
    def get_available_operators(cls):
        """Get list of currently available operators"""
        return cls.query.filter_by(is_available=True).all()

    def to_dict(self):
        """Convert operator details to dictionary"""
        return {
            'id': self.id,
            'name': self.full_name,
            'email': self.email,
            'phone_number': self.phone_number,
            'extension': self.extension,
            'role': self.role,
            'is_available': self.is_available,
            'last_active': self.last_active.isoformat() if self.last_active else None
        } 