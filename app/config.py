from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://localhost:5432/books"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    allowed_genres: tuple[str, ...] = (
        "Fiction",
        "Non-Fiction",
        "Science",
        "History",
        "Biography",
        "Fantasy",
        "Mystery",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached process-wide Settings instance."""
    return Settings()
