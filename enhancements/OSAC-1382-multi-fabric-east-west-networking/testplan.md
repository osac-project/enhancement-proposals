# Test Plan — OSAC-1382 Multi-fabric east-west networking

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 12

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The current API carries one `virtual_network` reference and rejects changes to the member list in this release. The cases distinguish that behavior from the proposal’s eventual resize requirement.

## Test Cases

#### TC-FD-01: Ethernet creation requires the NetworkClass capability

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_fabric_domains_server_test.go`
- **Evidence:** `TestServers / requires the NetworkClass Ethernet capability` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L82)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='requires the NetworkClass Ethernet capability'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed the test VirtualNetwork and its NetworkClass with Ethernet east-west disabled.

1. Create an Ethernet FabricDomain for the fixture network.
2. Read the result.

**Expected results.** InvalidArgument names supports_east_west_ethernet.

#### TC-FD-02: Empty servers are rejected by Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_fabric_domains_server_test.go`
- **Evidence:** `TestServers / requires servers` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L118)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='requires servers'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the private FabricDomain server fixture with an otherwise formed request and no server names.

1. Send Create.
2. Read the status and diagnostic.

**Expected results.** InvalidArgument identifies servers.

#### TC-FD-03: Create requires a nonempty VirtualNetwork reference

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_fabric_domains_server_test.go`
- **Evidence:** `TestServers / requires a VirtualNetwork` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L125)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='requires a VirtualNetwork'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a FabricDomain request with one server and a blank virtual_network reference.

1. Send Create.
2. Inspect the status and diagnostic.

**Expected results.** InvalidArgument identifies virtual_network.

#### TC-FD-04: A tenant can reference only its own VN

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** FabricDomain API and operator test suites on OSAC main do not establish this complete assertion at the selected tier.

**Preconditions.** Seed two synthetic tenants with distinct VNs in one test database.

1. Submit tenant A’s normal domain request referencing tenant B’s fixture network.
2. Compare the result and stored objects.

**Expected results.** PermissionDenied and no domain is created.

#### TC-FD-05: FabricDomain status converges with provider results

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — provider convergence](design.md#integration-tests)
- **Dependencies:** Real controller, Kubernetes API, AAP and dedicated Fabric Manager/backend fixture. No provider double.
- **Gap:** The envtest task harness injects responses. No real Fabric Manager convergence with per-member status was verified.

**Preconditions.** Use a fixture NetworkClass and runnable isolated Fabric Manager supporting Ethernet EW.

1. Create a domain with two members. Observe the first reconciliation.
2. Complete the task and inspect Ready, backend ID and each member. Repeat with a declared failed member.

**Expected results.** Ready is initially False/Provisioning. Success sets Ready and a backend ID, with both members ACTIVE. Failure reports ProvisioningFailed and the failed member’s status/message.

#### TC-FD-06: A real Ethernet FabricDomain reconciles and cleans up

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — full FabricDomain lifecycle](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, Kubernetes, AAP, Fabric Manager and two dedicated test bare-metal hosts. Only synthetic workload and network fixtures.
- **Gap:** The deployed stretched BMI/VM suite verifies ordinary subnet reachability without creating a FabricDomain. No deployed Ethernet FabricDomain lifecycle was verified.

**Preconditions.** Prepare a dedicated test NetworkClass and VN, preconfigured Ethernet template and two test bare-metal members.

1. Create the Ethernet domain and observe networking status and provider resource inventory.
2. Delete it and verify cleanup.

**Expected results.** Ready becomes true with a provider ID, the provider cluster identifies the selected members, and its resource disappears on delete.

#### TC-FD-07: Missing Ethernet template is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** FabricDomain API and operator test suites on OSAC main do not establish this complete assertion at the selected tier.

**Preconditions.** Seed a class that advertises Ethernet EW without template_id and a VN using the class.

1. Submit a valid one-VN Ethernet domain Create.
2. Read its response and domain inventory.

**Expected results.** FailedPrecondition with the missing template identified, without a new domain.

#### TC-FD-08: Known unsupported fabric types return Unimplemented

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_fabric_domains_server_test.go`
- **Evidence:** `TestServers / rejects unsupported fabric types` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L103)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='rejects unsupported fabric types'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the private server fixture with one server and one VN.

1. Set type to InfiniBand or NVLink across the two table entries.
2. Submit Create and record the status for each.

**Expected results.** Both entries return Unimplemented.

#### TC-FD-09: FabricDomain writes emit one metric and lifecycle event per transition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — FabricDomain observability](design.md#observability-and-monitoring)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Execution:** `osac-operator/internal/controller/fabricdomain_observability_test.go`
- **Evidence:** `TestControllers / observes Ready, Failed and Deleted once, after the write` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/fabricdomain_observability_test.go#L246)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='observes\ Ready,\ Failed\ and\ Deleted\ once,\ after\ the\ write'` from `osac-operator` in OSAC.

**Preconditions.** Start the networking envtest harness. Attach its fake recorder and real Prometheus registry.

1. Reconcile a successful create and delete, then a failing create using scripted AAP results.
2. Reconcile each completed state again and read events and counts.

**Expected results.** Successful create produces one sample and one event, delete emits its event after removal, and failed creation yields one warning and failure increment.

#### TC-FD-10: Proposed member resize leaves other domain identity fields immutable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests) and [Current FabricDomain API tests](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L133)
- **Dependencies:** Real fulfillment, controller, Kubernetes and database in Kind. AAP/Fabric Manager outcomes are supplied by the fixture.
- **Gap:** The design proposes member resize. The pinned server rejects a member-list change in this release. End-to-end resize remains unverified.

**Preconditions.** Use an Ethernet FabricDomain fixture with one member and the current class template. Supply controlled manager results.

1. When resize is implemented in the fixture release, update the servers list and observe reconcile. Issue separate normal writes changing type and VN.

**Expected results.** The member change reconciles the new set against the same template. The other two changes are rejected.

#### TC-FD-11: Current API rejects member changes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — FabricDomain API validation](design.md#unit-tests) and [Current FabricDomain API tests](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L133)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_fabric_domains_server_test.go`
- **Evidence:** `TestServers / rejects a servers change` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_fabric_domains_server_test.go#L132)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='rejects a servers change'` from `fulfillment-service` in OSAC.

**Preconditions.** Create an eligible Ethernet domain with server-a.

1. Send a masked spec.servers Update adding server-b.
2. Read the returned status and diagnostic.

**Expected results.** InvalidArgument reports that servers cannot change in this release.

#### TC-FD-12: A referenced VirtualNetwork cannot be deleted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — VN teardown guard](design.md#integration-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Gap:** The public FabricDomain and VirtualNetwork server/operator suites inspected do not verify this complete delete sequence.

**Preconditions.** Create a synthetic VN and an active FabricDomain referencing it.

1. Request ordinary VN deletion while the domain exists.
2. Remove the fixture domain, then request VN deletion again.

**Expected results.** The first operation leaves the VN protected while referenced. The second permits cleanup after the dependency is gone.
