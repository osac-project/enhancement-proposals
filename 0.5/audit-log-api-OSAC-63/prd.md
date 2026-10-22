# Activity and Audit Log API


| Field     | Value                                                  |
| --------- | ------------------------------------------------------ |
| Author(s) | Elkana Hendler                                         |
| Jira      | [OSAC-63](https://redhat.atlassian.net/browse/OSAC-63) |
| Date      | 2026-10-20                                             |


## Problem Statement

OSAC does not record or expose an audit trail of platform activity. No
persona can see who performed an action, when it occurred, or what changed
on any resource. Platform operators cannot produce compliance-ready audit
reports, and tenants have no self-service access to their organization's
activity history.

Sovereign cloud deployments are subject to regulatory frameworks (GDPR,
DPDPA, NIS2, local data protection laws) that mandate auditable records of
data access and administrative actions, with guarantees about where audit
data is stored and who can access it. Without an audit log, OSAC cannot
satisfy these requirements — blocking compliance readiness efforts across
multiple regulatory domains (HIPAA, NIST SP 800-53, EU sovereignty) that
depend on this capability.

## In Scope

- Audit event capture for control-plane actions across OSAC services
(BMaaS, CaaS, VMaaS, MaaS, Enclave): resource mutations, API access to
sensitive resources, failed authorization attempts, and administrative
actions (organization lifecycle, role changes, IdP configuration, project
permissions). This first increment captures events from services that
already have audit event support; adding support to remaining services
is a follow-up. [Clarify: D8]
- Authentication events from the organization's Keycloak realm — login
success/failure, token operations, session events — appear in the
tenant's audit trail. [Clarify: D3]
- Tenant-scoped and cross-tenant query via gRPC and HTTP+JSON API.
Supported filters: time range, actor, action type, resource type,
resource ID, and outcome. Tenant scope is derived from the authenticated
principal — Tenant Admins cannot query outside their organization, and
denied access attempts are recorded. [Clarify: D7, D9]
- API-level append-only storage — no API exposes update or delete of
audit records. This does not protect against direct database access or
privileged operator intervention; cryptographic tamper-evidence that
covers storage-level integrity is deferred (see Out of Scope).
- Audit-of-audit: Cloud Provider Admin access to tenant audit data is
itself recorded. [Clarify: D9]
- Data residency: audit data is co-located with the platform deployment,
inheriting the deployment's sovereign jurisdiction. [Clarify: D11]
- Target milestone: 0.5 (Dev Preview) — functional but not
production-hardened. [Clarify: D1]



## Out of Scope

- Cryptographic integrity verification (hash chains, Merkle trees) —
follow-up Feature under the same Outcome (OSAC-3415). This first
increment provides append-only immutability; cryptographic
tamper-evidence is a later increment.
- Bulk export of audit records in JSON and CSV — follow-up Feature.
The paginated query API serves compliance workflows initially.
- Before/after state capture for resource mutations — follow-up Feature.
Audit records capture the action and target resource; full state diffs
are a later increment.
- Configurable retention policy — follow-up Feature. Records are retained
indefinitely in this first increment; retention management (minimum
floor, runtime adjustment) is a later increment.
- UI and CLI for audit log browsing — API-only for this milestone.
[Clarify: D7]
- Real-time alerting on audit events (event-driven alerting and webhook
integration are a follow-up Feature).
- Audit log forwarding to external SIEM systems.
- Data-plane audit logging (individual object reads/writes in storage,
network packet logging) — control-plane actions only.
- Audit log analytics and dashboards.
- Specific regulatory certification (GDPR, DPDPA, NIS2) — this feature
provides the technical controls; certification is an organizational
process.
- Performance SLOs (query latency, ingestion lag, throughput) — deferred
to a post-Dev-Preview milestone. Functional correctness is the bar for
0.5. [Clarify: R3.Q1]



## User Stories

Cloud Infrastructure Admin and Tenant User do not have audit log access
in this milestone. [Clarify: D6]

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to query audit events across all
tenants — using the filters defined in In Scope — so that I can
investigate security incidents and produce platform-wide compliance
reports. [Clarify: D9]
- As a Cloud Provider Admin, I want to query audit events scoped to a
specific tenant so that I can produce tenant-scoped audit extracts for
regulatory authorities upon lawful request without exposing other
tenants' data. [Clarify: D9]



### Tenant Admin

- As a Tenant Admin, I want to query a chronological audit trail of all
actions performed within my organization — using the filters defined
in In Scope — so that I can investigate incidents and track changes
without requesting platform operator assistance.
- As a Tenant Admin, I want each audit record to include the actor,
timestamp, action, target resource, and outcome so that I can see
exactly who did what.
- As a Tenant Admin, I want authentication events (login success/failure,
token issuance, session events) from my organization's users to appear
in the audit trail so that I have complete visibility into identity
activity. [Clarify: D3]



## Assumptions

- Keycloak is deployed as part of the OSAC platform and can be configured
to make authentication events available to the audit log.
- All OSAC services that manage tenant resources can deliver resource
lifecycle events to the audit log. Services that do not yet have
audit event support for all their resource types are covered by a
follow-up Feature; this first increment consumes what is already
available.
- All platform infrastructure involved in audit event capture, transport,
retention, backup, replication, and failover runs within the
deployment's sovereign jurisdiction. The audit log inherits this
platform-wide placement guarantee.



## Dependencies

- **OSAC-6154 (blocking):** Audit records for resource lifecycle
actions must identify the user who initiated the action. Until
OSAC-6154 delivers actor attribution for resource lifecycle events,
those audit records cannot attribute actions to users. [Clarify: D2]
- **OSAC-983 (satisfied):** The audit log depends on platform event
delivery infrastructure that is already in place (OSAC-983 is Closed).
- **Keycloak authentication events:** Authentication events (login,
token, session) originate from Keycloak and carry their own actor
identity independently of OSAC-6154. These events must be available
to the audit log independently of resource lifecycle events.
[Clarify: D3]

---

## Provenance

Authored: revise @ prd 0.11.5 - 4164796, workspace main @ f4607b916
Phases: draft, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"4164796","source_repo":"f4607b916","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
