from copy import deepcopy

import pytest

from backend.infrastructure.connectors.openclaw.adapter import (
    OpenClawInboundAdapter,
    OpenClawPayloadError,
    deterministic_event_id,
)


def payload(**overrides):
    value = {
        "connector": "openclaw",
        "channel": "whatsapp",
        "account_id": "account-a",
        "team_id": "team-alpha",
        "sender": "sender-a",
        "conversation_id": "conversation-a",
        "timestamp": 1_789_552_800_000,
        "text": "Prepare the demo",
        "message_id": "message-a",
        "from_me": False,
        "metadata": {"safe": "value"},
        "openclaw_hook": {"event": {"messageId": "message-a"}},
    }
    value.update(overrides)
    return value


def test_openclaw_payload_normalizes_to_canonical_event_and_preserves_raw():
    original = payload()
    event = OpenClawInboundAdapter().normalize_event(deepcopy(original))

    assert event.type == "message_received"
    assert event.source == "whatsapp"
    assert event.team_id == "team-alpha"
    assert event.content == "Prepare the demo"
    assert event.participants == ["sender-a", "conversation-a"]
    assert event.timestamp.isoformat() == "2026-09-16T10:00:00+00:00"
    assert event.raw == original


def test_event_id_is_deterministic_and_team_scoped():
    args = ("openclaw", "account-a", "whatsapp", "message-a", "team-alpha")
    assert deterministic_event_id(*args) == deterministic_event_id(*args)
    assert deterministic_event_id(*args) != deterministic_event_id(*args[:-1], "team-beta")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"channel": "telegram"}, "Unsupported channel"),
        ({"from_me": True}, "Outbound or fromMe"),
        ({"from_me": None}, "Outbound or fromMe"),
        ({"team_id": ""}, "Missing or empty team_id"),
        ({"message_id": ""}, "Missing or empty message_id"),
        ({"text": "  "}, "Missing or empty text"),
    ],
)
def test_invalid_or_outbound_payloads_are_rejected(override, message):
    with pytest.raises(OpenClawPayloadError, match=message):
        OpenClawInboundAdapter().normalize_event(payload(**override))


def test_malformed_payload_shape_is_rejected():
    with pytest.raises(OpenClawPayloadError, match="JSON object"):
        OpenClawInboundAdapter().normalize_event([])  # type: ignore[arg-type]
