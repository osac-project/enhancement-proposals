# CaaS Cluster Storage

| Field       | Value   |
|-------------|---------|
| Author(s)   | Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1332 |
| Date        | 2026-06-24 |

## 1. Problem Statement

CaaS tenant clusters are provisioned without persistent storage. When a ClusterOrder reaches Ready, the cluster has compute but no StorageClasses or CSI driver, so tenant workloads cannot create PVCs. The OSAC Storage Controller already handles backend setup (Stage 1) at tenant onboarding and cluster-side setup (Stage 2) for VMaaS, but it ignores ClusterOrder events. There is no automation connecting CaaS cluster readiness to storage installation.

## 2. Goals and Non-Goals

### 2.1 Goals

- Automatically install the CSI driver and per-tenant, per-tier StorageClasses on a CaaS cluster when it reaches Ready.
- Track storage readiness on the ClusterOrder CR via a `ClusterStorageReady` condition, visible to Cloud Provider Admins.
- Clean up cluster-side storage resources on CaaS cluster deletion. Leave backend resources (VAST tenant, views, quotas, hub Secret) intact for other clusters.
- Handle multiple CaaS clusters per tenant independently, each with its own storage readiness.
- Integrate with the Storage Tier API (OSAC-1110) and StorageBackend API (OSAC-1111) when available, falling back to `STORAGE_TIERS` env var and single implicit backend otherwise.

### 2.2 Non-Goals

- VAST provider CaaS changes (tenant-UID paths, RBAC credentials, `hcp_data_plane` target). Covered by OSAC-1122.
- UI for storage.
- Stage 1 (backend setup). Assumed complete before any CaaS cluster reaches Ready.
- VMaaS cluster-side storage. Existing flow is unchanged.

## 3. Requirements

### 3.1 Functional Requirements

#### CaaS Stage 2 Trigger

- **FR-1:** When a ClusterOrder reaches `phase=Ready` and the owning Tenant has `StorageBackendReady=True`, the storage controller invokes `osac-create-tenant-cluster-storage` with `provisioning_target=hcp_data_plane`.
- **FR-2:** The storage controller passes the CaaS cluster's connection details (kubeconfig or equivalent) to the AAP playbook as extra vars. The playbook does not discover cluster access on its own.
- **FR-3:** The storage controller resolves tiers from the Tier API (OSAC-1110) when available, falling back to `STORAGE_TIERS` env var.
- **FR-4:** The storage controller discovers backends from the StorageBackend API (OSAC-1111) when available, falling back to the single implicit backend.

#### Storage Readiness

- **FR-5:** The storage controller sets a `ClusterStorageReady` condition on the ClusterOrder CR: `True` when the AAP job succeeds and StorageClasses are confirmed, `False` with reason on failure.
- **FR-6:** The storage controller records per-cluster detail in the Tenant CR's `status.clusterStorage` array (ClusterOrder name, readiness, reason).
- **FR-7:** `kubectl get clusterorder -o wide` shows a `ClusterStorageReady` column.

#### Teardown

- **FR-8:** The storage controller places a finalizer on each ClusterOrder where storage was set up. On deletion, it triggers `osac-delete-tenant-cluster-storage` to remove StorageClasses, VolumeSnapshotClasses, and CSI Secret from the CaaS cluster. The finalizer is removed only after cleanup completes.
- **FR-9:** After cleanup, the storage controller removes the ClusterOrder's entry from `status.clusterStorage` on the Tenant CR.

### 3.2 Non-Functional Requirements

- **NFR-1:** The storage controller must not log or emit events containing credentials, Secret contents, or sensitive AAP parameters.

## 4. Acceptance Criteria

**Trigger**
- [ ] ClusterOrder reaching Ready with `StorageBackendReady=True` triggers `osac-create-tenant-cluster-storage` with `provisioning_target=hcp_data_plane`
- [ ] AAP playbook receives cluster connection details as extra vars
- [ ] Tiers resolved from Tier API when available, `STORAGE_TIERS` env var otherwise
- [ ] Backends discovered from StorageBackend API when available, single implicit backend otherwise

**Readiness**
- [ ] `ClusterStorageReady=True` on ClusterOrder when setup succeeds
- [ ] `ClusterStorageReady=False` with reason on failure
- [ ] `kubectl get clusterorder -o wide` shows storage readiness
- [ ] Tenant CR `status.clusterStorage` has an entry per CaaS cluster

**Teardown**
- [ ] Finalizer placed on ClusterOrders where storage was set up
- [ ] ClusterOrder deletion triggers `osac-delete-tenant-cluster-storage`
- [ ] Finalizer removed only after cleanup completes
- [ ] Backend resources unaffected by cluster deletion
- [ ] `status.clusterStorage` entry removed after cleanup

**Multi-Cluster**
- [ ] Second ClusterOrder for the same tenant gets independent storage setup
- [ ] Deleting one ClusterOrder does not affect other clusters

**Testing**
- [ ] Unit tests with mock AAP providers cover trigger, readiness, teardown, and multi-cluster
- [ ] (Stretch) E2E against live VAST + CaaS cluster

## 5. Assumptions

- Stage 1 is always complete before a CaaS cluster reaches Ready. The controller does not handle a Ready ClusterOrder with an unprovisioned backend.
- AAP playbooks accept `hcp_data_plane` and use the passed kubeconfig to target the CaaS cluster. Delivered by OSAC-1122.
- VAST is the only storage provider for v0.1. A global VIP Pool is shared by all tenants.
- The kubeconfig for a CaaS cluster is obtainable from the HostedControlPlane status via the ClusterOrder's cluster reference. Exact mechanism pending CaaS working group confirmation.

## 6. Dependencies

- **OSAC-23 (Storage Controller):** Implemented and merged (osac-operator PR #299). This PRD extends the controller's ClusterOrder handling.
- **osac-aap PR #338 (playbook split):** Under review. Required for CaaS setup and teardown to operate independently from backend operations.
- **OSAC-1122 (VAST for CaaS):** VAST provider must accept `hcp_data_plane` and use the passed kubeconfig. Without this, the trigger fires but the playbook cannot act.
- **OSAC-1110 (Tier API):** Not blocking. Controller integrates when available, falls back to env var.
- **OSAC-1111 (StorageBackend API):** Not blocking. In development (fulfillment-service PR #728). Controller integrates when available, falls back to single implicit backend.

## 7. Risks

### 7.1 CaaS cluster kubeconfig access is unconfirmed

- **Owner:** Akshay Nadkarni / CaaS working group
- **Mitigation:** The expected path (`ClusterOrder.status.clusterReference` to `HostedControlPlane.status.kubeConfig`) is traceable through the HyperShift API. If the mechanism differs, only credential retrieval changes; trigger and condition logic are unaffected.

## 8. Open Questions

### 8.1 What credential should the storage controller use for CaaS cluster access?

- **Owner:** CaaS working group
- **Impact:** Affects FR-2. The expected path is `HostedControlPlane.status.kubeConfig`, but a scoped service account token may be preferred.
