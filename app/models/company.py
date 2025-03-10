from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from .. import db

class Company(db.Model):
    """Company model for tracking referrals and their statuses"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='referral_form_completed')  # Updated default status
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_date = db.Column(db.DateTime)
    company_metadata = db.Column(JSONB)
    
    # New fields for enhanced tracking
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    service_type = db.Column(db.String(20))  # safety, recruitment, both
    preferred_contact_time = db.Column(db.String(20))
    additional_info = db.Column(db.Text)
    
    # New fields for service status tracking
    safety_status = db.Column(db.String(20), default='inactive')  # active, inactive
    recruitment_status = db.Column(db.String(20), default='inactive')  # active, inactive
    recruitment_requests = db.Column(JSONB, default={
        'requests': []
    })  # Simplified recruitment request structure
    
    # Safety configuration fields
    truck_count = db.Column(db.Integer, default=0)
    price_per_truck = db.Column(db.Float, default=0.0)

    # Valid statuses
    VALID_STATUSES = [
        'lead',
        'referral_form_completed',
        'filled_out_form',
        'demo_scheduled',
        'demo_completed',
        'client_renewed',
        'client_signed_up'
    ]

    # Status order for validation
    STATUS_ORDER = {
        'lead': 0,
        'referral_form_completed': 1,
        'filled_out_form': 2,
        'demo_scheduled': 3,
        'demo_completed': 4,
        'client_signed_up': 5,
        'client_renewed': 6
    }

    # Relationships
    user = db.relationship('User', backref=db.backref('companies', lazy='dynamic'))

    def __init__(self, name, user_id, status='lead', metadata=None, **kwargs):
        self.name = name
        self.user_id = user_id
        self.status = status
        self.company_metadata = metadata or {}
        self.recruitment_requests = {'requests': []}
        
        # Initialize status history for new companies
        if 'status_history' not in self.company_metadata:
            self.company_metadata['status_history'] = [{
                'from': None,
                'to': status,
                'timestamp': datetime.utcnow().isoformat(),
                'points_awarded': 0
            }]
        
        # Set additional fields if provided
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def update_status(self, new_status, points_awarded=0):
        """Update company status and record in metadata"""
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}. Must be one of: {', '.join(self.VALID_STATUSES)}")
            
        if new_status == self.status:
            return False
            
        old_status = self.status
        self.status = new_status
        
        # Initialize metadata if not exists
        if not self.company_metadata:
            self.company_metadata = {}
        
        # Initialize status_history if not exists
        if 'status_history' not in self.company_metadata:
            self.company_metadata['status_history'] = []
        
        # Record status change in metadata with points
        status_history = self.company_metadata['status_history']
        status_history.append({
            'from': old_status,
            'to': new_status,
            'timestamp': datetime.utcnow().isoformat(),
            'points_awarded': points_awarded
        })
        self.company_metadata['status_history'] = status_history

        if new_status == 'client_signed_up' and not self.payment_date:
            self.payment_date = datetime.utcnow()

        db.session.add(self)
        db.session.commit()
        return True

    @property
    def status_display(self):
        """Human readable status"""
        return Company.get_status_display(self.status)
        
    @staticmethod
    def get_status_display(status):
        """Get human readable status from status code"""
        return {
            'lead': 'Lead',
            'referral_form_completed': 'Referral form completed',
            'filled_out_form': 'Filled out form',
            'demo_scheduled': 'Demo scheduled',
            'demo_completed': 'Demo completed',
            'client_renewed': 'Client renewed',
            'client_signed_up': 'Client signed up'
        }.get(status, status)
        
    @property
    def service_display(self):
        """Human readable service type"""
        return {
            'safety': 'Safety Service',
            'recruitment': 'Recruitment Service',
            'both': 'Safety & Recruitment Services'
        }.get(self.service_type, 'Unknown')

    @classmethod
    def get_stats_for_user(cls, user_id):
        """Get company statistics for a user"""
        stats = {
            'total': cls.query.filter_by(user_id=user_id).count(),
            'by_status': {}
        }
        
        # Get counts by status
        status_counts = db.session.query(
            cls.status, 
            db.func.count(cls.id)
        ).filter_by(user_id=user_id).group_by(cls.status).all()
        
        for status, count in status_counts:
            stats['by_status'][status] = count
            
        return stats

    def update_service_status(self, service, status):
        """Update status for a specific service"""
        if service == 'safety':
            self.safety_status = status
        elif service == 'recruitment':
            self.recruitment_status = status
        db.session.commit()

    def add_recruitment_request(self, data):
        """Add a new recruitment request with simplified structure"""
        if not self.recruitment_requests:
            self.recruitment_requests = {'requests': []}
        
        request = {
            'id': len(self.recruitment_requests['requests']),
            'role': data['position'],
            'charge': float(data.get('charge', 0)),
            'notes': data.get('notes', ''),
            'status': data.get('status', 'new'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Create a completely new dictionary to ensure SQLAlchemy detects the change
        new_requests = {'requests': list(self.recruitment_requests['requests'])}
        new_requests['requests'].append(request)
        
        # Force SQLAlchemy to detect the change
        self.recruitment_requests = None
        db.session.flush()
        self.recruitment_requests = new_requests
        
        db.session.add(self)
        db.session.commit()
        return len(new_requests['requests']) - 1

    def update_recruitment_request(self, request_index, updates):
        """Update a recruitment request with simplified structure"""
        if not self.recruitment_requests or 'requests' not in self.recruitment_requests:
            raise ValueError("No recruitment requests found")
            
        if request_index >= len(self.recruitment_requests['requests']):
            raise ValueError("Invalid request index")
            
        # Create a completely new dictionary to ensure SQLAlchemy detects the change
        new_requests = {'requests': list(self.recruitment_requests['requests'])}
        request = dict(new_requests['requests'][request_index])
        
        # Update fields
        if 'position' in updates:
            request['role'] = updates['position']
        if 'charge' in updates:
            request['charge'] = float(updates['charge'])
        if 'notes' in updates:
            request['notes'] = updates['notes']
        if 'status' in updates:
            request['status'] = updates['status']
        
        request['updated_at'] = datetime.utcnow().isoformat()
        new_requests['requests'][request_index] = request
        
        # Force SQLAlchemy to detect the change
        self.recruitment_requests = None
        db.session.flush()
        self.recruitment_requests = new_requests
        
        db.session.add(self)
        db.session.commit()
        return request

    def delete_recruitment_request(self, request_index):
        """Delete a recruitment request"""
        if not self.recruitment_requests or 'requests' not in self.recruitment_requests:
            raise ValueError("No recruitment requests found")
            
        if request_index >= len(self.recruitment_requests['requests']):
            raise ValueError("Invalid request index")
            
        # Create a completely new dictionary to ensure SQLAlchemy detects the change
        new_requests = {'requests': list(self.recruitment_requests['requests'])}
        new_requests['requests'].pop(request_index)
        
        # Update indices for remaining requests
        for i, request in enumerate(new_requests['requests']):
            request['id'] = i
            
        # Force SQLAlchemy to detect the change
        self.recruitment_requests = None
        db.session.flush()
        self.recruitment_requests = new_requests
        
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        """Convert company to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'contact_name': self.contact_name,
            'email': self.email,
            'phone': self.phone,
            'service_type': self.service_type,
            'service_display': self.service_display,
            'status': self.status,
            'status_display': self.status_display,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'preferred_contact_time': self.preferred_contact_time,
            'additional_info': self.additional_info,
            'metadata': self.company_metadata,
            'safety_status': self.safety_status,
            'recruitment_status': self.recruitment_status,
            'recruitment_requests': self.recruitment_requests
        }

    def save(self):
        """Save changes to the database"""
        self.updated_at = datetime.utcnow()
        db.session.add(self)
        db.session.commit()
