from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class CrmAccount(db.Model):
    __tablename__ = 'crm_account'

    id = db.Column(db.Integer, primary_key=True)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    website = db.Column(db.String(255), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)  # Main company line
    
    # For a structured address, consider JSONB or separate address fields/table
    # For simplicity now, a text field. Can be enhanced to JSONB.
    address = db.Column(db.Text, nullable=True) 
    
    status = db.Column(db.String(50), nullable=True, default='Prospect', index=True) 
    # Example statuses: 'Prospect', 'Active Client', 'Former Client', 'Partner', 'On Hold'
    
    custom_data = db.Column(JSONB, nullable=True) # For flexible, user-defined fields
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # Sales rep who owns this account
    sales_rep = db.relationship('SalesUser', backref=db.backref('crm_accounts', lazy='dynamic'))
    # Contacts associated with this account
    contacts = db.relationship('Contact', backref='crm_account', lazy='dynamic', order_by='Contact.first_name')

    def __repr__(self):
        return f'<CrmAccount {self.id}: {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'sales_rep_id': self.sales_rep_id,
            'name': self.name,
            'website': self.website,
            'industry': self.industry,
            'phone_number': self.phone_number,
            'address': self.address,
            'status': self.status,
            'custom_data': self.custom_data or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'sales_rep_name': self.sales_rep.user.name if self.sales_rep and self.sales_rep.user else None
        }

# Example CrmAccount statuses (can be managed in config or as an Enum later)
CRM_ACCOUNT_STATUSES = [
    'Prospect', 
    'Needs Assessment',
    'Negotiation',
    'Active Client', 
    'On Hold',
    'Former Client', 
    'Partner',
    'Not a Fit'
] 