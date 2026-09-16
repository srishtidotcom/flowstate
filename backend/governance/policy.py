"""Pure governance policies shared by routing and execution."""

from typing import Dict, List, TypeVar


TaskT = TypeVar("TaskT")


def requires_review(
    task: TaskT,
    extraction_threshold: float,
    ownership_threshold: float,
) -> bool:
    """Apply confidence rules without penalizing an explicitly named owner."""

    if task.confidence < extraction_threshold or task.duplicate_candidates:
        return True
    if task.owner:
        return False
    return not task.inferred_owner or (task.inference_confidence or 0) < ownership_threshold


def execution_candidates(routing: Dict[str, List[TaskT]]) -> List[TaskT]:
    """Return approved tasks that have a deadline and may be executed.

    The review queue is intentionally ignored. A task must be present in the
    approved routing result before an execution adapter can see it.
    """

    return [task for task in routing.get("approved", []) if task.deadline]
