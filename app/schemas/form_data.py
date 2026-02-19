from pydantic import BaseModel, Field, RootModel
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal

class FamilyMemberCreate(BaseModel):
    name: str
    age: int
    gender: str
    relation: str
    is_eligible: bool
    voter_id: Optional[str] = None
    aadhar_id: Optional[str] = None

class FormDataCreate(BaseModel):
    volunteer_id: int
    household_name: Optional[str] = None
    address: Optional[str] = None
    colony: Optional[str] = None
    family_members: Optional[int] = 0
    
    # ✅ NEW: Head of family voter details
    head_voter_id: Optional[str] = None
    head_aadhar: Optional[str] = None
    head_voter_name: Optional[str] = None
    head_voter_age: Optional[str] = None
    head_voter_relation: Optional[str] = None
    
    gender: Optional[str] = None
    
    # Political
    knows_corporator: Optional[bool] = None
    satisfied_with_corporator: Optional[bool] = None
    knows_politician: Optional[str] = None
    supports_politician: Optional[str] = None
    politician_visit_freq: Optional[str] = None
    
    # Services
    services: Optional[str] = None
    service_frequency: Optional[str] = None
    service_satisfaction: Optional[str] = None
    attended_events: Optional[bool] = None
    known_leaders: Optional[str] = None
    
    # Demographics
    income_range: Optional[str] = None
    main_occupation: Optional[str] = None
    education: Optional[str] = None
    housing_type: Optional[str] = None
    children_count: Optional[int] = 0
    
    # Survey meta
    visit_date: Optional[date] = None
    volunteer_name: Optional[str] = None
    corporator_division: Optional[str] = None
    zone: Optional[str] = None
    remarks: Optional[str] = None
    
    # Location
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    
    # Family details
    family_details: Optional[List[FamilyMemberCreate]] = []

class FormDataResponse(BaseModel):
    id: int
    volunteer_id: int
    household_name: Optional[str]
    address: Optional[str]
    colony: Optional[str]
    head_voter_id: Optional[str]
    head_aadhar: Optional[str]
    head_voter_name: Optional[str]
    head_voter_age: Optional[str]
    head_voter_relation: Optional[str]
    gender: Optional[str]
    knows_corporator: Optional[bool]
    satisfied_with_corporator: Optional[bool]
    knows_politician: Optional[str]
    supports_politician: Optional[str]
    services: Optional[str]
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    visit_date: Optional[date]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MapPinResponse(BaseModel):
    id: int
    volunteer_id: int
    volunteer_name: Optional[str]
    household_name: Optional[str]
    address: Optional[str]
    colony: Optional[str]
    area: Optional[str]
    services_received: Optional[str]
    image_url: Optional[str]
    person_image_url: Optional[str]
    latitude: Decimal
    longitude: Decimal
    visit_date: Optional[date]
    
    mobile_number: Optional[str]
    caste: Optional[str]
    religion: Optional[str]
    gender: Optional[str]
    current_party_support: Optional[str]
    favourite_party: Optional[str]
    satisfaction_with_corporator: Optional[str]
    satisfaction_with_service: Optional[str]
    family_members_count: Optional[int]
    
    class Config:
        from_attributes = True

class DashboardSummaryResponse(BaseModel):
    total_households: int
    total_voters: int
    total_supporters: int
    satisfaction_count: Dict[str, int]

class VoterDemographicsResponse(BaseModel):
    age_groups: Dict[str, int]
    gender_distribution: Dict[str, int]

class PoliticalSupportResponse(RootModel[Dict[str, int]]):
    """Dynamic political support breakdown"""
    root: Dict[str, int]

# ✅ NEW: Voter ID check response
class VoterIdCheckResponse(BaseModel):
    exists: bool
    is_surveyed: bool
    form_id: Optional[int] = None
    household_name: Optional[str] = None
    survey_date: Optional[date] = None
    message: str
