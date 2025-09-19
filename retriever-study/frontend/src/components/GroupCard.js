import React from 'react';
import { useNavigate } from 'react-router-dom';
import './GroupCard.css';

const GroupCard = ({ group, onJoin, isJoined = false }) => {
  const navigate = useNavigate();

  const handleCardClick = () => {
    navigate(`/group/${group.id}`);
  };

  const handleJoinClick = (e) => {
    e.stopPropagation();
    onJoin(group.id);
  };
  const handleOpenClick = (e) => {
    e.stopPropagation();
    navigate(`/group/${group.id}`);
  };

  const memberCount = group.memberCount || 0;
  const capacity = group.maxMembers || null;
  const isFull = group.isFull || (capacity ? memberCount >= capacity : false);
  const schedule = Array.isArray(group.timePrefs) ? group.timePrefs.join(', ') : '';
  const studyStyles = Array.isArray(group.studyStyle) ? group.studyStyle : [];
  const activityScore = typeof group.recentActivityScore === 'number' ? group.recentActivityScore : 0;
  const hasTrendingBadge = activityScore >= 4.5;
  const highlightBadges = [];
  if (hasTrendingBadge) highlightBadges.push('Trending');
  if (group.fillingUpFast) highlightBadges.push('Filling up fast');
  if (group.startsSoon) highlightBadges.push('Starting this week');
  const mutualConnections = typeof group.mutualConnections === 'number' ? group.mutualConnections : 0;

  const renderBadge = (label) => (
    <span className="badge" key={label} style={{ background: '#fcead6', color: '#8b4b00' }}>{label}</span>
  );

  return (
    <div className="group-card" onClick={handleCardClick}>
      <div className="group-card-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h3 className="group-name" style={{ margin: 0 }}>{group.name}</h3>
          {isFull && (
            <span className="badge" aria-label="Group is full" title="Group is full" style={{ background: '#eee', color: '#444', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>FULL</span>
          )}
          {hasTrendingBadge && (
            <span className="badge" aria-label="Trending group" title="Trending group" style={{ background: '#ffe8d1', color: '#a2571b', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>🔥 TRENDING</span>
          )}
        </div>
        <p className="group-description">{group.description}</p>
        <div className="group-meta" style={{ flexWrap: 'wrap', gap: 6 }}>
          {group.department && <span className="group-department">🏫 {group.department}</span>}
          {group.difficulty && <span className="group-difficulty">🎯 {group.difficulty}</span>}
          {group.meetingType && <span className="group-meeting">🤝 {group.meetingType}</span>}
          {group.timeSlot && <span className="group-timeslot">🕒 {group.timeSlot}</span>}
          {group.groupSize && <span className="group-size">👥 {group.groupSize}</span>}
        </div>
        <div className="group-meta">
          <span className="group-subject" aria-label="Course code">{group.subject}</span>
          <span className="group-members" aria-label="Capacity">{capacity ? `${memberCount}/${capacity}` : memberCount} members</span>
        </div>
        <div className="group-meta" style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
          {group.location && <span aria-label="Location">📍 {group.location}</span>}
          {schedule && <span aria-label="Schedule" style={{ marginLeft: 10 }}>🗓 {schedule}</span>}
          {group.ownerId && <span aria-label="Owner" style={{ marginLeft: 10 }}>👤 {String(group.ownerId).slice(0, 6)}</span>}
          {mutualConnections > 0 && (
            <span aria-label="Mutual connections" style={{ marginLeft: 10 }}>🤝 {mutualConnections} mutual</span>
          )}
        </div>
        {studyStyles.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {studyStyles.map(style => (
              <span key={style} className="badge" style={{ background: '#eef2ff', color: '#30308d' }}>{style}</span>
            ))}
          </div>
        )}
        {highlightBadges.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {highlightBadges.map(renderBadge)}
          </div>
        )}
      </div>
      <div className="group-card-actions">
        {!isJoined ? (
          <button
            className="join-btn"
            onClick={handleJoinClick}
            aria-label={isFull ? 'Group is full' : 'Join group'}
            disabled={isFull}
            title={isFull ? 'Group is full' : 'Join group'}
          >
            {isFull ? 'FULL' : 'JOIN'}
          </button>
        ) : (
          <button className="join-btn" onClick={handleOpenClick} aria-label="Open group">OPEN</button>
        )}
      </div>
    </div>
  );
};

export default GroupCard;
