from datetime import datetime
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
    vehicle_id = db.Column(db.BigInteger, db.ForeignKey('samsara_vehicles.id'), nullable=False)
    alert_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    priority = db.Column(db.String(20), nullable=False, default='medium')  # high, medium, low
    description = db.Column(db.Text)
    data = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, nullable=False)
    resolution = db.Column(db.Text)  # Store resolution details
    resolved_at = db.Column(db.DateTime)  # When the alert was resolved
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Who resolved it
    tags = db.Column(db.JSON)  # Store tags for better categorization
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('samsara_clients.id'), nullable=False)

    # Relationships
    vehicle = db.relationship('SamsaraVehicle', back_populates='alerts')
    assignments = db.relationship('SamsaraAlertAssignment', back_populates='alert', lazy=True)
    client = db.relationship('SamsaraClient', backref='alerts')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_alerts')

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