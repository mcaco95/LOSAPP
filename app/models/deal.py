from .. import db
from datetime import datetime
from .sales_user import SalesUser # For relationship
from .contact import Contact # For relationship
from .crm_account import CrmAccount # For relationship
from .note import Note # Added import for Note

DEAL_STAGES = [
    ('Prospecting', 'Prospecting'),
    ('Qualification', 'Qualification'),
    ('Needs Analysis', 'Needs Analysis'),
    ('Value Proposition', 'Value Proposition'),
    ('Proposal Sent', 'Proposal Sent'),
    ('Negotiation/Review', 'Negotiation/Review'),
    ('Closed Won', 'Closed Won'),
    ('Closed Lost', 'Closed Lost'),
]

class Deal(db.Model):
    __tablename__ = 'crm_deal'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    stage = db.Column(db.String(100), nullable=False, default=DEAL_STAGES[0][0]) # Default to first stage
    expected_close_date = db.Column(db.Date, nullable=True)
    probability = db.Column(db.Integer, nullable=True) # Percentage 0-100

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign Keys
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=True)
    crm_account_id = db.Column(db.Integer, db.ForeignKey('crm_account.id'), nullable=False)

    # Relationships
    sales_rep = db.relationship('SalesUser', backref=db.backref('deals', lazy='dynamic'))
    contact = db.relationship('Contact', backref=db.backref('deals', lazy='dynamic'))
    crm_account = db.relationship('CrmAccount', backref=db.backref('deals', lazy='dynamic'))
    # notes = db.relationship('Note', backref='deal', lazy='dynamic', cascade="all, delete-orphan") # Removed - relies on backref from Note.deal

    def __repr__(self):
        return f'<Deal {self.id}: {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'amount': self.amount,
            'stage': self.stage,
            'expected_close_date': self.expected_close_date.isoformat() if self.expected_close_date else None,
            'probability': self.probability,
            'sales_rep_id': self.sales_rep_id,
            'sales_rep_name': self.sales_rep.user.name if self.sales_rep and self.sales_rep.user else None,
            'contact_id': self.contact_id,
            'contact_name': self.contact.full_name if self.contact else None,
            'crm_account_id': self.crm_account_id,
            'crm_account_name': self.crm_account.name if self.crm_account else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            # Add notes count or recent notes if needed
            # 'notes': [note.to_dict() for note in self.notes.limit(5).all()] # Example
        }

    # Potential helper methods:
    # - Method to get current probability based on stage (if we define defaults per stage)
    # - Method to check if deal is closed (won or lost)
    def is_closed(self):
        return self.stage in ['Closed Won', 'Closed Lost'] 