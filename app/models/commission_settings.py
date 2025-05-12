from datetime import datetime
from app import db
from sqlalchemy.exc import NoResultFound

class CommissionSettings(db.Model):
    __tablename__ = 'commission_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, key, value, description=None):
        self.key = key
        self.value = value
        self.description = description
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value by key"""
        try:
            setting = cls.query.filter_by(key=key).first()
            if setting:
                return setting.value
            return default
        except Exception:
            return default
    
    @classmethod
    def set_value(cls, key, value, description=None):
        """Set a setting value by key"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()
        return setting
    
    @classmethod
    def get_all_settings(cls):
        """Get all settings as a dictionary"""
        settings = cls.query.all()
        return {s.key: s.value for s in settings}
    
    @classmethod
    def initialize_default_settings(cls):
        """Initialize default settings if they don't exist"""
        defaults = {
            'first_2_years_rate': (0.10, 'Commission rate for the first 2 years (24 months)'),
            'after_2_years_rate': (0.025, 'Commission rate after 2 years (month 25+)'),
            'network_commission_rate': (0.025, 'Commission rate for partners on their network\'s sales')
        }
        
        for key, (value, description) in defaults.items():
            if not cls.query.filter_by(key=key).first():
                cls.set_value(key, value, description)
        
        return cls.get_all_settings() 