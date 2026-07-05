"""
Pytest configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# Use file-based SQLite for testing to avoid connection wiping issues
TEST_DATABASE_URL = "sqlite:///./test_knowtis.db"



@pytest.fixture(name="db")
def db_fixture():
    """Fixture to create database tables and provide a clean session"""
    engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables in models.py (Base imports them since they are registered)
    # Ensure they are imported here so SQLAlchemy registers them on Base.metadata
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def client_fixture(db):
    """Fixture to override get_db dependency and yield TestClient"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Mock user register payload"""
    return {
        "email": "student@example.com",
        "username": "student1",
        "password": "securepassword123",
        "confirm_password": "securepassword123",
        "full_name": "Test Student"
    }


@pytest.fixture
def test_event_data():
    """Mock academic event create payload"""
    return {
        "event_type": "DEADLINE",
        "course_code": "ELE310",
        "title": "ELE310 Assignment 2",
        "description": "Submit before noon on portal",
        "venue": "Department Hall B",
        "date_time": "2026-06-15T12:00:00"
    }
