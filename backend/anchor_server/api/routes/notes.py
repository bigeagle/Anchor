"""Note endpoints: read-only access to an item's linked markdown note."""

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from anchor_server.database import get_db
from anchor_server.models import Item
from anchor_server.services import notes_service

router = APIRouter(tags=["notes"])


def _get_item_or_404(item_id: uuid.UUID, db: Session) -> Item:
    """Fetch a non-deleted item or raise 404."""
    item = db.get(Item, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items/{item_id}/note")
def get_item_note(
    item_id: uuid.UUID, db: Session = Depends(get_db)
) -> PlainTextResponse:
    """Return the raw markdown of the item's linked note.

    404 when the item has no linked note, or when the file has not been
    delivered to this machine yet (Syncthing may still be catching up).
    """
    item = _get_item_or_404(item_id, db)

    try:
        path = notes_service.note_file(item)
    except notes_service.InvalidNotePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if path is None:
        raise HTTPException(status_code=404, detail="Item has no linked note")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Note file not available locally")
    return PlainTextResponse(
        content=path.read_text(encoding="utf-8"), media_type="text/markdown"
    )


@router.get("/notes/lookup/{filename}")
def get_note_asset_by_name(filename: str) -> Response:
    """Serve an image found by bare filename anywhere under the notes dir.

    Backs Obsidian-style embeds (``![[image.png]]``), which resolve
    vault-wide by name rather than by path.
    """
    file_path = notes_service.find_image_by_name(filename)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return Response(content=file_path.read_bytes(), media_type=media_type)


@router.get("/notes/assets/{path:path}")
def get_note_asset(path: str) -> Response:
    """Serve an image from the notes directory (for note embeds)."""
    suffix = Path(path).suffix.lower()
    if suffix not in notes_service.IMAGE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Not an image asset")
    try:
        file_path = notes_service.resolve_notes_path(path)
    except notes_service.InvalidNotePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return Response(content=file_path.read_bytes(), media_type=media_type)
