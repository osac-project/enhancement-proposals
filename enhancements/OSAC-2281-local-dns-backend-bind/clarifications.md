# Clarification Log — OSAC-2281

## Status

- Rounds completed: 3
- Open gaps: 0
- Exit criteria met: Yes

## Pre-clarification direction

### P.1: Feature scope

The Feature's Definition of Done predates the pluggable DNS backend
interface delivered by OSAC-1050, and the latest Feature comment proposes
narrowing it to CaaS endpoint DNS through that existing interface. Which
scope should the PRD cover?

#### Answer

The narrowed scope from the Feature comment: CaaS endpoint DNS through the
existing DNS backend interface, including configuration, credentials,
documentation, and validation against a real BIND server through cluster
creation and cleanup. VM hostname DNS remains with OSAC-6156.

#### Impact

The "DNS backend abstraction" and "CaaS template uses the abstraction"
Definition of Done items are treated as delivered by OSAC-1050 and cited as
an existing dependency, not re-delivered. VMaaS is not a service in scope.

#### Decision (D1)

Scope is CaaS cluster endpoint DNS (API, API-internal and application
ingress names) through the existing DNS backend interface. VM hostname DNS
is out of scope and tracked by OSAC-6156.

---

### P.2: Authenticated updates

During earlier implementation discussion, the driver decided how the DNS
server authenticates OSAC's record changes.

#### Answer

Record changes are always authenticated with a shared key that the DNS
server trusts; the key name is mandatory and unauthenticated updates are
not supported.

#### Impact

The PRD states that OSAC only sends authenticated record changes and that
the Cloud Infrastructure Admin must supply the key.

#### Decision (D2)

OSAC sends only authenticated DNS record changes. A key trusted by the DNS
server is required; unauthenticated (address-based) update permission is
not a supported configuration.

---

## Round 1 — Scope and personas

### R1.Q1: Supported DNS servers

The Feature names BIND and lists PowerDNS and CoreDNS as deferred, while the
backend uses the standard dynamic DNS update protocol that many servers
implement. What should the PRD promise about which servers work?

#### Answer

Any DNS server that accepts standard dynamic updates with a shared key can
be configured, but BIND is the only server validated and documented in this
milestone.

#### Impact

BIND is the supported, validated server. Other compatible servers are
mentioned as expected to work but unvalidated; validating them stays out of
scope, matching the Feature's out-of-scope list.

#### Decision (D3)

BIND is the validated and documented DNS server for this milestone. Other
servers that accept standard dynamic updates with a shared key may be
configured but are not validated.

---

### R1.Q2: Per-region DNS backend selection

The Definition of Done and the Cloud Provider Admin story ask to select and
approve DNS backends per region. OSAC currently selects one DNS backend per
deployment at installation and has no region concept for DNS. How should
the PRD treat this?

#### Answer

Out of scope. One DNS backend per OSAC deployment, chosen by the Cloud
Infrastructure Admin at installation.

#### Impact

The Cloud Provider Admin per-region story and the per-region Definition of
Done item move to Out of Scope with a note that a later Feature can address
them. The Cloud Provider Admin is not an affected persona.

#### Decision (D4)

One DNS backend per OSAC deployment, selected at installation. Per-region
DNS backend selection and Cloud Provider Admin approval of backends are out
of scope.

---

### R1.Q3: Tenant Admin verification

The Tenant Admin story asks to verify that DNS records for the tenant's
clusters are resolvable and correctly configured. Should tenants get a new
way to see DNS state?

#### Answer

No new tenant-facing surface. Tenants observe that their cluster's API and
console addresses resolve and connect once the cluster is ready, as with
the existing DNS backends; the backend stays invisible to tenants.

#### Impact

Tenant User and Tenant Admin stories are expressed as "cluster addresses
work regardless of backend". No UI, CLI or API changes for tenants.

#### Decision (D5)

No new tenant-visible DNS status. The tenant experience is unchanged:
cluster API and console addresses resolve once the cluster is ready,
whichever DNS backend the provider uses.

---

### R1.Q4: Configuration surface

The settings are installation values. The Enclave Wizard renders controls
from the installer schema but cannot show fields conditionally on the
selected backend. What is in scope for this milestone?

#### Answer

Installation values in this milestone. The Wizard may pick up the settings
from the schema automatically, but Wizard-specific behavior is a separate
Enclave follow-up.

#### Impact

