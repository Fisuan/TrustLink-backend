from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.incident import IncidentStatus, IncidentType


# Shared properties
class IncidentBase(BaseModel):
    type: IncidentType
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_address: Optional[str] = None


# Properties to receive on incident creation
class IncidentCreate(IncidentBase):
    # No additional fields needed for creation
    pass


# Properties to receive on incident update
class IncidentUpdate(BaseModel):
    type: Optional[IncidentType] = None
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_address: Optional[str] = None
    status: Optional[IncidentStatus] = None


# Properties to return to client
class Incident(IncidentBase):
    id: int
    status: IncidentStatus
    reported_at: datetime
    user_id: int
    
    class Config:
        orm_mode = True


# Properties to return in a detailed incident
class IncidentDetail(Incident):
    # Will include attachment ids in the response
    attachments: List[int] = []
    
    class Config:
        orm_mode = True 