const API_BASE_URL = 'https://trustlink-backend-production.up.railway.app/api';

// Аутентификация
export const login = async (email, password) => {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
    });
    return await response.json();
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};

export const register = async (userData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });
    return await response.json();
  } catch (error) {
    console.error('Register error:', error);
    throw error;
  }
};

// Инциденты
export const getIncidents = async (token) => {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      }
    });
    return await response.json();
  } catch (error) {
    console.error('Get incidents error:', error);
    throw error;
  }
};

export const createIncident = async (token, incidentData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(incidentData),
    });
    return await response.json();
  } catch (error) {
    console.error('Create incident error:', error);
    throw error;
  }
};

// WebSocket чат
export const connectToChat = (incidentId, token) => {
  const socket = new WebSocket(`wss://trustlink-backend-production.up.railway.app/api/ws/chat/${incidentId}?token=${token}`);
  
  socket.onopen = () => {
    console.log('WebSocket подключен');
  };
  
  socket.onerror = (error) => {
    console.error('WebSocket ошибка:', error);
  };
  
  return socket;
};
