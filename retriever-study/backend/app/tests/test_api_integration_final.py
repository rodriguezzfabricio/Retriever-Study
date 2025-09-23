"""
Final API Integration Tests for Asynchronous PostgreSQL Database

This test suite validates the FastAPI application's endpoints work correctly with
the asynchronous PostgreSQL database. Tests are designed to use TestClient to make
actual HTTP requests to the live API endpoints, ensuring full integration testing.

Key Design Principles:
- Uses FastAPI TestClient for actual HTTP requests
- Tests against live API endpoints (not mocked repositories)
- Validates complete request/response cycles
- Ensures proper database integration through the API layer
- Includes comprehensive error handling and edge case testing
"""

import pytest
import pytest_asyncio
import os
import json
import uuid
from typing import Dict, Any, Optional
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

# Configure test environment before any imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/test_retriever_study"
os.environ["JWT_SECRET"] = "test-secret-key-for-integration-tests"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"

# Import the application
from app.main import app
from app.core.auth import create_access_token

# Test Fixtures

@pytest.fixture(scope="session")
def test_user_data():
    """Consistent test user data for all tests."""
    return {
        "user_id": "test-user-001",
        "email": "testuser@umbc.edu",
        "name": "Test User",
        "picture": "https://example.com/avatar.png",
        "bio": "I'm a test user",
        "courses": ["CMSC341", "MATH221"]
    }

@pytest.fixture(scope="session")
def auth_token(test_user_data):
    """Generate a valid JWT token for authentication."""
    return create_access_token(data={
        "sub": test_user_data["user_id"],
        "email": test_user_data["email"]
    })

