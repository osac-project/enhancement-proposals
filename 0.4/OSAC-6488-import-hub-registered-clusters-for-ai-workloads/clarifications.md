# Clarification Log — OSAC-6488

## Status

- Rounds completed: 1
- Open gaps: 2
- Exit criteria met: No

## Round 1 — Import and workload lifecycle

### R1.Q1: Readiness for AI workloads

OSAC-6488 says admins can see import and readiness status, and only a ready
cluster should receive AI workloads. What should admins be able to verify
before the cluster is shown as ready? If readiness checks are required, what
user-visible conditions should they cover?

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

### R1.Q3: Disconnect with active workloads

If an admin disconnects a cluster that has running or pending AI workloads,
what should happen to those workloads before the HUB registration is unlinked
and the cluster stops receiving new work?

#### Answer

Reject disconnect while workloads are active (assigned to an AI grid).

#### Impact

An admin cannot disconnect a cluster while it has active workloads assigned to
an AI grid.

#### Decision (D1)

Reject a disconnect request while workloads are active on an AI grid.

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

The Cloud Infrastructure Admin sees the cause of an import failure. The import
flow does not require a retry or recovery action.

#### Decision (D2)

On import failure, show the cause. Do not require a retry or recovery action in
the import flow.

---

## Remaining Gaps

- Workload-cluster readiness status criteria.
- Tenant allocation and visibility for imported clusters.

## PRD Revision Decisions

### Decision (D3): Workload readiness and AI workload use

OSAC AI workloads can use workload clusters while preserving tenant
isolation. The readiness definition remains open and does not gate AI workload
use.

### Decision (D4): HUB registration on disconnect

Disconnecting removes the cluster's link to its OSAC workload-cluster
representation without changing its registration with the HUB.
