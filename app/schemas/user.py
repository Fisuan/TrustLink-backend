from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
import re

from app.models.user import UserRole


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = True
    is_verified: Optional[bool] = False
    
    @validator("phone_number")
    def validate_phone_number(cls, v):
        if v is None:
            return v
        
        # Simple phone number validation - adjust as needed for your region/requirements
        if not re.match(r"^\+?[0-9]{10,15}$", v):
            raise ValueError("Invalid phone number format")
        return v


# Properties to receive on user creation
class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=8)
    
    @validator("password")
    def password_complexity(cls, v):
        # Check password complexity
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one digit")
        return v


# Properties to receive on user update
class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8)
    
    @validator("password")
    def password_complexity(cls, v):
        if v is None:
            return v
            
        # Check password complexity
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one digit")
        return v


# Properties to return to client
class User(UserBase):
    id: int
    
    class Config:
        orm_mode = True


# Properties for user login
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Token response
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Token payload
class TokenPayload(BaseModel):
    sub: Optional[int] = None 