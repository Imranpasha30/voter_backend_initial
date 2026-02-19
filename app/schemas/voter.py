from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class VoterBase(BaseModel):
    """Base schema for Voter with PollingVoter structure"""
    epic_no: str = Field(..., min_length=1, max_length=50, description="EPIC number (Voter ID)")
    part_id: int = Field(..., gt=0, description="Part ID (required)")

    # Polling Information
    ward_no: Optional[str] = Field(None, max_length=10)
    district: Optional[str] = Field(None, max_length=100)
    municipality: str = Field(..., max_length=200)
    polling_station_no: str = Field(..., max_length=10)
    polling_station_location: Optional[str] = Field(None)
    serial_no: Optional[str] = Field(None, max_length=10)

    # Personal Information
    voter_name: Optional[str] = Field(None, max_length=200)
    relation_name: Optional[str] = Field(None, max_length=200)
    age: Optional[int] = Field(None, ge=18, le=120)
    gender: Optional[str] = Field(None, max_length=20)

    # Address
    house_no: Optional[str] = Field(None, max_length=100)

    # Metadata
    date_time: Optional[str] = Field(None, max_length=100)
    pdf_url: Optional[str] = Field(None)
    phone_number: Optional[str] = Field(None, max_length=15)


class VoterCreate(VoterBase):
    """Schema for creating a new voter"""

    @field_validator('epic_no')
    @classmethod
    def validate_epic_no(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('EPIC number cannot be empty')
        return v.strip().upper()

    @field_validator('phone_number')
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        cleaned = ''.join(filter(str.isdigit, v))
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) != 10:
            raise ValueError('Phone number must be exactly 10 digits')
        if not cleaned.startswith(('6', '7', '8', '9')):
            raise ValueError('Phone number must start with 6, 7, 8, or 9')
        return cleaned

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        valid_genders = ['Male', 'Female', 'Other', 'M', 'F', 'O']
        if v not in valid_genders:
            raise ValueError('Gender must be one of: Male, Female, Other')
        gender_map = {'M': 'Male', 'F': 'Female', 'O': 'Other'}
        return gender_map.get(v, v)


class VoterUpdate(BaseModel):
    """Schema for updating voter details — all fields optional"""

    # Personal Information
    voter_name: Optional[str] = Field(None, max_length=200)
    relation_name: Optional[str] = Field(None, max_length=200)
    age: Optional[int] = Field(None, ge=18, le=120)
    gender: Optional[str] = Field(None, max_length=20)
    phone_number: Optional[str] = Field(None, max_length=15)

    # Address
    house_no: Optional[str] = Field(None, max_length=100)
    ward_no: Optional[str] = Field(None, max_length=10)
    district: Optional[str] = Field(None, max_length=100)
    municipality: Optional[str] = Field(None, max_length=200)

    # ⚠️ Polling — use with caution
    part_id: Optional[int] = Field(None, gt=0, description="⚠️ Changes constituency assignment")
    polling_station_no: Optional[str] = Field(None, max_length=10)
    polling_station_location: Optional[str] = Field(None)
    serial_no: Optional[str] = Field(None, max_length=10)

    # Metadata
    date_time: Optional[str] = Field(None, max_length=100)
    pdf_url: Optional[str] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "voter_name": "Rajesh Kumar",
                "age": 35,
                "gender": "Male",
                "phone_number": "9876543210",
                "house_no": "123/A"
            }
        }

    @field_validator('phone_number')
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        cleaned = ''.join(filter(str.isdigit, v))
        if not cleaned.isdigit():
            raise ValueError('Phone number must contain only digits')
        if len(cleaned) != 10:
            raise ValueError('Phone number must be exactly 10 digits')
        if not cleaned.startswith(('6', '7', '8', '9')):
            raise ValueError('Phone number must start with 6, 7, 8, or 9')
        return cleaned

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        valid_genders = ['Male', 'Female', 'Other', 'M', 'F', 'O']
        if v not in valid_genders:
            raise ValueError('Gender must be one of: Male, Female, Other')
        gender_map = {'M': 'Male', 'F': 'Female', 'O': 'Other'}
        return gender_map.get(v, v)

    @field_validator('age')
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 18:
            raise ValueError('Age must be at least 18')
        if v > 120:
            raise ValueError('Age cannot exceed 120')
        return v


