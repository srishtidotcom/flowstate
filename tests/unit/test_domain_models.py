from backend.models import Commitment, Event, Task


def test_task_has_canonical_fields_and_legacy_read_aliases():
    task = Task(
        description="Prepare the demo",
        confidence=0.9,
        source_ref="chat.txt:4",
        team_id="team-alpha",
    )

    assert task.task == "Prepare the demo"
    assert task.task_id == task.id
    assert task.status == "pending"
    assert task.to_dict()["description"] == "Prepare the demo"


def test_commitment_and_event_use_isolated_collection_defaults():
    first_event = Event(type="file_upload", source="upload", content="a", team_id="team-alpha")
    second_event = Event(type="file_upload", source="upload", content="b", team_id="team-alpha")
    commitment = Commitment(title="Ship demo", team_id="team-alpha")

    first_event.participants.append("Siya")
    commitment.task_ids.append("task-1")

    assert second_event.participants == []
    assert commitment.event_ids == []
