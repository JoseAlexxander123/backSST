from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SST Backend"
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 15
    OTP_EXPIRE_MINUTES: int = 5
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@sst.local"

    class Config:
        env_file = ".env"


settings = Settings()
