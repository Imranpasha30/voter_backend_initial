from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, Numeric, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class FormData(Base):
    __tablename__ = "form_data"
    
    id = Column(Integer, primary_key=True, index=True)
    volunteer_id = Column(Integer, ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False)
    
    # Household Info
    household_name = Column(String(255))
    address = Column(Text)
    colony = Column(String(255))
    family_members = Column(Integer)
    
    # Voter Info
    voter_id = Column(String(255))
    aadhar = Column(String(255))
    voter_names = Column(Text)
    voter_ages = Column(Text)
    voter_relation = Column(Text)
    gender = Column(String(255))
    
    # Political Awareness
    knows_corporator = Column(Boolean)
    satisfied_with_corporator = Column(Boolean)
    knows_politician = Column(Boolean)
    supports_politician = Column(String(255))
    politician_visit_freq = Column(String(255))
    
    # Services
    services = Column(Text)
    service_frequency = Column(String(255))
    service_satisfaction = Column(String(255))
    attended_events = Column(Boolean)
    known_leaders = Column(Text)
    
    # Demographics
    income_range = Column(String(255))
    main_occupation = Column(String(255))
    education = Column(Text)
    housing_type = Column(String(255))
    children_count = Column(Integer)
    
    # Survey Meta
    visit_date = Column(Date)
    volunteer_name = Column(String(255))
    corporator_division = Column(String(255))
    zone = Column(String(255))
    remarks = Column(Text)
    
    # Media
    image_url = Column(String(255))
    person_image_url = Column(String(255))
    
    # Location
    latitude = Column(Numeric(9, 6))
    longitude = Column(Numeric(9, 6))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    volunteer = relationship("Volunteer", back_populates="form_data")
    family_members_list = relationship("FamilyMember", back_populates="form_data", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_form_data_volunteer_id', 'volunteer_id'),
    )
