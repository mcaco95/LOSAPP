from flask import Flask
from app import db
from app.models.user import User

app = Flask(__name__)
app.config.from_object('app.config.Config')
db.init_app(app)

with app.app_context():
    admin_email = 'simon@logisticsonesource.com'
    admin = User.query.filter_by(email=admin_email).first()
    
    if admin:
        # Update the password hash directly in the database
        admin.password_hash = 'pbkdf2:sha256:600000$dummysalt$6b4e903b2e028dfd1ce748388a262e4bb6c0e2768b42f46c8d069dcf936efb99'  # This is 'admin123'
        db.session.commit()
        print(f'Reset password for admin user {admin_email} to: admin123')
    else:
        print(f'Admin user {admin_email} not found') 