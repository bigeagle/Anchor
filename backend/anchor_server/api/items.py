"""Item CRUD endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from anchor_server.database import get_db
from anchor_server.models import Item
from anchor_server.schemas import ItemCreate, ItemOut, ItemUpdate
from anchor_server.services import storage

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=list[ItemOut])
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: str | None = Query(None, description="Filter by title substring"),
    db: Session = Depends(get_db),
) -> list[Item]:
    """List items with optional title filter and pagination."""
    query = db.query(Item)
    if q:
        query = query.filter(Item.title.ilike(f"%{q}%"))
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=ItemOut, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)) -> Item:
    """Create a new bibliographic item."""
    item = Item(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)) -> Item:
    """Retrieve a single item by ID."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
) -> Item:
    """Update an existing item."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Delete an item and all its attachments."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    storage.delete_item_attachments(item_id)
    db.delete(item)
    db.commit()
