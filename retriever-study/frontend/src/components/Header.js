import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Header.css';

const Header = ({ onSearch }) => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [term, setTerm] = useState('');

  const handleLogout = () => {
    logout();
    navigate('/login'); // Redirect to login page after logout
  };

  const submitSearch = (e) => {
    e && e.preventDefault();
    const q = term.trim();
    if (!q) return;
    if (onSearch) onSearch(q);
    navigate('/search');
  };

  const pathname = location.pathname;
  const showSearchBar = (
    pathname === '/groups' ||
    pathname === '/search' ||
    pathname === '/recommendations'
  );

  return (
    <header className="header">
      <div className="header-container">
        {/* Logo - Zara style bold branding */}
        <Link to="/" className="header-logo">
          <h1 className="logo-text">RETRIEVER STUDY</h1>
        </Link>

        {/* Search Bar - Center like Zara */}
        {showSearchBar && (
          <div className="header-search">
            <form onSubmit={submitSearch} role="search" aria-label="Search groups">
              <input
                className="search-input"
                type="search"
                placeholder="Search groups (course, topic, etc.)"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                aria-label="Search groups"
              />
              <button type="submit" className="search-button" aria-label="Search">
                🔍
              </button>
            </form>
          </div>
        )}

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
