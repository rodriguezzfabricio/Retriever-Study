import React, { useState, useEffect } from 'react';
import GroupCard from '../components/GroupCard';
import { getAllGroups, getGroupsByCourse, getRecommendations, searchGroups, joinGroup, createGroup, getJoinedGroups } from '../services/api';
import { useAuth } from '../context/AuthContext'; // Import the auth hook
import './GroupsList.css';
import CreateGroupModal from '../components/CreateGroupModal';
import usePageTitle from '../hooks/usePageTitle';

const GroupsList = ({ 
  searchQuery = '', 
  showRecommendations = false, 
  showSearch = false,
  showMyGroups = false,
}) => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [joinedGroups, setJoinedGroups] = useState(new Set());
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  const { user, isAuthenticated } = useAuth();
  const userId = user?.userId || user?.id || null; // internal id for profile updates
  const memberId = user?.sub || user?.googleSub || null; // google id for membership checks
  const defaultCourse = (user?.courses && user.courses[0]) || 'CS101';

  // Set page title based on the current view
  const titlePrefix = (() => {
    if (showRecommendations) return 'Recommended Groups';
    if (showMyGroups) return 'Your Groups';
    if (showSearch) return searchQuery ? `Search: ${searchQuery}` : 'Search';
    return 'All Groups';
  })();
  usePageTitle(titlePrefix);

  useEffect(() => {
    // Only load groups if we are not in recommendation mode OR if the user is authenticated
    if (!showRecommendations || isAuthenticated) {
      loadGroups();
    }
  }, [searchQuery, showRecommendations, showSearch, userId]);

  const loadGroups = async () => {
    setLoading(true);
    setError(null);
    
    try {
      let groupsData = [];
      
      if (showRecommendations) {
        if (isAuthenticated && userId) {
          // Load AI-powered recommendations for the logged-in user
          groupsData = await getRecommendations(userId, 10);
        } else {
          // Don't load recommendations if user is not logged in
          groupsData = []; 
        }
      } else if (showMyGroups) {
        if (isAuthenticated && (memberId || userId)) {
          groupsData = await getJoinedGroups(memberId || userId);
        } else {
          groupsData = [];
        }
      } else if (showSearch && searchQuery.trim()) {
        // Load search results
        groupsData = await searchGroups(searchQuery, 20);
      } else {
        // Load all groups across courses (real "All Groups")
        groupsData = await getAllGroups(0, 50);
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
    if (!isAuthenticated || !userId) {
      // Or redirect to login
      console.error('User must be logged in to join a group');
      return;
    }
    try {
      await joinGroup(groupId, memberId || userId); // Backend ignores body, but pass member id
      setJoinedGroups(prev => new Set([...prev, groupId]));
      await loadGroups();
      // Seamless post-join: land in the group chat
      window.location.assign(`/group/${groupId}`);
    } catch (err) {
      console.error('Failed to join group:', err);
    }
  };

  const handleOpenCreate = () => {
    if (!isAuthenticated) {
      alert('Please sign in to create a group.');
      return;
    }
    setShowCreateModal(true);
  };

  const handleCreate = async (payload) => {
    try {
      const created = await createGroup(payload, userId);
      setShowCreateModal(false);
      await loadGroups();
      // Navigate straight to the new group for a smoother flow
      if (created && (created.groupId || created.id)) {
        const newId = created.groupId || created.id;
        window.location.assign(`/group/${newId}`);
      }
    } catch (err) {
      console.error('Failed to create group:', err);
      alert(err?.data?.detail || 'Failed to create group.');
    }
  };

  const getPageTitle = () => {
    if (showRecommendations) return 'RECOMMENDED FOR YOU';
    if (showMyGroups) return 'YOUR GROUPS';
    if (showSearch) return `SEARCH RESULTS${searchQuery ? ` FOR "${searchQuery}"` : ''}`;
    return 'ALL STUDY GROUPS';
  };

  const getEmptyMessage = () => {
    if (showRecommendations) {
      return isAuthenticated ? 'No recommendations available. Try updating your profile.' : 'Please log in to see your recommendations.';
    }
    if (showMyGroups) return 'You have not joined any groups yet.';
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
        {/* Always allow creating a group when authenticated */}
        {isAuthenticated && (
          <button className="retry-btn" onClick={handleOpenCreate} style={{ marginLeft: 'auto' }}>
            CREATE GROUP
          </button>
        )}
      </div>
      
      {groups.length === 0 ? (
        <div className="empty-state">
          {/* Simple friendly illustration */}
          <svg width="120" height="80" viewBox="0 0 120 80" aria-hidden="true" style={{marginBottom: 14}}>
            <rect x="10" y="20" width="100" height="40" rx="8" fill="#f5f5f5" />
            <circle cx="30" cy="40" r="8" fill="#e0e0e0" />
            <rect x="48" y="34" width="50" height="12" rx="6" fill="#e6e6e6" />
          </svg>
          <p>{getEmptyMessage()}</p>
          {isAuthenticated && !showMyGroups && (
            <button className="retry-btn" onClick={handleOpenCreate}>START THE FIRST GROUP</button>
          )}
          {!isAuthenticated && !showMyGroups && <p>Please sign in to create a group.</p>}
          {showMyGroups && <p className="helper-text">Browse all groups or get recommendations to find your first one.</p>}
        </div>
      ) : (
        <div className="groups-grid">
          {groups.map((group) => {
            const id = group.groupId || group.id;
            const alreadyMember = Array.isArray(group.members) && (memberId ? group.members.includes(memberId) : false);
            return (
              <GroupCard
                key={id}
                group={{
                  id,
                  name: group.title,
                  description: group.description,
                  subject: group.courseCode,
                  memberCount: group.members ? group.members.length : 0
                }}
                onJoin={handleJoinGroup}
                isJoined={alreadyMember || joinedGroups.has(id)}
              />
            );
          })}
        </div>
      )}
      
      {showSearch && groups.length === 0 && !searchQuery.trim() && (
        <div className="search-prompt">
          <p>Enter a search term to find study groups</p>
        </div>
      )}

      <CreateGroupModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleCreate}
        defaultCourse={defaultCourse}
      />
    </div>
  );
};

export default GroupsList;
