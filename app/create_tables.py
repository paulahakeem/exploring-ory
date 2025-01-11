# create_tables.py
import logging
from app.db import engine, Base
from app.models import Blog  # Import the Blog model

# Create tables
def create_tables() -> None:
    try:
        # Debugging: Print all tables registered with Base.metadata
        print("Tables in Base.metadata:", Base.metadata.tables.keys())

        # Create all tables defined in Base.metadata
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")
    except Exception as e:
        logging.error(f"Failed to create tables: {e}")
        print(f"Error: {e}")