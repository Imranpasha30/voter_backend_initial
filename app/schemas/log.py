from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ChangeLogResponse(BaseModel):
    log_id: int
    voter_id: int
    epic_no: str
    user_type: str
    user_name: str
    user_email: str
    action_type: str
    field_changed: str
    old_value: Optional[str]
    new_value: Optional[str]
    change_timestamp: datetime
    
    class Config:
        from_attributes = True


class ChangeLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    logs: List[ChangeLogResponse]
