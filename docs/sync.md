# Multi-Device Sync Design

Status: agreed design, not yet implemented.

## Context

Anchor runs on multiple devices, and all of them need write access
(multi-writer). Attachment bytes are already synchronized across devices with
Syncthing — the attachments directory lives inside a Syncthing folder. A
self-hosted central service on the public internet coordinates metadata sync.

Decisions already made:

- Conflict resolution: **last-writer-wins (LWW)**, ordered by the central
  server's change sequence. No conflict UI.
- The central server stores **metadata only**, never attachment bytes.
- Sync trigger: devices poll on an interval (~30 s) and **push immediately**
  on local writes. No WebSocket.

## Current-State Facts That Shape the Design

- `Item` / `Attachment` primary keys are UUIDs, so devices can create objects
  offline without ID collisions.
- `attachments.storage_path` is a **relative** path under the attachments
  directory (e.g. `pdfs/zhang_2024_foo.pdf`), so it is portable across
  devices with different data roots.
- Filenames are rendered from item metadata via a Jinja template, with `_1`,
  `_2` suffixes for local duplicates. This mechanism stays unchanged.
- There is no `version` / `deleted_at` yet, deletes are hard deletes, and
  there is no authentication. All three must land before sync.

## Architecture

One codebase, three runtime roles selected by configuration
(e.g. `ANCHOR_ROLE`):

```text
device A ──┐                         ┌── attachments dir (Syncthing folder,
device B ──┼── HTTPS /api/v1/sync ──▶│    shared peer-to-peer by devices)
device C ──┘    central server       └── central DB: metadata + change log only
                (FastAPI + SQLite)
```

- `standalone` (default): today's behavior, no sync.
- `central`: exposes sync endpoints, owns the authoritative change log.
- `device`: normal Anchor server plus a background sync client.

The central server also runs on SQLite; personal scale does not justify
another database.

## Schema Groundwork (prerequisite phase)

- Add `version` (integer, incremented on every local mutation) and
  `deleted_at` (nullable timestamp) to `items` and `attachments`.
- Switch deletes to soft deletes. Physical cleanup of tombstones can happen
  later, once all devices have acknowledged them.
- Devices get two additional local-only tables: `outbox` (pending pushes)
  and `sync_state` (device id + pull cursor). Neither is itself synced.
- Existing databases must be backed up to `backup/` before migrating, per
  `AGENTS.md`.

## Sync Protocol

The central server keeps a `changes` table (oplog):

| column          | meaning                                     |
|-----------------|---------------------------------------------|
| `seq`           | monotonically increasing, assigned by central |
| `object_type`   | `item` / `attachment`                       |
| `object_id`     | UUID                                        |
| `op`            | `upsert` / `delete`                         |
| `payload`       | full object snapshot                        |
| `origin_device` | device id that pushed the change            |
| `created_at`    | server timestamp                            |

Endpoints (all under `/api/v1/sync`, token-authenticated):

- `POST /push` — device uploads a batch of local changes. Central applies
  them to its own tables and appends oplog entries.
- `GET /changes?since=<seq>` — returns oplog entries newer than the cursor.
  Devices apply them idempotently (upsert by primary key; delete = set
  `deleted_at`). If `since` is older than the oldest retained oplog entry,
  respond `410 Gone` so the device falls back to a full snapshot.
- `GET /snapshot` — full dump for bootstrapping a new device. The response
  includes the `seq` the snapshot is consistent with; the device adopts it
  as its initial cursor.

Central `seq` values are the only global ordering. Local changes carry no
global sequence until the central server accepts them; the local outbox only
needs a local autoincrement id to preserve push order.

The oplog is also the durability backstop for LWW, so it cannot be trimmed
blindly. Retention policy (e.g. keep 30 days or the last N entries) plus the
`410 Gone` gap response together guarantee that a device that has been
offline too long re-bootstraps from a snapshot instead of silently falling
behind.

