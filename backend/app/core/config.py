from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEV_SECRET_KEY = "change-me-in-production-please-32+chars"
DEV_FIELD_KEY = "u0bXj3yXq5rX2mQx9nH3kqL8Vd1c7s0yQm2rT6wZp4E="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "B2B CRM"
    ENV: str = "dev"
    # Значения по умолчанию — только для разработки и тестов; в продуктиве задаются в .env
    SECRET_KEY: str = DEV_SECRET_KEY
    # Ключ Fernet (32 байта base64) для шифрования телефонов в БД
    FIELD_ENCRYPTION_KEY: str = DEV_FIELD_KEY
    TIMEZONE: str = "Europe/Moscow"

    DATABASE_URL: str = "postgresql+psycopg://crm:crm@db:5432/crm"
    REDIS_URL: str = "redis://redis:6379/0"
    # В тестах фоновые задачи выполняются синхронно
    CELERY_ALWAYS_EAGER: bool = False

    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    RATE_LIMIT_PER_MINUTE: int = 100
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    # Список через запятую: http://a.ru,http://b.ru
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:8080"]
    # Внешний адрес системы: используется в письмах, трекинг-пикселе, публичных ссылках
    PUBLIC_BASE_URL: str = "http://localhost:8080"

    STORAGE_BACKEND: str = "s3"  # s3 | local
    LOCAL_STORAGE_PATH: str = "/data/files"
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "crm-files"
    S3_REGION: str = "us-east-1"

    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = False
    SMTP_SSL: bool = False
    MAIL_FROM: str = "CRM <crm@example.com>"

    IMAP_ENABLED: bool = False
    IMAP_HOST: str = ""
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_FOLDER: str = "INBOX"

    TELEGRAM_BOT_TOKEN: str = ""

    TELEPHONY_PROVIDER: str = "mock"  # mock | generic_http
    TELEPHONY_API_URL: str = ""
    TELEPHONY_API_TOKEN: str = ""
    TELEPHONY_WEBHOOK_SECRET: str = "telephony-secret"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


    @model_validator(mode="after")
    def forbid_dev_secrets_in_production(self):
        if self.ENV == "production" and (self.SECRET_KEY == DEV_SECRET_KEY or self.FIELD_ENCRYPTION_KEY == DEV_FIELD_KEY):
            raise ValueError("В продуктиве задайте собственные SECRET_KEY и FIELD_ENCRYPTION_KEY в .env")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
