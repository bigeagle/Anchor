# Product Scope

## Positioning

Anchor is a lightweight, personal reference manager. It is **not** trying to be a
full Zotero replacement or a hosted service. The immediate goal is a small local
HTTP server that owns the library data, with integrations and a UI added one
phase at a time.

## Phased Roadmap

### Phase 1 — Backend core: item CRUD + attachments

**Goal:** Have a running local HTTP server that can create, read, update, and
delete bibliographic items, plus upload and download their file attachments.

In scope:

- FastAPI server launched from a single command.
- SQLite persistence in a configurable data directory.
- Alembic schema migrations set up from the start.
- `Item` model with fields:
  - `title` (required string)
  - `item_type` (required string, e.g. `article`, `book`, `webpage`)
  - `creators` (optional list of name strings)
  - `year` (optional integer)
  - `doi` (optional string)
  - `url` (optional string)
  - `abstract` (optional string)
  - `publication_title` (optional string)
  - `publisher` (optional string)
  - `extra` (optional string)
- REST endpoints for item CRUD:
  - `POST /api/v1/items`
  - `GET /api/v1/items`
  - `GET /api/v1/items/{item_id}`
  - `PATCH /api/v1/items/{item_id}`
  - `DELETE /api/v1/items/{item_id}`
- Attachments associated with items: upload, download, replace, list, delete.
- Local filesystem storage for attachments under the data directory.
- List endpoint supports `limit` and `offset` only.
- Automated tests for item CRUD and attachment upload/download.

Out of scope for Phase 1:

- Authentication and users.
- Search.
- Tags, collections, notes.
- Zotero Connector or Zotero API compatibility.
- Sync, soft deletes, revision metadata.
- Frontend.

**Definition of done:**
The server starts, and a client can `curl` to create, list, update, and delete
items, plus upload, replace, and download attachments.

---

### Phase 2 — Zotero Connector integration

**Goal:** Accept saves from Zotero Connector.

In scope:

- Authentication: single owner user + API token.
- Zotero Connector endpoints (`status`, `save`, `saveSnapshot`) for common web
  capture flows.
- Import service that turns connector payloads into items + attachments,
  with duplicate detection by DOI or URL.

Out of scope for Phase 2:

- Full two-way Zotero sync.
- Zotero API compatibility layer.
- Groups, annotations, and advanced Zotero data model features.
- Multi-device sync.

**Definition of done:**
The Zotero Connector can save a webpage or PDF into Anchor.

---

### Phase 3 — Frontend

**Goal:** Provide a small Vue web UI for browsing, searching, and editing the
library.

In scope:

- Library view: list items, search, pagination, create/edit/delete.
- Item detail view: metadata, creators, attachments.
- Settings view: data directory path and API token display.
- The frontend uses the same public API as any other client.

Out of scope for Phase 3:

- Tags.
- Offline/PWA support.
- In-browser PDF annotation.
- Real-time collaboration.

**Definition of done:**
A user can open the web UI in a browser and manage the library without using
`curl`.

---

### Phase 4 — Product polish

**Goal:** Add quality-of-life features once the core three phases are stable.

In scope:

- Tags (many-to-many with items) and tag management in the UI.
- Notes on items.
- Import endpoints for DOI, URL, BibTeX, RIS.
- Batch update APIs.
- Soft deletes / trash and restore.
- Full-text search improvements (FTS5).

Out of scope for Phase 4:

- Multi-device sync.
- Multi-user accounts.
- Hosted cloud service.

**Definition of done:**
Tags, notes, imports, batch updates, trash/restore, and search are all usable
through the API and the frontend.

---

## Long-term Non-Goals

These are intentionally deferred past the three phases above:

- Multi-device bidirectional sync.
- Multi-user accounts and sharing.
- Hosted cloud service.
- Full Zotero data model parity.
- Advanced PDF annotation sync.

## Stack

- Backend: Python, FastAPI, Pydantic, pydantic-settings, SQLite.
- Frontend: Vue, Vite, Tailwind CSS.
- Python environment and dependencies: `uv`.
- TypeScript dependencies and builds: `pnpm`.
- Pre-commit hooks: `prek`.
