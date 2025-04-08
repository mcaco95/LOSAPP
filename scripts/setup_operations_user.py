from app import create_app, db
from app.models.user import User
from app.models.operations_user import OperationsUser
from werkzeug.security import generate_password_hash

def setup_operations_user(email, name, password, phone_number=None, extension=None):
    """
    Set up a new operations user with the given details.
    If the user already exists, it will be updated with operations role.
    """
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Create new user
            user = User(
                email=email,
                name=name,
                is_admin=False  # Operations users don't need admin privileges by default
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # Get the user ID
        
        # Check if operations profile exists
        ops_user = OperationsUser.query.filter_by(user_id=user.id).first()
        
        if not ops_user:
            # Create operations profile
            ops_user = OperationsUser(
                user_id=user.id,
                phone_number=phone_number,
                extension=extension,
                role='operator'
            )
            db.session.add(ops_user)
        else:
            # Update existing operations profile
            ops_user.phone_number = phone_number
            ops_user.extension = extension
        
        try:
            db.session.commit()
            print(f"Successfully set up operations user: {email}")
            print(f"User ID: {user.id}")
            print(f"Operations Profile ID: {ops_user.id}")
            print(f"Role: {ops_user.role}")
            if phone_number:
                print(f"Phone Number: {ops_user.phone_number}")
            if extension:
                print(f"Extension: {ops_user.extension}")
        except Exception as e:
            db.session.rollback()
            print(f"Error setting up operations user: {str(e)}")
            raise

if __name__ == "__main__":
    # Example usage
    setup_operations_user(
        email="operations@logisticsonesource.com",
        name="Operations Team",
        password="ChangeMe123!",  # Remember to change this
        phone_number="+1234567890",  # Replace with actual number
        extension="1001"
    ) 