import React, { useState, useEffect, useMemo, useRef } from 'react';
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
  const [totalCount, setTotalCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [joinedGroups, setJoinedGroups] = useState(new Set());
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const pageSize = 20;
  const pagesCache = useRef(new Map()); // offset -> items
  const [filters, setFilters] = useState({ courseCode: '', tags: '', schedule: '', hideFull: false });

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
    // Reset pagination when the view context changes
    setGroups([]);
    setOffset(0);
    pagesCache.current.clear();
    setTotalCount(null);
    // Only load groups if we are not in recommendation mode OR if the user is authenticated
    if (!showRecommendations || isAuthenticated) {
      loadGroups(0);
    }
  }, [searchQuery, showRecommendations, showSearch, userId]);

  const loadGroups = async (startOffset = offset) => {
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
        // Load all groups across courses (real "All Groups") with pagination
        // Use cache to avoid refetching the same page
        if (pagesCache.current.has(startOffset)) {
          const cached = pagesCache.current.get(startOffset);
          groupsData = cached.items;
          setTotalCount(cached.total ?? totalCount);
        } else {
          const { items, total } = await getAllGroups(startOffset, pageSize);
          pagesCache.current.set(startOffset, { items, total });
          groupsData = items;
          setTotalCount(total ?? totalCount);
        }
      }
      
      if (!showRecommendations && !showMyGroups && !showSearch) {
        // Paginated view: merge pages
        setGroups(prev => {
          if (startOffset === 0) return groupsData;
          return [...prev, ...groupsData];
        });
      } else {
        setGroups(groupsData);
      }
    } catch (err) {
      console.error('Failed to load groups:', err);
      setError(err.message || 'Failed to load groups');
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (loading || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const nextOffset = offset + pageSize;
      await loadGroups(nextOffset);
      setOffset(nextOffset);
    } catch (e) {
      console.error('Failed to load more groups', e);
    } finally {
      setIsLoadingMore(false);
    }
  };

  // Virtualization: compute a visible slice to render for performance
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const itemHeight = 140; // px, approximate card height
  const viewportHeight = 600; // px default viewport

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  const filteredGroups = useMemo(() => {
    const base = groups || [];
    const byCourse = filters.courseCode ? base.filter(g => (g.courseCode || '').toLowerCase().includes(filters.courseCode.toLowerCase())) : base;
    const tags = (filters.tags || '').split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
    const byTags = tags.length > 0 ? byCourse.filter(g => Array.isArray(g.tags) && tags.every(t => g.tags.map(x => String(x).toLowerCase()).includes(t))) : byCourse;
    const sched = (filters.schedule || '').trim().toLowerCase();
    const bySchedule = sched ? byTags.filter(g => (g.timePrefs || []).some(tp => String(tp).toLowerCase().includes(sched))) : byTags;
    const byCapacity = filters.hideFull ? bySchedule.filter(g => {
      const max = g.maxMembers || 0; const count = Array.isArray(g.members) ? g.members.length : 0; return !(max && count >= max);
    }) : bySchedule;
    return byCapacity;
  }, [groups, filters]);

  const virtual = useMemo(() => {
    if (showRecommendations || showMyGroups || showSearch) {
      return { start: 0, end: filteredGroups.length, padTop: 0, padBottom: 0 };
    }
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - 5);
    const visibleCount = Math.ceil(viewportHeight / itemHeight) + 10;
    const endIndex = Math.min(filteredGroups.length, startIndex + visibleCount);
    const padTop = startIndex * itemHeight;
    const padBottom = Math.max(0, (filteredGroups.length - endIndex) * itemHeight);
    return { start: startIndex, end: endIndex, padTop, padBottom };
  }, [scrollTop, filteredGroups, showRecommendations, showMyGroups, showSearch]);

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
            onClick={() => loadGroups(0)}
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
        {filteredGroups.length > 0 && (
          <p className="groups-count">
            {totalCount ? `${filteredGroups.length} of ${totalCount}` : `${filteredGroups.length}`} GROUP{filteredGroups.length !== 1 ? 'S' : ''} LOADED
          </p>
        )}
        {/* Always allow creating a group when authenticated */}
        {isAuthenticated && (
          <button className="retry-btn" onClick={handleOpenCreate} style={{ marginLeft: 'auto' }}>
            CREATE GROUP
          </button>
        )}
      </div>
      
      {/* Filters */}
      {!showRecommendations && !showMyGroups && (
        <div className="filters" style={{ display: 'flex', gap: 12, padding: '8px 0', alignItems: 'center' }}>
          <input
            aria-label="Filter by course code"
            placeholder="Course (e.g., CMSC201)"
            value={filters.courseCode}
            onChange={(e) => setFilters({ ...filters, courseCode: e.target.value })}
          />
          <input
            aria-label="Filter by tags"
            placeholder="Tags (comma-separated)"
            value={filters.tags}
            onChange={(e) => setFilters({ ...filters, tags: e.target.value })}
          />
          <input
            aria-label="Filter by schedule"
            placeholder="Schedule (e.g., Fri, evening)"
            value={filters.schedule}
            onChange={(e) => setFilters({ ...filters, schedule: e.target.value })}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={filters.hideFull}
              onChange={(e) => setFilters({ ...filters, hideFull: e.target.checked })}
              aria-label="Hide full groups"
            />
            Hide full groups
          </label>
          <button className="retry-btn" onClick={() => setFilters({ courseCode: '', tags: '', schedule: '', hideFull: false })} aria-label="Clear filters">CLEAR</button>
        </div>
      )}

      {filteredGroups.length === 0 ? (
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
        <div
          ref={containerRef}
          style={{ maxHeight: showRecommendations || showMyGroups || showSearch ? 'none' : `${viewportHeight}px`, overflowY: showRecommendations || showMyGroups || showSearch ? 'visible' : 'auto' }}
        >
          {/* Virtual padding to keep scrollbar proportional */}
          {!showRecommendations && !showMyGroups && !showSearch && (
            <div style={{ height: virtual.padTop }} />
          )}
          <div className="groups-grid">
            {(showRecommendations || showMyGroups || showSearch ? filteredGroups : filteredGroups.slice(virtual.start, virtual.end)).map((group) => {
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
                    memberCount: group.members ? group.members.length : 0,
                    maxMembers: group.maxMembers,
                    location: group.location,
                    timePrefs: group.timePrefs || [],
                    ownerId: group.ownerId,
                    isFull: group.isFull || (group.maxMembers ? (group.members || []).length >= group.maxMembers : false),
                  }}
                  onJoin={handleJoinGroup}
                  isJoined={alreadyMember || joinedGroups.has(id)}
                />
              );
            })}
          </div>
          {!showRecommendations && !showMyGroups && !showSearch && (
            <>
              <div style={{ height: virtual.padBottom }} />
              {(totalCount === null || filteredGroups.length < totalCount) && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '16px' }}>
                  <button className="retry-btn" onClick={loadMore} disabled={isLoadingMore} aria-label="Load more groups">
                    {isLoadingMore ? 'LOADING...' : 'LOAD MORE'}
                  </button>
                </div>
              )}
            </>
          )}
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
