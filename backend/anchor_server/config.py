"""Application settings."""

from pathlib import Path

from pydantic import field_validator
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
    attachments_dir: Path = Path("./data/attachments")
    attachment_name_template: str = (
        "{{ year }}_{{ authors_last_names }}_{{ title_slug }}"
    )
    host: str = "127.0.0.1"
    port: int = 23119  # Same default port as the Zotero local HTTP server
    log_level: str = "info"

    # Phase 2.2 — translator support
    translators_dir: Path = Path("./data/translators")
    zotero_repo_url: str = "https://repo.zotero.org/repo/"
    http_proxy: str | None = None

    # Markdown conversion cache for attachments
    markdown_cache_dir: Path = Path("./data/cache/markdown")

    @field_validator(
        "data_dir",
        "attachments_dir",
        "translators_dir",
        "markdown_cache_dir",
        mode="after",
    )
    @classmethod
    def _resolve_path(cls, value: Path) -> Path:
        """Resolve relative paths against the current working directory."""
        return value.expanduser().resolve()


settings = Settings()
