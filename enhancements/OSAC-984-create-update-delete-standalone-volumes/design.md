---
title: volume-cud-public-api
authors:
  - Akshay Nadkarni
creation-date: 2026-09-11
last-updated: 2026-09-12
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2685
prd:
  - "prd.md"
see-also:
  - "OSAC-2872 (storage control plane — private Volume API)"
  - "OSAC-4542 (Volume Get/List public API)"
  - "OSAC-4884 (attach/detach)"
---

# Volume CUD Public API

## Summary

Add Create, Update, and Delete operations to the public Volume API: extend the
existing read-only `osac.public.v1.Volumes` service (OSAC-4542) with `Create`,
`Update`, and `Delete` RPCs over gRPC and REST at `/api/fulfillment/v1/volumes`.
The public server wraps `PrivateVolumesServer`, reusing its DAO, tenancy
enforcement, tier resolution, and immutability validation, and maps
private-to-public so that internal routing fields never leave the service.
Additionally, the CSI driver is updated to auto-populate `display_name` with
`{pvc-name}.{namespace}` for CSI-provisioned volumes.

See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC-4542 delivered read-only public Volume endpoints (Get/List), but tenants
still cannot create, update, or delete volumes through the public API. Volume
lifecycle remains gated behind the private API, blocking the console's storage
management flow and preventing tenants from preparing storage independently from
compute.

### Goals

- Extend the public `VolumesServer` (from OSAC-4542) with Create, Update, and
  Delete, following the established `ComputeInstancesServer` wrapper pattern.
- Inherit tier resolution, immutability validation, and tenant scoping from the
  private server rather than reimplementing them.
- Expose only tenant-meaningful fields in responses; keep internal routing
  (`backend`, `protocol`, `hub`, `vendor_volume_id`, `vendor_context`) private.
- Validate that the resolved storage tier uses the block protocol; reject NFS
  tiers with a clear error until file-storage support ships.
