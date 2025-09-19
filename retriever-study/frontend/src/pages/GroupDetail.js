import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getGroupDetails, getMessages, summarizeChat, joinGroup, leaveGroup } from '../services/api';
import { connectSocket, disconnectSocket, joinRoom, leaveRoom, sendChatMessage, onNewMessage, onConnectionState, SOCKET_STATE } from '../services/socket';
import './GroupDetail.css';
import usePageTitle from '../hooks/usePageTitle';

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
  // note: remove unused 'sending' state to satisfy lint
  const [summary, setSummary] = useState([]);
  const [showSummary, setShowSummary] = useState(false);
  const [wsState, setWsState] = useState(SOCKET_STATE.DISCONNECTED);

  const isMember = group && user ? (
    (Array.isArray(group.members) && (
      group.members.includes(user.sub) ||
      (user.id && group.members.includes(user.id)) ||
      (user.userId && group.members.includes(user.userId))
    ))
  ) : false;

  // Title should reflect the group name when known
  usePageTitle(group?.name ? `Group: ${group.name}` : 'Group');

  // Effect for fetching initial data
  useEffect(() => {
    const fetchGroupData = async () => {
      setLoading(true);
      setError(null);
      try {
        const groupData = await getGroupDetails(groupId);
        setGroup(groupData);
        // Don't fetch messages here - let WebSocket handle it
        // This prevents duplicate messages when WebSocket sends history
        setMessages([]);
      } catch (err) {
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

      const unsubscribeMsg = onNewMessage((newMessage) => {
        setMessages(prevMessages => {
          // Check for duplicates based on message ID
          const isDuplicate = prevMessages.some(msg => msg.id === newMessage.id);
          if (isDuplicate) {
            return prevMessages;
          }
          return [...prevMessages, newMessage];
        });
      }, groupId);
      const unsubscribeState = onConnectionState(groupId, setWsState);

      // Cleanup on component unmount
      return () => {
        try { unsubscribeMsg && unsubscribeMsg(); } catch (e) {}
        try { unsubscribeState && unsubscribeState(); } catch (e) {}
        leaveRoom(groupId);
        disconnectSocket();
      };
    }
  }, [groupId, isMember]);

  // Fallback: If WebSocket fails to load history, fetch via REST API
  useEffect(() => {
    if (wsState === SOCKET_STATE.ERROR && isMember && messages.length === 0) {
      // Only fetch if we have no messages and WebSocket is in error state
      const fetchMessagesFallback = async () => {
        try {
          const messagesData = await getMessages(groupId, 100);
          const normalized = Array.isArray(messagesData) ? messagesData.map(m => ({
            id: m.messageId || m.id,
            groupId: m.groupId || groupId,
            senderId: m.senderId,
            senderName: m.senderName || 'Member',
            content: m.content,
            timestamp: m.createdAt || m.timestamp,
          })) : [];
          setMessages(normalized);
        } catch (err) {
        }
      };
      
      // Add a small delay to allow WebSocket to retry first
      const timeoutId = setTimeout(fetchMessagesFallback, 2000);
      return () => clearTimeout(timeoutId);
    }
  }, [wsState, isMember, groupId, messages.length]);

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
      alert('Failed to join group.');
    }
  };

  const handleLeaveGroup = async () => {
    if (!isAuthenticated) return;
    const confirmLeave = window.confirm('Are you sure you want to leave this group?');
    if (!confirmLeave) return;
    
    try {
      const response = await leaveGroup(groupId);
      
      // Refresh group data to get updated member list
      const updatedGroupData = await getGroupDetails(groupId);
      setGroup(updatedGroupData);
      
      // Show success message
      alert('Successfully left the group!');
    } catch (err) {
      
      // Show more detailed error message
      const errorMessage = err.message || err.detail || 'Failed to leave group.';
      alert(`Error: ${errorMessage}`);
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
          {isMember && <button className="join-group-btn" onClick={handleLeaveGroup}>LEAVE</button>}
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
            <div className="connection-status" aria-live="polite" style={{ fontSize: 12, color: '#666', padding: '4px 0' }}>
              {wsState === SOCKET_STATE.CONNECTING && 'Connecting...'}
              {wsState === SOCKET_STATE.DISCONNECTED && 'Disconnected'}
            </div>
            {messages.map((msg) => {
              const isOwn = user && (msg.senderId === user.sub || msg.senderId === user.id || msg.senderId === user.userId);
              return (
              <div key={msg.id} className={`message ${isOwn ? 'own-message' : 'other-message'}`}>
                <div className="message-header">
                  <span className="sender-name">{isOwn ? 'You' : (msg.senderName || 'Member')}</span>
                  <span className="message-time">{formatTimestamp(msg.timestamp)}</span>
                </div>
                <div className="message-content">{msg.content}</div>
              </div>
            )})}
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
