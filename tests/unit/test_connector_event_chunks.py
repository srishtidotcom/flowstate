from datetime import datetime, timezone

from backend.models import Event
from backend.preprocessing.normalizer import event_to_chunks


def test_connector_event_to_chunk_is_deterministic():
    event = Event(
        id="event-1",
        type="message_received",
        source="whatsapp",
        content="Prepare the demo",
        team_id="team-alpha",
        participants=["sender-a", "conversation-a"],
        timestamp=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
    )

    first = event_to_chunks(event)
    second = event_to_chunks(event)

    assert first == second
    assert first[0].text == "Prepare the demo"
    assert first[0].speaker == "sender-a"
    assert first[0].source_ref == "event:event-1"
    assert first[0].metadata["team_id"] == "team-alpha"
