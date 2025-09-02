
import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode'; // Corrected import

const AuthContext = createContext(null);

// Helper function to get initial state from localStorage
const getInitialState = () => {
  try {
    const token = localStorage.getItem('authToken');
    if (token) {
      const user = jwtDecode(token); // Corrected usage
      // Check if token is expired
      if (user.exp * 1000 > Date.now()) {
        return { token, user };
      }
    }
  } catch (error) {
    console.error("Error reading from localStorage", error);
  }
  return { token: null, user: null };
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(getInitialState().token);
  const [user, setUser] = useState(getInitialState().user);

  const login = (userData, authToken) => {
    console.log("AuthContext: Logging in user", userData);
    setUser(userData);
    setToken(authToken);
    localStorage.setItem('authToken', authToken);
  };

  const logout = () => {
    console.log("AuthContext: Logging out user");
    setUser(null);
    setToken(null);
    localStorage.removeItem('authToken');
  };

  // This effect will run on component mount to check for token expiration
  useEffect(() => {
    const tokenFromStorage = localStorage.getItem('authToken');
    if (tokenFromStorage) {
      try {
        const decodedUser = jwtDecode(tokenFromStorage); // Corrected usage
        if (decodedUser.exp * 1000 < Date.now()) {
          console.log("AuthContext: Token expired, logging out.");
          logout();
        }
      } catch (error) {
        console.error("Invalid token in storage", error);
        logout();
      }
    }
  }, []);

  const value = {
    user,
    token,
    isAuthenticated: !!user,
    login,
    logout,
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
