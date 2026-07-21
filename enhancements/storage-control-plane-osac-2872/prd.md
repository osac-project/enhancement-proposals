# OSAC Storage Control Plane

| Field       | Value   |
|-------------|---------|
| Author(s)   | Akshay Nadkarni, Roy Golan |
| Jira        | [OSAC-2872](https://redhat.atlassian.net/browse/OSAC-2872) |
| Date        | 2026-07-20 |

## Problem Statement

OSAC CaaS tenants need block storage on their clusters, but there is no vendor-agnostic storage layer today. Without one, tenants would see vendor-specific StorageClasses and backend addresses, vendor credentials would be stored on tenant clusters, there would be no enforcement point for per-tenant storage policy, and the platform would have no inventory of what volumes exist or which tenant owns them.

The Storage Control Plane introduces a single storage driver that presents opaque storage tiers to tenants, enforces authorization and tier-access policies, provides vendor credentials per-request without persisting them on tenant clusters, and tracks every volume in a central inventory.

## In Scope

1. **Storage driver for tenant clusters**: Handles PVC create, delete, and read (get/list) on tenant clusters through a standard Kubernetes PVC interface. StorageClasses are named after the tenant's configured storage tiers. v0.2 supports VAST as the only vendor backend for block storage.

2. **Storage control plane services**: Tier resolution (maps a tenant's StorageClass to the correct vendor backend), policy enforcement (authorization and tier-access checks), and credential management (vendor credentials provided per-request, never stored on tenant clusters).

3. **Volume inventory**: Every volume tracked centrally with tenant, tier, state, and size. State lifecycle for v0.2: creating, available, deleting, deleted.

4. **Private Volume API**: Internal CRUD operations for volume records, consumed by platform services. Not exposed to tenants.

5. **Storage driver packaging**: Packaged for distribution and installation on tenant clusters, including StorageClasses generated from the tenant's configured tiers.

6. **Automated cluster storage deployment**: When a tenant cluster is provisioned, the storage driver, vendor plugins, and tenant-specific StorageClasses are deployed automatically. Cross-cluster authentication is established without manual credential distribution. This extends the existing Cluster Storage Setup (OSAC-1001) and Tenant Onboarding (OSAC-1332).

## Out of Scope

- **Volume resize**
- **Volume snapshots and clones**
- **Public Volume API** for tenant-facing volume management (OSAC-984)
- **UI integration** for volume management (OSAC-984)
- **Vendor REST adapters** for non-CSI volume management (OSAC-984)
- **Storage metering**
- **CSI certification** (conformance tests, OLM bundle): planned as a separate feature
- **Quota lifecycle** (reserve/commit/release): targeted for v0.3
- **VMaaS storage integration**: storage during ComputeInstance lifecycle
- **BMaaS storage integration**: storage during BareMetalInstance lifecycle
- **Audit logging**: structured audit trail for storage operations

## User Stories

### Tenant Admin/User

Tenant Admin and Tenant User have the same storage capabilities in v0.2.

- As a Tenant Admin/User, I want to create a PVC using a StorageClass named after one of my configured storage tiers, so that I can provision block storage without seeing vendor details, credentials, or backend addresses.

- As a Tenant Admin/User, I want to delete a PVC, so that the underlying volume is cleaned up and the storage is released.

- As a Tenant Admin/User, I want to view my persistent volumes and claims using standard Kubernetes tools (kubectl), so that I can monitor storage usage on my cluster.

- As a Tenant Admin/User, I want a PVC referencing an unconfigured StorageClass to stay Pending with a standard Kubernetes event, so that the behavior is predictable and consistent with native Kubernetes.

- As a Tenant Admin/User, I want storage to be ready on my cluster immediately after provisioning, so that I can start creating PVCs without requesting manual setup.

- As a Tenant User, I want every volume I create tracked centrally by the platform, so that my storage usage is attributable to me.

- As a Tenant Admin, I want to see all volumes across clusters owned by my organization, so that I can manage storage usage within my organization.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want the storage driver, vendor plugins, and tenant-specific StorageClasses deployed automatically when a cluster is provisioned, so that tenants can consume storage without manual intervention.

- As a Cloud Provider Admin, I want cross-cluster authentication established automatically during cluster provisioning, so that tenant clusters communicate securely with the storage control plane without manual credential distribution.

- As a Cloud Provider Admin, I want vendor credentials never stored on tenant clusters and provided only per-request, so that a compromised tenant cluster cannot access storage backends directly.

- As a Cloud Provider Admin, I want to see all volumes created by a tenant, so that I can account for storage resources across tenants.

## Assumptions

- OSAC-917 (Storage Framework) delivers StorageBackend and StorageTier entities before this feature can function end-to-end.
- ClusterOrder provisioning is functional and supports post-provisioning automation hooks.
- Cluster Storage Setup (OSAC-1001) and Tenant Onboarding (OSAC-1332) exist as baselines that this feature extends.

## Dependencies

- **OSAC-917 (Storage Framework)**: Delivers StorageBackend and StorageTier entities. Must land before tier resolution and StorageClass generation can function.
- **ClusterOrder provisioning**: Must be functional for automated storage driver deployment during cluster provisioning.
- **OSAC-1001 (Cluster Storage Setup)** and **OSAC-1332 (Tenant Onboarding)**: Existing automation that this feature extends to deploy the OSAC storage driver.

## References

- [Architecture doc: OSAC CSI Meta-Driver](https://docs.google.com/document/d/1GCWco97kWNwFwfbC4TAoyXIxPSMO4CNyqFKv_lQczZU/edit?usp=sharing)
- [Storage User Flows Roadmap](https://docs.google.com/spreadsheets/d/1kwpUdOUeCI8qVtDN1iL1iu-M1a7N_ZSCso-Rt_KpVKE/edit?usp=sharing)
- [OSAC Storage and CSI Components Diagram](https://docs.google.com/drawings/d/1-e2wep_RKmJRLFtqMu1RzKPvV_7mz2ZpLHaVLHZayd8/edit?usp=sharing)
- [OSAC CSI Driver Flow - CaaS Diagram](https://docs.google.com/drawings/d/1QVn4y_NSfyWoHd50w8buiXV1LaQZOFYCwLwczTTvbEQ/edit?usp=sharing)
