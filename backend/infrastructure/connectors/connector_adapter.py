"""Channel-neutral boundary for normalizing inbound connector events."""

from typing import Any, Protocol

from backend.models import Event


class ConnectorPayloadError(ValueError):
    """An external connector payload cannot be normalized safely."""


class InboundConnectorAdapter(Protocol):
    connector_name: str

    def normalize_event(self, payload: dict[str, Any]) -> Event:
        """Validate and normalize an external payload into the canonical Event."""
        ...
