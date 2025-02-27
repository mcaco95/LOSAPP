from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Commission(db.Model):
    """Model for tracking individual commission entries"""
    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('commission_partner.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    service_type = db.Column(db.String(20), nullable=False)  # professional, standard
    is_initial_month = db.Column(db.Boolean, default=True)
    month_number = db.Column(db.Integer, default=1)  # 1 for initial month, 2+ for recurring
    status = db.Column(db.String(20), default='pending')  # pending, paid, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    commission_metadata = db.Column(JSONB)
    
    # Relationships
    partner = db.relationship('CommissionPartner', backref=db.backref('commissions', lazy='dynamic'))
    company = db.relationship('Company', backref=db.backref('commissions', lazy='dynamic'))
    
    def __init__(self, partner_id, company_id, amount, service_type, is_initial_month=True, 
                 month_number=1, status='pending', metadata=None):
        self.partner_id = partner_id
        self.company_id = company_id
        self.amount = amount
        self.service_type = service_type
        self.is_initial_month = is_initial_month
        self.month_number = month_number
        self.status = status
        self.commission_metadata = metadata or {}
    
    def mark_as_paid(self):
        """Mark commission as paid"""
        self.status = 'paid'
        self.paid_at = datetime.utcnow()
        db.session.commit()
    
    def cancel(self, reason=None):
        """Cancel commission"""
        self.status = 'cancelled'
        if reason:
            if not self.commission_metadata:
                self.commission_metadata = {}
            self.commission_metadata['cancellation_reason'] = reason
        db.session.commit()
    
    @classmethod
    def get_partner_commissions(cls, partner_id, status=None):
        """Get all commissions for a partner, optionally filtered by status"""
        query = cls.query.filter_by(partner_id=partner_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_company_commissions(cls, company_id):
        """Get all commissions for a company"""
        return cls.query.filter_by(company_id=company_id).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def calculate_commission(cls, partner_id, company_id, service_type, is_initial_month=True, month_number=1):
        """Calculate commission amount based on service type and month number"""
        from ..models.commission_partner import CommissionPartner
        
        partner = CommissionPartner.query.get(partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
        
        # Get base service price
        if service_type == 'professional':
            base_amount = 3000.0  # $3,000/month for Professional
        else:  # standard
            base_amount = 500.0   # $500/month for Standard
        
        # Get commission rate based on month number
        rate = partner.get_commission_rate(service_type, month_number)
        
        # Calculate commission amount
        commission_amount = base_amount * rate
        
        return commission_amount
    
    @property
    def is_network_commission(self):
        """Check if this is a network commission (from referred partner)"""
        if self.commission_metadata and 'network_commission' in self.commission_metadata:
            return self.commission_metadata['network_commission']
        return False
    
    @property
    def commission_type_display(self):
        """Get a display string for the commission type"""
        if self.is_network_commission:
            return "Network Commission (2.5%)"
        elif self.month_number <= 24:
            return f"Direct Commission - Year {(self.month_number-1)//12 + 1} (10%)"
        else:
            return f"Direct Commission - Year {(self.month_number-1)//12 + 1} (2.5%)"
    
    def to_dict(self):
        """Convert commission to dictionary"""
        return {
            'id': self.id,
            'partner_id': self.partner_id,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'amount': self.amount,
            'service_type': self.service_type,
            'is_initial_month': self.is_initial_month,
            'month_number': self.month_number,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'metadata': self.commission_metadata,
            'commission_type': self.commission_type_display,
            'is_network_commission': self.is_network_commission
        } 