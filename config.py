import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus

load_dotenv()

class Settings(BaseSettings):
    MONGO_USERNAME: str = os.getenv("MONGO_USERNAME", "")
    MONGO_PASSWORD: str = os.getenv("MONGO_PASSWORD", "")
    MONGO_CLUSTER: str = os.getenv("MONGO_CLUSTER", "")
    DB_NAME: str = os.getenv("DB_NAME", "")
    
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super_secret_jwt_key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def MONGO_URI(self) -> str:
        return f"mongodb+srv://{quote_plus(self.MONGO_USERNAME)}:{quote_plus(self.MONGO_PASSWORD)}@{self.MONGO_CLUSTER}/{self.DB_NAME}?retryWrites=true&w=majority"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()