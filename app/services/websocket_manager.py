from typing import Dict, List, Any, Optional
import json

from fastapi import WebSocket


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
        
        # Broadcast user's online status to others in the incident
        await self.broadcast_message(
            incident_id=incident_id,
            message={
                "type": "user_status",
                "data": {
                    "user_id": user_id,
                    "status": "online",
                }
            },
            exclude=websocket,
        )
    
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
        Optionally exclude a specific connection.
        """
        if incident_id in self.active_connections:
            for user_id, connection in self.active_connections[incident_id].items():
                if connection != exclude:
                    await self.send_message(connection, message)
    
    async def send_message_to_user(self, user_id: int, message: dict):
        """
        Send a message to all connections of a specific user.
        """
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                await self.send_message(connection, message)
    
    async def broadcast_to_police(self, message: dict):
        """
        Broadcast a message to all connected police officers.
        Used for emergency notifications.
        """
        for connection in self.police_connections:
            await self.send_message(connection, message)


# Create a singleton instance
chat_manager = ConnectionManager() 