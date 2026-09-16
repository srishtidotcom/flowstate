from dataclasses import dataclass

from backend.governance.policy import execution_candidates, requires_review


@dataclass
class StubTask:
    name: str
    deadline: str | None = None
    confidence: float = 0.9
    owner: str | None = None
    inferred_owner: str | None = None
    inference_confidence: float | None = None
    duplicate_candidates: list[str] | None = None


def test_execution_candidates_only_returns_approved_tasks_with_deadlines():
    approved = StubTask("approved", "2026-09-01T10:00:00Z")
    approved_without_deadline = StubTask("approved without deadline")
    under_review = StubTask("under review", "2026-09-01T11:00:00Z")

    result = execution_candidates(
        {
            "approved": [approved, approved_without_deadline],
            "review": [under_review],
        }
    )

    assert result == [approved]


def test_execution_candidates_fails_closed_without_approved_key():
    under_review = StubTask("under review", "2026-09-01T11:00:00Z")

    assert execution_candidates({"review": [under_review]}) == []


def test_explicit_owner_does_not_require_inference_confidence():
    task = StubTask("assigned", owner="Siya")

    assert requires_review(task, 0.75, 0.70) is False


def test_uncertain_inferred_owner_requires_review():
    task = StubTask(
        "inferred",
        inferred_owner="Siya",
        inference_confidence=0.69,
    )

    assert requires_review(task, 0.75, 0.70) is True
