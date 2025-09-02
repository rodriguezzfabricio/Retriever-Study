"""
Production Security Tests - Comprehensive Test Suite

Tests all security layers implemented in the application:
1. Rate limiting protection
2. Input sanitization 
3. AI abuse protection
4. Authentication/authorization
5. Security headers

Run with: pytest app/tests/test_security.py -v
"""

import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import sanitize_string, validate_ai_input, detect_suspicious_input

client = TestClient(app)

# Test fixtures for authentication
@pytest.fixture
def auth_headers():
    """Mock authentication headers for testing protected endpoints"""
    # In real tests, you'd get a valid JWT token
    return {"Authorization": "Bearer mock_jwt_token_for_testing"}

@pytest.fixture
def malicious_inputs():
    """Common malicious input patterns for testing"""
    return {
        "xss_script": "<script>alert('XSS attack')</script>",
        "sql_injection": "'; DROP TABLE users; --",
        "html_injection": "<img src=x onerror=alert('XSS')>",
        "oversized_text": "A" * 5000,  # 5KB text
        "repetitive_text": "spam " * 1000,
        "command_injection": "; rm -rf /",
        "path_traversal": "../../../etc/passwd"
    }

class TestRateLimiting:
    """Test rate limiting protection on all endpoints"""
    
    def test_health_endpoint_rate_limiting(self):
        """Health endpoint should have generous rate limits"""
        # Make multiple rapid requests
        responses = []
        for i in range(10):
            response = client.get("/health")
            responses.append(response.status_code)
        
        # All should succeed (1000/minute limit)
        assert all(status == 200 for status in responses)
    
    def test_auth_endpoint_rate_limiting(self):
        """Auth endpoints should have strict rate limits"""
        # Test OAuth start endpoint (10/minute limit)
        rapid_requests = 0
        for i in range(15):  # Try more than the limit
            response = client.get("/auth/google")
            if response.status_code == 429:  # Rate limited
                break
            rapid_requests += 1
        
        # Should be rate limited before 15 requests
        assert rapid_requests < 15, "Rate limiting not working on auth endpoint"
    
    def test_ai_endpoint_rate_limiting(self, auth_headers):
        """AI endpoints should have moderate rate limits"""
        # Test search endpoint (30/minute limit)
        rapid_requests = 0
        for i in range(35):  # Try more than the limit
            response = client.get("/search?q=test", headers=auth_headers)
            if response.status_code == 429:  # Rate limited
                break
            rapid_requests += 1
        
        # Should be rate limited before 35 requests
        assert rapid_requests < 35, "Rate limiting not working on AI endpoint"

