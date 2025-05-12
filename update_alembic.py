from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # First, let's apply the migration
    db.session.execute(text('UPDATE alembic_version SET version_num = :version'), {'version': 'add_commission_models'})
    db.session.commit()
    print("Updated alembic_version to 'add_commission_models'")
    
    # Verify the update
    result = db.session.execute(text('SELECT version_num FROM alembic_version')).fetchone()
    print(f'Current version in database: {result[0] if result else None}') 