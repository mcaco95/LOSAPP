from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Commission(db.Model):
    """Model for tracking individual commission entries"""
    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('commission_partner.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission_type = db.Column(db.String(20), default='safety')  # 'safety' or 'recruitment'
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
    
    def __init__(self, partner_id, company_id, amount, service_type, commission_type='safety',
                 is_initial_month=True, month_number=1, status='pending', metadata=None):
        self.partner_id = partner_id
        self.company_id = company_id
        self.amount = amount
        self.service_type = service_type
        self.commission_type = commission_type
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
    def calculate_commission(cls, partner_id, company_id, service_type, commission_type='safety',
                           is_initial_month=True, month_number=1, recruitment_charge=None):
        """Calculate commission amount based on service type and month number"""
        from ..models.commission_partner import CommissionPartner
        from ..models.company import Company
        
        partner = CommissionPartner.query.get(partner_id)
        if not partner:
            raise ValueError(f"Partner {partner_id} not found")
            
        company = Company.query.get(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        
        # Get base amount based on commission type
        if commission_type == 'recruitment':
            if not recruitment_charge:
                raise ValueError("Recruitment charge is required for recruitment commission")
            base_amount = recruitment_charge
            # Recruitment is always 10% for direct commission
            rate = 0.10
        else:  # safety service
            if not company.truck_count or not company.price_per_truck:
                raise ValueError("Company must have truck count and price per truck set")
            base_amount = company.truck_count * company.price_per_truck
            # Safety service rate depends on month number
            if month_number <= 24:  # First 2 years
                rate = 0.10
            else:
                rate = 0.025
        
        # If this is a network commission, always use 2.5%
        if partner.referrer_id:
            rate = 0.025
        
        return base_amount * rate
    
    @property
    def display_info(self):
        """Get display information based on commission type"""
        if self.commission_type == 'recruitment':
            role = self.commission_metadata.get('recruitment_role', 'Recruitment')
            return {
                'type': 'Recruitment',
                'description': f'One-time fee for {role}',
                'is_recurring': False,
                'badge_type': 'purple',
                'badge_text': 'One-time'
            }
        else:
            return {
                'type': 'Safety Service',
                'description': f'Month {self.month_number}',
                'is_recurring': True,
                'badge_type': 'info' if self.is_initial_month else 'light',
                'badge_text': 'Initial' if self.is_initial_month else f'Month {self.month_number}'
            }
    
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
        elif self.commission_type == 'recruitment':
            return "Recruitment Commission (10%)"
        elif self.month_number <= 24:
            return f"Direct Commission - Year {(self.month_number-1)//12 + 1} (10%)"
        else:
            return f"Direct Commission - Year {(self.month_number-1)//12 + 1} (2.5%)"
    
    def to_dict(self):
        """Convert commission to dictionary"""
        display = self.display_info
        return {
            'id': self.id,
            'partner_id': self.partner_id,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'amount': self.amount,
            'commission_type': self.commission_type,
            'service_type': self.service_type,
            'is_initial_month': self.is_initial_month,
            'month_number': self.month_number,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'metadata': self.commission_metadata,
            'display_type': display['type'],
            'display_description': display['description'],
            'is_recurring': display['is_recurring'],
            'badge_type': display['badge_type'],
            'badge_text': display['badge_text'],
            'commission_type_display': self.commission_type_display,
            'is_network_commission': self.is_network_commission
        } 