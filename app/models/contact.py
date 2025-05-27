from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Contact(db.Model):
    __tablename__ = 'crm_contact'

    id = db.Column(db.Integer, primary_key=True)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=True, index=True)
    crm_account_id = db.Column(db.Integer, db.ForeignKey('crm_account.id'), nullable=True, index=True)
    
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone_number = db.Column(db.String(30), nullable=False) # Direct line for contact
    job_title = db.Column(db.String(100), nullable=True)
    
    status = db.Column(db.String(50), nullable=False, default='Lead', index=True)
    # Example statuses: 'Lead', 'Contacted', 'Needs Follow-up', 'Working', 'Qualified', 'Unqualified', 'Converted to Customer', 'Lost'
    
    source = db.Column(db.String(50), nullable=True) 
    # Example sources: 'Website Lead', 'Referral', 'Cold Call', 'Event', 'Advertisement', 'Other'
    
    custom_data = db.Column(db.JSON, nullable=True) # For flexible custom fields initially
    is_primary_for_account = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sales_rep = db.relationship('SalesUser', backref=db.backref('crm_contacts', lazy='dynamic'))
    # crm_account relationship is now handled by the backref in CrmAccount.contacts
    # crm_account = db.relationship('CrmAccount', backref=db.backref('contacts', lazy='dynamic')) # Removed to avoid conflict
    # call_logs relationship is now handled by the backref in CallLog.contact
    notes = db.relationship('Note', backref='contact', lazy='dynamic', order_by='desc(Note.timestamp)', cascade="all, delete-orphan")
    
    # Relationship to custom field values
    custom_field_values = db.relationship('CustomFieldValue', back_populates='contact', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Contact {self.id}: {self.first_name} {self.last_name}>'

    @property
    def full_name(self):
        if self.last_name:
            return f'{self.first_name} {self.last_name}'
        return self.first_name

    def to_dict(self):
        return {
            'id': self.id,
            'sales_rep_id': self.sales_rep_id,
            'crm_account_id': self.crm_account_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone_number': self.phone_number,
            'job_title': self.job_title,
            'status': self.status,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sales_rep_name': self.sales_rep.user.name if self.sales_rep and self.sales_rep.user else None,
            'crm_account_name': self.crm_account.name if self.crm_account else None
        }

# Example Contact statuses
CONTACT_STATUSES = [
    'Lead', 
    'Prospecting',
    'Contacted', 
    'Needs Follow-up',
    'Working',
    'Nurturing',
    'Qualified', 
    'Demo Scheduled',
    'Proposal Sent',
    'Negotiation',
    'Converted to Customer', 
    'Unqualified', 
    'Lost', 
    'Do Not Contact'
]

# Example Contact sources
CONTACT_SOURCES = [
    'Website Lead',
    'Manual Entry',
    'Referral Program',
    'Cold Call',
    'Email Campaign',
    'Social Media',
    'Event/Conference',
    'Trade Show',
    'Advertisement',
    'Partner Referral',
    'Existing Client',
    'Other'
] 