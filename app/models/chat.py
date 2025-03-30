from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class ChatMessage(Base):
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    sender_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    sender = relationship("User", foreign_keys=[sender_id])
    
    incident_id = Column(Integer, ForeignKey("incident.id"), nullable=False)
    incident = relationship("Incident", back_populates="chat_messages")
    
    # For emergency chat not related to a specific incident
    is_emergency = Column(Boolean, default=False, nullable=False)
    
    # For attachments in messages
    attachments = relationship("Attachment", back_populates="chat_message", cascade="all, delete-orphan") 