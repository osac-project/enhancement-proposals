# Test Plan — OSAC-1270 Base OS management for BMaaS

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 19

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

Image URL projection and the guest’s boot identity have separate cases. The lifecycle assertion verifies the configured URL on the BMH.

## Test Cases

#### TC-BOS-01: Effective image is required

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects creation without an effective disk_image` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L272)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ creation\ without\ an\ effective\ disk_image$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a published catalog without an image default.

1. Create a BMI without a disk_image and with valid inline fixture data.
2. Read status.

**Expected results.** The response is nil with InvalidArgument.

#### TC-BOS-02: Unknown DiskImage name returns NotFound

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects an unknown disk_image reference before creating the BMI` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L743)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ an\ unknown\ disk_image\ reference\ before\ creating\ the\ BMI$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a valid template and synthetic image name missing-bmi-disk-image.

1. Create the BMI with that name.
2. Read result.

**Expected results.** The response is nil with NotFound.

#### TC-BOS-03: Cross-tenant image is not visible

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Does not disclose a cross-tenant disk_image` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L362)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Does\ not\ disclose\ a\ cross\-tenant\ disk_image$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed an image owned by another synthetic tenant and a restricted tenancy fixture.

1. Call private BMI Create with the image reference.
2. Read status and response.

**Expected results.** NotFound with no object returned.

#### TC-BOS-04: Catalog image default applies before validation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Applies a CatalogItem disk_image default before validation` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L397)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Applies\ a\ CatalogItem\ disk_image\ default\ before\ validation$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a published catalog with editable image default default-bmi-disk-image.

1. Omit disk_image in private BMI Create.
2. Read the returned effective spec.

**Expected results.** Create succeeds and returns the default image ID.

#### TC-BOS-05: Masked Update rejects a replacement DiskImage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects PATCH that changes disk_image` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L1381)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ PATCH\ that\ changes\ disk_image$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a BMI with default-bmi-disk-image and a second available image.

1. Send private Update with spec.disk_image in the mask and the replacement ID.
2. Read the returned status.

**Expected results.** InvalidArgument contains “disk image is immutable.”

