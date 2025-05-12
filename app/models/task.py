from .. import db
from datetime import datetime
# from sqlalchemy.dialects.postgresql import UUID # No longer using UUID for this model
# import uuid # No longer using UUID for this model
from .sales_user import SalesUser 
from .contact import Contact
from .crm_account import CrmAccount
from .deal import Deal # Added import for Deal
from .note import Note # Added import for Note

TASK_STATUSES = [
    ('Open', 'Open'),
    ('In Progress', 'In Progress'),
    ('Completed', 'Completed'),
    ('Cancelled', 'Cancelled'),
    ('Pending Input', 'Pending Input') # Added a common status
]

TASK_PRIORITIES = [
    ('Low', 'Low'),
    ('Medium', 'Medium'),
    ('High', 'High'),
    ('Urgent', 'Urgent') # Added a common priority
]

class Task(db.Model):
    __tablename__ = 'crm_tasks' # Explicit table name to avoid conflicts

    id = db.Column(db.Integer, primary_key=True) # Changed to Integer for consistency
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    
    status = db.Column(db.String(50), nullable=False, default='Open')
    priority = db.Column(db.String(50), nullable=True, default='Medium')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Changed ForeignKeys to point to singular table names and use Integer type
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=True)
    crm_account_id = db.Column(db.Integer, db.ForeignKey('crm_account.id'), nullable=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'), nullable=True) # New field for Deal FK

    # Relationships
    sales_rep = db.relationship('SalesUser', backref=db.backref('crm_tasks', lazy='dynamic'))
    contact = db.relationship('Contact', backref=db.backref('crm_tasks', lazy='dynamic', cascade="all, delete-orphan"))
    crm_account = db.relationship('CrmAccount', backref=db.backref('crm_tasks', lazy='dynamic')) # Cascade might be too aggressive here if account deleted
    deal = db.relationship('Deal', backref=db.backref('crm_tasks', lazy='dynamic')) # New relationship
    # notes = db.relationship('Note', backref='task', lazy='dynamic', cascade="all, delete-orphan") # Removed - relies on backref from Note.task

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

    def can_be_edited_by(self, user):
        if not user or not user.sales_profile:
            return False
        return self.sales_rep_id == user.sales_profile.id

    def mark_complete(self):
        self.status = 'Completed'
        self.completed_at = datetime.utcnow()
        db.session.add(self)

    def mark_open(self):
        self.status = 'Open'
        self.completed_at = None # Clear completed_at if reopening
        db.session.add(self)

    # Consider a to_dict() method for API or complex frontend needs later
    def to_dict(self, include_contact=False, include_account=False):
        data = {
            'id': self.id, # Will be integer now
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'sales_rep_id': self.sales_rep_id,
            'contact_id': self.contact_id,
            'crm_account_id': self.crm_account_id,
            'deal_id': self.deal_id,
        }
        if include_contact and self.contact:
            data['contact_name'] = self.contact.full_name
        if include_account and self.crm_account:
            data['crm_account_name'] = self.crm_account.name
        # Example: include note count
        # data['note_count'] = self.notes.count()
        return data 