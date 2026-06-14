"""FastAPI application entry point."""

from fastapi import FastAPI

from anchor_server.api import attachments, items

app = FastAPI(
    title="Anchor",
    description="Personal reference manager API",
    version="0.1.0",
)

app.include_router(items.router)
app.include_router(attachments.router)


@app.get("/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
