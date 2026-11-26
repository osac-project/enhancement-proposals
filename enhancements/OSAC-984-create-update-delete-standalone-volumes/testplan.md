# Test Plan — OSAC-984 Create, update and delete standalone volumes

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 25

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

## Test Cases

#### TC-V-01: Create requires metadata.name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C2](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Validation / Create without metadata.name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L791)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Validation Create without metadata\.name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid private Volume spec with gold tier, 100 GiB and access mode but no name.

1. Call Create and read error status and field path.

**Expected results.** InvalidArgument identifies metadata.name.

#### TC-V-02: Duplicate active name in the tenant is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C7](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Name uniqueness / Create with duplicate active name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L882)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Name uniqueness Create with duplicate active name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create one active fixture in the private server suite.

1. Create the same name again for the scoped test tenant.
2. Read status.

**Expected results.** The duplicate returns AlreadyExists.

#### TC-V-03: Storage tier cannot be replaced after Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U2](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Spec immutability / Rejects update that changes storage_tier` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L918)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Spec immutability Rejects update that changes storage_tier$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic Volume with a valid registered tier.

1. Update its storage_tier to another tier.
2. Observe status.

**Expected results.** Update of the immutable tier is rejected.

#### TC-V-04: Allowed metadata changes from CREATING, AVAILABLE and FAILED

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U1, TC-U5, TC-U6](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** The public update spec verifies a successful request in one initial state. It does not assert all metadata changes across CREATING, AVAILABLE and FAILED.

**Preconditions.** Seed independent fixture volumes in the three allowed states.

1. Update display_name, description, user labels and annotations.
2. Read each stored record.

**Expected results.** Every allowed state persists exactly the new mutable metadata without changing state or spec.

#### TC-V-05: Create sets state and discards caller-supplied status

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C8](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / CUD operations / Drops a caller-supplied status on create` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L270)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server CUD operations Drops a caller-supplied status on create$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid public Volume request in the server fixture with a display message in the supplied status.

1. Call Create with the fixture status.
2. Inspect the returned server-owned fields.

**Expected results.** State is CREATING and the supplied status message is absent.

#### TC-V-06: Private Get returns NotFound after deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-D4](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Delete removes the object` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L731)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Delete removes the object$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create one private Volume in the server fixture.

1. Delete it and then Get its ID.
2. Inspect returned status.

**Expected results.** Get returns NotFound.

