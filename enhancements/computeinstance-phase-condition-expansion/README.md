---
title: computeinstance-phase-condition-expansion
authors:
  - Akshay Nadkarni
creation-date: 2026-01-29
last-updated: 2026-04-19
tracking-link:
  - TBD
see-also:
replaces:
  - "[ComputeInstance-VM_PhasesAndConditions_Proposal (Google Doc)](https://docs.google.com/document/d/1wgqAblnT7OHlT5bvaI4bi842kyeR3u4VfC_TAJXbGcI/edit?usp=sharing)"
superseded-by:
---

# ComputeInstance Phase and Condition Expansion

## 1. Summary

This enhancement proposes a cleanup and expansion of the `ComputeInstancePhaseType` and `ComputeInstanceConditionType` values for the OSAC VMaaS offering.

The current 4-phase model (`Progressing`, `Ready`, `Failed`, `Deleting`) was designed for initial provisioning workflows. As VMaaS matures to support full lifecycle operations (start, stop, pause, resume), the phase model needs to expand to represent these power states. Additionally, the current conditions overlap with phases rather than providing orthogonal health information.

The redesign expands from 4 phases to 7 phases to properly represent the full VM lifecycle, aligning with industry standards from AWS, GCE, and KubeVirt. Conditions are redesigned to be orthogonal health indicators that complement, rather than duplicate, the lifecycle phase.

