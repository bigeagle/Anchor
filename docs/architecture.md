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

The server is the only writer. Authentication is added in Phase 2; Phase 1 runs
without auth to keep the first milestone minimal.

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
  pyproject.toml
  anchor_server/
    main.py
    settings.py
    api/
      deps.py
      routes/
        items.py
        attachments.py
    core/
      database.py
      clocks.py
      storage.py
    models/
      item.py
      attachment.py
    schemas/
      item.py
      attachment.py
    repositories/
      item_repo.py
      attachment_repo.py
    services/
      item_service.py
      attachment_service.py
```

Phase 1 includes items and attachments. No search, no auth, no tags or
collections.

### Phase 2 — Zotero Connector integration

Add authentication and the Zotero Connector adapter (attachments and storage
already exist from Phase 1):

```text
anchor_server/
  api/routes/
    zotero_connector.py
  core/
    security.py
  models/
    note.py            # optional, only if connector needs it
  schemas/
    zotero.py
  services/
    import_service.py
    zotero_service.py
```

Phase 2 also adds `version` and `deleted_at` fields to syncable objects so
future sync does not need a migration.

### Phase 3 — Frontend

```text
frontend/
  package.json
  vite.config.ts
  src/
    api/           # generated or hand-written API client
    components/
    layouts/
    router/
    stores/
    views/
      LibraryView.vue
      ItemDetailView.vue
      SettingsView.vue
```

The frontend consumes the same public API as scripts and the Zotero Connector.

## Schema Migrations

Use [Alembic](https://alembic.sqlalchemy.org/) to manage SQLAlchemy schema
migrations from the start. Even though the project is small, Alembic keeps
schema changes reproducible and avoids the "delete the SQLite file" workflow
during development.

Recommended workflow:

- Migrations live in `backend/alembic/versions/`.
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

Default layout under `~/.anchor/`:

```text
~/.anchor/
  anchor.db
  config.toml
  attachments/       # Phase 1
    ab/
      cd/
        {attachment-id}.pdf
```

`ANCHOR_DATA_DIR` overrides the default path.

## Authentication

Phase 1 has no authentication.

Phase 2 introduces a single owner user and one API token auto-created on first
startup. The token is stored as a SHA-256 hash. Clients send:

```text
Authorization: Bearer <token>
```

CORS is configurable and conservative by default.

## Search

Phase 1 has no search; the item list endpoint only supports pagination.

Search is added in Phase 4, starting with SQLite `LIKE` queries and later
moving to FTS5.

## Attachment Storage

Attachments are stored by ID under a sharded directory. Metadata keeps the
original filename, MIME type, size, and SHA-256 checksum. This makes future
sync/deduplication easier.

## Deletion

Phase 1 uses hard deletes for simplicity. Phase 2 switches to soft deletes
(`deleted_at`) for items, attachments, and notes so future sync can see
tombstones.
