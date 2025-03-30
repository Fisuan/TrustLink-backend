from typing import Dict, List, Any, Optional
import json

from fastapi import WebSocket
from app.services.redis import publish_message, subscribe_to_channel


class ConnectionManager:
    """
    Manages WebSocket connections for chat functionality.
    """
    def __init__(self):
        # Track active connections by incident_id -> user_id -> WebSocket
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
        # Track user connections across all incidents
        self.user_connections: Dict[int, List[WebSocket]] = {}
        # Track police connections for emergency broadcasts
        self.police_connections: List[WebSocket] = []
        # Redis channel names
        self.incident_channel_prefix = "incident:"
        self.user_channel_prefix = "user:"
        self.police_channel = "police:all"
    
    async def connect(self, websocket: WebSocket, user_id: int, incident_id: int, is_police: bool = False):
        """
        Register a new connection.
        """
        # Initialize dictionaries if they don't exist
        if incident_id not in self.active_connections:
            self.active_connections[incident_id] = {}
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        
        # Add connection to incident-specific dict
        self.active_connections[incident_id][user_id] = websocket
        
        # Add connection to user-specific list
        self.user_connections[user_id].append(websocket)
        
        # Add to police list if applicable
        if is_police:
            self.police_connections.append(websocket)
        
        # Broadcast user's online status to others in the incident via Redis
        await publish_message(
            f"{self.incident_channel_prefix}{incident_id}",
            {
                "type": "user_status",
                "data": {
                    "user_id": user_id,
                    "status": "online",
                }
            }
        )
        
        # Subscribe to Redis channels
        # Note: In a production app, you'd need a background task to handle subscriptions
        
    def disconnect(self, websocket: WebSocket, user_id: int, incident_id: int):
        """
        Remove a connection when disconnected.
        """
        # Remove from incident-specific dict
        if incident_id in self.active_connections and user_id in self.active_connections[incident_id]:
            if self.active_connections[incident_id][user_id] == websocket:
                del self.active_connections[incident_id][user_id]
                
                # Remove incident dict if empty
                if not self.active_connections[incident_id]:
                    del self.active_connections[incident_id]
        
        # Remove from user-specific list
        if user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            
            # Remove user entry if empty
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from police list if present
        if websocket in self.police_connections:
            self.police_connections.remove(websocket)
        
        # Broadcast disconnect via Redis
        publish_message(
            f"{self.incident_channel_prefix}{incident_id}",
            {
                "type": "user_status",
                "data": {
                    "user_id": user_id,
                    "status": "offline",
                }
            }
        )
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """
        Send a message to a specific websocket.
        """
        try:
            await websocket.send_json(message)
        except Exception:
            # Handle connection error
            pass
    
    async def broadcast_message(self, incident_id: int, message: dict, exclude: Optional[WebSocket] = None):
        """
        Broadcast a message to all connected clients for a specific incident.
        Also publish to Redis for other instances.
        """
        # Local broadcast
        if incident_id in self.active_connections:
            for user_id, connection in self.active_connections[incident_id].items():
                if connection != exclude:
                    await self.send_message(connection, message)
        
        # Redis broadcast
        await publish_message(f"{self.incident_channel_prefix}{incident_id}", message)
    
    async def send_message_to_user(self, user_id: int, message: dict):
        """
        Send a message to all connections of a specific user.
        Also publish to Redis for other instances.
        """
        # Local send
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                await self.send_message(connection, message)
        
        # Redis broadcast
        await publish_message(f"{self.user_channel_prefix}{user_id}", message)
    
    async def broadcast_to_police(self, message: dict):
        """
        Broadcast a message to all connected police officers.
        Also publish to Redis for other instances.
        """
        # Local broadcast
        for connection in self.police_connections:
            await self.send_message(connection, message)
        
        # Redis broadcast
        await publish_message(self.police_channel, message)


# Create a singleton instance
chat_manager = ConnectionManager() 