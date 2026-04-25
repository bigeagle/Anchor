# API Draft

All endpoints are versioned under `/api/v1`. MVP is single-owner, but responses
should still include ownership and revision metadata where useful.

## Conventions

- Authentication: `Authorization: Bearer <token>`.
- Request and response bodies: JSON, except file upload/download endpoints.
- IDs: stable UUID or ULID strings.
- Deleted objects are excluded by default.
- List endpoints should support pagination.
- Error responses should use a stable structure:

```json
{
  "error": {
    "code": "item_not_found",
    "message": "Item not found"
  }
}
```

## Items

```text
GET    /api/v1/items
POST   /api/v1/items
GET    /api/v1/items/{item_id}
PATCH  /api/v1/items/{item_id}
DELETE /api/v1/items/{item_id}
POST   /api/v1/items/{item_id}/restore
```

Useful filters for `GET /items`:

- `q`
- `type`
- `tag`
- `collection_id`
- `creator`
- `year`
- `doi`
- `url`
- `limit`
- `cursor`

## Creators

Creators may be managed as part of item create/update payloads. Separate
endpoints can be added later if editing workflows need them.

## Attachments

```text
GET    /api/v1/items/{item_id}/attachments
POST   /api/v1/items/{item_id}/attachments
GET    /api/v1/attachments/{attachment_id}
PATCH  /api/v1/attachments/{attachment_id}
DELETE /api/v1/attachments/{attachment_id}
GET    /api/v1/attachments/{attachment_id}/file
```

Upload should use multipart form data with a file field plus optional metadata.

## Collections

```text
GET    /api/v1/collections
POST   /api/v1/collections
GET    /api/v1/collections/{collection_id}
PATCH  /api/v1/collections/{collection_id}
DELETE /api/v1/collections/{collection_id}
POST   /api/v1/collections/{collection_id}/items/{item_id}
DELETE /api/v1/collections/{collection_id}/items/{item_id}
```

## Tags

```text
GET    /api/v1/tags
POST   /api/v1/items/{item_id}/tags
DELETE /api/v1/items/{item_id}/tags/{tag_id}
```

Tags can be created implicitly when attached to an item.

## Notes

```text
GET    /api/v1/items/{item_id}/notes
POST   /api/v1/items/{item_id}/notes
PATCH  /api/v1/notes/{note_id}
DELETE /api/v1/notes/{note_id}
```

## Search

```text
GET /api/v1/search?q=...
```

Search results should return typed hits:

```json
{
  "items": [],
  "attachments": [],
  "notes": []
}
```

## Imports

```text
POST /api/v1/import/doi
POST /api/v1/import/url
POST /api/v1/import/bibtex
POST /api/v1/import/ris
```

Import responses should include created item IDs and duplicate candidates.

## Zotero Connector Compatibility

Zotero Connector support should live in a clearly separated route module:

```text
GET  /api/v1/zotero-connector/status
POST /api/v1/zotero-connector/save
```

If real Zotero Connector compatibility requires unversioned or Zotero-shaped
paths, implement those paths as thin adapters that call the same import service.

## Agent-Oriented Batch APIs

Agents should not need to make hundreds of small calls for common tasks:

```text
POST /api/v1/batch/items/get
POST /api/v1/batch/items/update
POST /api/v1/batch/items/tag
POST /api/v1/batch/items/collections
```

Batch APIs should be conservative:

- bounded maximum batch size
- per-item success/error results
- no hidden partial rollback unless explicitly documented

## Reserved Future Sync APIs

These routes can exist as stubs or be left unimplemented until the sync phase:

```text
GET  /api/v1/sync/capabilities
GET  /api/v1/sync/changes?since=...
POST /api/v1/sync/push
GET  /api/v1/sync/attachments/missing
POST /api/v1/sync/attachments/{attachment_id}
```

Do not expose sync routes as production-ready until conflict behavior, cursors,
and retention rules are specified.

## Users And Devices

MVP can expose minimal introspection endpoints:

```text
GET /api/v1/me
GET /api/v1/devices
```

Actual user administration can wait until multi-user hosting is in scope.
