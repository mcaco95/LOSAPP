from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()
migrate = Migrate()
csrf = CSRFProtect()

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
    csrf.init_app(app)
    
    # Request cleanup
    @app.teardown_request
    def cleanup_request(exception=None):
        if hasattr(g, 'db_session'):
            g.db_session.remove()
        db.session.remove()
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()
    
    with app.app_context():
        # Import models and routes
        from .models import user, link_tracking, company, point_config, reward, oauth, commission_partner, commission, commission_settings, samsara
        from .routes import main as main_routes
        from .routes import auth as auth_routes
        from .routes import users as users_routes
        from .routes import commission as commission_routes
        from .routes import referrals as referrals_routes
        from .routes import operations as operations_routes
        from .routes import samsara
        from .api.v1 import bp as api_v1_bp
        # Import the new CRM blueprint correctly
        from .routes import crm
        
        # Initialize OAuth
        from .oauth import init_oauth
        init_oauth(app)
        
        # Just set admin flag if needed
        try:
            from .models.user import User
            admin = User.query.filter_by(email='simon@logisticsonesource.com').first()
            if admin and not admin.is_admin:
                admin.is_admin = True
                db.session.commit()
        except Exception as e:
            print(f"Couldn't set admin flag: {str(e)}")
        
        # Register blueprints
        app.register_blueprint(main_routes.main)
        app.register_blueprint(auth_routes.bp)
        app.register_blueprint(users_routes.users)
        app.register_blueprint(commission_routes.bp)
        app.register_blueprint(referrals_routes.bp)
        app.register_blueprint(operations_routes.bp)
        app.register_blueprint(samsara.bp)
        app.register_blueprint(api_v1_bp)  # Register the API blueprint
        # Import the webhook blueprint
        try:
            # Check if webhook blueprint is imported and register it
            from .routes import webhook
            app.register_blueprint(webhook.bp)
            app.logger.info("Registered webhook blueprint.")
        except ImportError:
            app.logger.warning("Webhook blueprint not found or failed to import.")
        except AttributeError:
            app.logger.warning("Webhook module found, but no 'bp' attribute.")
       
        # Register the CRM blueprint
        app.register_blueprint(crm.crm_bp)

        # Exempt Samsara webhook routes from CSRF protection
        csrf.exempt(samsara.webhook)
        csrf.exempt(samsara.test_webhook)
        csrf.exempt(samsara.update_client)
        csrf.exempt(samsara.create_client)
        
        # Add context processors
        @app.context_processor
        def utility_processor():
            from flask_login import current_user
            from .models.commission_partner import CommissionPartner
            
            def is_commission_partner():
                if not current_user.is_authenticated:
                    return False
                return CommissionPartner.query.filter_by(user_id=current_user.id).first() is not None
            
            return {
                'is_commission_partner': is_commission_partner
            }

        # Add CLI commands
        @app.cli.command('setup-admin')
        def setup_admin():
            """Set up the admin user."""
            try:
                from .models.user import User
                print("Starting admin setup...")
                admin_email = 'simon@logisticsonesource.com'
                admin = User.query.filter_by(email=admin_email).first()
                
                if admin:
                    print(f"Found existing user {admin_email}")
                    admin.is_admin = True
                    db.session.commit()
                    print(f'Updated existing user {admin_email} to admin')
                else:
                    print(f"Creating new admin user {admin_email}")
                    admin = User(
                        email=admin_email,
                        name='Simon',
                        is_admin=True
                    )
                    admin.set_password('admin123')  # Set a temporary password
                    db.session.add(admin)
                    db.session.commit()
                    print(f'Created new admin user {admin_email} with password: admin123')
                
                # Verify the change
                admin = User.query.filter_by(email=admin_email).first()
                if admin and admin.is_admin:
                    print("Admin setup verified successfully")
                else:
                    print("Warning: Admin setup could not be verified")
                
            except Exception as e:
                print(f"Error in admin setup: {str(e)}")
                raise
            
            print('Admin setup complete')

        @app.cli.command('init-points-rewards')
        def init_points_rewards():
            """Initialize points and rewards system."""
            from .services.points import PointService
            from .services.reward import RewardService
            
            print('Initializing points system...')
            if PointService.initialize_point_system():
                print('Points system initialized successfully')
            else:
                print('Error initializing points system')
            
            print('Initializing rewards system...')
            if RewardService.initialize_reward_system():
                print('Rewards system initialized successfully')
            else:
                print('Error initializing rewards system')
            
            print('Points and rewards system initialization complete')

        @app.cli.command('reset-admin-password')
        def reset_admin_password():
            """Reset the admin user's password."""
            from .models.user import User
            admin_email = 'simon@logisticsonesource.com'
            admin = User.query.filter_by(email=admin_email).first()
            
            if admin:
                admin.set_password('admin123')  # Temporary password
                db.session.commit()
                print(f'Reset password for admin user {admin_email} to: admin123')
            else:
                print(f'Admin user {admin_email} not found')

        # Set up logging
        if not app.debug and not app.testing:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/app.log',
                                             maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

            app.logger.setLevel(logging.INFO)
            app.logger.info('Application startup')

        return app