# ========================================
# SURVEY SUMMARY — embedded in VoterResponse
# ========================================

class SurveySummary(BaseModel):
    """Lightweight survey info shown on voter card"""
    form_id: int
    household_name: Optional[str] = None
    volunteer_name: Optional[str] = None
    visit_date: Optional[str] = None
    current_party_support: Optional[str] = None
    favourite_party: Optional[str] = None
    is_voted: bool = False
    voting_status: Optional[str] = None  # 'red', 'yellow', 'green'
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


# ========================================
# VOTER RESPONSE
# ========================================

class VoterResponse(VoterBase):
    """Voter response with survey tracking fields"""
    voter_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Joined fields from Part table
    part_no: Optional[int] = None
    part_name: Optional[str] = None

    # ✅ Survey tracking — drives Flutter UI button state
    is_surveyed: bool = False
    form_id: Optional[int] = None
    survey_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========================================
# PAGINATED LIST RESPONSE
# ========================================

class VotersListResponse(BaseModel):
    """Paginated list of voters"""
    total: int = Field(..., description="Total voters matching query")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=500)
    voters: List[VoterResponse] = Field(..., description="List of voters")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 1523,
                "page": 1,
                "page_size": 20,
                "voters": [
                    {
                        "voter_id": 3394,
                        "epic_no": "IXR2227981",
                        "voter_name": "సయద్ అహ్మద్",
                        "age": 32,
                        "gender": "Male",
                        "part_no": 73,
                        "is_surveyed": True,
                        "form_id": 12,
                        "survey_date": "2026-02-18T14:20:31"
                    }
                ]
            }
        }


# ========================================
# BULK UPDATE
# ========================================

class VoterBulkUpdate(BaseModel):
    """Schema for bulk updating multiple voters"""
    voter_ids: List[int] = Field(..., min_length=1, max_length=100)
    updates: VoterUpdate


# ========================================
# FULL SURVEY DETAIL RESPONSE
# (used when Flutter taps 'View Survey' button)
# ========================================

class FamilyMemberDetail(BaseModel):
    member_id: int
    name: str
    age: int
    gender: str
    relation_to_head: Optional[str] = None
    voter_id: Optional[str] = None
    is_eligible_to_vote: bool = False
    is_voter_verified: bool = False

    class Config:
        from_attributes = True


class LinkedVoterDetail(BaseModel):
    voter_id: int
    epic_no: str
    voter_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    survey_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class FormDetailResponse(BaseModel):
    """
    Full survey form detail — returned when Flutter taps 'View Survey'.
    Called via GET /api/volunteers/form/{form_id}
    """
    form_id: int
    household_name: Optional[str] = None
    mobile_number: Optional[str] = None
    address: Optional[str] = None
    colony: Optional[str] = None
    area: Optional[str] = None
    caste: Optional[str] = None
    religion: Optional[str] = None
    gender: Optional[str] = None
    family_members_count: Optional[int] = None

    # Political
    knows_corporator: Optional[bool] = None
    corporator_name: Optional[str] = None
    current_party_support: Optional[str] = None
    favourite_party: Optional[str] = None
    other_politicians_known: Optional[str] = None

    # Services
    services_received: Optional[str] = None
    service_frequency: Optional[str] = None
    satisfaction_with_corporator: Optional[str] = None
    satisfaction_with_service: Optional[str] = None
    politician_visit_freq: Optional[str] = None

    # Engagement
    attended_events: Optional[bool] = None
    work_done_in_ward: Optional[bool] = None
    work_details: Optional[str] = None

    # Demographics
    income_range: Optional[str] = None
    main_occupation: Optional[str] = None
    highest_education: Optional[str] = None
    housing_type: Optional[str] = None
    govt_schemes: Optional[str] = None
    children_count: Optional[int] = None

    # Survey meta
    visit_date: Optional[str] = None
    volunteer_name: Optional[str] = None
    remarks: Optional[str] = None
    corporator_division: Optional[str] = None
    zone: Optional[str] = None

    # Voting status
    is_voted: bool = False
    voting_status: Optional[str] = None  # 'red', 'yellow', 'green'

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[str] = None
    person_image_url: Optional[str] = None

    created_at: Optional[str] = None

    # Related data
    family_members: List[FamilyMemberDetail] = []
    linked_voters: List[LinkedVoterDetail] = []

    class Config:
        from_attributes = True
