"""Attachment write orchestration: dedup by rendered target path and content.

Every attachment write path (public API, Zotero Connector) goes through
``store_attachment`` so dedup rules apply uniformly. The rendered target path
is deterministic in the item's metadata, so re-saving the same item collides
on the same path:

1. If a live attachment already claims the target path and the on-disk file
   has identical content (md5), the item is very likely being saved twice —
   raise ``DuplicateAttachmentError`` so the caller can report the duplicate.
2. If the target file exists with identical content but no attachment row
   claims the path (e.g. delivered out-of-band by Syncthing), the file is
   adopted instead of writing a copy.
3. Otherwise (different content, or the path is claimed by a tombstone row —
   storage_path is unique), the file is saved with ``_1``, ``_2``, …
   suffixes as before.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from anchor_server.config import settings
from anchor_server.models import Attachment, Item
from anchor_server.services import storage


class DuplicateAttachmentError(ValueError):
    """A live attachment with identical content already exists at the target."""

    def __init__(self, existing: Attachment):
        self.existing = existing
        item_title = existing.item.title if existing.item else None
        super().__init__(
            f"Identical attachment already exists on item "
            f"{existing.item_id}" + (f" ({item_title})" if item_title else "")
        )


def store_attachment(
    db: Session,
    item: Item,
    filename: str,
    content_type: str | None,
    data: bytes,
) -> Attachment:
    """Store an attachment with dedup; see module docstring."""
    target = storage.render_target_path(item, filename, content_type)

    existing = (
        db.query(Attachment)
        .filter(
            Attachment.storage_path == target,
            Attachment.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        path = settings.attachments_dir / target
        if path.is_file() and storage.md5_hex(path.read_bytes()) == storage.md5_hex(
            data
        ):
            raise DuplicateAttachmentError(existing)
        # Different content, or the file has not arrived locally yet:
        # fall through and save with a _N suffix.

    # Tombstone rows included: storage_path is unique, so even soft-deleted
    # rows make their path unavailable for new attachments.
    taken_paths = {row[0] for row in db.query(Attachment.storage_path).all()}
    storage_path = storage.save_attachment(
        item,
        filename,
        content_type,
        data,
        is_free=lambda path: path not in taken_paths,
    )

    attachment = Attachment(
        item_id=item.id,
        filename=Path(storage_path).name,
        content_type=content_type,
        size=len(data),
        storage_path=storage_path,
    )
    db.add(attachment)
    db.flush()
    return attachment
