from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# Shared properties
class ChatMessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    is_emergency: Optional[bool] = False


# Properties to receive on chat message creation
class ChatMessageCreate(ChatMessageBase):
    incident_id: int


# Properties to receive on chat message update
class ChatMessageUpdate(BaseModel):
    is_read: Optional[bool] = None


# Properties to return to client
class ChatMessage(ChatMessageBase):
    id: int
    sender_id: int
    incident_id: int
    sent_at: datetime
    is_read: bool
    
    class Config:
        orm_mode = True


# For emergency messages that are not tied to a specific incident
class EmergencyChatCreate(ChatMessageBase):
    # Override the is_emergency field to always be True for emergency messages
    is_emergency: bool = True


# For WebSocket messages
class WSMessage(BaseModel):
    type: str  # "message", "read", "typing", etc.
    data: dict  # Message content or other data


# For real-time status updates through WebSockets
class ChatStatus(BaseModel):
    user_id: int
    status: str  # "online", "offline", "typing"
    incident_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow) 