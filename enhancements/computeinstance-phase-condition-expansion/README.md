---
title: neat-enhancement-idea
authors:
  - TBD
creation-date: yyyy-mm-dd
last-updated: yyyy-mm-dd
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
  - TBD
see-also:
  - "/enhancements/this-other-neat-thing"
replaces:
  - "/enhancements/that-less-than-great-idea"
superseded-by:
  - "/enhancements/our-past-effort"
---

To get started with this template:``
1. **Create a directory.** Create the directory for your enhancement proposal.
1. **Make a copy of this template.** Copy this template into the directory for
   the proposal as `README.md`.
1. **Fill out the metadata at the top.** The embedded YAML document is
   checked by the linter.
1. **Fill out the "overview" sections.** This includes the Summary and
   Motivation sections. These should be easy and explain why the community
   should desire this enhancement.
1. **Create a PR.** Assign it to folks with expertise in that domain to help
   sponsor the process.
1. **Merge after reaching consensus.** Merge when there is consensus
   that the design is complete and all reviewer questions have been
   answered so that work can begin.  Come back and update the document
   if important details (API field names, workflow, etc.) change
   during code review.
1. **Keep all required headers.** If a section does not apply to an
   enhancement, explain why but do not remove the section. This part
   of the process is enforced by the linter CI job.

See ../README.md for background behind these instructions.

Start by filling out the header with the metadata for this enhancement.

# Neat Enhancement Idea

This is the title of the enhancement. Keep it simple and descriptive. A good
title can help communicate what the enhancement is and should be considered as
part of any review.

The YAML `title` should be lowercased and spaces/punctuation should be
replaced with `-`.

The `Metadata` section above is intended to support the creation of tooling
around the enhancement process.

## Summary

This enhancement proposes a cleanup and expansion of the `ComputeInstancePhaseType` and `ComputeInstanceConditionType` values for the OSAC VMaaS offering.

The current 4-phase model (`Progressing`, `Ready`, `Failed`, `Deleting`) was designed for initial provisioning workflows. As VMaaS matures to support full lifecycle operations (stop, start, pause, resume), the phase model needs to expand to represent these power states. Additionally, the current conditions overlap with phases rather than providing orthogonal health information, and there are inconsistencies between the public and private APIs that need to be addressed.

The redesign expands from 4 phases to 9 phases to properly represent the full VM lifecycle, aligning with industry standards from AWS, GCE, and KubeVirt. Conditions are redesigned to be orthogonal health indicators that complement, rather than duplicate, the lifecycle phase.

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

* As a developer integrating with the OSAC API, I want consistent terminology (RESTART vs REBOOT), so that I don't have to handle inconsistencies between public and private APIs
* As a developer, I want a phase/condition model where conditions are orthogonal to phases, so that new conditions can be added in future releases without breaking my existing integrations
* As a developer, I want a well-defined phase model that can accommodate future VM operations (e.g., live migration), so that the API can evolve to support new capabilities

### Goals

* Represent VM power state clearly - Users can see if a VM is Running, Stopped, or Paused
* Expose transitional states - Users can see when operations are in progress (Starting, Stopping, Pausing, Deleting)
* Align with industry standards - Phase values match what users expect from AWS, GCE, and KubeVirt
* Make conditions orthogonal to phases - Conditions represent health/status attributes, not lifecycle state
* Fix API inconsistencies - Unify RESTART/REBOOT terminology between public and private APIs
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
- Fix RESTART/REBOOT terminology inconsistency

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

| Condition | Description |
|-----------|-------------|
| `Provisioned` | Infrastructure resources (compute, storage) are allocated |
| `Available` | VM is ready for user workloads |
| `Degraded` | VM is running but with reduced capability |
| `ConfigurationApplied` | Desired configuration matches actual |
| `RestartInProgress` | Restart operation is in progress |
| `RestartFailed` | Restart operation failed |

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
- Condition `RestartInProgress` is set to `True` throughout the operation
- On completion, `RestartInProgress` is set to `False`
- On failure, phase becomes `Failed` and condition `RestartFailed` is set to `True`

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
| Fulfillment Service | `ComputeInstanceConditionType` enum | Mirror public API, rename REBOOT_* to RESTART_* |

