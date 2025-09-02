import { io } from 'socket.io-client';

// Use the same base URL as our API service, or a dedicated WebSocket URL
const SOCKET_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

let socket;

// This function initializes and returns the socket instance.
// It ensures we only have one connection for the whole app.
export const getSocket = () => {
  if (!socket) {
    console.log('Socket.IO: Initializing connection...');
    socket = io(SOCKET_URL, {
      // We can add authentication logic here later
      // For example, passing the token from localStorage
      // auth: {
      //   token: localStorage.getItem('authToken')
      // }
      autoConnect: false, // We will connect manually
    });

    // Generic event listeners for debugging
    socket.on('connect', () => {
      console.log('Socket.IO: Connected with id', socket.id);
    });

    socket.on('disconnect', (reason) => {
      console.log('Socket.IO: Disconnected', reason);
    });

    socket.on('connect_error', (err) => {
      console.error('Socket.IO: Connection Error', err.message);
    });
  }
  return socket;
};

// Explicitly connect to the socket
export const connectSocket = () => {
  const s = getSocket();
  if (!s.connected) {
    s.connect();
  }
};

// Explicitly disconnect from the socket
export const disconnectSocket = () => {
  const s = getSocket();
  if (s.connected) {
    s.disconnect();
  }
};

// Function to join a specific group's room
export const joinRoom = (groupId) => {
  const s = getSocket();
  console.log(`Socket.IO: Emitting 'join_room' for groupId: ${groupId}`);
  s.emit('join_room', { room: groupId });
};

// Function to leave a group's room
export const leaveRoom = (groupId) => {
  const s = getSocket();
  console.log(`Socket.IO: Emitting 'leave_room' for groupId: ${groupId}`);
  s.emit('leave_room', { room: groupId });
};

// Function to send a message to a room
export const sendChatMessage = (messageData) => {
  const s = getSocket();
  s.emit('send_message', messageData);
};

// Function to subscribe to new messages
export const onNewMessage = (callback) => {
  const s = getSocket();
  // We remove any previous listener to avoid duplicates
  s.off('new_message'); 
  s.on('new_message', callback);
};
