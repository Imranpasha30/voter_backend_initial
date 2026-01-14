"""
Location Schemas for Request/Response validation
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LocationUpdate(BaseModel):
    """Schema for volunteer sending location update"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    speed: Optional[float] = Field(None, ge=0)
    heading: Optional[float] = Field(None, ge=0, le=360)
    battery_level: Optional[int] = Field(None, ge=0, le=100)


class LocationResponse(BaseModel):
    """Schema for location response"""
    id: int
    volunteer_id: int
    latitude: float
    longitude: float
    accuracy: Optional[float]
    speed: Optional[float]
    heading: Optional[float]
    battery_level: Optional[int]
    timestamp: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class VolunteerLocationDetail(BaseModel):
    """Schema for volunteer location with details"""
    volunteer_id: int
    volunteer_name: str
    volunteer_email: str
    latitude: float
    longitude: float
    accuracy: Optional[float]
    speed: Optional[float]
    heading: Optional[float]
    battery_level: Optional[int]
    timestamp: datetime
    status: str  # 'online', 'offline', 'stale'
