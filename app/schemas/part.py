from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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
    parts: list[PartResponse]
