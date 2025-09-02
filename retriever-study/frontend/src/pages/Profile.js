import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { updateUser, getJoinedGroups } from '../services/api';
import './Profile.css';

const Profile = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [profile, setProfile] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [joinedGroups, setJoinedGroups] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && user.sub) {
      setLoading(true);
      // TODO: This should eventually be a single API call to get a user's full profile
      const fullUserProfile = {
        name: user.name,
        email: user.email,
        picture: user.picture,
        bio: user.bio || '',
        courses: user.courses || [],
        prefs: user.prefs || { studyStyle: [], timeSlots: [], locations: [] }
      };
      setProfile(fullUserProfile);

      // Fetch joined groups from the backend
      getJoinedGroups(user.sub)
        .then(groups => {
          setJoinedGroups(groups || []);
        })
        .catch(err => {
          console.error("Failed to fetch joined groups", err);
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [user]);

  const handleEditToggle = () => {
    if (editMode) {
      setEditData({});
    } else {
      setEditData({ bio: profile.bio });
    }
    setEditMode(!editMode);
  };

  const handleInputChange = (field, value) => {
    setEditData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updatedProfileData = await updateUser(user.sub, { bio: editData.bio });
      setProfile(prev => ({ ...prev, ...updatedProfileData }));
      setEditMode(false);
      setEditData({});
    } catch (err) {
      console.error('Failed to update profile:', err);
      alert('Failed to update profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div>Loading profile...</div>;
  }

  if (!profile) {
    return <div>Please log in to view your profile.</div>;
  }

  return (
    <div className="profile-container">
      <div className="profile-header">
        <h1 className="profile-title">MY PROFILE</h1>
        <button 
          className={`edit-btn ${editMode ? 'cancel' : ''}`}
          onClick={handleEditToggle}
          disabled={saving}
        >
          {editMode ? 'CANCEL' : 'EDIT PROFILE'}
        </button>
      </div>

      <div className="profile-content">
        <div className="profile-section personal-info">
          <h2 className="section-title">PERSONAL INFORMATION</h2>
          <div className="info-grid">
            <div className="info-item">
              <label className="info-label">NAME</label>
              <p className="info-value">{profile.name}</p>
            </div>
            <div className="info-item">
              <label className="info-label">EMAIL</label>
              <p className="info-value">{profile.email}</p>
            </div>
            <div className="info-item full-width">
              <label className="info-label">BIO</label>
              {editMode ? (
                <textarea
                  value={editData.bio || ''}
                  onChange={(e) => handleInputChange('bio', e.target.value)}
                  className="edit-textarea"
                  rows={3}
                />
              ) : (
                <p className="info-value">{profile.bio || 'Tell us about yourself!'}</p>
              )}
            </div>
          </div>
          {editMode && (
            <div className="edit-actions">
              <button 
                className="save-btn"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? 'SAVING...' : 'SAVE CHANGES'}
              </button>
            </div>
          )}
        </div>
        
        <div className="profile-section joined-groups">
          <h2 className="section-title">MY GROUPS ({joinedGroups.length})</h2>
          {joinedGroups.length === 0 ? (
            <div className="empty-groups">
              <p>You haven't joined any groups yet.</p>
              <button 
                className="browse-groups-btn"
                onClick={() => navigate('/groups')}
              >
                BROWSE GROUPS
              </button>
            </div>
          ) : (
            <div className="groups-list">
              {joinedGroups.map(group => (
                <div 
                  key={group.id}
                  className="group-item"
                  onClick={() => navigate(`/group/${group.id}`)}
                >
                  <div className="group-info">
                    <h3 className="group-name">{group.name}</h3>
                    <div className="group-details">
                      <span className="group-course">{group.subject}</span>
                      <span className="group-members">{group.memberCount || 0} members</span>
                    </div>
                  </div>
                  <div className="group-arrow">→</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;
