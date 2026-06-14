"""Local file storage for attachments."""

import re
import unicodedata
from pathlib import Path

from jinja2 import BaseLoader, Environment

from anchor_server.config import settings
from anchor_server.models import Item


PDF_CONTENT_TYPE = "application/pdf"


def _slugify(value: str, max_length: int = 80) -> str:
    """Convert a string to a safe, lowercase, underscore-separated form."""
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "_", value)
    return value[:max_length].strip("_")


def _last_name(author: dict) -> str:
    """Extract a last name from an author dict, with sensible fallbacks."""
    if last_name := author.get("lastName"):
        return last_name
    if name := author.get("name", "").strip():
        return name.split()[-1]
    return "unknown"


def _render_name(item: Item, filename: str) -> str:
    """Render the configured Jinja template into a safe filename base."""
    suffix = Path(filename).suffix.lower()
    authors = item.authors or []
    last_names = [_last_name(a) for a in authors]
    authors_last_names = "_".join(last_names) or "unknown"
    authors_short = f"{last_names[0]}_et_al" if last_names else "unknown"

    env = Environment(loader=BaseLoader())
    template = env.from_string(settings.attachment_name_template)
    base = template.render(
        year=item.year or "unknown",
        title=item.title or "untitled",
        title_slug=_slugify(item.title or "untitled"),
        authors=authors,
        authors_last_names=authors_last_names,
        authors_short=authors_short,
        item_type=item.item_type,
        arxiv_id=item.arxiv_id or "",
        publication=item.publication or "",
    )
    base = _slugify(base, max_length=200)
    return f"{base}{suffix}"


def _attachment_kind(content_type: str | None, filename: str) -> str:
    """Classify an attachment as PDF or other based on content type/extension."""
    if content_type == PDF_CONTENT_TYPE or filename.lower().endswith(".pdf"):
        return "pdfs"
    return "others"


def _unique_path(directory: Path, name: str) -> Path:
    """Return a non-conflicting path inside ``directory`` for ``name``."""
    candidate = directory / name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_attachment(
    item: Item,
    filename: str,
    content_type: str | None,
    data: bytes,
) -> str:
    """Save attachment bytes and return the relative storage path.

    Files are organized under ``<attachments_dir>/pdfs/`` or
    ``<attachments_dir>/others/`` and named according to the configured Jinja
    template. Duplicate filenames are resolved by appending ``_1``, ``_2``, etc.
    """
    kind = _attachment_kind(content_type, filename)
    directory = settings.attachments_dir / kind
    directory.mkdir(parents=True, exist_ok=True)

    name = _render_name(item, filename)
    storage_path = _unique_path(directory, name)
    storage_path.write_bytes(data)
    return str(storage_path.relative_to(settings.attachments_dir))


def read_attachment(relative_path: str) -> bytes:
    """Read attachment bytes from a relative storage path."""
    full_path = settings.attachments_dir / relative_path
    return full_path.read_bytes()


def delete_attachment(relative_path: str) -> None:
    """Delete the attachment file and clean up empty parent directories."""
    full_path = settings.attachments_dir / relative_path
    if not full_path.exists():
        return

    full_path.unlink()
    # Walk upward removing empty directories, stopping at the kind root.
    parent = full_path.parent
    kind_root = settings.attachments_dir
    while parent != kind_root and parent.is_relative_to(kind_root):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
