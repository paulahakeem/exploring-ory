from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from databases import Database
import logging

DATABASE_URL = "sqlite:///./test.db"

# Create the database instance
database = Database(DATABASE_URL)
metadata = MetaData()

# Base class for models
Base = declarative_base(metadata=metadata)

# Create the SQLAlchemy engine and session
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Check database connection
try:
    with engine.connect() as connection:
        print("Database connected successfully!")
except Exception as e:
    logging.error(f"Failed to connect to the database: {e}")
    print(f"Error: {e}")
