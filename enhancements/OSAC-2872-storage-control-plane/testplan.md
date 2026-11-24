# Test Plan — OSAC-2872 Storage control plane

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 21

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

Vendor provisioning failure is terminal in the current operator tests. A transient error submitting the hub object is a distinct fulfillment-controller retry boundary.

## Test Cases

#### TC-SCP-01: Standalone Create returns assigned identity and CREATING

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Create state and identity](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1054)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Creates a standalone volume` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L466)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Creates a standalone volume$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a private Volume server with synthetic gold tier and its fixture backend.

1. Create a 50 GiB standalone Volume.
2. Read the returned spec, ID and state.

**Expected results.** The ID is populated, tier is gold, size is 50 GiB and state is CREATING.

#### TC-SCP-02: Duplicate active volume name is a gRPC conflict

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Tenant-scoped duplicate handling](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1054)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Execution:** `fulfillment-service/internal/servers/private_volumes_server_test.go`
- **Evidence:** `TestServers / Private volumes server / Behaviour / Name uniqueness / Create with duplicate active name fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/servers/private_volumes_server_test.go#L882)).
- **Selector:** `go test ./internal/servers -run '^TestServers$' -ginkgo.focus='^Private volumes server Behaviour Name uniqueness Create with duplicate active name fails$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use an active synthetic volume with a test tenant and name.

1. Create another Volume with that identity.
2. Read the gRPC status.

**Expected results.** The duplicate returns AlreadyExists.

#### TC-SCP-03: Fulfillment reconciler adds a hub Volume with tenant and project annotations

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Hub Volume creation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1055)
- **Execution:** `fulfillment-service/internal/controllers/volume/volume_reconciler_function_test.go`
- **Evidence:** `TestVolume / update / sets tenant and project annotations when creating the hub Volume` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/volume/volume_reconciler_function_test.go#L479)).
- **Selector:** `go test ./internal/controllers/volume -run '^TestVolume$' -ginkgo.focus='^update sets tenant and project annotations when creating the hub Volume$'` from `fulfillment-service` in OSAC.

**Preconditions.** Provide a CREATING volume in hub-1, test namespace, tenant-1 and project-1; use an in-memory Kubernetes client.

1. Run the Fulfillment Volume update task.
2. List hub Volumes by its UUID label.

**Expected results.** Exactly one CR exists with tenant-1 and project-1 annotations.

#### TC-SCP-04: Missing StorageTier returns NotFound

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Missing tier handling](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1056)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Execution:** `fulfillment-service/it/it_volume_lifecycle_test.go`
- **Evidence:** `TestIntegration / Volume lifecycle / Tier resolution / should fail with NotFound for non-existent tier` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_volume_lifecycle_test.go#L304)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Volume lifecycle / Tier resolution / should fail with NotFound for non-existent tier` in the service-only phase.

**Preconditions.** Use a deployed fixture with a syntactically valid volume request for an absent tier.

1. Call Volume Create and inspect the status.

**Expected results.** Create returns NotFound.

#### TC-SCP-05: Tier policy allows only the permitted fixture tenant

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Storage tier policy](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1057)
- **Dependencies:** Real PostgreSQL test container and in-process fulfillment service, DAO and server logic. Test doubles supply tenancy and attribution where needed; deployed gateway and providers are outside the boundary.
- **Gap:** The resolver and Kind lifecycle fixtures exercise catalog resolution, without an allowed-versus-unassigned tenant tier policy comparison.

**Preconditions.** Set up a shared catalog with one tier assigned to a synthetic tenant and one deliberately unassigned fixture.

1. Evaluate otherwise valid creates under each applicable fixture policy.
2. Read authorization status and database changes.

**Expected results.** The allowed request is created. The disallowed request is denied without creating a volume.

#### TC-SCP-06: Kind private API reflects successful hub Volume feedback

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Volume lifecycle integration](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1074)
- **Dependencies:** Real Kind hub, PostgreSQL, fulfillment and feedback controllers. The suite injects vendor status into the hub CR; there is no vendor CSI or storage array.
- **Execution:** `fulfillment-service/it/it_volume_lifecycle_test.go`
- **Evidence:** `TestIntegration / Volume lifecycle / should create and delete a Volume end-to-end` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_volume_lifecycle_test.go#L133)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Volume lifecycle / should create and delete a Volume end-to-end` in the service-only phase.

