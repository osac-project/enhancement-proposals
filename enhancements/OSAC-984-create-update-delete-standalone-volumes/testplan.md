# Test Plan: Volume CUD Public API

| Field | Value |
|---|---|
| Design Task | [OSAC-2685](https://redhat.atlassian.net/browse/OSAC-2685) |
| Design Document | [design.md](design.md) |
| PRD | [OSAC-984 PRD](prd.md) |

## Requirement Traceability

| PRD Requirement | Test Cases | Type |
|---|---|---|
| Create requires name, storage_tier, size_gib, access_mode | TC-C1, TC-C2, TC-C3, TC-C4, TC-C5, TC-IT1 | Unit, Integration |
| Name unique within tenant, immutable | TC-C7, TC-U2, TC-IT3, TC-IT5 | Unit, Integration |
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
| Clear error for invalid/unauthorized/duplicate | TC-C2–C7, TC-U2–U4 | Unit |
| Optimistic locking | TC-U3 | Unit |
| Block-protocol validation | TC-C6 | Unit |
| Delete with active attachments returns FailedPrecondition | TC-D5 (gated on OSAC-4884) | Unit |
| Private fields never exposed in public API | TC-MAP1, TC-MAP2, TC-IT6 | Unit, Integration |
| CSI display_name auto-population | TC-CSI1–4, E2E-2 | Unit, E2E |

**Coverage summary:** 19 PRD requirements mapped to 30+ test cases across
unit, integration, and E2E tiers.

## Test Infrastructure

Tests follow existing OSAC Go test patterns using `testify/assert` and
`testify/require`. Key references:

- **Unit test pattern:** `compute_instances_server_test.go` — mock gRPC server,
  mock tier resolver, `testify` assertions. Follow for `volumes_server_test.go`.
- **OPA authorization:** `grpc_authz_interceptor_test.go` — pre-built test
  clients with tenant/admin/CSI identities.
- **Integration tests:** `it_compute_instances_test.go` — authenticated gRPC
  client against kind `osac-dev` cluster. Follow for `it_public_volumes_test.go`.
- **E2E tests:** `e2e/` harness with `wait_for_state` polling helpers.
- **Fixtures:** mock tier resolver returns `TierResolution{Backend, Protocol}`;
  tenant context configured via test gRPC metadata.

## Unit Tests

### Public Server — Create

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-C1 | Create with valid input | `name="analytics-data"`, `storage_tier="standard-block"`, `size_gib=100`, `access_mode=READ_WRITE_ONCE` | Volume in CREATING state; spec populated; no private status fields | Create requires name/tier/size/access_mode |
| TC-C2 | Create with missing name | No metadata.name | `InvalidArgument`: "field 'metadata.name' is required" | Clear error for invalid input |
| TC-C3 | Create with missing storage_tier | No spec.storage_tier | `InvalidArgument`: "field 'spec.storage_tier' is required" | Clear error for invalid input |
| TC-C4 | Create with invalid size | spec.size_gib = 0 | `InvalidArgument`: "field 'spec.size_gib' must be greater than zero" | Clear error for invalid input |
| TC-C5 | Create with missing access_mode | spec.access_mode = UNSPECIFIED | `InvalidArgument`: "field 'spec.access_mode' is required" | Clear error for invalid input |
| TC-C6 | Create with NFS-protocol tier | Tier resolves to STORAGE_PROTOCOL_NFS | `InvalidArgument`: "Storage tier '...' uses protocol NFS which is not supported..." | Block-only tiers this release |
| TC-C7 | Create with duplicate name | Same name already exists in tenant | `AlreadyExists` | Name unique within tenant |
| TC-C8 | Create ignores client-set status | Client sends `status.state=AVAILABLE`, `name="ignore-status"`, valid tier/size/access_mode | Status ignored; volume created in CREATING state | Status set by server |
| TC-C9 | Create with backend failure → FAILED lifecycle | `name="fail-test"`, valid tier/size/access_mode; mock backend to reject creation | Volume created in CREATING, transitions to FAILED after retries exhausted; no further retry; delete transitions through DELETING → DELETED | Failed is terminal |

### Public Server — Update

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-U1 | Update mutable metadata fields | Set `display_name="prod-volume"`, `description="Primary storage"`, `labels={"env":"prod"}`, `annotations={"team":"storage"}` | Updated Volume with all four fields applied | Mutable fields |
| TC-U2 | Update immutable spec field (storage_tier) | Change `spec.storage_tier` from `"standard-block"` to `"premium-block"` in mask | `InvalidArgument`: "field 'spec.storage_tier' is immutable..." | Immutable fields |
| TC-U2a | Update immutable spec field (size_gib) | Change `spec.size_gib` from `100` to `200` in mask | `InvalidArgument`: "field 'spec.size_gib' is immutable..." | Immutable fields |
| TC-U2b | Update immutable spec field (access_mode) | Change `spec.access_mode` from `READ_WRITE_ONCE` to `READ_ONLY_MANY` in mask | `InvalidArgument`: "field 'spec.access_mode' is immutable..." | Immutable fields |
| TC-U3 | Update with stale version (lock=true) | lock=true, metadata.version stale | `Aborted`: version mismatch | Optimistic locking |
| TC-U4 | Update volume in DELETING state | Volume state = DELETING | `FailedPrecondition`: "volume in state 'DELETING' cannot be updated" | Updates rejected while deleting |

### Public Server — Delete

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-D1 | Delete available volume | Valid ID, volume in AVAILABLE state | Success (empty response) | Available -> deleting |
| TC-D2 | Delete non-existent volume | Invalid/unknown ID | `NotFound` | Clear error |
| TC-D3 | Delete already-deleting volume | Volume in DELETING state | Success (idempotent, no second deletion) | Idempotent delete |
| TC-D4 | Delete archived volume | Volume already archived | `NotFound` | Archived returns not found |
| TC-D5 | Delete volume with active attachments | Valid ID; mock attachment state as active (gated on OSAC-4884 attachment query) | `FailedPrecondition`: "volume has active attachments..." | Delete with active attachments |

### Field Mapping and Schema Guards

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-MAP1 | Schema guard: public VolumeStatus fields | Reflect on public VolumeStatus descriptor | Contains exactly `state` and `message`; no other fields | Private fields never exposed |
| TC-MAP2 | Response field mapping | Create/Get a volume | Response has id, metadata, spec (tier/size/access_mode), status (state/message); no vendor_volume_id, backend, protocol, hub, vendor_context | Private fields never exposed |
| TC-MAP3 | List order forwarding | List with order="metadata.name asc" | Spy/mock asserts delegate receives SetOrder("metadata.name asc") | Order parameter forwarding |

### OPA Authorization

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-A1 | Tenant client allowed on CUD | Tenant client calls Create, Update, Delete | All allowed | Tenant-scoped access |
| TC-A2 | Tenant client denied on private-only RPC | Tenant client calls `PrivateVolumes/Create` | `PermissionDenied` | Private RPCs not in public allowlist |
| TC-A3 | CSI driver denied on public CUD | CSI driver calls public Create | `PermissionDenied` | CSI uses private API |

### CSI Driver display_name

| ID | Description | Input | Expected | PRD Req |
|---|---|---|---|---|
| TC-CSI1 | PVC name/namespace extraction | Parameters with csi.storage.k8s.io/pvc/name and /namespace | CreateVolumeParams has PVCName and PVCNamespace populated | CSI display_name |
| TC-CSI2 | display_name set correctly | PVCName="my-db", PVCNamespace="prod" | display_name = "my-db.prod" | CSI display_name format |
| TC-CSI3 | display_name truncation | `PVCName="a]x60"` (60 chars), `PVCNamespace="production"` | `display_name` = first 63 chars of `"aaa...aaa.production"` (prefix truncation, 63-char max, namespace retained within window) | Proto max_len: 63 |
| TC-CSI4 | No display_name when PVC info missing | Three sub-cases: (a) parameters missing `pvc/name`, (b) parameters missing `pvc/namespace`, (c) namespace is empty string | `display_name` not set (empty) in all cases | Optional display_name |

## Integration Tests

| ID | Description | Steps | Assertions | PRD Req |
|---|---|---|---|---|
| TC-IT1 | Create volume via public API | POST `/api/fulfillment/v1/volumes` with `name="it-vol-1"`, `storage_tier="standard-block"`, `size_gib=50`, `access_mode=READ_WRITE_ONCE` | Response: Volume with expected spec, CREATING state, no private status fields | Create flow |
| TC-IT2 | Update volume metadata | PATCH with `display_name="updated"` and `description="IT test"` | Response: Volume with updated metadata fields | Mutable fields |
| TC-IT3 | Reject immutable field update | PATCH with `spec.storage_tier="premium-block"` in body | Response: `InvalidArgument` | Immutable fields |
| TC-IT4 | Delete volume lifecycle + name reservation | DELETE volume; poll GET and assert volume transitions through `DELETING` before `NotFound`; while in `DELETING`, attempt Create with same name → assert `AlreadyExists`; after `NotFound`, Create with same name → assert success | Delete → archived; name reserved until complete | Delete -> archived |
| TC-IT5 | Tenant isolation (cross-tenant denial) | Create volume in tenant A; from tenant B attempt Get, Update, and Delete | Tenant B is denied on all operations (Get, Update, Delete) | Tenant-scoped |
| TC-IT5a | Same-tenant Tenant Admin CUD | Tenant Admin creates, updates, and deletes a volume within own tenant | All operations succeed | Tenant Admins manage all |
| TC-IT5b | Cloud Provider Admin cross-tenant | Cloud Provider Admin creates volume in tenant A, updates it, then deletes it | All operations succeed across tenants | Cloud Provider Admin access |
| TC-IT6 | Public field allowlist | Create volume, inspect response fields | Assert exact expected public field set (positive allowlist, not blocklist assertion) | Private fields never exposed |

## E2E Tests

| ID | Description | Steps | Assertions | PRD Req |
|---|---|---|---|---|
| E2E-1 | Full volume lifecycle via public API | Create `name="e2e-lifecycle"`, `storage_tier="standard-block"`, `size_gib=10`, `access_mode=READ_WRITE_ONCE` → poll until AVAILABLE → Update `display_name="e2e-updated"` → Delete → poll until gone | Lifecycle states: CREATING → AVAILABLE → (update succeeds) → DELETING → NotFound. Uses `wait_for_state` helper. | Full CUD lifecycle |
| E2E-2 | CSI-provisioned volume display_name | Create PVC on tenant cluster; wait for volume; Get via public API | Volume has pvc-{UID} name and {pvc-name}.{namespace} display_name | CSI display_name |

## Deferred Test Cases

| ID | Description | Blocked By | Expected Behavior |
|---|---|---|---|
| TC-D6 | Force-delete volume with active attachments | OSAC-4884 (attach/detach) — requires a defined force-delete operation with its own authorization contract | Success with cascade detach; requires `force` flag and explicit RBAC |

> **Note:** TC-D5 (delete with active attachments → `FailedPrecondition`) is
> listed in the unit test table above with mocked attachment state. It is
> gated on OSAC-4884 providing the attachment query mechanism — the test
> skeleton can be written immediately but will be enabled once OSAC-4884
> ships.

---

*Generated by design:draft (testplan) for OSAC-2685 on 2026-09-11.*