**Condition Changes:**

| Condition | Action | Notes |
|-----------|--------|-------|
| `DEGRADED` | Keep | No changes |
| `RESTART_IN_PROGRESS` | Keep | Private API: rename from REBOOT_IN_PROGRESS |
| `RESTART_FAILED` | Keep | Private API: rename from REBOOT_FAILED |
| `PROGRESSING` | Remove | Phase now represents this |
| `READY` | Remove | Replaced by `Available` |
| `FAILED` | Remove | Phase now represents this |
| `Provisioned` | New | Infrastructure resources are allocated |
| `Available` | New | VM is ready for user workloads |
| `ConfigurationApplied` | New | Desired configuration matches actual |

**Behavioral Changes:**

- `ComputeInstance.status.phase` will reflect VM power state (Running, Stopped, Paused) rather than reconciliation status
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
| fulfillment-service | `proto/private/v1/compute_instance_type.proto` | Replace enum values, rename REBOOT to RESTART |

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

Similar to the `Drawbacks` section the `Alternatives` section is used
to highlight and record other possible approaches to delivering the
value proposed by an enhancement, including especially information
about why the alternative was not selected.

## Open Questions [optional]

This is where to call out areas of the design that require closure before deciding
to implement the design.  For instance,
 > 1. This requires exposing previously private resources which contain sensitive
  information.  Can we do this?

## Test Plan

**Note:** *Section not required until targeted at a release.*

Consider the following in developing a test plan for this enhancement:
- Will there be e2e and integration tests, in addition to unit tests?
- How will it be tested in isolation vs with other components?
- What additional testing is necessary to support managed OpenShift service-based offerings?

No need to outline all of the test cases, just the general strategy. Anything
that would count as tricky in the implementation and anything particularly
challenging to test should be called out.

All code is expected to have adequate tests (eventually with coverage
expectations).

## Graduation Criteria

**Note:** *Section not required until targeted at a release.*

Define graduation milestones.

These may be defined in terms of API maturity, or as something else. Initial proposal
should keep this high-level with a focus on what signals will be looked at to
determine graduation.

Consider the following in developing the graduation criteria for this
enhancement:

- Maturity levels
  - [`alpha`, `beta`, `stable` in upstream Kubernetes][maturity-levels]
  - `Dev Preview`, `Tech Preview`, `GA` in OpenShift
- [Deprecation policy][deprecation-policy]

