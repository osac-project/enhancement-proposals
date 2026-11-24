# Test Plan — OSAC-1437 BMaaS networking

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 23

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

Current proposals main clarifies persisted lease timing and tenant versus administrator messaging, corrects the hardware port field, and adds the UI interface selection. The original PR head stays the document baseline for unchanged contracts. The newer [manager conformance design](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md) clarifies that the suite core ships without provider task or profile tests.

## Test Cases

#### TC-BN-01: Deployed controllers coordinate NetworkAttachment apply, lease and delete jobs

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The operator envtest proves narrower job ordering with injected outcomes. The combined Kind BMF and operator lifecycle is unverified.

**Preconditions.** Enable provider networking in an isolated Kind fixture and seed a BMI, subnet and eligible fake host.

1. Provision the fixture, observe attachment jobs and the OFF/ON handoff, then wait for the lease.
2. Delete the BMI and inspect the delete job before host release.

**Expected results.** Apply completes before handoff, lease query starts after handoff, and the recorded delete job completes before the host is released.

#### TC-BN-02: Two provisioned BMIs on one subnet can reach each other

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — BMaaS connectivity](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, Kubernetes, operators, AAP and Netris Fabric Manager with dedicated synthetic workloads. No provider double.
- **Execution:** `tests/e2e/networking/bmaas/test_bmaas_networking.py`
- **Evidence:** `test_07_l3_ping_same_subnet` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/networking/bmaas/test_bmaas_networking.py#L361)).
- **Selector:** `uv run pytest -n 0 tests/e2e/networking/bmaas/test_bmaas_networking.py` from the OSAC root. Run the ordered file with its setup/cleanup cases and inspect `test_07_l3_ping_same_subnet`.

**Preconditions.** Use the ordered BMaaS Netris suite with two Ready fixture BMIs on the same subnet.

1. Read the suite's assigned tenant addresses.
2. Observe its L3 probe from the first guest to the second.

**Expected results.** The probe succeeds within the suite retry window.

#### TC-BN-03: External IP attachment respects tenant ownership

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** Own-tenant allocation and retry assertions in BMaaS and visibility checks in UI E2E do not establish this API authorization boundary.

**Preconditions.** Seed tenant-owned synthetic endpoints and addresses for two test tenants.

1. Exercise ordinary same-tenant attachment in an isolated harness.
2. Inspect the cross-tenant authorization outcome and persisted fixture state.

**Expected results.** Only the owner can attach its address. A denied request leaves address and endpoint state unchanged.

#### TC-BN-04: Tenant guest traffic remains isolated

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — tenant isolation](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, Kubernetes, operators, AAP and Netris Fabric Manager with dedicated synthetic workloads. No provider double.
- **Execution:** `tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py`
- **Evidence:** `test_05_cross_tenant_isolation` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py#L587)).
- **Selector:** `uv run pytest -n 0 tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py` from the OSAC root. Run the ordered file with its setup/cleanup cases and inspect `test_05_cross_tenant_isolation`.

**Preconditions.** Use the ordered Netris suite with two isolated synthetic tenants with one provisioned BMI per tenant.

1. Observe each BMI reaching its own subnet gateway.
2. Observe both directions of the suite's cross-tenant isolation assertion.

**Expected results.** Each BMI reaches its own gateway, and both cross-tenant reachability checks fail.

#### TC-BN-05: A CaaS worker BMI uses its authorized shared subnet

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, Kubernetes, operators, AAP and Netris Fabric Manager with dedicated synthetic workloads. No provider double.
- **Gap:** OSAC-5688 owns worker lifecycle. The deployed shared VM/BMI suite does not exercise a CaaS worker.

**Preconditions.** Use a disposable CaaS cluster and synthetic worker and workload sharing the authorized subnet.

1. Wait for worker registration and read its tenant address.
2. Compare it with the shared subnet and remove the fixture.

**Expected results.** The worker registers with an address on the authorized shared subnet and removes its own attachment on teardown.

#### TC-BN-06: Apply precedes the lease query and failed retryable queries requeue

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Execution:** `osac-operator/internal/controller/networking_attachments_test.go`
- **Evidence:** `TestControllers / applies a bare-metal attachment on the Fabric, then queries the DHCP lease after the handoff` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/networking_attachments_test.go#L650)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='applies\ a\ bare\-metal\ attachment\ on\ the\ Fabric,\ then\ queries\ the\ DHCP\ lease\ after\ the\ handoff'` from `osac-operator` in OSAC.

**Preconditions.** Seed a ready subnet and a BMI with physical interface data in the operator harness.

1. Reconcile and mark apply succeeded.
2. Mark handoff complete, reconcile again and return a retryable lease result.

**Expected results.** Before handoff only Fabric apply is recorded. Afterwards query is recorded, requeues in 30 seconds and leaves DHCPLease unset.

#### TC-BN-07: Owner allocation can retry and release the same address

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real deployed fulfillment, Kubernetes, operators, AAP and Netris Fabric Manager with dedicated synthetic workloads. No provider double.
- **Execution:** `tests/e2e/networking/bmaas/test_external_ip_ownership.py`
- **Evidence:** `test_bmaas_netris_allocation_retry_and_release` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/networking/bmaas/test_external_ip_ownership.py#L32)).
- **Selector:** `uv run pytest -n 0 tests/e2e/networking/bmaas/test_external_ip_ownership.py -k test_bmaas_netris_allocation_retry_and_release` from the OSAC root.

**Preconditions.** Use a dedicated fixture pool and an independently resolved tenant identity.

1. Allocate through the tenant ExternalIP API and observe the recorded job.
2. Observe the controlled controller retry in the fixture, then delete the address through the tenant API.

**Expected results.** Tenant matches the fixture identity. Retry keeps address and UID and advances job attempt without another allocation; deletion restores pool capacity.

#### TC-BN-08: BMI Create rejects more than one attachment

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BareMetalInstance attachment admission](design.md#network-attachment-and-validation)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Rejects multiple attachments` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L2635)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Rejects multiple attachments'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid image, catalog and two synthetic attachments for the private BMI server.

1. Call Create with both attachments.
2. Inspect the status and diagnostic.

**Expected results.** InvalidArgument reports the single-attachment limit.

#### TC-BN-09: Worker authorization requires an owning Cluster and authorized network

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — worker authorization](design.md#caas-workers)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Use synthetic worker and Cluster ownership fixtures with authorized network and port.

1. Evaluate the valid worker fixture and separate missing, unresolvable, wrong-tenant and unauthorized-network fixtures.
2. Read admission state and lookup results.

**Expected results.** Only the valid worker is accepted with the authorized fabric interface, without writes for denied fixtures.

#### TC-BN-10: BMI endpoints must be ready before ExternalIP attachment

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — readiness and delete guards](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go`
- **Evidence:** `TestServers / Rejects non-ready BareMetalInstance targets without persisting attachments` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_external_ip_attachments_server_test.go#L894)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Rejects non-ready BareMetalInstance targets without persisting attachments'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed one allocated test address and independent BMI fixtures that are starting, lack a network address, or are deleting.

1. Call the ordinary ExternalIPAttachment Create for each fixture.
2. Inspect the result and persisted attachment set.

**Expected results.** Each returns FailedPrecondition and leaves the attachment list empty.

#### TC-BN-11: Handoff reuses its persisted deadline across restart

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Current design — Create](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/design.md#create) and [PRD — NFR-2](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/prd.md#4-requirements)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Use a scripted BMF clock and a BMI with persisted NetworkAttachmentsReady transition time.

1. Return pending observations, restart the controller and advance beyond 15 minutes.
2. Repeat with successful terminal observation at the first late reconcile.

**Expected results.** The incomplete cycle fails with NetworkHandoffFailed against the original timestamp. Observed completion wins when present on that reconcile.

#### TC-BN-12: Lease timeout persists and exposes role-appropriate messages

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Current design — Create](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/design.md#create) and [PRD — NFR-2](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/prd.md#4-requirements)
- **Dependencies:** Real BMF, osac-operator, Kind Kubernetes and the tenant-facing fulfillment API, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Seed a persisted NetworkHandoffComplete transition and scripted retryable no-lease results.

1. Restart at nine minutes, reconcile beyond ten and read administrator and tenant status.
2. Return an accepted lease and reconcile again.

**Expected results.** An administrator sees LeaseNotFound in LeasePending, the tenant sees “IP address discovery is in progress.” and retry continues. Accepted lease sets IPDiscovered/NETWORK_READY and clears the pending message.

#### TC-BN-13: Selected port uses inventory MAC after assignment

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Seed two label-eligible hosts and a synthetic selected fabric port; one has an invalid or absent selected-port MAC.

1. Assign a host using the type selector, then resolve the chosen port in separate fixtures.
2. Inspect attachment or failure state and release.

**Expected results.** Selection does not prefilter by MAC. A valid MAC is normalized and recorded with inventory host name; invalid data yields SelectedPortMACUnavailable and releases the host.

#### TC-BN-14: Deletion serializes power-off and attachment cleanup

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — ordered teardown](design.md#delete)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Use scripted power observations, one in-flight attachment creation and an unrelated attachment in the same fixture namespace.

1. Start deletion during pending creation/ON. Observe lookup, finalizers and host assignment until OFF is verified.
2. Complete Fabric delete and read inventories.

**Expected results.** Finalizers and ownership persist while unsettled, offboard waits for observed OFF, only the owned attachment disappears, then the host is released.

#### TC-BN-15: Disabled networking skips provider jobs and power handoff

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](design.md#test-plan)
- **Dependencies:** Real BMF, osac-operator and Kind Kubernetes, with scripted inventory, power and Fabric Manager responses. The host is a fixture.
- **Gap:** The public fulfillment, operator and BMF suites inspected establish narrower behavior. The complete requirement at this tier is unverified.

**Preconditions.** Disable provider networking for a synthetic BMI with a valid image.

1. Provision and delete the fixture.
2. Inspect events, jobs and power-call history.

**Expected results.** OS provisioning succeeds, reports ProvisioningDisabled after provisioning, and no tenant attach, query, handoff or teardown power call occurs.

#### TC-BN-16: An incomplete power observation fails at the Ready-based deadline

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Current design — Create](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/design.md#create) and [PRD — NFR-2](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/prd.md#4-requirements)
- **Dependencies:** Real envtest Kubernetes API/etcd and in-process BMF reconciler. Fixture power or Fabric responses are supplied by doubles; no real host.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go`
- **Evidence:** `TestControllers / fails wrong-state observations at the Ready-based deadline` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go#L2480)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='fails\ wrong\-state\ observations\ at\ the\ Ready\-based\ deadline'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use a test BMI whose persisted NetworkAttachmentsReady value is 16 minutes old and whose next requested target is ON.

1. Return observed OFF from the management double and reconcile.
2. Read the handoff condition and retry result.

**Expected results.** The result does not requeue; condition reason is NetworkHandoffFailed and message mentions 15 minutes.

#### TC-BN-17: Confirmed ON succeeds even when the handoff timestamp is overdue

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Current design — Create](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/design.md#create) and [PRD — NFR-2](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/prd.md#4-requirements)
- **Dependencies:** Real envtest Kubernetes API/etcd and in-process BMF reconciler. Fixture power or Fabric responses are supplied by doubles; no real host.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go`
- **Evidence:** `TestControllers / accepts a confirmed ON observation even after the 15-minute deadline` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_controller_test.go#L2499)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='accepts\ a\ confirmed\ ON\ observation\ even\ after\ the\ 15\-minute\ deadline'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use the same persisted deadline fixture and configure the double to report ON.

1. Reconcile handoff.
2. Read readiness and reason.

**Expected results.** Handoff is True with reason Succeeded.

#### TC-BN-18: Overdue lease discovery warns administrators and still requeues

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Current design — Create](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/design.md#create) and [PRD — NFR-2](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/prd.md#4-requirements)
- **Dependencies:** Real envtest Kubernetes API/etcd and in-process BMF reconciler. Fixture power or Fabric responses are supplied by doubles; no real host.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery_test.go`
- **Evidence:** `TestControllers / records LeaseNotFound after ten minutes and keeps querying` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery_test.go#L203)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='records\ LeaseNotFound\ after\ ten\ minutes\ and\ keeps\ querying'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use a BMI whose NetworkHandoffComplete timestamp is 11 minutes old and a retrying lease job with an opaque test ID.

1. Reconcile IP discovery with a fake event recorder.
2. Inspect the requeue, warning and saved condition.

**Expected results.** Requeue remains positive and the LeaseNotFound warning is emitted. LeasePending remains and its administrator message contains the warning marker and opaque test ID.

#### TC-BN-19: An attached CaaS worker protects its Subnet

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — readiness and delete guards](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_subnets_server_test.go`
- **Evidence:** `TestServers / names the owning Cluster for a CaaS worker` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_subnets_server_test.go#L226)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='names the owning Cluster for a CaaS worker'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed a synthetic Subnet and a worker BMI referencing it, with a Cluster association.

1. Request ordinary Subnet Delete.
2. Read status and diagnostic.

**Expected results.** FailedPrecondition names the worker's owning fixture Cluster.

#### TC-BN-20: Omitted interface selects the type’s default fabric port

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BareMetalInstance attachment admission](design.md#network-attachment-and-validation)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / defaults interface from the selected instance type when the template has no default` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L4182)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='defaults interface from the selected instance type when the template has no default'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the attachment fixture and explicitly select a type with a valid port; omit interface.

