from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AreaBase(BaseModel):
    area_name: str
    description: Optional[str] = None


class AreaCreate(AreaBase):
    file_name: Optional[str] = None


class AreaResponse(AreaBase):
    area_id: int
    upload_date: datetime
    uploaded_by: Optional[int] = None
    file_name: Optional[str] = None
    total_voters: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class AreaWithParts(AreaResponse):
    parts_count: int
    voters_count: int


class AreasListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    areas: List[AreaResponse]


class UserAreaCreate(BaseModel):
    area_id: int


class UserAreaResponse(BaseModel):
    id: int
    user_id: int
    area_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
