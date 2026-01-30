---
title: computeinstance-phase-condition-expansion
authors:
  - Akshay Nadkarni
creation-date: 2026-01-29
last-updated: 2026-01-29
tracking-link:
  - TBD
see-also:
replaces:
  - "[ComputeInstance-VM_PhasesAndConditions_Proposal (Google Doc)](https://docs.google.com/document/d/1wgqAblnT7OHlT5bvaI4bi842kyeR3u4VfC_TAJXbGcI/edit?usp=sharing)"
superseded-by:
---

# ComputeInstance Phase and Condition Expansion

## Summary

This enhancement proposes a cleanup and expansion of the `ComputeInstancePhaseType` and `ComputeInstanceConditionType` values for the OSAC VMaaS offering.

The current 4-phase model (`Progressing`, `Ready`, `Failed`, `Deleting`) was designed for initial provisioning workflows. As VMaaS matures to support full lifecycle operations (start, stop, pause, resume), the phase model needs to expand to represent these power states. Additionally, the current conditions overlap with phases rather than providing orthogonal health information.

The redesign expands from 4 phases to 8 phases to properly represent the full VM lifecycle, aligning with industry standards from AWS, GCE, and KubeVirt. Conditions are redesigned to be orthogonal health indicators that complement, rather than duplicate, the lifecycle phase.

