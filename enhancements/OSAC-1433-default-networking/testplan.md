# Test Plan — OSAC-1433 Default networking

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 16

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

## Test Cases

#### TC-DN-01: Invalid NetworkClass defaults name the invalid field

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real generated descriptors or schema fixtures. No deployed components.
- **Gap:** Fulfillment tenant and networking specs on OSAC main provide narrower fixtures. The complete ordering, readiness or contract assertion remains unverified.

**Preconditions.** Use one valid class and variants with an overly broad subnet prefix and invalid security-rule ports.

1. Run class admission separately for each input.
2. Read the field errors.

**Expected results.** The valid specimen passes. Each invalid specimen identifies the default CIDR or security-rule field.

#### TC-DN-02: An omitted BMI attachment resolves to the tenant default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — attachment and onboarding matrix](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Populates default network_attachments when omitted` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L3931)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Populates default network_attachments when omitted'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed the server’s ready tenant default subnet and group and a catalog selecting a type with fabric port data-0.

1. Create a BMI with an otherwise valid image and catalog and omit the attachments field.
2. Read the returned attachment.

**Expected results.** The sole attachment has the default subnet, default group and interface data-0.

#### TC-DN-03: Pool choice selects the lowest READY IPv4 ID with capacity

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process default-networking manager with in-memory resource servers and scripted readiness. No Kubernetes, PostgreSQL or provider.
- **Execution:** `fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go`
- **Evidence:** `TestDefaultNetworkingManager / allocates the default ExternalIP from the READY pool with the lowest ID that has capacity` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go#L389)).
- **Selector:** `go test ./internal/controllers/defaultnetworking -run '^TestDefaultNetworkingManager$' -ginkgo.focus='allocates\ the\ default\ ExternalIP\ from\ the\ READY\ pool\ with\ the\ lowest\ ID\ that\ has\ capacity'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed READY pools c, a and b with capacities 10, 0 and 1 respectively.

1. Reconcile default external allocation for tenant-a.
2. Read the created ExternalIP’s pool reference.

**Expected results.** Exactly one ExternalIP references shared pool-b.

#### TC-DN-04: Automatic VM external IP supports ingress and is reclaimed

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — automatic external access regression](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, Kubernetes, operators, AAP and Netris Fabric Manager with dedicated synthetic workloads. No provider double.
- **Execution:** `tests/e2e/networking/vmaas/test_vmaas_networking.py`
- **Evidence:** `test_12_automatic_external_ip_ingress_and_garbage_collection` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/networking/vmaas/test_vmaas_networking.py#L1743)).
- **Selector:** `uv run pytest -n 0 tests/e2e/networking/vmaas/test_vmaas_networking.py` from the OSAC root. Run the ordered file with its setup/cleanup cases and inspect `test_12_automatic_external_ip_ingress_and_garbage_collection`.

**Preconditions.** Use the ordered Netris VM suite with a test pool and explicit fixture network.

1. Create the VM with automatic external IP.
2. Wait for its ingress check and delete the VM.

**Expected results.** The allocated address is in the test pool, ingress reaches the workload, and the automatic address is collected on deletion.

#### TC-DN-05: Workload without a network choice uses its tenant defaults

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — workloads can omit network selection](design.md#graduation-criteria)
- **Dependencies:** Real deployed fulfillment, Kubernetes, workload provisioner, AAP and Fabric Manager; no provider double.
- **Gap:** The stretched BMI/VM case chooses an explicit subnet and the automatic ingress case supplies a network fixture. Neither shows an omitted selection resolving through deployed defaults.

**Preconditions.** Use a dedicated ready tenant, prepared default networking and an approved test workload fixture.

1. Create the workload with no network selection.
2. Compare its resolved subnet and ready connectivity with the existing tenant defaults.

**Expected results.** The workload receives an address from the existing default subnet and its isolated fixture path becomes reachable.

#### TC-DN-06: Enabled onboarding creates labeled defaults in dependency order

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process tenant reconciliation and PostgreSQL. Stub manager readiness and record controller operations. No deployed workload.
- **Gap:** Fulfillment tenant and networking specs on OSAC main provide narrower fixtures. The complete ordering, readiness or contract assertion remains unverified.

**Preconditions.** Enable provider networking. Use a synthetic Tenant, READY class and pool, and capture writes as dependencies become READY.

1. Reconcile for each prerequisite transition.
2. Read resource labels, references and the final Tenant condition.

**Expected results.** VN precedes Subnet and SecurityGroup, the ExternalIP precedes NATGateway, and each default has its expected label/name. AllResourcesReady appears only after all are ready.

#### TC-DN-07: Disabled onboarding omits external defaults but keeps readiness gates

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process tenant reconciliation and PostgreSQL. Stub manager readiness and record controller operations. No deployed workload.
- **Gap:** Fulfillment tenant and networking specs on OSAC main provide narrower fixtures. The complete ordering, readiness or contract assertion remains unverified.

**Preconditions.** Disable provider networking and create a fixture Tenant whose local defaults are initially unready.

1. Observe Tenant readiness before and after local defaults finish.
2. List all five resource kinds and issue a normal workload create using defaults.

**Expected results.** No ExternalIP or NATGateway exists. Readiness remains gated until local prerequisites succeed, then True/ProvisioningDisabled is observable.

#### TC-DN-08: Tenant deletion releases dependencies before removing the record

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process tenant reconciliation and PostgreSQL. Stub manager readiness and record controller operations. No deployed workload.
- **Gap:** Fulfillment tenant and networking specs on OSAC main provide narrower fixtures. The complete ordering, readiness or contract assertion remains unverified.

**Preconditions.** Give a synthetic Tenant all five ready defaults. Hold one NAT delete result pending.

1. Delete Tenant and inspect the condition, subsequent normal Create response and delete sequence.
2. Release the pending result and finish cleanup.

**Expected results.** Tenant stays DELETING with reason Deleting and new Create fails FailedPrecondition. NATGateway precedes ExternalIP, Subnet and group precede VN, and Tenant disappears last.

#### TC-DN-09: Pending and failed defaults report distinct readiness reasons

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process tenant reconciliation and PostgreSQL. Stub manager readiness and record controller operations. No deployed workload.
- **Gap:** Fulfillment tenant and networking specs on OSAC main provide narrower fixtures. The complete ordering, readiness or contract assertion remains unverified.

**Preconditions.** Use separate fixtures with a missing READY class/pool, a failed Subnet and a correctable failed SecurityGroup.

1. Reconcile the pending fixture then signal readiness.
2. Reconcile failures and repair the SecurityGroup through Update.

**Expected results.** Pending reports ResourcesPending; the failed Subnet reports ResourceFailed. Repairing the last failed SecurityGroup makes readiness true.

#### TC-DN-10: Missing READY IPv4 pool leaves allocation pending

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process default-networking manager with in-memory resource servers and scripted readiness. No Kubernetes, PostgreSQL or provider.
- **Execution:** `fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go`
- **Evidence:** `TestDefaultNetworkingManager / waits without failing when there is no READY IPv4 pool` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go#L404)).
- **Selector:** `go test ./internal/controllers/defaultnetworking -run '^TestDefaultNetworkingManager$' -ginkgo.focus='waits\ without\ failing\ when\ there\ is\ no\ READY\ IPv4\ pool'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed a READY IPv6 pool with free capacity but no IPv4 pool.

