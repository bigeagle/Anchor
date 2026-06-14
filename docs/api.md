# API Draft

All public endpoints are versioned under `/api/v1`.

## Conventions

- Phase 1 has no authentication. Phase 2 adds `Authorization: Bearer <token>`.
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

## Phase 2 — Zotero Connector

### Zotero Connector

```text
GET  /api/v1/zotero-connector/status
POST /api/v1/zotero-connector/save
POST /api/v1/zotero-connector/saveSnapshot
```

These accept Zotero Connector payloads and create items + attachments.

---

## Phase 3 — Frontend Support

No new backend endpoints are required for the first frontend. The UI consumes
the Phase 1 and Phase 2 public APIs above. Optional convenience endpoints can
be added if the UI needs them.

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