> **Note:** You can find more details on industry standards [here](https://docs.google.com/document/d/1wgqAblnT7OHlT5bvaI4bi842kyeR3u4VfC_TAJXbGcI/edit?tab=t.oocbc3frwt7c). 

This change enables users to understand VM power state (running, stopped, paused), see transitional progress (starting, stopping), and receive clear health signals through conditions - providing the operational visibility expected from a modern cloud platform.

## Motivation

As VMaaS matures to support full VM lifecycle operations, users need clear visibility into VM power state and operational status. The current phase model does not distinguish between a running VM and a stopped VM, and conditions overlap with phases rather than providing independent health information. This enhancement addresses these gaps to provide the operational visibility expected from a modern cloud platform.

### User Stories

**For Tenants:**

* As a tenant, I want to see if my VM is running, stopped, or paused, so that I understand its current power state
* As a tenant, I want to see when my VM is starting or stopping, so that I know an operation is in progress
* As a tenant, I want to see clear health indicators for my VM, so that I can identify issues without interpreting phase values
* As a tenant, I want to see when my VM is being deleted, so that I can track the deletion progress

**For Cloud Providers:**

* As a cloud provider, I want to see clear VM power states for tenant VMs, so that I can provide effective support and troubleshooting
* As a cloud provider, I want VM phases that align with industry standards, so that I can build monitoring dashboards with familiar terminology

**For Developers:**

* As a developer, I want a phase/condition model where conditions are orthogonal to phases, so that new conditions can be added in future releases without breaking my existing integrations
* As a developer, I want a well-defined phase model that can accommodate future VM operations (e.g., live migration), so that the API can evolve to support new capabilities

### Goals

* Represent VM power state clearly - Users can see if a VM is Running, Stopped, or Paused
* Expose transitional states - Users can see when operations are in progress (Starting, Stopping, Deleting)
* Align with industry standards - Phase values match what users expect from AWS, GCE, and KubeVirt
* Make conditions orthogonal to phases - Conditions represent health/status attributes, not lifecycle state
* Expose DELETING in API - The K8s operator's Deleting phase should be visible in the public API

### Non-Goals

* Additional conditions - Conditions such as NetworkReady and RestartRequired will be addressed in future enhancements as their dependencies (networking design, configuration change detection) are not yet finalized
* New VM operations - This enhancement is about status representation, not adding pause/resume/stop operations themselves
* Hibernate (suspend to disk) - Only in-memory pause is supported by KubeVirt; hibernate is out of scope

## Proposal

This enhancement modifies the `ComputeInstance` status model across three layers:

**1. OSAC Operator (Kubernetes CRD)**
- Expand `ComputeInstancePhaseType` from 4 phases to 8 phases
- Refactor `ComputeInstanceConditionType` to be orthogonal to phases

**2. Fulfillment API (Public protobuf)**
- Add corresponding `ComputeInstanceState` enum values
- Update `ComputeInstanceConditionType` enum to match the orthogonal design
- Remove old values (`PROGRESSING`, `READY`) since there are no external clients

**3. Fulfillment Service (Private protobuf)**
- Mirror public API changes

**Proposed Phases (8):**

| Phase | Description |
|-------|-------------|
| `Pending` | VM is being provisioned, infrastructure resources allocating |
| `Starting` | VM is powering on, guest OS booting |
| `Running` | VM is running and operational |
| `Stopping` | VM is powering off, guest OS shutting down |
| `Stopped` | VM is powered off, resources retained |
| `Paused` | VM is paused, memory preserved, no CPU allocated |
| `Deleting` | VM is being permanently deleted |
| `Failed` | VM encountered an error |

**Proposed Conditions (orthogonal to phases):**

| Condition (CRD) | Condition (Protobuf) | Layer | Description |
|-----------------|---------------------|-------|-------------|
| `Provisioned` | `PROVISIONED` | CRD + API | Infrastructure resources (compute, storage) are allocated |
| `Available` | `AVAILABLE` | CRD + API | VM is ready for user workloads |
| `Degraded` | `DEGRADED` | CRD + API | VM is running but with reduced capability |
| `ConfigurationApplied` | `CONFIGURATION_APPLIED` | CRD + API | Desired configuration matches actual |
| — | `RESTART_IN_PROGRESS` | API only | Restart operation is in progress |
| — | `RESTART_FAILED` | API only | Restart operation failed |

> **Note:** CRD conditions use PascalCase (Kubernetes convention). Protobuf conditions use UPPER_SNAKE_CASE with prefix (e.g., `COMPUTE_INSTANCE_CONDITION_TYPE_AVAILABLE`). Restart conditions exist only in the protobuf API because restart functionality is implemented at the fulfillment service layer.

The phase values are derived from the underlying KubeVirt `VirtualMachine.Status.PrintableStatus`, ensuring accurate representation of VM power state.

### Workflow Description

**Phase Transitions**

A tenant creates a ComputeInstance and observes its lifecycle through phases:

1. **Create**: Tenant requests a new VM → Phase: `Pending`
2. **Provisioning completes**: KubeVirt VM is created, booting → Phase: `Starting`
3. **Boot completes**: VM is operational → Phase: `Running`
4. **Stop requested**: Tenant stops the VM → Phase: `Stopping` → `Stopped`
5. **Start requested**: Tenant starts the VM → Phase: `Starting` → `Running`
6. **Pause requested**: Tenant pauses the VM → Phase: `Paused`
7. **Resume requested**: Tenant resumes the VM → Phase: `Running`
8. **Delete requested**: Tenant deletes the VM → Phase: `Deleting` → (resource removed)

**Restart Handling**

Restart is not a separate phase. When a tenant restarts a VM:
- Phase transitions: `Running` → `Stopping` → `Stopped` → `Starting` → `Running`
- Condition `RESTART_IN_PROGRESS` is set to `True` throughout the operation (API only)
- On completion, `RESTART_IN_PROGRESS` is set to `False`
- On failure, phase becomes `Failed` and condition `RESTART_FAILED` is set to `True`

**State Transition Diagram**

```
                              ┌─────────────────────────────────────────┐
                              │                (start)                  │
                              ▼                                         │
[Create] ──► Pending ──► Starting ──► Running ──► Stopping ──► Stopped ─┘
                                          │
                                          │ (pause)
                                          ▼
                                       Paused
                                          │
                                          │ (resume)
                                          ▼
                                       Running

[Any state] ──► Failed (on error)
[Any state] ──► Deleting ──► (removed)
```

### API Extensions

This enhancement modifies existing API types rather than adding new CRDs or webhooks.

**Modified Resources:**

| Layer | Resource | Change |
|-------|----------|--------|
| OSAC Operator | `ComputeInstance` CRD | Expand `status.phase` values, refactor `status.conditions` |
| Fulfillment API | `ComputeInstanceState` enum | Replace 4 values with 8 new phase values |
| Fulfillment API | `ComputeInstanceConditionType` enum | Keep 3 conditions, remove 3, add 3 new |
| Fulfillment Service | `ComputeInstanceState` enum | Mirror public API changes |
| Fulfillment Service | `ComputeInstanceConditionType` enum | Mirror public API changes |

**Phase Mapping (Current → Proposed):**

| Current (CRD) | Current (Protobuf) | Proposed (CRD) | Proposed (Protobuf) |
|---------------|-------------------|----------------|---------------------|
| `Progressing` | `PROGRESSING` | `Pending` | `PENDING` |
| — | — | `Starting` | `STARTING` |
| `Ready` | `READY` | `Running` | `RUNNING` |
| — | — | `Stopping` | `STOPPING` |
| — | — | `Stopped` | `STOPPED` |
| — | — | `Paused` | `PAUSED` |
| `Deleting` | — | `Deleting` | `DELETING` |
| `Failed` | `FAILED` | `Failed` | `FAILED` |

**Condition Mapping (Current → Proposed):**

| Current (CRD) | Current (Protobuf) | Proposed (CRD) | Proposed (Protobuf) | Action |
|---------------|-------------------|----------------|---------------------|--------|
| `Accepted` | — | — | — | Remove (no longer needed) |
| `Progressing` | `PROGRESSING` | — | — | Remove (phase represents this) |
| `Available` | `READY` | `Available` | `AVAILABLE` | Rename in protobuf |
| `Deleting` | — | — | — | Remove (phase represents this) |
| — | `FAILED` | — | — | Remove (phase represents this) |
| — | `DEGRADED` | `Degraded` | `DEGRADED` | Keep, add to CRD |
| — | `RESTART_IN_PROGRESS` | — | `RESTART_IN_PROGRESS` | Keep (API only) |
| — | `RESTART_FAILED` | — | `RESTART_FAILED` | Keep (API only) |
| — | — | `Provisioned` | `PROVISIONED` | New |
| — | — | `ConfigurationApplied` | `CONFIGURATION_APPLIED` | New |

**Behavioral Changes:**

- `ComputeInstance.status.phase` will reflect VM power state (`Running`, `Stopped`, `Paused`) rather than reconciliation status
- Conditions are orthogonal to phases - a condition like `Available` can be True or False independent of the phase

### Implementation Details/Notes/Constraints

**Phase Determination Logic**

The controller determines the ComputeInstance phase based on the KubeVirt `VirtualMachine.Status.PrintableStatus` and the `ComputeInstance.DeletionTimestamp`:

| Condition | ComputeInstance Phase |
|-----------|----------------------|
| `DeletionTimestamp` is set | `Deleting` |
| KubeVirt VM does not exist | `Pending` |
| PrintableStatus = `Starting` | `Starting` |
| PrintableStatus = `Running` AND VMI `Paused` condition = True | `Paused` |
| PrintableStatus = `Running` | `Running` |
| PrintableStatus = `Stopping` | `Stopping` |
| PrintableStatus = `Stopped` | `Stopped` |
| PrintableStatus = `ErrorUnschedulable` | `Failed` |

> **Note:** KubeVirt does not have a transitional "Pausing" state. When a VM is paused, `PrintableStatus` remains "Running" but the VMI has a `Paused` condition set to `True`. The controller checks this condition to determine the `Paused` phase.

**Condition Semantics by Phase**

The following table shows the expected values of `Available` and `Degraded` conditions for each phase. These conditions are orthogonal to the phase - they represent the health and usability of the VM independent of its lifecycle state.

| Phase | Available | Degraded | Description |
|-------|-----------|----------|-------------|
| `Pending` | False | False | VM is being provisioned, not yet usable |
| `Starting` | False | False | VM is booting, not yet usable |
| `Running` | True | False | VM is healthy and operational |
| `Running` | True | True | VM is usable but has issues (e.g., performance degraded) |
| `Running` | False | True | VM has issues preventing normal use |
| `Stopping` | False | False | VM is shutting down |
| `Stopped` | False | False | VM is powered off |
| `Paused` | False | False | VM is paused, not usable until resumed |
| `Deleting` | False | False | VM is being deleted |
| `Failed` | False | False | VM encountered an unrecoverable error |

**Key observations:**
- `Available = True` only when phase is `Running` and the VM is usable
- `Degraded = True` indicates issues, but the VM may still be usable (`Available = True`) or not (`Available = False`)
- During transitional phases (`Starting`, `Stopping`, `Deleting`), both conditions are `False`
- In terminal states (`Stopped`, `Paused`, `Failed`), both conditions are `False`

**Files to Modify**

| Repository | File | Changes |
|------------|------|---------|
| osac-operator | `api/v1alpha1/computeinstance_types.go` | Add new phase and condition constants |
| osac-operator | `internal/controller/computeinstance_controller.go` | Update phase determination logic |
| osac-operator | `internal/controller/computeinstance_feedback_controller.go` | Update phase-to-state mapping |
| fulfillment-api | `proto/fulfillment/v1/compute_instance_type.proto` | Replace enum values |
| fulfillment-service | `proto/private/v1/compute_instance_type.proto` | Replace enum values |

**Migration Approach**

Since the product is in development with no external clients, old enum values (`PROGRESSING`, `READY`, `FAILED` for conditions) will be removed rather than deprecated. The controller will emit only the new phase and condition values.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Breaking changes for internal consumers** - UI components, scripts, or any code tied to current phase/condition values will break when values change | Coordinate with internal teams before rollout; update all consumers in the same release |
| **Developer scripts tied to old values** - Developers may have local scripts or automation that check for `Progressing`, `Ready`, or `Failed` conditions | Communicate changes clearly in release notes; provide migration guidance |
| **Incorrect phase mapping from KubeVirt** - Controller could incorrectly map KubeVirt states, showing wrong phase values | Comprehensive unit tests for phase determination logic; manual testing with real VMs in dev environment |
| **Edge cases in KubeVirt state transitions** - KubeVirt may have transitional states or error conditions not fully mapped | Review KubeVirt documentation; manual testing with various VM scenarios (create, stop, start, pause, resume, delete, error conditions) |
| **Condition logic complexity** - Determining when `Available` and `Degraded` should be True/False adds controller complexity | Document condition semantics clearly; use table-driven logic in controller for maintainability |

### Drawbacks

**Migration effort for internal consumers**

Any UI components, scripts, or automation that reference current phase/condition values will need to be updated. Since the product is in development with no external clients, this is a one-time internal effort.

**Increased state complexity**

Expanding from 4 phases to 8 phases means more states to reason about in controllers, tests, and documentation. However, the additional granularity aligns with industry standards and provides the operational visibility users expect.

**No transitional Pausing phase**

Unlike Stopping, we cannot show a "Pausing" transitional phase because KubeVirt does not expose this state - pause is instantaneous. GCE is the only major cloud provider that exposes a `SUSPENDING` transitional state; AWS and KubeVirt transition directly to the paused/stopped state. This minor inconsistency reflects the underlying platform behavior accurately.

## Alternatives (Not Implemented)

**1. Deprecate old values instead of removing them**

We could deprecate old phase/condition values and maintain them for several releases before removal.

*Why not selected:* Since the product is in development with no external clients, deprecation adds unnecessary complexity. A clean break is simpler and avoids carrying legacy values.

**2. Add a Pausing transitional phase**

We could add a `Pausing` phase to mirror the `Stopping` transitional phase.

*Why not selected:* KubeVirt does not expose a transitional "pausing" state - pause is instantaneous. Adding a phase we cannot accurately populate would be misleading.

## Open Questions [optional]

- **NetworkReady condition** - Requires networking design to be finalized before this condition can be defined
- **RestartRequired condition** - Requires configuration change detection logic to be designed

## Test Plan

- **Unit tests**: Phase determination logic in `computeinstance_controller.go` - test each KubeVirt `PrintableStatus` → ComputeInstance phase mapping
- **Unit tests**: Condition setting logic - test `Available` and `Degraded` conditions for each phase
- **Unit tests**: Feedback controller phase-to-state mapping
- **Manual testing**: Create VMs in dev environment and verify phase transitions through lifecycle operations (create, stop, start, pause, resume, delete)
- **Manual testing**: Verify error scenarios produce `Failed` phase

## Graduation Criteria

TBD

## Upgrade / Downgrade Strategy

TBD

## Version Skew Strategy

N/A

## Support Procedures

TBD

## Infrastructure Needed [optional]

N/A
