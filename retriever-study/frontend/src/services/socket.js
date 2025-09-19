// Native WebSocket client with reconnection & JWT auth

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function httpToWs(url) {
  try {
    const u = new URL(url);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.toString().replace(/\/$/, '');
  } catch {
    return url.startsWith('https') ? url.replace('https', 'wss') : url.replace('http', 'ws');
  }
}

const WS_BASE = httpToWs(API_URL);

// Connection states
export const SOCKET_STATE = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
};

class GroupSocket {
  constructor(groupId) {
    this.groupId = groupId;
    this.ws = null;
    this.state = SOCKET_STATE.DISCONNECTED;
    this.listeners = new Set(); // message listeners
    this.stateListeners = new Set(); // connection state listeners
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 10000; // 10s
    this.baseDelay = 500; // 0.5s
    this.manualClose = false;
    this.connect();
  }

  _emitState(newState) {
    this.state = newState;
    for (const cb of this.stateListeners) {
      try { cb(newState); } catch (_) {}
    }
  }

  _normalizeMessage(data) {
    const now = new Date().toISOString();
    return {
      id: data.messageId || data.id || `${this.groupId}-${now}`,
      groupId: data.groupId || this.groupId,
      senderId: data.senderId || data.userId || 'unknown',
      senderName: data.senderName || 'Member',
      content: data.content || '',
      timestamp: data.createdAt || now,
    };
  }

  _scheduleReconnect() {
    if (this.manualClose) return;
    const exp = Math.min(this.maxReconnectDelay, this.baseDelay * Math.pow(2, this.reconnectAttempts));
    const jitter = Math.floor(Math.random() * 250);
    const delay = Math.max(this.baseDelay, exp) + jitter;
    this.reconnectAttempts += 1;
    setTimeout(() => this.connect(), delay);
  }

  connect() {
    try {
      const token = localStorage.getItem('authToken');
      const url = `${WS_BASE}/ws/groups/${encodeURIComponent(this.groupId)}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
      this._emitState(SOCKET_STATE.CONNECTING);
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._emitState(SOCKET_STATE.CONNECTED);
      };

      this.ws.onmessage = (evt) => {
        let data = null;
        try {
          data = JSON.parse(evt.data);
        } catch (e) {
          console.warn('WS: non-JSON message', evt.data);
          return;
        }
        
        // Handle different message types
        if (data && data.type === 'chat_history') {
          // Handle batch chat history
          if (data.messages && Array.isArray(data.messages)) {
            for (const msg of data.messages) {
              const normalized = this._normalizeMessage(msg);
              for (const cb of this.listeners) {
                try { cb(normalized); } catch (e) {
                  console.warn('Error in message listener:', e);
                }
              }
            }
          }
        } else if (data && data.type === 'error') {
          // Handle error messages from server
          console.warn('WebSocket error from server:', data.error, data.message);
          // Emit error to state listeners
          this._emitState(SOCKET_STATE.ERROR);
        } else if (data && (data.type === 'message' || data.type === 'history_message' || data.content)) {
          // Handle single message (new or history)
          const normalized = this._normalizeMessage(data);
          for (const cb of this.listeners) {
            try { cb(normalized); } catch (e) {
              console.warn('Error in message listener:', e);
            }
          }
        }
      };

      this.ws.onerror = (err) => {
        console.error('WS error', err);
        this._emitState(SOCKET_STATE.ERROR);
      };

      this.ws.onclose = () => {
        this._emitState(SOCKET_STATE.DISCONNECTED);
        if (!this.manualClose) {
          this._scheduleReconnect();
        }
      };
    } catch (e) {
      console.error('WS connect exception', e);
      this._emitState(SOCKET_STATE.ERROR);
      this._scheduleReconnect();
    }
  }

  send(content) {
    const payload = JSON.stringify({ type: 'message', content: String(content || '').slice(0, 2000) });
    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(payload);
      } else {
        console.warn('WS not open, dropping message');
      }
    } catch (e) {
      console.error('WS send failed', e);
    }
  }

  close() {
    this.manualClose = true;
    try { this.ws && this.ws.close(); } catch (_) {}
    this._emitState(SOCKET_STATE.DISCONNECTED);
  }

  onMessage(cb) {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  onStateChange(cb) {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }
}

// Maintain per-group connections
const groupSockets = new Map();

function getGroupSocket(groupId) {
  if (!groupSockets.has(groupId)) {
    groupSockets.set(groupId, new GroupSocket(groupId));
  }
  return groupSockets.get(groupId);
}

// Compatibility helpers used by GroupDetail.js
export const connectSocket = () => {
  // No-op: connections are per-group via joinRoom
};

export const disconnectSocket = () => {
  // Close all group sockets
  for (const [, sock] of groupSockets) {
    try { sock.close(); } catch (_) {}
  }
  groupSockets.clear();
};

export const joinRoom = (groupId) => {
  getGroupSocket(groupId); // constructing triggers connect
};

export const leaveRoom = (groupId) => {
  const sock = groupSockets.get(groupId);
  if (sock) {
    sock.close();
    groupSockets.delete(groupId);
  }
};

export const sendChatMessage = ({ groupId, content }) => {
  const sock = getGroupSocket(groupId);
  sock.send(content);
};

export const onNewMessage = (callback, groupId = null) => {
  // If groupId specified, subscribe to that room; otherwise subscribe to all
  if (groupId) {
    const sock = getGroupSocket(groupId);
    return sock.onMessage(callback);
  }
  const unsubscribers = [];
  for (const [, sock] of groupSockets) {
    unsubscribers.push(sock.onMessage(callback));
  }
  return () => unsubscribers.forEach((u) => u && u());
};

export const onConnectionState = (groupId, cb) => {
  const sock = getGroupSocket(groupId);
  return sock.onStateChange(cb);
};
