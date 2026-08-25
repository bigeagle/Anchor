# Architecture

## Runtime Shape

Anchor runs as a single local FastAPI process. Persistence is SQLite plus a
local filesystem directory for attachments (added in Phase 1).

```text
Browser / agents / Zotero Connector
              |
              v
        FastAPI HTTP server
              |
    -----------------------
    |          |          |
 SQLite   attachment   search
 database  storage     (SQLite)
```

The server is the only writer. Authentication is added in Phase 4; Phases 1,
2.1, and 2.2 run without auth to keep early milestones minimal.

For multi-device deployments, the same codebase can also run as a central
sync server or as a syncing device; see [sync.md](sync.md) for that design.

## Backend Layering

The backend keeps three concerns separate:

```text
HTTP request
  -> api route
  -> Pydantic schema validation
  -> service method
  -> repository method
  -> ORM model / SQLite
  -> response schema
  -> HTTP response
```

- `api`: thin routes, dependency injection, error translation.
- `services`: product workflows (create item, import from Zotero, upload file).
- `repositories`: database queries and writes, hiding persistence details.
- `models`: SQLAlchemy ORM tables. These are internal persistence models.
- `schemas`: Pydantic request/response contracts exposed by the API.
- `core`: settings, database connection, storage helpers, clocks, security.

Pydantic is used for API validation and configuration (`pydantic-settings`), not
for database tables. If you later want one class for both, `SQLModel` is an
option, but the default is SQLAlchemy + separate Pydantic schemas.

## Module Layout by Phase

### Phase 1 — Backend core

```text
backend/
  anchor_server/
    main.py
    config.py          # pydantic-settings, ANCHOR_* env vars
    database.py
    enums.py
    models.py          # all ORM tables in one module
    schemas/           # Pydantic request/response contracts
    api/
      routes/
        items.py
        attachments.py
    services/
      storage.py       # attachment file storage
      import_service.py
```

Phase 1 includes items and attachments. No search, no auth, no tags or
collections.

Note: the layering above still describes the intended data flow, but the code
keeps services calling the ORM directly — there is no separate `core/` or
`repositories/` package yet. Introduce them only when a second persistence
backend or genuinely shared query logic justifies the indirection.

### Phase 2.1 — Zotero Connector: basic save workflow

Add the Zotero Connector adapter (attachments and storage already exist from
Phase 1):

```text
anchor_server/
  api/routes/
    zotero_connector.py   # all /connector/* endpoints
  schemas/
    zotero.py             # request/response models for connector payloads
  services/
    import_service.py     # Zotero item -> Anchor item field mapping
    zotero_service.py     # session management and save orchestration
  models.py               # add ConnectorSession table
```

Connector endpoints live under `/connector/*`, outside the public `/api/v1`
namespace, because the extension expects the local Zotero server contract.

`ConnectorSession` tracks pending attachments so `/connector/sessionProgress`
can report `done: true` only after every expected attachment has been uploaded.
`hasAttachmentResolvers` returns `false` and `delaySync` is a no-op so the
extension's progress window closes cleanly.

### Phase 2.2 — Zotero Connector: translator support

Add translator serving so the extension can match pages against official Zotero
translators:

```text
anchor_server/
  services/
    translator_service.py # scan translator files, serve metadata and code
    translator_sync.py    # fetch/update translators from the Zotero repo
```

Translator files live under `ANCHOR_TRANSLATORS_DIR` (default
`./data/translators/`).

`/connector/getTranslators` returns translator metadata; `/connector/getTranslatorCode`
returns the JavaScript source. `ping` includes `translatorsHash` for incremental
updates.

### Phase 3 — Frontend

```text
frontend/
  package.json
  vite.config.ts
  src/
    services/      # API client (relative /api/v1 paths, vite proxy in dev)
    components/
    composables/
    router/
    utils/
    views/
      LibraryView.vue
      ItemView.vue
```

The frontend consumes the same public API as scripts. The Zotero Connector uses
its own `/connector/*` namespace. When `ANCHOR_FRONTEND_DIST_DIR` contains a
built `index.html`, the backend serves the SPA at `/` with fallback to
`index.html` for unknown paths.

### Phase 4 — Product polish

Add authentication, soft deletes, and schema fields needed for future sync:

```text
anchor_server/
  api/routes/        # auth dependencies wired into existing routers
  models/            # add Note table (models stay in the flat models.py today)
  services/          # markdown_service.py already exists for attachment text
```

Phase 4 also adds `version` and `deleted_at` fields to syncable objects. These
are the schema foundation for multi-device sync; the full design (oplog,
device outbox, LWW conflicts) is in [sync.md](sync.md).

## Schema Migrations

