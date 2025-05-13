from datetime import datetime
from .. import db
import enum

# Enum for field types
class CustomFieldType(enum.Enum):
    TEXT = 'text'
    NUMBER = 'number'
    DATE = 'date'
    DROPDOWN = 'dropdown'
    BOOLEAN = 'boolean' # e.g., Yes/No

# Enum for which model the field applies to
class CustomFieldAppliesTo(enum.Enum):
    CONTACT = 'Contact'
    ACCOUNT = 'CrmAccount'

class CustomFieldDefinition(db.Model):
    __tablename__ = 'custom_field_definitions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True) # Name shown in UI (e.g., "Lead Score")
    field_type = db.Column(db.Enum(CustomFieldType), nullable=False) # Type of field (Text, Number, etc.)
    applies_to = db.Column(db.Enum(CustomFieldAppliesTo), nullable=False, index=True) # Which model it links to
    options = db.Column(db.JSON, nullable=True) # For dropdown choices, e.g., {"options": ["Hot", "Warm", "Cold"]}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to values
    values = db.relationship('CustomFieldValue', back_populates='definition', lazy='dynamic')

    def __repr__(self):
        return f'<CustomFieldDefinition {self.name} ({self.field_type.value} for {self.applies_to.value})>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'field_type': self.field_type.value if self.field_type else None, # Ensure enum is converted to string
            'applies_to': self.applies_to.value if self.applies_to else None, # Ensure enum is converted to string
            'options': self.options # options is already JSON or None
        }

class CustomFieldValue(db.Model):
    __tablename__ = 'custom_field_values'
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key to the definition
    definition_id = db.Column(db.Integer, db.ForeignKey('custom_field_definitions.id'), nullable=False, index=True)
    definition = db.relationship('CustomFieldDefinition', back_populates='values')

    # Foreign keys to the specific object (Contact or Account)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=True, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('crm_account.id'), nullable=True, index=True)
    # Ensure only one of contact_id or account_id is set (can add a CheckConstraint later if DB supports it)

    # The actual value stored
    # Using Text for flexibility, will need conversion based on definition.field_type
    value = db.Column(db.Text, nullable=True) 

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships back to the specific object (optional but useful)
    contact = db.relationship('Contact', back_populates='custom_field_values')
    account = db.relationship('CrmAccount', back_populates='custom_field_values')

    def __repr__(self):
        target_id = self.contact_id or self.account_id
        target_type = 'Contact' if self.contact_id else 'Account'
        return f'<CustomFieldValue {self.definition.name}={self.value} for {target_type} {target_id}>' 