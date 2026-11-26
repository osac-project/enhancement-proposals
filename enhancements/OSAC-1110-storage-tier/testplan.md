# Test Plan — OSAC-1110 StorageTier API

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 18

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

The design scopes StorageTier to the private API. The newer public read path has its own Kind assertions and is outside these catalog cases.

## Test Cases

#### TC-ST-01: Private Create and Get return the configured tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private CRUD](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L486)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Creates and gets a storage tier` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L183)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Creates and gets a storage tier$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use the PostgreSQL server fixture and a registered synthetic backend.

1. Create a valid block tier and Get its ID.
2. Compare the returned tier with the Create response.

**Expected results.** Get returns the same tier and backend association.

#### TC-ST-02: Create rejects a missing backend ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Missing backend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L487)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Validation / Create with non-existent backend_id fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L617)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Validation Create with non-existent backend_id fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid tier specimen referencing no-such-backend.

1. Call private Create.
2. Read status and diagnostic.

**Expected results.** It returns NotFound and names no-such-backend.

#### TC-ST-03: A tier name cannot change

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Immutable name](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L488)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Immutability / Update changing metadata.name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L751)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Immutability Update changing metadata\.name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic tier with a valid backend.

1. Send private Update changing metadata.name.
2. Read its status.

**Expected results.** The change returns InvalidArgument with an immutable-name diagnostic.

#### TC-ST-04: Stale locked update is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Optimistic concurrency](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L489)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Optimistic locking / Update with stale version and lock=true fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L830)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Optimistic locking Update with stale version and lock=true fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Save a tier’s original version and make one successful locked update.

1. Send a second locked update carrying the original version.
2. Observe the returned status.

**Expected results.** The stale request returns Aborted.

#### TC-ST-05: Private tier List honors a page limit

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private CRUD and pagination](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L486)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / List objects with limit` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L231)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour List objects with limit$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed five active tiers in the isolated shared catalog.

1. List tiers with limit=2.
2. Read the returned page size.

**Expected results.** The returned page has size two.

#### TC-ST-06: A backend referenced by an active tier cannot be soft-deleted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Referential integrity](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L494)
- **Dependencies:** Real PostgreSQL fixture with Goose migrations. No fulfillment gateway, Kubernetes or storage vendor.
- **Execution:** `fulfillment-service/internal/database/migrations/76_add_storage_tier_ref_triggers_test.go`
- **Evidence:** `TestMigrations / Add storage tier referential integrity triggers / Prevents soft-deleting a backend referenced by an active storage tier` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/76_add_storage_tier_ref_triggers_test.go#L201)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Add storage tier referential integrity triggers Prevents soft-deleting a backend referenced by an active storage tier$'` from `fulfillment-service` in OSAC.

**Preconditions.** Apply the storage reference migration to fixture PostgreSQL; create a backend referenced by an active tier.

1. Soft-delete the referenced backend in the fixture transaction.
2. Read SQLSTATE.

**Expected results.** The reference trigger rejects the write with Z0003.

#### TC-ST-07: Tenant onboarding reports real StorageClasses for resolved tiers

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Tenant tier resolution](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L30)
- **Dependencies:** Deployed hub, storage operator, AAP and configured storage provider with an isolated tenant fixture. No provider double.
- **Execution:** `tests/e2e/storage/test_tenant_storage_lifecycle.py`
- **Evidence:** `test_tenant_storage_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/storage/test_tenant_storage_lifecycle.py#L24)).
- **Selector:** Select the pytest node `tests/e2e/storage/test_tenant_storage_lifecycle.py::test_tenant_storage_lifecycle` from the isolated OSAC test environment.

**Preconditions.** Use an isolated Tenant in the deployed managed-storage fixture.

1. Wait for StorageBackendReady and ClusterStorageReady.
2. Read the reported class names and tier identifiers, then check the hub classes.

**Expected results.** At least one name-and-tier pair is reported. Every reported class exists on the hub.

#### TC-ST-08: Update rejects a missing replacement backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Missing backend validation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L487)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Validation / Update with non-existent backend_id fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L666)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Validation Update with non-existent backend_id fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a tier pointing to a valid backend.

1. Send Update with the association changed to no-such-backend.
2. Read status and diagnostic.

**Expected results.** The response is NotFound naming no-such-backend.

#### TC-ST-09: An active tier name cannot be duplicated

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Name uniqueness](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L495)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Name uniqueness / Create with duplicate active name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L791)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Name uniqueness Create with duplicate active name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create the fixture tier with a valid backend.

1. Repeat Create with the same active name.
2. Read the status.

**Expected results.** The duplicate returns AlreadyExists.

#### TC-ST-10: A deleted tier name becomes available for reuse

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Name reuse](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L495)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Name uniqueness / Create after delete of same name succeeds` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L815)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Name uniqueness Create after delete of same name succeeds$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a valid tier named reusable-name.

