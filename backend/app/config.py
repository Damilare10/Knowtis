"""
Configuration settings for Knowtis
"""
from pydantic import BaseModel

class Settings(BaseModel):
    similarity_threshold: float = 0.75
    database_url: str = "sqlite:///./knowtis.db"
    jwt_secret_key: str = "SUPER_SECRET_JWT_KEY_CHANGE_ME"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

settings = Settings()
