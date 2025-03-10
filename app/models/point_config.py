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
            # Basic click points
            'click': 1,                    # Regular click
            'unique_click': 1,             # Unique visitor click
            
            # Sales cycle points
            'status_referral_form_completed': 2,  # Referral form completed
            'status_filled_out_form': 2,         # Filled out form
            'status_demo_scheduled': 5,          # Demo scheduled
            'status_demo_completed': 15,         # Demo completed
            'status_client_signed_up': 50,       # Client signed up
            'status_client_renewed': 25,         # Client renewed
            
            # Bonus points
            'bonus_fast_track': 1,         # Fast-Track Bonus (double points if client signs within 30 days)
            'bonus_high_value': 30,        # High-Value Client Bonus (Professional Plan)
            'bonus_consistent_closer': 50   # Consistent Closer Bonus (3+ clients in a quarter)
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
