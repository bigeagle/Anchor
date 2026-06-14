"""Zotero Connector endpoints under /connector/*."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from anchor_server.database import get_db
from anchor_server.schemas.zotero import (
    ConnectorCollectionResponse,
    ConnectorPingResponse,
    ConnectorSaveAttachmentMetadata,
    ConnectorSaveItemsRequest,
    ConnectorSaveSingleFileRequest,
    ConnectorSaveSnapshotRequest,
    ConnectorSessionProgressRequest,
    ConnectorSessionProgressResponse,
    ConnectorStandaloneAttachmentMetadata,
    ConnectorStandaloneAttachmentResponse,
)
from anchor_server.services import translator_service, zotero_service

router = APIRouter(tags=["zotero-connector"])

# The version the connector sees in X-Zotero-Version responses.
CONNECTOR_SERVER_VERSION = "0.2.0"


def _connector_response(data: Any) -> Response:
    """Return a JSON response with the X-Zotero-Version header."""
    return Response(
        content=json.dumps(data),
        media_type="application/json",
        headers={"X-Zotero-Version": CONNECTOR_SERVER_VERSION},
    )


@router.post("/connector/ping")
def ping(request: Request) -> Response:
    """Connector heartbeat and capability advertisement."""
    prefs = {
        "downloadAssociatedFiles": True,
        "automaticSnapshots": True,
        "reportActiveURL": True,
        "supportsAttachmentUpload": True,
        "supportsTagsAutocomplete": False,
        "canUserAddNote": False,
        "translatorsHash": translator_service.get_translators_hash(),
        "sortedTranslatorHash": translator_service.get_translators_hash(
            sorted_ids=True
        ),
    }
    return _connector_response(ConnectorPingResponse(prefs=prefs).model_dump())


@router.post("/connector/getSelectedCollection")
def get_selected_collection(request: Request) -> Response:
    """Return the default library target for single-owner Anchor."""
    response = ConnectorCollectionResponse(
        targets=[{"id": "default", "name": "My Library"}],
    )
    return _connector_response(response.model_dump())


@router.post("/connector/saveItems")
def save_items(
    payload: ConnectorSaveItemsRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Create items from a Zotero translator result."""
    try:
        result = zotero_service.save_items(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connector_response(result)


@router.post("/connector/sessionProgress")
def session_progress(
    payload: ConnectorSessionProgressRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Return the current progress for a connector save session."""
    result = zotero_service.session_progress(db, payload.sessionID)
    return _connector_response(ConnectorSessionProgressResponse(**result).model_dump())


@router.post("/connector/saveSnapshot")
def save_snapshot(
    payload: ConnectorSaveSnapshotRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Create a parent item for a webpage or direct PDF save."""
    try:
        result = zotero_service.save_snapshot(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connector_response(result)


@router.post("/connector/saveAttachment")
async def save_attachment(
    request: Request,
    session_id: str = Query(..., alias="sessionID"),
    x_metadata: str = Header(..., alias="X-Metadata"),
    db: Session = Depends(get_db),
) -> Response:
    """Store a binary attachment uploaded by the connector."""
    metadata = ConnectorSaveAttachmentMetadata.model_validate_json(x_metadata)
    data = await request.body()
    try:
        result = zotero_service.save_attachment(db, session_id, metadata, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connector_response(result)


@router.post("/connector/saveStandaloneAttachment")
async def save_standalone_attachment(
    request: Request,
    session_id: str = Query(..., alias="sessionID"),
    x_metadata: str = Header(..., alias="X-Metadata"),
    db: Session = Depends(get_db),
) -> Response:
    """Create a parent item and store a standalone binary attachment."""
    metadata = ConnectorStandaloneAttachmentMetadata.model_validate_json(x_metadata)
    data = await request.body()
    try:
        result = zotero_service.save_standalone_attachment(
            db, session_id, metadata, data
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connector_response(
        ConnectorStandaloneAttachmentResponse(**result).model_dump()
    )


@router.post("/connector/saveSingleFile")
def save_single_file(
    payload: ConnectorSaveSingleFileRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Store a SingleFile HTML snapshot attachment."""
    try:
        result = zotero_service.save_single_file(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connector_response(result)


@router.post("/connector/hasAttachmentResolvers")
def has_attachment_resolvers() -> Response:
    """Report that Anchor has no attachment resolvers (e.g. OA PDF lookup)."""
    return _connector_response(False)


@router.post("/connector/delaySync")
def delay_sync() -> Response:
    """No-op endpoint for the connector's sync delay request."""
    return _connector_response({})


@router.post("/connector/getTranslators")
def get_translators() -> Response:
    """Return metadata for all cached translators."""
    return _connector_response(translator_service.list_translators())


@router.post("/connector/getTranslatorCode")
def get_translator_code(payload: dict[str, Any]) -> Response:
    """Return JavaScript source for a translator by ID."""
    translator_id = payload.get("translatorID")
    if not translator_id:
        raise HTTPException(status_code=400, detail="translatorID is required")
    try:
        code = translator_service.get_translator_code(translator_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=code,
        media_type="application/javascript",
        headers={"X-Zotero-Version": CONNECTOR_SERVER_VERSION},
    )


@router.get("/connector/proxies")
def get_proxies() -> Response:
    """Return proxy configuration hints."""
    return _connector_response(translator_service.get_proxy_list())


@router.get("/connector/getClientHostnames")
def get_client_hostnames() -> Response:
    """Return local hostnames the connector may see."""
    return _connector_response(translator_service.get_client_hostnames())
