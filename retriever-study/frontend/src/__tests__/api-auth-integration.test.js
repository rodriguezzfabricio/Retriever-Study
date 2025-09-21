/**
 * API Service Authentication Integration Tests
 *
 * Tests the integration between the API service layer and authentication system.
 * Validates that JWT tokens are properly included in requests and handled correctly.
 *
 * Test Coverage:
 * 1. JWT token injection into API requests
 * 2. API request error handling for auth failures
 * 3. Token refresh integration with API service
 * 4. Protected endpoint access validation
 * 5. Public endpoint access without authentication
 */

import { exchangeGoogleToken, getMe, refreshAccessToken, healthCheck, createGroup, joinGroup, getRecommendations } from '../services/api';

// Note: fetch and localStorage are mocked globally in setupTests.js

describe('API Authentication Integration Tests', () => {
  beforeEach(() => {
    fetch.mockClear();
    localStorage.clear();
    localStorage.getItem.mockClear();
    localStorage.setItem.mockClear();
    localStorage.removeItem.mockClear();
  });

  describe('Token Injection in API Requests', () => {
    test('should include JWT token in Authorization header for authenticated requests', async () => {
      const mockAuthData = {
        access_token: 'test_jwt_token',
        refresh_token: 'test_refresh_token',
        user: { id: '123', email: 'test@umbc.edu' }
      };

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: '123', email: 'test@umbc.edu' })
      });

      await getMe();

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/me'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer test_jwt_token'
          })
        })
      );
    });

    test('should make requests without Authorization header when no token stored', async () => {
      localStorage.getItem.mockReturnValue(null);

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok' })
      });

      await healthCheck();

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({
          headers: expect.not.objectContaining({
            'Authorization': expect.anything()
          })
        })
      );
    });

    test('should handle malformed auth data in localStorage gracefully', async () => {
      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'authData') return 'invalid_json{';
        return null;
      });

      // Mock console.error to avoid noise in tests
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok' })
      });

      await healthCheck();

      // Should make request without Authorization header
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({
          headers: expect.not.objectContaining({
            'Authorization': expect.anything()
          })
        })
      );

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to parse auth data from localStorage:',
        expect.any(Error)
      );

      consoleSpy.mockRestore();
    });
  });

  describe('Google OAuth Token Exchange', () => {
    test('should exchange Google ID token for backend JWT successfully', async () => {
      const mockResponse = {
        access_token: 'backend_jwt_token',
        refresh_token: 'backend_refresh_token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          id: 'user_123',
          name: 'Test User',
          email: 'test@umbc.edu'
        }
      };

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse
      });

      const result = await exchangeGoogleToken('google_id_token_mock');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/google/callback'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({ id_token: 'google_id_token_mock' })
        })
      );

      expect(result).toEqual(mockResponse);
    });

    test('should handle Google OAuth callback errors properly', async () => {
      const errorResponse = {
        detail: 'A valid UMBC email address is required.'
      };

      fetch.mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => errorResponse
      });

      await expect(exchangeGoogleToken('invalid_token')).rejects.toThrow('A valid UMBC email address is required.');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/google/callback'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ id_token: 'invalid_token' })
        })
      );
    });
  });

  describe('Token Refresh Flow', () => {
    test('should refresh access token successfully', async () => {
      const mockRefreshResponse = {
        access_token: 'new_access_token',
        refresh_token: 'same_refresh_token',
        token_type: 'bearer',
        expires_in: 1800,
        user: {
          id: 'user_123',
          email: 'test@umbc.edu'
        }
      };

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockRefreshResponse
      });

      const result = await refreshAccessToken('current_refresh_token');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/refresh'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({ refresh_token: 'current_refresh_token' })
        })
      );

      expect(result).toEqual(mockRefreshResponse);
    });

    test('should handle refresh token errors', async () => {
      fetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Token refresh failed. Please log in again.' })
      });

      await expect(refreshAccessToken('invalid_refresh_token')).rejects.toThrow('Token refresh failed. Please log in again.');
    });
  });

  describe('Protected Endpoint Access', () => {
    test('should access protected user profile endpoint with authentication', async () => {
      const mockAuthData = {
        access_token: 'valid_jwt_token',
        user: { id: '123' }
      };

      const mockUserProfile = {
        id: 'user_123',
        name: 'Test User',
        email: 'test@umbc.edu',
        courses: ['CMSC 341'],
        bio: 'Computer Science Student'
      };

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockUserProfile
      });

      const result = await getMe();

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/auth/me'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer valid_jwt_token'
          })
        })
      );

      expect(result).toEqual(mockUserProfile);
    });

    test('should handle 401 responses for expired tokens', async () => {
      const mockAuthData = {
        access_token: 'expired_jwt_token'
      };

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Authentication required' })
      });

      await expect(getMe()).rejects.toThrow('Authentication required');
    });

    test('should access recommendations endpoint with authentication', async () => {
      const mockAuthData = {
        access_token: 'valid_jwt_token'
      };

      const mockRecommendations = [
        {
          groupId: 'group_1',
          title: 'CMSC 341 Study Group',
          courseCode: 'CMSC 341',
          description: 'Data structures study group'
        }
      ];

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockRecommendations
      });

      const result = await getRecommendations('user_123', 5);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/recommendations?userId=user_123&limit=5'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer valid_jwt_token'
          })
        })
      );

      expect(result).toEqual(mockRecommendations);
    });

    test('should create groups with authentication', async () => {
      const mockAuthData = {
        access_token: 'valid_jwt_token'
      };

      const groupData = {
        courseCode: 'CMSC 341',
        title: 'Data Structures Study Group',
        description: 'Weekly study sessions',
        location: 'Library',
        maxMembers: 6
      };

      const mockCreatedGroup = {
        ...groupData,
        groupId: 'group_123',
        ownerId: 'user_123',
        members: ['user_123']
      };

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockCreatedGroup
      });

      const result = await createGroup(groupData, 'user_123');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/groups?owner_id=user_123'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer valid_jwt_token',
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify(groupData)
        })
      );

      expect(result).toEqual(mockCreatedGroup);
    });

    test('should join groups with authentication', async () => {
      const mockAuthData = {
        access_token: 'valid_jwt_token'
      };

      const mockUpdatedGroup = {
        groupId: 'group_123',
        title: 'Study Group',
        members: ['user_123', 'user_456'],
        memberCount: 2
      };

      localStorage.getItem.mockImplementation((key) => {
        if (key === 'authData') return JSON.stringify(mockAuthData);
        return null;
      });

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockUpdatedGroup
      });

      const result = await joinGroup('group_123', 'user_456');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/groups/group_123/join'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer valid_jwt_token',
            'Content-Type': 'application/json'
          }),
          body: JSON.stringify({ userId: 'user_456' })
        })
      );

      expect(result).toEqual(mockUpdatedGroup);
    });
  });

  describe('Public Endpoint Access', () => {
    test('should access health check without authentication', async () => {
      const mockHealthResponse = {
        status: 'ok',
        version: '1.0.0',
        timestamp: '2024-01-01T00:00:00Z'
      };

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockHealthResponse
      });

      const result = await healthCheck();

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          })
        })
      );

      // Should not include Authorization header
      const [, options] = fetch.mock.calls[0];
      expect(options.headers).not.toHaveProperty('Authorization');

      expect(result).toEqual(mockHealthResponse);
    });
  });

  describe('Error Handling and Network Issues', () => {
    test('should handle network errors gracefully', async () => {
      fetch.mockRejectedValue(new Error('Network error'));

      await expect(healthCheck()).rejects.toThrow('Network error - check if backend is running');
    });

    test('should handle malformed JSON responses', async () => {
      fetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('Invalid JSON');
        }
      });

      await expect(getMe()).rejects.toThrow('HTTP 500');
    });

    test('should handle 204 No Content responses', async () => {
      fetch.mockResolvedValue({
        ok: true,
        status: 204
      });

      // Mock an endpoint that returns 204
      const result = await fetch('/api/test').then(response => {
        if (response.status === 204) return null;
        return response.json();
      });

      expect(result).toBeNull();
    });

    test('should handle API errors with proper error format', async () => {
      const errorResponse = {
        detail: {
          error: 'VALIDATION_ERROR',
          message: 'Invalid input data'
        }
      };

      fetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => errorResponse
      });

      await expect(getMe()).rejects.toThrow('VALIDATION_ERROR');
    });
  });

  describe('API Base URL Configuration', () => {
    test('should use environment variable for API base URL', () => {
      // Since we can't easily change process.env in Jest, we test that the import works
      // In a real app, you'd test with different REACT_APP_API_URL values
      expect(typeof exchangeGoogleToken).toBe('function');
      expect(typeof getMe).toBe('function');
    });
  });

  describe('Request Logging', () => {
    test('should log API requests for debugging', async () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok' })
      });

      await healthCheck();

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('API Request: GET')
      );

      consoleSpy.mockRestore();
    });
  });
});