from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Voter Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    
    # Security
    # ✅ CHANGED: No default value, MUST come from environment
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Validation
    PASSWORD_MIN_LENGTH: int = 8
    PHONE_MIN_LENGTH: int = 10
    PHONE_MAX_LENGTH: int = 15
    
    # ImageKit Configuration (Optional - set empty strings as default)
    IMAGEKIT_PUBLIC_KEY: Optional[str] = ""
    IMAGEKIT_PRIVATE_KEY: Optional[str] = ""
    IMAGEKIT_URL_ENDPOINT: Optional[str] = ""
    
    # ✅ NEW: Document folder paths
    IMAGEKIT_FOLDER_PATH: str = "/VoterConnectImages/VoterCard"
    IMAGEKIT_FOLDER_PATH_2: str = "/VoterConnectImages/VoterCard2"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # ✅ Ignore extra env vars
        # ✅ ADDED: Force environment variables to take priority
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
