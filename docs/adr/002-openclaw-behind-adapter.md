# ADR 002: OpenClaw behind ConnectorAdapter

Status: accepted, implementation deferred

Any future OpenClaw integration must live below
`backend/infrastructure/connectors/connector_adapter.py`. Core engines and API
routes must depend on the adapter contract and must never import an OpenClaw
client or SDK directly.

Phase 1 adds no connector or OpenClaw behavior.
