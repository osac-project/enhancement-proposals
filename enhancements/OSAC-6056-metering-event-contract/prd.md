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
| **Component** | The billable line a meter feeds. It is the meter's name unless a rule sets another. |
| **Schema** | The published description of a usage event's fields. |
| **Reader** | A system that reads the heartbeat topics of one or more tenants. |
| **External billing account id** | The tenant's id in the provider's billing system. |

## Problem

OSAC measures usage and publishes usage events. Its own adapters read them and send usage to the billing
provider. The event fields and their meaning live only in OSAC's code.

A provider whose billing system has no OSAC adapter has no way to read usage. There are many billing systems,
and some are private to the customer. OSAC cannot ship an adapter for each one.

Two more problems follow. Event fields can change in any release, so an outside reader can break without
warning. Only OSAC's credentials can read the heartbeat topics, so the platform cannot hand them out.

A reader per tenant would turn every new tenant into an operator task. The reader must exist once, before
the first tenant, and read every tenant's heartbeat topics after it. Creating a tenant then touches only the
OSAC API, CLI, or UI, with no chart update and no step in the platform repository.

This contract gives a customer's system a safe way to read usage itself. OSAC-6060 builds on it.

## In Scope

- A published contract for usage events: the fields and how to consume them.
- The consumption rules: sum every event, treat a correction as negative, drop repeats by the deduplication
  key, and read in arrival order. The reference also states how long records stay readable.
- The billing dimensions each event carries, so a reader can price usage.
- A reference covering every resource type that emits usage events when the contract is published, with its
  meters, units, and billable states.
- Schema rules: a published schema never changes. A new field is a new schema. A new resource type changes
  no schema, because the type name is a field value.
- A replay rule: a rebuild reads each record with the schema that was in effect when the record was written.
- Access for a reader over all tenants' heartbeat topics: one grant, one credential, and one consumer group.
- A worked example: a small reader run against a dev deployment.

## What OSAC meters

OSAC meters six resource types in seven meters. The default rules are metering's revision 0001, a set of
rules the chart ships. A change ships as a new revision. A shipped revision is never edited.

| Resource | Meter | Unit | Bills while | Dimensions |
|---|---|---|---|---|
| Compute instance | `compute` | `second` | RUNNING | instance type, image, boot disk size |
| Cluster | `control_plane` | `second` | PROGRESSING, READY | template, version |
| Bare metal instance | `allocation` | `second` | STARTING, RUNNING, STOPPING, STOPPED, DELETING | instance type, cluster, node set |
| Bare metal instance | `consumption` | `second` | RUNNING | instance type, cluster, node set |
| Volume | `capacity` | `gibibyte_second` | AVAILABLE, DELETING | storage tier |
| External IP | `allocation` | `second` | ALLOCATED, DELETING | pool, IP family, attached |
| NAT gateway | `allocation` | `second` | READY, DELETING | virtual network, external IP |

Volume capacity multiplies by the volume's provisioned size. A failed resource never bills. Every event also
names the deployment, tenant, project, catalog item, template, and meter type.
[OSAC-5753](/enhancements/OSAC-5753-event-log-driven-metering/prd.md) holds the full rules.

## Out of Scope

- The raw event log. It stays internal. The contract covers usage events only.
- MaaS inference metering. It joins when its metering lands.
- Adapter SDKs and plugin contracts for customer-built adapters (OSAC-6060).
- Provider adapters. M360 is OSAC-3784; Red Hat Cost Management is OSAC-4284.
- Pricing, rating, and invoicing. The reader prices; OSAC measures. Billing integration is OSAC-3784, rate
  authoring is OSAC-3792, and catalog price display is OSAC-3793.
- New meters: network bandwidth (OSAC-3149), file storage (OSAC-4940), and object storage (OSAC-3444).
  VirtualNetwork and Subnet are configuration resources and carry no meter.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want a reference for every field in a usage event, so that I can map usage onto
  my billing without reading OSAC's code.
- As a Cloud Provider Admin, I want each event to name the billing dimensions and the billing account, so that
  my system prices and attributes usage.
- As a Cloud Provider Admin, I want the delivery rules stated: order, guarantee, and the deduplication key, so
  that my billing charges each usage exactly once.
- As a Cloud Provider Admin, I want schemas that never change once published, so that an upgrade never
  breaks my reader.
- As a Cloud Provider Admin, I want my reader to have credentials of its own, so that it reads heartbeat
  topics safely.
- As a Cloud Provider Admin, I want one reader for every tenant, so that I add or rotate one credential instead of
  one per tenant.
- As a Cloud Provider Admin, I want a worked example that reads usage events and derives a billable quantity,
  so that my team starts from a running reader.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to grant and revoke a reader with a settings change, so that
  onboarding forces no restart of OSAC services.
