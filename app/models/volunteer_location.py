"""
Volunteer Location Model for Real-time Tracking
Optimized with indexes for fast queries
"""

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class VolunteerLocation(Base):
    __tablename__ = "volunteer_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    volunteer_id = Column(Integer, ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float)  # meters
    speed = Column(Float)  # m/s
    heading = Column(Float)  # degrees (0-360)
    battery_level = Column(Integer)  # percentage (0-100)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    volunteer = relationship("Volunteer", backref="locations")
    
    __table_args__ = (
        Index('idx_volunteer_timestamp', 'volunteer_id', 'timestamp'),
        Index('idx_active_locations', 'is_active', 'timestamp'),
        Index('idx_volunteer_active', 'volunteer_id', 'is_active'),
    )
