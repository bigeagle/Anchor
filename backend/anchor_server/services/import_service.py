"""Map Zotero connector item payloads into Anchor models."""

import re
from typing import Any

from anchor_server.enums import ItemType
from anchor_server.models import Item
from anchor_server.schemas.zotero import ConnectorItem


# Zotero item types that map cleanly to Anchor's enum. Unknown types fall back
# to ``other``.
_ZOTERO_TO_ANCHOR_TYPE = {
    "journalArticle": ItemType.JOURNAL_ARTICLE,
    "book": ItemType.BOOK,
    "bookSection": ItemType.BOOK_SECTION,
    "conferencePaper": ItemType.CONFERENCE_PAPER,
    "thesis": ItemType.THESIS,
    "report": ItemType.REPORT,
    "patent": ItemType.PATENT,
    "webpage": ItemType.WEBPAGE,
    "document": ItemType.DOCUMENT,
    "preprint": ItemType.PREPRINT,
}


def _parse_year(date_or_year: str | int | None, year: int | None) -> int | None:
    """Extract a four-digit year from a date string or year value."""
    if year is not None:
        return year
    if not date_or_year:
        return None
    if isinstance(date_or_year, int):
        return date_or_year
    match = re.search(r"\b(19|20)\d{2}\b", str(date_or_year))
    return int(match.group(0)) if match else None


def _extract_authors(creators: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert Zotero creators into Anchor's author shape."""
    authors = []
    for creator in creators:
        if creator.get("creatorType") != "author":
            continue
        authors.append(
            {
                "firstName": creator.get("firstName", ""),
                "lastName": creator.get("lastName", ""),
            }
        )
    return authors


def map_connector_item_to_item(payload: ConnectorItem) -> Item:
    """Create a new Anchor ``Item`` from a Zotero connector payload."""
    item_type = _ZOTERO_TO_ANCHOR_TYPE.get(payload.itemType, ItemType.OTHER)
    return Item(
        title=payload.title or "Untitled",
        item_type=item_type.value,
        authors=_extract_authors(payload.creators),
        abstract=payload.abstractNote,
        publication=payload.publicationTitle,
        volume=payload.volume,
        issue=payload.issue,
        pages=payload.pages,
        year=_parse_year(payload.date, payload.year),
        doi=payload.DOI,
        isbn=payload.ISBN,
        arxiv_id=payload.arxivID,
        url=payload.url,
        language=payload.language,
        extra=_collect_extra(payload),
    )


def _collect_extra(payload: ConnectorItem) -> dict[str, Any]:
    """Store unhandled Zotero fields in ``extra`` for later use."""
    extra: dict[str, Any] = {}
    if payload.extra:
        extra["zotero_extra"] = payload.extra
    return extra
