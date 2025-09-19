import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Navigation.css';

const Navigation = () => {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  const navItems = [
    { path: '/groups', label: 'ALL GROUPS', protected: false },
    { path: '/my-groups', label: 'YOUR GROUPS', protected: true },
    { path: '/recommendations', label: 'RECOMMENDED', protected: true },
    { path: '/search', label: 'SEARCH', protected: false },
    { path: '/profile', label: 'PROFILE', protected: true },
  ];

  return (
    <nav className="navigation">
      <div className="navigation-container">
        <ul className="nav-list">
          {navItems
            .filter(item => isAuthenticated || !item.protected)
            .map((item) => (
              <li key={item.path} className="nav-item">
                <Link
                  to={item.path}
                  className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
                  aria-label={item.protected ? `${item.label} (requires login)` : item.label}
                >
                  {item.label}
                  {(!isAuthenticated && item.protected) ? ' 🔒' : ''}
                </Link>
              </li>
            ))}
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;
