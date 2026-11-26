# Test Plan — OSAC-3254 Expose bare-metal instance NIC MAC addresses

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 15

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The current CLI displays `(none)` for absent NIC metadata. The plan checks that rendering and keeps the deployed populated-table assertion separate.

## Test Cases

#### TC-NIC-01: Metal3 HardwareData maps MACs to lowercase

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/metal3_test.go`
- **Evidence:** `TestGetHostNICs/returns lowercased MACs from HardwareData when present` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/metal3_test.go#L1113)).
- **Selector:** `go test ./internal/inventory -run '^TestGetHostNICs$/^returns_lowercased_MACs_from_HardwareData_when_present$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Seed a fake Kubernetes BMH and three mixed-case HardwareData NIC addresses.

1. Call GetHostNICs for the fixture host.
2. Compare the returned MAC sequence.

**Expected results.** The three addresses are aa:bb:cc:dd:ee:01, aa:bb:cc:dd:ee:02 and ff:00:11:22:33:44.

#### TC-NIC-02: OpenStack NIC fetch can retry a fixture authentication failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Gap:** The isolated OpenStack spec checks returned auth error, with no verified retry/recovery assertion.

**Preconditions.** Script a temporary authentication error followed by a successful response from the synthetic port backend.

1. Invoke the normal NIC fetch and observe the client’s retry behavior.
2. Read the final MACs.

**Expected results.** The client retries as designed and returns the normalized MACs.

#### TC-NIC-03: Metal3 excludes a host without usable NIC data

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/metal3_test.go`
- **Evidence:** `TestFindFreeHost/skips host when neither source has NICs` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/metal3_test.go#L725)).
- **Selector:** `go test ./internal/inventory -run '^TestFindFreeHost$/^skips_host_when_neither_source_has_NICs$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use a fake Kubernetes host with no usable NIC data in HardwareData or status.

1. Call FindFreeHost for the fixture selector.
2. Inspect selected host.

**Expected results.** No host is returned.

