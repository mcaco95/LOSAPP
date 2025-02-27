from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text('SELECT version_num FROM alembic_version')).fetchone()
    print(f'Current version in database: {result[0] if result else None}') 