#### TC-BOS-06: Guest identity identifies its selected boot image

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — image selection at provisioning](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Gap:** The lifecycle asserts BMH image URL only. The architecture test tests catalog constraints. Guest identity remains unverified.

**Preconditions.** Prepare two approved fixture images with distinct benign guest OS identity markers.

1. Create a BMI selecting one image.
2. After provision read the guest marker and clean up.

**Expected results.** The running guest reports only the marker for the selected image.

#### TC-BOS-07: Obsolete image returns FailedPrecondition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Rejects an obsolete disk_image` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L340)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Rejects\ an\ obsolete\ disk_image$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a visible image in OBSOLETE lifecycle and a valid catalog.

1. Submit BMI Create referencing it.
2. Read status and text.

**Expected results.** FailedPrecondition with an obsolete diagnostic and no response object.

#### TC-BOS-08: Deprecated image succeeds with one warning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`
- **Evidence:** `TestServers / Private bare metal instances server / Returns a warning for a deprecated disk_image` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instances_server_test.go#L763)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instances server.*Returns\ a\ warning\ for\ a\ deprecated\ disk_image$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a synthetic DEPRECATED image and valid template.

1. Create with the image ID.
2. Read warnings.

**Expected results.** Create succeeds and one warning mentions deprecation.

#### TC-BOS-09: Catalog Create rejects an obsolete image default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Private bare metal instance catalog items server / rejects an obsolete DiskImage default on Create` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go#L152)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instance catalog items server.*rejects\ an\ obsolete\ DiskImage\ default\ on\ Create$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed an obsolete image and valid template in the catalog server fixture.

1. Create a BMI catalog item defaulting to that image.
2. Read the returned error.

**Expected results.** Create returns FailedPrecondition with an obsolete diagnostic.

#### TC-BOS-10: Catalog fields Update rejects another tenant’s image default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — DiskImage server and reconciler paths](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Private bare metal instance catalog items server / rejects a DiskImage default owned by another tenant on fields update` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go#L215)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instance catalog items server.*rejects a DiskImage default owned by another tenant on fields update$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use an existing catalog and a default candidate outside the catalog item's synthetic owning/shared scopes.

1. Apply a normal catalog fields update.
2. Inspect the returned status and scope diagnostic.

**Expected results.** InvalidArgument mentions the owning tenant or shared tenant.

#### TC-BOS-11: Catalog Create warns on deprecation; title-only PATCH succeeds

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Private bare metal instance catalog items server / reports DiskImage deprecation on Create and skips revalidation for title-only PATCH` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_baremetal_instance_catalog_items_server_test.go#L124)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Private bare metal instance catalog items server.*reports\ DiskImage\ deprecation\ on\ Create\ and\ skips\ revalidation\ for\ title\-only\ PATCH$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed a deprecated image and an eligible catalog template.

1. Create the catalog with that default.
2. Patch only the title and examine warnings/results.

**Expected results.** Create warns about the deprecated image. Title-only PATCH succeeds without revalidating the default.

#### TC-BOS-12: Selected DiskImage source reaches the Metal3 host

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — image selection at provisioning](design.md#e2e-tests)
- **Dependencies:** Real deployed fulfillment, hub Kubernetes, BMF, Metal3/Ironic provisioning, and dedicated test BMHs; no service doubles.
- **Execution:** `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`
- **Evidence:** `test_baremetal_instance_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py#L109)).
- **Selector:** `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py -k test_baremetal_instance_lifecycle` from the OSAC root using the BMaaS sanity fixtures.

**Preconditions.** Use the BMaaS deployed lifecycle fixture with its configured image and eligible BMH.

1. Provision the BMI and wait for the BMH.
2. Read the BMH image URL.

**Expected results.** The URL equals the configured fixture DiskImage source reference.

#### TC-BOS-13: DiskImage references are protected on database transitions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** The public BMI, catalog and DAO sources checked do not establish this complete behavior at the named boundary.

**Preconditions.** Prepare an active BMI referencing one image and a separate soft-deleted image.

1. Soft-delete the in-use image in the database fixture.
2. Insert a new BMI referring to the deleted image in a separate transaction.

**Expected results.** The first transaction fails with Z0003 and the second with Z0002, leaving existing rows consistent.

#### TC-BOS-14: Public catalog Create and field Update warn on deprecated images

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — DiskImage server and reconciler paths](design.md#unit-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Execution:** `fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go`
- **Evidence:** `TestServers / Bare metal instance catalog items server / returns DiskImage deprecation warnings from Create and fields updates` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/baremetal_instance_catalog_items_server_test.go#L167)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='Bare metal instance catalog items server.*returns DiskImage deprecation warnings from Create and fields updates$'` from `fulfillment-service` in OSAC.

**Preconditions.** Seed two deprecated synthetic DiskImages visible to the fixture catalog.

1. Create a catalog item that defaults to the first. Change only fields to use the second.
2. Inspect both response warning lists.

**Expected results.** Both operations succeed and each yields one deprecation warning.

#### TC-BOS-15: Reconciler projects the resolved DiskImage as imageURL

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — DiskImage server and reconciler paths](design.md#unit-tests)
- **Dependencies:** In-process mutation helper and mocked DiskImages client. No running hub or registry.
- **Execution:** `fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go`
- **Evidence:** `TestBareMetalInstance / should include imageURL in templateParameters when disk_image is set` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go#L696)).
- **Selector:** `go test ./internal/controllers/baremetalinstance -run '^TestBareMetalInstance$' -ginkgo.focus='should include imageURL in templateParameters when disk_image is set'` from `fulfillment-service` in OSAC.

**Preconditions.** Configure the fixture image client to return a synthetic source reference for disk-image-1.

1. Build the BMI CR through the reconciler's mutation helper.
2. Decode spec.templateParameters and compare imageURL.

**Expected results.** imageURL equals the fixture image's source reference.

#### TC-BOS-16: Reconciler reports failure to resolve a DiskImage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — DiskImage server and reconciler paths](design.md#unit-tests)
- **Dependencies:** In-process mutation helper and mocked DiskImages client. No running hub or registry.
- **Execution:** `fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go`
- **Evidence:** `TestBareMetalInstance / should return a wrapped error when disk_image resolution fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go#L738)).
- **Selector:** `go test ./internal/controllers/baremetalinstance -run '^TestBareMetalInstance$' -ginkgo.focus='should return a wrapped error when disk_image resolution fails'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a fixture BMI referring to an image that the mock image service cannot resolve.

1. Invoke the BMI mutation helper and inspect the error.

**Expected results.** The returned error preserves the image lookup failure.

#### TC-BOS-17: Deployed image default is materialized on the resulting CR

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — DiskImage lifecycle and reference protection](design.md#integration-tests)
- **Dependencies:** Real fulfillment, PostgreSQL and hub API in Kind. Registry and provisioning are omitted.
- **Gap:** The server and CR mutation specs prove the two steps separately. The combined default-to-CR check was not verified.

**Preconditions.** Create a visible synthetic image and a catalog item with that image default; leave the BMI image unset.

1. Create through the catalog and wait for the reconciliation to publish the BMI CR.
2. Read its templateParameters imageURL.

**Expected results.** The CR carries the catalog image’s exact fixture source reference.

#### TC-BOS-18: Seeded image references survive incompatible Image delete

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — DiskImage lifecycle and reference protection](design.md#integration-tests)
- **Dependencies:** Real PostgreSQL test container, in-process fulfillment server and DAOs. Fixture doubles supply tenancy and attribution. No deployed gateway or provider.
- **Gap:** Public BMI/catalog image policy checks and migration tests were searched. The active BMI and catalog delete/release sequence is not established.

**Preconditions.** Seed a synthetic DiskImage and an active BMI or catalog field referring to it, using separate fixtures.

1. Request ordinary DiskImage Delete while the fixture consumer is active.
2. Remove the consumer and retry.

**Expected results.** The referenced image is protected with FailedPrecondition. Once unused, it can be removed.

#### TC-BOS-19: Concurrent fixture writes preserve image reference integrity

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — DiskImage lifecycle and reference protection](design.md#integration-tests)
- **Dependencies:** Real PostgreSQL with image migrations and server DAO calls. No Kubernetes, registry or provisioning.
- **Gap:** No pinned test was verified for both BMI and catalog image write races.

**Preconditions.** Use a dedicated database and an unused synthetic DiskImage.

1. Run ordinary workload or catalog creation and soft-delete tests in two coordinated transactions, separately for each kind.
2. Read the resulting committed objects.

**Expected results.** A committed new reference always has a live image. If deletion commits first, the other operation does not persist a reference.
