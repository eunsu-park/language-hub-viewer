"""Configuration for the Language Viewer application."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
_LANGUAGE_HUB = Path(os.environ.get("LANGUAGE_HUB_PATH", BASE_DIR.parent.parent / "language-hub"))
CONTENT_DIR = _LANGUAGE_HUB / "content"


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'data.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CONTENT_DIR = CONTENT_DIR

    # Auth toggle
    AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

    # Instruction languages (for lesson reading)
    SUPPORTED_LANGUAGES = ["ko", "en"]
    DEFAULT_LANGUAGE = "ko"
    LANGUAGE_NAMES = {
        "ko": "한국어",
        "en": "English",
    }

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True
    BCRYPT_LOG_ROUNDS = 12
    REMEMBER_COOKIE_DURATION = 30 * 24 * 60 * 60


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        if self.AUTH_ENABLED and not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in production with AUTH_ENABLED")


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
