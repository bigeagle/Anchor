# Architecture

## Runtime Shape

The first version runs as one local or self-hosted server process:

```text
Browser / agents / Zotero Connector
              |
              v
        FastAPI HTTP server
              |
    -----------------------
    |          |          |
 SQLite   attachment   search
 database  storage     index
```

SQLite and local filesystem storage are the default persistence layer. The
server is the only writer. Other devices can access the same library through the
HTTP API when the owner exposes the server over a trusted network, VPN, tunnel,
or local LAN.

## Backend Modules

Recommended package layout:

```text
backend/
  anchor_server/
    main.py
    settings.py
    api/
      deps.py
      routes/
        items.py
        attachments.py
        collections.py
        tags.py
        search.py
        zotero_connector.py
        sync.py
        users.py
    core/
      database.py
      security.py
      storage.py
      search.py
      clocks.py
    models/
      item.py
      attachment.py
      collection.py
      tag.py
      note.py
      user.py
      sync.py
    schemas/
      item.py
      attachment.py
      collection.py
      zotero.py
      sync.py
    repositories/
      item_repo.py
      attachment_repo.py
      collection_repo.py
    services/
      item_service.py
      attachment_service.py
      import_service.py
      zotero_service.py
      search_service.py
      sync_service.py
```

Responsibilities:

- `api`: HTTP routing, request validation, response serialization.
- `services`: business rules and workflows.
- `repositories`: database reads and writes.
- `models`: ORM models and persistence shape.
- `schemas`: Pydantic input/output contracts.
- `core`: settings, security, storage, search, and infrastructure helpers.

## Backend Layering

The backend should keep HTTP contracts, business rules, and persistence concerns
separate. The normal request flow is:

```text
HTTP request
  -> api route
  -> schema validation
  -> service method
  -> repository method
  -> ORM model / database
  -> response schema
  -> HTTP response
```

### `models`

`models` define the database shape. In practice these are ORM models mapped to
tables such as `items`, `attachments`, `collections`, and `api_tokens`.

Models include persistence details:

- primary keys and foreign keys
- indexes and uniqueness constraints
- ownership fields such as `owner_user_id`
- sync-compatible fields such as `version` and `deleted_at`
- relationships between tables
- internal-only fields such as `token_hash`

Models are internal. They should not be treated as the public API contract.

### `schemas`

`schemas` define the API input and output shape using Pydantic. They are the
contract seen by the frontend, scripts, Zotero Connector adapters, and AI
agents.

Schemas should be specific to API use cases. For example:

- `ItemCreate`: fields a client may provide when creating an item.
- `ItemUpdate`: fields a client may patch.
- `ItemRead`: fields returned for a full item.
- `ItemListEntry`: smaller shape used in list views.

Schemas intentionally differ from models. A create request should not allow the
client to provide `id`, `owner_user_id`, `version`, or `deleted_at`, while a read
response may include some of those fields.

### `repositories`

`repositories` are the database access layer. They use ORM models to perform
queries and writes, and they hide persistence details from services.

Repository methods should express data operations:

- `get_by_id`
- `list`
- `create`
- `update`
- `soft_delete`
- `find_by_doi`
- `find_duplicate_candidates`
- `list_for_item`

Repositories are the right place for repeated database filters such as:

- excluding soft-deleted rows by default
- filtering by `owner_user_id`
- applying pagination
- eager-loading relationships needed by a use case

They should not contain high-level product behavior. For example, "when saving
from Zotero Connector, detect duplicate DOI, attach the PDF, and add a tag" is a
service workflow, not a repository method.

### `services`

`services` implement business workflows. They call repositories, storage helpers,
search helpers, import parsers, and other services as needed.

Service methods should express product actions:

- create an item after checking for duplicate DOI or URL
- upload an attachment and store both the file and metadata
- import a reference from a Zotero Connector request
- move an item between collections
- merge tags
- rebuild a search index

Services should not depend on FastAPI request objects. Keeping them independent
from HTTP makes them reusable from future CLI commands, background jobs, tests,
and sync workers.

### `api`

`api` modules are thin FastAPI routes. They should handle:

- path, query, and body parameters
- dependency injection, including `current_user`
- calling the appropriate service method
- choosing the response schema and status code
- translating expected service errors into HTTP errors

