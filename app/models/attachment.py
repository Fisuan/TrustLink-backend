from sqlalchemy import Column, String, Integer, ForeignKey, Enum
import enum
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class AttachmentType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class Attachment(Base):
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False, unique=True)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    mime_type = Column(String(100), nullable=False)
    type = Column(Enum(AttachmentType), nullable=False)
    
    # Relationships - an attachment can be linked to either an incident or a chat message
    incident_id = Column(Integer, ForeignKey("incident.id"), nullable=True)
    incident = relationship("Incident", back_populates="attachments")
    
    chat_message_id = Column(Integer, ForeignKey("chatmessage.id"), nullable=True)
    chat_message = relationship("ChatMessage", back_populates="attachments") 