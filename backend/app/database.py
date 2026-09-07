"""
Database connection and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("sqlite"):
    # Ensure directory exists for SQLite db file if path is specified
    db_file_path = DATABASE_URL.replace("sqlite:////", "/").replace("sqlite:///", "").split("?")[0]
    if db_file_path and db_file_path != ":memory:":
        dir_name = os.path.dirname(db_file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL, pool_size=20, max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get the database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
