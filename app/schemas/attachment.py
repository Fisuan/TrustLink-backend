from typing import Optional
from pydantic import BaseModel

from app.models.attachment import AttachmentType


# Shared properties
class AttachmentBase(BaseModel):
    filename: str
    mime_type: str
    type: AttachmentType


# Properties for response
class Attachment(AttachmentBase):
    id: int
    file_path: str
    file_size: int
    incident_id: Optional[int] = None
    chat_message_id: Optional[int] = None
    
    class Config:
        orm_mode = True


# Properties for file upload response
class FileUploadResponse(BaseModel):
    attachment_id: int
    filename: str
    file_path: str
    mime_type: str
    file_size: int
    type: AttachmentType 