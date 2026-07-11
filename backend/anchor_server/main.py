"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from anchor_server.api.routes import attachments, items, zotero_connector
from anchor_server.config import settings

app = FastAPI(
    title="Anchor",
    description="Personal reference manager API",
    version="0.1.0",
)

API_PREFIX = "/api/v1"

app.include_router(items.router, prefix=API_PREFIX)
app.include_router(items.search_router, prefix=API_PREFIX)
app.include_router(attachments.router, prefix=API_PREFIX)
app.include_router(zotero_connector.router)


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
