# API Draft

All public endpoints are versioned under `/api/v1`. The Zotero Connector uses a
separate local-server namespace under `/connector/*` and is documented in its
own section below.

## Conventions

- Phase 1, Phase 2.1, and Phase 2.2 have no authentication. Phase 4 adds `Authorization: Bearer <token>`.
- Request and response bodies are JSON unless noted.
- IDs are stable UUID strings.
- List endpoints support pagination with `limit` and `offset` (`cursor` is added
  later).
- Error responses use a stable structure:

```json
{
  "error": {
    "code": "item_not_found",
    "message": "Item not found"
  }
}
```

## Phase 1 — Items and Attachments

### Items

```text
GET    /api/v1/items
POST   /api/v1/items
GET    /api/v1/items/{item_id}
PATCH  /api/v1/items/{item_id}
DELETE /api/v1/items/{item_id}
```

`GET /api/v1/items` supports pagination only:

- `limit`
- `offset`

Creators are embedded in item create/update payloads.

### Search

```text
GET /api/v1/search?q=...
```

Search across item titles, abstracts, authors, publication, identifiers (`doi`,
`arxiv_id`, `isbn`, `url`), volume/issue/pages, language, and item type.

- `q` (required) — search term
- `limit` — default 20, max 1000

### Attachments

```text
GET    /api/v1/items/{item_id}/attachments
POST   /api/v1/items/{item_id}/attachments
GET    /api/v1/attachments/{attachment_id}
PATCH  /api/v1/attachments/{attachment_id}
DELETE /api/v1/attachments/{attachment_id}
GET    /api/v1/attachments/{attachment_id}/file
```

Upload uses multipart form data with a `file` field plus optional metadata.

---

## Phase 2.1 — Zotero Connector: basic save workflow

The connector namespace is served from `/connector/*` on the same local HTTP
server. It implements the modern Zotero connector workflow: the extension
creates items and then uploads attachments directly as binary blobs.

### Implemented endpoints

```text
POST /connector/ping
POST /connector/getSelectedCollection
POST /connector/saveItems
POST /connector/sessionProgress
POST /connector/saveSnapshot
POST /connector/saveAttachment
POST /connector/saveStandaloneAttachment
POST /connector/saveSingleFile
POST /connector/hasAttachmentResolvers
POST /connector/delaySync
```

All requests and responses are JSON except `saveAttachment` and
`saveStandaloneAttachment`, which accept raw binary bodies with metadata in the
`X-Metadata` header.

The connector endpoints do **not** require authentication or CORS headers; the
browser extension talks directly to `127.0.0.1:23119`.

### Save flow

1. The extension calls `/connector/ping` to confirm the server is online and
check capabilities (`supportsAttachmentUpload` must be `true`).
2. Before saving it calls `/connector/getSelectedCollection` to learn the
target library and whether it is editable.
3. For translator-based captures it posts to `/connector/saveItems`. The server
creates Anchor items and stores a session mapping from connector IDs to Anchor
IDs. The set of expected binary attachments is recorded in the connector
session.
4. The extension uploads PDFs/EPUBs via `/connector/saveAttachment` and HTML
snapshots via `/connector/saveSingleFile`. Each uploaded attachment is removed
from the session's pending list.
5. The extension polls `/connector/sessionProgress` until `done` is `true`.
`done` becomes `true` only after every expected attachment has been uploaded.
6. For generic web pages with no translator, `/connector/saveSnapshot` creates a
parent item and is optionally followed by `/connector/saveSingleFile`.
7. For PDFs saved directly, `/connector/saveSnapshot` creates a `document` item
and is optionally followed by `/connector/saveSingleFile`.
8. For restricted pages (e.g. Firefox PDF viewer), `/connector/saveStandaloneAttachment`
creates a parent item and attaches the binary in one step.

### Not implemented in Phase 2.1

Duplicate detection, the legacy attachment-download workflow, translator
listing/execution, `/connector/proxies`, `/connector/import`,
`/connector/installStyle`, and word-processor integration endpoints are
deferred.

---

## Phase 2.2 — Zotero Connector: translator support

Phase 2.2 adds translator serving so the extension can match pages against
official Zotero translators.

### Endpoints

```text
POST /connector/getTranslators
POST /connector/getTranslatorCode
```

`ping` will also include `translatorsHash` / `sortedTranslatorHash` so the
extension can update its translator cache incrementally.

### Translator bundle

Translator JavaScript files are bundled under the Anchor data directory or
synced from the official Zotero translators repository. `getTranslators`
returns the metadata object parsed from each file's header; `getTranslatorCode`
returns the full JavaScript source for a given `translatorID`.

---

## Phase 3 — Frontend Support

No new backend endpoints are required for the first frontend. The UI consumes
the Phase 1 public API. The Zotero Connector namespace remains separate.
Optional convenience endpoints can be added if the UI needs them.

---

## Phase 4 — Product Polish

Public endpoints deferred until the core product is stable:

### Search

```text
GET /api/v1/search?q=...
```

### Tags

```text
GET    /api/v1/tags
POST   /api/v1/items/{item_id}/tags
DELETE /api/v1/items/{item_id}/tags/{tag_id}
```

### Notes

```text
GET    /api/v1/items/{item_id}/notes
POST   /api/v1/items/{item_id}/notes
PATCH  /api/v1/notes/{note_id}
DELETE /api/v1/notes/{note_id}
```

### Import

```text
POST /api/v1/import/doi
POST /api/v1/import/url
POST /api/v1/import/bibtex
POST /api/v1/import/ris
```

### Batch

```text
POST /api/v1/batch/items/get
POST /api/v1/batch/items/update
```

### Trash / Restore

```text
GET    /api/v1/trash
POST   /api/v1/items/{item_id}/restore
```

---

## Reserved for the Future

These are intentionally not implemented in the three phases above:

```text
GET  /api/v1/sync/capabilities
GET  /api/v1/sync/changes?since=...
POST /api/v1/sync/push
GET  /api/v1/sync/attachments/missing
```
