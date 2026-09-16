"""Validate and normalize OpenClaw WhatsApp hook payloads."""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from backend.infrastructure.connectors.connector_adapter import ConnectorPayloadError
from backend.models import Event


class OpenClawPayloadError(ConnectorPayloadError):
    pass


def deterministic_event_id(
    connector: str,
    account_id: str,
    channel: str,
    external_message_id: str,
    team_id: str,
) -> str:
    parts = (connector, account_id, channel, external_message_id, team_id)
    identity = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, f"flowstate:event:{identity}"))


class OpenClawInboundAdapter:
    connector_name = "openclaw"

    def normalize_event(self, payload: dict[str, Any]) -> Event:
        if not isinstance(payload, dict):
            raise OpenClawPayloadError("Payload must be a JSON object")
        connector = _required_text(payload, "connector")
        if connector != self.connector_name:
            raise OpenClawPayloadError("Unsupported connector")
        channel = _required_text(payload, "channel").lower()
        if channel != "whatsapp":
            raise OpenClawPayloadError("Unsupported channel")
        team_id = _required_text(payload, "team_id")
        account_id = _required_text(payload, "account_id")
        message_id = _required_text(payload, "message_id")
        text = _required_text(payload, "text")
        if payload.get("from_me") is not False:
            raise OpenClawPayloadError("Outbound or fromMe events are not accepted")

        sender = _required_text(payload, "sender")
        conversation_id = _required_text(payload, "conversation_id")
        timestamp = _timestamp(payload.get("timestamp"))
        participants = list(dict.fromkeys([sender, conversation_id]))
        return Event(
            id=deterministic_event_id(
                connector,
                account_id,
                channel,
                message_id,
                team_id,
            ),
            type="message_received",
            source="whatsapp",
            content=text,
            participants=participants,
            timestamp=timestamp,
            team_id=team_id,
            raw=dict(payload),
        )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OpenClawPayloadError(f"Missing or empty {key}")
    return value.strip()


def _timestamp(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise OpenClawPayloadError("Invalid timestamp") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000 if value > 10_000_000_000 else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise OpenClawPayloadError("Invalid timestamp") from exc
    raise OpenClawPayloadError("Missing or invalid timestamp")
