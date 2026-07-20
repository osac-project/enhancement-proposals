# StorageBackend API

| Field       | Value   |
|-------------|---------|
| Author(s)   | Roy Golan rgolan@redhat.com |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1111 |
| Date        | 2026-06-04 |

## 1. Problem Statement

OSAC has no API-managed inventory of storage backends. Storage configuration flows through Ansible Automation Platform extra vars (`VAST_ENDPOINT`, `VAST_USERNAME`, `VAST_PASSWORD`), making backends opaque to the OSAC data model. Cloud Provider Admins cannot discover registered backends, rotate credentials without redeploying the fulfillment-service, or inspect backend operational status through the OSAC API. This blocks the platform from composing tiered storage offerings (StorageTier, OSAC-1110) because there is no registered infrastructure to reference.

Three prior enhancements addressed tenant-to-StorageClass resolution (`tenant-specific-storageclasses`, `tenant-storage-tiers`) but left the infrastructure layer — which backends exist, their endpoints, their credentials, and their health — invisible.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can register, list, update, and decommission storage backends through the OSAC private gRPC API without modifying environment variables or Ansible playbooks.
- Cloud Provider Admins can rotate storage backend credentials by updating the credential fields, without redeploying the fulfillment-service.
- Cloud Provider Admins can inspect backend operational status (state, model, firmware version) through the API to verify availability and troubleshoot connectivity.
- The StorageBackend entity follows the same DB-backed private API pattern as NetworkClass and PublicIPPool, maintaining consistency across OSAC infrastructure entities.
- The StorageBackend entity provides the foundation for future StorageTier composition (OSAC-1110), where tiers reference registered backends.

### 2.3 Non-Goals

- Full StorageTier design — OSAC-1110 is referenced in the design document's appendix (entity model + reconciliation flow only). Full design is a separate EP.
- Provider-specific integration beyond VAST — the `provider` field is generic ("vast", "ceph", "pure"). Provider-specific logic (model auto-detection, credential validation) is implemented incrementally, VAST first.
- Storage observability and monitoring — metrics, health checks, and capacity tracking are covered by the "OSAC Storage Observability" roadmap item.
- Automatic backend discovery — backends are explicitly registered by Cloud Provider Admins. No auto-discovery from infrastructure management systems.
- StorageBackend as a Kubernetes CRD — the entity is managed through the OSAC private API, not as a cluster-scoped Kubernetes resource. Reconciliation is triggered by Tenant onboarding, not by backend registration.
- CSI proxy or volume-level interception — intercepting CSI `CreateVolume` calls to inject OSAC metadata is a separate future effort (see `.planning/storage/csi-proxy-architecture.md`).

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** The fulfillment-service must expose a `StorageBackends` gRPC service under `osac.private.v1` with Create, Get, List, Update, and Delete RPCs.
- **FR-2:** All CRUD RPCs must include HTTP annotations for REST access via grpc-gateway (POST, GET, GET, PATCH, DELETE).
- **FR-3:** `CreateStorageBackend` must accept provider type, management endpoint (host + optional port), credentials (username and password), and optional description. The backend must be created with initial state `READY`.
- **FR-4:** `ListStorageBackends` must support pagination (`offset`/`limit`), CEL-based filtering, and SQL-like ordering. This follows the established OSAC List API pattern used by all existing entities (NetworkClass, Clusters, ComputeInstances, Roles, etc.).
- **FR-5:** `UpdateStorageBackend` must support partial updates (only specified fields are modified) and optimistic concurrency control to prevent conflicting writes.
- **FR-6:** `DeleteStorageBackend` must perform a soft delete. Deleted backends must be excluded from List results but preserved for audit and future references from StorageTier.
- **FR-7:** Cloud Provider Admins must be able to update backend operational metadata (model, firmware_version) and status message via the standard `Update` RPC. No Signal RPC is needed — StorageBackend has no reconciler or controller.
- **FR-8:** Backend state must include `READY` (backend registered and available). Additional states will be introduced as needed when reconciliation or health probing capabilities are added in future phases. [User]
- **FR-9:** Backend names must be unique among active (non-deleted) backends, allowing name reuse after decommission.
- **FR-10:** Credentials (username, password) must be stored inline in the StorageBackend entity, consistent with how all existing OSAC entities store credentials (break_glass_credentials, identity_provider, user, cluster_template, hub). Credentials must be excluded from the public API.

### 3.2 Non-Functional Requirements

- **NFR-1:** The StorageBackend entity must track creation and modification timestamps for auditability.
- **NFR-2:** Provider-specific credential schemas are not validated by the StorageBackend API. The credential content is opaque; validation is the responsibility of the provider-specific integration layer.

## 4. Acceptance Criteria

- [ ] `CreateStorageBackend` creates a backend with state `READY` and returns the created object with a generated ID.
- [ ] `GetStorageBackend` retrieves a backend by ID with all fields populated (including status).
- [ ] `ListStorageBackends` returns paginated results, supports filtering by field values (e.g., by provider), and excludes soft-deleted records.
- [ ] `UpdateStorageBackend` applies partial updates without modifying unspecified fields.
- [ ] `UpdateStorageBackend` rejects concurrent conflicting writes.
- [ ] `DeleteStorageBackend` soft-deletes the backend. Subsequent List calls exclude the deleted backend.
- [ ] All CRUD RPCs are accessible via both gRPC and REST endpoints.
- [ ] Integration tests cover the full CRUD lifecycle, pagination, filtering, and concurrency control.

## 5. Assumptions

- The management cluster (hub) is the same cluster that runs the fulfillment-service and creates HostedClusters via Hosted Control Planes. The terms "hub" (ACM terminology) and "management cluster" refer to the same cluster.
- StorageClasses are associated with tenants and tiers by naming convention, not by Kubernetes labels. The prior EP label-based approach (`osac.openshift.io/tenant`, `osac.openshift.io/storage-tier`) is superseded.
- Credentials are provided by the Cloud Provider Admin during backend registration and stored inline in the database, consistent with all existing OSAC credential patterns.

## 6. Dependencies

- **StorageTier (OSAC-1110):** StorageTier entities will reference StorageBackend by ID. StorageTier design depends on StorageBackend but not vice versa. StorageBackend can be implemented and deployed independently.
- **Tenant onboarding reconciliation:** Future reconciliation flow (resolve tier → backend(s) → install CSI driver on target cluster → create tenant-scoped StorageClass on target cluster) depends on both StorageBackend and StorageTier being implemented. CSI drivers and StorageClasses are installed on target clusters (VMaaS/CaaS), not the management cluster. Not in scope for this work.

## 7. Risks

### 7.1 Multi-provider maintenance burden

- **Owner:** Storage architect
- **Mitigation:** Start with VAST as the reference implementation. Establish a provider abstraction pattern (interface or strategy pattern for backend validation and model detection) and document the provider integration process for future contributors.

### 7.2 Soft-delete name reuse ambiguity

- **Owner:** Storage architect
- **Mitigation:** Name reuse after soft deletion is allowed (FR-9). If a future StorageTier references the decommissioned backend by ID (not name), there is no conflict. Document this behavior in the API reference.

## 8. Open Questions

### 8.1 Should credential rotation trigger re-validation?

- **Owner:** Storage architect
- **Impact:** FR-3, FR-8. When credentials are updated via `UpdateStorageBackend`, should the backend state change to indicate re-validation is needed? Deferred until additional states (e.g., `PENDING`) are introduced in a future phase.