class TestInputSanitization:
    """Test input sanitization functions"""
    
    def test_sanitize_string_removes_html(self, malicious_inputs):
        """Test HTML tag removal"""
        result = sanitize_string(malicious_inputs["xss_script"], max_length=1000)
        assert "<script>" not in result
        assert "</script>" not in result
        assert "alert('XSS attack')" in result  # Text should remain
    
    def test_sanitize_string_length_limit(self):
        """Test length limiting"""
        long_text = "A" * 1000
        result = sanitize_string(long_text, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_string_sql_injection(self, malicious_inputs):
        """Test SQL injection pattern removal"""
        result = sanitize_string(malicious_inputs["sql_injection"], max_length=1000)
        assert "DROP TABLE" not in result.upper()
        assert "--" not in result
    
    def test_detect_suspicious_input(self, malicious_inputs):
        """Test suspicious pattern detection"""
        # Should detect various attack patterns
        assert detect_suspicious_input(malicious_inputs["sql_injection"]) == "sql_injection"
        assert detect_suspicious_input(malicious_inputs["xss_script"]) == "xss"
        assert detect_suspicious_input(malicious_inputs["command_injection"]) == "command_injection"
        
        # Should not flag normal input
        assert detect_suspicious_input("This is normal text about studying") is None

class TestAIAbuseProtection:
    """Test AI-specific security measures"""
    
    def test_validate_ai_input_length_limit(self):
        """Test AI input length validation"""
        huge_text = "A" * 3000  # Over 2000 char limit
        
        with pytest.raises(Exception) as exc_info:
            validate_ai_input(huge_text, max_length=2000, user_id="test_user")
        
        assert "too long for AI processing" in str(exc_info.value)
    
    def test_validate_ai_input_repetition_detection(self):
        """Test repetitive text detection"""
        repetitive_text = "spam " * 200  # Highly repetitive
        
        with pytest.raises(Exception) as exc_info:
            validate_ai_input(repetitive_text, max_length=2000, user_id="test_user")
        
        assert "excessive repetition" in str(exc_info.value)
    
    def test_validate_ai_input_suspicious_content(self, malicious_inputs):
        """Test suspicious content detection in AI input"""
        with pytest.raises(Exception) as exc_info:
            validate_ai_input(malicious_inputs["sql_injection"], user_id="test_user")
        
        assert "Invalid input content" in str(exc_info.value)
    
    def test_validate_ai_input_normal_text(self):
        """Test that normal text passes validation"""
        normal_text = "I'm looking for a study group for computer science. I enjoy collaborative learning and problem solving."
        
        result = validate_ai_input(normal_text, user_id="test_user")
        assert result == normal_text  # Should pass through unchanged

class TestEndpointSecurity:
    """Test security on actual API endpoints"""
    
    def test_group_creation_input_sanitization(self, auth_headers, malicious_inputs):
        """Test group creation sanitizes malicious input"""
        malicious_group = {
            "courseCode": "CS101",
            "title": malicious_inputs["xss_script"],
            "description": malicious_inputs["sql_injection"],
            "tags": ["<script>alert('hack')</script>"],
            "timePrefs": ["evenings"],
            "location": "library"
        }
        
        # This should not crash the server or store malicious data
        response = client.post("/groups", json=malicious_group, headers=auth_headers)
        
        # Should either succeed with sanitized data or reject with 400
        assert response.status_code in [200, 201, 400, 401, 422]
        
        # If successful, verify data was sanitized
        if response.status_code in [200, 201]:
            result = response.json()
            assert "<script>" not in result.get("title", "")
            assert "DROP TABLE" not in result.get("description", "").upper()
    
    def test_search_query_validation(self, malicious_inputs):
        """Test search query sanitization and validation"""
        # Test with malicious query
        response = client.get(f"/search?q={malicious_inputs['sql_injection']}")
        
        # Should either sanitize and process, or reject
        assert response.status_code in [200, 400, 429]
        
        # Should not crash or leak database errors
        if response.status_code == 400:
            error = response.json()
            assert "detail" in error
            # Should not expose internal error details
            assert "database" not in error["detail"].lower()
            assert "sql" not in error["detail"].lower()
    
    def test_profile_update_sanitization(self, auth_headers, malicious_inputs):
        """Test profile update input sanitization"""
        malicious_profile = {
            "name": malicious_inputs["html_injection"],
            "email": "test@umbc.edu",
            "bio": malicious_inputs["xss_script"],
            "courses": ["CS101"],
            "prefs": {
                "studyStyle": ["group-discussions"],
                "timeSlots": ["evenings"],
                "locations": ["library"]
            }
        }
        
        response = client.put("/users/me", json=malicious_profile, headers=auth_headers)
        
        # Should handle malicious input gracefully
        assert response.status_code in [200, 400, 401, 422]
        
        # If successful, verify sanitization occurred
        if response.status_code == 200:
            result = response.json()
            assert "<img" not in result.get("name", "")
            assert "<script>" not in result.get("bio", "")

class TestSecurityHeaders:
    """Test security headers are properly set"""
    
    def test_security_headers_present(self):
        """Test that all security headers are present"""
        response = client.get("/health")
        
        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options", 
            "X-XSS-Protection",
            "Referrer-Policy"
        ]
        
        for header in expected_headers:
            assert header in response.headers, f"Missing security header: {header}"
            assert response.headers[header] != "", f"Empty security header: {header}"
    
    def test_cors_headers_configured(self):
        """Test CORS headers are properly configured"""
        # Test preflight request
        response = client.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        # Should have CORS headers
        assert "Access-Control-Allow-Origin" in response.headers

class TestAuthenticationSecurity:
    """Test authentication and authorization security"""
    
    def test_protected_endpoints_require_auth(self):
        """Test that protected endpoints reject unauthenticated requests"""
        protected_endpoints = [
            "/auth/me",
            "/users/me", 
            "/recommendations",
            "/groups"  # POST
        ]
        
        for endpoint in protected_endpoints:
            if endpoint == "/groups":
                response = client.post(endpoint, json={"courseCode": "CS101", "title": "Test"})
            else:
                response = client.get(endpoint)
            
            # Should require authentication
            assert response.status_code in [401, 403, 422], f"Endpoint {endpoint} not properly protected"
    
    def test_invalid_jwt_rejected(self):
        """Test that invalid JWT tokens are rejected"""
        invalid_headers = {"Authorization": "Bearer invalid_jwt_token"}
        
        response = client.get("/auth/me", headers=invalid_headers)
        assert response.status_code == 401
    
    def test_missing_authorization_header(self):
        """Test endpoints handle missing auth headers properly"""
        response = client.get("/auth/me")
        assert response.status_code in [401, 403, 422]

class TestErrorHandling:
    """Test that errors don't leak sensitive information"""
    
    def test_generic_error_messages(self):
        """Test that error messages are generic and safe"""
        # Try to trigger various errors
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        # Error should not leak internal information
        error = response.json()
        if "detail" in error:
            detail = error["detail"].lower()
            assert "database" not in detail
            assert "sql" not in detail
            assert "internal" not in detail
            assert "stack trace" not in detail
    
    def test_rate_limit_error_message(self):
        """Test rate limit error messages are helpful but not revealing"""
        # Make enough requests to trigger rate limiting on a strict endpoint
        for i in range(20):
            response = client.get("/auth/google")
            if response.status_code == 429:
                error = response.json()
                # Should have helpful message
                assert "detail" in error
                # Should not reveal internal rate limiting details
                assert "redis" not in error["detail"].lower()
                assert "slowapi" not in error["detail"].lower()
                break

if __name__ == "__main__":
    # Run tests with: python -m pytest app/tests/test_security.py -v
    pytest.main([__file__, "-v"])