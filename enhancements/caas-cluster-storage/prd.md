# CaaS Cluster Storage

| Field       | Value   |
|-------------|---------|
| Author(s)   | Akshay Nadkarni |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1332 |
| Date        | 2026-06-25 |

## Problem Statement

CaaS tenant clusters are provisioned without persistent storage. When a tenant's cluster becomes ready, it has compute but no way to create persistent volumes. Tenants cannot run stateful workloads until someone manually configures storage, and there is no visibility into whether storage is available on a given cluster.

## In Scope

- Automatic storage provisioning on CaaS clusters
- Storage readiness visibility for tenants and cloud admins
- Storage cleanup on CaaS cluster deletion

## Out of Scope

- Storage provider changes for CaaS support
- Storage UI
- Storage backend provisioning for a tenant (runs during tenant onboarding, before any cluster is ready)
- VMaaS storage changes

## User Stories

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want persistent storage to be available on my CaaS cluster when it is ready, so that I can run stateful workloads without waiting for manual configuration.
- As a Tenant Admin or Tenant User, I want to select a storage tier via StorageClasses when creating persistent volumes, so that I can choose the right performance level for my workload.
- As a Tenant Admin or Tenant User, I want to see whether my CaaS cluster's storage is ready and the reason if it is not, so that I know when I can deploy stateful workloads.
- As a Tenant Admin or Tenant User, I want storage resources on my CaaS cluster to be cleaned up when the cluster is deleted, without affecting my other clusters or backend resources.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to see storage readiness across all tenant clusters, so that I can identify and troubleshoot failures.

## Assumptions

- Storage backend provisioning is complete before a CaaS cluster becomes ready.
- CaaS cluster nodes have network reachability to the storage backend.

## Dependencies

- **Tenant Storage Onboarding:** Provides the storage automation framework that CaaS cluster storage builds on.
- **Storage provider CaaS support:** The storage provider must accept CaaS clusters as a target. Required for end-to-end functionality.
