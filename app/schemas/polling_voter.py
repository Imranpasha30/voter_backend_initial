from pydantic import BaseModel, Field, ConfigDict
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


class PollingVoterCreate(PollingVoterBase):
    pass


class PollingVoterUpdate(BaseModel):
    voter_name: Optional[str] = None
    relation_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    house_no: Optional[str] = None
    date_time: Optional[str] = None


class PollingVoterResponse(PollingVoterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)  # ✅ UPDATED for Pydantic v2


class PollingVoterListResponse(BaseModel):
    id: int
    voter_id: str
    voter_name: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    house_no: Optional[str]
    serial_no: Optional[str]

    model_config = ConfigDict(from_attributes=True)  # ✅ UPDATED for Pydantic v2


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
    errors: list = []
