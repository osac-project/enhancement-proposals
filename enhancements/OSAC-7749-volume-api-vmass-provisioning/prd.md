# Volume API owns VMaaS volume provisioning end-to-end

| Field       | Value   |
|-------------|---------|
| Author(s)   | Akshay Nadkarni anadkarn@redhat.com |
| Jira        | https://redhat.atlassian.net/browse/OSAC-7749 |
| Date        | 2026-11-14 |

## Problem Statement

Today, when a tenant creates a ComputeInstance with disks, volumes are registered but provisioned through a separate path that the Storage team
does not control. This means volumes lack ownership tracking (no way to answer "which volumes belong to this VM?"), the lifecycle is not managed
consistently, and there is no foundation for future capabilities like add-disk, remove-disk, or transfer.

## In Scope

- Volume ownership: every volume records which ComputeInstance owns it
- Volume provisioning owned end-to-end by the Volume API
- The ComputeInstance API remains the entry-point for the tenant. Its API does not change. The Volume API is called internally during
  ComputeInstance provisioning.
- The previous provisioning path must be disabled once the Volume API owns provisioning, so that only one path creates storage for a given disk
- Simplified volume lifecycle: PENDING, CREATING, AVAILABLE, FAILED, DELETING, DELETED, with visible failure reasons
- ComputeInstance cascade delete: deleting a ComputeInstance deletes its volumes
- Disk source preservation: existing disk sources (OCI registry images) keep working through the new path

## Out of Scope

- Standalone volumes (creating a volume with no owning ComputeInstance)
- Add-disk: attaching an existing volume to a running ComputeInstance
- Remove-disk: detaching a volume without deleting it
- Transfer: moving a volume between ComputeInstances
- Hot-plug / hot-unplug on running VMs
- Stable name mapping between an OSAC volume and its provisioned storage on the target cluster
- UI / Console support
- CLI commands for add-disk or remove-disk

## User Stories

### Tenant User

- As a Tenant User, I want to create a ComputeInstance with disks and have each disk automatically tracked as a volume with my VM as the owner,
  so that I can see which volumes belong to which VM and whether each volume is ready using volume list or volume get.

- As a Tenant User, I want to see the provisioning state of each volume (PENDING, CREATING, AVAILABLE, FAILED, DELETING, DELETED) and a
  descriptive failure reason when something goes wrong, so that I know the status of my disks without needing to inspect lower-level resources.

- As a Tenant User, I want my volumes to be automatically deleted when I delete a ComputeInstance, so that I don't accumulate orphaned storage.

- As a Tenant User, I want to create a ComputeInstance with a disk sourced from an OCI registry image (e.g. quay.io/my-org/golden-image) and
  have it work exactly as it does today, so that my existing disk source workflows are not broken by the new provisioning path.

## Assumptions

- This feature applies only to new ComputeInstances created after it ships. Existing VMs and their volumes are not migrated or backfilled with
  ownership.
- A volume is always created with exactly one owning ComputeInstance. Multi-attach, i.e. sharing a volume between two VMs, is not supported.

## Dependencies

- The volume must be provisioned in the same location as its owning ComputeInstance. The mechanism for resolving that location is a design
  decision for the HLD.
