from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class FamilyMember(Base):
    __tablename__ = "family_members"
    
    member_id = Column(Integer, primary_key=True, index=True)
    form_data_id = Column(Integer, ForeignKey("form_data.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255))
    age = Column(Integer)
    gender = Column(String(255))
    is_eligible_to_vote = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    voter_id = Column(String(50))
    # Relationships
    form_data = relationship("FormData", back_populates="family_members_list")
    
    __table_args__ = (
        Index('idx_family_members_form_data_id', 'form_data_id'),
    )
