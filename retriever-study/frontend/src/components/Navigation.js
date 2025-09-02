import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

const Navigation = () => {
  const location = useLocation();

  const navItems = [
    { path: '/groups', label: 'ALL GROUPS' },
    { path: '/recommendations', label: 'RECOMMENDED' },
    { path: '/search', label: 'SEARCH' },
    { path: '/profile', label: 'PROFILE' },
  ];

  return (
    <nav className="navigation">
      <div className="navigation-container">
        <ul className="nav-list">
          {navItems.map((item) => (
            <li key={item.path} className="nav-item">
              <Link 
                to={item.path} 
                className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
              >
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
};

export default Navigation;