from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./clinic.db"
    vapi_webhook_secret: str = "change-this-secret"
    admin_token: str = "change-admin-token"
    clinic_name: str = "AIIMS Patna OPD"

    class Config:
        env_file = ".env"


settings = Settings()