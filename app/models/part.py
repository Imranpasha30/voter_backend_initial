from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Part(Base):
    __tablename__ = "parts"
    
    part_id = Column(Integer, primary_key=True, index=True)
    part_no = Column(Integer, unique=True, nullable=False, index=True)
    area_id = Column(Integer, ForeignKey("areas.area_id", ondelete="RESTRICT"), nullable=True)  
    part_name_en = Column(String(255))
    part_name_v1 = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    area = relationship("Area", back_populates="parts") 
    voters = relationship("Voter", back_populates="part", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Part(id={self.part_id}, no={self.part_no})>"
