import React from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { exchangeGoogleToken, ApiError } from '../services/api';

import './Login.css';
import usePageTitle from '../hooks/usePageTitle';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  usePageTitle('Login');

  const handleLoginSuccess = async (credentialResponse) => {
    try {
      const idToken = credentialResponse?.credential;
      if (!idToken) {
        throw new Error('No credential returned from Google.');
      }

      const authResponse = await exchangeGoogleToken(idToken);

      // Use our application's access token and user profile
      login(authResponse);
      navigate('/groups');
    } catch (error) {
      if (error instanceof ApiError) {
        console.error('Google login rejected by backend:', error);
        alert(error.data?.detail || 'Unable to sign in with your UMBC account.');
      } else {
        console.error('Google login failed:', error);
        alert('Sign-in failed. Please try again.');
      }
    }
  };

  const handleLoginError = (error) => {
    console.error('Google Login Failed', error);
    alert('We could not reach Google Sign-In. Please retry.');
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
