# Rework Tenant Storage Onboarding

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo, Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-23 |
| Date        | 2026-06-09 |

## 1. Problem Statement

Storage provisioning logic is embedded in the Tenant controller and the Tenant CR's status fields. This includes backend setup, StorageClass resolution, AAP job tracking, and storage readiness. The Tenant CR holds storage state (StorageClasses, jobs, storage conditions) that conceptually belongs to storage lifecycle, not tenant lifecycle. Any change to storage onboarding risks breaking tenant state transitions, and supporting different storage workflows per delivery model (VMaaS, CaaS, BMaaS) requires branching logic inside a single controller. Storage issues cannot be diagnosed independently from tenant status, and the storage working group cannot iterate on storage onboarding without coordinating every change with the core tenant lifecycle.

## 2. Goals and Non-Goals

### 2.1 Goals

- Storage lifecycle operates independently from tenant lifecycle. Storage provisioning, readiness tracking, and teardown are managed by a dedicated controller without affecting tenant state transitions.
- Per-tenant storage state (provisioned tiers, provider resources, readiness) is observable as a standalone Kubernetes resource via `kubectl get tenantstorage`.
- The OSAC Storage Controller is the single entry point for all storage reconciliation, establishing the foundation for future storage capabilities (backend registration, CaaS cluster-side setup, resource creation storage).
- AAP storage playbooks are split into distinct lifecycle actions (create, ensure, cleanup, delete) so that each can be triggered independently by the controller.

### 2.2 Non-Goals

- StorageBackend API and registration automation
- StorageTier API
- CaaS Tenant Storage Setup
- VAST Support
- Fulfillment-service API or proto changes for storage state visibility
- Per-cluster storage resource on target clusters for tenant visibility. TenantStorage on the hub provides the CloudProviderAdmin view. A cluster-side resource for tenant admins to observe storage readiness on their own clusters is expected to follow in CaaS scope.

## 3. Requirements

OSAC tenant storage provisioning uses a two-stage model. Stage 1 (backend setup) runs at tenant onboarding: it creates the tenant's organization on the storage appliance, provisions VIP pools, credentials, per-tier views, and stores per-tenant credentials in a hub Secret. Stage 2 (cluster-side setup) runs when a target cluster has storage available: it discovers StorageClasses and, in future, installs CSI drivers on the target cluster. For VMaaS, both stages can run at tenant onboarding because the cluster already exists. For CaaS, Stage 2 runs after the cluster is provisioned (ClusterOrder reaches Ready). This PRD covers the controller, API, and both stages. Stage 1 and Stage 2 must be implemented as separate operations in the controller to avoid coupling that would need to be untangled when CaaS support is added.

### 3.1 Controller and API Foundation

These requirements establish the OSAC Storage Controller and TenantStorage API as the new home for all storage state and logic, decoupled from the Tenant controller.

- **FR-1:** A TenantStorage API captures per-tenant storage state. The spec contains a `tenantRef` field referencing the owning Tenant by name. The status contains phase (Progressing, Ready, Failed, Deleting), structured status conditions, AAP job tracking, and a per-cluster entries array. Each cluster entry tracks the cluster name, delivery model (VMaaS or CaaS), storage readiness, and resolved StorageClass names. For VMaaS, the cluster entry is populated at tenant onboarding. For CaaS, cluster entries are added when a ClusterOrder reaches Ready.

- **FR-2:** Remove storage-related fields from the Tenant API: StorageClasses status field, Jobs status field, StorageClassReady condition type, and storage-related print columns. Add a new `StorageBackendReady` condition type to the Tenant API, managed exclusively by the OSAC Storage Controller.

- **FR-3:** The Tenant controller does not run any storage logic. It manages namespace creation, UDN reconciliation, and tenant lifecycle only.

- **FR-4:** The ComputeInstance controller reads StorageClasses from the TenantStorage status instead of the Tenant status.

- **FR-5:** The OSAC Storage Controller checks the `osac.openshift.io/management-state` annotation and skips reconciliation when set to Unmanaged, consistent with all other OSAC controllers.

### 3.2 Storage Onboarding Workflow

These requirements define the onboarding, readiness, and teardown workflows that run on top of the foundation above.

- **FR-6 (Stage 1):** The OSAC Storage Controller watches Tenant resources. When a Tenant reaches Ready (namespace exists), the controller creates a TenantStorage resource and begins backend setup: checking for the tenant's hub Secret and triggering backend provisioning via AAP (`osac-create-tenant-storage`) if absent. When the hub Secret exists, Stage 1 is complete. The controller sets the `StorageBackendReady` condition on the Tenant so that storage readiness is visible through the primary Tenant resource.

- **FR-7 (Stage 2):** The OSAC Storage Controller discovers StorageClasses on the target cluster and populates the corresponding cluster entry in the TenantStorage status. Stage 2 is a separate operation from Stage 1. For VMaaS, Stage 2 runs at tenant onboarding because the cluster already exists and StorageClasses are manually pre-created. For CaaS, Stage 2 runs after ClusterOrder reaches Ready. Stage 2 does not automate StorageClass creation or CSI driver installation for v0.1.

- **FR-8:** On Tenant deletion, the OSAC Storage Controller triggers backend teardown via AAP (`osac-delete-tenant-storage`) to clean up storage provider resources (VAST tenant, views, quotas) and the per-tenant hub Secret, then deletes the TenantStorage resource. No owner reference is used. The controller explicitly watches Tenant deletion events.

