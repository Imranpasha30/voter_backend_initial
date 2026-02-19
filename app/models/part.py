from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Part(Base):
    __tablename__ = "parts"
    
    part_id = Column(Integer, primary_key=True, index=True)
    part_no = Column(Integer, nullable=False, index=True)  # ✅ REMOVED unique=True
    area_id = Column(Integer, ForeignKey("areas.area_id", ondelete="RESTRICT"), nullable=True)
      
    part_name_en = Column(String(255))
    part_name_v1 = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    area = relationship("Area", back_populates="parts") 
    voters = relationship("Voter", back_populates="part", cascade="all, delete-orphan")
    
    # ✅ NEW: Composite unique constraint for area_id + part_no
    __table_args__ = (
        Index('idx_part_no', 'part_no'),
        Index('idx_part_area_id', 'area_id'),
        Index('idx_part_area_part_no', 'area_id', 'part_no'),  # Composite index
    )
    
    def __repr__(self):
        return f"<Part(id={self.part_id}, no={self.part_no}, area={self.area_id})>"