Use [Alembic](https://alembic.sqlalchemy.org/) to manage SQLAlchemy schema
migrations from the start. Even though the project is small, Alembic keeps
schema changes reproducible and avoids the "delete the SQLite file" workflow
during development.

Recommended workflow:

- Migrations live in `backend/migrations/versions/` (`alembic.ini` at the
  repo root points there via `script_location`).
- The first migration creates the Phase 1 tables (`items`, `attachments`).
- After any model change, generate a new revision with
  `alembic revision --autogenerate -m "..."`.
- The server can refuse to start if the database is not at the latest revision,
  or it can run `alembic upgrade head` automatically on startup.
- For tests, use an in-memory SQLite database or a fresh temp directory.

If Alembic ever feels like overkill, the migration history can still be replayed
as plain SQL because each Alembic revision is just a Python wrapper around SQL
operations.

## Data Directory

By default everything lives relative to the working directory:

```text
./anchor.db                 # SQLite database (ANCHOR_DATABASE_URL)
./data/                     # ANCHOR_DATA_DIR
  attachments/              # ANCHOR_ATTACHMENTS_DIR
    pdfs/                   # files named from item metadata (see below)
    others/
  translators/              # synced Zotero translators
  cache/markdown/           # Markdown conversion cache
```

Each path has its own `ANCHOR_*` override; relative paths resolve against the
process working directory. There is no config file — all settings come from
environment variables or `.env` (see `anchor_server/config.py`).

## Authentication

Phase 1, Phase 2.1, and Phase 2.2 have no authentication.

Phase 4 introduces a single owner user and one API token auto-created on first
startup. The token is stored as a SHA-256 hash. Clients send:

```text
Authorization: Bearer <token>
```

CORS is configurable and conservative by default.

Authentication is also a hard prerequisite for exposing a central sync server
on the public internet — sync endpoints must never run unauthenticated (see
[sync.md](sync.md)).

## Search

Phase 1 has no search; the item list endpoint only supports pagination.

Search is added in Phase 4, starting with SQLite `LIKE` queries and later
moving to FTS5.

## Attachment Storage

Attachment bytes are stored under `attachments/pdfs/` or `attachments/others/`
(classified by content type). Filenames are rendered from item metadata with a
Jinja template (`ANCHOR_ATTACHMENT_NAME_TEMPLATE`, default
`{{ year }}_{{ authors_last_names }}_{{ title_slug }}`), slugified to safe
lowercase; the template may introduce subdirectories. Local name collisions
get `_1`, `_2`, … suffixes.

The database stores only the **relative** path under the attachments directory
(`attachments.storage_path`), plus the rendered filename, MIME type, and size.
Relative paths keep the database portable across machines and make the
directory safe to synchronize with external tools such as Syncthing (see
[sync.md](sync.md) for how multi-device sync builds on this).

All attachment writes (public API, Zotero Connector) go through
`services/attachment_service.store_attachment`, which dedups by the rendered
target path (deterministic in item metadata, so re-saving the same item
collides on the same path). Clients that create an item together with its
first file should use the atomic `POST /items/with-attachment` endpoint: it
probes for a duplicate with a transient item before writing anything, so a
409 leaves no orphan item behind. Dedup rules:

- If a live attachment already claims the target path and the on-disk file
  has identical content (md5 computed on the spot), the write is a no-op
  (`DuplicateAttachmentError`). The plain upload endpoint returns 200 with
  the existing attachment (idempotent), the atomic
  `POST /items/with-attachment` returns 409 (nothing is written), and the
  Zotero Connector treats it as success — re-saves never surface as errors.

The connector additionally avoids duplicate *items* in two stages, since its
fixed multi-request protocol (`saveItems` → `saveAttachment`) cannot be
atomic. `saveItems` first probes hard identifiers (DOI → arXiv → ISBN → URL —
translator metadata is usually reliable) and maps the session onto an
existing item instead of creating a new one. Items without identifiers slip
through and create a shell, but when a later attachment upload hits a
duplicate owned by another item, the shell (created by that session, no live
attachments) is soft-deleted and the session is repointed at the existing
item — a duplicate save leaves zero visible new rows.
- If the target file exists with identical content but no attachment row
  claims the path (e.g. delivered out-of-band by Syncthing), the file is
  adopted instead of writing a copy.
- `storage_path` is unique, so paths held by tombstone rows stay claimed and
  new attachments get the `_1`, `_2`, … suffixes instead.

## Deletion

Phase 1, Phase 2.1, and Phase 2.2 use hard deletes for simplicity. Phase 4
switches to soft deletes (`deleted_at`) for items, attachments, and notes so
that sync can propagate tombstones across devices (see [sync.md](sync.md)).
