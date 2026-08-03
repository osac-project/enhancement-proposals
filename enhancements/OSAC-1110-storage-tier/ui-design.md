---
title: storage-tier-ui
authors:
  - eaharoni
creation-date: 2026-08-02
last-updated: 2026-08-02
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1110
  - https://redhat.atlassian.net/browse/OSAC-1111
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1111-storage-backend"
  - "/enhancements/OSAC-2872-storage-control-plane"
  - "/enhancements/OSAC-1269-cluster-version-api"
replaces:
superseded-by:
---

# Storage Tier — UI Management

## Summary

This design specifies the `osac-ui` implementation for `StorageTier` (OSAC-1110) admin management: a single "Storage tiers" admin page where Cloud Provider Admins compose named tier offerings (e.g., "fast", "standard") from already-registered `StorageBackend` (OSAC-1111) infrastructure. See [PRD](prd.md) for detailed requirements and [design.md](design.md) for the `StorageTier` API contract this UI consumes.

## Motivation

OSAC has no API-managed inventory of storage tier offerings today: tier configuration lives in the `STORAGE_TIERS` environment variable plus Kubernetes label conventions, invisible to the OSAC API and to any UI. `StorageTier` (this EP) replaces that with a DB-backed private gRPC resource binding a named offering to a registered `StorageBackend` with QoS properties. `osac-ui` is the only *graphical* interface Cloud Provider Admins have to manage this data — neither `StorageTier` nor `StorageBackend` (OSAC-1111) has a public API, though both already have private `osac` CLI support (`osac create/describe storagetier`, `osac create/describe storagebackend`, confirmed merged in `fulfillment-service`).

Neither the OSAC-1110 nor the OSAC-1111 PRD states a UI requirement — unlike `ClusterVersion` (OSAC-1269), whose PRD explicitly required "The UI console supports catalog management for admins" (FR-9). In the absence of an explicit requirement, this design follows the closest in-codebase precedent for each resource individually: `StorageTier` composition is an interactive, form-shaped task (pick one or more backends by name, set QoS values per backend); `StorageBackend` registration is a one-time, infrequent action (register an endpoint and credentials for a new storage array) structurally identical to `NetworkClass`, which `osac-ui` manages today with zero admin UI, exposed only as a read-only dropdown source elsewhere in the app. This design builds a UI for the former and deliberately not for the latter — see Non-Goals.

### User Stories

- As a Cloud Provider Admin, I want to compose a named storage tier from one or more registered backends with QoS settings, so that I can offer a differentiated storage product without hand-crafting API requests.
- As a Cloud Provider Admin, I want to see every existing storage tier with its backend, protocol, and state in one place, so that I can audit the catalog without direct API access.
- As a Cloud Provider Admin, I want to adjust a tier's QoS settings or backend association after creation, so that I can correct or tune an offering without recreating it.
- As a Cloud Provider Admin, I want to delete a tier that is no longer needed, and be blocked with a clear reason if a Tenant still depends on it, so that I don't silently break existing tenant storage.

### Goals

- Follow `osac-ui`'s existing hooks-layer conventions (`useApiFetch` + `useApiQuery`/`useMutation` + `apiQueryKey`) for `StorageTier` CRUD, private-only with no public counterpart.
- Model the admin screen on `osac-ui`'s existing table-plus-row-actions list-page shape (`VirtualNetworksListPage`/`ClustersTable`), since no full-CRUD admin page exists yet in `osac-ui` to copy wholesale.
- Consume `StorageBackend` exclusively through a minimal, read-only hook module (`List`/`Get` only, no mutations), mirroring how `osac-ui` already treats `InstanceType` — a comparable resource deliberately exposed without a CRUD UI.
- Reintroduce role-gated admin navigation and routing in `osac-ui`, following the exact shape of equivalent code that existed for a prior admin feature before being fully removed when that feature was reverted (see Implementation Details, "Navigation and Routing").

### Non-Goals

- Any admin UI for `StorageBackend` (create/edit/delete/lifecycle-state screens) — neither PRD states a UI requirement for it, and `osac-ui` already manages a structurally identical resource (`NetworkClass`) with no CRUD UI, exposing it only as a read-only dropdown source. Backend registration and credential rotation remain `osac` CLI (`osac create storagebackend`) or direct API operations outside this design's scope.
- Any UI for Volume/PVC management or inventory — out of scope per OSAC-2872 (Storage Control Plane), which explicitly states "No UX changes in this EP... UI integration is OSAC-984 scope."
- Any tenant-facing surface — neither resource has a public API; there is nothing for a tenant to see or do here.
- Tenant-to-tier assignment UI — owned by the future OSAC Storage Controller (OSAC-23) and OSAC-2872's policy engine, not this design.
- A generic, field-type-driven form-rendering system — consistent with how every other resource in `osac-ui` hardcodes its own widgets rather than deriving them from proto metadata.