1. Reconcile the fixture.
2. Read the error and created resource counts.

**Expected results.** The manager returns ErrNoReadyPool, creates no ExternalIP, and still creates the default VN.

#### TC-DN-11: A full READY IPv4 pool is reported as exhausted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process default-networking manager with in-memory resource servers and scripted readiness. No Kubernetes, PostgreSQL or provider.
- **Execution:** `fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go`
- **Evidence:** `TestDefaultNetworkingManager / fails when every READY pool is full` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go#L426)).
- **Selector:** `go test ./internal/controllers/defaultnetworking -run '^TestDefaultNetworkingManager$' -ginkgo.focus='fails\ when\ every\ READY\ pool\ is\ full'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed shared READY pool-a with zero available addresses.

1. Reconcile the fixture.
2. Read the exception and ExternalIP count.

**Expected results.** The manager returns ErrNoPoolCapacity and creates no ExternalIP.

#### TC-DN-12: Default-manager creation respects dependency readiness

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process default-networking manager with in-memory resource servers and scripted readiness. No Kubernetes, PostgreSQL or provider.
- **Execution:** `fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go`
- **Evidence:** `TestDefaultNetworkingManager / creates the resources in dependency order across repeated Ensure calls` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go#L295)).
- **Selector:** `go test ./internal/controllers/defaultnetworking -run '^TestDefaultNetworkingManager$' -ginkgo.focus='creates\ the\ resources\ in\ dependency\ order\ across\ repeated\ Ensure\ calls'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a ready NetworkClass, recording in-memory servers and unready VN and ExternalIP fixtures.

