from dataclasses import dataclass

import pytest

import backend.worker as worker


@dataclass
class StubEntity:
    id: str


@dataclass
class StubResult:
    event: StubEntity
    commitment: StubEntity


def _job(job_type="process_upload"):
    return {"job_id": "job-1", "team_id": "team-alpha", "type": job_type}


def test_unknown_job_type_is_recorded_as_failed(monkeypatch):
    statuses = []
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: True)
    monkeypatch.setattr(
        worker,
        "set_job_status",
        lambda job_id, team_id, status, error=None: statuses.append((status, error)),
    )

    with pytest.raises(ValueError, match="Unsupported job type"):
        worker.process_queued_job(_job("mystery"))

    assert statuses == [("failed", "Unsupported job type: 'mystery'")]


def test_processing_failure_is_recoverable_and_inspectable(monkeypatch):
    statuses = []
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: True)
    monkeypatch.setattr(
        worker,
        "set_job_status",
        lambda job_id, team_id, status, error=None: statuses.append((status, error)),
    )

    def fail(_job):
        raise RuntimeError("extractor unavailable")

    with pytest.raises(RuntimeError, match="extractor unavailable"):
        worker.process_queued_job(_job(), processor=fail)

    assert statuses == [("failed", "extractor unavailable")]


def test_success_completes_with_result_references(monkeypatch):
    completed = []
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: True)
    monkeypatch.setattr(
        worker,
        "mark_job_completed",
        lambda job_id, team_id, event_id, commitment_id: completed.append(
            (job_id, team_id, event_id, commitment_id)
        )
        or True,
    )
    result = StubResult(StubEntity("event-1"), StubEntity("commitment-1"))

    assert worker.process_queued_job(_job(), processor=lambda job: result) is result
    assert completed == [("job-1", "team-alpha", "event-1", "commitment-1")]


def test_second_claim_is_rejected(monkeypatch):
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: False)

    with pytest.raises(ValueError, match="already been claimed"):
        worker.process_queued_job(_job())


def test_completion_failure_is_recorded(monkeypatch):
    statuses = []
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: True)
    monkeypatch.setattr(worker, "mark_job_completed", lambda *args: False)
    monkeypatch.setattr(
        worker,
        "set_job_status",
        lambda job_id, team_id, status, error=None: statuses.append((status, error)),
    )
    result = StubResult(StubEntity("event-1"), StubEntity("commitment-1"))

    with pytest.raises(RuntimeError, match="Could not complete"):
        worker.process_queued_job(_job(), processor=lambda job: result)

    assert statuses == [("failed", "Could not complete job job-1")]


def test_sync_connector_job_dispatches_to_connector_processor(monkeypatch):
    completed = []
    result = StubResult(StubEntity("event-1"), StubEntity("commitment-1"))
    monkeypatch.setattr(worker, "claim_job", lambda job_id, team_id: True)
    monkeypatch.setattr(worker, "process_connector_job", lambda job: result)
    monkeypatch.setattr(
        worker,
        "mark_job_completed",
        lambda *args: completed.append(args) or True,
    )

    connector_job = _job("sync_connector") | {"event_id": "event-1"}
    assert worker.process_queued_job(connector_job) is result
    assert completed == [("job-1", "team-alpha", "event-1", "commitment-1")]
