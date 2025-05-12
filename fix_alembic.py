from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Delete all rows from alembic_version
    db.session.execute(text('DELETE FROM alembic_version'))
    
    # Insert our migration version
    db.session.execute(text('INSERT INTO alembic_version (version_num) VALUES (:version)'), 
                      {'version': 'add_commission_models'})
    
    db.session.commit()
    print("Fixed alembic_version table, now contains only 'add_commission_models'")
    
    # Verify the update
    result = db.session.execute(text('SELECT * FROM alembic_version')).fetchall()
    print(f'Rows in alembic_version table:')
    for row in result:
        print(row) 