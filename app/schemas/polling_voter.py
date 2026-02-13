from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PollingVoterBase(BaseModel):
    voter_id: str
    ward_no: Optional[str] = None
    district: Optional[str] = None
    municipality: str
    polling_station_no: str
    polling_station_location: Optional[str] = None
    serial_no: Optional[str] = None
    voter_name: Optional[str] = None
    relation_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    house_no: Optional[str] = None
    date_time: Optional[str] = None
    pdf_url: Optional[str] = None
    phone_number: Optional[str] = None  # ✅ NEW
    is_voted: bool = False  # ✅ NEW
    voting_status: Optional[str] = None  # ✅ NEW


class PollingVoterResponse(PollingVoterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ✅ NEW: Update schema for PATCH requests
class PollingVoterUpdate(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=15)
    is_voted: Optional[bool] = None
    voting_status: Optional[str] = Field(None, pattern="^(red|yellow|green)$")

    class Config:
        from_attributes = True


class PollingVoterListResponse(BaseModel):
    success: bool
    voters: list[PollingVoterResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MunicipalityResponse(BaseModel):
    municipality: str
    voter_count: int


class PollingStationResponse(BaseModel):
    polling_station_no: str
    polling_station_location: Optional[str]
    voter_count: int


class CSVUploadResponse(BaseModel):
    success: bool
    message: str
    imported_count: int
    updated_count: int
    failed_count: int
