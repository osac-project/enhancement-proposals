# CaaS Cluster Storage

| Field       | Value   |
|-------------|---------|
| Author(s)   | Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1332 |
| Date        | 2026-06-24 |

## 1. Problem Statement

CaaS tenant clusters are provisioned without persistent storage. When a cluster is ready, it has compute but no way for tenant workloads to create persistent volumes. Storage backend resources (credentials, views, quotas) are already provisioned during tenant onboarding, but nothing connects cluster readiness to storage installation on that cluster. Cloud Provider Admins have no visibility into whether a cluster's storage is ready, and Tenant Admins and Users cannot use persistent storage until someone manually configures it.

## 2. Goals and Non-Goals

### 2.1 Goals

- When a CaaS cluster is provisioned and ready, persistent storage (CSI driver and per-tenant, per-tier StorageClasses) is automatically available without manual configuration.
- Cloud Provider Admins can see tenant-level storage status across all CaaS clusters.
- Tenant Admins and Users can see whether their cluster's storage is ready.
- When a CaaS cluster is deleted, storage resources on that cluster are cleaned up. Backend resources are left intact for other clusters.
- Multiple CaaS clusters per tenant are handled independently, each with its own storage readiness.
- When the Storage Tier API (OSAC-1110) and StorageBackend API (OSAC-1111) are available, the system uses them. Otherwise it falls back to the existing configuration.

### 2.2 Non-Goals

- Making the storage provider CaaS-ready. Covered by OSAC-1122.
- Storage UI.
- Storage backend provisioning (runs during tenant onboarding, assumed complete before any cluster is ready).
- VMaaS cluster-side storage changes. Existing flow is unchanged.
- Cloud Infrastructure Admin responsibilities (storage backend configuration, tier definitions). Covered by OSAC-1122 and OSAC-1110.

## 3. Capabilities

### Automatic Storage Setup

When a CaaS cluster is provisioned and ready, the system automatically installs the CSI driver and creates per-tenant, per-tier StorageClasses on that cluster. The tenant's storage backend must be fully provisioned before this happens. No manual intervention is required from any persona.

The system determines which tiers and backends are available for the tenant. If the Tier API or StorageBackend API are deployed, they are used. Otherwise the system falls back to the existing tier and backend configuration.

### Storage Readiness Visibility

As a Cloud Provider Admin, I can see the storage readiness of each tenant's CaaS clusters at the tenant level, so I can monitor onboarding progress and troubleshoot failures across tenants.

As a Tenant Admin or Tenant User, I can see whether my specific CaaS cluster's storage is ready, so I know when I can start creating persistent volumes. If storage setup failed, I can see the reason.

### Cluster Deletion and Cleanup

When a CaaS cluster is deleted, storage resources installed on that cluster are cleaned up. Backend resources shared across the tenant's clusters are not affected, because other clusters may still use them.

### Multi-Cluster Independence

A tenant can have multiple CaaS clusters. Each cluster's storage is set up and torn down independently. Adding or removing a CaaS cluster does not affect storage on other clusters belonging to the same tenant.

### 3.1 Operational Expectations

- Storage should be available shortly after the cluster is ready.
- Credentials and secrets are never exposed in user-visible error messages, status fields, or events.

## 4. Acceptance Criteria

- [ ] A tenant user can create a PVC on a newly provisioned CaaS cluster without manual storage configuration
- [ ] A Cloud Provider Admin can see storage readiness status for each tenant's CaaS clusters
- [ ] A Tenant Admin or User can see whether their specific CaaS cluster's storage is ready and the reason if it failed
- [ ] When a CaaS cluster is deleted, storage resources on that cluster are cleaned up
- [ ] Deleting one CaaS cluster does not affect storage on other clusters belonging to the same tenant
- [ ] Backend resources are unaffected by CaaS cluster deletion
- [ ] A second CaaS cluster for the same tenant gets independent storage setup

## 5. Assumptions

- Storage backend provisioning is always complete before a CaaS cluster reaches ready. The system does not handle a ready cluster with an unprovisioned backend.
- The storage provider's automation accepts CaaS clusters as a target and uses the provided cluster credentials. This is delivered by OSAC-1122.
- VAST is the only storage provider for v0.1.
- Cluster credentials are obtainable from the cluster provisioning infrastructure. Confirmed by the CaaS team.
- CaaS cluster nodes have network reachability to the storage backend. This is an infrastructure prerequisite managed by the Cloud Infrastructure Admin.

## 6. Dependencies

- **Tenant Storage Onboarding (OSAC-23):** Merged. Provides the storage automation framework and independent per-cluster setup and teardown actions that this PRD extends for CaaS clusters.
- **VAST for CaaS (OSAC-1122):** In progress. The storage provider must support CaaS clusters as a target. Required for end-to-end functionality.
- **Tier API (OSAC-1110):** In progress. Not blocking. The system integrates when available, falls back to existing configuration.
- **StorageBackend API (OSAC-1111):** In progress. Not blocking. The system integrates when available, falls back to single implicit backend.
