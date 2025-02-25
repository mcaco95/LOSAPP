from app import create_app, db
from app.models.user import User

app = create_app()
with app.app_context():
    # Get the user
    user = User.query.filter_by(email='simon@logisticsonesource.com').first()
    
    if not user:
        print("User not found. Creating admin user...")
        user = User(
            email='simon@logisticsonesource.com',
            name='Simon',
            is_admin=True
        )
        user.set_password('admin123')
        db.session.add(user)
    else:
        print(f"Found user: {user.email}")
        print(f"Current admin status: {user.is_admin}")
        user.is_admin = True
        print("Setting admin status to True")
    
    db.session.commit()
    print("Changes committed to database")
    
    # Verify the changes
    user = User.query.filter_by(email='simon@logisticsonesource.com').first()
    print(f"\nVerification:")
    print(f"User exists: {user is not None}")
    print(f"Is admin: {user.is_admin}") 