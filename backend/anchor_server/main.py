"""FastAPI application entry point."""

from fastapi import FastAPI

from anchor_server.api.routes import attachments, items, zotero_connector

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
