from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Clear all tables in the correct order to avoid foreign key conflicts
    db.session.execute(text('TRUNCATE TABLE point_transaction CASCADE'))
    db.session.execute(text('TRUNCATE TABLE user_reward CASCADE'))
    db.session.execute(text('TRUNCATE TABLE reward CASCADE'))
    db.session.execute(text('TRUNCATE TABLE link_click CASCADE'))
    db.session.execute(text('TRUNCATE TABLE company CASCADE'))
    db.session.execute(text('TRUNCATE TABLE point_config CASCADE'))
    db.session.execute(text('TRUNCATE TABLE "user" CASCADE'))
    
    # Commit all changes
    db.session.commit()
    
    print("Database has been cleared successfully!")
    print("Next steps:")
    print("1. Create your admin user (simon@logisticsonesource.com)")
    print("2. Initialize the points system")
    print("3. Start testing with a fresh state") 