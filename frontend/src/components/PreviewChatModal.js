import React, { useEffect, useState } from 'react';
import './PreviewChatModal.css';
import { getMessages } from '../services/api';

const PreviewChatModal = ({ isOpen, group, onClose, onJoin }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      if (!isOpen || !group?.id) return;
      setLoading(true);
      setError(null);
      try {
        const data = await getMessages(group.id, 30);
        const normalized = Array.isArray(data)
          ? data.map(m => ({
              id: m.messageId || m.id,
              content: m.content,
              senderName: m.senderName || 'Member',
              timestamp: m.createdAt || m.timestamp
            }))
          : [];
        setMessages(normalized);
      } catch (e) {
        setError('Failed to load recent messages');
        setMessages([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isOpen, group?.id]);

  if (!isOpen) return null;

  return (
    <div className="preview-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="preview-header">
          <h3 className="preview-title">Preview: {group?.name || 'Group'}</h3>
          <button className="preview-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="preview-body">
          {loading ? (
            <div className="loading-state"><div className="loading-spinner"></div></div>
          ) : error ? (
            <div className="error-state">{error}</div>
          ) : messages.length === 0 ? (
            <div className="empty-state">No recent messages yet.</div>
          ) : (
            <div className="preview-messages">
              {messages.map((m) => (
                <div key={m.id} className="preview-message">
                  <div className="preview-meta">
                    <span className="preview-sender">{m.senderName}</span>
                    <span className="preview-time">{new Date(m.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="preview-content">{m.content}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="preview-footer">
          <button className="btn" onClick={onClose}>Close</button>
          {group?.id && (
            <button className="btn primary" onClick={() => onJoin(group.id)}>Join Group</button>
          )}
        </div>
      </div>
    </div>
  );
};

export default PreviewChatModal;