## Proposal

`osac-ui` gains: two new hook modules (`storage-tiers.ts`, full CRUD; `storage-backends.ts`, read-only), one new admin list page (`StorageTiersListPage`) with create/edit forms, one new lifecycle-state label component, and a reintroduced role-gated "Administration" nav section and route guard. `StorageBackend` gets no new UI surface of its own — it is consumed only as read-only support data (a picker in the Tier form, a name lookup in the Tier table). No backend API changes are proposed by this EP; it consumes the `StorageTiers`/`StorageBackends` private gRPC services exactly as specified in [design.md](design.md) and [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md).

### Workflow Description

**Actors:** Cloud Provider Admin (all interactions; no other actor has access to this UI).

**Preconditions:** At least one `StorageBackend` exists in the `READY` state, registered via direct API/CLI access (no UI exists for this step — see Non-Goals).

```mermaid
sequenceDiagram
    participant Admin as Cloud Provider Admin
    participant UI as osac-ui (StorageTiersListPage)
    participant FS as fulfillment-service (private)

    Note over Admin,FS: Create a storage tier
    Admin->>UI: Open "Create" modal
    UI->>FS: List StorageBackends (filter: status.state == READY)
    FS-->>UI: [{id, metadata.name, status.state}, ...]
    Admin->>UI: Name tier, add one or more backend rows, set protocol + QoS per row
    UI->>UI: Client-side validation (DNS-label name, positive integer QoS)
    UI->>FS: CreateStorageTier(metadata.name, spec: {description, backends: [{backendId, protocol, qos...}]})
    FS-->>UI: StorageTier {id, status.state: ACTIVE}
    UI->>UI: Refresh list

    Note over Admin,FS: Edit QoS on an existing tier
    Admin->>UI: Open "Edit" on a row
    UI->>FS: GetStorageTier(id)
    FS-->>UI: StorageTier (current spec.backends array, spec fields)
    Admin->>UI: Change quota; UI shows QoS-propagation info alert
    UI->>FS: UpdateStorageTier(id, spec.backends: [complete updated array], update_mask: ["spec.backends"], lock=true)
    FS-->>UI: Updated StorageTier

    Note over Admin,FS: Delete a tier referenced by a Tenant (rejected, once OSAC-23's trigger lands)
    Admin->>UI: Delete row
    UI->>FS: DeleteStorageTier(id)
    FS-->>UI: FAILED_PRECONDITION "in use by Tenant(s)"
    UI->>Admin: Show error verbatim; tier remains in the list
```

