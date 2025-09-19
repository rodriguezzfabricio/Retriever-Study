import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthProvider } from './context/AuthContext';
import './index.css';
import App from './App';

// --- SENIOR ENGINEER DEBUGGING ---
console.log('Checking for Google Client ID:', process.env.REACT_APP_GOOGLE_CLIENT_ID);
// --- END DEBUGGING ---

const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement);
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const errorContainerStyle = {
  minHeight: '100vh',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: 'Inter, system-ui, sans-serif',
  gap: '0.75rem',
  padding: '0 1.5rem',
  textAlign: 'center',
};

const ConfigError = ({ message }) => (
  <div style={errorContainerStyle}>
    <h1>Retriever Study</h1>
    <p>{message}</p>
  </div>
);

async function resolveGoogleClientId() {
  if (process.env.REACT_APP_GOOGLE_CLIENT_ID) {
    return process.env.REACT_APP_GOOGLE_CLIENT_ID;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/google/config`);
    if (!response.ok) {
      throw new Error(`API responded with status ${response.status}`);
    }
    const data = await response.json();
    return data.client_id || data.clientId || null;
  } catch (error) {
    console.error('Failed to load Google OAuth client id from backend', error);
    return null;
  }
}

async function bootstrap() {
  const clientId = await resolveGoogleClientId();

  if (!clientId) {
    root.render(
      <React.StrictMode>
        <ConfigError message="Google Sign-In is temporarily unavailable. Please contact support." />
      </React.StrictMode>
    );
    return;
  }

  root.render(
    <React.StrictMode>
      <GoogleOAuthProvider clientId={clientId}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </GoogleOAuthProvider>
    </React.StrictMode>
  );
}

bootstrap();
