from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="ner_db")
    POSTGRES_SERVER: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)

    # Redis
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    # REDIS_PASSWORD: str = Field(default=None)  # optional

    # FastAPI
    FASTAPI_HOST: str = Field(default="0.0.0.0")
    FASTAPI_PORT: int = Field(default=8000)

    # JWT
    JWT_SECRET_KEY: str = Field(default="your-secret-key-here")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # Corridor
    CORRIDOR_NAME: str = Field(default="Guwahati-Shillong NH6")
    CORRIDOR_BBOX: str = Field(default="88.0,25.0,92.0,27.0")

    # Open-Meteo
    OPEN_METEO_BASE_URL: str = Field(default="https://api.open-meteo.com/v1/forecast")

    # GraphHopper
    GRAPHHOPPER_HOST: str = Field(default="localhost")
    GRAPHHOPPER_PORT: int = Field(default=8989)

    # Database URL
        # Database URL
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/ner_db")

    # Redis URL
        # Redis URL
    REDIS_URL: str = Field(default="redis://localhost:6379")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()