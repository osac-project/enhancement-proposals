# Volume Get/List Public API

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo |
| Jira        | [OSAC-4542](https://redhat.atlassian.net/browse/OSAC-4542) |
| Date        | 2026-08-27 |

## Problem Statement

The OSAC storage control plane (OSAC-2872) already provisions standalone storage volumes and tracks them in a central inventory, but that inventory is only reachable through the internal API. Tenants and the OSAC console have no supported way to see the volumes that exist. As a result, the console cannot show storage to users, and tenants have no operational visibility into their own volumes — they cannot confirm a volume's size, tier, or state, and administrators cannot review storage usage for troubleshooting or monitoring. This blocks the console's storage experience and leaves volume inventory effectively invisible to the people who own it.

## In Scope

*This release delivers the first, read-only slice of the public Volume API: retrieving individual volumes and listing them. It reuses the volumes already provisioned and inventoried by OSAC-2872 — no new provisioning path is introduced. Mutating operations remain internal and are deferred to later phases of the public Volume API (OSAC-984). See Out of Scope.*

- **Retrieve a volume's details.** A user can fetch a single volume and see its tenant-meaningful attributes — name, tier, size, access mode, and current state — so they can confirm its configuration and availability.
- **List volumes.** A user can list the volumes they are entitled to see, with filtering, sorting, and pagination consistent with other OSAC list endpoints, so the console and CLI can present and navigate storage inventory.
- **Tenant-scoped visibility.** Each caller sees only the volumes in the tenants they are entitled to: a Cloud Provider Admin across their assigned tenants, and tenant members within their own tenant — the same visibility model used by every other OSAC resource.
- **Read-only, tenant-meaningful representation.** The public view exposes only information that is meaningful to tenants; internal placement and routing details used to serve a volume are not shown. Volumes are read-only through this API.
- **Same access channels as other resources.** Volumes are reachable over the same public gRPC and REST endpoints, console, and CLI as other OSAC resources; no storage-specific access path is introduced.
- **Test and documentation.** Tests cover retrieving and listing standalone volumes through the public API, including tenant-scoped isolation; API documentation and the published API spec are updated with the new read endpoints.

## Out of Scope

Deferred to later work (this release is read-only Get/List only):

- **Volume lifecycle through the public API** — creating, updating, resizing, or deleting volumes. These remain on the internal API and are tracked under later OSAC-984 phases.
- **Per-user (owner-level) visibility** — restricting a Tenant User to only the volumes they personally created. OSAC scopes visibility at the tenant level today; owner-level visibility is a platform-wide capability deferred to a future tenancy feature so it can apply uniformly across all resources.
- **Volume attach / detach** — managed via VMaaS / Compute work.
- **Snapshots, clones, and restore.**
- **File storage** (NFS/SMB — OSAC-4515) and **object storage** (S3).

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to get and list storage volumes across all my assigned tenants, so that I have operational visibility for troubleshooting and monitoring.

### Tenant Admin

- As a Tenant Admin, I want to list the storage volumes within my tenant, so that I can view storage inventory and monitor usage.

### Tenant User

- As a Tenant User, I want to get the details of a specific storage volume — its size, tier, and state — so that I can understand its configuration and verify its availability.

### Cloud Infrastructure Admin

- Not affected by this feature.

## Assumptions

- The volumes to be read already exist and are inventoried by the storage control plane (OSAC-2872); this feature adds a read surface, not a new source of data.
- Tenant-level visibility is the correct and consistent default for this release, matching how every other OSAC resource scopes reads. Narrowing a Tenant User to only their own volumes is a separate, platform-wide decision (see Out of Scope).
- The public representation of a volume is a subset of the internal one; fields that are not meaningful to tenants are omitted rather than reshaped.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the private Volume API, the volume inventory, and the tier/backend model this read API surfaces. Must be in place for volumes to exist and be retrievable.
- **Console UI / UX and UI design gates (OSAC-4546, OSAC-4547):** consume this API to present the volume list and detail views; tracked separately.

## Open Questions

### 8.1 Should vendor storage identifiers ever be visible for support?

- **Owner:** Storage WG / product
- **Impact:** Whether a Cloud Provider Admin should be able to see a volume's underlying vendor identifier for support workflows. Kept out of the public representation for now; can be added later without affecting the read model.

---

## Provenance

Authored: draft @ prd 0.9.0 - f7f8c6d, workspace HEAD @ 93ca7ba16

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"f7f8c6d","source_repo":"93ca7ba16","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":25,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
