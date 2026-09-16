"""Deterministic task-graph construction and validation."""

from typing import Dict, Iterable, List

import networkx as nx

from backend.models import GraphEdge, Task


class GraphCycleError(ValueError):
    pass


def build_dag(tasks: List[Task]) -> nx.DiGraph:
    """Build an in-memory task dependency graph."""
    graph = nx.DiGraph()

    for task in tasks:
        graph.add_node(
            task.id,
            type="task",
            label=task.description,
            deadline=task.deadline,
            owner=task.owner or task.inferred_owner,
            confidence=task.confidence,
            status=task.status,
        )

    task_ids_by_title = {task.description.casefold(): task.id for task in tasks}
    for task in tasks:
        for dependency in task.dependencies:
            dependency_id = task_ids_by_title.get(dependency.casefold())
            if dependency_id:
                graph.add_edge(dependency_id, task.id, relationship="depends_on")

    if not nx.is_directed_acyclic_graph(graph):
        raise GraphCycleError("Extracted task dependencies contain a cycle")
    return graph


def validate_dependency_edges(edges: Iterable[GraphEdge]) -> None:
    """Reject dependency edges that would create a directed cycle."""
    graph = nx.DiGraph()
    for edge in edges:
        if edge.relationship_type in {"depends_on", "blocks"}:
            graph.add_edge(edge.source_id, edge.target_id)
    if not nx.is_directed_acyclic_graph(graph):
        raise GraphCycleError("Persisting these dependency edges would create a cycle")


def get_critical_path(graph: nx.DiGraph) -> List[str]:
    return nx.dag_longest_path(graph)


def get_bottlenecks(graph: nx.DiGraph) -> List[str]:
    return [node for node in graph.nodes if graph.in_degree(node) > 2]


def get_dag_summary(tasks: List[Task]) -> Dict:
    graph = build_dag(tasks)
    return {
        "total_tasks": graph.number_of_nodes(),
        "total_dependencies": graph.number_of_edges(),
        "critical_path": get_critical_path(graph),
        "bottlenecks": get_bottlenecks(graph),
    }
