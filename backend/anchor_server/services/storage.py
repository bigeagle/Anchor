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


def save_attachment(item_id: uuid.UUID, filename: str, data: bytes) -> str:
    """Save attachment bytes and return the relative storage path."""
    directory = _attachment_dir(item_id)
    safe_name = Path(filename).name
    suffix = Path(safe_name).suffix
    name = Path(safe_name).stem
    storage_name = f"{name}_{uuid.uuid4().hex}{suffix}"
    storage_path = directory / storage_name
    storage_path.write_bytes(data)
    return str(storage_path.relative_to(settings.data_dir))


def read_attachment(relative_path: str) -> bytes:
    """Read attachment bytes from a relative storage path."""
    full_path = settings.data_dir / relative_path
    return full_path.read_bytes()


def delete_attachment(relative_path: str) -> None:
    """Delete the attachment file and clean up empty parent directories."""
    full_path = settings.data_dir / relative_path
    if full_path.exists():
        full_path.unlink()
        # Try to remove the item-specific directory if it is empty.
        parent = full_path.parent
        try:
            parent.rmdir()
        except OSError:
            pass


def delete_item_attachments(item_id: uuid.UUID) -> None:
    """Delete all attachment files belonging to an item."""
    directory = settings.attachments_dir / str(item_id)
    if directory.exists():
        shutil.rmtree(directory)
