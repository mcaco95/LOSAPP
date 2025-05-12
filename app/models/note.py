from datetime import datetime
from .. import db
from sqlalchemy import desc # Import desc

class Note(db.Model):
    __tablename__ = 'crm_note'

    id = db.Column(db.Integer, primary_key=True)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=True, index=True)
    crm_account_id = db.Column(db.Integer, db.ForeignKey('crm_account.id'), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('crm_tasks.id'), nullable=True, index=True)
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    text = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sales_rep = db.relationship('SalesUser', backref=db.backref('crm_notes', lazy='dynamic'))
    # contact relationship is now handled by the backref in Contact.notes
    # contact = db.relationship('Contact', backref=db.backref('notes', lazy='dynamic', order_by='desc(Note.timestamp)')) # Removed to avoid conflict
    crm_account = db.relationship('CrmAccount', backref=db.backref('notes', lazy='dynamic', order_by=desc(timestamp)))
    deal = db.relationship('Deal', backref=db.backref('notes', lazy='dynamic', order_by=desc(timestamp)))
    task = db.relationship('Task', backref=db.backref('notes', lazy='dynamic', order_by=desc(timestamp)))

    # Constraint to ensure at least one of contact_id or crm_account_id is populated
    # This might require a CheckConstraint or handling at the application level if not directly supported by SQLAlchemy for all DBs.
    # For now, we'll rely on application logic to enforce this.

    def __repr__(self):
        return f'<Note {self.id} by SalesRep {self.sales_rep_id} on {self.timestamp.strftime("%Y-%m-%d %H:%M")}>'

    def to_dict(self):
        return {
            'id': self.id,
            'sales_rep_id': self.sales_rep_id,
            'contact_id': self.contact_id,
            'crm_account_id': self.crm_account_id,
            'deal_id': self.deal_id,
            'task_id': self.task_id,
            'timestamp': self.timestamp.isoformat(),
            'text': self.text,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'sales_rep_name': self.sales_rep.user.name if self.sales_rep and self.sales_rep.user else None,
            'contact_name': self.contact.full_name if self.contact else None,
            'crm_account_name': self.crm_account.name if self.crm_account else None,
            'deal_name': self.deal.name if self.deal else None,
            'task_title': self.task.title if self.task else None
        } 