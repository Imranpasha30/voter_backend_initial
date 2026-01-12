from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoginLogResponse(BaseModel):
    log_id: int
    user_id: int
    phone_number: str
    login_time: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        from_attributes = True


class LoginLogsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    logs: list[LoginLogResponse]
