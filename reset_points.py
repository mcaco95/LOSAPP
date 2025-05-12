from app import create_app, db
from sqlalchemy import text
from app.models.user import User

app = create_app()
with app.app_context():
    # 1. Clear the point_transaction table
    db.session.execute(text('TRUNCATE TABLE point_transaction CASCADE'))
    
    # 2. Reset all users' points and points_history
    users = User.query.all()
    for user in users:
        user.points = 0
        user.points_history = {'transactions': []}
    
    # 3. Commit all changes
    db.session.commit()
    
    print("Points have been reset successfully!")
    print("You can now test the system by:")
    print("1. Creating new companies (adds points for lead generation)")
    print("2. Updating company statuses (adds points for status changes)")
    print("3. Getting clicks on referral links (adds points for unique clicks)") 