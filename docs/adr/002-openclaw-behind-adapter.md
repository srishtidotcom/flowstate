# ADR 002: OpenClaw behind ConnectorAdapter

Status: accepted, implemented for Phase 2A inbound WhatsApp text

Any future OpenClaw integration must live below
`backend/infrastructure/connectors/connector_adapter.py`. Core engines and API
routes must depend on the adapter contract and must never import an OpenClaw
client or SDK directly.

Phase 1 added no connector behavior. Phase 2A implements a loopback inbound
bridge; see ADR 007. Outbound actions and additional channels remain deferred.
