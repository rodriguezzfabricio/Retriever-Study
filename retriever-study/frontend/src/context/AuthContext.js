
import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { jwtDecode } from 'jwt-decode';
import { getMe, refreshAccessToken } from '../services/api';

const AuthContext = createContext(null);

const buildUserProfile = (rawUser, tokenClaims) => {
  if (!rawUser && !tokenClaims) {
    return null;
  }

  const safeUser = rawUser ? { ...rawUser } : {};
  const claims = tokenClaims || {};

  const googleId = safeUser.googleId || safeUser.google_id || claims.sub || null;
  // Internal DB id may be absent before bootstrap; don't default to googleId here
  const internalId = safeUser.id || safeUser.userId || claims.user_id || null;

  return {
    ...safeUser,
    id: internalId,
    userId: internalId,
    // Align with JWT: 'sub' is the Google account id used in group membership
    sub: googleId,
    googleId,
    googleSub: googleId,
    email: safeUser.email || claims.email || '',
    name: safeUser.name || claims.name || '',
    picture: safeUser.picture || claims.picture || null,
  };
};

// Helper function to get initial state from localStorage
const getInitialState = () => {
  try {
    const token = localStorage.getItem('authToken');
    const userData = localStorage.getItem('userData');

    if (token && userData) {
      const parsedUser = JSON.parse(userData);
      const decoded = jwtDecode(token);

      if (decoded.exp * 1000 > Date.now()) {
        return { token, user: buildUserProfile(parsedUser, decoded) };
      }
    }

    // Token missing or expired—clean up stale storage.
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
  } catch (error) {
    console.error('AuthContext: Failed reading auth state from storage', error);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
  }

  return { token: null, user: null };
};

export const AuthProvider = ({ children }) => {
  const initialState = getInitialState();
  const [token, setToken] = useState(initialState.token);
  const [user, setUser] = useState(initialState.user);
  const refreshTimerRef = useRef(null);

  const persist = (nextUser, nextToken, nextRefresh) => {
    if (nextToken) localStorage.setItem('authToken', nextToken);
    if (nextUser) localStorage.setItem('userData', JSON.stringify(nextUser));
    if (nextRefresh) localStorage.setItem('refreshToken', nextRefresh);
  };

  const clearTimers = () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  };

  const scheduleProactiveRefresh = (jwt) => {
    if (!jwt) return;
    try {
      const claims = jwtDecode(jwt);
      const skewMs = 60_000; // refresh 1 minute before expiry
      const msUntil = claims.exp * 1000 - Date.now() - skewMs;
      clearTimers();
      if (msUntil > 0) {
        refreshTimerRef.current = setTimeout(() => {
          handleRefresh();
        }, msUntil);
      }
    } catch (e) {
      // invalid token -> logout
      logout();
    }
  };

  const login = (authResponse) => {
    const { access_token, refresh_token, user } = authResponse;
    
    let decoded = null;
    try {
      decoded = jwtDecode(access_token);
    } catch (error) {
      console.error('AuthContext: Failed to decode auth token during login', error);
    }

    const normalizedUser = buildUserProfile(user, decoded);
    setUser(normalizedUser);
    setToken(access_token);
    
    // Store the entire auth response object in localStorage
    localStorage.setItem('authData', JSON.stringify(authResponse));
    persist(normalizedUser, access_token, refresh_token);
    scheduleProactiveRefresh(access_token);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userData');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('authData');
    clearTimers();
  };

  // This effect will run on component mount to check for token expiration
  useEffect(() => {
    const tokenFromStorage = localStorage.getItem('authToken');
    if (tokenFromStorage) {
      try {
        const decodedUser = jwtDecode(tokenFromStorage); // Corrected usage
        if (decodedUser.exp * 1000 < Date.now()) {
          logout();
        }
      } catch (error) {
        console.error("Invalid token in storage", error);
        logout();
      }
    }
  }, []);

  // Keep other tabs in sync with this tab's auth state.
  useEffect(() => {
    const handleStorage = (event) => {
      if (event.key === 'authToken' || event.key === 'userData' || event.key === 'authData') {
        const tokenFromStorage = localStorage.getItem('authToken');
        const userFromStorage = localStorage.getItem('userData');
        const authDataFromStorage = localStorage.getItem('authData');

        if (!tokenFromStorage || !userFromStorage) {
          setToken(null);
          setUser(null);
          return;
        }

        try {
          const decoded = jwtDecode(tokenFromStorage);
          const parsed = JSON.parse(userFromStorage);
          const normalizedUser = buildUserProfile(parsed, decoded);
          if (decoded.exp * 1000 > Date.now()) {
            setToken(tokenFromStorage);
            setUser(normalizedUser);
            scheduleProactiveRefresh(tokenFromStorage);
          } else {
            logout();
          }
        } catch (error) {
          console.error('AuthContext: failed to sync auth state across tabs', error);
          logout();
        }
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // Bootstrap canonical profile from backend and schedule refresh
  useEffect(() => {
    const bootstrap = async () => {
      const stored = localStorage.getItem('authToken');
      if (!stored) return;
      try {
        const claims = jwtDecode(stored);
        if (claims.exp * 1000 < Date.now() + 60_000) {
          await handleRefresh();
        }
        const me = await getMe();
        const normalizedUser = buildUserProfile(me, claims);
        setUser(normalizedUser);
        persist(normalizedUser, localStorage.getItem('authToken'));
        scheduleProactiveRefresh(localStorage.getItem('authToken'));
      } catch (e) {
        console.warn('Auth bootstrap failed; logging out', e);
        logout();
      }
    };
    bootstrap();
  }, []);

  const handleRefresh = async () => {
    const rt = localStorage.getItem('refreshToken');
    if (!rt) {
      logout();
      return;
    }
    try {
      const res = await refreshAccessToken(rt);
      const decoded = jwtDecode(res.access_token);
      const normalizedUser = buildUserProfile(res.user, decoded);
      setToken(res.access_token);
      setUser(normalizedUser);
      persist(normalizedUser, res.access_token, res.refresh_token);
      scheduleProactiveRefresh(res.access_token);
    } catch (e) {
      console.error('Auth refresh failed; logging out', e);
      logout();
    }
  };

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    login,
    logout,
    refresh: handleRefresh,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