- As a Cloud Infrastructure Admin, I want to grant and revoke one reader that covers every tenant, so that I
  manage one entry and one credential instead of one per tenant.
- As a Cloud Infrastructure Admin, I want to see how far behind each reader is and who each reader is, so
  that a stuck reader is noticed before it matters.

Tenant Admin and Tenant User are unaffected. Tenant cost views stay with OSAC-3784.

## Acceptance Criteria

- [ ] The reference documents every resource type that emits usage events when the contract is published, with
  its meters, units, and billable states. It describes each field, its unit, and whether the field is required.
- [ ] The reference states the reading rule: a reader sums every usage event for a resource, meter,
  component, and set of billing dimensions, and a correction is a negative one.
- [ ] The reference states the lifecycle: start, change, stop, corrections, and how to rebuild a billable quantity.
- [ ] The transport section states topic naming, ordering, the delivery guarantee, and how long records stay
  readable. It names the deduplication key: the CloudEvent id, a hash of tenant, resource type, resource id,
  meter, component, dimensions, interval, and sending minute. A reader drops repeats by id and never
  recomputes it.
- [ ] Every usage event names its schema version.
- [ ] A published schema never changes. A new field is a new schema, with a new version and the date it takes effect.
- [ ] The reference states that a published schema stays readable for as long as its records are retained,
  and that retention is indefinite by default.
- [ ] A change to a published schema file fails the build.
- [ ] A rebuild from the stored usage events, using the schema in effect when each record was written,
  gives the same usage for every record still retained.
- [ ] A usage event carries the external billing account id when the tenant has one, and omits it when the
  tenant has none. The id labels where each event is reported. A reader correlates usage and corrections
  by tenant, resource, meter, component, and billing dimensions.
- [ ] Every usage event names the billing dimensions its meter bills on, plus the deployment, tenant, project,
  catalog item, template, and meter type.
- [ ] The Cloud Infrastructure Admin grants a reader access to every tenant's heartbeat topics,
  `osac.metering.heartbeat.<tenant>`, with one credential, and to a consumer group named after the reader.
  The grant covers the heartbeat topic prefix `osac.metering.heartbeat.` and that one group: not the raw
  event log and not the dead-letter topics.
- [ ] Revoking a reader stops its access to every tenant's heartbeat topics at once, with no restart of OSAC
  services.
- [ ] Offboarding a tenant deletes its heartbeat topics after the final invoice. The reader loses that tenant
  when the topics are gone, and its credential still covers the remaining tenants.
- [ ] Every grant and revocation is recorded: who made it, when, and which reader.
- [ ] A reader cannot write, and its failures cannot disturb OSAC's own billing pipeline.
- [ ] The provider can see how far behind each reader is, per heartbeat topic, and who each reader is.
- [ ] The contract states that a reader owns its retries and failed records.
- [ ] The contract states that the raw event log stays internal.
- [ ] The worked example runs on a dev deployment, reads usage events, derives a billable quantity, and
  carries no credentials.
- [ ] A schema change that leaves the published reference stale fails a check.

## Assumptions

- The contract covers the usage events metering publishes today. The reference is refreshed as coverage grows.
- A reader can reach the platform's message transport from its own systems.
- A reader reads several tenants' heartbeat topics at once and keeps their usage separate by tenant and
  billing account.
- Each reader keeps its own place in the stream, so a slow reader delays only itself.
- Retention is indefinite by default, so a reader can rebuild from the full history.

## Dependencies

- Event-log metering (OSAC-5753) provides the usage event pipeline the contract describes.
- The external billing id (OSAC-6161) provides the account id on each usage event.
- Customer-built adapters (OSAC-6060) build on this contract.

## Risks

- **A growing schema** (owner: contract design). Each new meter tempts a shortcut: a changed field folded
  into a published schema. One such change breaks every reader at once. The build fails on any change to a
  published schema file, so every change arrives as a new schema.
- **Leaked credentials** (owner: platform team). One reader reads every tenant, so a leaked credential
  exposes every tenant's heartbeat topics. The per-tenant model limited a leak to one tenant. The credential
  carries read-only ACLs, OSAC rotates it, the network admits only the reader's systems, and the provider
  audits who holds it. Tenants stay separate by `tenant_id` and by external billing account id, so one
  tenant's usage still maps to one bill.
- **No per-tenant revocation** (owner: platform team). A reader covers every tenant, so the provider cannot
  revoke access to one tenant alone. To stop one tenant, the provider stops the reader or deletes that
  tenant's heartbeat topics.
- **A stuck reader** (owner: metering design). A reader that stops reading falls behind, and the person who
  granted it may notice late. The provider can see how far behind each reader is, and a reader's failures
  affect only itself.

---

## Provenance

Committed: commit @ prd 0.11.3 - 9b25062, workspace main @ e526ec64b

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"e526ec64b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