- Guard delete requests for volumes with active attachments via
  `FailedPrecondition`. The guard is a no-op in this release (no attachment
  query mechanism exists); it is tracked by
  [OSAC-5189](https://redhat.atlassian.net/browse/OSAC-5189) as a follow-up
  dependency on OSAC-4884.
- Auto-populate `display_name` for CSI-provisioned volumes with
  `{pvc-name}.{namespace}` for traceability.
- Introduce no schema change — reuse the OSAC-2872 `volumes` table.

### Non-Goals

- Volume expansion, snapshots, clones, and restore —
  [OSAC-48](https://redhat.atlassian.net/browse/OSAC-48).
- Volume attach/detach —
  [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884).
- Force-delete for volumes with active attachments — deferred to OSAC-4884;
  requires an attachment query mechanism that does not exist yet.
- File storage (NFS) volume creation —
  [OSAC-4515](https://redhat.atlassian.net/browse/OSAC-4515). Block protocol
  only this release.
- Generated volume names — the public API always requires a user-provided name.
- Project-specific volume ownership or sharing rules.

## Proposal

Enumerated changes across `fulfillment-service` and `osac-csi-driver`:

1. **Public proto extension.** Add `Create`, `Update`, and `Delete` RPCs to
   the existing public `Volumes` service, with REST transcoding at
   `/api/fulfillment/v1/volumes`. Add corresponding request/response messages
   mirroring the private proto pattern (including `update_mask` and `lock` on
   UpdateRequest). The public `Volume` type already omits private status
   fields (OSAC-4542); no type changes needed.

2. **Public `VolumesServer` CUD methods** (`internal/servers/volumes_server.go`):
   add an `inMapper` (public-to-private, `SetStrict(true)`,
   `AddIgnoredFields(statusField.FullName())`) alongside the existing
   `outMapper`. Implement `Create`, `Update`, and `Delete` following the
   `ComputeInstancesServer` pattern. Add block-protocol validation on Create.

3. **Authorization** (`authz.rego`): add `Volumes/Create`, `Volumes/Update`,
   and `Volumes/Delete` to the `has_client_permissions` allow block alongside
   the Get/List entries from OSAC-4542.

4. **CSI driver display_name** (`osac-csi-driver`): extract PVC name and
   namespace from CSI parameters and set `metadata.display_name` to
   `{pvc-name}.{namespace}` on `CreateVolume`.

### Workflow Description

Actors: **Tenant User / Tenant Admin** (create, update, delete volumes via
console or CLI), **Cloud Provider Admin** (manage across tenants).

#### Create Flow

```text
HTTP/gRPC client
  -> REST gateway (grpc-gateway mux)              [REST callers only]
  -> gRPC interceptors: authn (JWT) -> authz (OPA) -> tenancy
  -> public VolumesServer.Create
     1. Validate required fields (name, storage_tier, size_gib, access_mode)
     2. Resolve tier via TierResolverFunc -> TierResolution{Backend, Protocol}
     3. Reject if Protocol != BLOCK (block-only guard — public layer)
     4. Map public Volume -> private Volume (inMapper)
     5. Delegate to PrivateVolumesServer.Create
        a. Validate volume fields (private validation)
        b. Set initial status (state=CREATING, backend, protocol)
        c. GenericServer.Create -> GenericDAO -> PostgreSQL
     6. Map private response -> public response (outMapper, strips private fields)
  -> Return public Volume in CREATING state
```

#### Update Flow

```text
HTTP/gRPC client
  -> gRPC interceptors: authn -> authz -> tenancy
  -> public VolumesServer.Update
     1. Validate object.id is present
     2. Two paths based on field mask:
        a. With mask: map public fields into empty private object with ID
        b. Without mask: GET current private object, merge public fields onto it
     3. Delegate to PrivateVolumesServer.Update
        a. Fetch existing, clone, merge, validate immutability
        b. GenericServer.Update -> GenericDAO -> PostgreSQL
     4. Map private response -> public response (outMapper)
  -> Return updated public Volume
```

#### Delete Flow

```text
HTTP/gRPC client
  -> gRPC interceptors: authn -> authz -> tenancy
  -> public VolumesServer.Delete
     1. Translate public ID to private DeleteRequest
     2. Delegate to PrivateVolumesServer.Delete
        a. GenericServer.Delete -> sets DELETING state, adds finalizer
     3. Return empty response
  -> Return success (empty body)
```

### API Extensions

**New public gRPC RPCs** added to `osac.public.v1.Volumes`:

| RPC | HTTP Method | Path | Body | Response |
|---|---|---|---|---|
| `Create` | `POST` | `/api/fulfillment/v1/volumes` | `object` | `object` (Volume in CREATING state) |
| `Update` | `PATCH` | `/api/fulfillment/v1/volumes/{object.id}` | `object` | `object` (updated Volume) |
| `Delete` | `DELETE` | `/api/fulfillment/v1/volumes/{id}` | — | empty |

**New public request/response messages:**

```protobuf
message VolumesCreateRequest {
  Volume object = 1;
}

message VolumesCreateResponse {
  Volume object = 1;
}

message VolumesUpdateRequest {
  Volume object = 1;
  google.protobuf.FieldMask update_mask = 2;
  bool lock = 3;
}

message VolumesUpdateResponse {
  Volume object = 1;
}

message VolumesDeleteRequest {
  string id = 1;
}

message VolumesDeleteResponse {}
```

These mirror the private proto request/response pattern exactly, matching the
convention used by `ComputeInstances`, `Clusters`, and `VirtualNetworks`.

**Public Volume type (unchanged from OSAC-4542):**

```protobuf
message Volume {
  string id = 1;
  Metadata metadata = 2;
  VolumeSpec spec = 3;
  VolumeStatus status = 4;
}

message VolumeSpec {
  string storage_tier = 1;
  int64 size_gib = 2;
  VolumeAccessMode access_mode = 3;
}

// Public VolumeStatus exposes ONLY these fields:
message VolumeStatus {
  VolumeState state = 1;
  optional string message = 2;
  // vendor_volume_id, backend, protocol, hub, vendor_context: EXCLUDED
}
```

**No new CRDs, webhooks, or external resources.** The `volumes` table schema
is unchanged.

### Volume Name Origins

Volumes reach the inventory through two paths. Both produce valid volumes
visible through Get/List; the public CUD API adds the second path.

| Path | Name format | display_name | Example |
|---|---|---|---|
| CSI/PVC (existing) | `pvc-{PVC-UID}` (auto-generated by external-provisioner) | `{pvc-name}.{namespace}` (auto-populated by CSI driver — new) | name: `pvc-a1b2c3d4`, display_name: `my-database.prod` |
| Public CUD API (new) | User-provided, human-readable, DNS label format | Optional — user's chosen name is already readable | name: `analytics-data`, display_name: (empty or user-set) |

### Validation Rules

#### Create Validation

| Field | Rule | Error Code | Message |
|---|---|---|---|
| `metadata.name` | Required, DNS label (`^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`), max 63, unique within tenant | `InvalidArgument` | "field 'metadata.name' is required" / buf validation |
| `spec.storage_tier` | Required, must resolve to a valid tier | `InvalidArgument` / `NotFound` | "field 'spec.storage_tier' is required" |
| `spec.storage_tier` | Resolved tier must use block protocol | `InvalidArgument` | "Storage tier '{tier_name}' uses protocol NFS which is not supported in this release. Only block-protocol tiers are accepted." |
| `spec.size_gib` | Required, > 0 | `InvalidArgument` | "field 'spec.size_gib' must be greater than zero" |
| `spec.access_mode` | Required, must be a defined enum value | `InvalidArgument` | "field 'spec.access_mode' is required" |
| `status` | Ignored from client — set by server | — | — |
| Duplicate name | Same name exists in tenant (not archived) | `AlreadyExists` | "volume with name '{name}' already exists in tenant '{tenant}'" |

#### Update Validation

| Field | Rule | Error Code | Message |
|---|---|---|---|
| `object.id` | Required | `InvalidArgument` | "object identifier is mandatory" |
| `metadata.name` | Immutable — rejected if changed | `InvalidArgument` | "field 'metadata.name' is immutable and cannot be changed after creation" |
| `spec.storage_tier` | Immutable | `InvalidArgument` | "field 'spec.storage_tier' is immutable and cannot be changed after creation" |
| `spec.size_gib` | Immutable | `InvalidArgument` | "field 'spec.size_gib' is immutable and cannot be changed after creation" |
| `spec.access_mode` | Immutable | `InvalidArgument` | "field 'spec.access_mode' is immutable and cannot be changed after creation" |
| Volume state | Rejected if `DELETING` or `DELETED` | `FailedPrecondition` | "volume in state '{state}' cannot be updated" |
| Version conflict | When `lock=true`, `metadata.version` must match current | `Aborted` | "optimistic lock failure: version mismatch" |

Mutable fields: `metadata.display_name`, `metadata.description`,
`metadata.labels`, `metadata.annotations`.

#### Delete Validation

| Condition | Error Code | Message |
|---|---|---|
| Volume not found / archived | `NotFound` | Standard not-found |
| Volume has active attachments | `FailedPrecondition` | "volume has active attachments and cannot be deleted; detach all resources first" |
| Volume already deleting | Idempotent — no error, no second deletion | — |

### Implementation Details

#### Private-to-Public Field Mapping (Allowlist Enforcement)

The field allowlist is enforced at the proto schema level: the public `Volume`
proto defines only the allowed fields (`id`, `metadata`, `spec`, and a
`VolumeStatus` containing only `state` and `message`). The `outMapper` with
`SetStrict(false)` silently drops any private field not present in the public
type.

This is functionally equivalent to a positive allowlist and is the established
OSAC pattern (used by `ComputeInstancesServer`, `ExternalIPsServer`, and the
read-only `VolumesServer` from OSAC-4542). A generated-schema guard test
(see Test Plan) asserts the exact field set of the public proto, so any future
private field added without `[(cleanapi.field).private = true]` fails the build.

Fields **never exposed** in the public API:

| Private field | Reason |
|---|---|
| `VolumeStatus.vendor_volume_id` | Opaque vendor identifier — no tenant meaning |
| `VolumeStatus.backend` | Internal StorageBackend name — topology leak |
| `VolumeStatus.protocol` | Internal routing — resolved from tier |
| `VolumeStatus.hub` | Hub cluster identifier — infrastructure detail |
| `VolumeStatus.vendor_context` | Backend-specific attach parameters — opaque |

#### Block-Protocol Validation

The public `VolumesServer.Create` method calls the `TierResolverFunc` (already
used by the private server) and checks the resolved `TierResolution.Protocol`.
If the protocol is not `STORAGE_PROTOCOL_BLOCK`, the request is rejected with
`InvalidArgument` before delegating to the private server.

This check is added to the **public** server layer, not the private server,
because:
- The private server is also called by the CSI driver, which may have different
  protocol support timelines.
- NFS support is purely additive — removing this check is the only change needed
  when file storage ships. No API contract change required.

```go
resolved, err := s.tierResolver(ctx, vol.GetSpec().GetStorageTier())
if err != nil {
    return nil, err
}
if resolved.Protocol != privatev1.StorageProtocol_STORAGE_PROTOCOL_BLOCK {
    return nil, grpcstatus.Errorf(grpccodes.InvalidArgument,
        "storage tier '%s' uses protocol %s which is not supported in this release; "+
        "only block-protocol tiers are accepted",
        vol.GetSpec().GetStorageTier(),
        resolved.Protocol.String())
}
```

#### Delete with Active Attachments (Cross-Feature Dependency)

The public Delete API must return `FailedPrecondition` if the volume has active
attachments. However, the attachment query mechanism does not exist until
OSAC-4884 (attach/detach) ships.

**Initial implementation (this design):** Delete delegates directly to the
private server without an attachment check — the guard is a **no-op** until
OSAC-4884 provides the attachment query mechanism. The private server's
finalizer-based deletion handles cleanup, so deletion is safe even without the
pre-check; the UX is suboptimal (the user is not warned before deleting an
attached volume) but there is no data loss.

**Follow-up ([OSAC-5189](https://redhat.atlassian.net/browse/OSAC-5189)):**
The public `VolumesServer.Delete` must be updated to query the attachment state
before delegating. This follow-up is tracked by OSAC-5189 and is a **mandatory
prerequisite** before OSAC-4884 (attach/detach) can ship — without the guard,
users could delete volumes from under running workloads.

Design constraint for OSAC-4884: the attach/detach feature must provide a
mechanism (DB query, gRPC call, or shared function) for the volume delete path
to query whether a volume has active attachments. The Volume CUD API will use
whatever interface OSAC-4884 provides.

#### CSI Driver display_name Auto-Population

**Current state:** The CSI driver sets `metadata.name` to `pvc-{PVC-UID}` but
never sets `display_name`. The `--extra-create-metadata` flag is already
configured on the external-provisioner sidecar, so PVC name and namespace are
available in `req.GetParameters()`.

**Changes:**

1. `pkg/fulfillment/volume.go`: add `PVCName` and `PVCNamespace` to
   `CreateVolumeParams`.
2. `pkg/driver/controller.go`: extract `csi.storage.k8s.io/pvc/name` and
   `csi.storage.k8s.io/pvc/namespace` from parameters.
3. `pkg/fulfillment/grpc_client.go`: construct and set display_name:

```go
if params.PVCName != "" && params.PVCNamespace != "" {
    displayName := params.PVCName + "." + params.PVCNamespace
    if len(displayName) > 63 {
        displayName = displayName[:63]
    }
    md.SetDisplayName(displayName)
}
```

**Truncation:** The proto enforces `max_len: 63` on `display_name`. Kubernetes
PVC names can be up to 253 characters. If the combined
`{pvc-name}.{namespace}` exceeds 63 characters, truncate to 63 characters.
The truncation is deterministic and preserves as much of the PVC name as
possible. No StorageClass or Helm chart changes are needed.

#### Update State Validation

Updates to volumes in terminal or transitional delete states are rejected at
two levels for defence in depth:

1. **Public pre-check (clear client error).** The public server fetches the
   current state before delegation and returns `FailedPrecondition` if the
   volume is `DELETING` or `DELETED`:

```go
existing, err := s.getPrivateVolume(ctx, id)
if err != nil {
    return nil, err
}
state := existing.GetStatus().GetState()
if state == privatev1.VolumeState_VOLUME_STATE_DELETING ||
   state == privatev1.VolumeState_VOLUME_STATE_DELETED {
    return nil, grpcstatus.Errorf(grpccodes.FailedPrecondition,
        "volume in state '%s' cannot be updated", state.String())
}
```

2. **Atomic DAO predicate (concurrency guard).** The private server's update
   path uses `GenericDAO.Update` with `lock=false` by default, which does not
   re-check lifecycle state at write time. A concurrent `Delete` that
   transitions the volume to `DELETING` between the public pre-check and the
   private write could allow a stale metadata update. To close this race, the
   DAO update must include a lifecycle predicate (e.g., a SQL `WHERE state NOT
   IN ('DELETING', 'DELETED')` clause) so that the write is rejected
   atomically if the volume was concurrently deleted.

   **Zero-row disambiguation.** When the DAO lifecycle predicate causes the
   `UPDATE` to affect zero rows, the caller cannot distinguish between three
   failure modes from the row count alone. The update path must perform a
   follow-up read to disambiguate:

   | Follow-up read result | Meaning | gRPC error |
   |---|---|---|
   | Volume exists with state `DELETING` or `DELETED` | Concurrent delete won the race | `FailedPrecondition` ("volume in state '...' cannot be updated") |
   | Volume not found | Volume was deleted and archived between the pre-check and the write | `NotFound` |
   | Volume exists with a different `metadata.version` | Concurrent update won; the lifecycle predicate passed but the version predicate failed | `Aborted` ("optimistic lock failure: version mismatch") |

   The pre-check (step 1) is retained for the common-path clear error message;
   the DAO predicate plus follow-up read is the correctness guarantee for the
   race window.

### Security Considerations

- Internal routing fields (`backend`, `protocol`, `hub`, `vendor_volume_id`,
  `vendor_context`) are excluded from the public type by construction.
  A generated-schema guard test prevents accidental exposure.
- The `status` field is ignored on the `inMapper` so clients cannot set
  lifecycle state or internal fields through Create/Update.
- Input validation (name format, tier existence, size bounds, access mode
  enum) prevents malformed resources from reaching the DAO.
- CEL filters are constrained to the public field set via `SetFilterDesc`.
- Tenant isolation is enforced by the existing tenancy layer at the
  GenericServer/DAO level, not reimplemented.

### Failure Handling and Recovery

| Scenario | Behavior |
|---|---|
| **Create — invalid input** | Returns `InvalidArgument` with field-level message. No resource created. |
| **Create — duplicate name** | Returns `AlreadyExists`. No resource created. |
| **Create — NFS tier** | Returns `InvalidArgument` with protocol-specific message. No resource created. |
| **Create — tier not found** | Returns `NotFound` or `InvalidArgument` from tier resolver. No resource created. |
| **Create — backend failure** | Volume created in DB with `CREATING` state. Backend reconciler retries. If retries exhausted, state moves to `FAILED`. |
| **Update — version conflict** | Returns `Aborted`. No change applied. Client retries with fresh version. |
| **Update — immutable field** | Returns `InvalidArgument`. No change applied. |
| **Update — deleting/deleted** | Returns `FailedPrecondition`. No change applied. |
| **Delete — not found/archived** | Returns `NotFound`. |
| **Delete — active attachments** | Returns `FailedPrecondition` (after OSAC-4884). |
| **Delete — already deleting** | Idempotent — returns success. No second deletion started. |
| **Delete — backend cleanup fails** | Volume remains in `DELETING`. Backend reconciler retries. Name stays reserved. |
| **Mapping error** | Returns `Internal` (logged). No partial data returned. |

### RBAC / Tenancy

Scoping is inherited, not reimplemented. OPA (`authz.rego`) gates method
access — this design adds `Volumes/Create`, `Volumes/Update`, and
`Volumes/Delete` to the `has_client_permissions` allowlist. Row scoping comes
from `GenericServer`/`GenericDAO` via `DefaultTenancyLogic.DetermineVisibleTenants`.

Authorization matrix:

| Actor | Create | Update | Delete | Get/List |
|---|---|---|---|---|
| Tenant User | Own tenant | Own tenant | Own tenant | Own tenant (+ shared) |
| Tenant Admin | Own tenant | Own tenant | Own tenant | Own tenant (+ shared) |
| Cloud Provider Admin | All tenants | All tenants | All tenants | All tenants |
| CSI Driver | Private API only | Private API only | Private API only | Private API only |
| Unauthenticated | `Unauthenticated` | `Unauthenticated` | `Unauthenticated` | `Unauthenticated` |

Tenant User and Tenant Admin have identical scope for CUD, consistent with
OSAC-2872 and OSAC-4542. The creating user is recorded in `metadata.creator`
for audit but does not restrict access.

### Observability and Monitoring

No new observability changes. Existing gRPC metrics, structured request logging,
and the interceptor chain apply to the new methods automatically. Volume
lifecycle state transitions (CREATING -> AVAILABLE, CREATING -> FAILED,
* -> DELETING -> DELETED) are already logged by the private server's reconciler.

### Extensibility / Future-Proofing

| Future capability | Impact on this design |
|---|---|
| **NFS/file-storage support (OSAC-4515)** | Remove the block-protocol check in the public server. No API contract change — protocol is not in the public schema. |
| **Attach/detach (OSAC-4884)** | Enable the attachment guard on Delete ([OSAC-5189](https://redhat.atlassian.net/browse/OSAC-5189)). Add `force` delete flag. No API contract change — the Delete request can add an optional `force` field additively. |
| **Volume expansion** | Add a separate `Resize` RPC. No change to Update — size remains immutable in Update. |
| **Volume snapshots/clones** | New RPCs and types. No change to existing CUD. |
| **Project-scoped ownership** | Enforced at the GenericServer/DAO level. No change to the Volume proto or server. |

### Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Private field leakage through future proto changes | High | Public proto defines only allowed fields; schema guard test fails build on unexpected fields |
| Block-protocol validation bypassed via private API | Low | Intentional — CSI driver may have different protocol timelines. Public API is the tenant surface. |
| display_name exceeds 63-char limit | Low | Truncate deterministically to 63 characters |
| Delete/attach race condition (TOCTOU) | Medium | OSAC-4884 must use finalizers or DB-level locking; documented as cross-feature constraint |
| cleanapi leaves unused imports on regeneration | Low | Hand-prune as established in OSAC-4542; follow-up tooling improvement |

### Drawbacks

- The attachment check on Delete is deferred until OSAC-4884 ships, so initially
  a volume with active attachments can be deleted through the public API. The
  private server's finalizer/reconciler handles cleanup, so this is safe but not
  ideal from a UX perspective.

## Alternatives (Not Implemented)

- **Separate public proto file (hand-written).** Rejected — public protos are
  generated from private via cleanapi by convention; hand-writing would diverge
  and drift on regeneration.
- **GenericMapper allowlist mode.** Rejected — GenericMapper only supports
  blocklist (`AddIgnoredFields`). The proto-level allowlist (public proto
  defines only allowed fields) is functionally equivalent and is the
  established pattern.
- **Block-protocol check in the private server.** Rejected — the CSI driver
  also uses the private server and may need NFS support on a different timeline.
  The check belongs in the public-facing layer.
- **LRO (Long-Running Operation) pattern for Create.** Rejected — the current
  synchronous-return-with-status-polling (return volume in CREATING state,
  client polls via Get) is pragmatic and consistent with the existing
  ComputeInstances pattern. LRO can be adopted later if needed.

## Open Questions

None — all design decisions were resolved during the PRD review and pre-design
discussions.

## Test Plan

### Requirement Traceability

| PRD Requirement | Test Cases | Type |
|---|---|---|
| Create requires name, storage_tier, size_gib, access_mode | TC-C1, TC-C2, TC-C3, TC-C4, TC-C5, TC-IT1 | Unit, Integration |
| Name unique within tenant, immutable | TC-C7, TC-U2, TC-U2c, TC-IT3, TC-IT5 | Unit, Integration |
| Immutable fields: storage_tier, size_gib, access_mode | TC-U2, TC-U2a, TC-U2b, TC-IT3 | Unit, Integration |
| Mutable fields: display_name, description, labels, annotations | TC-U1, TC-IT2 | Unit, Integration |
| Status set by server, client input ignored | TC-C8 | Unit |
| Lifecycle: creating -> available / failed | TC-C1, TC-C9, TC-IT1, E2E-1 | Unit, Integration, E2E |
| Failed is terminal; not retried in place | TC-C9 | Unit |
| Available/failed -> deleting -> deleted | TC-D1, TC-IT4, E2E-1 | Unit, Integration, E2E |
| Idempotent delete (already deleting) | TC-D3 | Unit |
| Archived volume returns not found | TC-D4, TC-IT4 | Unit, Integration |
| Name reserved until deletion complete | TC-IT4 | Integration |
| Tenant-scoped; Tenant Admins manage all | TC-A1, TC-IT5, TC-IT5a | Unit, Integration |
| Cloud Provider Admin cross-tenant access | TC-IT5b | Integration |
| Clear error for invalid/unauthorized/duplicate | TC-C2--C7, TC-U2--U4 | Unit |
| Optimistic locking | TC-U3 | Unit |
| Block-protocol validation | TC-C6 | Unit |
| Delete with active attachments returns FailedPrecondition | TC-D5 (gated on OSAC-4884 / OSAC-5189) | Unit |
| Private fields never exposed in public API | TC-MAP1, TC-MAP2, TC-IT6 | Unit, Integration |
| CSI display_name auto-population | TC-CSI1--4, E2E-2 | Unit, E2E |

**Coverage summary:** 19 PRD requirements mapped to 30+ test cases across
unit, integration, and E2E tiers.

### Test Infrastructure

Tests follow the existing OSAC Go test patterns using `testify/assert` and
`testify/require`. Key references in the osac repo:

- **Unit test pattern:** `fulfillment-service/internal/servers/compute_instances_server_test.go`
  — mock gRPC server, mock tier resolver, `testify` assertions. Follow for
  `volumes_server_test.go`.
- **OPA authorization:** `fulfillment-service/internal/auth/grpc_authz_interceptor_test.go`
  — pre-built test clients with tenant/admin/CSI identities.
- **Integration tests:** `fulfillment-service/it/it_compute_instances_test.go`
  — authenticated gRPC client against kind `osac-dev` cluster. Follow for
  `it_public_volumes_test.go`.
- **E2E tests:** `e2e/` harness with `wait_for_state` polling helpers.
- **Fixtures:** Mock tier resolver returns
  `TierResolution{Backend: "test-backend", Protocol: STORAGE_PROTOCOL_BLOCK}`;
  tenant context configured via test gRPC metadata.

### Unit Tests

**Public server (`fulfillment-service/internal/servers/volumes_server_test.go`):**
- TC-C1: `Create` with valid input (`name="analytics-data"`,
  `storage_tier="standard-block"`, `size_gib=100`,
  `access_mode=READ_WRITE_ONCE`) returns a public Volume in CREATING state
  with spec fields populated and no private status fields.
- TC-C2: `Create` with missing `metadata.name` returns `InvalidArgument`.
- TC-C3: `Create` with missing `spec.storage_tier` returns `InvalidArgument`.
- TC-C4: `Create` with missing `spec.size_gib` (or `size_gib=0`) returns
  `InvalidArgument`: "field 'spec.size_gib' must be greater than zero".
- TC-C4a: `Create` with `size_gib=-1` returns `InvalidArgument`: "field
  'spec.size_gib' must be greater than zero".
- TC-C5: `Create` with missing `spec.access_mode` returns `InvalidArgument`.
- TC-C6: `Create` with an NFS-protocol tier returns `InvalidArgument` with
  protocol-specific message.
- TC-C7: `Create` with a duplicate name returns `AlreadyExists`.
- TC-C8: `Create` ignores client-set status fields (inMapper drops status).
- TC-C9: `Create` with backend failure — mock the backend to fail creation;
  assert the volume is created in `CREATING` state, transitions to `FAILED`
  after retries are exhausted, does not retry further, and follows the
  documented `FAILED -> DELETING -> DELETED` path on deletion.
- TC-U1: `Update` with mutable metadata fields (`display_name="prod-volume"`,
  `description="Primary storage"`, `labels={"env":"prod"}`,
  `annotations={"team":"storage"}`) succeeds and returns updated public Volume
  reflecting all four fields.
- TC-U2: `Update` that changes `spec.storage_tier` from `"standard-block"` to
  `"premium-block"` (value included in update mask) returns `InvalidArgument`.
- TC-U2a: `Update` that changes `spec.size_gib` from `100` to `200` returns
  `InvalidArgument`.
- TC-U2b: `Update` that changes `spec.access_mode` from `READ_WRITE_ONCE` to
  `READ_ONLY_MANY` returns `InvalidArgument`.
- TC-U2c: `Update` that changes `metadata.name` from `"analytics-data"` to
  `"renamed-volume"` returns `InvalidArgument`: "field 'metadata.name' is
  immutable and cannot be changed after creation".
- TC-U3: `Update` with `lock=true` and stale version returns `Aborted`.
  After the rejection, `Get` the volume and assert that all fields and
  `metadata.version` are unchanged from the pre-update state.
- TC-U4: `Update` on a volume in DELETING state returns `FailedPrecondition`.
- TC-D1: `Delete` of an available volume returns success (empty response).
- TC-D2: `Delete` of a non-existent volume returns `NotFound`.
- TC-D3: `Delete` of an already-deleting volume is idempotent (no error).
- TC-D4: `Delete` of an archived volume returns `NotFound`.
- TC-D5: `Delete` of a volume with active attachments (mocked attachment
  state) returns `FailedPrecondition`. Initially gated behind OSAC-4884;
  enabled once the attachment query mechanism is available.
- TC-MAP1: **Generated-schema guard:** assert the public `VolumeStatus`
  descriptor contains exactly `state` and `message` — no other fields.
  Fails the build if a private field leaks into the public proto.
- TC-MAP2: Field mapping: public response carries `spec` (tier/size/access_mode)
  and `status` (state/message); private fields (`vendor_volume_id`, `backend`,
  `protocol`, `hub`, `vendor_context`) are absent by type. Additionally, assert
  at the descriptor level that `vendor_volume_id` does not appear in the public
  `Volume`, `VolumesCreateRequest`, or `VolumesUpdateRequest` message
  descriptors — preventing accidental exposure through request types.
- TC-MAP3: `List` forwards `order` parameter to delegate (spy/mock assertion on
  `SetOrder`).

**OPA authorization (`fulfillment-service/internal/auth/grpc_authz_interceptor_test.go`):**
- TC-A1: Tenant client is allowed on `Volumes/Create`, `/Update`, `/Delete`,
  `/Get`, `/List`.
- TC-A2: Tenant client calling `Signal` on the public `Volumes` service
  receives `Unimplemented` — `Signal` is a private-only RPC that is not
  registered on the public server, so gRPC returns `Unimplemented` before OPA
  is reached.
- TC-A3: CSI driver is denied on public `Volumes/Create` (CSI uses private API).

**CSI driver (`osac-csi-driver/pkg/driver/controller_test.go`,
`osac-csi-driver/pkg/fulfillment/grpc_client_test.go`):**
- TC-CSI1: `CreateVolume` extracts PVC name and namespace from parameters and
  populates `CreateVolumeParams.PVCName` and `.PVCNamespace`.
- TC-CSI2: `grpcVolumeClient.CreateVolume` sets `display_name` to
  `{pvc-name}.{namespace}`.
- TC-CSI3: When PVC name + namespace exceeds 63 characters, `display_name` is
  truncated to exactly 63 characters by simple prefix truncation.
  `PVCName="my-database-volume-with-a-very-long-name-that-needs-truncat0"`
  (60 chars) + `PVCNamespace="production"` → combined
  `"my-database-volume-with-a-very-long-name-that-needs-truncat0.production"`
  (71 chars) → expected `display_name` =
  `"my-database-volume-with-a-very-long-name-that-needs-truncat0.pr"`
  (63 chars).
- TC-CSI4: When PVC name or namespace is missing, `display_name` is not set.
  Covers three sub-cases: PVC name missing, namespace missing, and namespace
  empty string.

### Integration Tests

**Against the kind `osac-dev` cluster (`fulfillment-service/it/it_public_volumes_test.go`):**
- TC-IT1: Create a volume via the public gRPC endpoint with a valid storage
  tier. Assert the returned Volume has the expected spec, CREATING state,
  and no private status fields.
- TC-IT2: Update the volume's `display_name` and `description`. Assert the
  returned Volume reflects the changes.
- TC-IT3: Attempt to update `spec.storage_tier`. Assert `InvalidArgument`.
- TC-IT4: Delete the volume. Assert success. Poll `Get` and assert the volume
  transitions through `DELETING` before returning `NotFound` (after archival).
  Additionally, attempt to create a new volume with the same name while the
  original is in `DELETING` state and assert the name is reserved
  (`AlreadyExists`); after deletion completes, retry creation with the same
  name and assert success.
- TC-IT5: Tenant isolation: a subject in tenant A cannot see or manage volumes
  created by tenant B. Verify that an ordinary tenant client is denied
  cross-tenant `Update` and `Delete` (not just `Get/List`).
- TC-IT5a: Same-tenant Tenant Admin can Create, Update, and Delete volumes
  within their own tenant.
- TC-IT5b: Cloud Provider Admin can manage volumes across all tenants.
- TC-IT6: Public `VolumeStatus` field allowlist: assert the public Volume
  response contains exactly the expected fields — use a positive allowlist
  assertion, not a blocklist.

### E2E Tests

- Provision a volume via the public API, update its metadata, then delete it.
  Assert lifecycle states at each step (CREATING -> AVAILABLE -> DELETING).
- Create a volume via the CSI/PVC path and verify `display_name` is populated
  with `{pvc-name}.{namespace}` via the public Get API.

### Cross-Cutting Dimensions

| Dimension | Status |
|---|---|
| **Storage** | Primary — this design |
| **Provisioning** | Public CUD adds tenant-driven provisioning alongside CSI |
| **Tenant Onboarding** | Inherits existing tenancy; no new onboarding steps |
| **Installation** | No new deployment artifacts; endpoints register automatically |
| **Documentation** | Deferred — API reference documentation will be added as part of the docs sprint following milestone 0.3 |
| **UI / Console** | Deferred — console storage management integration tracked separately |

## Graduation Criteria

Ships as part of the public Volume API in milestone 0.3. Graduation
requirements:
- All TC-* unit tests pass (TC-C1 through TC-MAP3, TC-A1 through TC-A3,
  TC-CSI1 through TC-CSI4), **excluding** TC-D5 which is gated on
  OSAC-4884 / [OSAC-5189](https://redhat.atlassian.net/browse/OSAC-5189).
- All TC-IT* integration tests pass against the kind cluster.
- Both E2E scenarios (E2E-1, E2E-2) pass.
- No regressions in existing volume or ComputeInstances tests.
- Pre-commit CI is green.

No separate maturity ladder; the CUD endpoints graduate with the rest of the
public API.

## Upgrade / Downgrade Strategy

Additive API surface with no schema change. Upgrade adds the new CUD endpoints;
downgrade removes them with no data migration. Volumes created via the public API
use the same DB table and reconciler as CSI-created volumes, so they remain
accessible through the private API after downgrade.

## Version Skew Strategy

The public API is generated from the private API and served by the same process;
there is no cross-component skew. An older console simply does not call the new
CUD endpoints. The CSI driver display_name change is backward-compatible — older
CSI drivers simply leave display_name empty.

## Support Procedures

Failures surface as standard gRPC/REST errors (`InvalidArgument`, `AlreadyExists`,
`FailedPrecondition`, `NotFound`, `Aborted`, `Internal`) visible in request logs.
The CUD endpoints can be effectively disabled by removing their entries from the
OPA allowlist (callers then receive `PermissionDenied`); this does not affect
CSI-driven provisioning, which uses the private API.

## Infrastructure Needed

None.

## Task Decomposition

### Task 1: Public Volume CUD API + Fulfillment Service

**Starting point:** [osac PR #743](https://github.com/osac-project/osac/pull/743)

**Scope:**
- Extend public Volume proto with Create/Update/Delete RPCs and
  request/response messages. Regenerate via `buf generate`.
- Extend `VolumesServer` with `inMapper`, `Create`, `Update`, `Delete` methods
  following the `ComputeInstancesServer` pattern.
- Add block-protocol validation on Create.
- Add update state validation (reject DELETING/DELETED).
- Register CUD RPCs on gRPC server and REST gateway (already done in PR #743;
  verify and adjust).
- Add OPA policy entries for the three new public methods.
- Add unit tests (TC-C1 through TC-D4, TC-MAP1 through TC-MAP3, TC-A1 through
  TC-A3).
- Add/update integration tests (TC-IT1 through TC-IT6) with positive
  allowlist field assertions.
- Prune unused cleanapi imports in generated public protos if needed.

**Size:** L (substantial but mechanical — most patterns exist in
ComputeInstances; proto changes are largely generated code)

### Task 2: CSI Driver display_name Auto-Population

**Starting point:** New — no existing PR.

**Scope:**
- Add `PVCName` and `PVCNamespace` fields to `CreateVolumeParams`.
- Extract `csi.storage.k8s.io/pvc/name` and `csi.storage.k8s.io/pvc/namespace`
  from CSI parameters in `controller.go`.
- Set `display_name` to `{pvc-name}.{namespace}` (with 63-char truncation) in
  `grpc_client.go`.
- Add unit tests (TC-CSI1 through TC-CSI4).

**Size:** S (4 files changed, straightforward extraction and formatting)

---

## Provenance

Authored: draft @ design 0.10.1, enhancement-proposals main @ 51d7e06

Phases: ingest, research, draft, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.10.1","source_repo":"51d7e06","source_repo_branch":"main","phases":["ingest","research","draft","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
