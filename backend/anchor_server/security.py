"""API token authentication.

Single-owner token auth: tokens are stored as SHA-256 hashes in the
``api_tokens`` table and clients send ``Authorization: Bearer <token>``.
Auth is a no-op unless ``ANCHOR_AUTH_ENABLED`` is set, so local standalone
deployments keep working unchanged.
"""

import hashlib
import hmac
import logging
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from anchor_server.config import settings
from anchor_server.database import get_db
from anchor_server.models import ApiToken

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest stored for a plaintext token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_api_token(db: Session) -> str | None:
    """Create the owner API token on first startup.

    Uses ``ANCHOR_API_TOKEN`` when configured, otherwise generates a random
    token. Returns the plaintext only when a random token was generated (so
    it can be shown once); returns None when a token already exists or was
    seeded from configuration.
    """
    if db.query(ApiToken).first() is not None:
        return None
    if settings.api_token:
        db.add(ApiToken(token_hash=hash_token(settings.api_token)))
        db.commit()
        logger.info("API token seeded from ANCHOR_API_TOKEN")
        return None
    token = secrets.token_urlsafe(32)
    db.add(ApiToken(token_hash=hash_token(token)))
    db.commit()
    return token


def require_auth(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    """FastAPI dependency: enforce Bearer token auth when enabled."""
    if not settings.auth_enabled:
        return
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized
    digest = hash_token(authorization.removeprefix("Bearer ").strip())
    for row in db.query(ApiToken).all():
        if hmac.compare_digest(row.token_hash, digest):
            return
    raise unauthorized