#### TC-V-07: Kind Create observes hub status and Delete removes the active Volume

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-IT1, TC-IT4](design.md#requirement-traceability)
- **Dependencies:** Real Kind Kubernetes, fulfillment, PostgreSQL and feedback controllers. Vendor readiness and vendor ID are injected; no running vendor CSI or array.
- **Execution:** `fulfillment-service/it/it_volume_lifecycle_test.go`
- **Evidence:** `TestIntegration / Volume lifecycle / should create and delete a Volume end-to-end` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_volume_lifecycle_test.go#L133)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Volume lifecycle / should create and delete a Volume end-to-end` in the service-only phase.

**Preconditions.** Use deployed fulfillment services and controllers in Kind. Seed a synthetic tenant, project and active block tier.

1. Create a Volume and wait for its hub CR.
2. Set the fixture Ready phase and vendor ID on the CR; inspect the private API.
3. Delete, then poll for the CR and API record to disappear.

**Expected results.** The API reports AVAILABLE and the injected vendor ID, then Get returns NotFound once the hub CR is removed.

#### TC-V-08: User manages a standalone volume across a deployed lifecycle

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — E2E-1](design.md#requirement-traceability)
- **Dependencies:** Real deployed fulfillment, operators and supported test block storage vendor. No service doubles.
- **Gap:** Kind tests inject vendor completion. The deployed VMaaS storage tests create disk attachments rather than a user-managed standalone Volume with mutable metadata.

**Preconditions.** Use a dedicated deployment with an eligible standalone block tier and isolated tenant.

1. Create a Volume through the tenant interface and wait for availability.
2. Update its description, read it, delete it, and verify removal.

**Expected results.** The resource reaches AVAILABLE, retains the changed description, then leaves the active API after backend cleanup.

#### TC-V-09: Create requires storage tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C3](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Validation / Create without storage_tier fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L808)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Validation Create without storage_tier fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid named fixture with size and access mode but no storage tier.

1. Call private Create.
2. Read the field diagnostic.

**Expected results.** InvalidArgument names storage_tier.

#### TC-V-10: Size cannot change after Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U2a](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Spec immutability / Rejects update that changes size_gib and preserves the original value` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L939)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Spec immutability Rejects update that changes size_gib and preserves the original value$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a fixture with known capacity.

1. Change its size via Update and Get it again.
2. Read the error and stored size.

**Expected results.** Update is rejected and the original size remains.

#### TC-V-11: Hub Volume provisioning failure is terminal for that object

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — TC-C9](design.md#requirement-traceability)
- **Dependencies:** Real Kubernetes API and etcd in envtest. Vendor provisioner is a scripted fixture; no deployed fulfillment or array.
- **Execution:** `osac-operator/internal/controller/volume_controller_test.go`
- **Evidence:** `TestControllers / VolumeReconciler / does not auto-retry provisioning once Failed (terminal phase)` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/volume_controller_test.go#L379)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^VolumeReconciler does not auto-retry provisioning once Failed \(terminal phase\)$'` from `osac-operator` in OSAC.

**Preconditions.** Use a hub Volume CR with a synthetic vendor Create error in the vendor mock.

1. Reconcile the hub Volume to Failed and record vendor Create calls.
2. Clear the mock error and reconcile the same object again.

**Expected results.** The hub phase remains Failed and the Create call count does not increase.

#### TC-V-12: Repeated Delete remains safe while a name is reserved

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-D3, TC-IT4](design.md#requirement-traceability)
- **Dependencies:** Requires real Kind fulfillment and hub adapters with a fixture holding cleanup pending.
- **Gap:** The server suite checks ordinary Delete and reuse afterward. The Kind lifecycle does not assert repeated Delete or collision while a controlled deletion is pending.

**Preconditions.** Use a deployed fixture Volume whose deletion can be held pending by a controlled cleanup dependency.

1. Start Delete, then repeat it while the Volume is DELETING.
2. Attempt a same-name Create while cleanup is still pending.

**Expected results.** Repeated Delete is idempotent and the pending Volume still reserves its name.

#### TC-V-13: Volume API authorization respects tenant and provider roles

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-A1, TC-IT5, TC-IT5a, TC-IT5b](design.md#requirement-traceability)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** The migration proves the separate name-uniqueness boundary. The Kind and server Volume sources do not establish this role and tenant matrix.

**Preconditions.** Use two synthetic tenants with separate Volumes, their tenant-scoped clients and an authorized provider-admin fixture.

1. Exercise supported Create, Update and Delete through the fixture clients and compare the allowed resource scopes to each role.

**Expected results.** Each tenant client manages only resources permitted by its role. Provider administration follows the documented cross-tenant policy.

#### TC-V-14: Create requires nonzero size

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C4](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Validation / Create without size_gib fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L827)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Validation Create without size_gib fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a fixture with a valid name, tier and mode but zero size.

1. Call Create.
2. Read the field error.

**Expected results.** InvalidArgument identifies size_gib.

#### TC-V-15: Create requires an explicit access mode

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C5](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Validation / Create without access_mode fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L846)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Validation Create without access_mode fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use an otherwise valid named Volume with a valid tier and size but no access mode.

1. Call private Create through the PostgreSQL-backed server fixture.

**Expected results.** Create returns InvalidArgument identifying access_mode.

#### TC-V-16: Access mode cannot change after Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U2b](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Spec immutability / Rejects update that changes access_mode` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L1005)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Spec immutability Rejects update that changes access_mode$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a fixture with a valid mode.

1. Request an update to a different access mode.
2. Observe the result.

**Expected results.** Update of the immutable mode is rejected.

