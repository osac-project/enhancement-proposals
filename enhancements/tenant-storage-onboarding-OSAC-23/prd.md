# Rework Tenant Storage Onboarding

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo, Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-23 |
| Date        | 2026-06-10 |

## 1. Problem Statement

Storage provisioning logic is embedded in the Tenant controller. Backend setup, StorageClass resolution, AAP job tracking, and storage readiness are all handled within a single controller alongside namespace creation and tenant lifecycle management. Any change to storage onboarding risks breaking tenant state transitions, and supporting different storage workflows per delivery model (VMaaS, CaaS, BMaaS) requires branching logic inside the Tenant controller. Storage issues cannot be diagnosed independently from tenant status, and the storage working group cannot iterate on storage onboarding without coordinating every change with the core tenant lifecycle.

## 2. Goals and Non-Goals

### 2.1 Goals

- Storage lifecycle operates independently from tenant lifecycle. Storage provisioning, readiness tracking, and teardown are managed by a dedicated OSAC Storage Controller without affecting tenant state transitions.
- The OSAC Storage Controller owns all storage-related conditions and status fields on the Tenant CR using the condition ownership pattern. The Tenant controller has zero storage responsibilities.
- The OSAC Storage Controller is the single entry point for all tenant storage reconciliation.
- AAP storage playbooks are split into distinct lifecycle actions (create-storage-backend, create-cluster-storage, delete-cluster-storage, delete-storage-backend) so that each can be triggered independently by the controller.
- Storage readiness is observable via `kubectl get tenant` print columns showing backend and class readiness status.

### 2.2 Non-Goals

- StorageBackend API and registration automation
- StorageTier API
- Tier addition and removal workflows
- CaaS Tenant Storage Setup: Stage 2 trigger logic for CaaS clusters is a separate PRD
- VAST support for CaaS
- Per-cluster storage resource on target clusters for tenant admin visibility
- Fulfillment-service API or proto changes for storage state visibility

## 3. Requirements

OSAC tenant storage provisioning uses a two-stage model:

- **Stage 1 (backend setup)** runs at tenant onboarding. It creates the tenant's organization on the storage appliance, provisions VIP pools, credentials, and per-tier views (each tier has its own view for a tenant), and stores per-tenant credentials in a hub Secret.
- **Stage 2 (cluster-side setup)** runs after Stage 1 completes. AAP playbooks install the CSI operator (if needed) and create per-tenant StorageClasses and CSI credentials on the VMaaS target cluster.

For VMaaS, both stages run at tenant onboarding. For CaaS, Stage 2 runs after the cluster is provisioned (ClusterOrder reaches Ready), covered by a separate PRD.

This PRD covers the controller and both stages. Stage 1 and Stage 2 must be implemented as separate operations in the controller to avoid coupling that would need to be untangled when CaaS support is added.

### 3.1 Controller Foundation

These requirements establish the OSAC Storage Controller as the owner of all storage-related state on the Tenant CR.

- **FR-1:** The OSAC Storage Controller owns all storage-related conditions and status on the Tenant CR:
  - Backend readiness: tracks whether per-tenant resources are provisioned on each configured storage backend. Set to True when Stage 1 completes successfully for all backends, False on failure with a descriptive reason. Per-backend detail (name, provider, status, error) is available in the Tenant status.
  - Cluster storage readiness: tracks whether StorageClasses and CSI drivers are installed on each cluster associated with the tenant. For this PRD, this covers the VMaaS target cluster only. Per-cluster detail (cluster name, readiness, reason) is available in the Tenant status.
  - The list of the tenant's resolved StorageClass names, using the same tier resolution algorithm (tenant-specific entry with Default fallback) previously owned by the Tenant controller.
  - AAP job tracking for in-flight storage operations, written to the shared `status.jobs` field on the Tenant CR (also used by other controllers such as networking).

  Storage readiness is observable via `kubectl get tenant`. Exact condition names, status structure, and API details are specified in the design document.

- **FR-2:** The Tenant controller does not run any storage logic. It manages namespace creation, UDN reconciliation, and tenant lifecycle only. All storage-related conditions and status fields are managed exclusively by the OSAC Storage Controller.

- **FR-3:** The ComputeInstance controller continues to read the tenant's resolved StorageClasses from the Tenant CR. No changes are required to the ComputeInstance controller.

- **FR-4:** The OSAC Storage Controller checks the `osac.openshift.io/management-state` annotation and skips steady-state reconciliation when set to Unmanaged. Finalizer and deletion handling must still run to prevent Tenants from being stuck in Terminating.

### 3.2 Storage Onboarding Workflow

These requirements define the onboarding, readiness, and teardown workflows managed by the OSAC Storage Controller.

- **FR-5 (Stage 1):** The OSAC Storage Controller watches Tenant resources. When a Tenant reaches Ready (namespace exists), the controller begins backend setup: checking for the tenant's hub Secret and triggering backend provisioning via AAP (`osac-create-tenant-storage-backend`) if absent. When the hub Secret exists and is valid, Stage 1 is complete and the controller sets the backend readiness condition to True on the Tenant. If the AAP job fails, the condition is set to False with a reason reflecting the failure and the controller retries with backoff.

- **FR-6 (Stage 2):** After Stage 1 completes, the OSAC Storage Controller triggers cluster-side setup via AAP (`osac-create-tenant-cluster-storage`) to install the CSI operator and create per-tenant StorageClasses on the VMaaS target cluster (remote or hub). The controller discovers installed StorageClasses using the `osac.openshift.io/tenant` label and populates the resolved StorageClass list on the Tenant. When discovery confirms all expected StorageClasses are present, the controller sets the class readiness condition to True on the Tenant.

