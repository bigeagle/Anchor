"""Local file storage for attachments."""

import shutil
import uuid
from pathlib import Path

from anchor_server.config import settings


def _ensure_dir(path: Path) -> None:
    """Create the directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def _attachment_dir(item_id: uuid.UUID) -> Path:
    """Return the storage directory for a given item."""
    directory = settings.attachments_dir / str(item_id)
    _ensure_dir(directory)
    return directory


def _sanitize_subdirs(relative: Path) -> list[str]:
    """Return safe directory parts, dropping traversal attempts."""
    return [part for part in relative.parts if part not in ("", ".", "..")]


def save_attachment(item_id: uuid.UUID, filename: str, data: bytes) -> str:
    """Save attachment bytes and return the relative storage path.

    The supplied ``filename`` may contain subdirectories (e.g.
    ``papers/2024/paper.pdf``) which are recreated under the item's storage
    directory for hierarchical organization.
    """
    base_dir = _attachment_dir(item_id)
    relative = Path(filename)

    basename = relative.name
    if not basename or basename in (".", ".."):
        raise ValueError("Invalid filename")

    subdirs = _sanitize_subdirs(relative.parent)
    target_dir = base_dir.joinpath(*subdirs)
    _ensure_dir(target_dir)

    suffix = Path(basename).suffix
    stem = Path(basename).stem
    storage_name = f"{stem}_{uuid.uuid4().hex}{suffix}"
    storage_path = target_dir / storage_name
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
    # Walk upward removing empty directories, stopping at the item root.
    parent = full_path.parent
    item_root = settings.attachments_dir
    while parent != item_root and parent.is_relative_to(item_root):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def delete_item_attachments(item_id: uuid.UUID) -> None:
    """Delete all attachment files belonging to an item."""
    directory = settings.attachments_dir / str(item_id)
    if directory.exists():
        shutil.rmtree(directory)