Clearly define what graduation means by either linking to the [API doc definition](https://kubernetes.io/docs/concepts/overview/kubernetes-api/#api-versioning),
or by redefining what graduation means.

In general, we try to use the same stages (alpha, beta, GA), regardless how the functionality is accessed.

[maturity-levels]: https://git.k8s.io/community/contributors/devel/sig-architecture/api_changes.md#alpha-beta-and-stable-versions
[deprecation-policy]: https://kubernetes.io/docs/reference/using-api/deprecation-policy/

**If this is a user facing change requiring new or updated documentation in [openshift-docs](https://github.com/openshift/openshift-docs/),
please be sure to include in the graduation criteria.**

**Examples**: These are generalized examples to consider, in addition
to the aforementioned [maturity levels][maturity-levels].

### Removing a deprecated feature

- Announce deprecation and support policy of the existing feature
- Deprecate the feature

## Upgrade / Downgrade Strategy

If applicable, how will the component be upgraded and downgraded? Make sure this
is in the test plan.

Consider the following in developing an upgrade/downgrade strategy for this
enhancement:
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to keep previous behavior?
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to make use of the enhancement?

Upgrade expectations:
- Each component should remain available for user requests and
  workloads during upgrades. Ensure the components leverage best practices in handling [voluntary
  disruption](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/). Any exception to
  this should be identified and discussed here.
- Micro version upgrades - users should be able to skip forward versions within a
  minor release stream without being required to pass through intermediate
  versions - i.e. `x.y.N->x.y.N+2` should work without requiring `x.y.N->x.y.N+1`
  as an intermediate step.
- Minor version upgrades - you only need to support `x.N->x.N+1` upgrade
  steps. So, for example, it is acceptable to require a user running 4.3 to
  upgrade to 4.5 with a `4.3->4.4` step followed by a `4.4->4.5` step.
- While an upgrade is in progress, new component versions should
  continue to operate correctly in concert with older component
  versions (aka "version skew"). For example, if a node is down, and
  an operator is rolling out a daemonset, the old and new daemonset
  pods must continue to work correctly even while the cluster remains
  in this partially upgraded state for some time.

Downgrade expectations:
- If an `N->N+1` upgrade fails mid-way through, or if the `N+1` cluster is
  misbehaving, it should be possible for the user to rollback to `N`. It is
  acceptable to require some documented manual steps in order to fully restore
  the downgraded cluster to its previous state. Examples of acceptable steps
  include:
  - Deleting any CVO-managed resources added by the new version. The
    CVO does not currently delete resources that no longer exist in
    the target version.

## Version Skew Strategy

How will the component handle version skew with other components?
What are the guarantees? Make sure this is in the test plan.

Consider the following in developing a version skew strategy for this
enhancement:
- During an upgrade, we will always have skew among components, how will this impact your work?
- Does this enhancement involve coordinating behavior in the control plane and
  in the kubelet? How does an n-2 kubelet without this feature available behave
  when this feature is used?
- Will any other components on the node change? For example, changes to CSI, CRI
  or CNI may require updating that component before the kubelet.

## Support Procedures

Describe how to
- detect the failure modes in a support situation, describe possible symptoms (events, metrics,
  alerts, which log output in which component)

  Examples:
  - If the webhook is not running, kube-apiserver logs will show errors like "failed to call admission webhook xyz".
  - Operator X will degrade with message "Failed to launch webhook server" and reason "WehhookServerFailed".
  - The metric `webhook_admission_duration_seconds("openpolicyagent-admission", "mutating", "put", "false")`
    will show >1s latency and alert `WebhookAdmissionLatencyHigh` will fire.

- disable the API extension (e.g. remove MutatingWebhookConfiguration `xyz`, remove APIService `foo`)

  - What consequences does it have on the cluster health?

    Examples:
    - Garbage collection in kube-controller-manager will stop working.
    - Quota will be wrongly computed.
    - Disabling/removing the CRD is not possible without removing the CR instances. Customer will lose data.
      Disabling the conversion webhook will break garbage collection.

  - What consequences does it have on existing, running workloads?

    Examples:
    - New namespaces won't get the finalizer "xyz" and hence might leak resource X
      when deleted.
    - SDN pod-to-pod routing will stop updating, potentially breaking pod-to-pod
      communication after some minutes.

  - What consequences does it have for newly created workloads?

    Examples:
    - New pods in namespace with Istio support will not get sidecars injected, breaking
      their networking.

- Does functionality fail gracefully and will work resume when re-enabled without risking
  consistency?

  Examples:
  - The mutating admission webhook "xyz" has FailPolicy=Ignore and hence
    will not block the creation or updates on objects when it fails. When the
    webhook comes back online, there is a controller reconciling all objects, applying
    labels that were not applied during admission webhook downtime.
  - Namespaces deletion will not delete all objects in etcd, leading to zombie
    objects when another namespace with the same name is created.

## Infrastructure Needed [optional]

Use this section if you need things from the project. Examples include a new
subproject, repos requested, github details, and/or testing infrastructure.
