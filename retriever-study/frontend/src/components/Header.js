import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Header.css';

const Header = ({ onSearch }) => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login'); // Redirect to login page after logout
  };

  return (
    <header className="header">
      <div className="header-container">
        {/* Logo - Zara style bold branding */}
        <Link to="/" className="header-logo">
          <h1 className="logo-text">RETRIEVER STUDY</h1>
        </Link>

        {/* Search Bar - Center like Zara */}
        <div className="header-search">
          {/* Search functionality can be enhanced later */}
        </div>

        {/* Utility Links - Right side like Zara */}
        <nav className="header-nav">
          {isAuthenticated ? (
            <>
              <span className="header-link user-greeting">HELLO, {user?.name?.split(' ')[0] || ''}</span>
              <button onClick={handleLogout} className="header-link logout-button">LOG OUT</button>
            </>
          ) : (
            <>
              <Link to="/login" className="header-link">LOG IN</Link>
              <Link to="/help" className="header-link">HELP</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
};

export default Header;
