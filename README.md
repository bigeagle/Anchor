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

## Stack

- Backend: Python, FastAPI, Pydantic, pydantic-settings, SQLite
- Frontend: Vue, Vite, Tailwind CSS
- Python environment and dependencies: uv
- TypeScript dependencies and builds: pnpm
- Pre-commit hooks: prek

## Design Docs

- [Product Scope](docs/product.md)
- [Architecture](docs/architecture.md)
- [API Draft](docs/api.md)
