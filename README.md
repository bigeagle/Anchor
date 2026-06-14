# Anchor

Anchor is a lightweight, personal-first reference manager. It runs as a local
HTTP server and exposes a stable API for the web UI, browser integrations,
automation scripts, and AI agents.

The first milestone is a single-machine, single-owner application:

- manage bibliographic metadata
- manage local attachments
- browse, search, and edit a personal library from a small web UI
- accept saves from Zotero Connector-compatible flows
- expose complete OpenAPI-backed HTTP APIs

Anchor is designed so future multi-device sync and multi-user hosting can be
added without rewriting the core data model.

## Roadmap

1. **Backend core** — CRUD for items plus file attachments.
2. **Zotero Connector** — accept saves from Zotero Connector.
3. **Frontend** — small Vue UI for browsing and editing the library.
4. **Product polish** — tags, notes, imports, batch updates, trash, FTS search.

See `docs/product.md` for the full phased plan.

## Stack

- Backend: Python, FastAPI, Pydantic, pydantic-settings, SQLite
- Frontend: Vue, Vite, Tailwind CSS
- Python environment and dependencies: uv
- TypeScript dependencies and builds: pnpm
- Pre-commit hooks: prek

## Development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

Install dependencies and activate the virtual environment:

```bash
uv sync
```

Run database migrations:

```bash
uv run alembic upgrade head
```

Start the backend server for development (uses `.env.dev` to keep data separate
from production):

```bash
uv run --env-file .env.dev uvicorn anchor_server.main:app --reload
```

The API will be available at `http://127.0.0.1:23119/api/v1`. Interactive API
docs are at `/docs`.

To start with the production `.env` instead, omit `--env-file .env.dev`.

Run the test suite:

```bash
uv run pytest -v
```

Run linting and formatting checks (also enforced by pre-commit hooks):

```bash
uv run prek run --all-files
```

## Configuration

Anchor uses sensible defaults and loads environment variables from `.env` when
present. All environment variables are prefixed with `ANCHOR_`:

| Variable | Default | Description |
|---|---|---|
| `ANCHOR_DATABASE_URL` | `sqlite:///./anchor.db` | SQLite database URL |
| `ANCHOR_DATA_DIR` | `./data` | Root directory for runtime data |
| `ANCHOR_ATTACHMENTS_DIR` | `./data/attachments` | Directory for attachment files (can be moved outside `DATA_DIR`) |
| `ANCHOR_ATTACHMENT_NAME_TEMPLATE` | `{{ year }}_{{ authors_last_names }}_{{ title_slug }}` | Jinja template for attachment filenames (extension is preserved) |
| `ANCHOR_HOST` | `127.0.0.1` | Server bind host |

Attachment files are organized under `<ANCHOR_ATTACHMENTS_DIR>/pdfs/` or
`<ANCHOR_ATTACHMENTS_DIR>/others/` based on content type/extension. Filenames are
generated from the configured Jinja template and made filesystem-safe. Duplicate
names are resolved by appending `_1`, `_2`, etc.

Available template variables: `year`, `title`, `title_slug`, `authors`,
`authors_last_names`, `authors_short`, `item_type`, `arxiv_id`, `publication`.
| `ANCHOR_PORT` | `23119` | Server bind port (same default as Zotero local server) |
| `ANCHOR_LOG_LEVEL` | `info` | Uvicorn log level |

Relative paths in `ANCHOR_DATA_DIR` are resolved against the current working
directory.

## Design Docs

- [Product Scope](docs/product.md)
- [Architecture](docs/architecture.md)
- [API Draft](docs/api.md)
