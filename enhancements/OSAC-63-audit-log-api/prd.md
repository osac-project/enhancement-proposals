# Activity and Audit Log API


| Field     | Value                                                  |
| --------- | ------------------------------------------------------ |
| Author(s) | Elkana Hendler                                         |
| Jira      | [OSAC-63](https://redhat.atlassian.net/browse/OSAC-63) |
| Milestone | 0.5 (Dev Preview)                                      |
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
is a follow-up. Captured user-initiated events identify the authenticated
user who initiated the action as the actor. [Clarify: D8] [User]
- Desired-state request records indicate whether each change was accepted.
Significant platform actions and completion or failure outcomes are recorded
even when an outcome has no attributable actor.
Where available, outcomes identify the desired-state revision being
processed. Outcomes are linked to requests when that relationship is
known. [User]
- Keycloak authentication events (login success/failure, token operations,
  and session events) appear in the audit trail. Attribute an event to a
  tenant only when Keycloak provides a trusted organization context. Failed
  login events have no tenant attribution and are visible only to Cloud
  Provider Admins. If the Keycloak event includes the resolved target account,
  record it as the actor. Tenant Admins cannot see failed-login events.
  Never infer a tenant from the submitted login identifier. [Clarify: D3]
  [User]
- Audit records and events forwarded to the audit log must not contain
password values, token values, private keys, or other credential contents.
For credential access, the audit record states that access occurred,
what was accessed, and the outcome without including credential values.
- Tenant-scoped and cross-tenant query via gRPC and HTTP+JSON API.
Supported filters: time range, actor, action type, resource type,
resource ID, and outcome. Tenant scope is derived from the authenticated
principal — Tenant Admins cannot query outside their organization, and
denied access attempts are recorded. An actor filter matches records whose
actor is the requested identity. Records without an actor are returned when
no actor filter is set and remain queryable through other filters.
[Clarify: D7, D9] [User]
- API-level append-only storage — no API exposes update or delete of
audit records. This does not protect against direct database access or
privileged operator intervention.
- Audit-of-audit: Access to audit data by every principal is itself
recorded. [Clarify: D9]
- Data residency: audit data is co-located with the platform deployment,
inheriting the deployment's sovereign jurisdiction. [Clarify: D11]



## Out of Scope

- Cryptographic integrity verification is deferred to follow-up Feature
OSAC-3415.
- Fail-closed behavior when audit event capture or delivery is unavailable
— follow-up Feature. This increment is fail-open: platform actions may
proceed when audit events cannot be captured or delivered.
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
- Known lifecycle reason codes are not captured in this increment; lifecycle
  outcomes are recorded without a separate reason field.
- Real-time alerting on audit events (event-driven alerting and webhook
integration are a follow-up Feature).
- Audit log forwarding to external SIEM systems.
- Data-plane audit logging (individual object reads/writes in storage,
network packet logging) — control-plane actions only.
- Native audit events produced by ACM or OCP, including actions performed
directly in those products, are out of scope. This increment captures
events emitted by OSAC services only.
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
- As a Cloud Provider Admin, I want user-initiated audit events across
  tenants to identify the user who performed each action so that I can
  establish accountability and investigate incidents. [User]
- As a Cloud Provider Admin, I want to query failed login attempts across
  the platform, with the targeted account identified when the Keycloak event
  includes it and no tenant attribution, so that I can investigate
  authentication failures. [Clarify: D3] [User]



### Tenant Admin

- As a Tenant Admin, I want to query a chronological audit trail of
available events from my organization — using the filters defined in In
Scope — so that I can investigate incidents and track changes without
requesting platform operator assistance.
- As a Tenant Admin, I want audit events for resource lifecycle and
administrative actions in my organization to identify the authenticated
user who initiated each action so that I can trace and investigate
changes. [User]
- As a Tenant Admin, I want desired-state request records to show whether
each change was accepted and lifecycle outcomes to remain visible even
when an outcome has no attributable actor, so that I can understand what
happened after a request. Where available, lifecycle events identify the
desired-state revision being processed; outcomes link to requests only
when that relationship is known. [User]
- As a Tenant Admin, I want Keycloak authentication activity tied to my
  organization to appear with the user's identity in my audit trail so I can
  investigate identity activity. Failed-login events are excluded from my
  audit trail; only Cloud Provider Admins can see them. [Clarify: D3] [User]



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

- **OSAC-6154 (blocking for resource lifecycle actor attribution):**
OSAC-6154 is required to attribute resource lifecycle events to the
authenticated user who initiated the action. Those events cannot be
delivered as complete in-scope audit records without actor attribution.
[User]
- **OSAC-983 (satisfied):** The audit log depends on platform event
delivery infrastructure that is already in place (OSAC-983 is Closed).
- **Keycloak authentication events:** Authentication events (login,
token, session) originate from Keycloak and carry their own actor
identity independently of OSAC-6154. These events must be available
to the audit log independently of resource lifecycle events.
[Clarify: D3]

---

## Provenance

Authored: draft @ prd 0.11.5 - 4164796, workspace main @ f4607b916
Final: revise @ prd 0.11.5 - b369da0, workspace codex/OSAC-63-design-readability @ 1e608538d (dirty)

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"b369da0","source_repo":"1e608538d (dirty)","source_repo_branch":"codex/OSAC-63-design-readability","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","manual-edit","revise","revise","respond","respond","manual-edit","revise","revise","revise","revise","revise","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
