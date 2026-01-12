from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Volunteer(Base):
    __tablename__ = "volunteers"
    
    id = Column(Integer, primary_key=True, index=True)
    politician_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    username = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    phone_number = Column(String(15))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    politician = relationship("User", back_populates="volunteers")
    form_data = relationship("FormData", back_populates="volunteer", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_volunteers_email', 'email'),
        Index('idx_volunteers_politician_id', 'politician_id'),
    )
