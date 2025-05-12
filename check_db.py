from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    
    print("\nDatabase Tables:")
    print("-" * 50)
    for table_name in inspector.get_table_names():
        print(f"\nTable: {table_name}")
        print("Columns:")
        for column in inspector.get_columns(table_name):
            print(f"  - {column['name']}: {column['type']}") 