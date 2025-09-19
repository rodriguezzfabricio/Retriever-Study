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

  return (
    <div className="group-card" onClick={handleCardClick}>
      <div className="group-card-content">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h3 className="group-name" style={{ margin: 0 }}>{group.name}</h3>
          {isFull && (
            <span className="badge" aria-label="Group is full" title="Group is full" style={{ background: '#eee', color: '#444', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>FULL</span>
          )}
        </div>
        <p className="group-description">{group.description}</p>
        <div className="group-meta">
          <span className="group-subject" aria-label="Course code">{group.subject}</span>
          <span className="group-members" aria-label="Capacity">{capacity ? `${memberCount}/${capacity}` : memberCount} members</span>
        </div>
        <div className="group-meta" style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
          {group.location && <span aria-label="Location">📍 {group.location}</span>}
          {schedule && <span aria-label="Schedule" style={{ marginLeft: 10 }}>🗓 {schedule}</span>}
          {group.ownerId && <span aria-label="Owner" style={{ marginLeft: 10 }}>👤 {String(group.ownerId).slice(0, 6)}</span>}
        </div>
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
