import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add the backend directory to the python path to fix the ModuleNotFoundError.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Set environment variables for testing BEFORE importing the app
os.environ['ENVIRONMENT'] = 'test'
# Use a separate, in-memory SQLite database for tests for speed and isolation
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET'] = 'test-secret'
os.environ['GOOGLE_CLIENT_ID'] = 'test-google-id'

from app.main import app
from app.data.async_db import Base, get_db

# Create a reusable sync engine for the test session
engine = create_engine(os.environ['DATABASE_URL'], connect_args={"check_same_thread": False})

# Create a sessionmaker for creating new test sessions
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Creates the database tables once per test session.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Provides a clean database transaction for each test function.
    Rolls back the transaction after the test is complete.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    Provides a FastAPI TestClient with the database dependency overridden
    to use the clean test session.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    del app.dependency_overrides[get_db]