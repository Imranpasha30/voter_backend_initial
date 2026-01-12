from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Area(Base):
    __tablename__ = "areas"
    
    area_id = Column(Integer, primary_key=True, index=True)
    area_name = Column(String(255), nullable=False, index=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))
    file_name = Column(String(255))
    total_voters = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user_areas = relationship("UserArea", back_populates="area", cascade="all, delete-orphan")
    parts = relationship("Part", back_populates="area")
    
    __table_args__ = (
        Index('idx_areas_area_name', 'area_name'),
        Index('idx_areas_upload_date', 'upload_date'),
    )