1. Run Ensure as VN is created, FAILED, then READY. Finally mark the ExternalIP ALLOCATED and repeat Ensure.

**Expected results.** VN and default-nat are created first. Subnet and group appear only once VN is READY; NATGateway appears once the IP is ALLOCATED. Repeated calls create no duplicates.

#### TC-DN-13: Disabled default manager creates local defaults only

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real in-process default-networking manager with in-memory resource servers and scripted readiness. No Kubernetes, PostgreSQL or provider.
- **Execution:** `fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go`
- **Evidence:** `TestDefaultNetworkingManager / creates no ExternalIP and no NATGateway when provider networking is disabled` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/defaultnetworking/default_networking_manager_test.go#L435)).
- **Selector:** `go test ./internal/controllers/defaultnetworking -run '^TestDefaultNetworkingManager$' -ginkgo.focus='creates\ no\ ExternalIP\ and\ no\ NATGateway\ when\ provider\ networking\ is\ disabled'` from `fulfillment-service` in OSAC.

**Preconditions.** Configure the manager with provisioning disabled and an IPv4 fixture class.

1. Run Ensure and mark the VN READY.
2. Run Ensure again and count created kinds.

**Expected results.** One Subnet and one SecurityGroup are created. ExternalIP and NATGateway counts stay zero.

#### TC-DN-14: An empty BMI attachment list resolves to tenant defaults

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — attachment and onboarding matrix](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Populates default network_attachments when the list is empty` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L4020)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Populates default network_attachments when the list is empty'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the ready tenant default fixture and an otherwise valid BMI request containing an explicitly empty list.

1. Call private Create.
2. Read the effective network attachment.

**Expected results.** One attachment has the default subnet and security group and interface data-0.

#### TC-DN-15: A subnet-only BMI attachment resolves its other fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — attachment and onboarding matrix](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Fills default security group when subnet is on the default VirtualNetwork` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L4069)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Fills default security group when subnet is on the default VirtualNetwork'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a ready explicit subnet on the tenant default VN and leave security groups and interface unset.

1. Create the BMI.
2. Inspect the projected attachment.

**Expected results.** The explicit subnet is retained, the tenant default group is selected and the interface is data-0.

#### TC-DN-16: A complete BMI attachment preserves its explicit values

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — attachment and onboarding matrix](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Does not overwrite fully specified network_attachments` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L4097)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Does not overwrite fully specified network_attachments'` from `fulfillment-service` in OSAC.

**Preconditions.** Supply the fixture explicit subnet and group and select data-1.

1. Create the BMI and read the effective spec.

**Expected results.** The sole attachment retains the explicit subnet, its group and data-1.
