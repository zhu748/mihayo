from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    API_KEYS: List[str]
    ALLOWED_TOKENS: List[str]
    BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    MODEL_SEARCH: List[str] = ["gemini-2.0-flash-exp"]
    TOOLS_CODE_EXECUTION_ENABLED: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
