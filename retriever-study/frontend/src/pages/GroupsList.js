import React, { useState, useEffect } from 'react';
import GroupCard from '../components/GroupCard';
import { getGroupsByCourse, getRecommendations, searchGroups, joinGroup } from '../services/api';
import { useAuth } from '../context/AuthContext'; // Import the auth hook
import './GroupsList.css';

const GroupsList = ({ 
  searchQuery = '', 
  showRecommendations = false, 
  showSearch = false 
}) => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [joinedGroups, setJoinedGroups] = useState(new Set());
  
  const { user, isAuthenticated } = useAuth(); // Get real user data
  const defaultCourse = 'CS101';

  useEffect(() => {
    // Only load groups if we are not in recommendation mode OR if the user is authenticated
    if (!showRecommendations || isAuthenticated) {
      loadGroups();
    }
  }, [searchQuery, showRecommendations, showSearch, user]); // Add user to dependency array

  const loadGroups = async () => {
    setLoading(true);
    setError(null);
    
    try {
      let groupsData = [];
      
      if (showRecommendations) {
        if (isAuthenticated && user?.sub) {
          // Load AI-powered recommendations for the logged-in user
          groupsData = await getRecommendations(user.sub, 10);
        } else {
          // Don't load recommendations if user is not logged in
          groupsData = []; 
        }
      } else if (showSearch && searchQuery.trim()) {
        // Load search results
        groupsData = await searchGroups(searchQuery, 20);
      } else {
        // Load all groups for default course
        groupsData = await getGroupsByCourse(defaultCourse);
      }
      
      setGroups(groupsData);
    } catch (err) {
      console.error('Failed to load groups:', err);
      setError(err.message || 'Failed to load groups');
    } finally {
      setLoading(false);
    }
  };

  const handleJoinGroup = async (groupId) => {
    if (!isAuthenticated || !user?.sub) {
      // Or redirect to login
      console.error('User must be logged in to join a group');
      return;
    }
    try {
      await joinGroup(groupId, user.sub); // Use real user ID
      setJoinedGroups(prev => new Set([...prev, groupId]));
      await loadGroups();
    } catch (err) {
      console.error('Failed to join group:', err);
    }
  };

  const getPageTitle = () => {
    if (showRecommendations) return 'RECOMMENDED FOR YOU';
    if (showSearch) return `SEARCH RESULTS${searchQuery ? ` FOR "${searchQuery}"` : ''}`;
    return 'ALL STUDY GROUPS';
  };

  const getEmptyMessage = () => {
    if (showRecommendations) {
      return isAuthenticated ? 'No recommendations available. Try updating your profile.' : 'Please log in to see your recommendations.';
    }
    if (showSearch) return 'No groups found matching your search.';
    return 'No study groups available for this course.';
  };

  if (loading) {
    return (
      <div className="groups-list-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>LOADING GROUPS...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="groups-list-container">
        <div className="error-state">
          <h2>ERROR LOADING GROUPS</h2>
          <p>{error}</p>
          <button 
            className="retry-btn"
            onClick={loadGroups}
          >
            TRY AGAIN
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="groups-list-container">
      <div className="groups-list-header">
        <h1 className="groups-list-title">{getPageTitle()}</h1>
        {groups.length > 0 && (
          <p className="groups-count">{groups.length} GROUP{groups.length !== 1 ? 'S' : ''} FOUND</p>
        )}
      </div>
      
      {groups.length === 0 ? (
        <div className="empty-state">
          <p>{getEmptyMessage()}</p>
        </div>
      ) : (
        <div className="groups-grid">
          {groups.map((group) => (
            <GroupCard
              key={group.groupId || group.id}
              group={{
                id: group.groupId || group.id,
                name: group.title,
                description: group.description,
                subject: group.courseCode,
                memberCount: group.members ? group.members.length : 0
              }}
              onJoin={handleJoinGroup}
              isJoined={joinedGroups.has(group.groupId || group.id)}
            />
          ))}
        </div>
      )}
      
      {showSearch && !searchQuery.trim() && (
        <div className="search-prompt">
          <p>Enter a search term to find study groups</p>
        </div>
      )}
    </div>
  );
};

export default GroupsList;
