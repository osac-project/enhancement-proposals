# Volume Get/List Public API

| Field       | Value   |
|-------------|---------|
| Author(s)   | Zoltan Szabo |
| Jira        | [OSAC-4542](https://redhat.atlassian.net/browse/OSAC-4542) |
| Date        | 2026-08-27 |
| Target Release | 0.3 |

## Problem Statement

The OSAC storage control plane (OSAC-2872) already provisions standalone storage volumes and tracks them in a central inventory, but that inventory is only reachable through the internal API. Tenants and the OSAC console have no supported way to see the volumes that exist. As a result, the console cannot show storage to users, and tenants have no operational visibility into their own volumes — they cannot confirm a volume's size, tier, or state, and administrators cannot review storage usage for troubleshooting or monitoring. This blocks the console's storage experience and leaves volume inventory effectively invisible to the people who own it.

## In Scope

*This release delivers the first, read-only slice of the public Volume API: retrieving individual volumes and listing them. It reuses the volumes already provisioned and inventoried by OSAC-2872 — no new provisioning path is introduced. Mutating operations remain internal and are deferred to later phases of the public Volume API (OSAC-984). See Out of Scope.*

- **Retrieve a volume's details.** A user can fetch a single volume and see its tenant-meaningful attributes — name, tier, size, access mode, and current state — so they can confirm its configuration and availability.
- **List volumes.** A user can list the volumes they are entitled to see, consistent with the standard OSAC list contract, so the console and CLI can present and navigate storage inventory.
- **Tenant- and project-scoped visibility.** Each caller sees only the volumes they are entitled to under OSAC's standard tenant- and project-based visibility: a Cloud Provider Admin across all tenants, and tenant members within the tenants and projects visible to them — the same visibility model used by every other OSAC resource.
- **Read-only, tenant-meaningful representation.** The public view exposes only information that is meaningful to tenants; internal placement and routing details used to serve a volume — the serving backend, its storage protocol, the hub that hosts it, and the vendor-assigned volume identifier — are never shown. Volumes are read-only through this API.
- **Stable public identifier.** Each volume has an immutable, system-generated `id` that `List` returns and `Get` accepts as the request key. `name` is a separate, immutable attribute that is unique within the volume's tenant/project scope (a valid RFC 1123 label), and `display_name` is an optional human-friendly label; neither is the request key. Console deep-links and `Get` requests use `id`.
- **Same access channels as other resources.** Volumes are reachable over the same public gRPC and REST endpoints, console, and CLI as other OSAC resources; no storage-specific access path is introduced. CLI support (`osac get volumes`, `osac get volume <id>`) comes for free from the existing `get_cmd.go` / `list_cmd.go` patterns and requires no separate tracking.
- **Test and documentation.** Tests cover retrieving and listing standalone volumes through the public API, including tenant-scoped isolation; API documentation and the published API spec are updated with the new read endpoints.

## Out of Scope

Deferred to later work (this release is read-only Get/List only):

- **Volume lifecycle through the public API** — creating, updating, and deleting volumes. These remain on the internal API and are tracked under [OSAC-984](https://redhat.atlassian.net/browse/OSAC-984).
- **Volume expansion, snapshots, clones, and restore** — tracked under [OSAC-48](https://redhat.atlassian.net/browse/OSAC-48).
- **Volume attach / detach** — tracked under [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884).
- **Volume identifiability / provenance** — distinguishing what each volume represents (e.g. a VM filesystem disk vs. a workload PV) and which tenant cluster it belongs to. Deferred to [OSAC-4793](https://redhat.atlassian.net/browse/OSAC-4793) under the OSAC-2871 Storage Volumes outcome.
- **File storage** (NFS/SMB — OSAC-4515) and **object storage** (S3).

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to get and list storage volumes across all tenants, so that I have operational visibility for troubleshooting and monitoring.

### Tenant Admin / Tenant User

- As a tenant member, I want to get the details of a specific storage volume — its size, tier, and state — so that I can understand its configuration and verify its availability.
- As a tenant member, I want to list the storage volumes in my tenant, so that I can find a volume and navigate storage inventory in the console. Tenant User and Tenant Admin have the same read scope in this release (both see all volumes in the tenant), consistent with OSAC-2872, where both roles share the same storage capabilities.

### Cloud Infrastructure Admin

- Not affected by this feature.

## Assumptions

- The volumes to be read already exist and are inventoried by the storage control plane (OSAC-2872); this feature adds a read surface, not a new source of data.
- Tenant- and project-scoped visibility is the correct and consistent default for this release, matching how every other OSAC resource scopes reads.
- The public representation of a volume is a subset of the internal one; fields that are not meaningful to tenants are omitted rather than reshaped.

## Dependencies

- **OSAC-2872 (Storage Control Plane):** provides the private Volume API, the volume inventory, and the tier/backend model this read API surfaces. Must be in place for volumes to exist and be retrievable.
- **Console UI / UX and UI design gates (OSAC-4546, OSAC-4547):** consume this API to present the volume list and detail views; tracked separately.

## Acceptance Criteria

`List` inherits the standard OSAC list contract (CEL filtering via `this.<field>`, `offset`/`limit` pagination, SQL-like ordering with implicit secondary sort on `id asc`). The following volume-specific criteria apply:

- **Identifier.** `List` items and `Get` both key on the immutable `id`; a `Get` by the `id` of a visible volume returns it, and a `Get` by an id outside the caller's tenants returns `not found` (indistinguishable from a non-existent id, so existence is not leaked across tenants).
- **Inventory states.** `List` and `Get` return volumes in every non-archived state tracked by OSAC-2872 (`creating`, `available`, `deleting`). Once a volume is fully deprovisioned its record is archived (`deleted`) and no longer appears through `List`/`Get`. There is no other implicit state filter — callers filter by `status.state` for a subset.
- **Isolation.** A caller never receives a volume outside their entitled tenants through either `List` or `Get`, and this is covered by an automated tenant-isolation test.

---

## Provenance

Committed: commit @ prd 0.9.0 - 562b610, workspace prd/OSAC-4542-review-followups @ 04971f4

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"04971f4","source_repo_branch":"prd/OSAC-4542-review-followups","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