The PRD describes configuration through installation values. Wizard-specific
behavior (such as showing the backend's settings only when it is selected)
is listed as a dependency/follow-up for the Enclave team, not delivered here.

#### Decision (D6)

The Cloud Infrastructure Admin configures the backend through installation
values. Enclave Wizard-specific behavior for this backend is out of scope
for this Feature and handled as an Enclave follow-up.

---

## Round 2 — Lifecycle, validation and environment

### R2.Q1: Behavior when the DNS server rejects or does not answer

What should users experience when the DNS server rejects OSAC's record
change (wrong key, update not permitted, wrong zone) or does not answer,
during cluster creation or deletion?

#### Answer

Fail visibly. Cluster creation does not report ready and cluster deletion
does not report complete; the failure is visible to the admin with a
message naming the setting to fix, and OSAC retries. Records are never left
behind silently after a delete.

#### Impact

Adds requirements for visible create and delete failures, actionable error
messages, retry, and no silent success on deletion.

#### Decision (D7)

A rejected or unanswered DNS change blocks the cluster lifecycle step:
creation does not report ready and deletion does not report complete until
the change succeeds. The admin sees an actionable message, and OSAC never
reports a deletion as complete while the cluster's records remain.

---

### R2.Q2: End-to-end validation against a real BIND server

The Feature asks for an e2e test with BIND covering cluster creation and
cleanup, and no CI lab has a BIND server today. What should the PRD require?

#### Answer

A documented manual validation in a lab with BIND is sufficient for this
milestone; automated e2e is tracked separately.

#### Impact

The acceptance criteria include a manual lab validation of cluster creation
and deletion against a real BIND server. Automated e2e coverage with BIND is
listed as a separately tracked follow-up (it needs a CI lab with a BIND
server); the PRD records it as a known gap rather than a deliverable of this
milestone.

#### Decision (D8)

Validation for this milestone is a documented manual run in a lab with a
real BIND server, covering cluster creation (names resolve) and deletion
(names removed). Automated e2e coverage against BIND is tracked separately.

---

### R2.Q3: Changing the DNS backend while clusters exist

What may the Cloud Infrastructure Admin do when clusters already exist, for
example moving from no DNS management or Route 53 to BIND?

#### Answer

Not supported. The DNS backend is chosen at installation and must not change
while clusters exist; documentation says so, existing clusters keep their
records where they are, and no migration is offered.

#### Impact

Adds a documented constraint and keeps migration tooling out of scope, as in
the Feature.

#### Decision (D9)

The DNS backend must not change while any cluster exists. Switching backends
and migrating records are out of scope.

---

### R2.Q4: Disconnected operation

Should the PRD state as a requirement that cluster DNS works with only the
datacenter DNS server reachable from the management cluster?

#### Answer

Yes, as a requirement.

#### Impact

Adds a testable requirement: managing cluster DNS needs no access beyond the
datacenter DNS server (no internet or cloud services).

#### Decision (D10)

Managing cluster DNS with this backend requires network access only to the
configured datacenter DNS server; no internet or cloud service is needed.

---

## Round 3 — Prerequisites, security and documentation

### R3.Q1: Making the zone resolvable for clients

OSAC writes records to the configured DNS server, but clients, cluster
nodes and the management cluster only find them if the provider's DNS makes
the zone reachable (delegation or forwarding). Who owns that?

#### Answer

A provider prerequisite. The Cloud Infrastructure Admin sets it up in their
DNS infrastructure; OSAC documents what is needed but does not configure
delegation or forwarding.

#### Impact

Listed as an assumption/prerequisite and covered in the documentation; no
OSAC requirement to configure resolution.

#### Decision (D11)

Making the cluster DNS zone resolvable (delegation or forwarding) is a
prerequisite owned by the Cloud Infrastructure Admin. OSAC documents it but
does not configure it.

---

### R3.Q2: Protecting the shared key

Should the PRD require that the key is stored only as a protected credential
and never appears in job output, logs or error messages?

#### Answer

Yes. The key is supplied as a protected credential and never shown in job
output, logs or error messages; error messages also do not reveal record
names or addresses.

#### Impact

Adds a security requirement covering the key and record data in output.

#### Decision (D12)

The shared key is supplied as a protected credential and never appears in
job output, logs, error messages or events. The DNS backend's own job
output and failure messages do not reveal record names or addresses.

Refined in PR review: the record-name rule covers only the DNS backend's
own output. Administrator-facing cluster failure events from the existing
CaaS diagnostics keep naming the affected record and job; the secret rule
applies everywhere.

---

### R3.Q3: Operator documentation scope

What should the BIND guide for the Cloud Infrastructure Admin cover?

#### Answer

Full setup: OSAC settings, the BIND-side setup (zone, key, update permission
limited to that zone), making the zone resolvable, network access from the
management cluster, and troubleshooting by error message.

#### Impact

Documentation requirements cover both OSAC and BIND-side configuration.

---

## Remaining Gaps

- None blocking. Automated e2e coverage against BIND is a separately tracked
  follow-up (D8); its tracking issue is created when the design is
  decomposed into Jira work.
