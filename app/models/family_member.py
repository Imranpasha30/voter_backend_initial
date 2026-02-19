from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class FamilyMember(Base):
    __tablename__ = "family_members"

    member_id = Column(Integer, primary_key=True, index=True)
    form_data_id = Column(Integer, ForeignKey("form_data.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(50), nullable=False)
    
    # Voter Details
    is_eligible_to_vote = Column(Boolean, default=False, nullable=False)
    voter_id = Column(String(50), nullable=True, index=True)
    aadhar_id = Column(String(50), nullable=True)
    
    # Relationship to Head of Family
    relation_to_head = Column(String(100), nullable=True)
    
    # ==============================
    # ✅ NEW: Survey Tracking
    # ==============================
    is_voter_verified = Column(Boolean, default=False, nullable=False)
    # True if voter_id exists in voters table at time of submission

    # ==============================
    # Relationships
    # ==============================
    form_data = relationship("FormData", back_populates="family_members_list")
    
    # ==============================
    # Indexes for Performance
    # ==============================
    __table_args__ = (
        Index('idx_family_member_form_data_id', 'form_data_id'),
        Index('idx_family_member_voter_id', 'voter_id'),
        Index('idx_family_member_aadhar', 'aadhar_id'),
        Index('idx_family_member_eligible', 'is_eligible_to_vote'),
    )
    
    def __repr__(self):
        return f"<FamilyMember {self.name} - {self.age} yrs - {self.gender}>"
