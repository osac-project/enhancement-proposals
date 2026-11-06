# DiskImage Pull-Secret References

| Field | Value |
| --- | --- |
| Author(s) | Ygal Blum |
| Jira | [OSAC-7339](https://redhat.atlassian.net/browse/OSAC-7339) |
| Date | 2026-11-06 |

## Problem Statement

Cloud Provider Admins and Tenant Admins need to make private-registry images available for VM provisioning without distributing registry credentials to each tenant user. Cluster-wide private-registry credentials can be configured directly on the target cluster, but not through OSAC. OSAC lacks per-DiskImage configuration for selecting an existing pull secret. Admins therefore lack image-specific credential-reference configuration for VMaaS provisioning.

## In Scope

- Authorized Cloud Provider Admins and Tenant Admins configure, change, or clear one optional reference to an existing pull secret on a DiskImage through the UI, CLI, and API, within existing resource and secret permissions. References follow the existing type-safe resource-reference contract; nonexistent, unauthorized, or incompatible secret references are rejected using existing error conventions.
- VMaaS uses the selected complete secret to acquire the private-registry image. Credentials are not merged or supplemented with registry entries from another secret. An empty reference supplies no DiskImage-level secret.
- The DiskImage's secret selection is resolved once when a ComputeInstance is created, even if initial provisioning has not started. Existing instances retain that selection; changing or clearing the DiskImage reference affects only subsequently created instances. Existing secret-content update rules remain unchanged.
- Tenants authorized to use a provider-managed DiskImage can provision from it without permission to retrieve or select its protected secret. Tenant-facing UI, CLI, and API views, selectors, responses, and errors do not disclose the protected secret's identity or value, grant secret discovery or retrieval access, or permit unauthorized explicit reuse. Normal visibility of authorized source configuration and the caller's own authorized selections remains unchanged. On tenant-scoped DiskImages, displayed pull-secret references must hide the secret’s identity from viewers who lack permission to discover it; authorized viewers retain their existing visibility.
- Secret deletion is blocked while an active DiskImage references the secret. Once OSAC marks a referring resource for deletion, that resource no longer blocks secret deletion; background cleanup completion is not required. Other active references remain independent. [User]
- Concurrent deletion of the selected source secret must not break an accepted instance’s initial image acquisition, including its retries. A successfully provisioned VM must not block secret deletion solely because it remains alive. [User]
- UI, CLI, and API documentation explains reference configuration, authorization, complete-secret selection, and the lifecycle behavior above.

## Out of Scope

- ComputeInstance pull-secret overrides and ComputeInstanceCatalogItem pull-secret references.
- Installation-wide or tenant-scoped default pull-secret references.
- Secret creation and content management, credential rotation or expiry, and external secret-manager integration.
- Registry mirrors or proxies, multi-registry fallback, registry CA trust configuration, and CaaS credential management.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to associate protected registry credentials with a DiskImage available to authorized tenants so that they can use private images without obtaining those credentials.

### Tenant Admin

- As a Tenant Admin, I want to configure an authorized pull-secret reference on my tenant's DiskImage so that my organization's VM requests can use its private-registry images without per-instance credential setup.

### Tenant User

- As a Tenant User, I want to provision a VM from a private-registry-backed DiskImage without knowing which registry credentials OSAC uses so that image authentication remains an OSAC-managed concern.

### Cloud Provider Admin / Tenant Admin

- As a Cloud Provider Admin or Tenant Admin, I want to clean up otherwise unreferenced pull secrets without deleting successfully provisioned VMs so that credential maintenance does not require VM teardown.

## Dependencies

- Existing typed Secrets API support for pull secrets and type-safe resource references provide authorized selection of existing credentials.
