from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric, Index, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class FormData(Base):
    __tablename__ = "form_data"
    
    id = Column(Integer, primary_key=True, index=True)
    volunteer_id = Column(Integer, ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False)
    
    # ==============================
    # 1. Basic Info
    # ==============================
    household_name = Column(String(255))
    mobile_number = Column(String(20))
    caste = Column(String(100))
    religion = Column(String(100))
    gender = Column(String(255))
    
    address = Column(Text)
    colony = Column(String(255))
    area = Column(String(255))
    
    family_members = Column(Integer, nullable=True)
    family_members_count = Column(Integer, nullable=True)
    
    
    
    # ✅ DEPRECATED: Keep for backward compatibility (can be removed later)
    voter_id = Column(String(255), nullable=True)
    aadhar = Column(String(255), nullable=True)
    voter_names = Column(Text, nullable=True)
    voter_ages = Column(Text, nullable=True)
    voter_relation = Column(Text, nullable=True)
    
    # ==============================
    # ✅ NEW: Voting Status Tracking
    # ==============================
    is_voted = Column(Boolean, nullable=False, default=False, server_default='false', index=True)
    voting_status = Column(String(10), nullable=True, index=True)  # 'red', 'yellow', 'green'
    
    
    # ==============================
    # 3. Political Influence
    # ==============================
    knows_corporator = Column(Boolean)
    corporator_name = Column(String(255))
    knows_politician = Column(Text, nullable=True)
    other_politicians_known = Column(Text, nullable=True)
    current_party_support = Column(String(255))
    favourite_party = Column(String(255))
    
    # ==============================
    # 4. Services & Performance
    # ==============================
    services_received = Column(Text)
    service_frequency = Column(String(255))
    politician_visit_freq = Column(String(255))
    satisfaction_with_corporator = Column(String(50))
    satisfaction_with_service = Column(String(50))
    
    # ==============================
    # 5. Community Engagement
    # ==============================
    attended_events = Column(Boolean)
    work_done_in_ward = Column(Boolean)
    work_details = Column(Text)
    
    # ==============================
    # 6. Demographics
    # ==============================
    income_range = Column(String(255))
    main_occupation = Column(String(255))
    education = Column(Text, nullable=True)
    highest_education = Column(Text, nullable=True)
    housing_type = Column(String(255))
    govt_schemes = Column(Text)
    children_count = Column(Integer, nullable=True, default=0)
    
    # ==============================
    # 7. Survey Meta & Location
    # ==============================
    visit_date = Column(Date, nullable=True)
    volunteer_name = Column(String(255))
    remarks = Column(Text, nullable=True)
    corporator_division = Column(String(255), nullable=True)
    zone = Column(String(255), nullable=True)
    
    # Media
    image_url = Column(String(255), nullable=True)
    person_image_url = Column(String(255), nullable=True)
    
    # Location
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    location_accuracy = Column(Numeric(10, 2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # ==============================
    # Relationships
    # ==============================
    volunteer = relationship("Volunteer", back_populates="form_data")
    family_members_list = relationship("FamilyMember", back_populates="form_data", cascade="all, delete-orphan")
    
    # ✅ NEW: Relationship to voters that were surveyed in this form
    surveyed_voters = relationship(
        "Voter",
        foreign_keys="Voter.form_id",
        back_populates="form",
        cascade="all"
    )
    
    __table_args__ = (
        Index('idx_form_data_volunteer_id', 'volunteer_id'),
        Index('idx_form_data_is_voted', 'is_voted'),
        Index('idx_form_data_voting_status', 'voting_status'),
        
        Index('idx_form_data_mobile_number', 'mobile_number'),
        # ✅ NEW
        # ✅ Check constraint for voting_status
        CheckConstraint(
            "voting_status IS NULL OR voting_status IN ('red', 'yellow', 'green')",
            name='check_voting_status'
        ),
    )
