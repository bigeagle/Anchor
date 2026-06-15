"""Convert attachment files to Markdown with attachment-id based caching."""

from pathlib import Path

from markitdown import MarkItDown

from anchor_server.config import settings
from anchor_server.models import Attachment


def _cache_path(attachment_id: str) -> Path:
    """Return the filesystem path for the cached Markdown of an attachment."""
    return settings.markdown_cache_dir / f"{attachment_id}.md"


def _is_cache_valid(attachment: Attachment) -> bool:
    """Return True if a cached Markdown file exists and is newer than the attachment."""
    cache_path = _cache_path(str(attachment.id))
    if not cache_path.exists():
        return False
    return cache_path.stat().st_mtime >= attachment.date_added.timestamp()


def get_attachment_markdown(attachment: Attachment) -> str:
    """Return Markdown text for an attachment, using the cache when valid.

    The cache key is the attachment ID. If the attachment file changes,
    the cache is invalidated by comparing the cache mtime with the attachment's
    ``date_added`` timestamp.
    """
    cache_path = _cache_path(str(attachment.id))

    if _is_cache_valid(attachment):
        return cache_path.read_text(encoding="utf-8")

    settings.markdown_cache_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()
    full_path = (settings.attachments_dir / attachment.storage_path).resolve()
    result = md.convert(str(full_path))
    markdown_text = result.text_content

    cache_path.write_text(markdown_text, encoding="utf-8")
    return markdown_text


def invalidate_attachment_markdown_cache(attachment_id: str) -> None:
    """Remove the cached Markdown for an attachment, if it exists."""
    cache_path = _cache_path(attachment_id)
    if cache_path.exists():
        cache_path.unlink()
