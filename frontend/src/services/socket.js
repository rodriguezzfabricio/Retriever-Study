const connect = (groupId, token) => {
  const url = `ws://localhost:8000/ws/chat/${groupId}?token=${token}`;
  const socket = new WebSocket(url);

  socket.onopen = () => {
    console.log("WebSocket connection established.");
  };

  socket.onclose = () => {
    console.log("WebSocket connection closed.");
  };

  socket.onerror = (error) => {
    console.error("WebSocket error:", error);
  };

  return socket;
};

const disconnect = (socket) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }
};

const sendMessage = (socket, message) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    const payload = {
      content: message,
    };
    socket.send(JSON.stringify(payload));
  }
};

const socketService = {
  connect,
  disconnect,
  sendMessage,
};

export default socketService;
