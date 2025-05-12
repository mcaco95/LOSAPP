from datetime import datetime
from .. import db
from .sales_user import SalesUser
# Ensure Contact model is imported if not already (adjust path if necessary)
# from .contact import Contact # Uncomment if needed, or handle via __init__.py

class CallLog(db.Model):
    """Model for tracking call activities"""
    __tablename__ = 'call_logs'

    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('operations_user.id'), nullable=True, index=True)
    sales_rep_id = db.Column(db.Integer, db.ForeignKey('sales_user.id'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=True, index=True)
    call_sid = db.Column(db.String(100), unique=True)  # Twilio call ID
    from_number = db.Column(db.String(20))
    to_number = db.Column(db.String(20))
    direction = db.Column(db.String(20))  # inbound or outbound
    duration = db.Column(db.Integer)  # Duration in seconds
    status = db.Column(db.String(20))  # queued, ringing, in-progress, completed, failed
    recording_url = db.Column(db.Text)
    call_data = db.Column(db.JSON)  # Additional call metadata
    notes = db.Column(db.Text)
    start_time = db.Column(db.DateTime)  # When the call was answered
    end_time = db.Column(db.DateTime)  # When the call ended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to SalesUser is handled by the backref in SalesUser.call_logs
    # sales_rep = db.relationship('SalesUser', foreign_keys=[sales_rep_id]) # Removed redundant relationship
    # Relationship to Contact
    contact = db.relationship('Contact', backref=db.backref('call_logs', lazy='dynamic', order_by='desc(CallLog.created_at)'))

    def __init__(self, call_sid, from_number, to_number, status='queued', direction='outbound', operator_id=None, sales_rep_id=None, contact_id=None):
        if operator_id is None and sales_rep_id is None:
            raise ValueError("Either operator_id or sales_rep_id must be provided.")
        if operator_id is not None and sales_rep_id is not None:
            raise ValueError("Provide either operator_id or sales_rep_id, not both.")
            
        self.operator_id = operator_id
        self.sales_rep_id = sales_rep_id
        self.call_sid = call_sid
        self.from_number = from_number
        self.to_number = to_number
        self.status = status
        self.direction = direction
        self.call_data = {}
        self.contact_id = contact_id

    def update_status(self, status, duration=None):
        """Update call status and duration"""
        self.status = status
        if duration is not None:
            self.duration = duration
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def add_recording(self, url):
        """Add recording URL to call log"""
        self.recording_url = url
        db.session.commit()

    def add_note(self, note):
        """Add note to call log"""
        if self.notes:
            self.notes = f"{self.notes}\n{note}"
        else:
            self.notes = note
        db.session.commit()

    def update_call_data(self, data):
        """Update call metadata"""
        self.call_data.update(data)
        db.session.commit()

    @classmethod
    def get_operator_calls(cls, operator_id, status=None):
        """Get all calls for a specific operator"""
        query = cls.query.filter_by(operator_id=operator_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_sales_rep_calls(cls, sales_rep_id, status=None):
        """Get all calls for a specific sales representative"""
        query = cls.query.filter_by(sales_rep_id=sales_rep_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.created_at.desc()).all()

    def to_dict(self):
        """Convert call log to dictionary"""
        return {
            'id': self.id,
            'operator_id': self.operator_id,
            'sales_rep_id': self.sales_rep_id,
            'contact_id': self.contact_id,
            'call_sid': self.call_sid,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'duration': self.duration,
            'status': self.status,
            'recording_url': self.recording_url,
            'notes': self.notes,
            'call_data': self.call_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'contact_name': self.contact.full_name if self.contact else None,
            'sales_rep_name': self.sales_rep.user.name if self.sales_rep and self.sales_rep.user else None
        } 