> **Note:** You can find more details on industry standards [here](https://docs.google.com/document/d/1wgqAblnT7OHlT5bvaI4bi842kyeR3u4VfC_TAJXbGcI/edit?tab=t.oocbc3frwt7c).

This change enables users to understand VM power state (running, stopped, paused), see transitional progress (starting, stopping), and receive clear health signals through conditions - providing the operational visibility expected from a modern cloud platform.

## 2. Motivation

As VMaaS matures to support full VM lifecycle operations, users need clear visibility into VM power state and operational status. The current phase model does not distinguish between a running VM and a stopped VM, and conditions overlap with phases rather than providing independent health information. This enhancement addresses these gaps to provide the operational visibility expected from a modern cloud platform.

### 2.1 User Stories

**For Tenants:**

* As a tenant, I want to see if my VM is running, stopped, or paused, so that I understand its current power state
* As a tenant, I want to see when my VM is starting or stopping, so that I know an operation is in progress
* As a tenant, I want to see status conditions for my VM, so that I can understand its readiness and configuration state
* As a tenant, I want to see when my VM is being deleted, so that I can track deletion progress and identify if resource removal fails
* As a tenant, I want to know when my VM requires a restart for configuration changes to take effect, so that I can initiate a reboot when convenient

**For Cloud Providers:**

* As a cloud provider, I want to see clear VM power states for tenant VMs, so that I can provide effective support and troubleshooting
* As a cloud provider, I want VM phases that align with industry standards, so that I can build monitoring dashboards with familiar terminology
* As a cloud provider, I want visibility into VM deletion status, so that I can troubleshoot stuck deletions and ensure resources are properly cleaned up

**For Developers:**

* As a developer, I want a phase/condition model where conditions are orthogonal to phases, so that new conditions can be added in future releases without breaking my existing integrations
* As a developer, I want a well-defined phase model that can accommodate future VM operations (e.g., live migration), so that the API can evolve to support new capabilities

### 2.2 Goals

* Represent VM power state clearly - Users can see if a VM is Running, Stopped, or Paused
* Expose transitional states - Users can see when operations are in progress (Starting, Stopping, Deleting)
* Align with industry standards - Phase values match what users expect from AWS, GCE, and KubeVirt
* Make conditions orthogonal to phases - Conditions represent health/status attributes, not lifecycle state
* Give tenants and cloud providers visibility into the deletion phase - Track deletion progress and identify issues if resource removal fails

### 2.3 Non-Goals

* Additional conditions - The Degraded condition is deferred pending further discussion (see Open Questions)
* New VM operations - This enhancement is about status representation, not adding pause/resume/stop operations themselves
* Hibernate (suspend to disk) - Only in-memory pause is supported by KubeVirt; hibernate is out of scope

## 3. Proposal

This enhancement modifies the `ComputeInstance` status model across three layers:

**1. OSAC Operator (Kubernetes CRD)**
- Expand `ComputeInstancePhaseType` from 4 phases to 7 phases
- Refactor `ComputeInstanceConditionType` to be orthogonal to phases

**2. Fulfillment API (Public protobuf)**
- Add corresponding `ComputeInstanceState` enum values
- Update `ComputeInstanceConditionType` enum to match the orthogonal design
- Remove old values (`PROGRESSING`, `READY`) since there are no external clients

**3. Fulfillment Service (Private protobuf)**
- Mirror public API changes

**Proposed Phases (7):**

| Phase | Description |
|-------|-------------|
| `Starting` | Cluster resources associated with the VM are being provisioned and prepared, or VM is being prepared for running |
| `Running` | VM is running |
| `Stopping` | VM is in the process of being stopped |
| `Stopped` | VM is stopped |
| `Paused` | VM is paused |
| `Deleting` | VM is in the process of deletion, as well as its associated resources |
| `Failed` | VM encountered an error |

**Proposed Conditions (orthogonal to phases):**

| Condition (CRD) | Condition (Protobuf) | Layer | Description |
|-----------------|---------------------|-------|-------------|
| `Provisioned` | `PROVISIONED` | CRD + API | Infrastructure resources (compute, storage) are allocated |
| `Ready` | `READY` | CRD + API | Compute instance is running and ready (readiness check has passed) |
| `ConfigurationApplied` | `CONFIGURATION_APPLIED` | CRD + API | Desired configuration matches actual |
| `RestartRequired` | `RESTART_REQUIRED` | CRD + API | VM needs a restart for configuration changes to take effect |
| `RestartInProgress` | `RESTART_IN_PROGRESS` | CRD + API | Restart operation is in progress |
| `RestartFailed` | `RESTART_FAILED` | CRD + API | Restart operation failed |

> **Note:** CRD conditions use PascalCase (Kubernetes convention). Protobuf conditions use UPPER_SNAKE_CASE with prefix (e.g., `COMPUTE_INSTANCE_CONDITION_TYPE_READY`).

The phase values are derived from the underlying KubeVirt `VirtualMachine.Status.PrintableStatus`, ensuring accurate representation of VM power state.

### 3.1 Workflow Description

**Phase Transitions**

A tenant creates a ComputeInstance and observes its lifecycle through phases:

1. **Create**: Tenant requests a new VM → Phase: `Starting`
2. **Boot completes**: VM is running → Phase: `Running`
3. **Stop requested**: Tenant stops the VM → Phase: `Stopping` → `Stopped`
4. **Start requested**: Tenant starts the VM → Phase: `Starting` → `Running`
5. **Pause requested**: Tenant pauses the VM → Phase: `Paused`
6. **Resume requested**: Tenant resumes the VM → Phase: `Running`
7. **Delete requested**: Tenant deletes the VM → Phase: `Deleting` → (resource removed)

**Restart Handling**

Restart is not a separate phase. When a tenant restarts a VM:
- Phase transitions: `Running` → `Stopping` → `Stopped` → `Starting` → `Running`
- Condition `RestartInProgress` is set to `True` throughout the operation
- On completion, `RestartInProgress` is set to `False`
- On failure, phase becomes `Failed` and condition `RestartFailed` is set to `True`

**State Transition Diagram**

```
                    ┌──────────────────────────────────────┐
                    │              (start)                 │
                    ▼                                      │
[Create] ──► Starting ──► Running ──► Stopping ──► Stopped ─┘
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

### 3.2 API Extensions

This enhancement modifies existing API types rather than adding new CRDs or webhooks.

**Modified Resources:**

| Layer | Resource | Change |
|-------|----------|--------|
| OSAC Operator | `ComputeInstance` CRD | Expand `status.phase` values, refactor `status.conditions` |
| Fulfillment API | `ComputeInstanceState` enum | Replace 4 values with 7 new phase values |
| Fulfillment API | `ComputeInstanceConditionType` enum | Keep 3 conditions, remove 4, add 3 new |
| Fulfillment Service | `ComputeInstanceState` enum | Mirror public API changes |
| Fulfillment Service | `ComputeInstanceConditionType` enum | Mirror public API changes |

**Phase Mapping (Current → Proposed):**

| Current (CRD) | Current (Protobuf) | Proposed (CRD) | Proposed (Protobuf) |
|---------------|-------------------|----------------|---------------------|
| `Progressing` | `PROGRESSING` | `Starting` | `STARTING` |
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
| `Available` | `READY` | `Ready` | `READY` | Rename CRD + protobuf to align with KubeVirt |
| `Deleting` | — | — | — | Remove (phase represents this) |
| — | `FAILED` | — | — | Remove (phase represents this) |
| — | `DEGRADED` | — | — | Remove (see Open Questions) |
| `RestartInProgress` | `RESTART_IN_PROGRESS` | `RestartInProgress` | `RESTART_IN_PROGRESS` | Keep |
| `RestartFailed` | `RESTART_FAILED` | `RestartFailed` | `RESTART_FAILED` | Keep |
| — | — | `Provisioned` | `PROVISIONED` | New |
| — | — | `ConfigurationApplied` | `CONFIGURATION_APPLIED` | New |
| — | — | `RestartRequired` | `RESTART_REQUIRED` | New |

**Behavioral Changes:**

- `ComputeInstance.status.phase` will reflect VM power state (`Running`, `Stopped`, `Paused`) rather than reconciliation status
- Conditions are orthogonal to phases - a condition like `Ready` can be True or False independent of the phase

### 3.3 Implementation Details/Notes/Constraints

**Phase Determination Logic**

The controller determines the ComputeInstance phase based on the KubeVirt `VirtualMachine.Status.PrintableStatus` and the `ComputeInstance.DeletionTimestamp`:

| Condition | ComputeInstance Phase |
|-----------|----------------------|
| `DeletionTimestamp` is set | `Deleting` |
| KubeVirt VM does not exist | `Starting` |
| PrintableStatus = `Starting` | `Starting` |
| PrintableStatus = `Running` AND VMI `Paused` condition = True | `Paused` |
| PrintableStatus = `Running` | `Running` |
| PrintableStatus = `Stopping` | `Stopping` |
| PrintableStatus = `Stopped` | `Stopped` |
| PrintableStatus = `ErrorUnschedulable` | `Failed` |

> **Note:** KubeVirt does not have a transitional "Pausing" state. When a VM is paused, `PrintableStatus` remains "Running" but the VMI has a `Paused` condition set to `True`. The controller checks this condition to determine the `Paused` phase.

**Ready Condition Logic**

The `Ready` condition (renamed from `Available` to align with the KubeVirt `VirtualMachineReady` condition it mirrors) is set to `True` when `VirtualMachine.Status.Ready = true`. The `VirtualMachine.Status.Ready` field ([VirtualMachineStatus Ready](https://github.com/kubevirt/api/blob/fe5ef708bb5c1ed6ef155c4ad9ec1e7cfcb99500/core/v1/types.go#L2074-L2075)) is derived from the `VirtualMachineInstance.Conditions[Ready]` condition ([VirtualMachineInstanceConditionType Ready](https://github.com/kubevirt/api/blob/fe5ef708bb5c1ed6ef155c4ad9ec1e7cfcb99500/core/v1/types.go#L698-L700)). KubeVirt's virt-controller syncs VMI conditions to the VM object ([see vm.go](https://github.com/kubevirt/kubevirt/pull/6575)), and the VMI Ready condition is synced from the virt-launcher pod's Ready condition.

| VirtualMachine.Status.Ready | Ready |
|----------------------------|-------|
| `true` | True |
| `false` | False |

**Timeline:** `VirtualMachine.Status.Ready` becomes `true` when `VirtualMachineInstance.Conditions[Ready] = True`, which is synced from the virt-launcher pod's Ready condition. The complete flow is:

1. **QEMU process starts** → `VirtualMachineInstance.Phase` = `Running` ([VirtualMachineInstancePhase Running](https://github.com/kubevirt/api/blob/fe5ef708bb5c1ed6ef155c4ad9ec1e7cfcb99500/core/v1/types.go#L1104-L1105))
2. **virt-launcher pod becomes ready** → Pod `Ready` condition = `True`
3. **Pod Ready condition syncs to VMI** → `VirtualMachineInstance.Conditions[Ready]` = `True` ([VirtualMachineInstanceConditionType Ready](https://github.com/kubevirt/api/blob/fe5ef708bb5c1ed6ef155c4ad9ec1e7cfcb99500/core/v1/types.go#L698-L700)) - [synced by virt-handler](https://github.com/kubevirt/kubevirt/pull/1921)
4. **VMI Ready condition syncs to VM** → `VirtualMachine.Status.Ready` = `true` ([VirtualMachineStatus Ready](https://github.com/kubevirt/api/blob/fe5ef708bb5c1ed6ef155c4ad9ec1e7cfcb99500/core/v1/types.go#L2074-L2075)) - [synced by virt-controller](https://github.com/kubevirt/kubevirt/pull/6575)
5. **ComputeInstance controller observes VM Ready** → `ComputeInstance.Conditions[Ready]` = `True`

This means `Ready = True` indicates that the VM infrastructure (virt-launcher pod ready, QEMU process running) is operational, but does not verify guest OS boot status.

> **Note:** `Ready = True` indicates VM infrastructure readiness but does not guarantee that the guest OS has fully booted or that applications inside the VM are ready to serve traffic.

**Provisioned Condition Logic**

The `Provisioned` condition indicates whether infrastructure resources (compute, storage) have been allocated for the ComputeInstance. Unlike a simple True/False toggle, the condition uses granular `Reason` and `Message` values to communicate provisioning progress:

| State | Status | Reason | Message |
|-------|--------|--------|---------|
| Initial (conditions just created) | `False` | `Initialized` | *(empty)* |
| Tenant not ready | `False` | `TenantNotReady` | `Tenant '<name>' is not ready (phase: <phase>)` |
| No KubeVirt VM yet | `False` | `WaitingForVM` | `VirtualMachine not yet created, waiting for provisioning` |
| KubeVirt `PrintableStatus` = `Provisioning` | `False` | `ProvisioningStorage` | `Creating DataVolumes for boot disk (<size>GiB)` (with optional `and <N> additional disk(s)`) |
| Infrastructure ready | `True` | `InfrastructureReady` | `All infrastructure resources provisioned successfully` |

This enables consumers to understand exactly where in the provisioning pipeline a ComputeInstance is, rather than only knowing that it is "not yet provisioned".

**Kubernetes Events**

The controller emits Kubernetes events (via `events.EventRecorder`) at key provisioning transitions. Events are only emitted when the condition reason actually changes, not on every reconcile cycle. This provides an audit trail of provisioning progress without flooding the event stream.

| Event Reason | Event Type | When |
|-------------|-----------|------|
| `TenantNotReady` | Warning | Tenant is not in Ready phase |
| `WaitingForVM` | Normal | KubeVirt VM does not yet exist |
| `ProvisioningStorage` | Normal | KubeVirt is creating DataVolumes |
| `InfrastructureReady` | Normal | All infrastructure provisioned |
| `Ready` | Normal | VM is ready (with IP address) |

**RestartRequired Condition Logic**

The `RestartRequired` condition is derived from KubeVirt's `VirtualMachine.Status.Conditions` where `type = RestartRequired`. This condition is set by KubeVirt when configuration changes (such as adding or removing resources like CPUs, memory, or devices) have been applied to the VM spec but require a restart to take effect since they can't be live-propagated to the VMI.

| KubeVirt VM Condition | RestartRequired |
|-----------------------|-----------------|
| `RestartRequired` = True | True |
| `RestartRequired` = False or absent | False |

This enables tenants to see when their VM needs a restart and decide when to initiate the reboot based on their workload needs.

**Files to Modify**

| Repository | File | Changes |
|------------|------|---------|
| osac-operator | `api/v1alpha1/computeinstance_types.go` | Add new phase and condition constants; rename `Available` to `Ready` |
| osac-operator | `api/v1alpha1/conditions.go` | Add `ConditionReady` and granular reason constants (`ReasonTenantNotReady`, `ReasonProvisioningStorage`, `ReasonWaitingForVM`, `ReasonInfrastructureReady`) |
| osac-operator | `internal/controller/computeinstance_controller.go` | Update phase determination logic; add `EventRecorder` for Kubernetes events; enhance `Provisioned` condition with granular reasons and messages |
| osac-operator | `internal/controller/computeinstance_feedback_controller.go` | Rename `syncAvailable` to `syncReady`; sync `Reason` field to fulfillment service |
| fulfillment-service | `proto/public/osac/public/v1/compute_instance_type.proto` | Rename `AVAILABLE` to `READY`; document `Provisioned` reason values |
| fulfillment-service | `proto/private/osac/private/v1/compute_instance_type.proto` | Rename `AVAILABLE` to `READY` |

**Migration Approach**

Since the product is in development with no external clients, old enum values (`PROGRESSING`, `READY`, `FAILED` for conditions) will be removed rather than deprecated. The controller will emit only the new phase and condition values.

**Wire compatibility for the Available → Ready rename:** The protobuf enum value `COMPUTE_INSTANCE_CONDITION_TYPE_AVAILABLE` is renamed to `COMPUTE_INSTANCE_CONDITION_TYPE_READY` but retains the same numeric value (2). Since protobuf stores numeric values on the wire and in the fulfillment-service database (not string names), existing stored conditions will deserialize correctly without migration.

**Stale `Available` condition on existing CRs:** After the controller is updated, it will no longer manage the old `Available` condition. Existing ComputeInstance CRs that were created before the rename may carry a stale `Available` condition in their `status.conditions` array. Since the product is in development with no production workloads, no automated cleanup is planned. The stale condition is harmless (the controller ignores it) and will be removed when the CR is deleted and recreated.

### 3.4 Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Breaking changes for internal consumers** - UI components, scripts, or any code tied to current phase/condition values will break when values change | Coordinate with internal teams before rollout; update all consumers in the same release |
| **Developer scripts tied to old values** - Developers may have local scripts or automation that check for `Progressing`, `Ready`, or `Failed` conditions | Communicate changes clearly in release notes; provide migration guidance |
| **Incorrect phase mapping from KubeVirt** - Controller could incorrectly map KubeVirt states, showing wrong phase values | Comprehensive unit tests for phase determination logic; manual testing with real VMs in dev environment |
| **Edge cases in KubeVirt state transitions** - KubeVirt may have transitional states or error conditions not fully mapped | Review KubeVirt documentation; manual testing with various VM scenarios (create, stop, start, pause, resume, delete, error conditions) |
| **Condition logic complexity** - Determining when `Ready` should be True/False adds controller complexity | Document condition semantics clearly; use table-driven logic in controller for maintainability |

### 3.5 Drawbacks

**Migration effort for internal consumers**

Any UI components, scripts, or automation that reference current phase/condition values will need to be updated. Since the product is in development with no external clients, this is a one-time internal effort.

**Increased state complexity**

Expanding from 4 phases to 7 phases means more states to reason about in controllers, tests, and documentation. However, the additional granularity aligns with industry standards and provides the operational visibility users expect.

**No transitional Pausing phase**

Unlike Stopping, we cannot show a "Pausing" transitional phase because KubeVirt does not expose this state - pause is instantaneous. GCE is the only major cloud provider that exposes a `SUSPENDING` transitional state; AWS and KubeVirt transition directly to the paused/stopped state. This minor inconsistency reflects the underlying platform behavior accurately.

## 4. Alternatives (Not Implemented)

**1. Deprecate old values instead of removing them**

We could deprecate old phase/condition values and maintain them for several releases before removal.

*Why not selected:* Since the product is in development with no external clients, deprecation adds unnecessary complexity. A clean break is simpler and avoids carrying legacy values.

**2. Add a Pausing transitional phase**

We could add a `Pausing` phase to mirror the `Stopping` transitional phase.

*Why not selected:* KubeVirt does not expose a transitional "pausing" state - pause is instantaneous. Adding a phase we cannot accurately populate would be misleading.

## 5. Open Questions

- **Should we add a Degraded condition?** The existing `DEGRADED` enum value in the API is never set. What signals from KubeVirt would indicate a VM is "degraded" (running but with issues) vs "failed" (not running)? The KubeVirt signals considered (CrashLoopBackOff, ErrorUnschedulable, etc.) mostly indicate failure rather than degradation.

- **~~Should the Available condition capture whether the guest OS is ready and accessible (e.g., user can SSH into it)?~~** **Resolved:** The condition has been renamed from `Available` to `Ready` to directly mirror the KubeVirt `VirtualMachineReady` condition. `Ready = True` indicates VM infrastructure readiness (virt-launcher pod ready, QEMU process running) and does not verify guest OS boot status.

- **~~If Available should capture guest OS readiness, which mechanism should we use?~~** **Resolved:** Since `Ready` mirrors KubeVirt's infrastructure-level readiness, guest OS readiness is out of scope for this condition. KubeVirt readiness probes could be used in the future for a separate guest-level readiness signal if needed.

## 6. Test Plan

- **Unit tests**: Phase determination logic in `computeinstance_controller.go` - test each KubeVirt `PrintableStatus` → ComputeInstance phase mapping
- **Unit tests**: Condition setting logic - test `Ready`, `Provisioned` (with granular reasons: `TenantNotReady`, `WaitingForVM`, `ProvisioningStorage`, `InfrastructureReady`), and `RestartRequired` conditions
- **Unit tests**: Verify `Provisioned` condition transitions correctly through reason values as provisioning progresses (TenantNotReady → WaitingForVM → ProvisioningStorage → InfrastructureReady)
- **Unit tests**: Feedback controller phase-to-state mapping, including `Reason` field propagation
- **Unit tests**: Verify Kubernetes events are only emitted on condition transitions, not on every reconcile cycle
- **Manual testing**: Create VMs in dev environment and verify phase transitions through lifecycle operations (create, stop, start, pause, resume, delete)
- **Manual testing**: Verify error scenarios produce `Failed` phase
- **Manual testing**: Modify VM configuration (e.g., CPU/memory) and verify `RestartRequired` condition is surfaced; reboot VM and verify condition clears
- **Manual testing**: Monitor Kubernetes events during provisioning and verify granular progress messages appear

## 7. Graduation Criteria

TBD

## 8. Upgrade / Downgrade Strategy

TBD

## 9. Version Skew Strategy

N/A

## 10. Support Procedures

TBD

## 11. Infrastructure Needed

N/A