1. Delete it, then Create the same name again.
2. Read the returned identity.

**Expected results.** Create succeeds and returns reusable-name as ID and metadata.name.

#### TC-ST-11: The setPayload dispatcher handles a StorageTier event

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Event payload](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L490)
- **Gap:** No matching StorageTier payload dispatch assertion was verified in fulfillment event/DAO unit sources.

**Preconditions.** Use a StorageTier with unique fixture fields and a synthetic event payload.

1. Pass it through setPayload and inspect the resulting oneof.

**Expected results.** The StorageTier branch is selected and preserves the fixture Tier identity and fields.

#### TC-ST-12: Kind private API round trips through gRPC and REST

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Kind dual-protocol CRUD](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L493)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Gap:** Public read, filtering and invalid Create specs in Kind leave successful private CRUD over both protocols unverified.

**Preconditions.** Use valid administrative clients and a synthetic backend in a disposable Kind deployment.

1. Create, Get/List, update QoS and delete distinct fixtures over both protocols.
2. Compare each result with the stored tier.

**Expected results.** Both protocols agree on ID and QoS after update and omit the deleted fixture.

#### TC-ST-13: Tier insertion populates the backend reference helper

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Trigger behavior](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L496)
- **Dependencies:** Real PostgreSQL test container and migration-specific database snapshot. No fulfillment API or provider.
- **Execution:** `fulfillment-service/internal/database/migrations/76_add_storage_tier_ref_triggers_test.go`
- **Evidence:** `TestMigrations / Add storage tier referential integrity triggers / Materializes backend references into the helper table on insert` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/76_add_storage_tier_ref_triggers_test.go#L144)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Add storage tier referential integrity triggers Materializes backend references into the helper table on insert$'` from `fulfillment-service` in OSAC.

**Preconditions.** Apply migration 76 and seed two existing synthetic backends.

1. Insert one tier referencing the two backend IDs through the migration fixture.
2. Count helper rows for that tier.

**Expected results.** The reference helper contains two rows for the inserted tier.

#### TC-ST-14: A VMaaS boot disk uses the class for its selected tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Tenant onboarding workflow](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L30)
- **Dependencies:** Deployed fulfillment, hub and VMaaS Kubernetes, ComputeInstance operator and configured storage provider. No provider double.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py`
- **Evidence:** `test_compute_instance_explicit_boot_disk_tier` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py#L59)).
- **Selector:** Select the pytest node `tests/e2e/vmaas/sanity/test_compute_instance_storage_tier.py::test_compute_instance_explicit_boot_disk_tier` from the isolated OSAC test environment.

**Preconditions.** Use the deployed VMaaS fixture with an explicit default storage tier, workload template and isolated synthetic ComputeInstance.

1. Create the ComputeInstance with the selected boot tier and wait for it to provision.
2. Read its stored boot tier and root DataVolume StorageClass.

**Expected results.** The boot tier equals the requested tier, and the root DataVolume has the StorageClass resolved for that tier.

#### TC-ST-15: Replacing a backend reference updates the helper rows

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Trigger behavior](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L496)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Gap:** Migration 76 checks insertion. The tier server fixture changes association settings but does not query the helper after replacing a backend ID.

**Preconditions.** Seed a tier linked to backend A and a second active backend B.

1. Use the supported tier update to change the association to B.
2. Read the helper rows for the tier.

**Expected results.** The tier has a single row for B and no row for A.

#### TC-ST-16: Tier List filters to a single fixture ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private CRUD and List filtering](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L486)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / List objects with filter` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L257)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour List objects with filter$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed three private tier rows linked to a fixture backend.

1. List with an equality filter for one seeded ID.
2. Compare the returned page to that ID.

**Expected results.** The page has one item and its ID matches the filter.

#### TC-ST-17: Tier masked Update changes the reported read bandwidth

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private CRUD and QoS updates](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L486)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Update backends replaces the backend association` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L306)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Update backends replaces the backend association$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a tier linked to the seeded fixture backend.

1. Update its protocol to BLOCK and request read bandwidth 2000 through the spec mask.
2. Inspect the updated tier.

**Expected results.** The result has protocol BLOCK and a single association reporting read bandwidth 2000.

#### TC-ST-18: Private tier Delete removes the fixture from Get

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Private CRUD and Delete](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1110-storage-tier/design.md#L486)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_storage_tiers_server_test.go`
- **Evidence:** `TestServers / Private storage tiers server / Behaviour / Delete removes the object` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_storage_tiers_server_test.go#L378)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private storage tiers server Behaviour Delete removes the object$'` from `fulfillment-service` in OSAC.

**Preconditions.** Create a synthetic tier with no Volume references.

1. Delete it through the private server.
2. Get the original ID.

**Expected results.** Delete succeeds and Get returns NotFound.
