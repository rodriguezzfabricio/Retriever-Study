import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import socketService from '../services/socket';
import './GroupDetail.css';

const GroupDetail = () => {
  const { groupId } = useParams();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [groupName, setGroupName] = useState('Loading...');
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Hardcoded for now, would fetch from API
    setGroupName(`Study Group ${groupId}`);

    const token = localStorage.getItem('token');

    if (groupId && token) {
      const socket = socketService.connect(groupId, token);
      socketRef.current = socket;

      socket.onmessage = (event) => {
        const receivedMessage = JSON.parse(event.data);
        setMessages((prevMessages) => [...prevMessages, receivedMessage]);
      };

      return () => {
        socketService.disconnect(socket);
      };
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (newMessage.trim() && socketRef.current) {
      socketService.sendMessage(socketRef.current, newMessage);
      setNewMessage('');
    }
  };

  return (
    <div className="group-detail-container">
      <header className="group-header">
        <h2>{groupName}</h2>
      </header>
      <main className="chat-box">
        <div className="messages-list">
          {messages.map((msg, index) => (
            <div key={index} className="message">
              <span className="message-sender">{msg.sender || 'Anonymous'}:</span>
              <p className="message-content">{msg.content}</p>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <form className="message-input-form" onSubmit={handleSendMessage}>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
            aria-label="Type a message"
          />
          <button type="submit">Send</button>
        </form>
      </main>
    </div>
  );
};

export default GroupDetail;
