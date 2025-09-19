"""Application configuration helpers."""

import os
from dataclasses import dataclass
from enum import Enum
from typing import List


class Environment(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    STAGING = "staging"


@dataclass
class LoggingSettings:
    level: str
    file_path: str


@dataclass
class SecuritySettings:
    allowed_cors_origins: List[str]


@dataclass
class AISettings:
    thread_pool_size: int


class AppConfig:
    def __init__(self) -> None:
        env_value = os.getenv("ENVIRONMENT", "development").lower()
        if env_value == "production":
            self.environment = Environment.PRODUCTION
        elif env_value == "staging":
            self.environment = Environment.STAGING
        else:
            self.environment = Environment.DEVELOPMENT

        log_file = os.getenv("LOG_FILE", "logs/retriever_api.log")
        self.logging = LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file_path=log_file,
        )

        cors_origins = os.getenv("ALLOWED_CORS_ORIGINS", "*")
        allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
        self.security = SecuritySettings(allowed_cors_origins=allowed_origins or ["*"])

        thread_pool_size = int(os.getenv("AI_THREAD_POOL_SIZE", "4"))
        self.ai = AISettings(thread_pool_size=thread_pool_size)

        self.app_name = os.getenv("APP_NAME", "Retriever Study API")
        self.version = os.getenv("APP_VERSION", "0.1.0")
        self.debug = self.is_development()

    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def get_database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///retriever_study_local.db")


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def is_development() -> bool:
    return get_config().is_development()


def is_production() -> bool:
    return get_config().is_production()
