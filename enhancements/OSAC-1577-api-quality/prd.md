# API Quality — Declarative Validation, Auto-Generated Public API, and Consistency

| Field       | Value   |
|-------------|---------|
| Author(s)   | Haim Tayrie |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1577 |
| Date        | 2026-07-19 |

## Problem Statement

API validation in the OSAC fulfillment service is hand-written in Go and drifts from proto documentation, producing inconsistent error messages and allowing invalid input through gaps in coverage. The public and private APIs are maintained as separate proto files that must be kept in sync manually — a process that is error-prone and creates unnecessary maintenance burden. Cross-object constraints that depend on soft-deletion state (e.g., preventing a compute instance from attaching to a soft-deleted subnet) cannot be enforced by standard PostgreSQL foreign keys and require ad-hoc implementations that vary by resource type. These inconsistencies compound across the growing number of resource types and slow down both API development and API consumption.

## Prior Work

- Declarative input validation via protovalidate (OSAC-1275) — complete. Replaced hand-written Go validation with schema-derived validation. `[Clarify: R1.Q3]`

## In Scope

- Automated generation of the public API from annotated private API definitions via a protoc plugin, eliminating manual dual-maintenance of proto files (OSAC-1274)
- A standard pattern for enforcing cross-object constraints that respect soft deletion — preventing relationships to soft-deleted objects, replacing per-resource ad-hoc logic (OSAC-1331)
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
- As an API developer, I want cross-object constraints to automatically prevent relationships to soft-deleted objects so that I do not write ad-hoc deletion-aware enforcement logic per resource type.
- As an API developer, I want consistent DAO and query semantics across all resource types so that each resource behaves predictably and I do not encounter inconsistencies when adding or modifying resources.

### API Consumer

- As an API consumer, I want validation errors derived from the proto schema so that error messages are consistent across resource types and accurately reflect the accepted input format.
- As an API consumer, I want the API to reject attempts to reference soft-deleted objects (e.g., attaching to a deleted subnet or allocating from a deleted IP pool) so that I receive a clear error instead of creating an invalid relationship.
- As an API consumer, I want the public API to be a faithful projection of the private API so that documented behavior matches actual behavior without drift.

## Assumptions

- OSAC does not currently support upgrades, so data migration and backward compatibility for existing persisted data are not concerns for this milestone.
- The protovalidate adoption (OSAC-1275) has been completed without causing breaking changes to existing API consumers. `[Clarify: R1.Q3]`
- Each epic (OSAC-1274, OSAC-1331, OSAC-1540) is responsible for its own testing, documentation, and installation impact — no separate cross-cutting workstreams are needed. `[Clarify: R1.Q5]`

## Dependencies

- **protoc-gen-cleanapi:** The public API auto-generation (OSAC-1274) depends on the protoc-gen-cleanapi plugin, which has a proof-of-concept at https://github.com/jhernand/protoc-gen-cleanapi. The plugin must be production-ready before OSAC-1274 can be completed.

---

## Provenance

Authored: respond @ prd 0.5.0 - 92734a2, workspace main @ 5450556
Phases: draft, revise, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"5450556","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond"],"authoring_modes":["skill"],"context_changed":false} -->
