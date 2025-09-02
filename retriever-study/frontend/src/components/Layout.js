import React from 'react';
import Header from './Header';
import Navigation from './Navigation';
import './Layout.css';

const Layout = ({ children, onSearch }) => {
  return (
    <div className="layout">
      <Header onSearch={onSearch} />
      <Navigation />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default Layout;