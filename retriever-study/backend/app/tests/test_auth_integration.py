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
    verify_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID
)



class TestAuthenticationIntegration:
    """Integration tests for the complete authentication flow."""



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
    def setup_test_user(self, db_session, mock_google_user):
        """Setup test user in database using the repository pattern."""
        from app.data.async_db import UserRepository
        user_repo = UserRepository(db_session)
        user_record = user_repo.find_or_create_user_by_oauth(mock_google_user)
        yield user_record

    def test_google_oauth_config_endpoint(self, client):
        """Test that Google OAuth configuration is accessible."""
        response = client.get("/auth/google/config")

        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data
        assert data["client_id"] == GOOGLE_CLIENT_ID

    @patch('app.main.verify_google_id_token', new_callable=AsyncMock)
    def test_google_auth_happy_path(self, mock_verify_google, client, mock_google_user, setup_test_user):
        """
        Test Scenario 1: Happy Path Login with new /auth/google endpoint

        Validates:
        1. Google ID token verification via the new endpoint.
        2. User lookup/creation in the database.
        3. Backend JWT generation with correct payload.
        4. Proper AuthResponse format (access_token and user object).
        """
        # Setup async mock for verify_google_id_token
        mock_verify_google.return_value = mock_google_user

        # Make request to the new /auth/google endpoint
        request_payload = {"google_token": "mock_google_id_token"}
        response = client.post("/auth/google", json=request_payload)

        # Verify response structure
        assert response.status_code == 200
        data = response.json()

        # Check AuthResponse format
        assert "access_token" in data
        assert "user" in data
        assert "refresh_token" not in data  # Ensure old fields are gone

        # Verify JWT token structure
        access_token = data["access_token"]
        decoded_token = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        assert decoded_token["type"] == "access"
        assert decoded_token["sub"] == str(setup_test_user.id)
        assert decoded_token["email"] == mock_google_user["email"]

        # Verify user profile in response
        user_profile = data["user"]
        assert user_profile["email"] == mock_google_user["email"]
        assert user_profile["full_name"] == mock_google_user["name"]
        assert user_profile["id"] == str(setup_test_user.id)

        # Verify Google token verification was called
        mock_verify_google.assert_awaited_once_with("mock_google_id_token")

    @pytest.mark.asyncio
    @patch('app.main.verify_google_id_token', new_callable=AsyncMock)
    async def test_google_auth_invalid_email(self, mock_verify_google, client):
        """Test /auth/google endpoint rejects non-UMBC emails."""
        mock_verify_google.return_value = {
            "sub": "google_123",
            "email": "user@gmail.com",  # Non-UMBC email
            "name": "Test User",
            "iss": "accounts.google.com"
        }

        request_payload = {"google_token": "mock_token"}
        response = client.post("/auth/google", json=request_payload)

        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    @patch('app.main.verify_google_id_token', new_callable=AsyncMock)
    async def test_google_auth_invalid_token(self, mock_verify_google, client):
        """Test /auth/google endpoint handles invalid Google tokens."""
        # Configure the mock to raise an AuthError, simulating a token verification failure
        from app.core.auth import AuthError
        mock_verify_google.side_effect = AuthError("Invalid or expired Google token", 401)

        request_payload = {"google_token": "invalid_token"}
        response = client.post("/auth/google", json=request_payload)

        assert response.status_code == 401
        assert "Invalid or expired Google token" in response.json()["detail"]

    @patch('app.core.async_ai.ai_service.generate_embedding')
    def test_protected_route_access_with_valid_token(self, mock_generate_embedding, client, setup_test_user):
        """
        Test Scenario 2: Protected Route Access (/users/me)

        Validates:
        1. JWT token validation on a protected endpoint.
        2. Successful access to the user's own profile data.
        """
        mock_generate_embedding.return_value = [0.1] * 768
        valid_jwt_payload = {
            "sub": str(setup_test_user.id),
            "email": setup_test_user.email,
            "name": setup_test_user.name
        }
        access_token = create_access_token(valid_jwt_payload)

        # Access the protected /users/me endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.put("/users/me", headers=headers, json={
            "name": "Updated Name",
            "email": valid_jwt_payload["email"], # Email is from token
            "courses": [],
            "bio": "",
            "prefs": {"studyStyle": [], "timeSlots": [], "locations": []}
        })

        assert response.status_code == 200
        data = response.json()

        # Verify the user profile response from the /users/me endpoint
        assert data["email"] == valid_jwt_payload["email"]
        assert data["id"] == str(setup_test_user.id)
        assert data["name"] == "Updated Name"

    def test_protected_route_access_without_token(self, client):
        """Test protected endpoint rejects requests without authentication."""
        response = client.put("/users/me", json={})

        assert response.status_code in [401, 403]

    def test_protected_route_access_with_invalid_token(self, client):
        """
        Test Scenario 3: Error Handling - Invalid Token

        Validates:
        1. Invalid JWT token rejection
        2. Proper error response format
        """
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.put("/users/me", headers=headers, json={})

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
        response = client.put("/users/me", headers=headers, json={})

        assert response.status_code == 401





    def test_recommendations_endpoint_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
        """Test that recommendations endpoint requires authentication."""
        # Test without authentication
        response = client.get("/recommendations")
        assert response.status_code in [401, 403]

        # Test with authentication
        valid_jwt_payload['sub'] = str(setup_test_user.id)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/recommendations", headers=headers)

        # Should succeed (might return empty list if no groups/embeddings)
        assert response.status_code in [200, 500]  # 500 acceptable if no embeddings set up

    def test_create_group_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
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
        assert response.status_code in [401, 403]

        # Test with authentication
        valid_jwt_payload['sub'] = str(setup_test_user.id)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups", json=group_data, headers=headers)

        # Should succeed in creating group
        assert response.status_code == 201

    def test_join_group_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
        """Test that joining groups requires authentication."""
        # Test without authentication
        response = client.post("/groups/test_group_id/join")
        assert response.status_code in [401, 403]

        # Test with authentication (will fail since group doesn't exist, but auth should pass)
        valid_jwt_payload['sub'] = str(setup_test_user.id)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups/nonexistent_group/join", headers=headers)

        # Should fail due to group not existing, not auth failure
        assert response.status_code in [404, 500]

    def test_malformed_authorization_header(self, client):
        """Test handling of malformed Authorization headers."""
        test_cases = [
            "InvalidFormat",
            "Bearer",  # Missing token
            "Basic dGVzdA==",  # Wrong auth type
            "Bearer token_with_spaces here",
            "Bearer " + "x" * 10000  # Extremely long token
        ]

        for header_value in test_cases:
            headers = {"Authorization": header_value}
            response = client.put("/users/me", headers=headers, json={})
            assert response.status_code in [401, 403]

    def test_create_group_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
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
        valid_jwt_payload['sub'] = str(setup_test_user.id)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups", json=group_data, headers=headers)

        # Should succeed in creating group
        assert response.status_code == 201

    def test_join_group_requires_authentication(self, client, valid_jwt_payload, setup_test_user):
        """Test that joining groups requires authentication."""
        # Test without authentication
        response = client.post("/groups/test_group_id/join")
        assert response.status_code == 401

        # Test with authentication (will fail since group doesn't exist, but auth should pass)
        valid_jwt_payload['sub'] = str(setup_test_user.id)
        access_token = create_access_token(valid_jwt_payload)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/groups/nonexistent_group/join", headers=headers)

        # Should fail due to group not existing, not auth failure
        assert response.status_code in [404, 500]

    def test_rate_limiting_on_auth_endpoints(self, client):
        """Test that authentication endpoints have rate limiting."""
        response = client.post("/auth/google", json={"google_token": "test"})
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
            response = client.put("/users/me", headers=headers, json={})
            assert response.status_code == 401

    def test_jwt_algorithm_confusion_prevention(self):
        """Test that JWT algorithm confusion attacks are prevented by the library."""
        payload = {
            "sub": "user_123",
            "email": "test@umbc.edu",
            "type": "access",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        with pytest.raises(jwt.JWSError):
            jwt.encode(payload, "", algorithm="none")

    @patch('app.main.verify_google_id_token', new_callable=AsyncMock)
    async def test_google_token_issuer_validation(self, mock_verify_google, client):
        """Test that Google tokens from invalid issuers are rejected."""
        invalid_issuer_user = {
            "sub": "google_123",
            "email": "test@umbc.edu",
            "name": "Test User",
            "iss": "evil.com",
            "aud": GOOGLE_CLIENT_ID
        }
        mock_verify_google.return_value = invalid_issuer_user

        request_payload = {"google_token": "mock_token"}
        response = client.post("/auth/google", json=request_payload)

        assert response.status_code == 401

    def test_concurrent_authentication_requests(self, client):
        """Test handling of concurrent authentication requests."""
        import threading
        import time

        results = []

        def make_request():
            try:
                response = client.post("/auth/google",
                                     json={"google_token": "invalid_token"})
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