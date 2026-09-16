from sqlalchemy.orm import Session

from backend.core.activity.engine import persist_extracted_activity
from backend.db.repositories import add_task
from backend.ingestion.service import (
    claim_job,
    enqueue_upload_job,
    mark_job_completed,
)
from backend.models import Job, Task
from backend.preprocessing.normalizer import Chunk


def test_jobs_results_and_reviews_are_isolated_by_team(
    isolated_db,
    controlled_queue,
    api_request,
):
    job = Job(
        id="private-job",
        type="process_upload",
        team_id="team-alpha",
        filename="private.txt",
        file_path="/objects/private.txt",
        file_type=".txt",
    )
    enqueue_upload_job(job, controlled_queue)
    controlled_queue.pop_job()
    assert claim_job(job.id, job.team_id) is True
    activity = persist_extracted_activity(
        {
            "job_id": job.id,
            "team_id": job.team_id,
            "filename": job.filename,
            "file_path": job.file_path,
            "file_type": job.file_type,
        },
        [Chunk(text="Private task", source_ref="private.txt:1")],
        [
            Task(
                id="private-result-task",
                team_id="team-alpha",
                description="Private result task",
                confidence=0.9,
                source_ref="private.txt:1",
                status="approved",
            )
        ],
    )
    assert mark_job_completed(
        job.id,
        job.team_id,
        activity.event.id,
        activity.commitment.id,
    )

    with Session(isolated_db) as db:
        add_task(
            db,
            Task(
                id="alpha-review",
                team_id="team-alpha",
                description="Alpha review",
                confidence=0.5,
                source_ref="alpha.txt:1",
                status="pending_review",
            ),
        )
        add_task(
            db,
            Task(
                id="beta-review",
                team_id="team-beta",
                description="Beta review",
                confidence=0.5,
                source_ref="beta.txt:1",
                status="pending_review",
            ),
        )
        db.commit()

    assert api_request(
        "GET",
        f"/jobs/{job.id}",
        params={"team_id": "team-beta"},
    ).status_code == 404
    assert api_request(
        "GET",
        f"/jobs/{job.id}/results",
        params={"team_id": "team-beta"},
    ).status_code == 404

    alpha_queue = api_request(
        "GET", "/review/tasks", params={"team_id": "team-alpha"}
    ).json()
    beta_queue = api_request(
        "GET", "/review/tasks", params={"team_id": "team-beta"}
    ).json()
    assert {task["id"] for task in alpha_queue} == {"alpha-review"}
    assert {task["id"] for task in beta_queue} == {"beta-review"}

    cross_team_mutation = api_request(
        "POST",
        "/review/tasks/beta-review/decision",
        params={"team_id": "team-alpha"},
        json={"reviewer_id": "reviewer-1", "decision": "approved"},
    )
    assert cross_team_mutation.status_code == 404
