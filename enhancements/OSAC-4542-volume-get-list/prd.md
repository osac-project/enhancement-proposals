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
- **Read-only, tenant-meaningful representation.** The public view exposes only information that is meaningful to tenants; internal placement and routing details used to serve a volume — the serving backend, its storage protocol, the hub that hosts it, and the vendor-assigned volume identifier — are never shown. Volumes are read-only through this API.
- **Stable public identifier.** Each volume has an immutable, tenant-unique `id` that `List` returns and `Get` accepts; `name` is a display attribute and is not the request key. Console deep-links and Get requests use `id`, so they remain stable even if a volume is renamed and are unambiguous when names repeat.
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
- As a Tenant User, I want to list the storage volumes in my tenant, so that I can find a volume and navigate storage inventory in the console. Tenant User and Tenant Admin have the same read scope in this release (both see all volumes in the tenant), consistent with OSAC-2872, where both roles share the same storage capabilities. Restricting a Tenant User to only the volumes they created is explicitly out of scope (see Out of Scope).

### Cloud Infrastructure Admin

- Not affected by this feature.

## Assumptions

- The volumes to be read already exist and are inventoried by the storage control plane (OSAC-2872); this feature adds a read surface, not a new source of data.
- Tenant-level visibility is the correct and consistent default for this release, matching how every other OSAC resource scopes reads. Narrowing a Tenant User to only their own volumes is a separate, platform-wide decision (see Out of Scope).
- The public representation of a volume is a subset of the internal one; fields that are not meaningful to tenants are omitted rather than reshaped.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the private Volume API, the volume inventory, and the tier/backend model this read API surfaces. Must be in place for volumes to exist and be retrievable.
- **Console UI / UX and UI design gates (OSAC-4546, OSAC-4547):** consume this API to present the volume list and detail views; tracked separately.

## Acceptance Criteria

The "consistent with other OSAC list endpoints" behavior above resolves to the following testable contract, inherited from the shared list machinery:

- **Identifier.** `List` items and `Get` both key on the immutable `id`; a `Get` by the `id` of a visible volume returns it, and a `Get` by an id outside the caller's tenants returns `not found` (indistinguishable from a non-existent id, so existence is not leaked across tenants).
- **Filtering.** `List` accepts a CEL filter over public fields only (e.g. `status.state`, `spec.storage_tier`). A filter that references a non-public field (e.g. the serving backend) is rejected as an invalid argument rather than silently ignored.
- **Ordering.** Results have a stable, deterministic order (by `id`) so pagination does not drop or duplicate rows across pages.
- **Pagination.** `List` accepts `offset` and `limit`; the default page size is 100 and the maximum is 1000 (a larger `limit` is capped, not rejected). The response reports the total count so the console can page through the full set.
- **Inventory states.** `List` and `Get` return volumes in every state tracked by OSAC-2872 (`creating`, `available`, `deleting`, `deleted`) as long as the volume remains in inventory; there is no implicit state filter — callers filter by `status.state` if they want a subset.
- **Isolation.** A caller never receives a volume outside their entitled tenants through either `List` or `Get`, and this is covered by an automated tenant-isolation test.

---

## Provenance

Committed: commit @ prd 0.9.0 - f7f8c6d, workspace main @ b177ce9 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"f7f8c6d","source_repo":"b177ce9 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