- **FR-7:** The OSAC Storage Controller places a finalizer on the Tenant CR to block deletion until storage teardown completes. On Tenant deletion, the teardown sequence is: first, trigger cluster-side cleanup via AAP (`osac-delete-tenant-cluster-storage`) to remove StorageClasses, CSI Secrets, and VolumeSnapshotClasses; then, trigger backend teardown via AAP (`osac-delete-tenant-storage-backend`) to clean up storage provider resources (VAST tenant, views, quotas) and the per-tenant hub Secret. The finalizer is removed only after both steps complete successfully. If teardown fails, the finalizer remains in place and the Tenant stays in Terminating until the issue is resolved.

- **FR-8:** AAP playbooks are split into four lifecycle actions: `osac-create-tenant-storage-backend` (Stage 1 backend setup), `osac-create-tenant-cluster-storage` (Stage 2 cluster-side StorageClasses and CSI), `osac-delete-tenant-cluster-storage` (cluster-side resource removal during deletion), and `osac-delete-tenant-storage-backend` (backend teardown).

- **FR-9:** The OSAC Storage Controller establishes a watch on ClusterOrder resources to prepare for CaaS support. No action is taken on ClusterOrder events in this scope. CaaS Stage 2 trigger logic is defined in a separate PRD.

### 3.3 Non-Functional Requirements

- **NFR-1:** Admin credentials (VAST endpoint, username, password) are mounted as environment variables in the AAP automation pod from a pre-configured Secret, cleared from playbook memory after use, and never accessed by the controller.

- **NFR-2:** Per-tenant credentials are stored in a Secret in the osac-system namespace, managed exclusively by the OSAC Storage Controller. These Secrets are used by downstream cluster-side setup workflows.

- **NFR-3:** The AAP playbook changes and operator changes must be deployed together. The `osac-create-tenant-storage-backend` playbook replaces the previous combined playbook that executed both Stage 1 and Stage 2. Deploying the AAP changes without the operator changes breaks existing Tenant controller provisioning.

- **NFR-4:** Controller logs and Kubernetes events must not expose credentials, Secret contents, or sensitive AAP parameters during any storage operation (provisioning, teardown, or failure recovery).

## 4. Acceptance Criteria

**Controller Foundation**
- [ ] OSAC Storage Controller owns storage-related conditions and status fields on the Tenant CR
- [ ] Tenant controller has no storage-related logic
- [ ] ComputeInstance controller reads StorageClasses from Tenant status (no change required)
- [ ] `kubectl get tenant` displays storage readiness columns
- [ ] OSAC Storage Controller skips steady-state reconciliation when `osac.openshift.io/management-state` is set to Unmanaged (finalizer and deletion handling still run)

**Stage 1 (Backend Setup)**
- [ ] OSAC Storage Controller watches Tenant resources and begins storage onboarding when Tenant reaches Ready
- [ ] OSAC Storage Controller triggers AAP backend provisioning (`osac-create-tenant-storage-backend`) when hub Secret is absent
- [ ] Backend readiness condition is set to True on Tenant when Stage 1 completes
- [ ] Backend readiness condition is set to False with reason on AAP job failure, controller retries with backoff

**Stage 2 (Cluster-Side Setup)**
- [ ] After Stage 1 completes, OSAC Storage Controller triggers cluster-side setup (`osac-create-tenant-cluster-storage`) on the VMaaS target cluster (remote or hub)
- [ ] OSAC Storage Controller discovers StorageClasses using `osac.openshift.io/tenant` label and populates the resolved StorageClass list
- [ ] Class readiness condition is set to True when StorageClasses are confirmed on the VMaaS target cluster
- [ ] ClusterOrder watch is established (no action taken on events in this scope)

**Teardown**
- [ ] OSAC Storage Controller places a finalizer on the Tenant CR to block deletion until teardown completes
- [ ] On Tenant deletion, controller triggers cluster-side cleanup (`osac-delete-tenant-cluster-storage`) then backend teardown (`osac-delete-tenant-storage-backend`)
- [ ] Finalizer is removed only after both cleanup steps complete successfully

**AAP Playbooks**
- [ ] AAP playbooks split into four job templates: `osac-create-tenant-storage-backend`, `osac-create-tenant-cluster-storage`, `osac-delete-tenant-cluster-storage`, `osac-delete-tenant-storage-backend`

**Testing**
- [ ] Unit tests pass for the new OSAC Storage Controller and updated Tenant controller
- [ ] E2E tests validate the full storage onboarding lifecycle (Stage 1 and Stage 2) against a VAST appliance

## 5. Assumptions

- AAP is the only provisioning backend for v0.1. No direct API provisioning path exists.
- VAST is the only storage provider for v0.1.
- Tier configuration via the STORAGE_TIERS environment variable is sufficient for this PRD. The StorageTier API is a separate effort.
- StorageClasses are created by AAP playbooks (`osac-create-tenant-cluster-storage`). The OSAC Storage Controller discovers them using the `osac.openshift.io/tenant` label but does not create them directly. In development environments without access to a VAST appliance, StorageClasses may need to be created manually for testing.

## 6. Dependencies

- **Tenant CR**: The OSAC Storage Controller depends on the Tenant CR lifecycle. Storage onboarding begins when a Tenant reaches Ready. Tenant deletion triggers storage teardown.
- **osac-operator and osac-aap coordinated deployment**: Changes span both repos and must be merged and deployed together. Deploying one without the other breaks tenant storage provisioning.

## 7. Risks

None. The project is pre-GA — breaking changes are expected and acceptable.

## 8. Open Questions

None at this time.
