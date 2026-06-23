# StorageTier API

| Field       | Value   |
|-------------|---------|
| Author(s)   | Roy Golan rgolan@redhat.com |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1110 |
| Date        | 2026-06-22 |

## 1. Problem Statement

OSAC has no API-managed catalog of storage tier offerings. Tier configuration flows through environment variables (`STORAGE_TIERS`) and Kubernetes label conventions on StorageClasses (`osac.openshift.io/storage-tier`). Neither mechanism exposes tiers through the OSAC API, captures QoS properties (IOPS limits, encryption), or establishes referential relationships with registered storage backends (StorageBackend, OSAC-1111). Without a tier abstraction, all tenants get the same storage characteristics, and downstream workflows (Tenant Storage Onboarding, Resource Creation) have no mechanism to determine which StorageClasses to create or what QoS policies to apply.

[StorageBackend](../storage-backend-osac-1111/prd.md) (OSAC-1111) registers infrastructure — endpoints, credentials, provider type. The [tenant-storage-tiers EP](../tenant-storage-tiers/README.md) introduced label-based tier resolution — which StorageClass serves a given tier for a given tenant. The missing layer is a tier definition that binds a named offering to registered backends with QoS properties, enabling Cloud Provider Admins to compose differentiated storage offerings (e.g., fast, standard, archive) and making them queryable by internal services.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can create, list, update, and delete storage tier offerings through the OSAC private gRPC API.
- Each StorageTier binds a named offering to one or more registered StorageBackends with per-backend protocol and provider-neutral QoS properties (bandwidth, quota, encryption), establishing a formal relationship between offerings and infrastructure.
- StorageTier replaces environment-variable-based tier configuration (`STORAGE_TIERS`) with API-managed definitions that are queryable, auditable, and validated against registered backends.
- Tier definitions are queryable by internal services (osac-operator, OSAC Storage Controller) to drive downstream workflows such as Tenant Storage Onboarding and Resource Creation.
- The StorageTier entity follows the same DB-backed private API pattern as StorageBackend and NetworkClass.
- StorageTier provides the referencing entity for tenant storage onboarding (OSAC-23), where the OSAC Storage Controller reads tier definitions to determine which backends and QoS parameters apply to a tenant.

### 2.3 Non-Goals

- Tenant-facing public StorageTier API — tenants see their assigned tiers through the Tenant CR status. A public read-only tier catalog may be added in a future enhancement.
- Automatic tier-to-tenant assignment during onboarding — managed by the OSAC Storage Controller (OSAC-23).
- CSI driver installation or StorageClass lifecycle on target clusters — part of the tenant storage onboarding flow (OSAC-23).
- Quota enforcement per tier.
- Per-tier capacity tracking or utilization monitoring — storage observability roadmap.
- StorageTier as a Kubernetes CRD — consistent with StorageBackend and NetworkClass. A CRD may be introduced in a future milestone.
- Advanced QoS policies and per-tenant entitlements — deferred to future milestones.
- Provider-specific QoS validation — QoS properties are stored as declared by the admin. Validation against provider capabilities is a future enhancement.
- CSI-level volume interception — today QoS enforcement flows through StorageClass parameters and provider-side policies (e.g., VAST QoS policies). A future CSI proxy layer (see `.planning/storage/csi-proxy-architecture.md`) could resolve QoS from the tier definition at volume-creation time, fully decoupling enforcement from Kubernetes StorageClass immutability. That architecture is out of scope for this work.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** The fulfillment-service must expose a `StorageTiers` gRPC service under `osac.private.v1` with Create, Get, List, Update, and Delete RPCs.
- **FR-2:** All CRUD RPCs must include HTTP annotations for REST access via grpc-gateway (POST, GET, GET, PATCH, DELETE).
- **FR-3:** `CreateStorageTier` must accept a tier name, optional description, and one or more backend associations. Each backend association references a StorageBackend by ID, declares the storage protocol (`nfs` or `block`), and declares provider-neutral QoS properties: maximum read bandwidth (MB/s), maximum write bandwidth (MB/s), quota (bytes), and encryption enabled. The tier must be created with initial state `ACTIVE`.
- **FR-4:** `ListStorageTiers` must support pagination (`offset`/`limit`), CEL-based filtering, and SQL-like ordering, following the established OSAC List API pattern.
- **FR-5:** `UpdateStorageTier` must support partial updates — including backend association QoS properties — and optimistic concurrency control to prevent conflicting writes. QoS properties (e.g., IOPS limits) are mutable because the underlying storage provider policies (e.g., VAST QoS policies) can be updated in-place, and changes take effect for both existing and new volumes without StorageClass recreation.
- **FR-6:** `DeleteStorageTier` must permanently delete the tier. Delete must be rejected if any Tenant references the tier (referential integrity).
- **FR-7:** `CreateStorageTier` and `UpdateStorageTier` must validate that all referenced StorageBackend IDs exist. Referencing a non-existent backend must return an error.
- **FR-8:** Tier names must be unique among active (non-deleted) tiers, allowing name reuse after deletion.
- **FR-9:** StorageTier state must include `ACTIVE` (tier available for new tenant assignments). Additional states (`DEPRECATED` for retiring tiers with existing tenant assignments) are deferred to a later phase.
- **FR-10:** Deleting a StorageBackend (OSAC-1111) must be rejected if any StorageTier references it. This requirement is already captured in OSAC-1111 FR-6 and is restated here to confirm the bidirectional referential integrity contract.

