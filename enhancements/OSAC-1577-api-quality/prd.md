# API Quality — Declarative Validation, Auto-Generated Public API, and Consistency

| Field       | Value   |
|-------------|---------|
| Author(s)   | Haim Tayrie |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1577 |
| Date        | 2026-07-19 |

## Problem Statement

API validation in the OSAC fulfillment service is hand-written in Go and drifts from proto documentation, producing inconsistent error messages and allowing invalid input through gaps in coverage. The public and private APIs are maintained as separate proto files that must be kept in sync manually — a process that is error-prone and creates unnecessary maintenance burden. Cross-object constraints (uniqueness across active resources, referential integrity within JSONB columns) are enforced through ad-hoc implementations that vary by resource type. These inconsistencies compound across the growing number of resource types and slow down both API development and API consumption.

## In Scope

- Declarative input validation via protovalidate annotations in proto files, replacing hand-written Go validation (OSAC-1275 — complete) `[Clarify: R1.Q3]`
- Automated generation of the public API from annotated private API definitions via a protoc plugin, eliminating manual dual-maintenance of proto files (OSAC-1274)
- A standard pattern for enforcing cross-object constraints (uniqueness, referential integrity) that respects soft deletion, replacing per-resource ad-hoc logic (OSAC-1331)
- Incremental DAO/query semantics cleanup and consistency fixes across resource types (OSAC-1540)

## Out of Scope

- New resource types or domain-specific API changes
- Breaking API changes
- Adoption of Google API Improvement Proposals (AIPs) as a formal standard `[Clarify: R1.Q1]`
- UI changes, except where API changes would break existing UI behavior `[Clarify: R1.Q4]`

## User Stories

### API Developer

- As an API developer, I want validation rules declared in proto files so that validation logic stays in sync with the schema and I do not maintain separate Go validation code.
- As an API developer, I want the public API generated automatically from the private API so that I maintain one set of proto definitions instead of two.
- As an API developer, I want a standard mechanism for enforcing cross-object constraints (e.g., unique names across active resources, foreign key integrity within JSONB) so that I use a consistent pattern instead of writing ad-hoc enforcement logic per resource type.
- As an API developer, I want consistent DAO and query semantics across all resource types so that each resource behaves predictably and I do not encounter inconsistencies when adding or modifying resources.

### API Consumer

- As an API consumer, I want validation errors derived from the proto schema so that error messages are consistent across resource types and accurately reflect the accepted input format.
- As an API consumer, I want cross-object constraints enforced consistently so that I receive clear errors when I violate uniqueness or referential integrity rules, regardless of which resource type I am working with.
- As an API consumer, I want the public API to be a faithful projection of the private API so that documented behavior matches actual behavior without drift.

## Assumptions

- OSAC does not currently support upgrades, so data migration and backward compatibility for existing persisted data are not concerns for this milestone.
- The protovalidate adoption (OSAC-1275) has been completed without causing breaking changes to existing API consumers. `[Clarify: R1.Q3]`
- Each epic (OSAC-1274, OSAC-1331, OSAC-1540) is responsible for its own testing, documentation, and installation impact — no separate cross-cutting workstreams are needed. `[Clarify: R1.Q5]`

## Dependencies

- **protoc-gen-cleanapi:** The public API auto-generation (OSAC-1274) depends on the protoc-gen-cleanapi plugin, which has a proof-of-concept at https://github.com/jhernand/protoc-gen-cleanapi. The plugin must be production-ready before OSAC-1274 can be completed.

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ 5450556

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"5450556","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
