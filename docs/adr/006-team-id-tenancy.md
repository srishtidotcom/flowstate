# ADR 006: `team_id` is the current tenancy key

Status: accepted for the MVP

The existing MVP consistently supplies `team_id` at upload and carries it on
jobs, events, commitments, tasks, and graph edges. Phase 1 therefore treats
`team_id` as the mandatory isolation key rather than inventing a second user or
workspace tenancy model.

All reads, mutations, job results, review decisions, and derived indexes must
be scoped by `team_id`. Authentication and a future tenancy redesign are out
of scope and require a separate ADR.
