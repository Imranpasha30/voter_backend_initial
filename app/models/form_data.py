from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric, Index
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
    
    # ✅ FIXED: Use actual DB column names (both exist in DB)
    family_members = Column(Integer, nullable=True)  # Old column
    family_members_count = Column(Integer, nullable=True)  # New column (Flutter sends this)
    
    # ==============================
    # 2. HEAD OF FAMILY VOTER INFO (Missing from Flutter!)
    # ==============================
    voter_id = Column(String(255), nullable=True)
    aadhar = Column(String(255), nullable=True)
    voter_names = Column(Text, nullable=True)
    voter_ages = Column(Text, nullable=True)
    voter_relation = Column(Text, nullable=True)
    
    # ==============================
    # 3. Political Influence
    # ==============================
    knows_corporator = Column(Boolean)
    corporator_name = Column(String(255))
    
    # ✅ FIXED: Both columns exist in DB
    knows_politician = Column(Text, nullable=True)  # Old column
    other_politicians_known = Column(Text, nullable=True)  # New column (Flutter sends this)
    
    
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
    
    # ✅ FIXED: Both columns exist in DB
    education = Column(Text, nullable=True)  # Old column
    highest_education = Column(Text, nullable=True)  # New column (Flutter sends this)
    
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
    
    __table_args__ = (
        Index('idx_form_data_volunteer_id', 'volunteer_id'),
    )
