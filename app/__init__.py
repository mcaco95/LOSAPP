from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configure ProxyFix for handling proxy headers (needed for Ngrok)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        # Import models and routes
        from .models import user, link_tracking
        from .routes import auth
        from .routes import main
        from .routes import referrals
        from .routes.users import users
        
        # Register blueprints
        app.register_blueprint(auth.bp)
        app.register_blueprint(main.main)
        app.register_blueprint(users)
        app.register_blueprint(referrals.bp)

        # Add CLI commands
        @app.cli.command('setup-admin')
        def setup_admin():
            """Set up the admin user."""
            from .models.user import User
            admin_email = 'simon@logisticsonesource.com'
            admin = User.query.filter_by(email=admin_email).first()
            
            if admin:
                admin.is_admin = True
                print(f'Updated existing user {admin_email} to admin')
            else:
                admin = User(
                    email=admin_email,
                    name='Simon',
                    is_admin=True
                )
                admin.set_password('admin123')  # Set a temporary password
                db.session.add(admin)
                print(f'Created new admin user {admin_email} with password: admin123')
            
            db.session.commit()
            print('Admin setup complete')

        return app
