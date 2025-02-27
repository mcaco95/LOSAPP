from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class CommissionPartner(db.Model):
    """Model for tracking commission partners and their hierarchical relationships"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('commission_partner.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Commission settings
    commission_tier = db.Column(db.String(20), default='standard')  # standard, premium, etc.
    custom_rates = db.Column(db.Boolean, default=False)  # Whether this partner has custom commission rates
    partner_metadata = db.Column(JSONB)  # Store additional partner data and custom rates if applicable
    
    # Relationships
    user = db.relationship('User', backref=db.backref('commission_partner', uselist=False))
    referrer = db.relationship('CommissionPartner', remote_side=[id], backref=db.backref('referred_partners', lazy='dynamic'))
    
    def __init__(self, user_id, referrer_id=None, commission_tier='standard', metadata=None):
        self.user_id = user_id
        self.referrer_id = referrer_id
        self.commission_tier = commission_tier
        self.partner_metadata = metadata or {}
    
    @property
    def referred_count(self):
        """Get count of partners directly referred by this partner"""
        return self.referred_partners.count()
    
    @property
    def active_referred_count(self):
        """Get count of active partners directly referred by this partner"""
        return self.referred_partners.filter_by(is_active=True).count()
    
    def get_commission_rate(self, service_type, is_initial_month=False):
        """Get commission rate based on service type and month"""
        # Check if partner has custom rates
        if self.custom_rates and self.partner_metadata and 'custom_rates' in self.partner_metadata:
            custom_rates = self.partner_metadata['custom_rates']
            key = f"{service_type}_{'initial' if is_initial_month else 'recurring'}"
            if key in custom_rates:
                return custom_rates[key]
        
        # Default rates
        if service_type == 'professional':
            return 0.20 if is_initial_month else 0.025  # 20% initial, 2.5% recurring
        else:  # standard
            return 0.20 if is_initial_month else 0.025  # 20% initial, 2.5% recurring
    
    def to_dict(self):
        """Convert partner to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user': self.user.name if self.user else None,
            'referrer_id': self.referrer_id,
            'referrer': self.referrer.user.name if self.referrer and self.referrer.user else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'commission_tier': self.commission_tier,
            'referred_count': self.referred_count,
            'metadata': self.partner_metadata
        } 