**Preconditions.** Use the deployed fulfillment and hub controllers in Kind, with a fixture tenant, project, backend and block tier.

1. Create the fixture and wait for its hub Volume.
2. Set the synthetic Ready status and vendor ID on the CR, then read the private API.

**Expected results.** The API reports AVAILABLE with the fixture vendor ID.

#### TC-SCP-07: CSI CreateVolume polls the mock service until AVAILABLE

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [CSI availability polling](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1066)
- **Execution:** `osac-csi-driver/pkg/driver/controller_test.go`
- **Evidence:** `TestCreateVolume_PollsUntilAvailable` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-csi-driver/pkg/driver/controller_test.go#L357)).
- **Selector:** `go test ./pkg/driver -run '^TestCreateVolume_PollsUntilAvailable$'` from `osac-csi-driver` in OSAC.

**Preconditions.** Use a mock Fulfillment client returning CREATING, then AVAILABLE on the third Get for vol-1.

1. Call CreateVolume with tier gold.
2. Count GetVolume calls and read the returned ID.

**Expected results.** At least three Gets occur and the successful result contains vol-1.

#### TC-SCP-08: Tier resolver reports a missing associated backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Missing tier backend](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1056)
- **Dependencies:** Real PostgreSQL fixture with in-process server and DAO. Tenancy and request attribution use fixture implementations; no gateway or provider.
- **Execution:** `fulfillment-service/internal/cmd/service/start/grpcserver/storage_tier_resolver_test.go`
- **Evidence:** `TestRegisterServers / Storage tier resolver / preserves resolution errors and rejects deleting tiers / missing backend` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/cmd/service/start/grpcserver/storage_tier_resolver_test.go#L137)).
- **Selector:** `go test ./internal/cmd/service/start/grpcserver -run '^TestRegisterServers$' -ginkgo.focus='^Storage tier resolver preserves resolution errors and rejects deleting tiers missing backend$'` from `fulfillment-service` in OSAC.

**Preconditions.** In the isolated resolver fixture, use an active tier row whose synthetic backend reference cannot be resolved.

1. Resolve the tier using the real DAO and transaction.
2. Inspect the returned status and diagnostic.

**Expected results.** The result is Unknown and identifies failure to look up the storage backend.

#### TC-SCP-09: Migration creates the active Volume table

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Volume persistence migration](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1058)
- **Dependencies:** Real PostgreSQL test container and migration-specific database snapshot. No fulfillment API or provider.
- **Execution:** `fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go`
- **Evidence:** `TestMigrations / Create volumes tables / Creates the expected tables / volumes` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go#L51)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Create volumes tables Creates the expected tables volumes$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use PostgreSQL at the version immediately preceding migration 95.

1. Apply migration 95.
2. Insert a fixture volume into the active table and look up its ID.

**Expected results.** The insert succeeds and the active table has exactly one row for that ID.

#### TC-SCP-10: Vendor provisioning failure updates the hub Volume phase

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Operator vendor provisioning](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1061)
- **Dependencies:** Real Kubernetes API/etcd and Volume reconciler. Vendor CSI controller is an in-process double.
- **Execution:** `osac-operator/internal/controller/volume_controller_test.go`
- **Evidence:** `TestControllers / VolumeReconciler / should set phase to Failed when vendor provisioning fails` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/volume_controller_test.go#L351)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^VolumeReconciler should set phase to Failed when vendor provisioning fails$'` from `osac-operator` in OSAC.

**Preconditions.** Create a hub Volume in the operator envtest harness with a vendor implementation double configured to fail.

1. Run the Volume reconciler.
2. Read the stored Volume phase.

**Expected results.** The Volume records Failed after the vendor error.

