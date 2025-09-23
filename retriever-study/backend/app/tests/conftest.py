import os
import sys
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Set test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_retriever_study"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"

# Import after setting environment variables
from app.data.async_db import Base, get_db

# Create test database engine
TEST_DATABASE_URL = os.getenv("DATABASE_URL")
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)

# Create async session factory
TestSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

def create_test_app():
    """Create a test FastAPI application."""
    # Import the actual app instead of creating a mock
    from app.main import app
    return app

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create test database tables and return the database engine."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_engine
    
    # Clean up after tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session with a rollback at the end of the test."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = TestSessionLocal(bind=connection)
    
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()

@pytest_asyncio.fixture
async def app(db_session):
    """Create a test FastAPI app with database dependency override."""
    from app.main import app as main_app
    
    # Override the database dependency
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    main_app.dependency_overrides[get_db] = override_get_db
    
    yield main_app
    
    # Clear overrides after test
    main_app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def test_user():
    """Test user data for authentication."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "name": "Test User",
        "courses": ["CMSC341", "MATH301"],
        "bio": "Test bio",
        "prefs": {
            "studyStyle": ["focused"],
            "timeSlots": ["morning"],
            "locations": ["library"]
        }
    }

@pytest.fixture
def test_group():
    """Test group data."""
    return {
        "courseCode": "CMSC341",
        "title": "Test Study Group",
        "description": "A test study group",
        "tags": ["algorithms", "data_structures"],
        "timePrefs": ["monday_10am"],
        "location": "Library",
        "maxMembers": 4
    }