import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// This component acts as a guard for our routes.
const ProtectedRoute = ({ children }) => {
  // 1. Get the authentication state from our custom hook.
  const { isAuthenticated } = useAuth();
  
  // 2. Get the current location.
  // We use this to redirect the user back to the page they were trying to access
  // after they successfully log in. This provides a better user experience.
  const location = useLocation();

  // 3. The Guard Logic
  if (!isAuthenticated) {
    // If the user is not authenticated, we redirect them to the /login page.
    // The `replace` prop is used to replace the current entry in the history stack,
    // so the user won't be able to click the "back" button to get back to the protected page.
    // The `state` prop passes the original location, so we can redirect back after login.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // 4. Render the children
  // If the user is authenticated, we render the component they were trying to access.
  // `children` will be the page component defined in our App.js routes (e.g., <Profile />).
  return children;
};

export default ProtectedRoute;
