"""FastAPI application entry point."""

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from anchor_server.api.routes import attachments, items, notes, sync, zotero_connector
from anchor_server.config import settings
from anchor_server.database import get_db_context
from anchor_server.security import ensure_api_token, require_auth
from anchor_server.services import sync_client  # noqa: F401  (registers outbox hooks)

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx logs every HTTP request at INFO; that is pure noise for the sync
# loop's periodic polls. Keep request logs for warnings and errors only.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Seed the owner API token; start the sync loop on device role."""
    if settings.auth_enabled:
        with get_db_context() as db:
            token = ensure_api_token(db)
        if token:
            logger.warning(
                "Generated new API token (shown once, store it safely): %s", token
            )
    sync_task = None
    if settings.role == "device" and settings.central_url:
        sync_task = asyncio.create_task(sync_client.sync_loop())
    try:
        yield
    finally:
        if sync_task is not None:
            sync_task.cancel()


app = FastAPI(
    title="Anchor",
    description="Personal reference manager API",
    version="0.1.0",
    lifespan=lifespan,
)

API_PREFIX = "/api/v1"

_auth = [Depends(require_auth)]

app.include_router(items.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(items.search_router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(attachments.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(notes.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(sync.router, prefix=API_PREFIX, dependencies=_auth)
app.include_router(zotero_connector.router, dependencies=_auth)


@app.get(f"{API_PREFIX}/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unknown paths.

    Lets the Vue router's client-side routes (e.g. /items/{id}) survive a page
    refresh when the SPA is served by this backend.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Phase 3 — serve the built frontend at "/" when the dist directory exists.
# Mounted last so /api/v1/* and /connector/* keep matching their own routes.
_index_file = settings.frontend_dist_dir / "index.html"
if _index_file.is_file():
    app.mount(
        "/",
        SPAStaticFiles(directory=settings.frontend_dist_dir, html=True),
        name="frontend",
    )


def run() -> None:
    """Start uvicorn with host/port taken from settings.

    Keeps ANCHOR_PORT (repo-root .env) as the single source of truth for the
    listen port — the vite dev proxy reads the same value. Pass --reload for
    development auto-reload.
    """
    uvicorn.run(
        "anchor_server.main:app",
        host=settings.host,
        port=settings.port,
        reload="--reload" in sys.argv,
    )
