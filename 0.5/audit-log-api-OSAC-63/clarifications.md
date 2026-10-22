# Clarification Log — OSAC-63

## Status

- Rounds completed: 3
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Scope and Phasing

### R1.Q1: 0.5 Dev Preview MVP boundary

The Definition of Done covers all resource types, Keycloak authentication
events, before/after state capture, sovereign data residency controls,
cross-tenant operator queries, cryptographic integrity, and E2E tests.
That is a very broad scope for a Dev Preview milestone (fix version 0.5,
release date 2026-10-30). What is the MVP subset for 0.5, and what gets
deferred to later milestones?

#### Answer

All DoD items are in scope for 0.5. "Dev Preview" means the feature is
functional but not production-hardened — e.g., retention policy is
configurable but not yet tested at scale, crypto integrity is implemented
but not yet independently audited.

#### Impact

The PRD will declare all DoD items as in-scope for 0.5 and describe the
Dev Preview maturity level. No phased delivery — all capabilities ship
together. The PRD should note that production hardening (scale testing,
independent audit of crypto integrity, retention policy stress testing)
is a follow-up for a later milestone.

#### Decision (D1)

The 0.5 Dev Preview milestone delivers the walking skeleton: audit
event capture, query, and API-level append-only immutability.
Cryptographic integrity, bulk export, before/after state, and
configurable retention are deferred to follow-up Features (see D4, D5,
D10, R2.Q3). Dev Preview means functional but not production-hardened.

---

### R1.Q2: Actor attribution (OSAC-6154) as prerequisite

OSAC-6154 (Add actor attribution to Fulfillment Events) is currently in
New status. Without it, audit records cannot identify who performed an
action — only what happened and when. Is actor attribution a hard
prerequisite for the 0.5 audit log delivery, or can the audit log
launch without "who" attribution?

#### Answer

Hard prerequisite — the audit log is meaningless without actor identity.

#### Impact

OSAC-6154 must be delivered before or in parallel with the audit log.
The PRD will list actor attribution as a blocking dependency. If
OSAC-6154 slips, the audit log feature is blocked.

#### Decision (D2)

OSAC-6154 (actor attribution in Fulfillment Events) is a hard
prerequisite for the audit log. The feature will not ship without it.

---

### R1.Q3: Keycloak authentication event capture for 0.5

The user story "Authentication events" calls for capturing Keycloak
login attempts, token issuance, and session events. This requires
Keycloak integration (webhook or event listener) separate from the
fulfillment event pipeline. Is Keycloak audit event capture in scope
for 0.5?

#### Answer

Yes, in scope for 0.5.

#### Impact

The PRD must include a requirement for Keycloak event integration.
This is a separate event source from Fulfillment Events (Kafka) and
will need its own capture mechanism (Keycloak event listener or SPI).
The design will need to address how Keycloak events are ingested into
the audit log alongside fulfillment events.

#### Decision (D3)

Keycloak authentication event capture (login success/failure, token
operations, session events) is in scope for 0.5.

---

### R1.Q4: Before/after state capture scope

The DoD includes "Before/after state capture for configuration changes."
Capturing the full before/after state of every resource mutation could
produce very large payloads (e.g., a cluster order spec change). Is
before/after state capture in scope for 0.5, and is it limited to
specific resource types?

#### Answer

Full before/after capture for all resource mutations in 0.5.

#### Impact

The PRD will require before/after state capture for all audited
resource mutations. The design will need to address payload size
management (e.g., diff-only vs. full snapshots, compression, storage
implications).

#### Decision (D4)

~~Full before/after state capture for all resource mutations is in
scope for 0.5.~~ Revised after EP review: deferred to a follow-up
Feature. The walking skeleton captures the action and target resource
without full state diffs.

---

### R1.Q5: Tamper-evident immutability definition

The DoD requires "Append-only, immutable storage — records cannot be
modified or deleted via any API." Does "tamper-evident" in the Feature
Goal mean cryptographic integrity verification (e.g., hash chains so
a reader can detect if records were removed or altered at the storage
layer), or is it sufficient that no API exposes update/delete
operations?

#### Answer

Cryptographic integrity verification is required.

#### Impact

The PRD will require cryptographic tamper-evidence (e.g., hash chains
or Merkle trees) in addition to API-level immutability. This is a
significant requirement that affects storage design, query
performance, and verification workflows. The design must address the
specific cryptographic mechanism.

#### Decision (D5)

~~Audit records must have cryptographic integrity verification (not
just API-level immutability).~~ Revised after EP review: deferred to a
follow-up Feature. The walking skeleton provides API-level append-only
immutability; cryptographic tamper-evidence is a later increment.

---

## Round 2 — Personas and User Capabilities

### R2.Q1: Audit log access by persona

OSAC has four personas: Cloud Provider Admin, Cloud Infrastructure Admin,
Tenant Admin, and Tenant User. The requirements mention "tenant admins"
and "platform operators" but don't map precisely to all four. Which
personas can query audit logs?

#### Answer

Cloud Provider Admin (cross-tenant audit queries) and Tenant Admin
(tenant-scoped audit queries). Cloud Infrastructure Admin and Tenant
User are excluded from audit log access in 0.5.

#### Impact

The PRD will define two audit query access levels: (1) Tenant Admin —
can query audit events scoped to their own organization; (2) Cloud
Provider Admin — can query audit events across all tenants and within
a specific tenant. Cloud Infrastructure Admin and Tenant User do not
have audit log access.

#### Decision (D6)

Only Cloud Provider Admin and Tenant Admin can query audit logs.
Cloud Infrastructure Admin and Tenant User are excluded.

---

### R2.Q2: CLI access for audit queries

