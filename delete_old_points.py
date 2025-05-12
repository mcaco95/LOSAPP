from app import create_app
from app.models.point_config import PointConfig
from app import db

app = create_app()
with app.app_context():
    # List of outdated keys to remove
    keys_to_remove = [
        'status_completed_form',
        'status_meeting_scheduled',
        'status_sold',
        'status_paid',
        'click'  # Remove regular clicks as requested
    ]
    
    # Delete each configuration
    for key in keys_to_remove:
        config = PointConfig.query.filter_by(key=key).first()
        if config:
            db.session.delete(config)
            print(f"Deleted configuration: {key}")
    
    # Commit the changes
    db.session.commit()
    print("Outdated point configurations successfully removed") 