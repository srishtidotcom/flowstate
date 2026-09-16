import asyncio

import httpx

import backend.api.jobs as jobs_api
from backend.api.main import app
from backend.ingestion.service import JobNotCompletedError, JobResults
from backend.models import Commitment, Event, GraphEdge, Job, Task


def request(method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def _job():
    return Job(
        id="job-1",
        team_id="team-alpha",
        type="process_upload",
        status="completed",
        filename="chat.txt",
        file_path="/private/chat.txt",
        result_event_id="event-1",
        result_commitment_id="commitment-1",
    )


def test_job_status_is_team_scoped_and_hides_file_path(monkeypatch):
    observed = []

    def get_job(job_id, team_id):
        observed.append((job_id, team_id))
        return _job() if team_id == "team-alpha" else None

    monkeypatch.setattr(jobs_api, "get_job", get_job)
    response = request("GET", "/jobs/job-1", params={"team_id": "team-alpha"})
    denied = request("GET", "/jobs/job-1", params={"team_id": "team-beta"})

    assert response.status_code == 200
    assert "file_path" not in response.json()
    assert denied.status_code == 404
    assert observed == [("job-1", "team-alpha"), ("job-1", "team-beta")]


def test_job_results_return_domain_records_and_noncompleted_conflict(monkeypatch):
    task = Task(
        id="task-1",
        team_id="team-alpha",
        commitment_id="commitment-1",
        description="Ship demo",
        confidence=0.9,
        source_ref="chat.txt:1",
        status="approved",
    )
    results = JobResults(
        job=_job(),
        event=Event(
            id="event-1",
            team_id="team-alpha",
            type="file_upload",
            source="upload",
            content="Ship demo",
        ),
        commitment=Commitment(
            id="commitment-1",
            team_id="team-alpha",
            title="Ship",
        ),
        tasks=[task],
        edges=[
            GraphEdge(
                id="edge-1",
                team_id="team-alpha",
                source_id="task-1",
                target_id="commitment-1",
                relationship_type="belongs_to",
            )
        ],
    )
    monkeypatch.setattr(jobs_api, "get_job_results", lambda job_id, team_id: results)

    response = request(
        "GET",
        "/jobs/job-1/results",
        params={"team_id": "team-alpha"},
    )

    assert response.status_code == 200
    assert response.json()["tasks"][0]["description"] == "Ship demo"
    assert response.json()["edges"][0]["relationship_type"] == "belongs_to"

    def incomplete(job_id, team_id):
        raise JobNotCompletedError("not completed")

    monkeypatch.setattr(jobs_api, "get_job_results", incomplete)
    conflict = request(
        "GET",
        "/jobs/job-1/results",
        params={"team_id": "team-alpha"},
    )
    assert conflict.status_code == 409


def test_job_endpoints_require_team_id():
    assert request("GET", "/jobs/job-1").status_code == 422
    assert request("GET", "/jobs/job-1/results").status_code == 422
