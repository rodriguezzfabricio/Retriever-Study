import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getGroupDetails, getMessages, summarizeChat, joinGroup } from '../services/api';
import { connectSocket, disconnectSocket, joinRoom, leaveRoom, sendChatMessage, onNewMessage } from '../services/socket';
import './GroupDetail.css';

const GroupDetail = () => {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const messagesEndRef = useRef(null);
  
  const [group, setGroup] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const [summary, setSummary] = useState([]);
  const [showSummary, setShowSummary] = useState(false);

  const isMember = group && user ? group.members.includes(user.sub) : false;

  // Effect for fetching initial data
  useEffect(() => {
    const fetchGroupData = async () => {
      setLoading(true);
      setError(null);
      try {
        const groupData = await getGroupDetails(groupId);
        setGroup(groupData);
        const messagesData = await getMessages(groupId, 100);
        setMessages(messagesData);
      } catch (err) {
        console.error('Failed to load group data:', err);
        setError('Failed to load group details.');
      } finally {
        setLoading(false);
      }
    };
    fetchGroupData();
  }, [groupId]);

  // Effect for managing WebSocket connection
  useEffect(() => {
    if (isMember) {
      connectSocket();
      joinRoom(groupId);

      onNewMessage((newMessage) => {
        setMessages(prevMessages => [...prevMessages, newMessage]);
      });

      // Cleanup on component unmount
      return () => {
        leaveRoom(groupId);
        disconnectSocket();
      };
    }
  }, [groupId, isMember]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !isAuthenticated) return;
    
    const messageData = {
      groupId: groupId,
      senderId: user.sub,
      senderName: user.name,
      content: newMessage.trim()
    };
    
    // Send message via WebSocket instead of HTTP API
    sendChatMessage(messageData);
    setNewMessage('');
  };

  const handleSummarizeChat = async () => {
    try {
      setShowSummary(true);
      const summaryData = await summarizeChat(groupId);
      setSummary(summaryData.bullets || []);
    } catch (err) {
      console.error('Failed to get summary:', err);
      setSummary(['Failed to generate summary.']);
    }
  };

  const handleJoinGroup = async () => {
    if (!isAuthenticated) return;
    try {
      await joinGroup(groupId, user.sub);
      const updatedGroupData = await getGroupDetails(groupId);
      setGroup(updatedGroupData);
    } catch (err) {
      console.error('Failed to join group:', err);
      alert('Failed to join group.');
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return <div className="loading-state-full-page"><div className="loading-spinner"></div></div>;
  }

  if (error) {
    return <div className="error-state-full-page"><h2>ERROR</h2><p>{error}</p></div>;
  }

  return (
    <div className="group-detail-container">
      <div className="group-header">
        <button className="back-btn" onClick={() => navigate('/groups')}>← BACK</button>
        <div className="group-info">
          <h1 className="group-title">{group.name}</h1>
          <p className="group-description">{group.description}</p>
        </div>
        <div className="group-actions">
          <button className="summarize-btn" onClick={handleSummarizeChat}>SUMMARIZE</button>
          {!isMember && <button className="join-group-btn" onClick={handleJoinGroup}>JOIN</button>}
        </div>
      </div>

      {showSummary && (
        <div className="summary-panel">
          <div className="summary-header"><h3>CHAT SUMMARY</h3><button onClick={() => setShowSummary(false)}>×</button></div>
          <ul>{summary.map((bullet, i) => <li key={i}>{bullet}</li>)}</ul>
        </div>
      )}

      {!isMember ? (
        <div className="join-prompt">
          <p>Join this group to see the chat.</p>
          <button onClick={handleJoinGroup}>JOIN GROUP</button>
        </div>
      ) : (
        <div className="chat-container">
          <div className="messages-container">
            {messages.map((msg) => (
              <div key={msg.id} className={`message ${msg.senderId === user.sub ? 'own-message' : 'other-message'}`}>
                <div className="message-header">
                  <span className="sender-name">{msg.senderId === user.sub ? 'You' : msg.senderName}</span>
                  <span className="message-time">{formatTimestamp(msg.timestamp)}</span>
                </div>
                <div className="message-content">{msg.content}</div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          <form className="message-form" onSubmit={handleSendMessage}>
            <input type="text" value={newMessage} onChange={(e) => setNewMessage(e.target.value)} placeholder="Type a message..." />
            <button type="submit" disabled={!newMessage.trim()}>SEND</button>
          </form>
        </div>
      )}
    </div>
  );
};

export default GroupDetail;
