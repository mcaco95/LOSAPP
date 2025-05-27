from datetime import datetime, timezone
from app import db

class SamsaraClient(db.Model):
    """Model for storing Samsara client/organization information"""
    __tablename__ = 'samsara_clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    org_id = db.Column(db.BigInteger, unique=True, nullable=False)  # Samsara's orgId
    api_key = db.Column(db.String(100), nullable=False)
    webhook_id = db.Column(db.String(100))  # Optional, for reference
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # New field and relationship
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)  # Nullable for now
    company = db.relationship('Company', backref=db.backref('samsara_clients', lazy='dynamic'))

    def __repr__(self):
        return f'<SamsaraClient {self.name} ({self.org_id})>'

class SamsaraVehicle(db.Model):
    """Model for storing Samsara vehicles"""
    __tablename__ = 'samsara_vehicles'

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.BigInteger, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    serial = db.Column(db.String(50))
    license_plate = db.Column(db.String(20))
    vin = db.Column(db.String(17))
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.Integer)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    external_ids = db.Column(db.JSON)
    data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alerts = db.relationship('SamsaraAlert', back_populates='vehicle', lazy=True)
    locations = db.relationship('SamsaraVehicleLocation', back_populates='vehicle', lazy=True)

    def __repr__(self):
        return f'<SamsaraVehicle {self.name} ({self.vehicle_id})>'

class SamsaraDriver(db.Model):
    """Model for storing Samsara drivers"""
    __tablename__ = 'samsara_drivers'

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.BigInteger, unique=True, nullable=False)  # Samsara's driver ID
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    license_number = db.Column(db.String(50))
    license_state = db.Column(db.String(5))
    license_class = db.Column(db.String(10))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    external_ids = db.Column(db.JSON)
    data = db.Column(db.JSON)  # Store full driver data from Samsara
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = db.relationship('Company', backref=db.backref('samsara_drivers', lazy='dynamic'))

    def __repr__(self):
        return f'<SamsaraDriver {self.name} ({self.driver_id})>'

    @property
    def display_name(self):
        """Get display name with ID for dropdowns"""
        return f"{self.name} (ID: {self.driver_id})"

class SamsaraWebhookEvent(db.Model):
    """Model for storing raw webhook events from Samsara"""
    __tablename__ = 'samsara_webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    event_data = db.Column(db.JSON)
    webhook_id = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, nullable=False)
    processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('samsara_clients.id'), nullable=False)

    # Relationships
    client = db.relationship('SamsaraClient', backref='webhook_events')

    def __repr__(self):
        return f'<SamsaraWebhookEvent {self.event_type} ({self.timestamp})>'

class SamsaraVehicleLocation(db.Model):
    """Model for storing Samsara vehicle locations"""
    __tablename__ = 'samsara_vehicle_locations'

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.BigInteger, db.ForeignKey('samsara_vehicles.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float)
    heading = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    vehicle = db.relationship('SamsaraVehicle', back_populates='locations')

    def __repr__(self):
        return f'<SamsaraVehicleLocation for vehicle {self.vehicle_id}>'

class SamsaraAlert(db.Model):
    """Model for storing Samsara alerts"""
    __tablename__ = 'samsara_alerts'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(100), unique=True, nullable=False)
    vehicle_id = db.Column(db.BigInteger, db.ForeignKey('samsara_vehicles.id'), nullable=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('samsara_drivers.id'), nullable=True)
    alert_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='unassigned')
    priority = db.Column(db.String(20), nullable=False, default='medium')  # high, medium, low
    description = db.Column(db.Text)
    data = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, nullable=False)
    resolution = db.Column(db.Text)  # Store final resolution details (deprecated - use activities)
    resolved_at = db.Column(db.DateTime)  # When the alert was resolved
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Who resolved it
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    tags = db.Column(db.JSON)  # Store tags for better categorization
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('samsara_clients.id'), nullable=False)

    # Relationships
    vehicle = db.relationship('SamsaraVehicle', back_populates='alerts')
    driver = db.relationship('SamsaraDriver', backref=db.backref('alerts', lazy='dynamic'))
    assignments = db.relationship('SamsaraAlertAssignment', back_populates='alert', lazy=True)
    activities = db.relationship('SamsaraAlertActivity', back_populates='alert', lazy=True, order_by='SamsaraAlertActivity.created_at.desc()')
    client = db.relationship('SamsaraClient', backref='alerts')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_alerts')
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id], backref='current_assigned_alerts')

    def __repr__(self):
        return f'<SamsaraAlert {self.alert_type} for vehicle {self.vehicle_id}>'

    @property
    def current_assignment(self):
        """Get the current active assignment for this alert"""
        return (SamsaraAlertAssignment.query
                .filter_by(alert_id=self.id)
                .order_by(SamsaraAlertAssignment.created_at.desc())
                .first())

    @property
    def resolution_time(self):
        """Calculate the time taken to resolve the alert"""
        if self.resolved_at:
            return self.resolved_at - self.timestamp
        return None

    def add_activity(self, activity_type, description, user_id=None, old_value=None, new_value=None, notes=None, metadata=None):
        """Add an activity record for this alert"""
        activity = SamsaraAlertActivity(
            alert_id=self.id,
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            old_value=old_value,
            new_value=new_value,
            notes=notes,
            activity_metadata=metadata,
            created_at=datetime.utcnow()
        )
        db.session.add(activity)
        return activity

