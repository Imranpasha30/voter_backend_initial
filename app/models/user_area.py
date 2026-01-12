from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class UserArea(Base):
    __tablename__ = "user_areas"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.area_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_areas")
    area = relationship("Area", back_populates="user_areas")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'area_id', name='uq_user_area'),
        Index('idx_user_areas_user_id', 'user_id'),
        Index('idx_user_areas_area_id', 'area_id'),
    )
