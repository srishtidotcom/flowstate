# ADR 005: Restrict LLM usage

Status: accepted

LLM calls are allowed only in the extraction module, the Planning Engine, and
the Communicator Agent. Phase 1 uses only
`backend/extraction/extractor.py`; normalization, enrichment, graph behavior,
persistence, governance, and execution eligibility remain deterministic.

Structured extraction output must be JSON-schema validated before conversion
to canonical domain objects.
