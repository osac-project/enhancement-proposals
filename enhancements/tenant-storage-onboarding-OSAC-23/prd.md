# Rework Tenant Storage Onboarding

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo, Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-23 |
| Date        | 2026-06-05 |

## 1. Problem Statement

Storage provisioning logic — Phase 1 backend setup, StorageClass resolution, AAP job tracking, and storage readiness — is embedded in the Tenant controller and the Tenant CR's status fields. This tight coupling means any change to storage onboarding risks breaking tenant lifecycle, and supporting different storage workflows per delivery model (VMaaS, CaaS, BMaaS) requires branching logic inside a single controller. Storage issues cannot be diagnosed independently from tenant status, and the storage working group cannot iterate on storage onboarding without coordinating every change with the core tenant lifecycle.

## 2. Goals and Non-Goals

### 2.1 Goals

- Storage lifecycle operates independently from tenant lifecycle — storage provisioning, readiness tracking, and teardown are managed by a dedicated controller without affecting tenant state transitions.
- Per-tenant storage state (provisioned tiers, provider resources, readiness) is observable as a standalone Kubernetes resource via `kubectl get tenantstorages`. [Clarify: D6]
- The OSAC Storage Controller is the single entry point for all storage reconciliation, establishing the foundation for future storage capabilities (backend registration, CaaS cluster-side setup, resource creation storage). [Clarify: D1, D2]

### 2.3 Non-Goals

- StorageBackend CRD implementation (OSAC-917) [Clarify: D5]
- StorageTier CRD implementation (OSAC-1110) [Clarify: D5]
- CaaS Phase 2 trigger from ClusterOrder controller (OSAC-1123) [Clarify: D5]
- Backend registration automation [Clarify: D5]
- Prometheus metrics or fulfillment-service API visibility for storage state [Clarify: D6]
- Fulfillment-service proto or API changes
- Changes to the storage provider roles or VAST integration logic (only the playbook entry points change)

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** A TenantStorage CRD captures per-tenant storage state. The spec contains a `tenantRef` field referencing the owning Tenant by name. The status contains `phase` (Progressing, Ready, Failed, Deleting), `storageClasses` (resolved StorageClass names with tier labels), `conditions` (structured status conditions), and `jobs` (AAP job tracking). [Clarify: D1]

- **FR-2:** The OSAC Storage Controller watches TenantStorage CRs and provisions storage via AAP. On creation, the controller checks for the tenant's hub Secret — if absent, it triggers the `osac-create-tenant-storage` AAP job (Phase 1 backend setup). When the hub Secret exists, the controller resolves StorageClasses by tenant label and sets the phase to Ready.

- **FR-3:** The Tenant controller creates a TenantStorage CR during tenant onboarding with an owner reference, so that TenantStorage is automatically deleted when the Tenant is deleted. [Clarify: D3]

- **FR-4:** Storage-related fields are removed from the Tenant CRD: `StorageClasses` status field, `Jobs` status field, `StorageClassReady` condition type, and storage-related print columns.

- **FR-5:** The ComputeInstance controller reads StorageClasses from the TenantStorage CR's status instead of the Tenant CR's status.

- **FR-6:** Hub Secret readiness is gated on TenantStorage (via the `StorageBackendReady` condition), not on the Tenant CR. The Tenant CR reaches Ready when its namespace exists — storage readiness is the TenantStorage controller's concern.

- **FR-7:** On deletion, the OSAC Storage Controller triggers the `osac-delete-tenant-storage` AAP job to clean up backend resources (VAST tenant, views, quotas) and the per-tenant hub Secret.

- **FR-8:** AAP playbooks are split into four lifecycle actions: `osac-create-tenant-storage` (Phase 1 backend setup), `osac-ensure-tenant-storage` (Phase 2 cluster-side CSI + StorageClasses), `osac-cleanup-tenant-storage` (cluster-side resource removal), and `osac-delete-tenant-storage` (backend teardown). A corresponding `cleanup` action is added to the `storage_provider` role dispatcher. [Clarify: D4]