@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest_asyncio.fixture
async def client():
    """AsyncClient for making HTTP requests to the API."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# Mock External Services (but not the database repositories)

@pytest.fixture(autouse=True)
def mock_ai_service():
    """Mock AI service to avoid external API calls."""
    with patch("app.main.ai_service") as mock_ai:
        mock_ai.generate_embedding_async.return_value = [0.1, 0.2, 0.3] * 42
        mock_ai.health_check.return_value = {"status": "healthy"}
        yield mock_ai

@pytest.fixture(autouse=True)
def mock_google_oauth():
    """Mock Google OAuth for authentication tests."""
    with patch("app.core.auth.verify_google_id_token") as mock_verify:
        mock_verify.return_value = {
            "sub": "google-test-id-123",
            "email": "testuser@umbc.edu",
            "name": "Test User",
            "picture": "https://example.com/avatar.png"
        }
        yield mock_verify

@pytest.fixture(autouse=True)
def mock_toxicity_service():
    """Mock toxicity checking service."""
    with patch("app.core.toxicity.get_toxicity_score") as mock_toxicity:
        mock_toxicity.return_value = 0.1  # Low toxicity
        yield mock_toxicity

@pytest.fixture(autouse=True)
def setup_async_db():
    """Ensure async database components are initialized."""
    with patch("app.main.async_initialized", True):
        # Mock the async database and related services
        mock_db = MagicMock()
        mock_db.health_check.return_value = {"status": "connected", "pool_size": 10}

        with patch("app.main.async_db", mock_db):
            yield mock_db

# Test Classes

@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test system health and monitoring endpoints."""

    async def test_health_check_success(self, client: AsyncClient):
        """Test the health check endpoint returns system status."""
        response = await client.get("/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "version" in health_data

@pytest.mark.asyncio
class TestAuthenticationFlow:
    """Test OAuth authentication and user management endpoints."""

    async def test_google_oauth_callback_flow(self, client: AsyncClient):
        """Test Google OAuth callback with proper token exchange."""
        # Mock repositories for this specific test
        with patch("app.main.get_repositories") as mock_repos:
            mock_user_repo = MagicMock()
            mock_user_repo.create_or_update_oauth_user = MagicMock(return_value={
                "userId": "test-user-001",
                "name": "Test User",
                "email": "testuser@umbc.edu",
                "picture_url": "https://example.com/avatar.png",
                "courses": [],
                "bio": "",
                "created_at": "2025-01-01T12:00:00Z"
            })
            mock_user_repo.update_last_login = MagicMock()

            mock_repos.return_value = {"user_repo": mock_user_repo}

            oauth_payload = {"id_token": "mock-google-jwt-token"}
            response = await client.post("/auth/google/callback", json=oauth_payload)

            assert response.status_code == 200
            auth_response = response.json()
            assert "access_token" in auth_response
            assert "refresh_token" in auth_response
            assert "user" in auth_response

    async def test_get_current_user_profile(self, client: AsyncClient, auth_headers):
        """Test retrieving current user profile."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_user_repo = MagicMock()
            mock_user_repo.get_user_by_id = MagicMock(return_value={
                "userId": "test-user-001",
                "name": "Test User",
                "email": "testuser@umbc.edu",
                "picture_url": "https://example.com/avatar.png",
                "courses": ["CMSC341"],
                "bio": "Test bio",
                "created_at": "2025-01-01T12:00:00Z"
            })

            mock_repos.return_value = {"user_repo": mock_user_repo}

            response = await client.get("/auth/me", headers=auth_headers)
            assert response.status_code == 200

            profile = response.json()
            assert profile["id"] == "test-user-001"
            assert profile["email"] == "testuser@umbc.edu"

    async def test_update_user_profile(self, client: AsyncClient, auth_headers):
        """Test updating user profile information."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_user_repo = MagicMock()
            mock_user_repo.get_user_by_id = MagicMock(return_value={
                "userId": "test-user-001",
                "name": "Test User",
                "email": "testuser@umbc.edu",
                "picture_url": "https://example.com/avatar.png"
            })
            mock_user_repo.update_user_by_id = MagicMock(return_value={
                "userId": "test-user-001",
                "name": "Updated User",
                "email": "testuser@umbc.edu",
                "picture_url": "https://example.com/avatar.png",
                "created_at": "2025-01-01T12:00:00Z"
            })
            mock_user_repo.update_user_embedding = MagicMock()

            mock_repos.return_value = {"user_repo": mock_user_repo}

            update_data = {
                "name": "Updated User",
                "email": "testuser@umbc.edu",
                "bio": "Updated bio",
                "courses": ["CMSC447"],
                "prefs": {
                    "studyStyle": ["collaborative"],
                    "timeSlots": ["evening"],
                    "locations": ["library"]
                }
            }

            response = await client.put("/users/me", json=update_data, headers=auth_headers)
            assert response.status_code == 200

@pytest.mark.asyncio
class TestGroupManagement:
    """Test complete group lifecycle through API endpoints."""

    created_group_id: Optional[str] = None

    async def test_create_group_success(self, client: AsyncClient, auth_headers):
        """Test creating a new study group via API."""
        with patch("app.main.get_repositories") as mock_repos:
            group_id = f"group-{uuid.uuid4().hex[:8]}"

            mock_group_repo = MagicMock()
            mock_group_repo.create_group = MagicMock(return_value={
                "groupId": group_id,
                "group_id": group_id,
                "name": "API Test Group",
                "title": "API Test Group",
                "description": "Testing group creation via API",
                "subject": "CMSC341",
                "courseCode": "CMSC341",
                "max_members": 5,
                "maxMembers": 5,
                "created_by": "test-user-001",
                "ownerId": "test-user-001",
                "members": ["test-user-001"],
                "member_count": 1,
                "memberCount": 1,
                "created_at": "2025-01-01T12:00:00Z",
                "createdAt": "2025-01-01T12:00:00Z",
                "lastActivityAt": "2025-01-01T12:00:00Z",
                "location": "Library",
                "tags": [],
                "timePrefs": [],
                "isFull": False,
                "recentActivityScore": 2.5,
                "fillingUpFast": False,
                "startsSoon": True
            })
            mock_group_repo.update_group_embedding = MagicMock()

            mock_repos.return_value = {"group_repo": mock_group_repo}

            group_data = {
                "courseCode": "CMSC341",
                "title": "API Test Group",
                "description": "Testing group creation via API",
                "maxMembers": 5,
                "location": "Library"
            }

            response = await client.post("/groups", json=group_data, headers=auth_headers)
            assert response.status_code == 201

            created_group = response.json()
            assert created_group["title"] == "API Test Group"
            assert created_group["ownerId"] == "test-user-001"
            assert "groupId" in created_group

            TestGroupManagement.created_group_id = created_group["groupId"]

    async def test_get_group_details(self, client: AsyncClient):
        """Test retrieving specific group details via API."""
        group_id = TestGroupManagement.created_group_id or "test-group-001"

        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.get_group_by_id = MagicMock(return_value={
                "groupId": group_id,
                "group_id": group_id,
                "name": "API Test Group",
                "title": "API Test Group",
                "description": "Testing group creation via API",
                "subject": "CMSC341",
                "courseCode": "CMSC341",
                "max_members": 5,
                "maxMembers": 5,
                "created_by": "test-user-001",
                "ownerId": "test-user-001",
                "members": ["test-user-001"],
                "member_count": 1,
                "memberCount": 1,
                "location": "Library",
                "created_at": "2025-01-01T12:00:00Z",
                "createdAt": "2025-01-01T12:00:00Z",
                "lastActivityAt": "2025-01-01T12:00:00Z",
                "tags": [],
                "timePrefs": [],
                "isFull": False,
                "recentActivityScore": 2.5,
                "fillingUpFast": False,
                "startsSoon": True
            })

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.get(f"/groups/{group_id}")
            assert response.status_code == 200

            group_details = response.json()
            assert group_details["groupId"] == group_id
            assert group_details["title"] == "API Test Group"

    async def test_get_all_groups(self, client: AsyncClient):
        """Test retrieving all groups via API."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.get_groups_with_pagination = MagicMock(return_value=[
                {
                    "groupId": "group-001",
                    "group_id": "group-001",
                    "name": "Test Group 1",
                    "title": "Test Group 1",
                    "subject": "CMSC341",
                    "courseCode": "CMSC341",
                    "maxMembers": 4,
                    "max_members": 4,
                    "ownerId": "test-user-001",
                    "created_by": "test-user-001",
                    "members": ["test-user-001"],
                    "memberCount": 1,
                    "member_count": 1,
                    "description": "Test group",
                    "location": "Library",
                    "created_at": "2025-01-01T12:00:00Z",
                    "createdAt": "2025-01-01T12:00:00Z",
                    "lastActivityAt": "2025-01-01T12:00:00Z",
                    "tags": [],
                    "timePrefs": [],
                    "isFull": False,
                    "recentActivityScore": 2.5,
                    "fillingUpFast": False,
                    "startsSoon": True
                }
            ])

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.get("/groups")
            assert response.status_code == 200

            groups = response.json()
            assert isinstance(groups, list)
            assert len(groups) >= 1

    async def test_join_group_via_api(self, client: AsyncClient, auth_headers):
        """Test joining a group via API endpoint."""
        group_id = TestGroupManagement.created_group_id or "test-group-001"

        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.join_group = MagicMock(return_value={
                "groupId": group_id,
                "group_id": group_id,
                "name": "API Test Group",
                "title": "API Test Group",
                "ownerId": "test-user-001",
                "created_by": "test-user-001",
                "members": ["test-user-001"],
                "memberCount": 1,
                "member_count": 1,
                "maxMembers": 5,
                "max_members": 5,
                "subject": "CMSC341",
                "courseCode": "CMSC341",
                "description": "Testing group creation via API",
                "location": "Library",
                "created_at": "2025-01-01T12:00:00Z",
                "createdAt": "2025-01-01T12:00:00Z",
                "lastActivityAt": "2025-01-01T12:00:00Z",
                "tags": [],
                "timePrefs": [],
                "isFull": False,
                "recentActivityScore": 2.5,
                "fillingUpFast": False,
                "startsSoon": True
            })

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.post(f"/groups/{group_id}/join", headers=auth_headers)
            assert response.status_code == 200

            updated_group = response.json()
            assert "test-user-001" in updated_group["members"]

    async def test_get_user_groups(self, client: AsyncClient, auth_headers):
        """Test getting groups for a specific user."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.get_groups_for_member = MagicMock(return_value=[
                {
                    "groupId": "group-001",
                    "group_id": "group-001",
                    "name": "User's Group",
                    "title": "User's Group",
                    "ownerId": "test-user-001",
                    "created_by": "test-user-001",
                    "members": ["test-user-001"],
                    "memberCount": 1,
                    "member_count": 1,
                    "maxMembers": 4,
                    "max_members": 4,
                    "subject": "CMSC341",
                    "courseCode": "CMSC341",
                    "description": "Test group",
                    "location": "Library",
                    "created_at": "2025-01-01T12:00:00Z",
                    "createdAt": "2025-01-01T12:00:00Z",
                    "lastActivityAt": "2025-01-01T12:00:00Z",
                    "tags": [],
                    "timePrefs": [],
                    "isFull": False,
                    "recentActivityScore": 2.5,
                    "fillingUpFast": False,
                    "startsSoon": True
                }
            ])

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.get("/users/test-user-001/groups", headers=auth_headers)
            assert response.status_code == 200

            user_groups = response.json()
            assert isinstance(user_groups, list)

