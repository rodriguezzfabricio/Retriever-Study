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

  return (
    <div className="group-card" onClick={handleCardClick}>
      <div className="group-card-content">
        <h3 className="group-name">{group.name}</h3>
        <p className="group-description">{group.description}</p>
        <div className="group-meta">
          <span className="group-subject">{group.subject}</span>
          <span className="group-members">{group.memberCount || 0} members</span>
        </div>
      </div>
      <div className="group-card-actions">
        {!isJoined ? (
          <button 
            className="join-btn"
            onClick={handleJoinClick}
          >
            JOIN
          </button>
        ) : (
          <span className="joined-status">JOINED</span>
        )}
      </div>
    </div>
  );
};

export default GroupCard;