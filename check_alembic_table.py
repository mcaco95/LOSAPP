from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Get all rows from alembic_version
    result = db.session.execute(text('SELECT * FROM alembic_version')).fetchall()
    print(f'Rows in alembic_version table:')
    for row in result:
        print(row) 