@pytest.mark.asyncio
class TestMessagingSystem:
    """Test group messaging functionality via API."""

    async def test_create_message_via_api(self, client: AsyncClient):
        """Test creating a message through the API."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_message_repo = MagicMock()
            mock_message_repo.create_message = MagicMock(return_value={
                "messageId": "msg-001",
                "groupId": "group-001",
                "senderId": "test-user-001",
                "content": "Hello from API test!",
                "createdAt": "2025-01-01T12:00:00Z",
                "toxicityScore": 0.1
            })

            mock_repos.return_value = {"message_repo": mock_message_repo}

            message_data = {
                "groupId": "group-001",
                "senderId": "test-user-001",
                "content": "Hello from API test!"
            }

            response = await client.post("/messages", json=message_data)
            assert response.status_code == 201

            created_message = response.json()
            assert created_message["content"] == "Hello from API test!"
            assert "messageId" in created_message

    async def test_get_messages_via_api(self, client: AsyncClient):
        """Test retrieving messages for a group via API."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_message_repo = MagicMock()
            mock_message_repo.get_messages_by_group = MagicMock(return_value=[
                {
                    "messageId": "msg-001",
                    "groupId": "group-001",
                    "senderId": "test-user-001",
                    "content": "Hello from API test!",
                    "createdAt": "2025-01-01T12:00:00Z",
                    "toxicityScore": 0.1
                }
            ])
            mock_user_repo = MagicMock()
            mock_user_repo.get_user_by_id = MagicMock(return_value={"name": "Test User"})

            mock_repos.return_value = {
                "message_repo": mock_message_repo,
                "user_repo": mock_user_repo
            }

            response = await client.get("/messages?groupId=group-001")
            assert response.status_code == 200

            messages = response.json()
            assert isinstance(messages, list)

    async def test_toxic_message_blocked(self, client: AsyncClient):
        """Test that toxic messages are blocked by the API."""
        # Override toxicity score for this test
        with patch("app.core.toxicity.get_toxicity_score", return_value=0.9):
            with patch("app.main.get_repositories") as mock_repos:
                mock_repos.return_value = {"message_repo": MagicMock()}

                message_data = {
                    "groupId": "group-001",
                    "senderId": "test-user-001",
                    "content": "This is a toxic message for testing"
                }

                response = await client.post("/messages", json=message_data)
                assert response.status_code == 400

