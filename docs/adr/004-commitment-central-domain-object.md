# ADR 004: Commitment is the central domain object

Status: accepted

Events and tasks created from one source roll up into a durable Commitment.
Tasks link to the Commitment relationally and graph edges retain provenance to
both the source Event and Commitment.

Canonical domain types live only in `backend/models/domain.py`. Persistence
records and API request/response schemas are translations of those types, not
parallel business models.
