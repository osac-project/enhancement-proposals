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

OSAC has no API-managed inventory of storage tier offerings today: tier configuration lives in the `STORAGE_TIERS` environment variable plus Kubernetes label conventions, invisible to the OSAC API and to any UI. `StorageTier` (this EP) replaces that with a DB-backed private gRPC resource binding a named offering to a registered `StorageBackend` with QoS properties. `osac-ui` is the only interface Cloud Provider Admins have to manage this data, since neither `StorageTier` nor `StorageBackend` (OSAC-1111) has a public API or CLI.

Neither the OSAC-1110 nor the OSAC-1111 PRD states a UI requirement — unlike `ClusterVersion` (OSAC-1269), whose PRD explicitly required "The UI console supports catalog management for admins" (FR-9). In the absence of an explicit requirement, this design follows the closest in-codebase precedent for each resource individually: `StorageTier` composition is an interactive, form-shaped task (pick a backend by name, set QoS values); `StorageBackend` registration is a one-time, infrequent action (register an endpoint and credentials for a new storage array) structurally identical to `NetworkClass`, which `osac-ui` manages today with zero admin UI, exposed only as a read-only dropdown source elsewhere in the app. This design builds a UI for the former and deliberately not for the latter — see Non-Goals.

### User Stories

- As a Cloud Provider Admin, I want to compose a named storage tier from a registered backend with QoS settings, so that I can offer a differentiated storage product without hand-crafting API requests.
- As a Cloud Provider Admin, I want to see every existing storage tier with its backend, protocol, and state in one place, so that I can audit the catalog without direct API access.
- As a Cloud Provider Admin, I want to adjust a tier's QoS settings or backend association after creation, so that I can correct or tune an offering without recreating it.
- As a Cloud Provider Admin, I want to delete a tier that is no longer needed, and be blocked with a clear reason if a Tenant still depends on it, so that I don't silently break existing tenant storage.

### Goals

- Follow `osac-ui`'s existing hooks-layer conventions (`useApiFetch` + `useApiQuery`/`useMutation` + `apiQueryKey`) for `StorageTier` CRUD, private-only with no public counterpart.
- Model the admin screen on `osac-ui`'s existing table-plus-row-actions list-page shape (`VirtualNetworksListPage`/`ClustersTable`), since no full-CRUD admin page exists yet in `osac-ui` to copy wholesale.
- Consume `StorageBackend` exclusively through a minimal, read-only hook module (`List`/`Get` only, no mutations), mirroring how `osac-ui` already treats `InstanceType` — a comparable resource deliberately exposed without a CRUD UI.
- Reintroduce role-gated admin navigation and routing in `osac-ui`, following the exact shape of equivalent code that existed for a prior admin feature before being fully removed when that feature was reverted (see Implementation Details, "Navigation and Routing").

### Non-Goals

- Any admin UI for `StorageBackend` (create/edit/delete/lifecycle-state screens) — neither PRD states a UI requirement for it, and `osac-ui` already manages a structurally identical resource (`NetworkClass`) with no CRUD UI, exposing it only as a read-only dropdown source. Backend registration and credential rotation remain API/CLI operations outside this design's scope.
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
    UI->>FS: List StorageBackends (filter: state == READY)
    FS-->>UI: [{id, name, state}, ...]
    Admin->>UI: Name tier, pick backend, set protocol + QoS
    UI->>UI: Client-side validation (DNS-label name, positive integer QoS)
    UI->>FS: CreateStorageTier(name, description, backends: [{backendId, protocol, qos...}])
    FS-->>UI: StorageTier {id, state: ACTIVE}
    UI->>UI: Refresh list

    Note over Admin,FS: Edit QoS on an existing tier
    Admin->>UI: Open "Edit" on a row
    UI->>FS: GetStorageTier(id)
    FS-->>UI: StorageTier (current backend, protocol, QoS)
    Admin->>UI: Change quota; UI shows QoS-propagation info alert
    UI->>FS: UpdateStorageTier(id, backends[0].quotaGib=..., lock=true)
    FS-->>UI: Updated StorageTier

    Note over Admin,FS: Delete a tier referenced by a Tenant (rejected)
    Admin->>UI: Delete row
    UI->>FS: DeleteStorageTier(id)
    FS-->>UI: FAILED_PRECONDITION "in use by Tenant(s)"
    UI->>Admin: Show error verbatim; tier remains in the list
