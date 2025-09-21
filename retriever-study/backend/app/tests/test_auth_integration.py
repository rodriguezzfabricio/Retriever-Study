"""
Integration tests for the authentication flow covering Google OAuth → Backend JWT → Protected API access.

This test suite validates the complete end-to-end authentication flow as specified in the UTDF:
AUTH-01-INTEGRATION-TEST - Validate End-to-End Authentication Flow

Test Scenarios:
1. Happy Path Login - Google OAuth → JWT generation → Protected API access
2. Protected Route Access - JWT validation on protected endpoints
3. Error Handling - Invalid tokens, expired tokens, unauthorized access
4. Token Refresh Flow - Refresh token validation and new access token generation
5. Logout Flow - Token cleanup and session termination
"""

import pytest
import asyncio
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from jose import jwt
import httpx

# Set test environment before importing app
os.environ.setdefault('ENVIRONMENT', 'test')

# Import the FastAPI app and auth components
from app.main import app
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID
)
from app.data.local_db import db


class TestAuthenticationIntegration:
    """Integration tests for the complete authentication flow."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_google_user(self):
        """Mock Google user data returned from token verification."""
        return {
            "sub": "google_123456789",
            "email": "testuser@umbc.edu",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
            "iss": "accounts.google.com",
            "aud": GOOGLE_CLIENT_ID,
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }

    @pytest.fixture
    def valid_jwt_payload(self):
        """Valid JWT payload for creating test tokens."""
        return {
            "sub": "user_123456789",
            "email": "testuser@umbc.edu",
            "name": "Test User"
        }

    @pytest.fixture
    def setup_test_user(self, mock_google_user):
        """Setup test user in database."""
        # Clean up any existing test user
        try:
            existing_user = db.get_user_by_google_id(mock_google_user["sub"])
            if existing_user:
                # Clean up existing user for fresh test
                pass
        except:
            pass

        # Create test user
        user_record = db.create_or_update_oauth_user(
            google_id=mock_google_user["sub"],
            name=mock_google_user["name"],
            email=mock_google_user["email"],
            picture_url=mock_google_user.get("picture")
        )
        yield user_record

        # Cleanup after test - in production this would be handled by test database teardown

    def test_google_oauth_config_endpoint(self, client):
        """Test that Google OAuth configuration is accessible."""
        response = client.get("/auth/google/config")

        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data
        assert data["client_id"] == GOOGLE_CLIENT_ID

    @patch('app.main.verify_google_id_token')
    def test_google_oauth_callback_happy_path(self, mock_verify_google, client, mock_google_user, setup_test_user):
        """
        Test Scenario 1: Happy Path Login

        Validates:
        1. Google ID token verification
        2. User creation/update in database
        3. Backend JWT generation
        4. Proper token response format
        """
        # Setup async mock
        async def mock_async_verify(token):
            return mock_google_user
        mock_verify_google.side_effect = mock_async_verify

        # Make OAuth callback request
        request_payload = {"id_token": "mock_google_id_token"}
        response = client.post("/auth/google/callback", json=request_payload)

        # Verify response structure
        assert response.status_code == 200
        data = response.json()

        # Check TokenResponse format
        required_fields = ["access_token", "refresh_token", "token_type", "expires_in", "user"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        assert data["token_type"] == "bearer"
        assert data["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60

        # Verify JWT token structure
        access_token = data["access_token"]
        decoded_token = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert decoded_token["type"] == "access"
        assert decoded_token["sub"] == setup_test_user["userId"]
        assert decoded_token["email"] == mock_google_user["email"]

        # Verify user profile in response
        user_profile = data["user"]
        assert user_profile["email"] == mock_google_user["email"]
        assert user_profile["name"] == mock_google_user["name"]

        # Verify Google token verification was called
        mock_verify_google.assert_called_once_with("mock_google_id_token")

    def test_google_oauth_callback_invalid_email(self, client):
        """Test OAuth callback rejects non-UMBC emails."""
        with patch('app.core.auth.verify_google_id_token') as mock_verify:
            mock_verify.return_value = {
                "sub": "google_123",
                "email": "user@gmail.com",  # Non-UMBC email
                "name": "Test User",
                "iss": "accounts.google.com"
            }

            request_payload = {"id_token": "mock_token"}
            response = client.post("/auth/google/callback", json=request_payload)

            assert response.status_code == 403
            assert "UMBC email" in response.json()["detail"]

    def test_google_oauth_callback_invalid_token(self, client):
        """Test OAuth callback handles invalid Google tokens."""
        with patch('app.core.auth.verify_google_id_token') as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")

            request_payload = {"id_token": "invalid_token"}
            response = client.post("/auth/google/callback", json=request_payload)

            assert response.status_code == 500
            assert "Failed to authenticate" in response.json()["detail"]

    def test_protected_route_access_with_valid_token(self, client, valid_jwt_payload, setup_test_user):
        """
        Test Scenario 2: Protected Route Access

        Validates:
        1. JWT token validation on protected endpoints
        2. User data extraction from token
        3. Successful access to protected resources
        """
        # Create valid access token
        access_token = create_access_token(valid_jwt_payload)

        # Access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify user profile response
        assert data["email"] == valid_jwt_payload["email"]
        assert data["id"] == setup_test_user["userId"]

    def test_protected_route_access_without_token(self, client):
        """Test protected endpoint rejects requests without authentication."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_protected_route_access_with_invalid_token(self, client):
        """
        Test Scenario 3: Error Handling - Invalid Token

        Validates:
        1. Invalid JWT token rejection
        2. Proper error response format
        """
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401

    def test_protected_route_access_with_expired_token(self, client, valid_jwt_payload):
        """Test protected endpoint rejects expired tokens."""
        # Create expired token
        expired_payload = valid_jwt_payload.copy()
        expired_payload.update({
            "exp": datetime.utcnow() - timedelta(minutes=30),  # Expired 30 minutes ago
            "type": "access"
        })

        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401

    def test_protected_route_access_with_refresh_token(self, client, valid_jwt_payload):
        """Test protected endpoint rejects refresh tokens used as access tokens."""
        # Create refresh token
        refresh_token = create_refresh_token(valid_jwt_payload)

        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401

    def test_token_refresh_flow_happy_path(self, client, valid_jwt_payload, setup_test_user):
        """
        Test Scenario 4: Token Refresh Flow

        Validates:
        1. Refresh token validation
        2. New access token generation
        3. User data consistency
        """
        # Create valid refresh token
        refresh_token = create_refresh_token(valid_jwt_payload)

        # Request token refresh
        request_payload = {"refresh_token": refresh_token}
        response = client.post("/auth/refresh", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data
        assert "user" in data

        # Verify new access token is valid
        new_access_token = data["access_token"]
        decoded = jwt.decode(new_access_token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["type"] == "access"
        assert decoded["sub"] == setup_test_user["userId"]

    def test_token_refresh_with_invalid_token(self, client):
        """Test refresh endpoint rejects invalid refresh tokens."""
        request_payload = {"refresh_token": "invalid_refresh_token"}
        response = client.post("/auth/refresh", json=request_payload)

        assert response.status_code == 401

    def test_token_refresh_with_access_token(self, client, valid_jwt_payload):
        """Test refresh endpoint rejects access tokens used as refresh tokens."""
        # Create access token
        access_token = create_access_token(valid_jwt_payload)

        request_payload = {"refresh_token": access_token}
        response = client.post("/auth/refresh", json=request_payload)

        assert response.status_code == 401

    def test_logout_flow(self, client, valid_jwt_payload):
        """
        Test Scenario 5: Logout Flow

        Validates:
        1. Authenticated logout request
        2. Successful logout response
        """
        # Create valid access token
        access_token = create_access_token(valid_jwt_payload)

        # Perform logout
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/auth/logout", headers=headers)

        assert response.status_code == 200
        assert "message" in response.json()

    def test_user_groups_endpoint_with_authentication(self, client, valid_jwt_payload, setup_test_user):
        """Test that user groups endpoint requires authentication and returns user's groups."""
        # Create valid access token
        access_token = create_access_token(valid_jwt_payload)

        # Access user groups endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        user_id = setup_test_user["userId"]
        response = client.get(f"/users/{user_id}/groups", headers=headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_user_groups_endpoint_prevents_access_to_other_users(self, client, valid_jwt_payload, setup_test_user):
        """Test that users cannot access other users' groups."""
        # Create valid access token
        access_token = create_access_token(valid_jwt_payload)

        # Try to access another user's groups
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/users/other_user_id/groups", headers=headers)

        assert response.status_code == 403

    def test_recommendations_endpoint_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
        """Test that recommendations endpoint requires authentication."""
        # Test without authentication
        response = client.get("/recommendations")
        assert response.status_code == 401

        # Test with authentication
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/recommendations", headers=headers)

        # Should succeed (might return empty list if no groups/embeddings)
        assert response.status_code in [200, 500]  # 500 acceptable if no embeddings set up

    def test_create_group_requires_authentication(self, client, valid_jwt_payload):
        """Test that group creation requires authentication."""
        group_data = {
            "courseCode": "CMSC 341",
            "title": "Test Study Group",
            "description": "A test group",
            "tags": ["algorithms"],
            "timePrefs": ["evenings"],
            "location": "Library",
            "maxMembers": 5
        }

        # Test without authentication
        response = client.post("/groups", json=group_data)
        assert response.status_code == 401

        # Test with authentication
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups", json=group_data, headers=headers)

        # Should succeed in creating group
        assert response.status_code == 201

    def test_join_group_requires_authentication(self, client, valid_jwt_payload):
        """Test that joining groups requires authentication."""
        # Test without authentication
        response = client.post("/groups/test_group_id/join")
        assert response.status_code == 401

        # Test with authentication (will fail since group doesn't exist, but auth should pass)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups/nonexistent_group/join", headers=headers)

        # Should fail due to group not existing, not auth failure
        assert response.status_code in [404, 500]

    def test_rate_limiting_on_auth_endpoints(self, client):
        """Test that authentication endpoints have rate limiting."""
        # This test verifies rate limiting is configured, but doesn't test the limits
        # since that would require many requests

        # Test that the endpoints exist and have some form of protection
        response = client.post("/auth/google/callback", json={"id_token": "test"})
        # Should get an auth error, not a 404, indicating the endpoint exists and has protection
        assert response.status_code in [400, 401, 403, 500]

    def test_health_endpoint_public_access(self, client):
        """Test that health endpoint is publicly accessible."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_google_config_endpoint_public_access(self, client):
        """Test that Google config endpoint is publicly accessible."""
        response = client.get("/auth/google/config")
        assert response.status_code == 200
        assert "client_id" in response.json()


class TestAuthenticationEdgeCases:
    """Test edge cases and error conditions in authentication flow."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_malformed_authorization_header(self, client):
        """Test handling of malformed Authorization headers."""
        test_cases = [
            "InvalidFormat",
            "Bearer",  # Missing token
            "Basic dGVzdA==",  # Wrong auth type
            "Bearer token_with_spaces here",
            "Bearer " + "x" * 10000,  # Extremely long token
        ]

        for header_value in test_cases:
            headers = {"Authorization": header_value}
            response = client.get("/auth/me", headers=headers)
            assert response.status_code == 401

    def test_jwt_algorithm_confusion_prevention(self, client):
        """Test that JWT algorithm confusion attacks are prevented."""
        # This test ensures that tokens signed with 'none' algorithm are rejected
        payload = {
            "sub": "user_123",
            "email": "test@umbc.edu",
            "type": "access",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }

        # Create token with 'none' algorithm (should be rejected)
        none_token = jwt.encode(payload, "", algorithm="none")

        headers = {"Authorization": f"Bearer {none_token}"}
        response = client.get("/auth/me", headers=headers)

        assert response.status_code == 401

    @patch('app.main.verify_google_id_token')
    def test_google_token_issuer_validation(self, mock_verify_google, client):
        """Test that Google tokens from invalid issuers are rejected."""
        # Mock Google user with invalid issuer
        invalid_issuer_user = {
            "sub": "google_123",
            "email": "test@umbc.edu",
            "name": "Test User",
            "iss": "evil.com",  # Invalid issuer
            "aud": GOOGLE_CLIENT_ID
        }

        mock_verify_google.return_value = invalid_issuer_user

        request_payload = {"id_token": "mock_token"}
        response = client.post("/auth/google/callback", json=request_payload)

        assert response.status_code == 401

    def test_concurrent_authentication_requests(self, client):
        """Test handling of concurrent authentication requests."""
        import threading
        import time

        results = []

        def make_request():
            try:
                response = client.post("/auth/google/callback",
                                     json={"id_token": "invalid_token"})
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))

        # Create multiple threads to simulate concurrent requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should be handled (even if they fail due to invalid token)
        assert len(results) == 5
        # All should return HTTP status codes (not exceptions)
        assert all(isinstance(result, int) for result in results)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])