### 3.2 Non-Functional Requirements

- **NFR-1:** The StorageTier entity must track creation and modification timestamps for auditability.
- **NFR-2:** QoS properties are provider-neutral: protocol (enum: `nfs`, `block`), max read bandwidth (integer, MB/s), max write bandwidth (integer, MB/s), quota (integer, bytes), and encryption (boolean). The design document maps these to provider-specific parameters (e.g., VAST QoS policy `static_limits`, VAST view quota). Provider-specific fields are not exposed in the StorageTier API.

## 4. Acceptance Criteria

- [ ] `CreateStorageTier` creates a tier with `ACTIVE` state and backend associations with protocol and QoS properties (bandwidth, quota, encryption), and returns the created object with a generated ID.
- [ ] `CreateStorageTier` rejects tiers that reference non-existent StorageBackends.
- [ ] `GetStorageTier` retrieves a tier by ID with all fields populated, including backend associations and their QoS properties.
- [ ] `ListStorageTiers` returns paginated results and supports filtering by field values (e.g., by state, by referenced backend).
- [ ] `UpdateStorageTier` applies partial updates — including QoS property changes on backend associations — without modifying unspecified fields.
- [ ] `UpdateStorageTier` rejects concurrent conflicting writes.
- [ ] `DeleteStorageTier` deletes the tier. Delete is rejected if any Tenant references the tier.
- [ ] `DeleteStorageBackend` (OSAC-1111) is rejected if any StorageTier references the backend.
- [ ] All CRUD RPCs are accessible via both gRPC and REST endpoints.
- [ ] Integration tests cover the full CRUD lifecycle, backend reference validation, pagination, filtering, and concurrency control.

## 5. Assumptions

- StorageTier is platform-scoped (not tenant-scoped), managed exclusively by Cloud Provider Admins. Tenant isolation applies at the tier-assignment level during tenant onboarding (OSAC-23), not at the tier-definition level.
- QoS properties are provider-neutral abstractions: protocol, max read/write bandwidth, quota, and encryption. The design document is responsible for mapping these to provider-specific parameters (e.g., VAST `qos_policy` name and `static_limits`). Additional properties (IOPS, latency targets, redundancy) can be added as proto fields without breaking changes.
- QoS property updates on a StorageTier propagate to the storage provider's policy (e.g., VAST QoS policy) and take effect for existing and new volumes. However, certain properties that are baked into Kubernetes StorageClass parameters (e.g., encryption settings, QoS policy *name*) require StorageClass recreation to take effect for new volumes — existing volumes are unaffected. A future CSI proxy layer could decouple QoS enforcement from StorageClass immutability entirely, but that is out of scope (see `.planning/storage/csi-proxy-architecture.md`).
- StorageTier is a catalog entity — it declares which backends can serve a tier and with what QoS properties. Backend selection for a specific tenant (which backend within the tier to provision on) is determined at the tier-to-tenant assignment layer (OSAC-23), not by the StorageTier API.
- StorageTier replaces the `STORAGE_TIERS` environment variable. Migration from env-var-based configuration to API-managed tiers is a one-time operation.
- Automatic StorageClass refresh when QoS properties change on a StorageTier is not in v0.1 scope. StorageClass lifecycle management (creation, recreation on parameter drift) is handled by the OSAC Storage Controller (OSAC-23).

## 6. Dependencies

- **StorageBackend (OSAC-1111):** StorageTier references StorageBackend by ID. StorageBackend must be implemented first. Backend reference validation (FR-7) and referential integrity on backend deletion (FR-10) depend on the StorageBackend entity existing.
- **Tenant storage onboarding (OSAC-23):** The OSAC Storage Controller consumes StorageTier definitions when provisioning tenant storage. StorageTier can be implemented and deployed independently, but the full onboarding flow requires both.

## 7. Risks

### 7.1 QoS update propagation limits

- **Owner:** Storage architect
- **Mitigation:** QoS limit changes (IOPS, bandwidth) propagate to the storage provider policy and take effect immediately. However, changes to properties embedded in Kubernetes StorageClass parameters (encryption settings, QoS policy name) require StorageClass recreation — only new volumes pick up the change. The OSAC Storage Controller (OSAC-23) must handle StorageClass recreation when the onboarding flow detects parameter drift. A future CSI proxy layer would eliminate this limitation by resolving QoS at volume-creation time from the tier definition rather than from static StorageClass parameters.

### 7.2 Multi-backend tier complexity

- **Owner:** Storage architect
- **Mitigation:** A tier can reference multiple backends, but StorageTier is a catalog — it declares which backends *can* serve this tier, not which backend a specific tenant *will* use. Backend selection for a tenant happens at the tier-to-tenant assignment layer (OSAC-23). This keeps the StorageTier API simple and pushes selection logic (affinity, capacity, admin preference) to the onboarding flow where tenant context is available.
