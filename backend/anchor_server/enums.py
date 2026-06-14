"""Domain enumerations."""

from enum import StrEnum


class ItemType(StrEnum):
    """Supported bibliographic item types."""

    JOURNAL_ARTICLE = "journalArticle"
    BOOK = "book"
    BOOK_SECTION = "bookSection"
    CONFERENCE_PAPER = "conferencePaper"
    THESIS = "thesis"
    REPORT = "report"
    PATENT = "patent"
    WEBPAGE = "webpage"
    DOCUMENT = "document"
    PREPRINT = "preprint"
    OTHER = "other"
