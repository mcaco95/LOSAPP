from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class PointConfig(db.Model):
    """Configuration model for point values of different actions"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)  # e.g. 'click', 'unique_click', 'status_change'
    value = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    config_metadata = db.Column(JSONB)

    def __init__(self, key, value, metadata=None):
        self.key = key
        self.value = value
        self.config_metadata = metadata or {}

    @classmethod
    def get_value(cls, key, default=0):
        """Get point value for a specific action"""
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default

    @classmethod
    def get_status_points(cls, status):
        """Get points for a specific company status"""
        return cls.get_value(f'status_{status}', 0)

    @classmethod
    def get_all_configs(cls):
        """Get all point configurations"""
        configs = cls.query.all()
        return {config.key: config.value for config in configs}

    @classmethod
    def set_value(cls, key, value, metadata=None):
        """Set point value for a specific action"""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            if metadata:
                config.config_metadata = metadata
        else:
            config = cls(key=key, value=value, metadata=metadata)
            db.session.add(config)
        
        db.session.commit()
        return config

    @classmethod
    def initialize_defaults(cls):
        """Initialize default point configurations"""
        defaults = {
            'click': 1,                    # Basic click
            'unique_click': 5,             # Unique visitor click
            'status_completed_form': 10,   # Company completed form
            'status_meeting_scheduled': 20, # Meeting scheduled
            'status_sold': 50,             # Deal closed
            'status_paid': 100             # Commission paid
        }
        
        for key, value in defaults.items():
            if not cls.query.filter_by(key=key).first():
                cls.set_value(key, value)

    def to_dict(self):
        """Convert config to dictionary"""
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.config_metadata
        }
