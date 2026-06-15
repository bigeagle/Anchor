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


---

# Worklog — Phase 2

> Status: **completed**
> Period: 2026-06-15 ~ 2026-06-15
> Goal (from `docs/product.md`): make the Zotero browser extension able to save items and attachments into Anchor over the local HTTP server.

## What was delivered

### Phase 2.1 — Basic connector save workflow

- Implemented the modern Zotero connector workflow under `/connector/*`:
  - `POST /connector/ping` — heartbeat with capability prefs.
  - `POST /connector/getSelectedCollection` — returns the single-owner "My Library" target.
  - `POST /connector/saveItems` — creates Anchor items from Zotero translator payloads.
  - `POST /connector/sessionProgress` — tracks pending attachments and reports `done: true` only after all expected uploads finish.
  - `POST /connector/saveSnapshot` — creates a parent item; uses `document` for direct PDF saves and `webpage` otherwise.
  - `POST /connector/saveAttachment` — stores PDF/EPUB binaries uploaded by the extension.
  - `POST /connector/saveStandaloneAttachment` — creates a parent item + attachment in one step for restricted pages.
  - `POST /connector/saveSingleFile` — stores SingleFile HTML snapshots.
- Added `ConnectorSession` model and Alembic migration to correlate connector IDs with Anchor UUIDs across the multi-request save sequence.
- Added `import_service.py` for Zotero → Anchor field mapping, including `archiveID` → `arxiv_id` handling.
- Added `zotero_service.py` for save orchestration and session management.
- Moved API routes and schemas into `api/routes/` and `schemas/` packages.
- Added 11 connector tests covering ping, save flow, snapshots, and standalone attachments.

### Phase 2.2 — Translator support

- Added `translator_sync.py` to download translators from `repo.zotero.org` and cache them in `translators_dir`.
- Added `translator_service.py` to serve metadata/code, compute `translatorsHash`/`sortedTranslatorHash`, and provide proxy/hostname hints.
- Added connector endpoints:
  - `POST /connector/getTranslators`
  - `POST /connector/getTranslatorCode`
  - `GET /connector/proxies`
  - `GET /connector/getClientHostnames`
- Updated `/connector/ping` to include translator hashes.
- Added config options `translators_dir`, `zotero_repo_url`, and `http_proxy`.
- Added 11 translator tests.

### Supporting changes

- Split Phase 2 into Phase 2.1 and Phase 2.2 in `docs/product.md`, `docs/architecture.md`, and `docs/api.md`.
- Moved authentication and soft deletes from Phase 2 to Phase 4 in docs.
- Added `.env.dev` with separate `anchor.dev.db` and `data-dev/` so manual testing does not touch production data.
- Added `backup/` directory policy in `AGENTS.md` requiring a timestamped DB backup before production migrations.

## Decisions and course corrections

| Topic | Initial plan | Final approach | Why |
|---|---|---|---|
| Authentication in Phase 2 | Include single-owner API token | Moved to Phase 4 | Connector namespace (`/connector/*`) does not use auth; auth is a product-polish feature. |
| Phase 2 scope | Monolithic Phase 2 | Split into 2.1 (basic save) and 2.2 (translator support) | Translator serving is orthogonal to save flow and adds repo-sync complexity; splitting keeps milestones reviewable. |
| Attachment upload | Extension uploads binaries | Server does not download attachments | Modern connector workflow; simpler and avoids proxy/network issues on the server side. |
| `sessionProgress` | Simple `done: true` always | Track pending attachments | User requested the complete version so the extension progress window is accurate. |
| `arxiv_id` | Map only `arxivID` field | Also map `archiveID` and preserve `arXiv:` prefix | Zotero arXiv translator populates `archiveID`; user wants the canonical prefix kept. |
| Translator source | Git submodule or raw GitHub | Official `repo.zotero.org` API + local cache | Matches Zotero client behavior, supports incremental updates, and works through the user's HTTP proxy. |
| Missing connector endpoints | Not implemented | Added `hasAttachmentResolvers` (returns `false`) and `delaySync` (no-op) | Manual testing showed the extension stalls without these endpoints. |

## Known limitations / deferred to later phases

- No duplicate detection during import (explicitly deferred from Phase 2.1).
- No legacy connector workflow where the server downloads attachments.
- No word-processor integration, `/connector/import`, `/connector/installStyle`.
- Translator sync is a manual command for now; no automatic background refresh.
- No full-text search improvements (Phase 4).
- No authentication or multi-user support (Phase 4).

## Next step

Phase 3: a web frontend that consumes the public API to browse, create, edit, and delete items and attachments.


---

# Worklog — Follow-up changes (post Phase 2)

> Period: 2026-06-15

## Attachment Markdown conversion endpoint

Added `GET /api/v1/attachments/{attachment_id}/markdown` so AI agents can read
papers stored in Anchor as Markdown text.