- **FR-9:** The OSAC Storage Controller checks the `osac.openshift.io/management-state` annotation and skips reconciliation when set to `Unmanaged`, consistent with all other OSAC controllers.

### 3.2 Non-Functional Requirements

- **NFR-1:** Admin credentials (VAST endpoint, username, password) are ephemeral — mounted as environment variables in the AAP automation pod, cleared after use, and never persisted to Kubernetes.

- **NFR-2:** Per-tenant credentials are stored in a Secret in the `osac-system` namespace, managed exclusively by the TenantStorage controller. These Secrets are the handoff point to downstream workflows (VMaaS cluster-side setup, CaaS cluster-side setup).

- **NFR-3:** The AAP playbook changes and operator changes must be deployed together. The `osac-create-tenant-storage` playbook replaces the previous combined playbook that executed both Phase 1 and Phase 2 — deploying the AAP changes without the operator changes breaks existing Tenant controller provisioning.

## 4. Acceptance Criteria

- [ ] TenantStorage CRD is defined with spec (`tenantRef`) and status (`phase`, `storageClasses`, `conditions`, `jobs`)
- [ ] OSAC Storage Controller reconciles TenantStorage CRs: triggers AAP provisioning when hub Secret is absent, sets phase to Ready when hub Secret exists and StorageClasses are resolved
- [ ] Tenant controller creates a TenantStorage CR with owner reference during onboarding
- [ ] Storage fields removed from Tenant CRD (`StorageClasses`, `Jobs`, `StorageClassReady` condition, storage print columns)
- [ ] ComputeInstance controller reads StorageClasses from TenantStorage status
- [ ] OSAC Storage Controller triggers AAP teardown on TenantStorage deletion and removes the finalizer after completion
- [ ] AAP playbooks split into four job templates: `osac-create-tenant-storage`, `osac-ensure-tenant-storage`, `osac-cleanup-tenant-storage`, `osac-delete-tenant-storage`
- [ ] `kubectl get tenantstorages` displays Tenant and Phase columns
- [ ] Unit tests pass for the new controller and updated Tenant/ComputeInstance controllers

## 5. Assumptions

- AAP is the only provisioning backend for v0.1 — no direct API provisioning path exists.
- VAST is the only storage provider for v0.1.
- Tier configuration via the `STORAGE_TIERS` environment variable is sufficient for v0.1; the StorageTier API is a separate effort.
- The TenantStorage CRD name can be changed in a future release when the broader storage controller scope materializes, without breaking external consumers (no external API contracts depend on this CRD name today). [Clarify: D2]

## 6. Dependencies

- **osac-aap** (OSAC-1145): AAP playbook split is delivered as part of this work. Coordinated merge required — AAP changes break backward compatibility if deployed without the operator changes. [Clarify: D4]
- **osac-operator provisioning framework**: The controller reuses the existing `provisioning.RunProvisioningLifecycle()` helper and `ProvisioningProvider` interface. No changes to the framework are required.

## 7. Risks

### 7.1 Breaking change in AAP playbook interface

The previous combined playbook (`osac-configure-tenant-storage`) is replaced by four separate playbooks. The new `osac-create-tenant-storage` playbook executes Phase 1 only, whereas the previous playbook executed both Phase 1 and Phase 2. Deploying the AAP changes without the operator changes causes the existing Tenant controller to provision storage incompletely.

- **Owner:** Zoltan Szabo
- **Mitigation:** Coordinated PR merge across osac-operator and osac-aap repos. PRs are linked in their descriptions. Deployment documentation specifies both components must be updated together.

### 7.2 ComputeInstance controller migration

The ComputeInstance controller's storage integration was wired up in May 2026 and is not yet widely used in production. Migrating it to read from TenantStorage instead of Tenant is low-risk but must be validated on the dev cluster.

- **Owner:** Zoltan Szabo
- **Mitigation:** Unit tests cover the new code path. E2E validation on hypershift1 dev cluster before merge.
