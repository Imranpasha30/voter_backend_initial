from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class FamilyMember(Base):
    __tablename__ = "family_members"

    member_id = Column(Integer, primary_key=True, index=True)
    form_data_id = Column(Integer, ForeignKey("form_data.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255))
    age = Column(Integer)
    gender = Column(String(50))
    
    # Voter Details
    is_eligible_to_vote = Column(Boolean, default=False)
    voter_id = Column(String(50))
    aadhar_id = Column(String(50))
    
    # Relationship to Head of Family
    relation_to_head = Column(String(100))

    # Relationships
    form_data = relationship("FormData", back_populates="family_members_list")
