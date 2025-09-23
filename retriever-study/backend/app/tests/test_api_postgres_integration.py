"""
Revised API Integration Tests for Asynchronous PostgreSQL Database

This suite validates the FastAPI endpoints against a live, asynchronous PostgreSQL test database.
It ensures that all CRUD operations function as expected through API requests.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
import os
from unittest.mock import patch
from pytest_mock import MockerFixture

# Set the environment to 'test' BEFORE importing the app
os.environ["ENVIRONMENT"] = "test"

from app.main import app
from app.core.auth import create_access_token

# --- Test Data Fixtures ---

@pytest.fixture(scope="module")
def test_user_data():
    """Provides consistent test user data."""
    return {
        "user_id": "testuser001",
        "email": "testuser@umbc.edu",
        "name": "Test User",
        "picture": "https://example.com/avatar.png",
    }

@pytest.fixture(scope="module")
def auth_token(test_user_data):
    """Generates a valid JWT for the test user."""
    return create_access_token(data={"sub": test_user_data["user_id"], "email": test_user_data["email"]})

@pytest.fixture
def auth_headers(auth_token):
    """Returns authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest_asyncio.fixture
async def client():
    """Provides an asynchronous test client for making API requests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- Mocks for External Dependencies ---

@pytest.fixture(autouse=True)
def mock_ai_service():
    """Mocks the AI service to avoid actual AI calls during tests."""
    with patch("app.main.ai_service") as mock_service:
        mock_service.generate_embedding_async.return_value = [0.1] * 128
        yield mock_service

@pytest.fixture(autouse=True)
def mock_repos(mocker: MockerFixture):
    """Mocks the get_repositories dependency to control repository data."""
    mock_user_repo = mocker.AsyncMock()
    mock_user_repo.get_user.side_effect = lambda user_id: {
        "userId": "testuser001",
        "google_id": "google_test_id",
        "name": "Test User",
        "email": "testuser@umbc.edu",
        "picture_url": "https://example.com/avatar.png",
        "bio": "Initial bio.",
        "courses": ["CMSC101"],
        "created_at": "2025-01-01T12:00:00Z"
    } if user_id == "testuser001" else None
    mock_user_repo.create_or_update_oauth_user.return_value = {
        "userId": "testuser001",
        "google_id": "google_test_id",
        "name": "Test User",
        "email": "testuser@umbc.edu",
        "picture_url": "https://example.com/avatar.png",
        "bio": "Initial bio.",
        "courses": ["CMSC101"],
        "created_at": "2025-01-01T12:00:00Z"
    }
    mock_user_repo.update_last_login.return_value = None
    mock_user_repo.update_user_embedding.return_value = None
    mock_user_repo.update_user_by_id.return_value = {
        "userId": "testuser001",
        "name": "Updated Test User",
        "email": "testuser@umbc.edu",
        "picture_url": "https://example.com/avatar.png",
        "created_at": "2025-01-01T12:00:00Z"
    }

    mock_group_repo = mocker.AsyncMock()
    mock_group_repo.create_group.return_value = {
        "groupId": "newgroup001",
        "ownerId": "testuser001",
        "title": "Data Structures Study Group",
        "maxMembers": 5,
        "members": ["testuser001"],
        "memberCount": 1
    }
    mock_group_repo.get_group_by_id.return_value = {
        "groupId": "newgroup001",
        "ownerId": "testuser001",
        "title": "Data Structures Study Group",
        "maxMembers": 5,
        "members": ["testuser001"],
        "memberCount": 1
    }
    mock_group_repo.get_groups_with_pagination.return_value = [
        {
            "groupId": "newgroup001",
            "ownerId": "testuser001",
            "title": "Data Structures Study Group",
            "maxMembers": 5,
            "members": ["testuser001"],
            "memberCount": 1
        }
    ]
    mock_group_repo.add_member.return_value = {
        "groupId": "newgroup001",
        "ownerId": "testuser001",
        "title": "Data Structures Study Group",
        "maxMembers": 5,
        "members": ["testuser001"],
        "memberCount": 2
    }
    mock_group_repo.remove_member.return_value = {
        "groupId": "newgroup001",
        "ownerId": "testuser001",
        "title": "Data Structures Study Group",
        "maxMembers": 5,
        "members": [],
        "memberCount": 1
    }
    mock_group_repo.get_groups_for_member.return_value = [
        {
            "groupId": "newgroup001",
            "ownerId": "testuser001",
            "title": "Data Structures Study Group",
            "maxMembers": 5,
            "members": ["testuser001"],
            "memberCount": 1
        }
    ]
    mock_group_repo.update_group_embedding.return_value = None
    mock_group_repo.get_trending_groups.return_value = []
    mock_group_repo.search_groups.return_value = []

    mock_message_repo = mocker.AsyncMock()
    mock_message_repo.create_message.return_value = {
        "messageId": "newmessage001",
        "groupId": "newgroup001",
        "senderId": "testuser001",
        "content": "Hello, world! This is a test message.",
        "createdAt": "2025-01-01T12:00:00Z"
    }
    mock_message_repo.get_messages_by_group.return_value = [
        {
            "messageId": "newmessage001",
            "groupId": "newgroup001",
            "senderId": "testuser001",
            "content": "Hello, world! This is a test message.",
            "createdAt": "2025-01-01T12:00:00Z"
        }
    ]

    with patch("app.main.get_repositories") as mock_get_repos:
        mock_get_repos.return_value = {
            "user_repo": mock_user_repo,
            "group_repo": mock_group_repo,
            "message_repo": mock_message_repo
        }
        yield mock_get_repos

# --- Test Classes ---

@pytest.mark.asyncio
class TestUserProfileEndpoints:
    """Validates user profile management endpoints."""

    async def test_get_current_user_profile_success(self, client: AsyncClient, auth_headers):
        """
        Scenario: An authenticated user requests their own profile.
        Expected: The API returns the user's profile data with a 200 OK status.
        """
        response = await client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        profile = response.json()
        assert profile["id"] == "testuser001"
        assert profile["email"] == "testuser@umbc.edu"
        assert "name" in profile

    async def test_update_current_user_profile(self, client: AsyncClient, auth_headers):
        """
        Scenario: An authenticated user updates their profile information.
        Expected: The API returns the updated profile with a 200 OK status.
        """
        update_payload = {
            "name": "Updated Test User",
            "email": "testuser@umbc.edu", # Email is ignored server-side but required by model
            "bio": "This is my updated bio.",
            "courses": ["CMSC202", "MATH221"],
            "prefs": {
                "studyStyle": ["collaborative"],
                "timeSlots": ["weekends"],
                "locations": ["online"]
            }
        }
        
        mock_user_repo = mock_repos.return_value["user_repo"]
        mock_user_repo.update_user_by_id.return_value = {
            "userId": "testuser001",
            "name": update_payload["name"],
            "email": update_payload["email"],
            "picture_url": "https://example.com/avatar.png",
            "created_at": "2025-01-01T12:00:00Z"
        }
        
        response = await client.put("/users/me", json=update_payload, headers=auth_headers)

        assert response.status_code == 200
        updated_profile = response.json()
        assert updated_profile["name"] == "Updated Test User"
        assert updated_profile["bio"] == "This is my updated bio."
        assert updated_profile["courses"] == ["CMSC202", "MATH221"]

@pytest.mark.asyncio
class TestGroupManagementEndpoints:
    """Comprehensive tests for group creation, retrieval, and management."""

    new_group_id: str = None

    async def test_create_group_success(self, client: AsyncClient, auth_headers):
        """
        Scenario: An authenticated user creates a new study group.
        Expected: The group is created, and the API returns the new group's data with a 201 Created status.
        """
        group_payload = {
            "courseCode": "CMSC341",
            "title": "Data Structures Study Group",
            "description": "Let's ace the final exam together.",
            "maxMembers": 5,
            "location": "ITE Building, Room 240",
            "tags": ["python", "algorithms"]
        }
        
        response = await client.post("/groups", json=group_payload, headers=auth_headers)
        
        assert response.status_code == 201
        group = response.json()
        assert group["title"] == "Data Structures Study Group"
        assert group["ownerId"] == "testuser001"
        assert group["maxMembers"] == 5
        assert "groupId" in group
        TestGroupManagementEndpoints.new_group_id = group["groupId"]

    async def test_get_group_details_success(self, client: AsyncClient):
        """
        Scenario: A user requests the details of an existing group.
        Expected: The API returns the full group details with a 200 OK status.
        """
        assert TestGroupManagementEndpoints.new_group_id is not None, "Group must be created first"
        group_id = TestGroupManagementEndpoints.new_group_id
        
        response = await client.get(f"/groups/{group_id}")
        
        assert response.status_code == 200
        group = response.json()
        assert group["groupId"] == group_id
        assert group["title"] == "Data Structures Study Group"

    async def test_get_all_groups(self, client: AsyncClient):
        """
        Scenario: A user requests the list of all available groups.
        Expected: The API returns an array of groups with a 200 OK status.
        """
        response = await client.get("/groups")
        assert response.status_code == 200
        groups = response.json()
        assert isinstance(groups, list)
        # Check if our newly created group is in the list
        assert any(g["groupId"] == self.new_group_id for g in groups)

    async def test_join_group_success(self, client: AsyncClient, auth_headers):
        """
        Scenario: An authenticated user joins an existing group.
        Expected: The user is added to the group, and the updated group data is returned with a 200 OK status.
        """
        group_id = self.new_group_id
        response = await client.post(f"/groups/{group_id}/join", headers=auth_headers)
        
        assert response.status_code == 200
        group = response.json()
        assert "testuser001" in group["members"]
        assert group["memberCount"] > 0

    async def test_get_user_groups_after_joining(self, client: AsyncClient, auth_headers, test_user_data):
        """
        Scenario: An authenticated user requests the list of groups they have joined.
        Expected: The API returns an array containing the group they just joined.
        """
        user_id = test_user_data["user_id"]
        response = await client.get(f"/users/{user_id}/groups", headers=auth_headers)

        assert response.status_code == 200
        groups = response.json()
        assert isinstance(groups, list)
        assert len(groups) > 0
        assert any(g["groupId"] == self.new_group_id for g in groups)

    async def test_leave_group_success(self, client: AsyncClient, auth_headers):
        """
        Scenario: An authenticated user leaves a group they previously joined.
        Expected: The user is removed from the group, and the updated group data is returned with a 200 OK status.
        """
        group_id = self.new_group_id
        response = await client.post(f"/groups/{group_id}/leave", headers=auth_headers)
        
        assert response.status_code == 200
        group = response.json()
        assert "testuser001" not in group["members"]

@pytest.mark.asyncio
class TestMessagingEndpoints:
    """Validates the messaging endpoints for group chats."""

    group_id_for_chat: str = None
    
    @pytest.fixture(autouse=True)
    async def setup_group_for_chat(self, client: AsyncClient, auth_headers):
        """Creates a dedicated group for chat tests."""
        if TestMessagingEndpoints.group_id_for_chat is None:
            group_payload = {
                "courseCode": "CMSC447",
                "title": "Software Engineering Chat",
                "description": "A group for testing messages.",
                "maxMembers": 2
            }
            response = await client.post("/groups", json=group_payload, headers=auth_headers)
            assert response.status_code == 201
            TestMessagingEndpoints.group_id_for_chat = response.json()["groupId"]

    async def test_create_message_success(self, client: AsyncClient, auth_headers, test_user_data):
        """
        Scenario: An authenticated user sends a message to a group.
        Expected: The message is created and returned with a 201 Created status.
        """
        message_payload = {
            "groupId": self.group_id_for_chat,
            "senderId": test_user_data["user_id"],
            "content": "Hello, world! This is a test message."
        }
        
        response = await client.post("/messages", json=message_payload, headers=auth_headers)
        
        assert response.status_code == 201
        message = response.json()
        assert message["content"] == "Hello, world! This is a test message."
        assert message["senderId"] == test_user_data["user_id"]
        assert "messageId" in message

    async def test_get_messages_for_group(self, client: AsyncClient):
        """
        Scenario: A user requests the messages for a specific group.
        Expected: The API returns an array of messages for that group with a 200 OK status.
        """
        # First, post a message to ensure there's something to retrieve
        await self.test_create_message_success(client, auth_headers, {"user_id": "testuser001"})

        response = await client.get(f"/messages?groupId={self.group_id_for_chat}")
        
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert messages[0]["content"] == "Hello, world! This is a test message."
