import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import GroupsList from './pages/GroupsList';
import GroupDetail from './pages/GroupDetail';
import Profile from './pages/Profile';
import Login from './pages/Login';
import ProtectedRoute from './components/ProtectedRoute'; // Import the guard

function App() {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (query) => {
    setSearchQuery(query);
  };

  return (
    <Layout onSearch={handleSearch}>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Navigate to="/groups" replace />} />
        <Route path="/login" element={<Login />} />
        <Route 
          path="/groups" 
          element={<GroupsList searchQuery={searchQuery} />} 
        />
        <Route 
          path="/search" 
          element={<GroupsList showSearch={true} searchQuery={searchQuery} />} 
        />
        <Route path="/help" element={<div>Help page - Coming soon!</div>} />

        {/* Protected Routes */}
        <Route 
          path="/recommendations" 
          element={
            <ProtectedRoute>
              <GroupsList showRecommendations={true} />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/group/:groupId" 
          element={
            <ProtectedRoute>
              <GroupDetail />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/profile" 
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Layout>
  );
}

export default App;