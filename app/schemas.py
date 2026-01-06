from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime


# ==================== User Schemas ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    phone_number: str  # ✅ Fixed - removed Field with min_length/max_length
    
    # ✅ Add validator for phone number
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        if len(v) > 15:
            raise ValueError('Phone number must not exceed 15 digits')
        return v


class UserResponse(BaseModel):
    user_id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str


# ==================== Login Log Schemas ====================

class LoginLogResponse(BaseModel):
    log_id: int
    user_id: int
    phone_number: str
    login_time: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True


class LoginLogsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    logs: List[LoginLogResponse]


# ==================== Part Schemas ====================

class PartResponse(BaseModel):
    part_id: int
    part_no: int
    part_name_en: Optional[str] = None
    part_name_v1: Optional[str] = None
    created_at: datetime
    voter_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class PartsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    parts: List[PartResponse]


# ==================== Voter Schemas ====================

class VoterBase(BaseModel):
    epic_no: str
    part_id: int
    part_no: Optional[int] = None
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
    c_house_no: Optional[str] = None
    c_house_no_v1: Optional[str] = None
    is_active: Optional[bool] = True


class VoterCreate(VoterBase):
    pass


class VoterUpdate(BaseModel):
    fm_name_en: Optional[str] = None
    lastname_en: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    mobile_no: Optional[str] = None
    c_house_no: Optional[str] = None
    is_active: Optional[bool] = None


class VoterResponse(VoterBase):
    voter_id: int
    created_at: datetime
    # Add display fields
    ac_name: Optional[str] = None
    part_name: Optional[str] = None
    section_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class VotersListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    voters: List[VoterResponse]
