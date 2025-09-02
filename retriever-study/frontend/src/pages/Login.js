import React from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { jwtDecode } from 'jwt-decode'; // Corrected import

import './Login.css';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLoginSuccess = (credentialResponse) => {
    console.log('Google Login Success:', credentialResponse);

    // The credentialResponse object contains a JWT token called "credential".
    // We need to decode it to get the user's profile information (name, email, picture).
    const userProfile = jwtDecode(credentialResponse.credential); // Corrected usage
    console.log('Decoded JWT:', userProfile);

    // Here, we call the login function from our AuthContext.
    // We pass it the user's profile and the token itself.
    // In a real production app, we would first send this token to our own backend
    // to verify it. The backend would then return OUR OWN JWT token, which we would store.
    // For now, we'll simulate a successful login directly on the frontend.
    login(userProfile, credentialResponse.credential);

    // After successfully logging in, we redirect the user to the main groups page.
    navigate('/groups');
  };

  const handleLoginError = () => {
    console.error('Google Login Failed');
    // TODO: Show an error message to the user (e.g., a toast notification)
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1 className="login-title">Retriever Study</h1>
        <p className="login-subtitle">Sign in to find your study group</p>
        <div className="google-button-wrapper">
          <GoogleLogin
            onSuccess={handleLoginSuccess}
            onError={handleLoginError}
            useOneTap
            theme="outline"
            size="large"
          />
        </div>
      </div>
    </div>
  );
};

export default Login;