#### TC-NIC-04: A populated NIC cache avoids another inventory fetch

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — NIC metadata, inventory and CLI](design.md#unit-tests)
- **Dependencies:** The controller helper uses only the in-memory BMI object and mocked inventory. Its parent envtest suite starts Kubernetes and etcd.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go`
- **Evidence:** `TestControllers / skips GetHostNICs when Hardware has NICs (idempotency guard)` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go#L2148)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='skips GetHostNICs when Hardware has NICs [(]idempotency guard[)]'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use the controller suite with a BMI status containing one NIC and a recording inventory client.

1. Reconcile NIC metadata and inspect the recorded fetch count.
2. Read the fixture's NIC list.

**Expected results.** The fetch count is zero and the list still has one NIC.

#### TC-NIC-05: Hardware NICs propagate from BMH to BMI and API

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — NIC propagation and visibility](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`
- **Evidence:** `test_baremetal_instance_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py#L109)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py -k test_baremetal_instance_lifecycle` from the OSAC root using the BMaaS sanity fixtures.

**Preconditions.** Provision a dedicated Metal3 fixture with known BMH MACs.

1. Read BMH, BMI and public API NICs once available.
2. Compare normalized addresses.

**Expected results.** The API and BMI hardware entries contain the matching BMH MAC addresses.

#### TC-NIC-06: CLI describe shows the populated network interface section

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — NIC propagation and visibility](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`
- **Evidence:** `test_baremetal_instance_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py#L109)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py -k test_baremetal_instance_lifecycle` from the OSAC root using the BMaaS sanity fixtures.

**Preconditions.** Use the deployed lifecycle fixture with known MACs.

1. Describe the provisioned BMI using the tenant CLI.
2. Read the Network Interfaces section.

**Expected results.** The section is present and contains each fixture MAC.

#### TC-NIC-07: OpenStack host selection skips a portless node

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go`
- **Evidence:** `TestFindFreeHost_PortFilter/skips node with no registered ports` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go#L204)).
- **Selector:** `go test ./internal/inventory -run '^TestFindFreeHost_PortFilter$/^skips_node_with_no_registered_ports$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Stub one eligible OpenStack node whose port list is empty.

1. FindFreeHost with hostType=gpu-node.
2. Inspect host and error.

**Expected results.** The selection returns nil host with no error.

#### TC-NIC-08: OpenStack host selection skips a node when port lookup fails

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go`
- **Evidence:** `TestFindFreeHost_PortFilter/skips node when port API returns error` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go#L234)).
- **Selector:** `go test ./internal/inventory -run '^TestFindFreeHost_PortFilter$/^skips_node_when_port_API_returns_error$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Stub one eligible node and a port lookup returning ServiceUnavailable.

1. FindFreeHost for the same selector.
2. Inspect host and error.

**Expected results.** The selection returns nil host with no error.

#### TC-NIC-09: OpenStack host selection accepts a matching node with ports

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go`
- **Evidence:** `TestFindFreeHost_PortFilter/selects node with ports` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go#L171)).
- **Selector:** `go test ./internal/inventory -run '^TestFindFreeHost_PortFilter$/^selects_node_with_ports$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Stub available node-1 with matching gpu-node label and one port.

1. FindFreeHost using hostType=gpu-node.
2. Read the inventory ID.

**Expected results.** The selection returns node-1 without error.

#### TC-NIC-10: OpenStack NIC lookup queries the node and normalizes its MACs

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go`
- **Evidence:** `TestGetHostNICs_OpenStack/returns lowercased MACs from port records` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/openstack_internal_test.go#L81)).
- **Selector:** `go test ./internal/inventory -run '^TestGetHostNICs_OpenStack$/^returns_lowercased_MACs_from_port_records$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Stub two port records for test-node-uuid, including an uppercase MAC.

1. Call GetHostNICs with that ID.
2. Compare query parameter and returned addresses.

**Expected results.** The request uses the node UUID and returns two normalized addresses.

#### TC-NIC-11: Feedback clears removed NIC hardware data

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — NIC inventory and status](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** No matching assertion was verified in the public BMF, fulfillment feedback, and CLI suites at this tier.

**Preconditions.** Use a stored BMI with a nonempty NIC list and a feedback object without hardware.

1. Apply feedback and Get the private API record.
2. Inspect stored NIC fields.

**Expected results.** Previous NIC entries are absent from the saved record and response.

#### TC-NIC-12: CLI renders a placeholder when no hardware is reported

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — NIC metadata, inventory and CLI](design.md#unit-tests)
- **Dependencies:** In-process CLI formatter with a synthetic API object. No running service.
- **Execution:** `fulfillment-service/internal/cmd/cli/describe/baremetalinstance/describe_baremetalinstance_test.go`
- **Evidence:** `TestDescribeBareMetalInstance / should show (none) when Status.Hardware is nil` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/cmd/cli/describe/baremetalinstance/describe_baremetalinstance_test.go#L51)).
- **Selector:** `go test ./internal/cmd/cli/describe/baremetalinstance -run '^TestDescribeBareMetalInstance$' -ginkgo.focus='should show [(]none[)] when Status.Hardware is nil'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the formatter fixture with status present and no Hardware.

1. Render the describe view.
2. Inspect the Network Interfaces section.

**Expected results.** The section shows (none).

#### TC-NIC-13: NIC visibility follows tenant and administrator boundaries

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — NIC propagation and visibility](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Gap:** No matching assertion was verified in the public BMF, fulfillment feedback, and CLI suites at this tier.

**Preconditions.** Use two isolated synthetic tenants with separate BMI identities and the authorized infrastructure-admin role.

1. Read each tenant's own BMI and evaluate the other-tenant view and authorized admin view.

**Expected results.** Tenant visibility stays scoped to owned hardware. The authorized administrator can read the fixture hardware.

#### TC-NIC-14: Metal3 HardwareData becomes a Ready BMI NIC

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — BMF NIC controller](design.md#integration-tests)
- **Dependencies:** Real envtest API, etcd, Metal3 inventory and BMF reconciler. HardwareData is seeded, provisioning is no-op and power is controlled.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_metal3_envtest_test.go`
- **Evidence:** `TestControllers / should populate status.hardware.nics from BareMetalHost hardware inspection` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_metal3_envtest_test.go#L1021)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='should populate status.hardware.nics from BareMetalHost hardware inspection'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Create the fixture BMH and companion HardwareData with one synthetic MAC.

1. Run the Metal3 reconciliation sequence.
2. Read persisted BMI phase and NIC status.

**Expected results.** The BMI phase is Ready and the only NIC equals the HardwareData fixture MAC.

#### TC-NIC-15: Inventory failure reports the recoverable NIC condition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — BMF NIC controller](design.md#integration-tests)
- **Dependencies:** Real Kubernetes API/etcd and in-process BMF with scripted inventory; no actual provider.
- **Gap:** The controller tests assert the local error and Progressing state, plus a separate successful-population test. The reason-and-recovery sequence remains unverified.

**Preconditions.** Seed a progressing BMI whose inventory returns an injected transient read error.

1. Reconcile and inspect phase, reason and hardware.
2. Restore a valid inventory response and reconcile again.

**Expected results.** The BMI stays Progressing with Ready=False/NICMetadataUnavailable, then restores readiness with the fixture NIC.