1. Create the BMI and inspect its effective attachment.

**Expected results.** The returned interface is the selected type’s first fixture fabric port.

#### TC-BN-21: Update rejects an attachment interface change

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BareMetalInstance attachment admission](design.md#network-attachment-and-validation)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Rejects update that changes interface` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L3092)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Rejects update that changes interface'` from `fulfillment-service` in OSAC.

**Preconditions.** Create one fixture BMI with an existing authorized attachment.

1. Send a normal masked update requesting a different fixture port.
2. Inspect the result.

**Expected results.** The API rejects the immutable interface change.

#### TC-BN-22: Shared subnet carries traffic between a BMI and ComputeInstance

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — shared BMI and ComputeInstance Subnet](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, Kubernetes, AAP, Fabric Manager and two dedicated test bare-metal hosts. Only synthetic workload and network fixtures.
- **Execution:** `tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py`
- **Evidence:** `test_bmi_and_compute_instance_reach_each_other_on_shared_subnet` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py#L50)).
- **Selector:** `uv run pytest -n 0 -m requires_stretched_networking tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py` from the OSAC root using the stretched-network fixture.

**Preconditions.** Use the dedicated stretched-network fixture with one BMI and one VM requesting the same explicit provider subnet.

1. Compare their assigned IPv4 addresses with the fixture subnet.
2. Observe the harness’s bidirectional guest reachability assertions.

**Expected results.** Both addresses are distinct and within the subnet, and both same-subnet reachability assertions succeed.

#### TC-BN-23: BMI Create rejects unavailable or non-fabric ports

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BareMetalInstance attachment admission](design.md#network-attachment-and-validation)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Rejects tenant interfaces that are not fabric ports` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L2693)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Rejects tenant interfaces that are not fabric ports'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the server fixture type exposing one fabric port and a separate management port.

1. Evaluate the unknown and management port cases through ordinary Create.
2. Inspect the two errors.

**Expected results.** Both reject the requested interface as invalid.
