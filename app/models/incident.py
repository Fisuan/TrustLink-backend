from sqlalchemy import Column, String, Integer, Enum, ForeignKey, Text, Float, DateTime
import enum
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base


class IncidentStatus(str, enum.Enum):
    REPORTED = "reported"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentType(str, enum.Enum):
    THEFT = "theft"
    VIOLENCE = "violence"
    VANDALISM = "vandalism"
    TRAFFIC = "traffic"
    NOISE = "noise"
    OTHER = "other"


class Incident(Base):
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(IncidentType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    location_address = Column(String(255), nullable=True)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    status = Column(Enum(IncidentStatus), default=IncidentStatus.REPORTED, nullable=False)
    
    # Relationships
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", back_populates="incidents")
    
    attachments = relationship("Attachment", back_populates="incident", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="incident", cascade="all, delete-orphan") 