"""Item CRUD endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, asc, desc, or_
from sqlalchemy.orm import Session

from anchor_server.database import get_db
from anchor_server.models import Item
from anchor_server.schemas import ItemCreate, ItemOut, ItemUpdate
from anchor_server.services import storage

router = APIRouter(prefix="/items", tags=["items"])
search_router = APIRouter(prefix="/search", tags=["search"])

# Fields exposed for sorting by GET /items.
SORTABLE_FIELDS = {
    "date_added": Item.date_added,
    "title": Item.title,
    "year": Item.year,
    "publication": Item.publication,
    "item_type": Item.item_type,
    "doi": Item.doi,
    "arxiv_id": Item.arxiv_id,
}


@router.get("/", response_model=list[ItemOut])
def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    q: str | None = Query(None, description="Filter by title substring"),
    order_by: str = Query(
        "date_added",
        description=f"Sort field. One of: {', '.join(SORTABLE_FIELDS)}.",
    ),
    sort: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction."),
    db: Session = Depends(get_db),
) -> list[Item]:
    """List items with optional title filter, sorting, and pagination."""
    if order_by not in SORTABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by field. Allowed: {', '.join(SORTABLE_FIELDS)}",
        )

    query = db.query(Item)
    if q:
        query = query.filter(Item.title.ilike(f"%{q}%"))

    order_clause = (
        desc(SORTABLE_FIELDS[order_by])
        if sort == "desc"
        else asc(SORTABLE_FIELDS[order_by])
    )
    return query.order_by(order_clause).offset(skip).limit(limit).all()


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

    for attachment in item.attachments:
        storage.delete_attachment(attachment.storage_path)
    db.delete(item)
    db.commit()


@search_router.get("/", response_model=list[ItemOut])
def search_items(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Item]:
    """Search items across titles, abstracts, authors, identifiers, and publication."""
    term = f"%{q}%"
    filters = [
        Item.title.ilike(term),
        Item.abstract.ilike(term),
        Item.publication.ilike(term),
        Item.doi.ilike(term),
        Item.arxiv_id.ilike(term),
        Item.isbn.ilike(term),
        Item.url.ilike(term),
        Item.volume.ilike(term),
        Item.issue.ilike(term),
        Item.pages.ilike(term),
        Item.language.ilike(term),
        Item.item_type.ilike(term),
        Item.authors.cast(String).ilike(term),
    ]
    return db.query(Item).filter(or_(*filters)).limit(limit).all()
