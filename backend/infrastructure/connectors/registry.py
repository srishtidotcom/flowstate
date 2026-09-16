"""Connector adapter registry; external implementations stay behind this module."""

from backend.infrastructure.connectors.connector_adapter import InboundConnectorAdapter
from backend.infrastructure.connectors.openclaw.adapter import OpenClawInboundAdapter


_ADAPTERS: dict[str, InboundConnectorAdapter] = {
    "openclaw": OpenClawInboundAdapter(),
}


def get_connector_adapter(name: str) -> InboundConnectorAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported connector: {name}") from exc
