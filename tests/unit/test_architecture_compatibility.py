from backend.core.graph import build_dag as canonical_build_dag
from backend.graph.dag import build_dag as legacy_build_dag
from backend.governance import router
from backend.models.domain import Task


def test_legacy_graph_import_is_an_explicit_alias():
    assert legacy_build_dag is canonical_build_dag


def test_governance_uses_the_canonical_task_type():
    assert router.Task is Task
