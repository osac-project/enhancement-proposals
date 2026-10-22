# Clarification Log — OSAC-6488

## Status

- Rounds completed: 1
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Import and workload lifecycle

### R1.Q1: Readiness for AI workloads

The initial PRD included readiness status, but no criteria were agreed. What
criteria and user-visible conditions should determine whether a workload
cluster is ready?

#### Answer

AI workload readiness is deferred from 0.4. In a post-merge comment, Michael
Hrivnak suggested ACM's `Available` condition as an initial indicator that ACM
policies can be applied ([comment](https://github.com/osac-project/enhancement-proposals/pull/392#discussion_r4318409162)).
This is not adopted as an AI workload readiness criterion for 0.4. If OSAC
directly interacts with clusters in a later enhancement, the status of that
connection and its service account can be considered separately.

#### Impact

The 0.4 feature reports import outcome only and makes no claim about AI
workload readiness. ACM's `Available` condition is a possible starting signal
for a later cluster-availability view, not a readiness guarantee for AI
workloads. Direct OSAC connection status is a separate future concern.

---

### R1.Q2: Tenant access to imported capacity

Should an imported provider cluster be available to AI workloads from multiple
tenants, with tenant isolation enforced, or be assigned to one tenant? Should
tenant admins and users see the underlying cluster or only their own AI
workloads?

#### Answer

Imported clusters are shared provider capacity, not assigned to individual
tenants. Praxis schedules inference requests to specific clusters; OSAC does
not track per-cluster tenant allocation. Cluster details are visible only to
Cloud Provider Admins; Tenant Admins and Tenant Users access capacity through
OSAC AI workload flows ([comment](https://github.com/osac-project/enhancement-proposals/pull/392#discussion_r4318280278)).

#### Impact

Imported cluster details are visible only to Cloud Provider Admins. Imported
capacity is shared at the provider level; OSAC does not assign clusters to
individual tenants. OSAC's tenant model governs access to AI workload flows.

---

### R1.Q3: Disconnect with active workloads (deferred from 0.4)

If an admin disconnects a cluster that has running or pending AI workloads,
what should happen to those workloads before the cluster is unlinked from OSAC?

#### Answer

Disconnect is out of scope for 0.4. If OSAC adds disconnect later, reject it
while workloads are active (assigned to an AI grid).

#### Impact

This behavior applies to a future disconnect capability. The current 0.4 scope
does not include disconnecting imported clusters.

#### Decision (D1)

For a future disconnect capability, reject a request while workloads are active
on an AI grid.

---

### R1.Q4: Import failure feedback and recovery

The Feature requires actionable import failures. What should the admin see or
be able to do—for example, a clear cause and recovery guidance, a retry action,
or both?

#### Answer

The import operation is currently understood to create the workload-cluster
construct in the OSAC database. If import fails, show the cause; no additional
recovery action is required in this flow.

#### Impact

The Cloud Provider Admin sees the cause of an import failure. The import
flow does not require a retry or recovery action.

#### Decision (D2)

On import failure, show the cause. Do not require a retry or recovery action in
the import flow.

---

## Remaining Gaps

- None. Readiness criteria and disconnect remain deferred from 0.4.

## PRD Revision Decisions

### Decision (D3): Workload readiness and AI workload use

MaaS AI inference workloads can use workload clusters while preserving tenant
isolation. Readiness status and criteria are deferred to a later enhancement
and do not gate workload use in this increment. ACM's `Available` condition is
a possible future cluster-availability signal, not an AI workload readiness
criterion for 0.4.

### Decision (D4): HUB registration on disconnect

If a later increment adds disconnect, it removes the cluster's link to its
OSAC workload-cluster representation without changing its registration with the
HUB.

### Decision (D5): Disconnect scope for 0.4

Disconnecting imported clusters is out of scope for 0.4. The active-workload
rejection and unchanged HUB-registration decisions apply only if a later
increment adds disconnect.

### Decision (D6): Tenant visibility

Imported workload-cluster details are visible only to Cloud Provider Admins.
Tenant Admins and Tenant Users access capacity through OSAC AI workload flows.

### Decision (D7): Shared provider capacity

Imported clusters are shared provider capacity, not assigned to individual
tenants. Praxis schedules requests to specific clusters; OSAC applies its
tenant model to AI workload access without tracking per-cluster tenant
allocation.
