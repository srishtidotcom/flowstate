# ADR 007: OpenClaw inbound bridge and trust boundary

Status: accepted for Phase 2A

Flowstate accepts inbound WhatsApp text notifications from one trusted local
OpenClaw plugin over a loopback-only HTTP route. The plugin uses the typed
`api.on("message_received", ...)` API and signs the timestamp plus exact request
body with HMAC-SHA256. Flowstate rejects missing or invalid authentication,
stale requests, non-loopback clients, unsupported channels, outbound messages,
and incomplete identities before persistence.

OpenClaw payload validation and normalization live only in
`backend/infrastructure/connectors/openclaw/`. The adapter produces the
canonical `backend.models.domain.Event`, retaining the complete received
payload in `Event.raw`. Core activity, extraction, enrichment, and graph code
remain unaware of OpenClaw.

Acceptance is database-primary: the canonical Event and its single durable
`sync_connector` Job commit before Redis publication. Deterministic UUIDv5 IDs
and database uniqueness make redelivery idempotent. Redis and the worker provide
at-least-once delivery; database-backed claiming and stable derived IDs prevent
duplicate business activity. This does not claim distributed exactly-once
delivery.
