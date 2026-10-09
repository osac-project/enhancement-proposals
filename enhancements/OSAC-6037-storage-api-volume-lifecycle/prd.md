# Storage API Integration for ComputeInstance Volume Lifecycle Management

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ygal Blum |
| Jira        | [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) |
| Date        | 2026-10-06 |

## Problem Statement

Volumes created during ComputeInstance provisioning are invisible to the Storage API. The Storage service has no awareness of volumes provisioned for compute instances, which produces four gaps: there is no unified inventory of storage resources across the platform, no ability to inspect or manage these volumes through the Storage API, no coordinated cleanup when a ComputeInstance is deleted, and no deletion protection for volumes that are actively backing a running instance. Orphaned volumes accumulate when instances are deleted, and accidental volume removal can disrupt running workloads. Without this integration, OSAC cannot provide a cohesive compute-storage experience — administrators lack visibility and tenants must trust that cleanup happens correctly without any way to verify it.

## In Scope

- Delivery targets the OSAC 0.4 milestone.
- Creating a ComputeInstance creates a corresponding Storage API volume for each required disk — boot disk and any additional disks — so that all volumes are tracked through the Storage API from the moment of provisioning.
- Deleting a ComputeInstance deletes all of its associated OSAC volumes through the Storage API, preventing orphaned storage resources.
- Volume IDs are visible in the ComputeInstance status and the UI, providing end-to-end traceability from the compute resource to the storage resource.

## Out of Scope

- Dynamic volume attach and detach — this PRD does not add or change the separate attach/detach lifecycle scoped under [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884).
- Volume-to-ComputeInstance reverse link — the Volume record does not indicate which ComputeInstance it is attached to; correlation is performed from the ComputeInstance side via volume IDs in its status.
- Volume resize or migration while attached to a ComputeInstance (tracked separately as [OSAC-6048](https://redhat.atlassian.net/browse/OSAC-6048)).
- Shared volumes across multiple ComputeInstances.
- Snapshot or backup integration for attached volumes.
- Standalone volume deletion — volumes cannot be deleted independently through the Storage API; they are only removed as part of ComputeInstance deletion.

## User Stories

### Cloud Provider Admin

Not directly affected by this feature — volume lifecycle management operates within existing tenant and infrastructure boundaries.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want volumes created for ComputeInstances to be automatically tracked and cleaned up on instance deletion so that orphaned storage resources do not accumulate across the infrastructure.

### Tenant Admin

- As a Tenant Admin, I want the ComputeInstance status to display the volume IDs of all attached volumes so that I can audit and correlate storage usage with compute resources in my tenant.

### Tenant User

- As a Tenant User, I want the service to automatically create the required boot and additional disk volumes when I create a ComputeInstance so that I do not need to separately provision and attach storage.
- As a Tenant User, I want volumes to be automatically deleted when I delete my ComputeInstance so that I do not accumulate orphaned storage resources.
- As a Tenant User, I want to see which volumes are attached to my ComputeInstance in its status so that I can verify my storage configuration.

## Dependencies

- **Storage API (Private API):** The Storage API private interface must be available for ComputeInstance provisioning to create and delete volumes as part of instance lifecycle. Separate volume attach and detach APIs are not required.
