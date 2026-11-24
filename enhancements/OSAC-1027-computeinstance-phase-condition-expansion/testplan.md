# Test Plan — OSAC-1027 ComputeInstance phase conditions

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 7

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-PH-01: A tenant becoming ready without a VM changes the provisioning reason

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [README.md, lines 246-266](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L246-L266)
- **Dependencies:** Real envtest API server and etcd, in-process ComputeInstance controller, fixture tenant and fake AAP; no KubeVirt VM or guest.
- **Execution:** `osac-operator/internal/controller/computeinstance_controller_test.go`
- **Evidence:** `should set WaitingForVM when tenant becomes Ready without VM` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/computeinstance_controller_test.go#L3768)).
- **Selector:** Ginkgo focus `should set WaitingForVM when tenant becomes Ready without VM` in `osac-operator/internal/controller` under the operator envtest suite. Source reviewed, test not run.

**Preconditions.** Prepare the controller's tenant fixture in a non-ready phase and leave its VM absent.

1. Reconcile the fixture instance.
2. Mark the tenant Ready and reconcile again, then repeat without changes.

**Expected results.** The Provisioned reason changes from TenantNotReady to WaitingForVM and repeated reconciliation leaves the reason unchanged.

#### TC-PH-02: Printable VM status and deletion determine the ComputeInstance phase

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 204-219](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L204-L219)
- **Dependencies:** Synthetic KubeVirt status and VMI inputs; no running VM.
- **Gap:** The controller specs check individual states. No focused selector reviewed covers this complete mapping table.

**Preconditions.** Prepare a ComputeInstance and VM/VMI status fixtures.

1. Evaluate absent VM, Starting, Running, Running with Paused, Stopping, Stopped and ErrorUnschedulable.
2. Repeat a Running input with a deletion timestamp.

**Expected results.** Results are Starting, Starting, Running, Paused, Stopping, Stopped and Failed respectively. Deletion takes precedence and produces Deleting.

#### TC-PH-03: Tenant lifecycle output shows a provisioning failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 344-355](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L344-L355)
- **Dependencies:** Real deployed fulfillment, operator, AAP and KubeVirt in a disposable stack; isolated scheduling fixture.
- **Gap:** Canonical VM lifecycle suites were reviewed. No deployed case found that drives ErrorUnschedulable and verifies the resulting failure in tenant output.

**Preconditions.** Use an isolated VM fixture with an unavailable scheduling placement.

1. Create the VM through the tenant API.
2. Observe KubeVirt status and read the tenant-facing lifecycle result.

**Expected results.** KubeVirt reaches ErrorUnschedulable and the tenant-visible phase is FAILED.

#### TC-PH-04: Ready remains independent of the lifecycle phase

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 197-228](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L197-L228)
- **Dependencies:** Synthetic VM and VMI statuses; no API server.
- **Gap:** The proposal does not define a separate unknown-reason transition. No exact focused test found for the independent readiness assertion in the operator controller and feedback suites.

**Preconditions.** Prepare a Running VM fixture with infrastructure readiness initially false.

1. Project phase and Ready, then toggle only VM readiness.
2. Project phase and Ready again.

**Expected results.** The phase stays Running while Ready moves from False to True.

#### TC-PH-05: Provisioning reasons and readiness events advance only on change

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 246-266](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L246-L266)
- **Dependencies:** In-process controller inputs and recording event sink; AAP and KubeVirt states are fixtures.
- **Gap:** Operator controller specs cover individual stages; a single four-stage and event-count assertion remains unresolved.

**Preconditions.** Use a non-ready tenant, then ready tenant, then storage-provisioning VM, then ready VM with IP.

1. Evaluate each stage twice and record events.
2. Compare Provisioned reason and Ready status at every stage.

**Expected results.** Reasons progress TenantNotReady, WaitingForVM, ProvisioningStorage, InfrastructureReady. No WaitingForVM event is emitted, and each other applicable event occurs once on its documented transition.

#### TC-PH-06: Legacy Available data preserves the Ready wire contract

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 344-352](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L344-L352)
- **Dependencies:** Synthetic legacy object and public/private protobuf descriptors; no cluster.
- **Gap:** No combined legacy CR and protobuf numeric-value assertion found in operator controller and API mapping tests.

**Preconditions.** Prepare an upgraded object with stale Available and a protobuf condition encoded as numeric 2.

1. Reconcile with current Ready input.
2. Decode the fixture condition through private and public messages.

**Expected results.** Only Ready is written by the controller. Numeric 2 decodes as READY on both APIs and remains 2 on serialization.

#### TC-PH-07: RestartRequired reflects unapplied VM configuration

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 268-274](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-1027-computeinstance-phase-condition-expansion/README.md#L268-L274)
- **Dependencies:** Real deployed fulfillment, hub, AAP and KubeVirt with a running fixture VM and supported fixture InstanceTypes.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_resize_requires_restart_and_applies_new_resources` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L771)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_resize_requires_restart_and_applies_new_resources` from OSAC root. Source reviewed, test not run.

**Preconditions.** Start the suite VM at the smaller active type and confirm the current CPU and memory on its VMI.

1. Apply the supported type resize and observe RestartRequired before the observed VMI resources change.
2. Request restart, wait for a replacement running VMI and reread condition and resources.

**Expected results.** RestartRequired becomes True while existing VMI resources stay unchanged. After restart it clears and the replacement VMI reports the target CPU and memory.