#### TC-SCP-11: Transient hub Create returns an error and leaves the Volume CREATING

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Hub Volume reconciliation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1055)
- **Dependencies:** In-memory hub Kubernetes client with a scripted Create error and a mocked fulfillment client.
- **Execution:** `fulfillment-service/internal/controllers/volume/volume_reconciler_function_test.go`
- **Evidence:** `TestVolume / Kubernetes validation error handling / requeues without marking FAILED on transient K8s Create error` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/controllers/volume/volume_reconciler_function_test.go#L1166)).
- **Selector:** `go test ./internal/controllers/volume -run '^TestVolume$' -ginkgo.focus='^Kubernetes validation error handling requeues without marking FAILED on transient K8s Create error$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use a CREATING Volume fixture with a Kubernetes client that returns a synthetic transient Create error.

1. Call the fulfillment Volume reconciliation task.
2. Inspect the error, failure-update calls and fixture state.

**Expected results.** It returns the Create error, records no FAILED update and leaves state CREATING.

#### TC-SCP-12: Duplicate active Volume name returns REST conflict

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [HTTP duplicate status](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1054)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Gap:** The server-backed duplicate test checks gRPC AlreadyExists. The fulfillment REST suites do not verify a duplicate Volume's HTTP status.

**Preconditions.** Create a fixture volume through the authenticated REST API under a synthetic tenant.

1. Submit a second Create with the same tenant and name.
2. Read the HTTP response.

**Expected results.** The response is 409 Conflict.

#### TC-SCP-13: CSI polling works against a real fulfillment service

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [CSI availability polling](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1066)
- **Dependencies:** Real Kind CSI controller, fulfillment API and PostgreSQL. Vendor outcome is controlled; no live storage target.
- **Gap:** The isolated polling test uses a fulfillment double. The real service boundary has no verified equivalent.

**Preconditions.** Use a Kind deployment with real CSI controller and fulfillment, and a test vendor that can hold provisioning pending.

1. Request a synthetic volume and release the pending outcome.
2. Observe both API state and CSI response.

**Expected results.** CSI returns the volume context only after the real fulfillment row becomes AVAILABLE.

#### TC-SCP-14: Migration creates a writable Volume archive table

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Archived Volume persistence](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1058)
- **Dependencies:** Real PostgreSQL test container and migration-specific database snapshot. No fulfillment API or provider.
- **Execution:** `fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go`
- **Evidence:** `TestMigrations / Create volumes tables / Creates the archived_volumes table` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go#L54)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Create volumes tables Creates the archived_volumes table$'` from `fulfillment-service` in OSAC.

**Preconditions.** Use PostgreSQL at the version preceding migration 95.

1. Apply migration 95.
2. Insert a timestamped fixture row into archived_volumes and query it.

**Expected results.** The archive contains exactly one row for the fixture ID.

#### TC-SCP-15: Migration protects active Volume ID, name and tenant from updates

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Volume immutability trigger](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1058)
- **Dependencies:** Real PostgreSQL test container and migration-specific database snapshot. No fulfillment API or provider.
- **Execution:** `fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go`
- **Evidence:** `TestMigrations / Create volumes tables / Enforces immutability of id, name, tenant, and project` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/internal/database/migrations/95_create_volumes_tables_test.go#L151)).
- **Selector:** `go test ./internal/database/migrations -run '^TestMigrations$' -ginkgo.focus='^Create volumes tables Enforces immutability of id, name, tenant, and project$'` from `fulfillment-service` in OSAC.

**Preconditions.** Apply migration 95 and insert the synthetic active Volume.

1. Attempt to change each immutable value individually in the database fixture.

**Expected results.** Changes to ID, name and tenant each fail with PostgreSQL state Z0001.

#### TC-SCP-16: Feedback sends DELETING for a deleting hub Volume

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Operator feedback state mapping](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1062)
- **Dependencies:** In-memory Kubernetes client and a real in-process gRPC transport to a fake fulfillment server. No envtest API, PostgreSQL or vendor.
- **Execution:** `osac-operator/internal/controller/volume_feedback_controller_test.go`
- **Evidence:** `TestControllers / VolumeFeedbackController / deletion handling / should sync Phase=Deleting to state=DELETING during deletion` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/volume_feedback_controller_test.go#L362)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^VolumeFeedbackController deletion handling should sync Phase=Deleting to state=DELETING during deletion$'` from `osac-operator` in OSAC.

**Preconditions.** Create a hub Volume with the feedback and vendor finalizers and a remote fixture in AVAILABLE.