class SamsaraAlertActivity(db.Model):
    """Model for tracking all activities/changes on alerts"""
    __tablename__ = 'samsara_alert_activities'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey('samsara_alerts.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # status_change, assignment, severity_change, note, resolution, etc.
    description = db.Column(db.Text, nullable=False)  # Human readable description
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Who made the change
    old_value = db.Column(db.String(255))  # Previous value (for changes)
    new_value = db.Column(db.String(255))  # New value (for changes)
    notes = db.Column(db.Text)  # Additional notes/comments
    activity_metadata = db.Column(db.JSON)  # Additional structured data
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    alert = db.relationship('SamsaraAlert', back_populates='activities')
    user = db.relationship('User', backref='alert_activities')

    def __repr__(self):
        return f'<SamsaraAlertActivity {self.activity_type} for alert {self.alert_id}>'

    @property
    def formatted_timestamp(self):
        """Get formatted timestamp with timezone"""
        return self.created_at.replace(tzinfo=timezone.utc).isoformat()

class SamsaraAlertAssignment(db.Model):
    """Model for tracking alert assignments"""
    __tablename__ = 'samsara_alert_assignments'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey('samsara_alerts.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # assigned, in_progress, resolved, escalated
    priority = db.Column(db.String(20), nullable=False, default='medium')  # high, medium, low
    notes = db.Column(db.Text)
    due_date = db.Column(db.DateTime)  # Optional due date for resolution
    resolution = db.Column(db.Text)  # Resolution notes
    resolution_time = db.Column(db.DateTime)  # When the assignment was resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alert = db.relationship('SamsaraAlert', back_populates='assignments')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_alerts')
    assigner = db.relationship('User', foreign_keys=[assigned_by], backref='assigned_alerts_by_me')

    def __repr__(self):
        return f'<SamsaraAlertAssignment Alert {self.alert_id} -> User {self.assigned_to}>'

    @property
    def is_overdue(self):
        """Check if the assignment is overdue"""
        return self.due_date and datetime.utcnow() > self.due_date

    @property
    def time_to_resolution(self):
        """Calculate time taken to resolve the assignment"""
        if self.resolution_time:
            return self.resolution_time - self.created_at
        return None

class DOTInfraction(db.Model):
    """Model for storing DOT inspection infractions"""
    __tablename__ = 'dot_infractions'

    id = db.Column(db.Integer, primary_key=True)
    
    # Company relationship (NEW)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    
    # Carrier Information
    carrier_name = db.Column(db.String(200))
    carrier_address = db.Column(db.Text)
    us_dot = db.Column(db.String(20))
    mc_number = db.Column(db.String(20))
    state_id = db.Column(db.String(20))
    
    # Report Information
    report_number = db.Column(db.String(50), unique=True, nullable=False)
    report_state = db.Column(db.String(5))
    inspection_state = db.Column(db.String(5))
    inspection_date = db.Column(db.Date, nullable=False)
    start_end_time = db.Column(db.String(20))
    inspection_level = db.Column(db.String(50))
    inspection_facility = db.Column(db.String(100))
    post_crash = db.Column(db.String(10))
    inspection_location = db.Column(db.String(200))
    hazmat_placard_required = db.Column(db.String(10))
    inspection_county = db.Column(db.String(100))
    
    # Driver Information - Updated to use relationship
    primary_driver_id = db.Column(db.Integer, db.ForeignKey('samsara_drivers.id'), nullable=True)
    driver_name = db.Column(db.String(100))  # Keep as fallback for manual entry
    driver_age = db.Column(db.Integer)
    driver_license_state = db.Column(db.String(5))
    
    # Shipper Information
    shipper_info_available = db.Column(db.Boolean, default=False)
    
    # Vehicle Information - Updated to support both relationships and manual data
    linked_vehicles = db.Column(db.JSON)  # Store array of linked vehicle IDs
    vehicles_data = db.Column(db.JSON)  # Store array of manual vehicle info (fallback)
    
    # File attachments
    pdf_file_path = db.Column(db.String(500))  # Path to uploaded PDF
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    company = db.relationship('Company', backref=db.backref('dot_infractions', lazy='dynamic'))
    primary_driver = db.relationship('SamsaraDriver', backref=db.backref('primary_infractions', lazy='dynamic'))
    violations = db.relationship('DOTViolation', back_populates='infraction', lazy=True, cascade='all, delete-orphan')
    linked_alerts = db.relationship('DOTInfractionAlert', back_populates='infraction', lazy=True)
    creator = db.relationship('User', backref='created_infractions')

    def __repr__(self):
        return f'<DOTInfraction {self.report_number} - {self.carrier_name}>'

    @property
    def violation_count(self):
        """Get total number of violations"""
        return len(self.violations)

    @property
    def severity_summary(self):
        """Get summary of violation severities"""
        if not self.violations:
            return {}
        
        summary = {}
        for violation in self.violations:
            severity = violation.violation_category or 'Unknown'
            summary[severity] = summary.get(severity, 0) + 1
        return summary

    @property
    def linked_vehicle_objects(self):
        """Get actual SamsaraVehicle objects for linked vehicles"""
        if not self.linked_vehicles:
            return []
        
        from app.models.samsara import SamsaraVehicle
        return SamsaraVehicle.query.filter(SamsaraVehicle.id.in_(self.linked_vehicles)).all()

    @property
    def driver_display_name(self):
        """Get driver name for display"""
        if self.primary_driver:
            return self.primary_driver.name
        return self.driver_name or 'Unknown Driver'

class DOTViolation(db.Model):
    """Model for storing individual DOT violations within an infraction"""
    __tablename__ = 'dot_violations'

    id = db.Column(db.Integer, primary_key=True)
    infraction_id = db.Column(db.Integer, db.ForeignKey('dot_infractions.id'), nullable=False)
    
    # Violation Details
    unit_type = db.Column(db.String(20))  # D (Driver), N (Vehicle), etc.
    oos_indicator = db.Column(db.String(5))  # Out of Service indicator
    section_code = db.Column(db.String(20), nullable=False)  # e.g., "393.55(f)"
    violation_description = db.Column(db.Text, nullable=False)
    violation_category = db.Column(db.String(50))  # BASIC, Weight, Citation, etc.
    emergency_equipment = db.Column(db.String(10))
    citation = db.Column(db.String(20))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    infraction = db.relationship('DOTInfraction', back_populates='violations')

    def __repr__(self):
        return f'<DOTViolation {self.section_code} - {self.violation_category}>'

class DOTInfractionAlert(db.Model):
    """Model for linking DOT infractions to Samsara alerts"""
    __tablename__ = 'dot_infraction_alerts'

    id = db.Column(db.Integer, primary_key=True)
    infraction_id = db.Column(db.Integer, db.ForeignKey('dot_infractions.id'), nullable=False)
    alert_id = db.Column(db.Integer, db.ForeignKey('samsara_alerts.id'), nullable=False)
    
    # Link metadata
    linked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    link_reason = db.Column(db.Text)  # Why this alert was linked to this infraction
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    infraction = db.relationship('DOTInfraction', back_populates='linked_alerts')
    alert = db.relationship('SamsaraAlert', backref='linked_infractions')
    linker = db.relationship('User', backref='linked_infraction_alerts')

    def __repr__(self):
        return f'<DOTInfractionAlert Infraction {self.infraction_id} -> Alert {self.alert_id}>' 