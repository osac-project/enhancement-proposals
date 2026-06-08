# Rework Tenant Storage Onboarding

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo, Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-23 |
| Date        | 2026-06-08 |

## 1. Problem Statement

Storage provisioning logic — backend setup, StorageClass resolution, AAP job tracking, and storage readiness — is embedded in the Tenant controller and the Tenant CR's status fields. Any change to storage onboarding risks breaking tenant lifecycle, and supporting different storage workflows per delivery model (VMaaS, CaaS, BMaaS) requires branching logic inside a single controller. Storage issues cannot be diagnosed independently from tenant status, and the storage working group cannot iterate on storage onboarding without coordinating every change with the core tenant lifecycle.

## 2. Goals and Non-Goals

### 2.1 Goals

- Storage lifecycle operates independently from tenant lifecycle — storage provisioning, readiness tracking, and teardown are managed by a dedicated controller without affecting tenant state transitions.
- Per-tenant storage state (provisioned tiers, provider resources, readiness) is observable as a standalone Kubernetes resource via `kubectl get tenantstorage`.
- The OSAC Storage Controller is the single entry point for all storage reconciliation, establishing the foundation for future storage capabilities (backend registration, CaaS cluster-side setup, resource creation storage).

### 2.3 Non-Goals

- StorageBackend CRD implementation (OSAC-917)
- StorageTier CRD implementation (OSAC-1110)
- CaaS Phase 2 trigger logic from ClusterOrder (OSAC-1123) — the controller watches ClusterOrder CRs, but the trigger logic for cluster-side storage setup is a separate effort
- Backend registration automation
- Prometheus metrics or fulfillment-service API visibility for storage state
- Fulfillment-service proto or API changes
- Changes to the storage provider role logic (setup, ensure_storage_class, teardown tasks) — only the playbook entry points and job template names change

## 3. Requirements

OSAC storage provisioning uses a two-phase model. Phase 1 (backend setup) runs at tenant onboarding: it creates the tenant's organization on the storage appliance, provisions VIP pools, credentials, per-tier views, and stores per-tenant credentials in a hub Secret. Phase 2 (cluster-side setup) runs when a target cluster is ready: it installs CSI drivers and creates StorageClasses on the cluster. This PRD covers the controller and CRD that manage Phase 1. Phase 2 triggering is out of scope (OSAC-1123).

### 3.1 Functional Requirements

- **FR-1:** A TenantStorage CRD captures per-tenant storage state. The spec contains a `tenantRef` field referencing the owning Tenant by name. The status contains phase (Progressing, Ready, Failed, Deleting), resolved StorageClass names with tier labels, structured status conditions, and AAP job tracking.

- **FR-2:** The OSAC Storage Controller watches Tenant CRs. When a Tenant reaches Ready (namespace exists), the controller creates a TenantStorage CR for that tenant and begins storage onboarding — checking for the tenant's hub Secret, triggering backend provisioning via AAP if absent, and resolving StorageClasses when the Secret exists. [Clarify: R1.Q1]

- **FR-3:** The OSAC Storage Controller watches ClusterOrder CRs to prepare for future CaaS Phase 2 triggering. For v0.1, no trigger logic is implemented — only the watch and informer are set up. [Clarify: R1.Q2]

- **FR-4:** Storage-related fields are removed from the Tenant CRD: StorageClasses status field, Jobs status field, StorageClassReady condition type, and storage-related print columns. [Clarify: R2.Q3]

- **FR-5:** The ComputeInstance controller reads StorageClasses from the TenantStorage CR's status instead of the Tenant CR's status.

- **FR-6:** The Tenant controller has zero storage responsibilities. It manages namespace creation, UDN reconciliation, and tenant lifecycle only. Storage readiness is entirely the OSAC Storage Controller's concern.

- **FR-7:** On Tenant deletion, the OSAC Storage Controller triggers backend teardown via AAP to clean up storage provider resources (VAST tenant, views, quotas) and the per-tenant hub Secret, then deletes the TenantStorage CR. No owner reference is used — the controller explicitly watches Tenant deletion events. [Clarify: R1.Q3]

