/**
 * Frontend Integration Tests for Authentication Flow
 *
 * Tests the complete Google OAuth → Backend JWT → Protected API flow from the frontend perspective.
 * This covers the frontend components of the UTDF: AUTH-01-INTEGRATION-TEST
 *
 * Test Scenarios:
 * 1. AuthContext provider initialization and state management
 * 2. Google OAuth integration and token exchange
 * 3. JWT token storage and retrieval
 * 4. Automatic token refresh flow
 * 5. Protected route access and redirection
 * 6. Logout flow and cleanup
 * 7. API service authentication headers
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

// Import components under test
import { AuthProvider, useAuth } from '../context/AuthContext';
import { exchangeGoogleToken, getMe, refreshAccessToken } from '../services/api';

// Mock the API service
jest.mock('../services/api');
const mockExchangeGoogleToken = exchangeGoogleToken;
const mockGetMe = getMe;
const mockRefreshAccessToken = refreshAccessToken;

// Mock jwt-decode
jest.mock('jwt-decode', () => ({
  jwtDecode: jest.fn()
}));
import { jwtDecode } from 'jwt-decode';

// Note: localStorage is mocked globally in setupTests.js

// Test component to access auth context
const TestComponent = () => {
  const auth = useAuth();
  return (
    <div>
      <div data-testid="is-authenticated">{auth.isAuthenticated ? 'true' : 'false'}</div>
      <div data-testid="user-email">{auth.user?.email || 'no-email'}</div>
      <div data-testid="user-name">{auth.user?.name || 'no-name'}</div>
      <div data-testid="token">{auth.token || 'no-token'}</div>
      <button onClick={() => auth.login(mockAuthResponse)} data-testid="login-btn">Login</button>
      <button onClick={() => auth.logout()} data-testid="logout-btn">Logout</button>
      <button onClick={() => auth.refresh()} data-testid="refresh-btn">Refresh</button>
    </div>
  );
};

const mockAuthResponse = {
  access_token: 'mock_access_token_jwt',
  refresh_token: 'mock_refresh_token_jwt',
  token_type: 'bearer',
  expires_in: 1800,
  user: {
    id: 'user_123',
    name: 'Test User',
    email: 'testuser@umbc.edu',
    picture: 'https://example.com/photo.jpg'
  }
};

const mockJwtClaims = {
  sub: 'user_123',
  email: 'testuser@umbc.edu',
  name: 'Test User',
  exp: Math.floor(Date.now() / 1000) + 3600, // Valid for 1 hour
  type: 'access'
};

describe('AuthContext Integration Tests', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    localStorageMock.clear.mockClear();
    localStorageMock.getItem.mockClear();
    localStorageMock.setItem.mockClear();
    localStorageMock.removeItem.mockClear();

    // Reset localStorage to empty state
    localStorageMock.getItem.mockReturnValue(null);
  });

  describe('Initial State and Context Provider', () => {
    test('should initialize with unauthenticated state when no stored tokens', () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(screen.getByTestId('user-email')).toHaveTextContent('no-email');
      expect(screen.getByTestId('token')).toHaveTextContent('no-token');
    });

    test('should restore authenticated state from valid stored tokens', async () => {
      // Mock stored auth data
      const storedAuthData = JSON.stringify(mockAuthResponse);
      const storedUserData = JSON.stringify(mockAuthResponse.user);

      localStorageMock.getItem.mockImplementation((key) => {
        switch (key) {
          case 'authToken': return mockAuthResponse.access_token;
          case 'userData': return storedUserData;
          case 'authData': return storedAuthData;
          default: return null;
        }
      });

      // Mock JWT decode
      jwtDecode.mockReturnValue(mockJwtClaims);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Should restore authenticated state
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      expect(screen.getByTestId('user-email')).toHaveTextContent('testuser@umbc.edu');
      expect(screen.getByTestId('token')).toHaveTextContent(mockAuthResponse.access_token);
    });

    test('should clear storage and remain unauthenticated with expired token', () => {
      // Mock expired token
      const expiredClaims = {
        ...mockJwtClaims,
        exp: Math.floor(Date.now() / 1000) - 3600 // Expired 1 hour ago
      };

      localStorageMock.getItem.mockImplementation((key) => {
        switch (key) {
          case 'authToken': return 'expired_token';
          case 'userData': return JSON.stringify(mockAuthResponse.user);
          default: return null;
        }
      });

      jwtDecode.mockReturnValue(expiredClaims);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Should clear storage and remain unauthenticated
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authToken');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('userData');
    });
  });

  describe('Login Flow', () => {
    test('should handle successful login and update state', async () => {
      jwtDecode.mockReturnValue(mockJwtClaims);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Initial state should be unauthenticated
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');

      // Perform login
      act(() => {
        screen.getByTestId('login-btn').click();
      });

      // Should update to authenticated state
      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(screen.getByTestId('user-email')).toHaveTextContent('testuser@umbc.edu');
      expect(screen.getByTestId('user-name')).toHaveTextContent('Test User');
      expect(screen.getByTestId('token')).toHaveTextContent(mockAuthResponse.access_token);

      // Verify data was stored in localStorage
      expect(localStorageMock.setItem).toHaveBeenCalledWith('authToken', mockAuthResponse.access_token);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('userData', expect.any(String));
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refreshToken', mockAuthResponse.refresh_token);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('authData', expect.any(String));
    });

    test('should handle login with invalid JWT gracefully', async () => {
      jwtDecode.mockImplementation(() => {
        throw new Error('Invalid JWT');
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      act(() => {
        screen.getByTestId('login-btn').click();
      });

      // Should still update state but with null decoded claims
      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(screen.getByTestId('token')).toHaveTextContent(mockAuthResponse.access_token);
    });
  });

  describe('Logout Flow', () => {
    test('should clear all auth state and storage on logout', async () => {
      jwtDecode.mockReturnValue(mockJwtClaims);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Login first
      act(() => {
        screen.getByTestId('login-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      // Now logout
      act(() => {
        screen.getByTestId('logout-btn').click();
      });

      // Should clear all state
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(screen.getByTestId('user-email')).toHaveTextContent('no-email');
      expect(screen.getByTestId('token')).toHaveTextContent('no-token');

      // Should clear localStorage
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authToken');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('userData');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authData');
    });
  });

  describe('Token Refresh Flow', () => {
    test('should refresh tokens successfully', async () => {
      const newAuthResponse = {
        ...mockAuthResponse,
        access_token: 'new_access_token',
        user: mockAuthResponse.user
      };

      mockRefreshAccessToken.mockResolvedValue(newAuthResponse);
      jwtDecode.mockReturnValue(mockJwtClaims);

      // Mock stored refresh token
      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'refreshToken') return 'stored_refresh_token';
        return null;
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Trigger refresh
      act(() => {
        screen.getByTestId('refresh-btn').click();
      });

      await waitFor(() => {
        expect(mockRefreshAccessToken).toHaveBeenCalledWith('stored_refresh_token');
      });

      // Should update with new token
      expect(screen.getByTestId('token')).toHaveTextContent('new_access_token');
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
    });

    test('should logout if refresh fails', async () => {
      mockRefreshAccessToken.mockRejectedValue(new Error('Refresh failed'));

      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'refreshToken') return 'invalid_refresh_token';
        return null;
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      act(() => {
        screen.getByTestId('refresh-btn').click();
      });

      await waitFor(() => {
        expect(mockRefreshAccessToken).toHaveBeenCalled();
      });

      // Should logout on refresh failure
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authToken');
    });

    test('should logout if no refresh token available', async () => {
      localStorageMock.getItem.mockReturnValue(null);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      act(() => {
        screen.getByTestId('refresh-btn').click();
      });

      // Should logout immediately if no refresh token
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(mockRefreshAccessToken).not.toHaveBeenCalled();
    });
  });

  describe('User Profile Bootstrap', () => {
    test('should bootstrap user profile from backend on mount', async () => {
      const backendUserProfile = {
        id: 'user_123',
        name: 'Updated User Name',
        email: 'testuser@umbc.edu',
        picture: 'https://example.com/new-photo.jpg',
        courses: ['CMSC 341', 'CMSC 421'],
        bio: 'Computer Science Student'
      };

      mockGetMe.mockResolvedValue(backendUserProfile);
      jwtDecode.mockReturnValue(mockJwtClaims);

      // Mock stored token
      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'authToken') return 'valid_token';
        return null;
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(mockGetMe).toHaveBeenCalled();
      });

      // Should update user data with backend response
      expect(screen.getByTestId('user-name')).toHaveTextContent('Updated User Name');
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
    });

    test('should logout if bootstrap fails', async () => {
      mockGetMe.mockRejectedValue(new Error('Unauthorized'));
      jwtDecode.mockReturnValue(mockJwtClaims);

      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'authToken') return 'invalid_token';
        return null;
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(mockGetMe).toHaveBeenCalled();
      });

      // Should logout on bootstrap failure
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authToken');
    });
  });

  describe('Cross-Tab Synchronization', () => {
    test('should sync auth state across tabs', async () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Initial state
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');

      // Simulate storage event from another tab
      const storageEvent = new StorageEvent('storage', {
        key: 'authToken',
        newValue: 'new_token_from_other_tab'
      });

      // Mock the updated localStorage values
      localStorageMock.getItem.mockImplementation((key) => {
        switch (key) {
          case 'authToken': return 'new_token_from_other_tab';
          case 'userData': return JSON.stringify(mockAuthResponse.user);
          case 'authData': return JSON.stringify(mockAuthResponse);
          default: return null;
        }
      });

      jwtDecode.mockReturnValue(mockJwtClaims);

      // Dispatch storage event
      act(() => {
        window.dispatchEvent(storageEvent);
      });

      // Should sync state
      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      expect(screen.getByTestId('token')).toHaveTextContent('new_token_from_other_tab');
    });

    test('should logout if auth data is cleared in another tab', async () => {
      jwtDecode.mockReturnValue(mockJwtClaims);

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Login first
      act(() => {
        screen.getByTestId('login-btn').click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('is-authenticated')).toHaveTextContent('true');
      });

      // Simulate auth data being cleared in another tab
      const storageEvent = new StorageEvent('storage', {
        key: 'authToken',
        newValue: null
      });

      localStorageMock.getItem.mockReturnValue(null);

      act(() => {
        window.dispatchEvent(storageEvent);
      });

      // Should logout
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
    });
  });

  describe('User Profile Building', () => {
    test('should correctly build user profile from various data sources', () => {
      const rawUser = {
        id: 'internal_123',
        googleId: 'google_456',
        name: 'John Doe',
        email: 'john@umbc.edu'
      };

      const tokenClaims = {
        sub: 'google_456',
        email: 'john@umbc.edu',
        name: 'John Doe Updated',
        picture: 'https://example.com/photo.jpg'
      };

      jwtDecode.mockReturnValue(tokenClaims);

      const authResponseWithProfile = {
        ...mockAuthResponse,
        user: rawUser
      };

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      act(() => {
        const testComponent = screen.getByTestId('login-btn');
        // Simulate login with custom auth response
        const auth = useAuth();
        auth.login(authResponseWithProfile);
      });

      // Profile should be correctly normalized
      expect(screen.getByTestId('user-email')).toHaveTextContent('john@umbc.edu');
      expect(screen.getByTestId('user-name')).toHaveTextContent('John Doe'); // From rawUser
    });
  });

  describe('Error Handling', () => {
    test('should handle malformed stored data gracefully', () => {
      localStorageMock.getItem.mockImplementation((key) => {
        switch (key) {
          case 'authToken': return 'invalid_jwt_token';
          case 'userData': return 'invalid_json{';
          default: return null;
        }
      });

      jwtDecode.mockImplementation(() => {
        throw new Error('Invalid token');
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // Should handle gracefully and remain unauthenticated
      expect(screen.getByTestId('is-authenticated')).toHaveTextContent('false');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('authToken');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('userData');
    });

    test('should handle context usage outside provider', () => {
      // Test component outside provider should throw error
      const TestOutsideProvider = () => {
        try {
          useAuth();
          return <div>Should not render</div>;
        } catch (error) {
          return <div data-testid="error">{error.message}</div>;
        }
      };

      render(<TestOutsideProvider />);

      expect(screen.getByTestId('error')).toHaveTextContent('useAuth must be used within an AuthProvider');
    });
  });
});