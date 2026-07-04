from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Distributed Background Job Scheduler"
    API_V1_STR: str = "/api/v1"
    
    # JWT Auth Settings
    SECRET_KEY: str = Field(default="supersecretjwtkeythatisverylongandsecureformultitenancy")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database Settings
    DATABASE_URL: str = Field(default="sqlite:///./jobscheduler.db")


    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