The Feature explicitly puts UI out of scope ("API-first"). The OSAC CLI
is a primary interface for many personas. Should the PRD include CLI
commands for querying audit logs, or is this API-only for 0.5?

#### Answer

API-only for 0.5. CLI access is deferred to a later milestone.

#### Impact

The PRD will specify that audit log queries are available via the
gRPC/HTTP API only. CLI commands are out of scope for 0.5. UI was
already declared out of scope in the Feature issue.

#### Decision (D7)

Audit log query is API-only for 0.5. CLI and UI are deferred.

---

### R2.Q3: Regulatory compliance export formats

The user story says "tenants can export audit data in formats suitable
for regulatory submissions." What does "export" mean from the user's
perspective, and what formats are required?

#### Answer

~~Bulk download endpoint returning JSON and/or CSV.~~ Revised after EP
review: deferred to a follow-up Feature. The paginated query API
serves compliance workflows initially.

#### Impact

Bulk export is out of scope for 0.5. The paginated query API provides
initial compliance reporting capability.

---

### R2.Q4: OSAC services in scope for event capture

OSAC has multiple services: BMaaS, CaaS, VMaaS, MaaS, Enclave. The
Feature lists resource types across compute, networking, storage,
identity, and secrets. Are all services in scope for audit event
capture in 0.5?

#### Answer

All services (BMaaS, CaaS, VMaaS, MaaS, Enclave).

#### Impact

The PRD will require audit event capture across all OSAC services.
The design must address how each service's events reach the audit
log — services that already emit Fulfillment Events via Kafka are
straightforward; services that do not may need new event emission
or alternative capture mechanisms.

#### Decision (D8)

All OSAC services (BMaaS, CaaS, VMaaS, MaaS, Enclave) are in scope
for audit event capture in 0.5.

---

### R2.Q5: Cross-tenant operator query model

The DoD says "Platform operator cross-tenant query capability (with
audit-of-audit)." Can the Cloud Provider Admin query audit events
across all tenants in a single query, or must they specify a tenant
and query one at a time?

#### Answer

Both modes — cross-tenant queries (e.g., "show all VM deletions
across all tenants") and per-tenant queries (scoped to a specific
tenant).

#### Impact

The PRD will define two query modes for Cloud Provider Admin: (1)
cross-tenant — queries across all tenants with optional tenant filter;
(2) per-tenant — queries scoped to a specific tenant. Both modes log
the operator's access (audit-of-audit).

#### Decision (D9)

Cloud Provider Admin gets both cross-tenant and per-tenant query
modes. Both modes are subject to audit-of-audit logging.

---

## Round 3 — Non-Functional Requirements and Operations

### R3.Q1: Performance expectations

The audit log will capture events from all services, all resource
mutations, plus Keycloak auth events. Are there query latency SLOs or
event ingestion lag targets for 0.5?

#### Answer

Dev Preview — defer SLOs to a later milestone. Functional correctness
is the bar for 0.5.

#### Impact

The PRD will note that performance SLOs (query latency, ingestion
lag, throughput) are deferred to a post-Dev-Preview milestone.
Functional correctness and completeness are the acceptance criteria
for 0.5. The PRD should state this explicitly so the design is not
over-constrained.

---

### R3.Q2: Retention policy configuration and defaults

The DoD says "Configurable retention policy with platform-defined
minimum (e.g., 30 days per NVIDIA SEC08)." Who configures the
retention policy, and what is the default?

#### Answer

Helm default plus runtime-adjustable by Cloud Provider Admin. The
minimum is 30 days (per NVIDIA SEC08). The default and any maximum
are to be determined by the design.

#### Impact

The PRD will require: (1) a default retention period set via Helm
values at installation; (2) a runtime API for the Cloud Provider Admin
to adjust the retention period, subject to the 30-day minimum floor.
The specific default value and any upper bound are design decisions.

#### Decision (D10)

~~Retention policy is configured via Helm default at install time and
adjustable at runtime by the Cloud Provider Admin via API. The minimum
retention period is 30 days.~~ Revised after EP review: deferred to a
follow-up Feature. The walking skeleton retains records indefinitely;
retention management is a later increment.

---

### R3.Q3: Data residency mechanism

The DoD says "Audit data residency within deployment jurisdiction." Is
this automatic (audit data stored in the same database/cluster) or does
the platform operator configure a separate storage location?

#### Answer

Automatic — audit data is stored in the same database/cluster as the
rest of the platform, inheriting the deployment's jurisdiction.

#### Impact

The PRD will state that audit data residency is satisfied by co-locating
audit storage with the platform deployment. No separate storage
configuration is needed for data residency. This simplifies the
deployment model. Explicit storage location configuration for audit
data (e.g., separate jurisdiction-specific storage) is a potential
future enhancement.

#### Decision (D11)

Audit data residency is automatic — audit data is co-located with
the platform deployment and inherits its jurisdiction. No separate
storage configuration for 0.5.

---

### R3.Q4: Deployment prerequisites

Does the audit log require new infrastructure beyond what OSAC already
deploys (e.g., dedicated PostgreSQL instance, additional Kafka topics)?
Or does it reuse existing infrastructure?

#### Answer

The PRD states the capability; the design decides the infrastructure
model. The PRD should not prescribe whether audit data uses the
fulfillment DB, a dedicated DB, or another approach.

#### Impact

The PRD will specify the audit log's functional and non-functional
requirements without prescribing infrastructure topology. The design
document will decide whether to extend existing infrastructure (e.g.,
fulfillment DB, existing Kafka topics) or introduce dedicated
components. The PRD will note that the audit log requires persistent
storage and event ingestion from Kafka and Keycloak, leaving the
specific deployment architecture to the design.

---

## Remaining Gaps

None. All identified gaps have been resolved.