```

The diagram shows the three primary flows this UI supports: creation (with a `READY`-filtered backend picker), QoS editing (informing the admin that some changes require StorageClass recreation to take effect for new volumes), and deletion (surfacing the server's referential-integrity rejection verbatim rather than pre-checking it client-side). All three route through the same private `StorageTiers` service; `osac-ui` never talks to the fulfillment-service outside of a typed hook.

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
| `useCreateStorageTier()` | `Create` | submits `metadata.name`, `description`, `backends: [...]` |
| `useUpdateStorageTier()` | `Update` | submits `description`/`backends[0].*`; `metadata.name` never included; uses `lock=true` for optimistic concurrency |
| `useDeleteStorageTier()` | `Delete` | no client-side pre-check for in-use references |
| `usePrivateStorageBackends(params)` | `List` | read-only; used for the Tier form's backend picker and the list table's name lookup only |
| `usePrivateStorageBackend(id)` | `Get` | read-only; used by the edit form to resolve a tier's currently-assigned backend when it has fallen out of the `READY` filter (see §5) |

#### 2. Navigation and Routing

`osac-ui` currently has **no "Administration" nav section**: `navRowsForRole(role, t)` in `apps/app-frontend/src/shell/shellNav.ts` ignores `role` entirely and returns only two tenant-facing sections (`nav-tenant-services`, `nav-tenant-networking`). A prior admin feature (unrelated to storage) had a role-gated `nav-administration` section and a matching role-conditional `<Route>` in `AppShell.tsx`, but both were fully removed when that feature was reverted for reasons unrelated to storage.

This design reintroduces the same shape for "Storage tiers":

- `navRowsForRole` conditionally pushes `{ kind: 'section', sectionId: 'nav-administration', label: t('Administration'), children: [{ id: 'storage-tiers', label: t('Storage tiers'), path: '/admin/storage-tiers' }] }` when `role === 'providerAdmin' || role === 'tenantAdmin'`.
- `AppShell.tsx` gains a matching role-conditional route: `{(role === 'providerAdmin' || role === 'tenantAdmin') && <Route path="/admin/storage-tiers/*" element={<ShellRoute><StorageTiersListPage /></ShellRoute>} />}`. A non-admin navigating to the URL directly falls through to the existing catch-all route and is redirected, rather than the page rendering and issuing API calls that would fail server-side.

This is a route-level guard, in addition to nav-entry hiding — not a substitute for the private API's own OPA-enforced authorization, which remains the authoritative check regardless of what the UI does.

#### 3. List Page

`libs/ui-components/src/pages/admin/StorageTiersListPage.tsx`, following the existing `VirtualNetworksListPage`/`ClustersTable` shape: a page-header wrapper around a plain PatternFly `Table` (no generic column abstraction exists in `osac-ui` today). Columns: NAME, BACKEND, PROTOCOL, STATE, and a row-actions kebab (Edit, Delete). BACKEND resolves `backends[0].backendId` to a name via a batched `List` call to the read-only backend hook plus a `Map<string, StorageBackend>` lookup — avoiding one `Get` per row — falling back to the raw ID if the lookup fails. STATE renders via `StorageTierStateLabel` (§6). Delete calls `useDeleteStorageTier()` with no pre-check; a blocked delete (`FAILED_PRECONDITION`, tier referenced by a Tenant) is shown verbatim and the row stays in place.

#### 4. Create Form

A modal (`StorageTierCreateModal`) modeled on `osac-ui`'s existing `VirtualNetworkCreateModal` (Formik + Yup, single mutation on submit): `name` (DNS-label validated, §9), `description` (optional), `backend` (single-select, populated from `usePrivateStorageBackends({ filter: STORAGE_BACKEND_READY_LIST_FILTER })`), `protocol` (`NFS`/`BLOCK`), `maxReadBandwidthMbs` / `maxWriteBandwidthMbs` / `quotaGib` (positive-integer numeric fields), `encryptionEnabled` (checkbox). Submits `{ name, description, backends: [{ backendId, protocol, maxReadBandwidthMbs, maxWriteBandwidthMbs, quotaGib, encryptionEnabled }] }`.

The backend picker is single-select, matching the server's v0.1 constraint of exactly one backend per tier — the underlying `backends` array is already shaped to accommodate a future multi-select without a data-model change (see Risks and Mitigations).

#### 5. Edit Form

`StorageTierEditForm`: `name` renders disabled (immutable); `description` and all of `backends[0]`'s fields — including `backendId` — remain editable, since only `metadata.name` is documented as immutable and this matches the literal FieldMask partial-update contract. The backend picker's option list is the union of the `READY`-filtered list and the tier's currently-assigned backend (fetched via `usePrivateStorageBackend(backendId)` if it has since left `READY`) — this avoids the create form's simpler single-filter approach silently dropping a tier's existing selection when its backend has been moved to `MAINTENANCE`/`DECOMMISSIONED`. Changing any QoS field shows an inline info alert: "Bandwidth and quota changes take effect immediately for existing and new volumes. Changes to encryption or protocol require the associated StorageClass to be recreated before new volumes pick them up; existing volumes are unaffected."

#### 6. Lifecycle State Label

`StorageTierStateLabel`, mapping `StorageTierState` directly to a PatternFly `Label` — `ACTIVE` → green, the only reachable value in this phase — without going through the shared `ResourceStatusLabel`/`StatusKind` primitive, whose semantics (`ready`/`failed`/`progressing`) describe runtime reconciliation state that does not apply to a resource with no reconciler.

#### 7. Data Model (as consumed by this UI)

`StorageBackend` fields beyond `id`/`metadata.name`/`status.state` (`provider`, `endpoint`, `credentials`, `status.model`, `status.firmwareVersion`) are never read or written by this UI — they exist in the full proto per [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md) but are irrelevant here:

```
StorageBackend { id, metadata { name }, status: { state: READY | MAINTENANCE | DECOMMISSIONED } }

