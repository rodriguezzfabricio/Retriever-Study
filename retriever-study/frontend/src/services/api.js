// API Service Layer - Handles all backend communication
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
  }
}

// Generic fetch wrapper with error handling and auth token injection
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const config = { ...defaultOptions, ...options, headers: { ...defaultOptions.headers, ...options.headers } };

  // Get the token from localStorage
  const token = localStorage.getItem('authToken');
  
  // If a token exists, add it to the Authorization header
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    console.log(`API Request: ${config.method || 'GET'} ${url}`);
    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(
        errorData.detail?.error || `HTTP ${response.status}`,
        response.status,
        errorData
      );
    }

    // Handle responses that might not have a JSON body (e.g., 204 No Content)
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    
    console.error('Network error:', error);
    throw new ApiError('Network error - check if backend is running', 0, null);
  }
}

// Health Check
export const healthCheck = () => apiRequest('/health');

// User Management
export const createUser = (userData) => 
  apiRequest('/users', {
    method: 'POST',
    body: JSON.stringify(userData),
  });

export const updateUser = (userId, updates) =>
  apiRequest(`/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });

export const getJoinedGroups = (userId) =>
  apiRequest(`/users/${userId}/groups`);

// Groups
export const getGroupDetails = (groupId) =>
  apiRequest(`/groups/${groupId}`);

export const createGroup = (groupData, ownerId) =>
  apiRequest(`/groups?owner_id=${ownerId}`, {
    method: 'POST',
    body: JSON.stringify(groupData),
  });

export const getGroupsByCourse = (courseCode) =>
  apiRequest(`/groups?courseCode=${encodeURIComponent(courseCode)}`);

export const joinGroup = (groupId, userId) =>
  apiRequest(`/groups/${groupId}/join`, {
    method: 'POST',
    body: JSON.stringify({ userId }),
  });

// AI Features
export const getRecommendations = (userId, limit = 5) =>
  apiRequest(`/recommendations?userId=${userId}&limit=${limit}`);

export const searchGroups = (query, limit = 10) =>
  apiRequest(`/search?q=${encodeURIComponent(query)}&limit=${limit}`);

// Messages & Chat
export const sendMessage = (messageData) =>
  apiRequest('/messages', {
    method: 'POST',
    body: JSON.stringify(messageData),
  });

export const getMessages = (groupId, limit = 50) =>
  apiRequest(`/messages?groupId=${groupId}&limit=${limit}`);

export const summarizeChat = (groupId, since = null) => {
  const params = new URLSearchParams({ groupId });
  if (since) params.append('since', since);
  
  return apiRequest(`/summarize?${params.toString()}`, {
    method: 'POST',
  });
};

// Export ApiError for component error handling
export { ApiError };
