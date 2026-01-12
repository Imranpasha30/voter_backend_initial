from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class VolunteerCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone_number: Optional[str] = None


class VolunteerLogin(BaseModel):
    email: EmailStr
    password: str


class VolunteerResponse(BaseModel):
    id: int
    politician_id: int
    username: str
    email: str
    phone_number: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class VolunteerUpdate(BaseModel):
    username: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
