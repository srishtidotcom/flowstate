from datetime import datetime, timezone
from types import SimpleNamespace

import backend.worker as worker
from backend.extraction.extractor import ExtractedTask
from backend.models import Event
from backend.preprocessing.normalizer import Chunk


def _extracted(source_ref: str) -> ExtractedTask:
    return ExtractedTask(
        title="Finish the video",
        owner=None,
        deadline="tomorrow",
        confidence=0.95,
        dependencies=[],
        source_ref=source_ref,
        source_snippet="Video is due tomorrow, make sure it gets done by the team",
    )


def _avoid_persistence(monkeypatch):
    monkeypatch.setattr(
        worker,
        "persist_extracted_activity",
        lambda job, chunks, tasks, **kwargs: SimpleNamespace(tasks=[]),
    )


def test_connector_worker_passes_canonical_event_timestamp_to_enrichment(monkeypatch):
    event_timestamp = datetime(2026, 9, 17, 16, 24, 26, tzinfo=timezone.utc)
    event = Event(
        id="event-1",
        type="whatsapp_message",
        source="whatsapp",
        content="Video is due tomorrow, make sure it gets done by the team",
        participants=["sender-a"],
        timestamp=event_timestamp,
        team_id="team-alpha",
    )
    monkeypatch.setattr(worker, "get_event", lambda event_id, team_id: event)
    _avoid_persistence(monkeypatch)
    seen_references = []

    def enrich(task, team_id, reference_datetime):
        seen_references.append(reference_datetime)
        return task

    worker.process_connector_job(
        {"event_id": event.id, "team_id": event.team_id},
        extractor=lambda chunks: [_extracted(chunks[0].source_ref)],
        enricher=enrich,
    )

    assert seen_references == [event_timestamp]


def test_upload_worker_explicitly_uses_no_source_timestamp_fallback(monkeypatch):
    _avoid_persistence(monkeypatch)
    seen_references = []

    def enrich(task, team_id, reference_datetime):
        seen_references.append(reference_datetime)
        return task

    worker.process_job(
        {
            "file_path": "/objects/chat.txt",
            "file_type": ".txt",
            "filename": "chat.txt",
            "team_id": "team-alpha",
        },
        normalizer=lambda path, file_type: [
            Chunk(text="Finish the video", source_ref="stored.txt:1")
        ],
        extractor=lambda chunks: [_extracted(chunks[0].source_ref)],
        enricher=enrich,
    )

    assert seen_references == [None]
