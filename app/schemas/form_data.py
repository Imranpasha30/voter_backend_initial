from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class FamilyMemberCreate(BaseModel):
    name: str
    age: int
    gender: str
    is_eligible_to_vote: bool


class FormDataCreate(BaseModel):
    volunteer_id: int
    household_name: Optional[str] = None
    address: Optional[str] = None
    colony: Optional[str] = None
    family_members: Optional[int] = 0
    voter_id: Optional[str] = None
    aadhar: Optional[str] = None
    voter_names: Optional[str] = None
    voter_ages: Optional[str] = None
    voter_relation: Optional[str] = None
    gender: Optional[str] = None
    
    # Political
    knows_corporator: Optional[bool] = None
    satisfied_with_corporator: Optional[bool] = None
    knows_politician: Optional[bool] = None
    supports_politician: Optional[str] = None
    politician_visit_freq: Optional[str] = None
    
    # Services
    services: Optional[str] = None  # JSON string
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
    services: Optional[str]
    image_url: Optional[str]
    person_image_url: Optional[str]
    latitude: Decimal
    longitude: Decimal
    visit_date: Optional[date]
    
    class Config:
        from_attributes = True


class DashboardSummaryResponse(BaseModel):
    total_households: int
    total_voters: int
    total_supporters: int
    satisfaction_count: dict


class VoterDemographicsResponse(BaseModel):
    age_groups: dict
    gender_distribution: dict


class PoliticalSupportResponse(BaseModel):
    yes: int
    no: int
    neutral: int
