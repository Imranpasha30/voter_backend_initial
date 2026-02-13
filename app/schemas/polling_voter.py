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
    phone_number: Optional[str] = None
    is_voted: bool = False
    voting_status: Optional[str] = None


class PollingVoterResponse(PollingVoterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    total_rows: int
    imported_rows: int
    skipped_rows: int
    errors: list[str]


# ✅ NEW: Stats Response Schema
class VoterStatsResponse(BaseModel):
    success: bool
    total_voters: int
    total_municipalities: int
    total_polling_stations: int
    
    # Gender stats
    male_count: int
    female_count: int
    other_count: int
    
    # Age stats
    age_18_25: int
    age_26_35: int
    age_36_50: int
    age_51_65: int
    age_65_plus: int
    
    # Voting Status stats
    status_no: int
    status_maybe: int
    status_confirmed: int
    status_not_set: int
    
    # Voted stats
    voted_yes: int
    voted_no: int
    
    # Phone stats
    with_phone: int
    without_phone: int


# ✅ NEW: Bulk Update Request Schema
class BulkUpdateRequest(BaseModel):
    voter_ids: list[str] = Field(..., min_items=1)
    voting_status: Optional[str] = Field(None, pattern="^(red|yellow|green)$")
    is_voted: Optional[bool] = None


# ✅ NEW: Bulk Update Response Schema
class BulkUpdateResponse(BaseModel):
    success: bool
    message: str
    updated_count: int
