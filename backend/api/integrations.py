"""Authenticated loopback-only HTTP ingress for external connectors."""

import ipaddress
import json
import os

import redis
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.infrastructure.connectors.connector_adapter import ConnectorPayloadError
from backend.infrastructure.connectors.registry import get_connector_adapter
from backend.infrastructure.connectors.security import (
    IngressAuthenticationError,
    verify_signature,
)
from backend.infrastructure.connectors.service import accept_connector_event


router = APIRouter(prefix="/integrations", tags=["integrations"])
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)


class IngressResponse(BaseModel):
    event_id: str
    job_id: str
    status: str
    duplicate: bool


@router.post(
    "/openclaw/events",
    response_model=IngressResponse,
    status_code=202,
)
async def openclaw_event(request: Request, response: Response) -> IngressResponse:
    if request.client is None or not _is_loopback(request.client.host):
        raise HTTPException(status_code=403, detail="Connector ingress is loopback-only")

    secret = os.getenv("FLOWSTATE_BRIDGE_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Connector ingress is not configured")
    body = await request.body()
    try:
        verify_signature(
            body,
            request.headers.get("x-flowstate-timestamp"),
            request.headers.get("x-flowstate-signature"),
            secret,
        )
    except IngressAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON") from exc

    try:
        acceptance = accept_connector_event(
            get_connector_adapter("openclaw"),
            payload,
            r,
        )
    except ConnectorPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if acceptance.duplicate:
        response.status_code = 200
    return IngressResponse(
        event_id=acceptance.event.id,
        job_id=acceptance.job.id,
        status=acceptance.job.status,
        duplicate=acceptance.duplicate,
    )


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
