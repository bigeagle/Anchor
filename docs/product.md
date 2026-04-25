# Product Scope

## Positioning

Anchor is a lightweight personal reference manager, similar in purpose to
Zotero but smaller in scope. The core product is a local HTTP server that owns
the library data, attachments, and integration APIs. The included frontend is a
client of that server, not a separate source of truth.

## Product Principles

- Local-first data ownership: a user's library and attachments live in a data
  directory they control.
- HTTP-first integration: all user-facing and automation-facing capabilities are
  available through documented HTTP APIs.
- Single-owner first: the first version assumes one owner and one writable
  server instance.
- Compatibility where useful: Zotero Connector support is an import surface, not
  a commitment to copy Zotero's internal model.
- Migration-friendly: identifiers, ownership fields, soft deletes, and revision
  metadata are included early so sync and multi-user support can be added later.

## MVP

The first milestone should support:

- Create, read, update, delete, and restore bibliographic items.
- Store common metadata: title, type, creators, year, DOI, URL, abstract,
  publication title, publisher, tags, collections, and notes.
- Upload, download, list, rename, and delete attachments.
- Search by title, creator, DOI, URL, tags, collection, and basic text fields.
- Use a simple Vue frontend to browse, search, edit, and open attachments.
- Accept saves from Zotero Connector-compatible requests for common web capture
  flows.
- Provide an OpenAPI schema suitable for scripts and AI agents.
- Use token authentication even in single-owner mode.

## Explicit Non-Goals For MVP

- Multi-device bidirectional sync.
- Multi-user accounts and sharing.
- Collaborative editing.
- Hosted cloud service.
- Full Zotero data model parity.
- Advanced PDF annotation sync.
- Browser extension development beyond Zotero Connector compatibility.

## Future Capabilities To Preserve

Anchor should reserve room for:

- Multiple users in one server.
- Multiple devices per user.
- Incremental sync by change cursor.
- Attachment sync by checksum.
- Conflict records for notes and metadata.
- Optional remote object storage.
- Read-only sharing or public library views.

These capabilities should influence schema and API shape, but they should not
add runtime complexity to the first milestone.