Why an oplog instead of `updated_at` deltas: idempotent, replayable, does not
depend on any device's local clock, and directly inspectable when debugging
("change #1523 set item X to ..."). LWW falls out naturally: whatever the
central applied last wins, and overwritten values remain visible in the log.

## Device-Side Sync Client

- A local `outbox` table records pending changes on every mutation. Entries
  are deleted only after the central server acknowledges the push.
- A single-row `sync_state` table holds the device's sync identity and
  cursor:

  ```text
  sync_state
    id            INTEGER PRIMARY KEY CHECK (id = 1)   -- enforce single row
    device_id     UUID      -- generated once on first start
    last_seq      INTEGER   -- largest central seq applied locally
    last_sync_at  DATETIME  -- last successful sync (for UI display)
  ```

- Background loop: push immediately whenever the outbox is non-empty;
  poll `changes?since=<last_seq>` every ~30 s.
- Applying remote changes overwrites local state unconditionally (LWW).
- **Cursor advancement commits in the same database transaction as the
  applied changes.** If apply crashes halfway, the cursor does not move and
  the next poll re-fetches the same entries — safe because apply is
  idempotent. Keeping the cursor in the same database (rather than a state
  file) is what makes this guarantee hold.
- Changes a device pushed itself come back on the next pull ("echo").
  Idempotent apply makes this harmless; as an optional optimization, skip
  entries whose `origin_device` is the local device and whose payload
  `version` is not ahead of local state.
- A `410 Gone` from `changes` means the local cursor fell behind retained
  oplog history: the device fetches a fresh snapshot, replaces its library
  state, and adopts the snapshot's `seq`.

All writes — public API, Zotero Connector (`/connector/*`), and frontend —
flow through the same service/repository layer, so the outbox hook lives
there and captures every write path uniformly.

## Attachments

- Bytes travel exclusively via Syncthing. The sync protocol carries only
  metadata (`id`, `item_id`, `filename`, `storage_path`, `size`,
  `content_type`).
- When a device receives attachment metadata but `storage_path` does not
  exist locally yet, the attachment is marked "pending" and shown as a
  placeholder in the UI; it becomes usable automatically once Syncthing
  delivers the file.
- The metadata-derived naming scheme is unchanged. The known residual risk:
  two devices saving different files that render to the same name while
  offline will collide in Syncthing (which preserves the loser as a
  `.sync-conflict` copy). Accepted as unlikely for personal use. Optional
  cheap mitigation: on apply, warn if a local file exists at `storage_path`
  with a different `size` than the metadata says.
- Only the device where a write happens touches its local filesystem
  (create / delete). Other devices receive the metadata via sync and the
  bytes via Syncthing. Renames therefore degrade to delete + create on
  peers, which Syncthing handles natively.

## Authentication and Transport

- Single owner token (as planned in Phase 4): stored as SHA-256 hash, sent
  as `Authorization: Bearer <token>`. Required on all sync endpoints.
- The central server sits behind HTTPS (e.g. Caddy reverse proxy). It must
  never be exposed unauthenticated.

## Implementation Order

1. Schema groundwork: `version`, `deleted_at`, soft deletes, migration with
   prior backup.
2. Authentication (token) — reusable by both roles.
3. Central: `changes` oplog + the three sync endpoints.
4. Device: `outbox` table, sync loop (push/pull), cursor persistence.
5. Attachment availability states ("pending" / ready) + optional size
   mismatch warning.
6. Frontend: sync status display (last sync time, pending outbox count,
   pending attachments).

Each step is independently testable and shippable.

## Out of Scope

- Conflict resolution UI or field-level merging.
- Real-time push (WebSocket / SSE) to devices.
- Central storage of attachment bytes.
- Multi-user accounts or sharing.
- Syncing the SQLite database file itself through Syncthing (would corrupt
  under multi-writer access; metadata sync replaces it).