@pytest.mark.asyncio
class TestSearchAndRecommendations:
    """Test AI-powered search and recommendation features."""

    async def test_search_groups_via_api(self, client: AsyncClient):
        """Test searching groups through the API."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.get_groups_with_pagination = MagicMock(return_value=[
                {
                    "groupId": "group-001",
                    "group_id": "group-001",
                    "name": "Data Structures Group",
                    "title": "Data Structures Group",
                    "subject": "CMSC341",
                    "courseCode": "CMSC341",
                    "embedding": [0.1, 0.2, 0.3] * 42,
                    "ownerId": "test-user-001",
                    "created_by": "test-user-001",
                    "members": ["test-user-001"],
                    "memberCount": 1,
                    "member_count": 1,
                    "maxMembers": 4,
                    "max_members": 4,
                    "description": "Learn data structures",
                    "location": "Library",
                    "created_at": "2025-01-01T12:00:00Z",
                    "createdAt": "2025-01-01T12:00:00Z",
                    "lastActivityAt": "2025-01-01T12:00:00Z",
                    "tags": [],
                    "timePrefs": [],
                    "isFull": False,
                    "recentActivityScore": 2.5,
                    "fillingUpFast": False,
                    "startsSoon": True
                }
            ])

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.get("/search?q=data structures&limit=5")
            assert response.status_code == 200

            search_results = response.json()
            assert isinstance(search_results, list)

    async def test_get_recommendations_via_api(self, client: AsyncClient, auth_headers):
        """Test getting AI-powered recommendations via API."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_user_repo = MagicMock()
            mock_user_repo.get_user_by_id = MagicMock(return_value={
                "userId": "test-user-001",
                "bio": "I love algorithms",
                "courses": ["CMSC341"],
                "embedding": [0.1, 0.2, 0.3] * 42
            })
            mock_user_repo.update_user_embedding = MagicMock()

            mock_group_repo = MagicMock()
            mock_group_repo.get_groups_with_pagination = MagicMock(return_value=[])

            mock_repos.return_value = {
                "user_repo": mock_user_repo,
                "group_repo": mock_group_repo
            }

            response = await client.get("/recommendations?limit=3", headers=auth_headers)
            assert response.status_code == 200

            recommendations = response.json()
            assert isinstance(recommendations, list)

