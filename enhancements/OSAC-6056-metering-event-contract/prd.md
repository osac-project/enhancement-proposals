# The metering event contract

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | ovishlit@redhat.com  |
| Jira        | [OSAC-6056](https://redhat.atlassian.net/browse/OSAC-6056) |
| Date        | 2026-10-28           |

## Glossary

| Term | Definition |
|------|-----------|
| **Usage event** | One measured quantity over one interval, for one resource and meter. |
| **Correction** | A usage event with a negative quantity; it takes back usage already sent. |
| **Meter** | What is measured on a resource, such as a running VM's seconds. |
| **Schema** | The published description of a usage event's fields. |
| **Reader** | The customer's system that reads usage events. |
| **External billing account id** | The tenant's id in the provider's billing system. |

## Problem

OSAC measures usage and publishes usage events. OSAC's own adapters read them. The adapters send usage to the
billing provider. Today, the rules for these events live only in OSAC's code.

A provider whose billing system has no OSAC adapter has no way to read usage. There are many billing systems,
and some are private to the customer. OSAC cannot ship an adapter for each one.

Two more problems stand in the way. The fields of an event can change in any release. An outside system that
reads events can break without warning. And the only credentials that can read events belong to OSAC itself.
The platform cannot hand them to anyone else.

This contract gives a customer's system a safe way to read usage itself. OSAC-6060 builds on it.

## In Scope

- A published contract for usage events: what they contain, how to derive a billable quantity, and how they
  arrive.
- A reference covering every resource type that emits usage events when the contract is published.
- Schema rules: a published schema never changes. A new field is a new schema. A new resource type changes
  no schema, because the type name is a field value.
- A replay rule: a rebuild reads each record with the schema that was in effect when the record was written.
- Access for readers: grant, revoke, and credentials of their own.
- A worked example: a small reader run against a dev deployment.
- Per-tenant grants. No grant covers all tenants.

## Out of Scope

- The raw event log. It stays internal; the contract covers usage events only.
- MaaS inference metering. It joins when its metering lands.
- Adapter SDKs and plugin contracts for customer-built adapters (OSAC-6060).
- Provider adapters. M360 is OSAC-3784; Red Hat Cost Management is OSAC-4284.
- Pricing and invoicing. The reader prices; OSAC measures.
- More metering coverage. BMaaS, Storage, Networking, and MaaS billing have their own tickets.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want a reference for every field in a usage event, so that I can map usage onto
  my billing without reading OSAC's code.
- As a Cloud Provider Admin, I want the delivery rules stated: order, guarantee, and event id, so that my
  billing charges each usage exactly once.
- As a Cloud Provider Admin, I want schemas that never change once published, so that an upgrade never
  breaks my reader.
- As a Cloud Provider Admin, I want my reader granted access with credentials of its own, so that it reads usage safely.
- As a Cloud Provider Admin, I want a worked example that reads usage events and derives a billable quantity,
  so that my team starts from a running reader.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to grant and revoke a reader with a settings change, so that
  onboarding forces no restart of OSAC services.
- As a Cloud Infrastructure Admin, I want to see how far behind each reader is and who each reader is, so
  that a stuck reader is noticed before it matters.

Tenant Admin and Tenant User are unaffected. Tenant cost views stay with OSAC-3784.

## Acceptance Criteria

- [ ] The reference documents every resource type that emits usage events when the contract is published. It
  says what each field means, its unit, and which fields are required.
- [ ] The reference states the reading rule: a reader sums every usage event, and a correction is a negative one.
- [ ] The reference states the lifecycle: start, change, stop, corrections, and how to rebuild a billable quantity.
- [ ] The transport section states topic naming, ordering, the delivery guarantee, and the event id used to
  drop repeated deliveries. It also states how long records stay readable.
- [ ] Every usage event names its schema version.
- [ ] A published schema never changes. A new field is a new schema, with a new version and the date it takes effect.
- [ ] A change to a published schema file fails the build.
- [ ] A rebuild from the stored usage events, using the schema in effect when each record was written,
  gives the same usage for every record still retained.
- [ ] A usage event carries the external billing account id if the tenant has one. It omits the id when there
  is none. Each event belongs to the account its id names, so a reader keeps each account's usage separate.
- [ ] The Cloud Infrastructure Admin grants a reader access to the usage events of the tenant the grant
  names, with its own credentials.
- [ ] Revoking a reader stops its access, with no restart of OSAC services.
- [ ] Every grant and revocation is recorded: who made it, when, and which reader.
- [ ] A reader cannot write anything and cannot disturb OSAC's own billing pipeline.
- [ ] The provider can see how far behind each reader is, and who each reader is.
- [ ] The contract states that a reader owns its own retries and its own failed records.
- [ ] The contract states that the raw event log stays internal.
- [ ] The worked example runs on a dev deployment, reads usage events, derives a billable quantity, and
  carries no credentials.
- [ ] A schema change that leaves the published reference stale fails a check.

## Assumptions

- The contract covers the usage events metering publishes today. The reference is refreshed as coverage grows.
- A reader can reach the platform's message transport from its own systems.
- Each reader keeps its own place in the stream, so a slow reader delays only itself.

## Dependencies

- Event-log metering (OSAC-5753) provides the usage event pipeline the contract describes.
- The external billing id (OSAC-6161) provides the account id on each usage event.
- Customer-built adapters (OSAC-6060) build on this contract.

## Risks

- **A growing schema** (owner: contract design). Each new coverage tempts a shortcut: a changed field folded
  into a published schema. One such change breaks every reader at once. The build fails on any change to a
  published schema file, so every change arrives as a new schema.
- **Leaked credentials** (owner: platform team). A reader's grant names one tenant, so a leaked credential
  exposes that tenant's usage. Each reader gets its own credentials that can only read, and revoking them
  needs no restart.
- **A stuck reader** (owner: metering design). A reader that stops reading falls behind, and the person who
  granted it may notice late. The provider can see how far behind each reader is, and a reader's failures
  affect only itself.

---

## Provenance

Committed: commit @ prd 0.11.3 - 9b25062, workspace main @ e526ec64b

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"e526ec64b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
