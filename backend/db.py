from typing import Optional, List, Dict
from backend.models import Task

# Mock database for demonstration
HISTORICAL_OWNERSHIP = {
    "team_alpha": {
        "Complete pitch deck": "Rahul",
        "Review project plan": "Priya",
    }
}

SPEAKER_ACTIVITY = {
    "team_alpha": {
        "sample_screenshot.png": [
            {"speaker": "Rahul", "frequency": 5},
            {"speaker": "Priya", "frequency": 3},
        ]
    }
}

TASKS_DB = {
    "task_123": Task(
        task_id="task_123",
        task="Complete pitch deck",
        owner="Rahul",
        deadline="2026-03-26T23:59:00+05:30",
        confidence=0.95,
        source_ref="sample_screenshot.png",
        team_id="team_alpha",
    ),
    "task_456": Task(
        task_id="task_456",
        task="Review project plan",
        owner="Priya",
        deadline="2026-03-27T18:00:00+05:30",
        confidence=0.90,
        source_ref="sample_chat.txt",
        team_id="team_alpha",
    ),
}

def get_historical_ownership(team_id: str, task_description: str) -> Optional[str]:
    """Retrieve historical owner for a task description."""
    return HISTORICAL_OWNERSHIP.get(team_id, {}).get(task_description)

def get_speaker_activity(team_id: str, source_ref: str) -> Optional[List[Dict[str, str]]]:
    """Retrieve speaker activity frequency for a source reference."""
    return SPEAKER_ACTIVITY.get(team_id, {}).get(source_ref)

def get_task_by_id(task_id: str) -> Optional[Task]:
    """Retrieve a task by its ID."""
    return TASKS_DB.get(task_id)