StorageTier {
  id, metadata { name },              // name immutable after creation
  description?: string,
  backends: [ BackendAssociation ],    // v0.1: server accepts exactly one
  state: ACTIVE
}
BackendAssociation {
  backendId: string,                   // references StorageBackend.id
  protocol: NFS | BLOCK,
  maxReadBandwidthMbs: int32,
  maxWriteBandwidthMbs: int32,
  quotaGib: int64,
  encryptionEnabled: bool
}
```

Both protos are prerequisites for this design to compile: neither `storage_backend_type_pb`/`storage_backends_service_pb` nor `storage_tier_type_pb`/`storage_tiers_service_pb` exist yet in `osac-ui`'s generated types (`libs/types`), since neither has merged in the fulfillment-service. `pnpm gen-types` must be re-run once they do, exporting both from `libs/types/src/index-private.ts` (both are private-only resources — no public variant is needed for either).

#### 8. Validation Constraints

- `name`: RFC 1035 DNS label (1–63 chars, lowercase alphanumeric plus hyphens, no leading/trailing hyphen), validated client-side before submission. This is a defensive measure: OSAC-2872 (Storage Control Plane) generates the StorageClass name `osac-{tenant}-{tier}` directly from the tier name, but whether the fulfillment-service itself enforces DNS-label formatting on `StorageTier.metadata.name` (as it does for `StorageBackend.metadata.name`) is unconfirmed — see Open Questions.
- `maxReadBandwidthMbs`, `maxWriteBandwidthMbs`, `quotaGib`: positive integers, rejected client-side before submission; the server is the final authority.

### Security Considerations

This UI never handles `StorageBackend` credentials, endpoint, or operational metadata — those fields are outside its read set entirely (§7), so there is no credential-exposure surface to reason about; backend registration and credential rotation happen exclusively via direct API/CLI access, outside this design's scope. Write access (create/update/delete) to `StorageTier` is restricted to Cloud Provider Admins via the existing OPA-based authorization already enforced server-side; the UI's role-gated nav entry and route (§2) are defense-in-depth, not a substitute for that check.

### Failure Handling and Recovery

| Scenario | UI behavior |
|---|---|
| Create/Update: duplicate active tier name | Server's `ALREADY_EXISTS` shown as a form-level error. |
| Create/Update: referenced `StorageBackend` does not exist (e.g., deleted between the picker's `List` call and submission) | Server's `NOT_FOUND` naming the invalid backend ID shown as a form-level error. |
| Update: concurrent conflicting write | Server's `FAILED_PRECONDITION`/`ABORTED` (stale version) shown as a submission error; admin re-fetches and retries. |
| Delete: tier still referenced by a Tenant | Server's `FAILED_PRECONDITION` shown verbatim. |
| Backend picker's `List` call fails or is slow | `Select` shows its loading state; on failure, no options render. |
| List table's backend-name lookup fails | BACKEND column falls back to the raw `backendId`. |

### RBAC / Tenancy

`StorageTier` is a platform-scoped, non-tenant resource managed exclusively by Cloud Provider Admins. The "Storage tiers" nav entry and route are visible/reachable only when `role === 'providerAdmin' || role === 'tenantAdmin'` — reintroducing role-gated admin navigation and routing that existed in `osac-ui` for a prior feature before being fully removed (§2), rather than extending a currently-live mechanism. No new RBAC concept is introduced beyond that reintroduction. There is no tenant-facing visibility to reason about, since neither resource has a public API.

### Observability and Monitoring

No new observability changes. Existing monitoring mechanisms (fulfillment-service gRPC Prometheus metrics and structured logging) already cover the underlying API calls; this design adds no client-side telemetry beyond what any other page in `osac-ui` already emits (none, per current convention).

### Risks and Mitigations

**Reintroducing removed nav/route-gating code.** This design restores role-gated admin navigation and routing that existed for an unrelated, now-reverted feature. *Mitigation:* the reintroduction follows the exact shape of the removed code (conditional section push in `navRowsForRole`, conditional `<Route>` in `AppShell.tsx`), so it carries no new architectural risk — only the risk of reproducing a stale variant if the removed code is copied without verifying it against the current `shellNav.ts`/`AppShell.tsx` at implementation time.

**External blocker on both fulfillment-service protos.** This design cannot be implemented until `StorageBackend` and `StorageTier` protos merge and `libs/types` regenerates. *Mitigation:* none needed beyond sequencing — this is a known, tracked dependency (see [design.md](design.md) and [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md)), not a risk to the UI design itself.

**Single-backend-per-tier UI matches a v0.1 server constraint that may change.** *Mitigation:* the `backends` field is modeled internally as an array even though only one row renders; when the server relaxes the constraint, the form adds a second row rather than changing its data shape.

### Drawbacks

`StorageBackend` registration and credential rotation have no UI at all — an admin must use `grpcurl`/REST calls (or a future CLI) to register a backend before any tier can reference it. This is a deliberate trade-off (see Motivation and Non-Goals): both PRDs describe backend registration as infrequent, and building a masked-credential-input primitive and a full lifecycle-action UI for a rarely-exercised workflow was judged not worth the added surface area, matching the precedent this codebase already sets for `NetworkClass`. If backend registration turns out to be more frequent in practice than the PRDs assume, this trade-off should be revisited.

## Alternatives (Not Implemented)

**Full CRUD UI for both `StorageBackend` and `StorageTier`.** Pros: complete admin control over both resources from one screen. Cons: neither PRD states a UI requirement for `StorageBackend`, and building one mirrors the exact shape (platform-scoped, admin-registered, no reconciler) of `NetworkClass`, which `osac-ui` deliberately manages with zero CRUD UI; it also requires a masked-credential-input primitive and a full lifecycle-action UI for an infrequent workflow. Rejected in favor of Tiers-only.

**Reusing `ResourceStatusLabel`'s `StatusKind` union for `StorageTierStateLabel`.** Pros: one fewer component. Cons: `StatusKind`'s semantics describe runtime reconciliation state; `StorageTier` has no reconciler. Rejected in favor of a standalone `StateLabel` component.

**Multi-select backend picker now, instead of single-select.** Pros: no rework when the server relaxes the v0.1 one-backend-per-tier constraint. Cons: builds UI for a server capability that does not exist yet, with no PRD guidance on multi-backend UX (ordering, per-backend QoS override). Rejected: single-select matches the current contract; the data model is already future-proof without it.

**Do nothing (continue with the `STORAGE_TIERS` env var).** Pros: zero UI work. Cons: this is the status quo the OSAC-1110 PRD is replacing — no API-managed catalog, no UI, blocks OSAC-23/OSAC-2872. Rejected because the PRD requires an API-managed tier catalog with CRUD access and there is no other planned interface for Cloud Provider Admins to compose tier offerings.

## Open Questions

### 1. Does the fulfillment-service enforce RFC 1035 DNS-label formatting on `StorageTier.metadata.name`, matching `StorageBackend.metadata.name`'s documented validation?

Client-side validation is added defensively because OSAC-2872 generates a StorageClass name from the tier name, but [design.md](design.md) does not state whether the server enforces this the way [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md) explicitly does for backend names.

- **Owner:** OSAC-1110 design owner (Roy Golan)
- **Impact:** §8 Validation Constraints, Security Considerations.

## Test Plan

**Unit and component tests** (Vitest + React Testing Library, mocked Connect transport per `osac-ui` convention — no fetch/REST mocks):
- Hook modules: correct RPC invoked per hook, cache invalidation on mutation success, `STORAGE_BACKEND_READY_LIST_FILTER`'s literal value.
- Nav/routing: `navRowsForRole` includes the `nav-administration` section only for `providerAdmin`/`tenantAdmin`; a non-admin navigating to `/admin/storage-tiers` directly is redirected rather than shown the page.
- List page: table renders expected rows/columns, backend-name resolution and its ID-fallback path, empty/loading states, delete success and `FAILED_PRECONDITION` handling.
- Create form: DNS-label and positive-integer validation, backend picker excludes non-`READY` backends, `ALREADY_EXISTS`/`NOT_FOUND` error surfacing.
- Edit form: prefill, `name` rendered disabled, backend picker includes a non-`READY` currently-assigned backend, QoS-change alert triggers correctly, stale-version conflict handling.

**E2E tests** (owned by QE, authored in `osac-test-infra` via the `/e2e` workflow — `osac-ui` has no e2e tests of its own):
- Full create → list → edit → delete flow against a real (or kind-deployed) fulfillment-service, including duplicate-name rejection and delete-blocked-by-tenant-reference.
- Role gating: a non-admin does not see the nav entry and cannot reach the page by direct URL.

This EP's UI work cannot be exercised end-to-end until the `StorageBackend`/`StorageTier` protos merge in the fulfillment-service — e2e coverage is blocked on that regardless of `osac-ui` readiness.

## Documentation

No dedicated admin-facing documentation is planned for this narrow, self-explanatory CRUD screen — consistent with how other simple admin catalog resources (`NetworkClass`) have no dedicated user guide in the OSAC docs repo today. Revisit if user feedback indicates the form (particularly the QoS fields and backend-state semantics) needs written guidance.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages: Dev Preview -> Tech Preview -> GA based on production deployment feedback, tracking the graduation of the underlying `StorageTier`/`StorageBackend` APIs.

## Upgrade / Downgrade Strategy

This is new UI with no upgrade impact — it is additive to `osac-ui` and does not change behavior for any existing route or nav entry. Downgrade requires removing the "Storage tiers" nav entry, its route, and the two new hook modules; no data migration is involved since all state lives in the fulfillment-service.

## Version Skew Strategy

No version skew concern beyond the standard `osac-ui`/fulfillment-service coupling: this UI requires the `StorageBackend`/`StorageTier` protos to be present in `libs/types`, generated from whatever fulfillment-service version is deployed. Once generated, proto backward compatibility (additive-only field changes) covers ordinary version skew.

## Support Procedures

**Detecting failures:** Browser console errors on the Storage tiers page; fulfillment-service gRPC error-rate metrics for `StorageTiers`/`StorageBackends` RPCs (existing dashboards, no new ones added).

**Disabling the feature:** Remove the "Storage tiers" route and nav entry (revert §2's changes). No impact on any other `osac-ui` page — this feature has no dependents.

**Recovery:** Re-enable by restoring the route and nav entry. No data loss risk, since all state lives in the fulfillment-service, not in `osac-ui`.

## Infrastructure Needed

None.

---

## Provenance

Authored: draft @ design 0.5.0 - 68284c8, workspace worktree-delightful-gliding-perlis @ 57ca666

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.5.0","ai_workflows":"68284c8","source_repo":"57ca666","source_repo_branch":"worktree-delightful-gliding-perlis","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
