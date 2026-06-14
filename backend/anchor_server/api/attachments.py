"""Attachment endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from anchor_server.database import get_db
from anchor_server.models import Attachment, Item
from anchor_server.schemas import AttachmentOut
from anchor_server.services import storage

router = APIRouter(tags=["attachments"])


def _get_item_or_404(item_id: uuid.UUID, db: Session) -> Item:
    """Fetch an item or raise 404."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/items/{item_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    item_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[Attachment]:
    """List attachments belonging to an item."""
    _get_item_or_404(item_id, db)
    return db.query(Attachment).filter(Attachment.item_id == item_id).all()


@router.post(
    "/items/{item_id}/attachments", response_model=AttachmentOut, status_code=201
)
def upload_attachment(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Attachment:
    """Upload a file attachment for an item."""
    item = _get_item_or_404(item_id, db)

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")

    data = file.file.read()
    relative_path = storage.save_attachment(
        item, file.filename, file.content_type, data
    )
    rendered_name = Path(relative_path).name

    attachment = Attachment(
        item_id=item_id,
        filename=rendered_name,
        content_type=file.content_type,
        size=len(data),
        storage_path=relative_path,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    """Download an attachment by ID."""
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    data = storage.read_attachment(attachment.storage_path)
    # Let browsers display PDFs inline; other files are offered as downloads.
    if attachment.content_type == "application/pdf":
        headers = {"Content-Disposition": "inline"}
    else:
        headers = {
            "Content-Disposition": f'attachment; filename="{attachment.filename}"'
        }
    return Response(
        content=data,
        media_type=attachment.content_type or "application/octet-stream",
        headers=headers,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Delete an attachment."""
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    storage.delete_attachment(attachment.storage_path)
    db.delete(attachment)
    db.commit()
