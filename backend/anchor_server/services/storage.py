"""Local file storage for attachments."""

import hashlib
import re
import unicodedata
from collections.abc import Callable
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
    # Preserve path separators from the template while making each part safe.
    parts = [part for part in base.split("/") if part]
    safe_parts = [_slugify(part, max_length=80) for part in parts]
    safe_parts = [part for part in safe_parts if part]
    base = "/".join(safe_parts)
    return f"{base}{suffix}"


def _attachment_kind(content_type: str | None, filename: str) -> str:
    """Classify an attachment as PDF or other based on content type/extension."""
    if content_type == PDF_CONTENT_TYPE or filename.lower().endswith(".pdf"):
        return "pdfs"
    return "others"


def render_target_path(item: Item, filename: str, content_type: str | None) -> str:
    """Relative storage path the attachment renders to (before dedup/suffixes).

    Deterministic in the item's metadata, so it doubles as the dedup key:
    re-saving the same item renders the same path.
    """
    kind = _attachment_kind(content_type, filename)
    return f"{kind}/{_render_name(item, filename)}"


def _unique_path(
    directory: Path, name: str, is_free: Callable[[str], bool] | None = None
) -> Path:
    """Return a non-conflicting path inside ``directory`` for ``name``.

    ``name`` may contain subdirectories; all required parent directories are
    created automatically. Duplicate basenames get ``_1``, ``_2``, etc.
    A path is unavailable when it exists on disk or ``is_free`` rejects it
    (e.g. a tombstone row still holds the unique storage_path).
    """
    relative = Path(name)
    target_dir = directory / relative.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    def available(candidate: Path) -> bool:
        if candidate.exists():
            return False
        if is_free is None:
            return True
        return is_free(str(candidate.relative_to(directory.parent)))

    candidate = target_dir / relative.name
    if available(candidate):
        return candidate

    stem = Path(relative.name).stem
    suffix = Path(relative.name).suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if available(candidate):
            return candidate
        counter += 1


def md5_hex(data: bytes) -> str:
    """Content hash used as the attachment dedup key."""
    return hashlib.md5(data).hexdigest()  # noqa: S324 - dedup, not security


def save_attachment(
    item: Item,
    filename: str,
    content_type: str | None,
    data: bytes,
    *,
    is_free: Callable[[str], bool] | None = None,
) -> str:
    """Save attachment bytes and return the relative storage path.

    Files are organized under ``<attachments_dir>/pdfs/`` or
    ``<attachments_dir>/others/`` and named according to the configured Jinja
    template. The rendered name may contain subdirectories, which are created
    automatically. Duplicate filenames are resolved by appending ``_1``,
    ``_2``, etc.

    ``is_free`` reports whether a relative path is unclaimed in the database
    (no attachment row, live or tombstone, holds it — storage_path has a
    unique constraint). When the rendered target already exists on disk, its
    content matches ``data`` (by md5), and ``is_free`` confirms the path is
    unclaimed, the existing file is adopted instead of writing a copy — this
    reuses files delivered out-of-band (e.g. by Syncthing).
    """
    kind = _attachment_kind(content_type, filename)
    directory = settings.attachments_dir / kind

    name = _render_name(item, filename)
    candidate = directory / name
    if candidate.exists() and is_free is not None:
        relative = str(candidate.relative_to(settings.attachments_dir))
        if is_free(relative) and md5_hex(candidate.read_bytes()) == md5_hex(data):
            return relative

    storage_path = _unique_path(directory, name, is_free)
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
