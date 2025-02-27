from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

app = create_app()

def reset_user_password(email, new_password):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(new_password, method='sha256')
            db.session.commit()
            print(f"Password updated successfully for {email}")
        else:
            print(f"User with email {email} not found")

if __name__ == "__main__":
    email = input("Enter email: ")
    password = input("Enter new password: ")
    reset_user_password(email, password) 