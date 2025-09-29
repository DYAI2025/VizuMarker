from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "LD35 Service"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = []
    
    # Default values that can be overridden by environment variables
    ALLOWED_ORIGINS: List[str] = ["*"]  # In production, specify actual domains
    ALLOWED_ORIGIN_REGEX: Optional[str] = None
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB default
    CHUNK_SIZE: int = 12000  # 12k characters per chunk
    LARGE_TEXT_THRESHOLD: int = 200000  # 200k characters
    LD35_MODEL_PATH: Optional[str] = os.getenv("LD35_MODEL_PATH")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./storage")
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    MARKER_ENGINE_PATH: Optional[str] = os.getenv("MARKER_ENGINE_PATH")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
