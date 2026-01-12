from pydantic import BaseModel, field_validator
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
    pass


class VoterUpdate(BaseModel):
    fm_name_en: Optional[str] = None
    lastname_en: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    mobile_no: Optional[str] = None
    c_house_no: Optional[str] = None


class VoterResponse(VoterBase):
    voter_id: int
    created_at: datetime
    part_no: Optional[int] = None
    part_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class VotersListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    voters: list[VoterResponse]
