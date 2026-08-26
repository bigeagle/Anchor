"""Read-only access to the Obsidian-style notes vault.

Items link one markdown file via ``Item.note_path`` (relative to
``settings.notes_dir``); note and image files live under that directory and
travel between machines out-of-band (Syncthing), exactly like attachments.
"""

from pathlib import Path

from anchor_server.config import settings
from anchor_server.models import Item

# Image extensions allowed on the assets endpoint (embeds in notes).
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".avif",
    ".bmp",
}


class InvalidNotePathError(Exception):
    """Raised when a note-relative path escapes the notes directory."""


def resolve_notes_path(relative_path: str) -> Path:
    """Resolve ``relative_path`` inside the notes dir, rejecting escapes."""
    candidate = (settings.notes_dir / relative_path).resolve()
    if not candidate.is_relative_to(settings.notes_dir):
        raise InvalidNotePathError(f"Path escapes notes directory: {relative_path!r}")
    return candidate


def note_file(item: Item) -> Path | None:
    """Return the linked note's path, or None when the item has no note."""
    if not item.note_path:
        return None
    return resolve_notes_path(item.note_path)


def find_image_by_name(filename: str) -> Path | None:
    """Find an image under the notes dir by bare filename (Obsidian-style).

    Obsidian resolves ``![[image.png]]`` vault-wide by name; this mirrors that
    for embeds written without a directory part. Deterministic: matches are
    sorted, first one wins.
    """
    if Path(filename).name != filename:  # must be a bare filename
        return None
    if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    matches = sorted(
        p for p in settings.notes_dir.rglob("*") if p.is_file() and p.name == filename
    )
    return matches[0] if matches else None
