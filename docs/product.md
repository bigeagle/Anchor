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

### Phase 2.1 — Zotero Connector: basic save workflow

**Goal:** Accept saves from the Zotero browser extension using the modern
connector workflow: the extension creates items and uploads attachments directly
as binary blobs.

In scope:

- Connector namespace served from the same local HTTP server (`/connector/*`).
- Endpoints required by the modern save workflow:
  - `POST /connector/ping`
  - `POST /connector/getSelectedCollection`
  - `POST /connector/saveItems`
  - `POST /connector/sessionProgress`
  - `POST /connector/saveSnapshot`
  - `POST /connector/saveAttachment`
  - `POST /connector/saveStandaloneAttachment`
  - `POST /connector/saveSingleFile`
- Import service that maps Zotero translator payloads to Anchor items and
  attachments. Duplicate detection is deferred.
- Connector sessions that persist across the multi-request save sequence
  (`saveItems` → `saveAttachment`/`saveSingleFile` → `sessionProgress`).
- `sessionProgress` tracks pending attachments and only reports `done: true`
  after every expected attachment has been uploaded.
- `saveSnapshot` creates a `document` item when saving a PDF directly.

Out of scope for Phase 2.1:

- Authentication.
- The legacy workflow where the server downloads attachments itself.
- Translator listing/execution, proxy support, style import, word-processor
  integration, and other advanced connector endpoints (see Phase 2.2).
- Full two-way Zotero sync.
- Zotero API compatibility layer.
- Groups, annotations, and advanced Zotero data model features.
- Multi-device sync.

**Definition of done:**
The Zotero Connector can save a webpage, an article with PDF, or a standalone
PDF into Anchor, and the saved items and attachments appear through the Phase 1
public API.

---

### Phase 2.2 — Zotero Connector: translator support

**Goal:** Enable rich metadata extraction by serving translators to the
extension, so pages matched by official Zotero translators are saved with full
bibliographic metadata.

In scope:

- Bundle or sync the official Zotero translators repository.
- `POST /connector/getTranslators` — return translator metadata.
- `POST /connector/getTranslatorCode` — return translator JavaScript code.
- `ping` returns `translatorsHash` / `sortedTranslatorHash` for incremental
  updates.
- Proxy support (`GET /connector/proxies`, `GET /connector/getClientHostnames`)
  if needed by translators.

Out of scope for Phase 2.2:

- Authentication.
- The legacy attachment-download workflow.
- Word-processor integration, `/connector/import`, `/connector/installStyle`.
- Full two-way Zotero sync.

**Definition of done:**
The Zotero Connector can save a journal article, news article, or book page
matched by an official translator and populate Anchor with complete metadata.

---

### Phase 3 — Frontend

**Goal:** Provide a small Vue web UI for browsing, searching, and editing the
library.

In scope:

- Library view: list items, search, pagination, create/edit/delete.
- Item detail view: metadata, creators, attachments.
- Settings view: data directory path display.
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

- Authentication: single owner user + API token.
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
