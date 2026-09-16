# ADR 001: PostgreSQL plus NetworkX

Status: accepted

Flowstate stores durable graph edges in PostgreSQL and reconstructs a directed
NetworkX graph for traversal, cycle detection, critical paths, and bottlenecks.
It does not persist a NetworkX object or introduce a native graph database.

This keeps transactional activity data and its graph provenance in one durable
store while retaining deterministic graph algorithms. Every edge is scoped by
`team_id`, and cycles are rejected before persistence.
