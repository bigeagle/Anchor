# Worklog — Phase 1

> Status: **completed**
> Period: 2026-06-14 ~ 2026-06-15
> Goal (from `docs/product.md`): a running local HTTP server that can create, read, update, and delete bibliographic items, plus upload and download their file attachments.

## What was delivered

### 1. Project skeleton

- Initialized Python project with `uv`, `prek` pre-commit hooks, and a phased roadmap.
- Wrote `docs/product.md`, `docs/architecture.md`, `docs/api.md`, and `README.md`.
- Added `AGENTS.md` with commit policy: short tasks must ask before committing, long-running tasks should commit for debuggability.

### 2. Item CRUD backend

- Implemented `Item` SQLAlchemy model and Pydantic request/response schemas.
- REST endpoints under `/api/v1/items`:
  - `POST /api/v1/items`
  - `GET /api/v1/items`
  - `GET /api/v1/items/{item_id}`
  - `PUT /api/v1/items/{item_id}`
  - `DELETE /api/v1/items/{item_id}`
- Added `ItemType` StrEnum with 11 common bibliographic types (`journalArticle`, `book`, `bookSection`, `conferencePaper`, `thesis`, `report`, `patent`, `webpage`, `document`, `preprint`, `other`) and Pydantic validation.
- Promoted `arxiv_id` to a top-level item field.
- Initially added a unique constraint on `arxiv_id`, then removed it after realizing duplicate arXiv entries are valid in a personal library.

### 3. Attachment storage and CRUD

- Implemented `Attachment` model associated with items; deleting an item cascades to its attachments.
- Endpoints under `/api/v1/items/{item_id}/attachments` and `/api/v1/attachments/{attachment_id}`:
  - upload via multipart form
  - list
  - download (`GET /api/v1/attachments/{attachment_id}`)
  - update metadata
  - delete
- Storage layout:
  - Configurable `ANCHOR_ATTACHMENTS_DIR`.
  - Files organized into `pdfs/` and `others/` based on content type.
  - Filenames generated from a Jinja template (`ANCHOR_ATTACHMENT_NAME_TEMPLATE`) with variables like `year`, `title_slug`, `authors_last_names`, etc.
  - Template output can contain path separators; subdirectories are auto-created.
  - Duplicate names are resolved by appending `_1`, `_2`, etc.
- Added `href` computed field to `AttachmentOut` so clients get a ready-to-use download URL.
- Download behavior: previewable types (PDF, HTML, images, etc.) are served `inline`; unknown binaries are offered as `attachment` downloads.

### 4. Configuration

- Environment variables are prefixed with `ANCHOR_`.
- Key settings:
  - `ANCHOR_DATABASE_URL`
  - `ANCHOR_DATA_DIR`
  - `ANCHOR_ATTACHMENTS_DIR`
  - `ANCHOR_ATTACHMENT_NAME_TEMPLATE`
  - `ANCHOR_HOST` (default `127.0.0.1`)
  - `ANCHOR_PORT` (default `23119`, matching Zotero local server)
  - `ANCHOR_LOG_LEVEL`
- Added `.env.example`.
- Default data directory `./data` is ignored by git.

### 5. Migrations

- Set up Alembic from the start.
- Migration history covers:
  - Initial `items` and `attachments` tables.
  - Adding `arxiv_id` with unique constraint.
  - Removing the unique constraint (using `batch_alter_table` for SQLite compatibility).

### 6. Tests

- Added `tests/test_items.py` and `tests/test_attachments.py`.
- Tests run against an in-memory SQLite database and a temporary attachments directory, isolated from local `.env` settings.
- Coverage includes:
  - item create/list/get/update/delete
  - validation errors (empty title, invalid `item_type`)
  - `arxiv_id` persistence
  - attachment upload/list/download/delete
  - cascade delete from item to attachments
  - PDF vs. others directory separation
  - duplicate filename protection
  - Jinja template subdirectory creation
  - inline vs. attachment `Content-Disposition`

## Decisions and course corrections

| Topic | Initial approach | Final approach | Why |
|---|---|---|---|
| `arxiv_id` uniqueness | Unique constraint | Removed | Personal libraries can contain duplicate arXiv entries (e.g., preprint + journal version). |
| PDF download | Inline for all PDFs (`ef6df05`) | Reverted, then inline only for previewable types | Serving every binary inline is too broad; limiting to previewable MIME types is safer and matches browser expectations. |
| Item update method | `PATCH` in docs | `PUT` in implementation | Implementation uses full replacement; docs will be aligned in a follow-up or Phase 2. |
| SQLite migrations | Direct `DROP INDEX`/`DROP CONSTRAINT` | `batch_alter_table` | SQLite requires table recreation for most ALTER operations. |
| Test isolation | Reused local `./data` | Temporary `tmp_path` + monkeypatch | Keeps CI/dev environments clean and repeatable. |

## Known limitations / deferred to later phases

- No authentication (Phase 2).
- No search beyond exact-match query param placeholder in `GET /api/v1/items`.
- No tags, collections, notes, or import endpoints.
- No Zotero Connector compatibility.
- Hard deletes only (soft deletes deferred to Phase 2).

## Next step

Phase 2: Zotero Connector integration. This will add a single-owner auth model, API token, and endpoints to accept saves from the Zotero Connector.
