# Logistics One Source - Referral System Architecture

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [Database Architecture](#6-database-architecture)
7. [Development Guidelines](#7-development-guidelines)
8. [Deployment & DevOps](#8-deployment--devops)

## 1. System Overview

### Purpose
The Logistics One Source Referral System is designed to be a scalable platform that enables:
- Generation and management of unique referral codes
- Comprehensive click tracking and analytics
- Commission calculation and distribution
- Performance dashboards and reporting
- Fraud detection and prevention

### Key Features
- User authentication and role-based access control
- Referral link generation with unique tracking
- Geographic and device-based analytics
- Commission management and distribution
- Administrative dashboard and controls
- Fraud detection system
- Performance metrics and reporting

### Architecture Goals
- Scalability to handle millions of referral records
- High performance with optimized database queries
- Maintainable and well-documented codebase
- Secure handling of user and financial data
- Easy integration with future AI and analytics modules

## 2. Technology Stack

### Core Dependencies

#### Backend Framework
```plaintext
Flask 3.0.0
Flask-SQLAlchemy 3.1.1
Flask-Login 0.6.3
Flask-Mail 0.9.1
Flask-Migrate 4.0.5
Werkzeug 3.0.1
```

#### Database
```plaintext
PostgreSQL (Primary Database)
SQLAlchemy (ORM)
Alembic (Migrations)
```

#### Frontend
```plaintext
Volt 5 Bootstrap Admin Dashboard
Bootstrap 5.0.2
Chart.js (Analytics visualization)
SweetAlert2 (Notifications)
Moment.js (Date handling)
```

#### Additional Tools
```plaintext
python-dotenv (Environment management)
geoip2 (Geographic tracking)
user-agents (Device detection)
```

### Required New Dependencies

#### Backend Extensions
```plaintext
psycopg2-binary==2.9.9    # PostgreSQL adapter
Flask-Caching==2.1.0      # API response caching
Flask-Limiter==3.5.0      # Rate limiting
Flask-Cors==4.0.0         # CORS support
marshmallow==3.20.1       # Schema validation
celery==5.3.6            # Async task processing
redis==5.0.1             # Caching & message queue
pytest==7.4.3            # Testing framework
black==23.11.0           # Code formatting
flake8==6.1.0            # Code linting
```

#### Frontend Enhancements
```plaintext
DataTables 1.13.8         # Enhanced table functionality
Select2 4.1.0            # Enhanced dropdowns
ApexCharts 3.45.1        # Advanced charting
```

## 3. Project Structure

```plaintext
app/
├── api/                    # API endpoints
│   ├── v1/
│   │   ├── routes/        # API route handlers
│   │   │   ├── referrals.py
│   │   │   ├── analytics.py
│   │   │   └── admin.py
│   │   └── schemas/       # Request/response schemas
│   │       ├── referral.py
│   │       └── user.py
│   └── common/            # Shared API utilities
│       ├── auth.py
│       └── responses.py
├── models/                 # Database models
│   ├── user.py            # User model
│   ├── link_tracking.py   # Click tracking
│   ├── commission.py      # Commission management
│   └── reward.py          # Reward system
├── services/              # Business logic
│   ├── referral/          # Referral management
│   │   ├── service.py
│   │   └── validators.py
│   ├── analytics/         # Analytics processing
│   │   ├── service.py
│   │   └── calculators.py
│   ├── fraud_detection/   # Fraud prevention
│   │   ├── service.py
│   │   └── rules.py
│   └── reward/            # Reward management
│       ├── service.py
│       └── calculators.py
├── tasks/                 # Async tasks
│   ├── __init__.py
│   ├── email.py          # Email notifications
│   └── analytics.py      # Background analytics
├── templates/             # Volt 5 templates
│   ├── auth/             # Authentication pages
│   ├── dashboard/        # Dashboard views
│   ├── referrals/        # Referral management
│   └── partials/         # Reusable components
├── static/               # Static assets
│   ├── css/             # Stylesheets
│   │   └── volt.css     # Volt 5 styles
│   ├── js/              # JavaScript
│   │   └── volt.js      # Volt 5 scripts
│   └── img/             # Images and icons
└── utils/               # Helper functions
    ├── decorators.py    # Custom decorators
    ├── validators.py    # Input validation
    └── helpers.py       # Utility functions
```

## 4. Frontend Architecture

### Volt 5 Integration

#### Template Structure
```html
<!-- Base Template (base.html) -->
<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Core Volt CSS -->
    <link href="{{ url_for('static', filename='css/volt.css') }}" rel="stylesheet">
</head>
<body>
    {% include 'partials/sidenav.html' %}
    <main class="content">
        {% include 'partials/topbar.html' %}
        {% block content %}{% endblock %}
        {% include 'partials/footer.html' %}
    </main>
    <!-- Volt JS -->
    <script src="{{ url_for('static', filename='js/volt.js') }}"></script>
</body>
</html>
```

#### Core Components

1. Navigation
```html
<!-- Sidebar Navigation -->
<nav class="navbar navbar-dark navbar-theme-primary">
    <!-- Use Volt's built-in navigation components -->
</nav>

<!-- Topbar -->
<nav class="navbar navbar-top navbar-expand">
    <!-- Use Volt's built-in topbar components -->
</nav>
```

2. Cards and Panels
```html
<!-- Standard Card -->
<div class="card border-0 shadow">
    <div class="card-header">
        <h5 class="mb-0">Title</h5>
    </div>
    <div class="card-body">
        <!-- Content -->
    </div>
</div>
```

3. Data Tables
```html
<!-- Enhanced Table -->
<div class="table-responsive">
    <table class="table table-centered table-nowrap mb-0 rounded">
        <!-- Table content -->
    </table>
</div>
```

### JavaScript Dependencies

```html
<!-- Core Dependencies -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>

<!-- Charts -->
<script src="https://cdn.jsdelivr.net/npm/chartist@0.11.4/dist/chartist.min.js"></script>

<!-- UI Enhancements -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11.0.18/dist/sweetalert2.all.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/notyf@3.10.0/notyf.min.js"></script>
```

### Best Practices

1. Component Usage
- Utilize Volt's built-in components whenever possible
- Maintain consistent styling with Volt's design system
- Follow Volt's grid system for layouts

2. Custom Styling
- Add custom styles in separate CSS files
- Use Volt's utility classes for common adjustments
- Maintain Volt's color scheme and variables

3. JavaScript Integration
- Initialize Volt components properly
- Use event delegation for dynamic content
- Follow Volt's plugin initialization patterns

## 5. Backend Architecture

### Service Layer Implementation

```python
# services/referral/service.py
class ReferralService:
    """Handles referral link generation and tracking"""
    
    def generate_link(self, user_id: int) -> str:
        """Generate unique referral link for user"""
        pass

    def track_click(self, link_id: int, request_data: dict) -> None:
        """Track click with geographic and device data"""
        pass

    def calculate_commission(self, link_id: int) -> Decimal:
        """Calculate commission for referral"""
        pass

# services/analytics/service.py
class AnalyticsService:
    """Handles analytics and reporting"""
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get user performance metrics"""
        pass

    def generate_reports(self) -> None:
        """Generate periodic reports"""
        pass
```

### API Structure

```python
# api/v1/routes/referral.py
@bp.route('/referral/generate', methods=['POST'])
@login_required
@validate_schema(ReferralSchema)
def generate_referral():
    """Generate new referral link"""
    return jsonify(
        referral_service.generate_link(current_user.id)
    )

# api/v1/schemas/referral.py
class ReferralSchema(Schema):
    """Referral data validation schema"""
    id = fields.Int(required=True)
    code = fields.Str(required=True)
    created_at = fields.DateTime(required=True)
```

### Background Tasks

```python
# tasks/analytics.py
@celery.task
def update_analytics():
    """Update analytics data periodically"""
    analytics_service.update_metrics()

# tasks/email.py
@celery.task
def send_performance_report(user_id: int):
    """Send weekly performance report"""
    pass
```

## 6. Database Architecture

### PostgreSQL Schema

```sql
-- Users and Authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128),
    name VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT FALSE,
    unique_link VARCHAR(100) UNIQUE,
    commission_rate DECIMAL(5,2),
    status VARCHAR(20)
);

-- Referral Tracking
CREATE TABLE referral_links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    code VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR(20),
    metadata JSONB
);

-- Click Tracking
CREATE TABLE link_clicks (
    id SERIAL PRIMARY KEY,
    referral_link_id INTEGER REFERENCES referral_links(id),
    visitor_ip VARCHAR(45),
    user_agent VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    country VARCHAR(2),
    city VARCHAR(100),
    region VARCHAR(100),
    device_type VARCHAR(20),
    session_id UUID,
    metadata JSONB
);

-- Commissions
CREATE TABLE commissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    referral_link_id INTEGER REFERENCES referral_links(id),
    amount DECIMAL(10,2),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    metadata JSONB
);

-- Rewards
CREATE TABLE rewards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(50),
    points INTEGER,
    achieved_at TIMESTAMP,
    metadata JSONB
);

-- Audit Logging
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    action VARCHAR(50),
    actor_id INTEGER REFERENCES users(id),
    changes JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Model Implementation

```python
# models/commission.py
class Commission(db.Model):
    """Commission tracking model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.JSON)

# models/reward.py
class Reward(db.Model):
    """User rewards model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.String(50))
    points = db.Column(db.Integer)
    achieved_at = db.Column(db.DateTime)
```

## 7. Development Guidelines

### Code Standards

1. Python Style Guide
- Follow PEP 8 conventions
- Use type hints for function arguments and returns
- Document classes and functions with docstrings
- Maximum line length of 88 characters (Black formatter)

2. Git Workflow
- Feature branches named as `feature/description`
- Pull request reviews required
- Commit messages follow conventional commits
- Version tags follow semantic versioning

3. Testing Requirements
- Unit tests for all services
- Integration tests for APIs
- Minimum 80% code coverage
- Test database fixtures provided

### Documentation

1. API Documentation
- OpenAPI/Swagger specifications
- Example requests and responses
- Authentication details
- Rate limiting information

2. Code Documentation
- Module-level documentation
- Function documentation with parameters
- Complex logic explanation
- Architecture decision records

## 8. Deployment & DevOps

### Environment Configuration

```plaintext
# .env.example
DATABASE_URL=postgresql://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-password
```

### Deployment Process

1. Database Migration
```bash
# Generate migration
flask db migrate -m "description"

# Apply migration
flask db upgrade
```

2. Asset Compilation
```bash
# Install dependencies
npm install

# Build assets
npm run build
```

3. Service Configuration
```ini
# supervisor configuration
[program:celery]
command=celery -A app.celery worker
directory=/path/to/app
user=www-data
autostart=true
autorestart=true
```

### Monitoring & Logging

1. Application Monitoring
- Error tracking with Sentry
- Performance monitoring with NewRelic
- Custom metrics with StatsD

2. Log Management
- Structured logging with JSON format
- Log rotation configuration
- Centralized log collection

### Backup Strategy

1. Database Backups
- Daily full backups
- Hourly incremental backups
- Point-in-time recovery capability

2. Application Backups
- Configuration files
- Static assets
- User uploads

### Security Measures

1. Application Security
- Regular dependency updates
- Security headers configuration
- CSRF protection
- XSS prevention

2. Infrastructure Security
- Firewall configuration
- SSL/TLS setup
- Regular security audits
- Access control policies

---

This architecture document serves as the primary reference for development and maintenance of the Logistics One Source Referral System. It should be updated as the system evolves and new architectural decisions are made.

For questions or clarifications, please contact the architecture team or create an issue in the project repository.
