# Test Plan — OSAC-1118 BareMetalInstance API

## Overview

- **Design:** [Public design](README.md)
- **Total test cases:** 13

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The design calls for BCM provisioning. The mapped deployed lifecycle uses Metal3/Ironic. A real BCM lifecycle remains a separate gap.

## Test Cases

#### TC-BMI-01: Tenant creates a BMI and reaches Ready

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`
- **Evidence:** `test_baremetal_instance_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py#L109)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py -k test_baremetal_instance_lifecycle` from the OSAC root using the BMaaS sanity fixtures.

**Preconditions.** Use a deployed BMaaS sanity fixture with a catalog item, image and eligible BMH.

1. Create the BMI through the tenant client.
2. Observe its final provisioned state and associated BMH.

**Expected results.** The public BMI reaches RUNNING, with Ready=True and Provisioned=True. The Metal3 BMH reaches the provisioned state.

#### TC-BMI-02: Public BMI Create resolves its catalog defaults

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Bare metal instances server / Creates object` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/baremetal_instances_server_test.go#L124)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Bare metal instances server.*Creates object$'` from `fulfillment-service` in OSAC.

**Preconditions.** Load the public server fixture with a published catalog, default type and allowed image.

1. Create a named BMI with the fixture catalog and image.
2. Inspect the returned identity and spec.

**Expected results.** Create returns a nonempty ID, the same catalog ID and instance type default-type.

#### TC-BMI-03: Invalid request identifies its invalid field

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real generated descriptors or schema fixtures. No deployed components.
- **Gap:** Public and private BMI/catalog suites establish parts of this behavior, but the complete stated procedure and boundary are unverified.

**Preconditions.** Use a valid generated BMI fixture and a variant omitting a required catalog or template selector.

1. Validate both before persistence.
2. Read status and field violations.

**Expected results.** The valid fixture passes its schema checks. The invalid request is InvalidArgument with the offending field identified.

#### TC-BMI-04: Metal3 deprovision releases its allocated host

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`
- **Evidence:** `test_baremetal_instance_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py#L109)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py -k test_baremetal_instance_lifecycle` from the OSAC root using the BMaaS sanity fixtures.

**Preconditions.** Use a lifecycle fixture with a claimed BMH that has an image URL and consumer reference.

1. Delete the BMI via the tenant CLI.
2. Wait for API deletion and inspect the released BMH.

**Expected results.** BMI disappears and the BMH becomes available with empty image URL and consumer reference.

#### TC-BMI-05: A public catalog title update preserves its template

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Bare metal instance catalog items server / Updates object through the public API` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go#L144)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Bare metal instance catalog items server.*Updates object through the public API$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic published catalog item with title Original title and the fixture template.

1. Update its title to Updated title using the title mask.
2. Read the returned title and template.

**Expected results.** The response contains Updated title and the unchanged fixture template ID.

#### TC-BMI-06: Unpublished catalog item is unavailable for provisioning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects unpublished catalog item` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L785)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ unpublished\ catalog\ item$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a fixture catalog item with Published=false and a valid private template.

1. Call BMI Create with its ID.
2. Read the status and message.

**Expected results.** Create returns NotFound with a message containing “not published.”

#### TC-BMI-07: Catalog visibility follows tenant and provider scopes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** Public and private BMI/catalog suites establish parts of this behavior, but the complete stated procedure and boundary are unverified.

**Preconditions.** Seed one scoped catalog item per test tenant and one provider shared item.

1. List and Get as each tenant and the provider.
2. Compare returned IDs and role access.

**Expected results.** Tenant clients see their allowed scoped/shared items without the other tenant’s scoped entry; provider scope follows the private catalog contract.

#### TC-BMI-08: Field policies, feedback and immutable catalog selection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** Public and private BMI/catalog suites establish parts of this behavior, but the complete stated procedure and boundary are unverified.

**Preconditions.** Seed a published fixture with a default and locked field and a controlled fulfillment feedback source.

1. Create through the fixture catalog, deliver a state-change Signal and observe public status.
2. Attempt to change catalog_item using a normal masked Update.

**Expected results.** The effective spec reflects default/locked fields, status follows feedback, and the immutable update fails without changing catalog identity.

#### TC-BMI-09: Failed deployment can be deleted and recreated

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — test plan](README.md#test-plan)
- **Dependencies:** Real deployed fulfillment, BMF and a dedicated supported BCM fixture with a controlled provider failure. No shared hosts.
- **Gap:** Public and private BMI/catalog suites establish parts of this behavior, but the complete stated procedure and boundary are unverified.

**Preconditions.** Use a disposable BCM fixture with scripted provisioning failure through its supported test interface.

1. Create the first BMI and observe Failed. Delete it, restore fixture readiness and create a fresh one.

**Expected results.** The failed object releases its claim and a new ID reaches Ready through the repaired fixture.

#### TC-BMI-10: Catalog published filter excludes drafts

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Bare metal instance catalog items server / Lists drafts and published items with optional published filter` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go#L200)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Bare metal instance catalog items server.*Lists drafts and published items with optional published filter$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create three published items and one draft in the scoped catalog fixture.

1. List normally and record the count.
2. List with the supported published filter.

**Expected results.** The first list shows four items. The filtered list shows three and every returned item is published.

#### TC-BMI-11: Catalog selection is immutable after Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Bare metal instances server / Rejects update that changes immutable catalog_item` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/baremetal_instances_server_test.go#L378)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Bare metal instances server.*Rejects update that changes immutable catalog_item$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a BMI with a selected published fixture catalog.

1. Send a public Update of spec.catalog_item to a different fixture reference.
2. Observe the admission result.

**Expected results.** The public server returns InvalidArgument.

#### TC-BMI-12: Both catalog APIs support an owned item lifecycle

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Gap:** The server suites verify discrete operations, including the mapped title update and publication filter. A lifecycle spanning both surfaces and scopes is not established by either spec.

**Preconditions.** Use distinct in-process public and private API fixtures with a valid template and authorized tenant/provider identity stubs.

1. Create, Get and List an item through each authorized surface.
2. Update the title, delete each item and verify its disappearance.

**Expected results.** Within each scope, the same identifier returns its new title before deletion, and is absent from Get and List after deletion.

#### TC-BMI-13: A valid BMI completes the deployed BCM lifetime

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — BMI API test plan](README.md#test-plan)
- **Dependencies:** Real BCM, deployed fulfillment, BMF and provider operations on dedicated test fixtures.
- **Gap:** Public sanity exercises the Metal3/Ironic journey. The BCM controller suite uses a stub HTTP server and envtest, so the deployed BCM path remains open.

**Preconditions.** Use a published fixture catalog and one dedicated host in a disposable supported BCM deployment.

1. Create a tenant BMI and check its public conditions and fixture host claim.
2. Delete the BMI and verify provider cleanup and host availability.

**Expected results.** The BMI reaches Ready with one expected host claim and is removed after deprovision. The host becomes available again.
