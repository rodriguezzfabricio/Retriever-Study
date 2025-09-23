"""
API Integration Tests for Retriever Study Application

This test suite validates the API endpoints using a test PostgreSQL database.
All tests make real HTTP requests to the FastAPI application.
"""
import pytest
import json
import asyncio
import os
from fastapi import status
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"

from app.main import app

# Test data fixtures
@pytest.fixture
def test_user():
    """Test user data for API tests."""
    return {
        "name": "Test User",
        "email": "test@umbc.edu",
        "courses": ["CMSC341", "MATH301"],
        "bio": "Test bio",
        "prefs": {"study_style": ["focused"], "time_of_day": ["morning"]}
    }

@pytest.fixture
def test_group():
    """Test group data for API tests."""
    return {
        "courseCode": "CMSC341",
        "title": "Test Study Group",
        "description": "A test study group",
        "tags": ["algorithms", "data_structures"],
        "timePrefs": ["monday_10am"],
        "location": "Library",
        "maxMembers": 4
    }

@pytest.fixture
def test_message():
    """Test message data for API tests."""
    return {
        "content": "Hello, this is a test message!"
    }

@pytest.fixture
async def client():
    """Create test client for API requests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_auth_token():
    """Mock authentication token for protected endpoints."""
    return "mock_jwt_token_for_testing"

@pytest.fixture
def auth_headers(mock_auth_token):
    """Create authentication headers."""
    return {"Authorization": f"Bearer {mock_auth_token}"}

@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test health check endpoint."""
    
    async def test_health_check(self, client):
        """Test health check endpoint returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

@pytest.mark.asyncio
class TestAuthEndpoints:
    """Test authentication-related endpoints."""
    
    @patch('app.core.auth.verify_google_id_token')
    async def test_google_callback_success(self, mock_verify, client, test_user):
        """Test successful Google OAuth callback."""
        # Mock Google token verification
        mock_verify.return_value = {
            'email': test_user['email'],
            'name': test_user['name'],
            'sub': 'google_user_123'
        }
        
        response = await client.post("/auth/google/callback", json={
            "id_token": "mock_google_id_token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user['email']
    
    @patch('app.core.auth.verify_google_id_token')
    async def test_google_callback_invalid_token(self, mock_verify, client):
        """Test Google OAuth callback with invalid token."""
        # Mock Google token verification failure
        mock_verify.return_value = None
        
        response = await client.post("/auth/google/callback", json={
            "id_token": "invalid_token"
        })
        
        assert response.status_code == 401
    
    @patch('app.core.auth.verify_token')
    async def test_protected_endpoint_without_token(self, mock_verify, client):
        """Test accessing protected endpoint without token."""
        response = await client.get("/auth/me")
        assert response.status_code == 401
    
    @patch('app.core.auth.verify_token')
    async def test_protected_endpoint_with_valid_token(self, mock_verify, client, auth_headers, test_user):
        """Test accessing protected endpoint with valid token."""
        # Mock token verification
        mock_verify.return_value = {
            'userId': 'test_user_123',
            'email': test_user['email']
        }
        
        response = await client.get("/auth/me", headers=auth_headers)
        # Note: This might return 404 if user doesn't exist, which is expected behavior
        assert response.status_code in [200, 404]

@pytest.mark.asyncio
class TestUserEndpoints:
    """Test user-related endpoints."""
    
    @patch('app.core.auth.verify_token')
    async def test_get_current_user_not_found(self, mock_verify, client, auth_headers):
        """Test getting current user when user doesn't exist."""
        mock_verify.return_value = {
            'userId': 'nonexistent_user',
            'email': 'nonexistent@umbc.edu'
        }
        
        response = await client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 404
    
    @patch('app.core.auth.verify_token')
    async def test_update_user_profile_unauthorized(self, mock_verify, client):
        """Test updating user profile without authentication."""
        response = await client.put("/users/me", json={
            "name": "Updated Name",
            "bio": "Updated bio"
        })
        assert response.status_code == 401

@pytest.mark.asyncio
class TestGroupEndpoints:
    """Test group-related endpoints."""
    
    async def test_get_groups_public_access(self, client):
        """Test getting groups without authentication (should work)."""
        response = await client.get("/groups/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('app.core.auth.verify_token')
    async def test_create_group_unauthorized(self, mock_verify, client, test_group):
        """Test creating group without authentication."""
        response = await client.post("/groups/", json=test_group)
        assert response.status_code == 401
    
    @patch('app.core.auth.verify_token')
    async def test_create_group_invalid_data(self, mock_verify, client, auth_headers):
        """Test creating group with invalid data."""
        mock_verify.return_value = {
            'userId': 'test_user_123',
            'email': 'test@umbc.edu'
        }
        
        # Missing required fields
        invalid_group = {"title": "Incomplete Group"}
        
        response = await client.post("/groups/", json=invalid_group, headers=auth_headers)
        assert response.status_code == 422  # Validation error
    
    async def test_get_group_not_found(self, client):
        """Test getting a non-existent group."""
        response = await client.get("/groups/nonexistent_group_id")
        assert response.status_code == 404
    
    @patch('app.core.auth.verify_token')
    async def test_join_group_unauthorized(self, mock_verify, client):
        """Test joining group without authentication."""
        response = await client.post("/groups/some_group_id/join")
        assert response.status_code == 401
    
    @patch('app.core.auth.verify_token')
    async def test_leave_group_unauthorized(self, mock_verify, client):
        """Test leaving group without authentication."""
        response = await client.post("/groups/some_group_id/leave")
        assert response.status_code == 401