- **FR-9:** AAP playbooks are split into four lifecycle actions: `osac-create-tenant-storage` (Stage 1 backend setup), `osac-ensure-tenant-storage` (Stage 2 cluster-side StorageClasses), `osac-cleanup-tenant-storage` (cluster-side resource removal), and `osac-delete-tenant-storage` (backend teardown).

- **FR-10:** The OSAC Storage Controller watches ClusterOrder resources. For VMaaS, this is not needed since Stage 2 runs at tenant onboarding. For CaaS, the watch enables Stage 2 triggering when ClusterOrder reaches Ready. Trigger logic is covered by CaaS Tenant Storage Setup.

### 3.3 Non-Functional Requirements

- **NFR-1:** Admin credentials (VAST endpoint, username, password) are ephemeral. They are mounted as environment variables in the AAP automation pod, cleared after use, and never persisted to Kubernetes.

- **NFR-2:** Per-tenant credentials are stored in a Secret in the osac-system namespace, managed exclusively by the OSAC Storage Controller. These Secrets are the handoff point to downstream workflows (VMaaS cluster-side setup, CaaS cluster-side setup).

- **NFR-3:** The AAP playbook changes and operator changes must be deployed together. The `osac-create-tenant-storage` playbook replaces the previous combined playbook that executed both Stage 1 and Stage 2. Deploying the AAP changes without the operator changes breaks existing Tenant controller provisioning.

## 4. Acceptance Criteria

**Controller and API Foundation**
- [ ] TenantStorage API is defined with spec (`tenantRef`) and status (phase, conditions, AAP job tracking, per-cluster entries array)
- [ ] Storage fields removed from Tenant API (StorageClasses, Jobs, StorageClassReady condition, storage print columns)
- [ ] Tenant controller has no storage-related logic
- [ ] ComputeInstance controller reads StorageClasses from TenantStorage status
- [ ] `kubectl get tenantstorage` displays Tenant and Phase columns
- [ ] OSAC Storage Controller skips reconciliation when `osac.openshift.io/management-state` is set to Unmanaged

**Stage 1 (Backend Setup)**
- [ ] OSAC Storage Controller watches Tenant resources and creates TenantStorage when Tenant reaches Ready
- [ ] OSAC Storage Controller triggers AAP backend provisioning (`osac-create-tenant-storage`) when hub Secret is absent
- [ ] `StorageBackendReady` condition is set on Tenant by the OSAC Storage Controller when Stage 1 completes

**Stage 2 (Cluster-Side Setup)**
- [ ] For VMaaS, OSAC Storage Controller discovers StorageClasses on the target cluster at tenant onboarding and populates the cluster entry in TenantStorage status
- [ ] ClusterOrder watch and informer are set up for CaaS Stage 2 triggering (trigger logic is covered by CaaS Tenant Storage Setup)

**Teardown**
- [ ] On Tenant deletion, OSAC Storage Controller triggers AAP teardown (`osac-delete-tenant-storage`) and deletes TenantStorage resource

**AAP Playbooks**
- [ ] AAP playbooks split into four job templates: `osac-create-tenant-storage`, `osac-ensure-tenant-storage`, `osac-cleanup-tenant-storage`, `osac-delete-tenant-storage`

**Testing**
- [ ] Unit tests pass for the new controller and updated Tenant/ComputeInstance controllers

## 5. Assumptions

- AAP is the only provisioning backend for v0.1. No direct API provisioning path exists.
- VAST is the only storage provider for v0.1.
- Tier configuration via the STORAGE_TIERS environment variable is sufficient for this PRD. The StorageTier API is a separate effort.
- StorageClasses are manually created. The OSAC Storage Controller discovers them but does not create them.

## 6. Dependencies

- **Tenant CR**: The OSAC Storage Controller depends on the Tenant CR lifecycle. Storage onboarding begins when a Tenant reaches Ready. Tenant deletion triggers storage teardown.
- **osac-operator and osac-aap coordinated deployment**: Changes span both repos and must be merged and deployed together. Deploying one without the other breaks tenant storage provisioning.

## 7. Risks

### 7.1 Breaking change in AAP playbook interface

The previous combined playbook (osac-configure-tenant-storage) is replaced by four separate playbooks. The new osac-create-tenant-storage playbook executes Stage 1 only, whereas the previous playbook executed both Stage 1 and Stage 2. Deploying the AAP changes without the operator changes causes the existing Tenant controller to provision storage incompletely.

- **Owner:** Storage WG
- **Mitigation:** Coordinated PR merge across osac-operator and osac-aap repos. PRs are linked in descriptions. Deployment documentation specifies both components must be updated together.

### 7.2 Migration of existing tenants

Existing tenants have storage state in the Tenant CR and no TenantStorage resource. When the new controller starts, it must create TenantStorage resources for existing tenants and populate them from current state, without re-triggering AAP provisioning.

- **Owner:** Storage WG
- **Mitigation:** The controller detects existing tenants with storage already provisioned (hub Secret exists) and creates TenantStorage resources with the correct state. No reprovisioning is triggered.

## 8. Open Questions

### 8.1 How does the OSAC Storage Controller determine the delivery model (VMaaS vs CaaS) for a given cluster to decide when Stage 2 runs?

- **Owner:** Storage WG
- **Impact:** FR-7 (Stage 2) and FR-10 (ClusterOrder watch)

### 8.2 What is the exact migration procedure for existing tenants?

- **Owner:** Storage WG
- **Impact:** Risk 7.2 (Migration of existing tenants)