- Installed `markitdown` (includes PDF support via pdfminer/pdfplumber).
- Added `markdown_cache_dir` config option (default `./data/cache/markdown`).
- Added `markdown_service.py`:
  - Converts attachments to Markdown using `MarkItDown`.
  - Caches results on disk keyed by attachment ID.
  - Invalidates cache when an attachment is deleted.
  - Cache is considered stale if the source file is newer than the cached
    Markdown (compared via `attachment.date_added`).
- Endpoint returns `text/markdown` via `PlainTextResponse`.
- Added 4 tests covering conversion, cache reuse, deletion invalidation, and 404.

Commit: `a9cbe11`

## Item list sorting

Extended `GET /api/v1/items/` with `order_by` and `sort` query parameters.

- `order_by`: `date_added`, `title`, `year`, `publication`, `item_type`, `doi`,
  `arxiv_id`.
- `sort`: `asc` or `desc` (default `desc`).
- Unknown `order_by` values return `400 Bad Request`.
- Updated `docs/api.md` and added 3 tests.

Commit: `dc65d6f`

---

# Worklog — AI agent skill: anchor-papers

> Period: 2026-06-15

## Goal

Give AI agents a convenient way to access, search, import, and fetch papers
stored in the local Anchor library.

## What was delivered

### 1. Project skill: `skill/anchor-papers/`

- Added `SKILL.md` with metadata, API cheat sheet, and workflow guidance.
- Added `scripts/anchor_papers.py`, an all-in-one CLI using PEP 723 inline
dependencies (`requests`, `markitdown[pdf]`).

Supported library commands:

- `list [--query]` — list items, with optional title-substring filter.
- `search <query>` — full cross-field search via `GET /api/v1/search`.
- `get <item_id>` — item details.
- `attachments <item_id>` — list attachments.
- `download <attachment_id> <output>` — download attachment bytes.
- `text <attachment_id>` — Markdown conversion via
  `GET /api/v1/attachments/{id}/markdown`.
- `import-pdf <path> --title ... --author ... --item-type ...` — create an item
  and upload a PDF, with optional metadata flags (year, url, doi, arxiv_id,
  abstract, publication, volume, issue, pages, language, isbn).

### 2. arXiv integration

Added an `arxiv` subcommand mirroring `zoterios arxiv`:

- `arxiv fetch <arxiv_id>` — fetch metadata from arXiv Atom API.
- `arxiv pdf <arxiv_id>` — download PDF to `~/.cache/anchor-papers/arxiv/pdf/`.
- `arxiv markdown <arxiv_id>` — convert PDF to Markdown.
- `arxiv source <arxiv_id>` — download and extract TeX source.
- `arxiv check <arxiv_id>` — search Anchor for an existing copy.
- `arxiv save <arxiv_id> [--no-pdf]` — save metadata (and PDF) to Anchor,
  skipping duplicates via `arxiv check`.

### 3. Backend search endpoint

- Added `GET /api/v1/search?q=...&limit=...`.
- Uses SQL `ilike` across titles, abstracts, authors (JSON cast), publication,
  identifiers (`doi`, `arxiv_id`, `isbn`, `url`), volume/issue/pages, language,
  and item type.
- Registered via a separate `search_router` in `main.py`.
- Updated `docs/api.md`.

### 4. Tests

- Added 3 backend tests for `/api/v1/search` in `tests/test_items.py`:
  - search by title/arxiv_id/author/DOI
  - no-match empty result
  - missing `q` returns 422
- Full test suite: 53 passed.

## Decisions and course corrections

| Topic | Initial approach | Final approach | Why |
|---|---|---|---|
| PDF text extraction in skill | Local `pymupdf` | Anchor's `/attachments/{id}/markdown` | Reuse Anchor's existing `markitdown` conversion; fewer dependencies. |
| arXiv Markdown | Reuse Anchor endpoint | Local `markitdown[pdf]` | arXiv PDF is not yet in Anchor; local conversion is needed. |
| `check` implementation | Client-side full scan | Backend `/api/v1/search` | Scalable and cleaner; personal libraries can still use search. |
| `import-pdf` required fields | Only `--title` | `--title`, `--author`, `--item-type` | Match user expectation for minimal viable bibliographic record. |
| Skill location | `.kimi-code/skills/` | `skill/anchor-papers/` | User explicitly asked for a top-level `skill/` directory. |

## Commits

- `e0b3283` — feat: add anchor-papers skill for AI agent paper access
- `e15dc6e` — feat(anchor-papers): add arxiv subcommands (fetch, pdf, markdown, source, save)
- `3e3203f` — feat: add /api/v1/search endpoint, arxiv check command, and backend tests

## Known limitations

- `/api/v1/search` uses `LIKE` filters, not FTS5, so it is a simple substring
  search and may slow down on very large libraries.
- `arxiv check` relies on the user having restarted the local Anchor server so
  that `/api/v1/search` is available.
- `arxiv pdf --open` only works on macOS.
