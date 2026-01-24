from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class VoterBase(BaseModel):
    epic_no: str
    part_id: int
    slnoinpart: Optional[int] = None
    fm_name_en: Optional[str] = None
    lastname_en: Optional[str] = None
    fm_name_v1: Optional[str] = None
    lastname_v1: Optional[str] = None
    relation_type: Optional[str] = None
    rln_fm_nm_en: Optional[str] = None
    rln_l_nm_en: Optional[str] = None
    rln_fm_nm_v1: Optional[str] = None
    rln_l_nm_v1: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    mobile_no: Optional[str] = None
    ac_no: Optional[int] = None
    section_no: Optional[int] = None
    pc_no: Optional[int] = None
    village_name_en: Optional[str] = None
    village_name_v1: Optional[str] = None
    tahsil_name_en: Optional[str] = None
    police_name_en: Optional[str] = None
    postoff_pin: Optional[str] = None
    c_house_no: Optional[str] = None
    c_house_no_v1: Optional[str] = None


class VoterCreate(VoterBase):
    """Schema for creating a new voter"""
    epic_no: str = Field(..., min_length=1, max_length=50, description="EPIC number (required)")
    part_id: int = Field(..., gt=0, description="Part ID (required)")
    
    @field_validator('epic_no')
    @classmethod
    def validate_epic_no(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('EPIC number cannot be empty')
        return v.strip().upper()


class VoterUpdate(BaseModel):
    """
    Schema for updating voter details.
    All fields are optional - only provided fields will be updated.
    """
    # Personal Information
    fm_name_en: Optional[str] = Field(None, max_length=100, description="First/Middle name (English)")
    lastname_en: Optional[str] = Field(None, max_length=100, description="Last name (English)")
    fm_name_v1: Optional[str] = Field(None, max_length=100, description="First/Middle name (Vernacular)")
    lastname_v1: Optional[str] = Field(None, max_length=100, description="Last name (Vernacular)")
    age: Optional[int] = Field(None, ge=18, le=120, description="Age (18-120)")
    gender: Optional[str] = Field(None, max_length=10, description="Gender: Male/Female/Other")
    dob: Optional[str] = Field(None, max_length=20, description="Date of birth")
    mobile_no: Optional[str] = Field(None, max_length=15, description="Mobile number (10 digits)")
    
    # Family Details
    relation_type: Optional[str] = Field(None, max_length=10, description="Relation type")
    rln_fm_nm_en: Optional[str] = Field(None, max_length=100, description="Relative first name (English)")
    rln_l_nm_en: Optional[str] = Field(None, max_length=100, description="Relative last name (English)")
    rln_fm_nm_v1: Optional[str] = Field(None, max_length=100, description="Relative first name (Vernacular)")
    rln_l_nm_v1: Optional[str] = Field(None, max_length=100, description="Relative last name (Vernacular)")
    
    # Address Information
    c_house_no: Optional[str] = Field(None, max_length=50, description="House number (English)")
    c_house_no_v1: Optional[str] = Field(None, max_length=50, description="House number (Vernacular)")
    village_name_en: Optional[str] = Field(None, max_length=100, description="Village name (English)")
    village_name_v1: Optional[str] = Field(None, max_length=100, description="Village name (Vernacular)")
    tahsil_name_en: Optional[str] = Field(None, max_length=100, description="Tahsil name")
    police_name_en: Optional[str] = Field(None, max_length=100, description="Police station name")
    postoff_pin: Optional[str] = Field(None, max_length=10, description="PIN code")
    
    # ⚠️ POLLING INFORMATION - USE WITH CAUTION
    # Changing these fields affects data retrieval and constituency assignment
    part_id: Optional[int] = Field(None, gt=0, description="⚠️ WARNING: Changing part_id affects constituency assignment")
    slnoinpart: Optional[int] = Field(None, description="Serial number in part")
    section_no: Optional[int] = Field(None, description="Section number")
    ac_no: Optional[int] = Field(None, description="Assembly Constituency number")
    pc_no: Optional[int] = Field(None, description="Parliamentary Constituency number")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fm_name_en": "Rajesh",
                "lastname_en": "Kumar",
                "age": 35,
                "gender": "Male",
                "mobile_no": "9876543210",
                "c_house_no": "123/A"
            }
        }
    
    # ✅ Validators
    @field_validator('mobile_no')
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        
        # Remove spaces and special characters
        cleaned = ''.join(filter(str.isdigit, v))
        
        if not cleaned.isdigit():
            raise ValueError('Mobile number must contain only digits')
        
        if len(cleaned) != 10:
            raise ValueError('Mobile number must be exactly 10 digits')
        
        if not cleaned.startswith(('6', '7', '8', '9')):
            raise ValueError('Mobile number must start with 6, 7, 8, or 9')
        
        return cleaned
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        
        valid_genders = ['Male', 'Female', 'Other', 'M', 'F', 'O']
        if v not in valid_genders:
            raise ValueError('Gender must be one of: Male, Female, Other')
        
        # Normalize to full name
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
    
    @field_validator('postoff_pin')
    @classmethod
    def validate_pin(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return v
        
        cleaned = ''.join(filter(str.isdigit, v))
        
        if len(cleaned) != 6:
            raise ValueError('PIN code must be 6 digits')
        
        return cleaned


class VoterResponse(VoterBase):
    """Schema for voter response with additional computed fields"""
    voter_id: int
    created_at: datetime
    
    # Additional display fields (from joins)
    part_no: Optional[int] = None
    part_name: Optional[str] = None
    
    class Config:
        from_attributes = True  # Pydantic v2
        # orm_mode = True  # Pydantic v1 (use if you're on v1)


class VotersListResponse(BaseModel):
    """Paginated list of voters"""
    total: int = Field(..., description="Total number of voters")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=500, description="Items per page")
    voters: list[VoterResponse] = Field(..., description="List of voters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 1523,
                "page": 1,
                "page_size": 20,
                "voters": [
                    {
                        "voter_id": 12345,
                        "epic_no": "ABC1234567",
                        "fm_name_en": "Rajesh",
                        "lastname_en": "Kumar",
                        "age": 35,
                        "gender": "Male",
                        "mobile_no": "9876543210",
                        "part_no": 123,
                        "part_name": "Model Town"
                    }
                ]
            }
        }


# ✅ Optional: Schema for bulk updates (if needed in future)
class VoterBulkUpdate(BaseModel):
    """Schema for bulk updating multiple voters"""
    voter_ids: list[int] = Field(..., min_length=1, max_length=100)
    updates: VoterUpdate
