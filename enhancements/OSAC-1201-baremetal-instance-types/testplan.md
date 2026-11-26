# Test Plan — OSAC-1201 BareMetal instance types

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 11

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

## Test Cases

#### TC-BIT-01: Private type description changes without replacing hardware

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — instance type API and host selection](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instance_types_server_test.go`
- **Evidence:** `TestServers / Private bare metal instance types server / Update object` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instance_types_server_test.go#L359)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instance types server.*Update object$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create the shared fixture type with eight cores, 32 GB and a valid port.

1. Update only spec.description using the documented mask.
2. Read the description and hardware.

**Expected results.** The response reports Updated description and retains eight cores and 32 GB.

#### TC-BIT-02: Malformed hardware values fail validation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real generated descriptors or schema fixtures. No deployed components.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Use a valid generated hardware fixture and variants missing required capacity or with invalid numeric values.

1. Validate each type.
2. Read the field paths.

**Expected results.** Valid hardware passes. Invalid inputs identify the precise hardware field and fail admission.

#### TC-BIT-03: Metal3 inventory picks a host matching the selector

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Fake Kubernetes client and BMH fixtures; no running Kubernetes control plane or Metal3 provider.
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/metal3_test.go`
- **Evidence:** `TestFindFreeHost/filters by host type label` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/metal3_test.go#L537)).
- **Selector:** `go test ./internal/inventory -run '^TestFindFreeHost$/^filters_by_host_type_label$'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use the in-memory Metal3 fixture with different host-type labels.

1. Call FindFreeHost for a supported fixture label.
2. Compare the returned host type label.

**Expected results.** The returned host is non-nil with HostType=gpu-node.

#### TC-BIT-04: Host selection records success and failure conditions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. No real host is manipulated in this fixture.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Use BMF with synthetic inventory responses containing one matching host or no matching host.

1. Reconcile each BMI and read conditions and ownership.

**Expected results.** The selected host is recorded with HostSelectionSucceeded; the empty result records HostSelectionFailed without claiming a host.

#### TC-BIT-05: Missing instance type reference is rejected at Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects a reference to a missing instance type` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L578)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ a\ reference\ to\ a\ missing\ instance\ type$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid image and published catalog item; refer to shared type ID does-not-exist.

1. Call private BMI Create.
2. Read the status and list by the fixture name.

**Expected results.** InvalidArgument names the missing type and no fixture row exists.

#### TC-BIT-06: A type without matching inventory leaves hosts unclaimed

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. No real host is manipulated in this fixture.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Create a type for one label and seed a provisioner with otherwise eligible hosts having another label.

1. Create a BMI with this type.
2. Compare its condition and all initial host claims.

**Expected results.** The BMI reports no eligible match and the existing hosts remain unclaimed.

#### TC-BIT-07: A real label assignment determines the claimed host

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Label two isolated test hosts with different hardware profiles; create one matching shared type.

1. Provision through the tenant BMI API.
2. Read the claimed host and verify its inventory label, then clean up.

**Expected results.** The claimed host has the selected label, the nonmatching host is unclaimed and teardown releases the matching fixture.

#### TC-BIT-08: UI and CLI list and select the same instance type

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real browser, UI proxy, tenant auth, CLI, fulfillment, BMF and fixture hosts; no service doubles.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Seed two visible fixture types in an isolated tenant and provide a published BMI catalog item.

1. List types from the browser and CLI; select the same fixture type in each entry point.
2. Compare submitted IDs and clean up.

**Expected results.** Both clients present the allowed type and created BMIs resolve to the selected ID.

#### TC-BIT-09: Concurrent different-label requests claim different matching hosts

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Gap:** The public Type API, BMF integration and deployed BMaaS test sources do not establish this complete assertion. The seeded fake Metal3 integration does not verify this label matrix against a real provider.

**Preconditions.** Use two types and two dedicated hosts with disjoint matching labels.

1. Submit the two tenant BMI creates concurrently.
2. Observe both host assignments and clean up.

**Expected results.** Each BMI claims its matching host; neither host backs both instances.

#### TC-BIT-10: Public type Get and List omit private Fabric bindings

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — instance type API and host selection](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instance_types_server_test.go`
- **Evidence:** `TestServers / Private bare metal instance types server / hides bindings in public get and list responses` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instance_types_server_test.go#L184)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instance types server.*hides bindings in public get and list responses$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create one shared fixture type with private Fabric mapping and a description.

1. Get and List via the public server and inspect the serialized replies.

**Expected results.** The only listed type and the Get object preserve the description and expose neither the private binding nor its fixture class ID.

#### TC-BIT-11: Public/private type lifecycle respects selector projection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — instance type API and host selection](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Gap:** Public tests establish Fabric binding projection and individual CRUD methods. No complete dual-API lifecycle assertion was found for the private host selector.

**Preconditions.** Use an isolated fixture type with private host selector and valid hardware.

1. Create and update as provider administrator, then read the type through the tenant's public Get and List.
2. Delete when unused and verify subsequent absence.

**Expected results.** The tenant sees the same resource ID and public description without the private selector. Deleted type disappears from both views.