- **FR-8:** AAP playbooks are split into four lifecycle actions: `osac-create-tenant-storage` (Phase 1 backend setup), `osac-ensure-tenant-storage` (Phase 2 cluster-side CSI + StorageClasses), `osac-cleanup-tenant-storage` (cluster-side resource removal), and `osac-delete-tenant-storage` (backend teardown). A corresponding cleanup action is added to the storage_provider role dispatcher. [Clarify: R1.Q4]

- **FR-9:** The OSAC Storage Controller checks the `osac.openshift.io/management-state` annotation and skips reconciliation when set to Unmanaged, consistent with all other OSAC controllers.

### 3.2 Non-Functional Requirements

- **NFR-1:** Admin credentials (VAST endpoint, username, password) are ephemeral — mounted as environment variables in the AAP automation pod, cleared after use, and never persisted to Kubernetes.

- **NFR-2:** Per-tenant credentials are stored in a Secret in the osac-system namespace, managed exclusively by the OSAC Storage Controller. These Secrets are the handoff point to downstream workflows (VMaaS cluster-side setup, CaaS cluster-side setup).

- **NFR-3:** The AAP playbook changes and operator changes must be deployed together. The `osac-create-tenant-storage` playbook replaces the previous combined playbook that executed both Phase 1 and Phase 2 — deploying the AAP changes without the operator changes breaks existing Tenant controller provisioning.

## 4. Acceptance Criteria

- [ ] TenantStorage CRD is defined with spec (tenantRef) and status (phase, storageClasses, conditions, jobs)
- [ ] OSAC Storage Controller watches Tenant CRs and creates TenantStorage when Tenant reaches Ready
- [ ] OSAC Storage Controller watches ClusterOrder CRs (informer set up, no trigger logic for v0.1)
- [ ] OSAC Storage Controller triggers AAP provisioning when hub Secret is absent, sets phase to Ready when Secret exists and StorageClasses are resolved
- [ ] Storage fields removed from Tenant CRD (StorageClasses, Jobs, StorageClassReady condition, storage print columns)
- [ ] Tenant controller has no storage-related logic or RBAC
- [ ] ComputeInstance controller reads StorageClasses from TenantStorage status
- [ ] On Tenant deletion, OSAC Storage Controller triggers AAP teardown and deletes TenantStorage CR
- [ ] AAP playbooks split into four job templates: osac-create-tenant-storage, osac-ensure-tenant-storage, osac-cleanup-tenant-storage, osac-delete-tenant-storage
- [ ] `kubectl get tenantstorage` displays Tenant and Phase columns
- [ ] Unit tests pass for the new controller and updated Tenant/ComputeInstance controllers

## 5. Assumptions

- AAP is the only provisioning backend for v0.1 — no direct API provisioning path exists.
- VAST is the only storage provider for v0.1.
- Tier configuration via the STORAGE_TIERS environment variable is sufficient for v0.1; the StorageTier API is a separate effort.

## 6. Dependencies

- **osac-aap** (OSAC-1145): AAP playbook split is delivered as part of this work. Coordinated merge required — AAP changes break backward compatibility if deployed without the operator changes.
- **osac-operator provisioning framework**: The controller reuses the existing `provisioning.RunProvisioningLifecycle()` helper and ProvisioningProvider interface. No changes to the framework are required.

## 7. Risks

### 7.1 Breaking change in AAP playbook interface

The previous combined playbook (osac-configure-tenant-storage) is replaced by four separate playbooks. The new osac-create-tenant-storage playbook executes Phase 1 only, whereas the previous playbook executed both Phase 1 and Phase 2. Deploying the AAP changes without the operator changes causes the existing Tenant controller to provision storage incompletely.

- **Owner:** Storage WG
- **Mitigation:** Coordinated PR merge across osac-operator and osac-aap repos. PRs are linked in descriptions. Deployment documentation specifies both components must be updated together.