Routes should avoid direct ORM queries. If a route needs data, it should ask a
service or repository through the established layer boundary.

## Frontend Modules

Recommended frontend layout:

```text
frontend/
  src/
    api/
    components/
    layouts/
    router/
    stores/
    views/
```

Initial views:

- Library: collection/tag navigation, item list, detail panel.
- Item detail: metadata, creators, attachments, notes.
- Search: query and filters.
- Settings: data directory, API token, backup/export status.

The frontend should use the same public API as agents and external clients.

## Data Directory

Default local layout:

```text
~/.anchor/
  anchor.db
  attachments/
    ab/
      cd/
        attachment-id.pdf
  cache/
  backups/
  config.toml
```

The data directory should be configurable with an environment variable such as
`ANCHOR_DATA_DIR`.

## Identity And Ownership

Even though MVP is single-owner, the schema should include ownership fields:

- `users` table with one initial owner.
- `owner_user_id` or `created_by_user_id` on user-owned objects.
- API dependencies that resolve `current_user`.
- Tokens stored with a user association.

The first version can auto-create one local owner and require one API token. This
keeps the runtime simple while avoiding a future migration from anonymous data to
owned data.

## Sync Compatibility

Do not implement full sync in MVP, but every syncable object should include:

- stable `id`
- `owner_user_id`
- `created_at`
- `updated_at`
- nullable `deleted_at`
- integer `version`
- `created_by_device_id`
- nullable `updated_by_device_id`

Add a `devices` table early:

```text
devices
  id
  user_id
  name
  created_at
  last_seen_at
```

For MVP, the server can create one default device named `local-server`. Later
sync can use device IDs without changing existing object records.

## Core Tables

```text
users
  id
  display_name
  created_at
  updated_at
  disabled_at

api_tokens
  id
  user_id
  name
  token_hash
  created_at
  last_used_at
  revoked_at

items
  id
  owner_user_id
  key
  type
  title
  abstract
  year
  doi
  url
  publication_title
  publisher
  extra
  created_at
  updated_at
  deleted_at
  version
  created_by_device_id
  updated_by_device_id

creators
  id
  item_id
  role
  first_name
  last_name
  full_name
  order_index

attachments
  id
  owner_user_id
  item_id
  type
  title
  mime_type
  original_filename
  storage_key
  size
  checksum_sha256
  created_at
  updated_at
  deleted_at
  version

collections
  id
  owner_user_id
  parent_id
  name
  created_at
  updated_at
  deleted_at
  version

tags
  id
  owner_user_id
  name

item_collections
  item_id
  collection_id

item_tags
  item_id
  tag_id

notes
  id
  owner_user_id
  item_id
  content
  format
  created_at
  updated_at
  deleted_at
  version
```

## Deletion

Use soft deletes for syncable objects. Hard deletion can be reserved for local
maintenance commands after backup or sync retention windows are defined.

## Attachment Storage

Attachments should be addressed internally by `storage_key`, not by user-provided
filenames. The original filename remains metadata. Upload flow:

1. Stream file to a temporary path.
2. Compute SHA-256 and size.
3. Move into content-addressed or ID-addressed storage.
4. Create attachment metadata in the database.

This makes future attachment sync and deduplication easier.

## Search

Start with SQLite queries and indexes. Add SQLite FTS5 for title, abstract,
creator names, notes, and selected metadata once basic CRUD is stable.

## Security

MVP should still require authentication:

- Bearer token for API clients.
- Same token or session cookie for the frontend.
- Token hashes stored in the database.
- CORS locked down by default, configurable for local integrations.

Avoid treating localhost as automatically trusted because users may expose the
server through tunnels or reverse proxies.

## Future Sync Direction

The later sync protocol should be incremental:

- Clients push local changes with object versions and device IDs.
- Server stores accepted changes and returns conflicts where needed.
- Clients pull changes since a cursor.
- Attachments are synced separately by checksum and storage key.

Default conflict policy can be simple:

- Tags and collection membership: set union.
- Attachments: checksum-based coexistence.
- Metadata: last write wins with previous versions retained.
- Notes: preserve conflicting copies for manual merge.
