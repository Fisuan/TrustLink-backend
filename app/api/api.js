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
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Login failed: ${errorData.detail || response.statusText}`);
    }
    
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
      body: JSON.stringify({
        email: userData.email,
        password: userData.password,
        full_name: userData.fullName || userData.full_name || "",
        phone_number: userData.phoneNumber || userData.phone_number || "",
        role: "citizen" // Устанавливаем роль по умолчанию
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Registration failed: ${errorData.detail || response.statusText}`);
    }
    
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

// Экстренные ситуации
export const sendEmergency = async (token, emergencyData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/emergency`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(emergencyData),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Emergency failed: ${errorData.detail || response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Send emergency error:', error);
    throw error;
  }
};

// Отчеты о происшествиях
export const sendReport = async (token, reportData) => {
  try {
    const response = await fetch(`${API_BASE_URL}/incidents/report`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(reportData),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Report failed: ${errorData.detail || response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Send report error:', error);
    throw error;
  }
};

// Получение сообщений чата
export const getIncidentMessages = async (token, incidentId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/incidents/${incidentId}/messages`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Get messages failed: ${errorData.detail || response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Get messages error:', error);
    throw error;
  }
};

// Отправка сообщения в чат
export const sendChatMessage = async (token, incidentId, message) => {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content: message,
        incident_id: incidentId,
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Send message failed: ${errorData.detail || response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Send message error:', error);
    throw error;
  }
};