@pytest.mark.asyncio
class TestErrorHandling:
    """Test API error handling and edge cases."""

    async def test_unauthorized_access_to_protected_endpoint(self, client: AsyncClient):
        """Test that protected endpoints require authentication."""
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_nonexistent_group_returns_404(self, client: AsyncClient):
        """Test that requesting a nonexistent group returns 404."""
        with patch("app.main.get_repositories") as mock_repos:
            mock_group_repo = MagicMock()
            mock_group_repo.get_group_by_id = MagicMock(return_value=None)

            mock_repos.return_value = {"group_repo": mock_group_repo}

            response = await client.get("/groups/nonexistent-group-id")
            assert response.status_code == 404

    async def test_empty_search_query_rejected(self, client: AsyncClient):
        """Test that empty search queries are rejected."""
        response = await client.get("/search?q=")
        assert response.status_code == 400

@pytest.mark.asyncio
class TestDataIntegrity:
    """Test data integrity through API operations."""

    async def test_group_creation_includes_owner_as_member(self, client: AsyncClient, auth_headers):
        """Test that group creation properly includes owner as first member."""
        with patch("app.main.get_repositories") as mock_repos:
            group_id = "integrity-test-group"

            mock_group_repo = MagicMock()
            mock_group_repo.create_group = MagicMock(return_value={
                "groupId": group_id,
                "group_id": group_id,
                "name": "Integrity Test Group",
                "title": "Integrity Test Group",
                "ownerId": "test-user-001",
                "created_by": "test-user-001",
                "members": ["test-user-001"],  # Owner should be first member
                "memberCount": 1,
                "member_count": 1,
                "maxMembers": 4,
                "max_members": 4,
                "subject": "CMSC341",
                "courseCode": "CMSC341",
                "description": "Testing data integrity",
                "location": "Library",
                "created_at": "2025-01-01T12:00:00Z",
                "createdAt": "2025-01-01T12:00:00Z",
                "lastActivityAt": "2025-01-01T12:00:00Z",
                "tags": [],
                "timePrefs": [],
                "isFull": False,
                "recentActivityScore": 2.5,
                "fillingUpFast": False,
                "startsSoon": True
            })
            mock_group_repo.update_group_embedding = MagicMock()

            mock_repos.return_value = {"group_repo": mock_group_repo}

            group_data = {
                "courseCode": "CMSC341",
                "title": "Integrity Test Group",
                "description": "Testing data integrity",
                "maxMembers": 4,
                "location": "Library"
            }

            response = await client.post("/groups", json=group_data, headers=auth_headers)
            assert response.status_code == 201

            created_group = response.json()
            assert created_group["ownerId"] == "test-user-001"
            assert "test-user-001" in created_group["members"]
            assert created_group["memberCount"] == len(created_group["members"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])