from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.core.config import settings  # ✅ FIXED

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f'Password must be at least {settings.PASSWORD_MIN_LENGTH} characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    phone_number: str
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        if len(v) < settings.PHONE_MIN_LENGTH:
            raise ValueError(f'Phone must be at least {settings.PHONE_MIN_LENGTH} digits')
        if len(v) > settings.PHONE_MAX_LENGTH:
            raise ValueError(f'Phone must not exceed {settings.PHONE_MAX_LENGTH} digits')
        return v

class UserResponse(UserBase):
    user_id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None

class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
