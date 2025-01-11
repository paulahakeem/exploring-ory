# models.py
from sqlalchemy import Column, String, Text, UUID
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid
from .db import Base 

class Blog(Base):
    __tablename__ = "blogs"  # Name of the table in the database

    # Columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, index=True)
    title = Column(String(100), nullable=False)  # Blog title (max 100 characters)
    content = Column(Text, nullable=False)       # Blog content (unlimited length)
    owner = Column(String(50), nullable=False)   # Owner of the blog (e.g., user ID or email)
    created_at = Column(String, default=func.now())  # Timestamp of blog creation

    def __repr__(self):
        return f"<Blog(id={self.id}, title={self.title}, owner={self.owner})>"