The diagram shows the three primary flows this UI supports: creation (with a `READY`-filtered backend picker), QoS editing (informing the admin that some changes require StorageClass recreation to take effect for new volumes), and deletion (surfacing the server's referential-integrity rejection verbatim rather than pre-checking it client-side). All three route through the same private `StorageTiers` service; `osac-ui` never talks to the fulfillment-service outside of a typed hook. The deletion flow's `FAILED_PRECONDITION` path is not yet reachable in practice: the fulfillment-service's current migrations implement the `StorageBackend`↔`StorageTier` referential-integrity triggers (verified in `76_add_storage_tier_ref_triggers.up.sql`), but the tenant-reference-blocks-delete trigger is still deferred to a follow-up migration shipping with OSAC-23, exactly as [design.md](design.md) states. Until that trigger lands, `DeleteStorageTier` always succeeds — the UI still implements this error-handling path now, since it costs nothing extra and the trigger is expected to land before this UI ships.

### API Extensions

None. This EP introduces no new backend API surface, CRDs, webhooks, or finalizers. It is a pure consumer of the `StorageTiers` and `StorageBackends` private gRPC services already specified in [design.md](design.md) and [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md). The only new artifacts are `osac-ui`-internal: two hook modules and their corresponding `ApiRoute` string-literal entries (`'v1/private/storage_tiers'`, `'v1/private/storage_backends'`) in `libs/ui-components/src/api/types.ts`.

### Implementation Details/Notes/Constraints

#### 1. Hooks Layer

Two new private-only hook modules in `libs/ui-components/src/api/v1/private/`:

- **`storage-tiers.ts`** — `usePrivateStorageTiers(params)` / `usePrivateStorageTier(id)` (`List`/`Get`), `useCreateStorageTier()` / `useUpdateStorageTier()` / `useDeleteStorageTier()` (mutations), following the existing `networking.ts` CRUD hook shape (`useMutation` + `useApiQueryClient()` + an `invalidate*Queries(qc)` helper in `onSuccess`).
- **`storage-backends.ts`** — `usePrivateStorageBackends(params)` / `usePrivateStorageBackend(id)` only, no mutations, mirroring `instance-types.ts`'s read-only-only shape. Exports `STORAGE_BACKEND_READY_LIST_FILTER = "this.status.state == ${StorageBackendState.READY}"`, restricting the Tier form's backend picker to usable backends.

| Hook | RPC | Notes |
|---|---|---|
| `usePrivateStorageTiers(params)` | `List` | pagination + CEL filter + ordering supported by the hook; the list page itself renders every tier unpaginated (see §3), consistent with the catalog's expected small size |
| `usePrivateStorageTier(id)` | `Get` | edit-form prefill |
| `useCreateStorageTier()` | `Create` | submits `metadata.name`, `spec: { description, backends: [...] }` |
| `useUpdateStorageTier()` | `Update` | submits `spec.description` and/or the complete `spec.backends` array (never an indexed sub-path — standard protobuf `FieldMask` addresses whole fields, not repeated-element indices) with a matching `update_mask` (`["spec.description"]`, `["spec.backends"]`, or both); `metadata.name` never included (rejected as immutable — verified in `private_storage_tiers_server.go`'s `validateStorageTierUpdate`); uses `lock=true` for optimistic concurrency |
| `useDeleteStorageTier()` | `Delete` | no client-side pre-check for in-use references |
| `usePrivateStorageBackends(params)` | `List` | read-only; used for the Tier form's backend picker and the list table's name lookup only |
| `usePrivateStorageBackend(id)` | `Get` | read-only; used by the edit form to resolve a tier's currently-assigned backend when it has fallen out of the `READY` filter (see §5) |

#### 2. Navigation and Routing

`osac-ui` currently has **no "Administration" nav section**: `navRowsForRole(role, t)` in `apps/app-frontend/src/shell/shellNav.ts` ignores `role` entirely and returns only two tenant-facing sections (`nav-tenant-services`, `nav-tenant-networking`). A prior admin feature (unrelated to storage) had a role-gated `nav-administration` section and a matching role-conditional `<Route>` in `AppShell.tsx`, but both were fully removed when that feature was reverted for reasons unrelated to storage.

This design reintroduces the same shape for "Storage tiers":

- `navRowsForRole` conditionally pushes `{ kind: 'section', sectionId: 'nav-administration', label: t('Administration'), children: [{ id: 'storage-tiers', label: t('Storage tiers'), path: '/admin/storage-tiers' }] }` when `role === 'providerAdmin'`. Unlike the removed code this reintroduction is modeled on (which also granted `tenantAdmin`, appropriate for that feature's tenant-scoped catalog items), `StorageTier` is platform-scoped and managed exclusively by Cloud Provider Admins — `tenantAdmin` is a tenant-scoped role in `osac-ui`'s three-tier model (`providerAdmin` | `tenantAdmin` | `tenantUser`) and has no legitimate access to it.
- `AppShell.tsx` gains a matching role-conditional route: `{role === 'providerAdmin' && <Route path="/admin/storage-tiers/*" element={<ShellRoute><StorageTiersListPage /></ShellRoute>} />}`. A non-admin — including a `tenantAdmin` — navigating to the URL directly falls through to the existing catch-all route and is redirected, rather than the page rendering and issuing API calls that would fail server-side.

This is a route-level guard, in addition to nav-entry hiding — not a substitute for the private API's own OPA-enforced authorization, which remains the authoritative check regardless of what the UI does.

#### 3. List Page

`libs/ui-components/src/pages/admin/StorageTiersListPage.tsx`, following the existing `VirtualNetworksListPage`/`ClustersTable` shape: a page-header wrapper around a plain PatternFly `Table` (no generic column abstraction exists in `osac-ui` today). Columns: NAME, BACKENDS, PROTOCOL(S), STATE, and a row-actions kebab (Edit, Delete). BACKENDS resolves every entry in `spec.backends[].backendId` to a name via a batched `List` call to the read-only backend hook plus a `Map<string, StorageBackend>` lookup — avoiding one `Get` per row — and renders the resolved names comma-separated, falling back to the raw ID for any entry that fails to resolve individually (a tier with a mix of resolved and unresolved backends shows both forms in the same cell). PROTOCOL(S) similarly lists each backend association's protocol, comma-separated, since different backends within one tier can use different protocols. STATE reads `status.state` and renders via `StorageTierStateLabel` (§6). Delete calls `useDeleteStorageTier()` with no pre-check; a blocked delete (`FAILED_PRECONDITION`, tier referenced by a Tenant) is shown verbatim and the row stays in place — see the Workflow Description note on this path not being reachable until OSAC-23's trigger lands.

#### 4. Create Form

A modal (`StorageTierCreateModal`) modeled on `osac-ui`'s existing `VirtualNetworkCreateModal` (Formik + Yup, single mutation on submit): `name` (DNS-label validated, §8), `description` (optional), and a repeatable **backend associations** section — one or more rows, each with `backend` (select, populated from `usePrivateStorageBackends({ filter: STORAGE_BACKEND_READY_LIST_FILTER })`), `protocol` (`NFS`/`BLOCK`), `maxReadBandwidthMbs` / `maxWriteBandwidthMbs` / `quotaGib` (positive-integer numeric fields), and `encryptionEnabled` (checkbox). Submits `{ metadata: { name }, spec: { description, backends: [{ backendId, protocol, maxReadBandwidthMbs, maxWriteBandwidthMbs, quotaGib, encryptionEnabled }, ...] } }` — one array entry per row.

**Backend associations are entered via `BackendAssociationsArrayField`**, a new shared component (used by both Create and Edit forms) following `osac-ui`'s existing repeatable-row pattern from `ClusterNodeSetsArrayField.tsx` — the only precedent for this shape in the codebase, and the one to copy exactly rather than inventing a new convention. No `FieldArray`/`useFieldArray` from Formik is used anywhere in `osac-ui`; the established pattern is hand-rolled array manipulation via `setFieldValue`:

- Formik state holds `spec.backends: BackendAssociationRow[]`, where each row carries a client-only `rowId` (`crypto.randomUUID()`, generated by `createEmptyBackendAssociationRow()`) used as the React `key` — never the array index — so removing a row doesn't cause sibling rows to remount or lose focus.
- Each row renders inside a PatternFly `FormFieldGroup` (`FormFieldGroupHeader` titled "Backend {n}", 1-based), fields stacked vertically inside, matching `ClusterNodeSetsArrayField.tsx`'s layout exactly — not a card or accordion.
- **Remove:** a plain `Button` (`variant="plain"`, `MinusCircleIcon`, `aria-label`) in the `FormFieldGroupHeader`'s `actions` slot, present on every row except the first — at least one backend association is always required and the first row cannot be removed, matching the existing precedent.
- **Add:** a `variant="link"` `Button` with `PlusCircleIcon`, labeled "Add backend", below the last row, appending a new empty row via `setFieldValue('spec.backends', [...values.spec.backends, createEmptyBackendAssociationRow()])`. Disabled while the backend picker's `List` call is loading.
- Each row's backend `Select` excludes backends already chosen in a sibling row (computed via `useMemo` over all rows' selected `backendId`s, mirroring `ClusterNodeSetsArrayField.tsx`'s duplicate-host-type exclusion for node sets) — a tier cannot reference the same backend twice.
- Yup validation: `yup.array().of(backendAssociationRowSchema).min(1, ...).test('unique-backend-ids', ...)`, in the same style as `ClusterNodeSetsArrayField.tsx`'s sibling `schemas.ts`.

**The server currently rejects more than one entry in `spec.backends`** with `INVALID_ARGUMENT` ("only one backend association is supported in v0.1") — verified in `private_storage_tiers_server.go`'s `validateBackends`. This UI is built for the full OSAC-1110 FR-3 requirement ("one or more backend associations") per confirmed reviewer/product direction (PR review discussion, `storage_tier_type.pb.go`'s `Backends` field already modeled as a repeated field), not the server's current interim restriction — an admin adding a second backend row and submitting will see the server's real `INVALID_ARGUMENT` message until that server-side restriction is lifted. See Risks and Mitigations.

#### 5. Edit Form

`StorageTierEditForm`: `name` renders disabled (immutable — enforced server-side in `validateStorageTierUpdate`, which rejects any `metadata.name` change with `INVALID_ARGUMENT`); `description` and the entire backend-associations list — via the same `BackendAssociationsArrayField` used by the Create form (§4) — remain editable, since only `metadata.name` is immutable. Prefill maps each of the tier's existing `spec.backends` entries to one row (assigning each a fresh client-only `rowId`, since the server doesn't persist one); an admin can add further rows, remove existing ones (down to a minimum of one), or edit any row's fields.

Editing *anything* in the backend-associations list — adding a row, removing one, or changing a single field on one row — submits the *complete*, current `spec.backends` array with `update_mask: ["spec.backends"]`; there is no per-row or per-field partial update, since standard protobuf `FieldMask` has no syntax for addressing individual elements of a repeated field. The form's Formik state always holds the full array regardless of what changed, and submits it whole.

Each row's backend `Select` option list is the union of the `READY`-filtered list and that row's own currently-assigned backend (fetched via `usePrivateStorageBackend(backendId)` if it has since left `READY`) — this avoids the create form's simpler always-`READY` filter silently dropping an existing selection when its backend has moved out of `READY`. The duplicate-backend exclusion (§4) still applies across rows during editing. Changing any QoS field on any row shows an inline info alert: "Bandwidth and quota changes take effect immediately for existing and new volumes. Changes to encryption or protocol require the associated StorageClass to be recreated before new volumes pick them up; existing volumes are unaffected."

#### 6. Lifecycle State Label

`StorageTierStateLabel` wraps the shared `ResourceStatusLabel`/`StatusKind` primitive rather than introducing a standalone component: `ACTIVE` maps to `status="ready"` (green, "Active"), and the proto3 zero value `UNSPECIFIED` maps to `status="unspecified"` (grey). `StatusKind`'s remaining values (`failed`, `progressing`) describe runtime reconciliation states that `StorageTier` — having no reconciler — never reaches, so this mapping only ever produces two of the primitive's four possible renderings; `ResourceStatusLabel`'s `text` prop still carries `StorageTier`-specific wording ("Active") rather than reusing generic reconciliation text, keeping the semantic mismatch contained to a single, obvious two-line mapping function rather than exposed to callers.

#### 7. Data Model (as consumed by this UI)

Both `StorageBackend` and `StorageTier` use the standard OSAC `spec`/`status` object shape, not the flat shape an earlier revision of this document assumed. `StorageBackend` fields beyond `id`/`metadata.name`/`status.state` (`spec.provider`, `spec.endpoint`, `spec.credentials`, `status.message`) are never read or written by this UI — they exist in the full proto per [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md) but are irrelevant here:

```text
StorageBackend {
  id, metadata { name },
  status: { state: READY }   // only value defined today; UNSPECIFIED is the proto3 zero value
}

StorageTier {
  id, metadata { name },                // name immutable after creation
  spec: {
    description?: string,
    backends: [ BackendAssociation ]    // this UI supports one or more per FR-3; server currently rejects >1 (see Risks)
  },
  status: { state: ACTIVE, message?: string }  // ACTIVE is the only value defined today
}
BackendAssociation {
  backendId: string,                    // references StorageBackend.id
  protocol: NFS | BLOCK,
  maxReadBandwidthMbs: int32,
  maxWriteBandwidthMbs: int32,
  quotaGib: int64,
  encryptionEnabled: bool
}
```

Both protos are already merged and generated: `storage_backend_type_pb`/`storage_backends_service_pb` and `storage_tier_type_pb`/`storage_tiers_service_pb` exist in `osac-ui`'s generated types (`libs/types`) and are already exported from `libs/types/src/index-private.ts` — verified directly against `fulfillment-service`'s `origin/main` (`StorageBackend`: PR #728, merged 2026-06-18; `StorageTier`: PR #832, merged 2026-07-02, restructured to `spec`/`status` by PR #887, merged 2026-07-12) and against `osac-ui`'s current `libs/types`. This design has no remaining external blocker — see Risks and Mitigations.

#### 8. Validation Constraints

- `name`: RFC 1035 DNS label (1–63 chars, lowercase alphanumeric plus hyphens, no leading/trailing hyphen), validated client-side before submission. **Confirmed the server performs no format validation of its own**: `private_storage_tiers_server.go`'s `validateStorageTierCreate` only checks that `metadata.name` is non-empty (the same is true of `private_storage_backends_server.go` for `StorageBackend.metadata.name` — the OSAC-1111 design's stated intent to reuse a generic DNS-label validator was not implemented this way). This client-side check is therefore the *only* validation preventing a StorageClass-incompatible name from being submitted, not a defensive duplicate of a server-side rule — OSAC-2872 (Storage Control Plane) generates the StorageClass name `osac-{tenant}-{tier}` directly from the tier name, so an invalid name here would surface as a failure much later, in volume provisioning.
- `maxReadBandwidthMbs`, `maxWriteBandwidthMbs`, `quotaGib`: positive integers, rejected client-side before submission; the server is the final authority.

### Security Considerations

This UI never handles `StorageBackend` credentials, endpoint, or operational metadata — those fields are outside its read set entirely (§7), so there is no credential-exposure surface to reason about; backend registration and credential rotation happen exclusively via direct API/CLI access, outside this design's scope. Write access (create/update/delete) to `StorageTier` is restricted to Cloud Provider Admins via the existing OPA-based authorization already enforced server-side; the UI's role-gated nav entry and route (§2) are defense-in-depth, not a substitute for that check.

### Failure Handling and Recovery

| Scenario | UI behavior |
|---|---|
| Create/Update: duplicate active tier name | Server's `ALREADY_EXISTS` shown as a form-level error. |
| Create/Update: referenced `StorageBackend` does not exist (e.g., deleted between the picker's `List` call and submission) | Server's `NOT_FOUND` naming the invalid backend ID shown as a form-level error. |
| Create/Update: more than one backend row submitted, before the server's v0.1 single-backend restriction is lifted | Server's `INVALID_ARGUMENT` ("only one backend association is supported in v0.1") shown as a form-level error; the row(s) are not removed from the form so the admin can retry after the restriction is lifted or remove rows manually. |
| Update: concurrent conflicting write | Server's `FAILED_PRECONDITION`/`ABORTED` (stale version) shown as a submission error; admin re-fetches and retries. |
| Delete: tier still referenced by a Tenant | Server's `FAILED_PRECONDITION` shown verbatim. Not yet reachable in the current backend — the enforcing trigger is deferred to OSAC-23 (see Workflow Description); build the handling now regardless, since it costs nothing extra and the trigger is expected before this UI ships. |
| Backend picker's `List` call fails or is slow | `Select` shows its loading state; on failure, no options render. |
| List table's backend-name lookup fails | BACKEND column falls back to the raw `backendId`. |

### RBAC / Tenancy

`StorageTier` is a platform-scoped, non-tenant resource managed exclusively by Cloud Provider Admins. The "Storage tiers" nav entry and route are visible/reachable only when `role === 'providerAdmin'` — `tenantAdmin`, a tenant-scoped role, is deliberately excluded, unlike the removed prior-feature code this reintroduction is modeled on for mechanism (§2), whose two-role check does not apply to a platform-only resource. No new RBAC concept is introduced beyond the reintroduced nav/route-gating mechanism itself. There is no tenant-facing visibility to reason about, since neither resource has a public API.

### Observability and Monitoring

No new observability changes. Existing monitoring mechanisms (fulfillment-service gRPC Prometheus metrics and structured logging) already cover the underlying API calls; this design adds no client-side telemetry beyond what any other page in `osac-ui` already emits (none, per current convention).

### Risks and Mitigations

**DNS-label name validity is enforced only by this UI, not by the server.** §8 documents that `private_storage_tiers_server.go` performs no name-format validation — any direct `osac` CLI or API caller can persist a `StorageTier.metadata.name` that later breaks StorageClass generation in OSAC-2872, bypassing this UI's client-side check entirely. *Mitigation:* none available within this document's scope — this UI cannot enforce a constraint on callers that don't go through it. The fulfillment-service should add the same RFC 1035 validation to `CreateStorageTier`/`UpdateStorageTier` server-side (matching the client-side rule this design already applies); that is a backend change to `design.md`/OSAC-1110, not this UI design, and is flagged here as a cross-team follow-up rather than implemented.

**Reintroducing removed nav/route-gating code.** This design restores role-gated admin navigation and routing that existed for an unrelated, now-reverted feature. *Mitigation:* the reintroduction follows the exact shape of the removed code (conditional section push in `navRowsForRole`, conditional `<Route>` in `AppShell.tsx`), so it carries no new architectural risk — only the risk of reproducing a stale variant if the removed code is copied without verifying it against the current `shellNav.ts`/`AppShell.tsx` at implementation time.

**This UI's multi-backend support is ahead of the server's current v0.1 capability.** `validateBackends` in `private_storage_tiers_server.go` still rejects more than one `spec.backends` entry with `INVALID_ARGUMENT` as of this revision, even though this design builds the full multi-row UI per OSAC-1110 FR-3 and confirmed reviewer/product direction. An admin who adds a second backend row and submits will hit that rejection until the fulfillment-service's own restriction is lifted. *Mitigation:* this is treated the same way the whole EP was once gated on the original `StorageBackend`/`StorageTier` protos merging — the UI is built correctly against the target contract now, and the multi-backend *feature* (as opposed to the UI code) is gated on a corresponding fulfillment-service change. The Failure Handling table's `INVALID_ARGUMENT` row ensures the interim experience (single-backend-only, in practice) fails clearly rather than silently.

**Delete-blocked-by-tenant-reference cannot be exercised until OSAC-23 lands.** The UI implements this error-handling path (§ Failure Handling and Recovery) against a server behavior that does not exist yet — the DB trigger enforcing it is deferred to a follow-up migration shipping with OSAC-23. *Mitigation:* none needed for this UI's correctness — the code path is inert until the trigger lands, not incorrect. Component/unit tests for this path must mock the `FAILED_PRECONDITION` response rather than relying on integration test coverage, since no real backend will produce it before OSAC-23 ships.

### Drawbacks

`StorageBackend` registration and credential rotation have no UI at all — an admin must use the `osac create storagebackend`/`osac describe storagebackend` CLI commands (already implemented) or direct API calls to register a backend before any tier can reference it. This is a deliberate trade-off (see Motivation and Non-Goals): both PRDs describe backend registration as infrequent, and building a masked-credential-input primitive and a full lifecycle-action UI for a rarely-exercised workflow was judged not worth the added surface area, matching the precedent this codebase already sets for `NetworkClass`. If backend registration turns out to be more frequent in practice than the PRDs assume, this trade-off should be revisited.

## Alternatives (Not Implemented)

**Full CRUD UI for both `StorageBackend` and `StorageTier`.** Pros: complete admin control over both resources from one screen. Cons: neither PRD states a UI requirement for `StorageBackend`, and building one mirrors the exact shape (platform-scoped, admin-registered, no reconciler) of `NetworkClass`, which `osac-ui` deliberately manages with zero CRUD UI; it also requires a masked-credential-input primitive and a full lifecycle-action UI for an infrequent workflow. Rejected in favor of Tiers-only.

**Standalone `StorageTierStateLabel` with its own color map, bypassing `ResourceStatusLabel` entirely.** Pros: no semantic mismatch to explain — a resource with no reconciler never needs a mapping to `StatusKind`'s reconciliation-oriented values. Cons: duplicates a component that already renders exactly the needed PatternFly `Label` shape, for a two-value enum that maps onto `StatusKind` with no ambiguity (`ACTIVE`→`ready`, `UNSPECIFIED`→`unspecified`). Rejected in favor of a thin wrapper around `ResourceStatusLabel`: the mismatch between `StatusKind`'s reconciliation semantics and `StorageTier`'s catalog-lifecycle semantics is real, but confining it to one small, explicit mapping function is cheaper than a second component that duplicates `ResourceStatusLabel`'s rendering logic.

**Single-select backend picker, matching only the server's current v0.1 constraint.** Pros: avoids building UI ahead of a server capability, and avoids the interim `INVALID_ARGUMENT` experience for any admin who tries a second backend. Cons: contradicts OSAC-1110 FR-3's explicit "one or more backend associations" requirement, and contradicts confirmed reviewer/product direction (PR review discussion — multiple backends per tier is the intended design, not a deferred nice-to-have). Rejected: building to the single-backend interim behavior would require a second, disruptive UI rework the moment the server catches up, for a UI-side cost (a repeatable-row component, following an existing in-codebase pattern) that is not itself expensive.

**Reuse Formik's `FieldArray`/`useFieldArray` for the repeatable backend rows.** Pros: a standard, purpose-built Formik primitive for array fields. Cons: no existing usage anywhere in `osac-ui` — every repeatable-row form in this codebase (e.g., `ClusterNodeSetsArrayField.tsx`) hand-rolls array manipulation via `setFieldValue` instead. Rejected in favor of matching that established convention exactly, rather than introducing a second, inconsistent pattern for the same kind of problem.

**Do nothing (continue with the `STORAGE_TIERS` env var).** Pros: zero UI work. Cons: this is the status quo the OSAC-1110 PRD is replacing — no API-managed catalog, no UI, blocks OSAC-23/OSAC-2872. Rejected because the PRD requires an API-managed tier catalog with CRUD access and there is no other planned interface for Cloud Provider Admins to compose tier offerings.

## Test Plan

**Unit and component tests** (Vitest + React Testing Library, mocked Connect transport per `osac-ui` convention — no fetch/REST mocks):
- Hook modules: correct RPC invoked per hook, cache invalidation on mutation success, `STORAGE_BACKEND_READY_LIST_FILTER`'s literal value.
- Nav/routing: `navRowsForRole` includes the `nav-administration` section only for `providerAdmin`, and excludes it for both `tenantAdmin` and `tenantUser`; a non-admin navigating to `/admin/storage-tiers` directly is redirected rather than shown the page.
- List page: table renders expected rows/columns, backend-name resolution and its ID-fallback path, empty/loading states, delete success and `FAILED_PRECONDITION` handling.
- Create form: DNS-label and positive-integer validation, backend picker excludes non-`READY` backends, `ALREADY_EXISTS`/`NOT_FOUND`/multi-backend `INVALID_ARGUMENT` error surfacing.
- `BackendAssociationsArrayField`: adding a row appends an empty one with a fresh `rowId`; removing a row is unavailable on the first row and removes any other row without affecting sibling rows' state (verifying `rowId`-based keying, not index-based, avoids cross-row state bleed); a backend already selected in one row is excluded from every other row's options; array-level Yup validation rejects zero rows and duplicate `backendId`s.
- Edit form: prefill renders one row per existing `spec.backends` entry, `name` rendered disabled, each row's backend picker includes that row's non-`READY` currently-assigned backend, QoS-change alert triggers correctly, stale-version conflict handling, adding/removing rows on an existing tier submits the complete updated array.

**E2E tests** (owned by QE, authored in `osac-test-infra` via the `/e2e` workflow — `osac-ui` has no e2e tests of its own):
- Full create → list → edit → delete flow against a real (or kind-deployed) fulfillment-service, including duplicate-name rejection and delete-blocked-by-tenant-reference.
- Role gating: a non-admin does not see the nav entry and cannot reach the page by direct URL.

The tenant-reference-blocks-delete scenario cannot be exercised as a true e2e test until OSAC-23's enforcing trigger lands (see Risks and Mitigations) — cover it with a mocked `FAILED_PRECONDITION` response in the meantime, and add the real e2e case once the trigger exists.

## Documentation

No dedicated admin-facing documentation is planned for this narrow, self-explanatory CRUD screen — consistent with how other simple admin catalog resources (`NetworkClass`) have no dedicated user guide in the OSAC docs repo today. Revisit if user feedback indicates the form (particularly the QoS fields and backend-state semantics) needs written guidance.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages: Dev Preview -> Tech Preview -> GA based on production deployment feedback, tracking the graduation of the underlying `StorageTier`/`StorageBackend` APIs.

## Upgrade / Downgrade Strategy

This is new UI with no upgrade impact — it is additive to `osac-ui` and does not change behavior for any existing route or nav entry. Downgrade requires removing the "Storage tiers" nav entry, its route, and the two new hook modules; no data migration is involved since all state lives in the fulfillment-service.

## Version Skew Strategy

Proto backward compatibility (additive-only field changes) covers schema-level version skew, but this UI depends on more than the schema: it also assumes the specific behaviors verified in this document — the `spec.backends` single-entry constraint (`validateBackends` rejecting more than one), the `status.state == READY` filter semantics, the `update_mask`/`FieldMask` handling, and the exact error codes in Failure Handling and Recovery. None of these are guaranteed by additive schema compatibility alone; a fulfillment-service version older than the one this design was verified against (StorageBackend PR #728, StorageTier PR #832/#887) may not exhibit them. **Minimum supported fulfillment-service version:** the commit introducing PR #887 (StorageTier `spec`/`status` restructuring, 2026-07-12) — this UI's payload shapes are written against that structure and will fail against an older, flat-shape server. There is no client-side capability gate or version check in this design; deploying this UI against an older fulfillment-service is a deployment-sequencing concern, not one this UI detects or handles at runtime.

## Support Procedures

**Detecting failures:** Browser console errors on the Storage tiers page; fulfillment-service gRPC error-rate metrics for `StorageTiers`/`StorageBackends` RPCs (existing dashboards, no new ones added).

**Disabling the feature:** Remove the "Storage tiers" route and nav entry (revert §2's changes). No impact on any other `osac-ui` page — this feature has no dependents.

**Recovery:** Re-enable by restoring the route and nav entry. No data loss risk, since all state lives in the fulfillment-service, not in `osac-ui`.

## Infrastructure Needed

None.

---

## Provenance

Authored: draft @ design 0.5.0 - 68284c8, workspace worktree-delightful-gliding-perlis @ 57ca666
Final: respond @ design 0.5.0 - 68284c8, workspace docs/OSAC-1110-1111-storage-ui-design @ 47288de (25 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.5.0","ai_workflows":"68284c8","source_repo":"47288de","source_repo_branch":"docs/OSAC-1110-1111-storage-ui-design","commits_behind_main":25,"commits_ahead_main":3,"main_ref":"main","phases":["draft","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true} -->
