# Clarification Log — OSAC-6488

## Status

- Rounds completed: 1
- Open gaps: 3
- Exit criteria met: No

## Round 1 — Import and workload lifecycle

### R1.Q1: Readiness for AI workloads

OSAC-6488 says admins can see import and readiness status, while AI workload
use is not gated on a defined readiness state. What criteria and user-visible
conditions should determine whether a workload cluster is ready?

#### Answer

Criteria are still TBD.

#### Impact

The PRD states that readiness is visible, while the status criteria remain an
open question. The revised scope states AI workload use separately from
readiness status.

---

### R1.Q2: Tenant access to imported capacity

Should an imported provider cluster be available to AI workloads from multiple
tenants, with tenant isolation enforced, or be assigned to one tenant? Should
tenant admins and users see the underlying cluster or only their own AI
workloads?

#### Answer

Visibility and allocation are still TBD.

#### Impact

The PRD can require tenant isolation, but it cannot yet specify whether
imported clusters are shared or tenant-assigned, or whether tenants can see the
underlying cluster.

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

- Workload-cluster readiness status criteria.
- Tenant allocation and visibility for imported clusters.
- Whether a later increment should support disconnect and how it handles active
  AI workloads.

## PRD Revision Decisions

### Decision (D3): Workload readiness and AI workload use

MaaS AI inference workloads can use workload clusters while preserving tenant
isolation. The readiness definition remains open and does not gate AI workload
use.

### Decision (D4): HUB registration on disconnect

If a later increment adds disconnect, it removes the cluster's link to its
OSAC workload-cluster representation without changing its registration with the
HUB.

### Decision (D5): Disconnect scope for 0.4

Disconnecting imported clusters is out of scope for 0.4. The active-workload
rejection and unchanged HUB-registration decisions apply only if a later
increment adds disconnect.
