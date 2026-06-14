"""Application settings."""

from pathlib import Path

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ANCHOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./anchor.db"
    data_dir: Path = Path("./data")
    host: str = "127.0.0.1"
    port: int = 23119  # Same default port as the Zotero local HTTP server
    log_level: str = "info"

    @field_validator("data_dir", mode="after")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        """Resolve relative data directories against the current working dir."""
        return value.expanduser().resolve()

    @computed_field
    @property
    def attachments_dir(self) -> Path:
        """Derived attachment storage directory."""
        return self.data_dir / "attachments"


settings = Settings()