#### TC-V-17: Same Volume name is allowed in separate database tenants

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C7, TC-IT5](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL test container and migration-specific database snapshot. No fulfillment API or provider.
- **Execution:** `fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go`
- **Evidence:** `TestMigrations / Create volumes tables / Allows same name in different tenants` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go#L105)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Create volumes tables Allows same name in different tenants$'` from `fulfillment-service` in OSAC.

**Preconditions.** Apply migration 95 and seed a second fixture tenant.

1. Insert active Volumes with different IDs but name shared-name, one in each tenant.

**Expected results.** Both inserts succeed.

#### TC-V-18: Deleted Volume name is available for a fresh Create

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-D4, TC-IT4](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Name uniqueness / Create after delete of same name succeeds` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L903)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Name uniqueness Create after delete of same name succeeds$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic Volume named reusable-name in the server suite.

1. Delete it, then Create another Volume with the same name.

**Expected results.** The second Volume has reusable-name and a different ID.

#### TC-V-19: Failed Volume can be deleted through the deployed lifecycle

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — TC-D1, E2E-1](design.md#requirement-traceability)
- **Dependencies:** Requires deployed fulfillment, hub operator and an isolated vendor fixture capable of a controlled failure.
- **Gap:** Hub Envtest verifies terminal failure, while Kind verifies removal after a synthetic success. Deployed storage sources do not verify this Failed-to-deleted path.

**Preconditions.** Use an isolated tenant and a provider fixture configured to return a synthetic provisioning failure.

1. Create the standalone Volume and wait for Failed.
2. Delete it and observe the backend fixture and active API inventory.

**Expected results.** The failed resource is removed after cleanup without being provisioned again.

#### TC-V-20: Private Create derives provider from the resolved tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C8](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider. The tier resolver is a test double.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / stamps the resolved provider over caller-provided status` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L446)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour stamps the resolved provider over caller-provided status$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the server suite with a fixture tier resolver returning test-provider and a synthetic Create request with a different caller status provider.

1. Create the Volume through the private server.
2. Read the returned provider.

**Expected results.** The returned provider is test-provider.

#### TC-V-21: A Volume name cannot change through public Update

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U2c](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Gap:** Migration tests verify database immutability. The public and private Volume Update tests do not verify this public name-specific result and unchanged readback.

**Preconditions.** Seed an authorized synthetic Volume with name volume-a.

1. Request a public Update changing only the name to volume-b.
2. Get the original ID.

**Expected results.** The rename returns InvalidArgument and Get retains volume-a.

#### TC-V-22: A stale locked Volume Update does not overwrite metadata

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-U3](design.md#requirement-traceability)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Gap:** The private and public Volume server sources do not verify a Volume-specific stale locked Update.

**Preconditions.** Read a synthetic Volume and save its version. Commit a metadata update using the current version.

1. Submit a locked change using the original version.
2. Read the Volume again.

**Expected results.** The stale change is rejected and the first metadata update is preserved.

#### TC-V-23: Public VolumeStatus declares only state and message

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — TC-MAP1](design.md#requirement-traceability)
- **Dependencies:** Descriptor-only assertion. The hosting server suite starts PostgreSQL; the spec performs no I/O.
- **Execution:** `fulfillment-service/internal/servers/volumes_server_test.go`
- **Evidence:** `TestServers / Public volumes server / Public schema / Public VolumeStatus has exactly state and message` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/volumes_server_test.go#L615)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Public volumes server Public schema Public VolumeStatus has exactly state and message$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the generated public VolumeStatus descriptor.

1. Compare its field names and total count against the approved schema.

**Expected results.** Only state and message are present.

#### TC-V-24: Standalone block-only validation rejects an incompatible offering

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — TC-C6](design.md#requirement-traceability)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** The canonical private Kind tier-resolution test accepts an NFS Volume request. No public-source assertion verifies the older standalone block-only policy at the public boundary.

**Preconditions.** Seed distinct synthetic BLOCK and NFS tiers and otherwise valid public standalone Volume requests.

1. Submit a valid block request and a request with the incompatible tier through the applicable public standalone API.

**Expected results.** The design calls for acceptance of the block request and rejection of the NFS request. This remains an unverified public API requirement.

#### TC-V-25: CSI allocates a human-readable display name for the inventory Volume

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — TC-CSI1–4](design.md#requirement-traceability)
- **Gap:** The CSI client tests assert metadata.name and other fields. No display_name assertion is present in the canonical CSI driver test sources.

**Preconditions.** Use a synthetic CSI request carrying a known PVC name and a recording fulfillment client.

1. Build CreateVolume inventory metadata.
2. Compare the generated display value with the PVC-derived expectation.

**Expected results.** The requested display value follows the design's documented PVC-derived form.