1. Mark the hub object deleting with phase Deleting, then run feedback.
2. Inspect the private Volume update sent to the client double.

**Expected results.** The update reports state DELETING while the vendor finalizer is still present.

#### TC-SCP-17: CSI DeleteVolume forwards the synthetic ID to fulfillment

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [CSI controller DeleteVolume](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1067)
- **Dependencies:** Mock fulfillment client. No vendor or deployed CSI endpoint.
- **Execution:** `osac-csi-driver/pkg/driver/controller_test.go`
- **Evidence:** `TestDeleteVolume_Success` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-csi-driver/pkg/driver/controller_test.go#L644)).
- **Selector:** `go test ./pkg/driver -run '^TestDeleteVolume_Success$'` from `osac-csi-driver` in OSAC.

**Preconditions.** Use the in-memory controller with a recording fulfillment client programmed to succeed.

1. Call DeleteVolume for vol-1.
2. Inspect the recorded client ID.

**Expected results.** The call succeeds and sends vol-1 to fulfillment without waiting on a provider.

#### TC-SCP-18: CSI resolves the configured vendor socket from the fixture volume context

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [CSI node socket routing](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1068)
- **Dependencies:** Pure socket lookup using a fixture map. No network or actual socket is opened.
- **Execution:** `osac-csi-driver/pkg/driver/node_test.go`
- **Evidence:** `TestResolveVendorSocket/valid backend` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-csi-driver/pkg/driver/node_test.go#L136)).
- **Selector:** `go test ./pkg/driver -run '^TestResolveVendorSocket$/^valid_backend$'` from `osac-csi-driver` in OSAC.

**Preconditions.** Use a NodeServer with the synthetic netapp backend mapped to its fixture socket.

1. Resolve a volume context naming the configured backend.

**Expected results.** The helper returns the configured netapp socket path.

#### TC-SCP-19: Deployed CaaS PVC provisions a VAST volume, mounts it and cleans up

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [VAST PVC lifecycle and mount](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1085)
- **Dependencies:** Requires deployed hub and tenant Kubernetes, OSAC CSI, fulfillment, VAST plugin and dedicated test backend. No provider double.
- **Gap:** OSAC storage E2E verifies cluster readiness and tenant classes. CSI suites use test doubles and do not exercise deployed VAST PVC I/O and cleanup.

**Preconditions.** Use an isolated CaaS fixture with OSAC CSI, the VAST node plugin, and a provider-backed synthetic StorageClass.

1. Create a PVC through the fixture StorageClass and wait for binding.
2. Inspect the hub Volume and inventory linkage, then mount the PVC in a synthetic pod and round-trip fixture bytes.
3. Delete the pod and PVC, then observe backend and inventory state.

**Expected results.** The PVC binds and its hub and inventory IDs correspond. The pod reads its own fixture bytes. On deletion the backend fixture disappears and inventory reaches its documented deleted state.

#### TC-SCP-20: A PVC using an absent StorageClass remains Pending

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Missing StorageClass](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1088)
- **Dependencies:** Requires a deployed tenant Kubernetes and CSI setup with isolated storage fixtures. No provider double.
- **Gap:** The deployed storage specs do not submit negative PVC fixtures. CSI sanity exercises driver RPCs without Kubernetes PVC scheduling.

**Preconditions.** Use an isolated namespace in the deployed CaaS fixture and reserve an unused StorageClass name.

1. Submit a synthetic PVC referencing the unused class.
2. Inspect its phase and volume binding within the fixture observation window.

**Expected results.** The PVC stays Pending and no volume is bound.

#### TC-SCP-21: A bound CSI PVC and PV carry their Volume reference

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [PVC and PV annotation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-2872-storage-control-plane/design.md#L1089)
- **Dependencies:** Requires tenant and hub Kubernetes, deployed CSI and fulfillment, and a dedicated storage provider fixture.
- **Gap:** The deployed storage suites inspect readiness and class resolution without a bound OSAC CSI PVC and PV.

**Preconditions.** Use a deployed tenant cluster with the supported OSAC-managed fixture class.

1. Create and bind a PVC.
2. Read the PVC, PV and its associated OSAC Volume.

**Expected results.** Both objects carry the documented Volume annotation and its value identifies the matching OSAC Volume.
