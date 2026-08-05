---
title: storage-tier-ui
authors:
  - eaharoni
creation-date: 2026-08-02
last-updated: 2026-08-04
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1110
  - https://redhat.atlassian.net/browse/OSAC-1111
prd:
  - "prd.md"
  - "../OSAC-1111-storage-backend/prd.md"
see-also:
  - "/enhancements/OSAC-1111-storage-backend"
  - "/enhancements/OSAC-2872-storage-control-plane"
  - "/enhancements/OSAC-1269-cluster-version-api"
replaces:
superseded-by:
---

# Storage Tier & Backend — UI Management

## Summary

This design specifies the `osac-ui` implementation for both `StorageBackend` (OSAC-1111) and `StorageTier` (OSAC-1110) admin management: a combined "Storage" admin section, with a Backends tab and a Tiers tab, where Cloud Provider Admins register storage infrastructure and compose named tier offerings (e.g., "fast", "standard") on top of it. See the [StorageTier PRD](prd.md) and [StorageBackend PRD](../OSAC-1111-storage-backend/prd.md) for detailed requirements, and [design.md](design.md) / [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md) for the API contracts this UI consumes.

## Motivation

OSAC has no API-managed inventory of storage infrastructure or tier offerings today: backend configuration lives in Ansible extra vars, and tier configuration lives in the `STORAGE_TIERS` environment variable plus Kubernetes label conventions — both invisible to the OSAC API and to any UI. `StorageBackend` and `StorageTier` replace these with DB-backed private gRPC resources. `osac-ui` is the only *graphical* interface Cloud Provider Admins have to manage this data — neither resource has a public API today, though both already have private `osac` CLI support (`osac create/describe storagetier`, `osac create/describe storagebackend`, confirmed merged in `fulfillment-service`). A public, tenant-facing Get/List API for `StorageTier` (not `StorageBackend`) is planned separately under OSAC-3014, to let VMaaS tenants see which tiers are available when selecting a disk tier during ComputeInstance creation (OSAC-1710); that public surface, and any UI built on it, is out of scope for this admin-only design — see Drawbacks.

Neither the OSAC-1110 nor the OSAC-1111 PRD states a UI requirement — unlike `ClusterVersion` (OSAC-1269), whose PRD explicitly required "The UI console supports catalog management for admins" (FR-9). Scope here is therefore determined by the actual Cloud Provider Admin workflow, not a PRD mandate: an admin registers a `StorageBackend` (vendor, endpoint, credentials) first, then composes `StorageTier`s on top of the registered backends. Splitting that workflow — full CRUD for `StorageTier` but only read-only visibility into `StorageBackend` — would force the admin back to the CLI or raw API calls partway through an otherwise-graphical task, for a resource that isn't meaningfully simpler or more static than `StorageTier` itself. This design builds full CRUD for both resources on that basis.

This design covers the Cloud Provider Admin (CSP admin) side only — registering backends and composing tiers. The tenant-consuming side (a tenant selecting a `StorageTier` for a disk, per OSAC-1710/OSAC-3014) is a later phase, owned by a future design, not this one. A related, binding constraint: **tenants must remain completely unaware of the `StorageBackend` concept.** A tenant's only mental model is "storage tiers" — they never see, select, or need to know that a tier is backed by one or more registered backends. This UI (admin-only, no tenant surface at all) satisfies that trivially, but the constraint matters for what comes next: OSAC-3014's public `StorageTier` Get/List API must never expose `spec.backends`/`backendId`/provider/endpoint in its tenant-facing representation — only tier-level, tenant-appropriate properties (name, description, effective QoS).

### User Stories

- As a Cloud Provider Admin, I want to register a new storage backend (provider, management endpoint, credentials) through a form, so that I don't have to construct API/CLI calls by hand to make it available for tier composition.
- As a Cloud Provider Admin, I want to see every registered storage backend with its provider, endpoint, and state in one place, so that I know what infrastructure is available before composing tiers.
- As a Cloud Provider Admin, I want to update a backend's endpoint, description, or credentials without re-registering it, so that I can rotate credentials or correct a mistake in place.
- As a Cloud Provider Admin, I want to delete a backend that is no longer needed, and be blocked with a clear reason if a tier still references it, so that I don't silently break tier definitions.
- As a Cloud Provider Admin, I want to compose a named storage tier from a registered backend with QoS settings, so that I can offer a differentiated storage product without manually constructing gRPC/REST calls (e.g., via `grpcurl` or the private REST endpoint) or using the `osac` CLI. (The data model already supports a *list* of backend associations per tier, and the UI is built against that list shape end-to-end; today the UI itself only lets the admin choose one backend per tier — see Non-Goals and Risks and Mitigations.)
- As a Cloud Provider Admin, I want to see every existing storage tier with its backend, protocol, and state in one place, so that I can audit the tier definitions without direct API access. (Here and elsewhere, "catalog" refers only to lists of `StorageBackend`/`StorageTier` definitions — it is unrelated to `osac-ui`'s separate `ClusterCatalogItem`/`CatalogManagementListPage` provisioning-template feature, which this design does not touch.)
- As a Cloud Provider Admin, I want to adjust a tier's QoS settings or backend association after creation, so that I can correct or tune an offering without recreating it.
- As a Cloud Provider Admin, I want to delete a tier that is no longer needed, and be blocked with a clear reason if a Tenant still depends on it, so that I don't silently break existing tenant storage.

### Goals

- Follow `osac-ui`'s existing hooks-layer conventions (`useApiFetch` + `useApiQuery`/`useMutation` + `apiQueryKey`) for full `StorageBackend` and `StorageTier` CRUD, private-only — no public API exists for either yet, so there is no public counterpart to build against today. (OSAC-3014 will add a public, tenant-facing Get/List API for `StorageTier` later; that will need its own hook module when it lands, following the existing public/private split pattern used elsewhere in `osac-ui`, e.g. `ClusterVersion`'s `api/v1/cluster-versions.ts` vs. `api/v1/private/cluster-versions.ts` — not built here. No public API is planned for `StorageBackend`.)
- Model both admin screens on `osac-ui`'s existing table-plus-row-actions list-page shape (`VirtualNetworksListPage`/`ClustersTable`), since no full-CRUD admin page exists yet in `osac-ui` to copy wholesale.
- Combine `StorageBackend` and `StorageTier` under one "Storage" nav entry with two tabs, reflecting their tight coupling (a tier cannot be created without at least one registered backend) rather than two separate top-level nav items.
- Introduce two UI primitives with no existing precedent in this codebase: a masked credential input (`StorageBackend.spec.credentials`) and an immutable-field-on-edit form pattern (both resources' identity fields — `metadata.name` on both, plus `spec.provider` on `StorageBackend`).
- Extend `osac-ui`'s existing, live `nav-administration` nav section (currently listing only "Tenants," added for OSAC-3372/OSAC-3379) with a "Storage" entry, and register `/admin/storage/*` unconditionally in `AppShell.tsx` — matching the exact, current pattern used by `/admin/tenants/*` (nav-entry hiding is the only client-side gate; there is no per-route role guard anywhere in this codebase today) rather than inventing a new mechanism (see Implementation Details, "Navigation and Routing").
- Use full-page routes for Create and Edit flows (`StorageBackendCreatePage`, `StorageTierCreatePage`, and their Edit counterparts), matching the current, consistent codebase-wide convention (`VmCreatePage`, `ClusterCreatePage`, `BareMetalCreatePage`, the newly-added `TenantCreatePage`) rather than a modal — the modal pattern (`VirtualNetworkCreateModal`) belongs only to the original Networking feature and hasn't been followed by anything built since.

### Non-Goals

- Any UI for Volume/PVC management or inventory — out of scope per OSAC-2872 (Storage Control Plane), which explicitly states "No UX changes in this EP... UI integration is OSAC-984 scope."
- `StorageBackend` lifecycle-state transitions (e.g., "Mark maintenance," "Decommission") — the real, merged `StorageBackendState` enum defines only `READY` today (`UNSPECIFIED`/`READY`); `MAINTENANCE`/`DECOMMISSIONED` do not exist as enum values yet, so there is nothing to build a transition UI against. This design builds the state label to display whatever state exists, but no lifecycle-action UI, and revisits this when the enum grows (see Risks and Mitigations).
- Any tenant-facing surface for *this admin screen* — neither resource has a public API today, so there is nothing for a tenant to see or do in the UI this design builds. (This does not preclude a *separate* tenant-facing surface elsewhere once OSAC-3014's public `StorageTier` Get/List API lands, e.g. a tier picker in the VMaaS disk-configuration wizard for OSAC-1710 — that is a distinct UI surface, owned by a future design, not this one. That future surface must also keep `StorageBackend` entirely invisible to tenants — see Motivation. No public API is planned for `StorageBackend`.)
- Tenant-to-tier assignment UI — owned by OSAC-2872 (Storage Control Plane)'s policy engine, not this design.
- Multi-backend *selection* UI (adding/removing more than one backend row per tier) — confirmed on the 2026-08-04 call: even though `spec.backends` is list-shaped in the data model and API, the CSP admin UI lets an admin choose exactly **one** backend per tier for now. This matches the server's own current `validateBackends` v0.1 restriction, so there is no near-term UI/server mismatch to manage (contrast with the previous revision of this design, which built ahead of the server). Add the repeatable add/remove UI in a later phase, once both product and the server are ready for more than one backend per tier — see Risks and Mitigations.
- A generic, field-type-driven form-rendering system — consistent with how every other resource in `osac-ui` hardcodes its own widgets rather than deriving them from proto metadata.

## Proposal

`osac-ui` gains: two new hook modules (`storage-backends.ts` and `storage-tiers.ts`, both full CRUD), one new combined list page (`StorageManagementPage`, Backends/Tiers tabs) plus four new full-page Create/Edit routes, two new lifecycle-state label components, and a "Storage" entry added to the existing, live `nav-administration` nav section. No backend API changes are proposed by this EP; it consumes the `StorageBackends`/`StorageTiers` private gRPC services exactly as specified in [design.md](design.md) and [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md).

### Workflow Description

**Actors:** Cloud Provider Admin (all interactions; no other actor has access to this UI).

#### Flow 1: Register and manage a storage backend

**Preconditions:** None — this is the first step in the storage setup workflow.

```mermaid
sequenceDiagram
    participant Admin as Cloud Provider Admin
    participant UI as osac-ui StorageManagementPage Backends tab
    participant FS as fulfillment-service private

    Note over Admin,FS: Register a storage backend
    Admin->>UI: Open Create page
    Admin->>UI: Name backend, pick provider, set endpoint and credentials
    UI->>UI: Client-side validation, DNS-label name, required fields
    UI->>FS: CreateStorageBackend with name, provider, endpoint, credentials
    FS-->>UI: StorageBackend with id, status.state READY
    UI->>UI: Refresh list

    Note over Admin,FS: Rotate credentials on an existing backend
    Admin->>UI: Open Edit on a row
    UI->>FS: GetStorageBackend by id
    FS-->>UI: StorageBackend with current spec fields, credentials fields left blank in the form
    Admin->>UI: Enter new username and password, leaving other fields unchanged
    UI->>FS: UpdateStorageBackend with new credentials, update_mask spec.credentials, lock=true
    FS-->>UI: Updated StorageBackend

    Note over Admin,FS: Delete a backend referenced by a tier, rejected
    Admin->>UI: Delete row
    UI->>FS: DeleteStorageBackend by id
    FS-->>UI: FAILED_PRECONDITION, still referenced by StorageTiers
    UI->>Admin: Show error verbatim, backend remains in the list
```

The diagram shows the three primary flows the Backends tab supports: registration (name, provider, endpoint, credentials), credential rotation (only changed fields submitted, name/provider locked), and deletion blocked by an existing tier reference. All three route through the same private `StorageBackends` service.

#### Flow 2: Compose a storage tier from registered backends

**Preconditions:** At least one `StorageBackend` exists in the `READY` state (Flow 1).

```mermaid
sequenceDiagram
    participant Admin as Cloud Provider Admin
    participant UI as osac-ui StorageManagementPage Tiers tab
    participant FS as fulfillment-service private

    Note over Admin,FS: Create a storage tier
    Admin->>UI: Open Create page
    UI->>FS: List StorageBackends, filter status.state == READY
    FS-->>UI: List of backends with id, name, state
    Admin->>UI: Name tier, pick one backend, set protocol and QoS
    UI->>UI: Client-side validation, DNS-label name, positive integer QoS
    UI->>FS: CreateStorageTier with name, description, backends array
    FS-->>UI: StorageTier with id, status.state ACTIVE
    UI->>UI: Refresh list

    Note over Admin,FS: Edit QoS on an existing tier
    Admin->>UI: Open Edit on a row
    UI->>FS: GetStorageTier by id
    FS-->>UI: StorageTier with current spec.backends array and spec fields
    Admin->>UI: Change quota, UI shows QoS-propagation info alert
    UI->>FS: UpdateStorageTier with updated backends array, update_mask spec.backends, lock=true
    FS-->>UI: Updated StorageTier

    Note over Admin,FS: Delete a tier referenced by a Tenant, rejected once OSAC-2872's trigger lands
    Admin->>UI: Delete row
    UI->>FS: DeleteStorageTier by id
    FS-->>UI: FAILED_PRECONDITION, in use by Tenants
    UI->>Admin: Show error verbatim, tier remains in the list
```

The diagram shows the three primary flows the Tiers tab supports: creation (with a `READY`-filtered backend picker), QoS editing (informing the admin that some changes require StorageClass recreation to take effect for new volumes), and deletion (surfacing the server's referential-integrity rejection verbatim rather than pre-checking it client-side). The deletion flow's `FAILED_PRECONDITION` path is not yet reachable in practice: the fulfillment-service's current migrations implement the `StorageBackend`↔`StorageTier` referential-integrity triggers (verified in `76_add_storage_tier_ref_triggers.up.sql`), but the tenant-reference-blocks-delete trigger is still deferred to a follow-up migration shipping with OSAC-2872 (Storage Control Plane) — OSAC-23, the enhancement this deferral was originally scoped against, is closed; OSAC-2872 is the current live epic that owns tenant-to-tier assignment and the corresponding backend enforcement. Until that trigger lands, `DeleteStorageTier` always succeeds — the UI still implements this error-handling path now, since it costs nothing extra and the trigger is expected to land before this UI ships.

### API Extensions

None. This EP introduces no new backend API surface, CRDs, webhooks, or finalizers. It is a pure consumer of the `StorageBackends` and `StorageTiers` private gRPC services already specified in [../OSAC-1111-storage-backend/design.md](../OSAC-1111-storage-backend/design.md) and [design.md](design.md). The only new artifacts are `osac-ui`-internal: two hook modules and their corresponding `ApiRoute` string-literal entries (`'v1/private/storage_backends'`, `'v1/private/storage_tiers'`) in `libs/ui-components/src/api/types.ts`.

### Implementation Details/Notes/Constraints

#### 1. Hooks Layer

Two new private-only hook modules in `libs/ui-components/src/api/v1/private/`, both full CRUD, following the existing `networking.ts` CRUD hook shape (`useMutation` + `useApiQueryClient()` + an `invalidate*Queries(qc)` helper in `onSuccess`):

| Hook | RPC | Notes |
|---|---|---|
| `usePrivateStorageBackends(params)` | `List` | pagination + CEL filter + ordering supported by the hook; the Tier forms' backend picker calls it unfiltered-by-ID and unpaginated to offer every `READY` backend as an option — an inherited, app-wide gap (see Risks and Mitigations), not Storage-specific; the Tiers list page instead scopes each call to referenced IDs via the new `storageBackendIdsFilter` (see §6) |
| `usePrivateStorageBackend(id)` | `Get` | edit-form prefill; also used by the Tiers tab to resolve a tier's currently-assigned backend when it has fallen out of the `READY` filter (see §8) |
| `useCreateStorageBackend()` | `Create` | submits `metadata.name`, `spec: { provider, endpoint, description, credentials }` |
| `useUpdateStorageBackend()` | `Update` | submits only changed fields among `spec.endpoint`/`spec.description`/`spec.credentials` with a matching `update_mask`; `spec.credentials` is all-or-nothing (both `username` and `password`, or neither — see §5) since a `FieldMask` entry addresses the whole nested message, not its individual leaf fields; `metadata.name`/`spec.provider` never included (both immutable, rejected by the server with `INVALID_ARGUMENT` if changed); uses `lock=true` for optimistic concurrency |
| `useDeleteStorageBackend()` | `Delete` | no client-side pre-check for in-use references |
| `usePrivateStorageTiers(params)` | `List` | pagination + CEL filter + ordering supported by the hook; the list page renders every tier unpaginated, consistent with the catalog's expected small size |
| `usePrivateStorageTier(id)` | `Get` | edit-form prefill |
| `useCreateStorageTier()` | `Create` | submits `metadata.name`, `spec: { description, backends: [...] }` |
| `useUpdateStorageTier()` | `Update` | submits `spec.description` and/or the complete `spec.backends` array (never an indexed sub-path — standard protobuf `FieldMask` addresses whole fields, not repeated-element indices) with a matching `update_mask`; `metadata.name` never included (immutable, rejected with `INVALID_ARGUMENT`); uses `lock=true` for optimistic concurrency |
| `useDeleteStorageTier()` | `Delete` | no client-side pre-check for in-use references |

Exports `STORAGE_BACKEND_READY_LIST_FILTER = "this.status.state == ${StorageBackendState.READY}"` from `storage-backends.ts`, restricting the Tier forms' backend picker to usable backends, mirroring `instance-types.ts`'s `INSTANCE_TYPE_ACTIVE_LIST_FILTER`. Also exports `storageBackendIdsFilter(ids: string[])`, building `` this.id in [...] `` — a new CEL-filter-building idiom (no `in [...]` filter exists anywhere else in this codebase, though `networking.ts`'s `combineListFilters` establishes the precedent for building a filter string programmatically) — used by the Tiers list page (§6) to resolve only the backend names it actually needs to render.

#### 2. Navigation and Routing

`osac-ui` currently has a live, role-gated `nav-administration` nav section (added for OSAC-3372's `UserRole` model and OSAC-3379's Tenant admin page), listing a single "Tenants" entry today: `getAdminNav(t)` in `apps/app-frontend/src/shell/shellNav.ts` returns `{ kind: 'section', sectionId: 'nav-administration', label: t('Administration'), children: [{ id: 'tenant', label: t('Tenants'), path: '/admin/tenants' }] }`, and `navRowsForRole(role, t)` returns it only when `role === 'admin'` (the platform-admin value of the current `UserRole = 'admin' | 'tenant-idp-manager' | 'tenant-admin' | 'tenant-user'` type).

This design extends that live section rather than introducing a new mechanism:

- `getAdminNav` gains a second child: `{ id: 'storage', label: t('Storage'), path: '/admin/storage' }`, alongside the existing "Tenants" entry — still gated by the same `role === 'admin'` check in `navRowsForRole`, since `StorageBackend` and `StorageTier` are platform-scoped, exactly like `Tenant`.
- `AppShell.tsx` registers `<Route path="/admin/storage/*" element={<ShellRoute><StorageRoutes /></ShellRoute>} />` **unconditionally**, with no role check — matching the exact, current pattern used by the existing `/admin/tenants/*` route (confirmed unconditional in `AppShell.tsx`: no `role === ...` guard wraps it). This codebase has no per-route role-guard component (no `ProtectedRoute`/`RequireRole` exists anywhere), so adding one for Storage alone would be a new, inconsistent mechanism rather than following precedent.
- A non-admin who navigates to `/admin/storage/*` directly by URL is **not** blocked at the route level: the page renders and its data-fetching hooks issue the same private RPCs any admin's session would, which the server's existing OPA-based authorization rejects. `TenantListPage.tsx` establishes this exact pattern today — it has no client-side role check of its own and relies entirely on `QueryErrorState` (`libs/ui-components/src/components/Resource/QueryErrorState.tsx`) to render an error state from whatever the API call returns. Storage's list/create/edit pages follow the same approach: no client-side role gate beyond the hidden nav entry.
- `StorageRoutes.tsx` (mirroring `TenantRoutes.tsx`/`ClusterRoutes.tsx`) wires six routes: `backends` (list), `backends/create`, `backends/:id/edit`, `tiers` (list), `tiers/create`, `tiers/:id/edit` — see §4, §5, §7, §8 for the Create/Edit pages these point to.

See Risks and Mitigations for a caveat on this pattern: `QueryErrorState` only recognizes gRPC `Unauthenticated` as "Unauthorized" today, not `PermissionDenied` — if OPA's role rejection surfaces as the latter, a non-admin hitting these routes directly sees a generic error, not a clear "Unauthorized" message. This gap is inherited from the existing `TenantListPage` pattern, not introduced by this design.

#### 3. Backends List Page

`libs/ui-components/src/pages/admin/StorageManagementPage.tsx` renders a `Tabs` component with "Backends" (default) and "Tiers" tabs, each wrapping a plain PatternFly `Table` (no generic column abstraction exists in `osac-ui` today — see `ClustersTable.tsx`). The Backends tab: columns NAME, PROVIDER, ENDPOINT, STATE, a "Create backend" button routing to `/admin/storage/backends/create`, and a row-actions kebab (Edit — routes to `/admin/storage/backends/:id/edit`; Delete). STATE renders via `StorageBackendStateLabel` (§9). Delete calls `useDeleteStorageBackend()` with no pre-check; a blocked delete (`FAILED_PRECONDITION`, backend referenced by an active `StorageTier` — enforced today by the `check_storage_backend_not_in_use_by_tier` trigger, verified in `76_add_storage_tier_ref_triggers.up.sql`) is shown verbatim and the row stays in place.

#### 4. Backend Create Form

A full page (`StorageBackendCreatePage`, routed at `/admin/storage/backends/create`) modeled on the current codebase-wide create-flow convention — `VmCreatePage`, `ClusterCreatePage`, `BareMetalCreatePage`, and the newly-added `TenantCreatePage` are all full `PageSection`/`Breadcrumb` pages, not modals; the modal pattern (`VirtualNetworkCreateModal`) belongs only to the original Networking feature and hasn't been followed by anything built since. Formik + Yup, single mutation on submit: `name` (`InputField`, DNS-label validated, §11), `provider` (`Select`, options `vast`/`ceph`/`pure` — constrained rather than free text, since OSAC-2872 (Storage Control Plane) resolves the vendor CSI controller via `{provider}.osac-csi-backend.svc.cluster.local`, making the exact string a live Kubernetes Service DNS name downstream; a typo in a free-text field would silently break volume provisioning with no client-side signal), `endpoint` (`InputField`, required), `description` (`InputField`, optional), `credentials.username` (`InputField`, required), `credentials.password` (`TextInput type="password"`, required — a new primitive with no existing precedent in this codebase; searched and confirmed no masked-password input exists anywhere in `osac-ui` today). Submits `{ metadata: { name }, spec: { provider, endpoint, description, credentials: { username, password } } }` via `useCreateStorageBackend()`, then navigates back to `/admin/storage/backends` on success.

#### 5. Backend Edit Form

`StorageBackendEditPage`, routed at `/admin/storage/backends/:id/edit` — a full page for the same reason as the Create page (§4). There is no existing Edit-page precedent yet in this codebase (Tenant, the closest analog, has no Edit flow at all today), but a modal Edit next to a full-page Create would be an arbitrary, unprecedented split, so this design applies the same full-page convention for consistency. `name` and `provider` render disabled (both immutable — enforced server-side, rejecting either change with `INVALID_ARGUMENT`); `endpoint`, `description`, and `credentials.username`/`credentials.password` remain editable. The credential fields start **blank**, with helper text "Leave blank to keep the current credentials," — this is the first implementation of an immutable-field-on-edit pattern in this codebase (locking specific fields while leaving others on the same record editable); there is no existing component to extend or copy. Submits via `useUpdateStorageBackend()` with `lock=true` for optimistic concurrency, then navigates back to `/admin/storage/backends` on success.

**Credential update semantics are all-or-nothing, not per-field.** `spec.credentials` is a single nested message; a protobuf `FieldMask` entry of `spec.credentials` replaces that message wholesale — there's no server-level merge of "just the username changed, keep the existing password" the way `spec.endpoint`/`spec.description` can be included or omitted independently as their own top-level mask entries. Treating `username` and `password` as independently optional (as an earlier revision of this document did) leaves the actual behavior of a username-only or password-only submission undefined: either the server would need undocumented field-level merge logic inside `spec.credentials` that isn't specified anywhere, or a partial submission would silently blank out the field left empty. Client-side Yup validation on this form therefore treats `credentials.username` and `credentials.password` as a single all-or-nothing pair: both blank submits no `spec.credentials` in the payload or `update_mask` (credentials unchanged), both filled submits a complete replacement `{ username, password }` object under `update_mask: ["spec.credentials"]`, and filling in only one is rejected client-side before submission with a validation error explaining that both fields are required together to rotate credentials.

#### 6. Tiers List Page

The Tiers tab: columns NAME, BACKENDS, PROTOCOL(S), STATE, a "Create tier" button routing to `/admin/storage/tiers/create`, and a row-actions kebab (Edit — routes to `/admin/storage/tiers/:id/edit`; Delete). BACKENDS resolves every entry in `spec.backends[].backendId` to a name via a single `List` call scoped to exactly the backend IDs referenced across the rendered page (`usePrivateStorageBackends({ filter: storageBackendIdsFilter(ids) })`, §1) rather than fetching every registered backend unfiltered — this bounds the lookup to what the page actually needs regardless of how many backends exist in total, addressing a reviewer concern about an unbounded `List` call. Results are cached in a `Map<string, StorageBackend>` and rendered comma-separated, falling back to the raw ID for any entry that fails to resolve individually (a tier with a mix of resolved and unresolved backends shows both forms in the same cell). PROTOCOL(S) similarly lists each backend association's protocol, comma-separated, since different backends within one tier can use different protocols. STATE reads `status.state` and renders via `StorageTierStateLabel` (§9). Delete calls `useDeleteStorageTier()` with no pre-check; a blocked delete (`FAILED_PRECONDITION`, tier referenced by a Tenant) is shown verbatim and the row stays in place — see the Workflow Description note on this path not being reachable until OSAC-2872's trigger lands.

#### 7. Tier Create Form

A full page (`StorageTierCreatePage`, routed at `/admin/storage/tiers/create`) — same page-not-modal rationale as §4. Formik + Yup, single mutation on submit: `name` (DNS-label validated, §11), `description` (optional), and a single **backend association** section — `backend` (select, populated from `usePrivateStorageBackends({ filter: STORAGE_BACKEND_READY_LIST_FILTER })`), `protocol` (`NFS`/`BLOCK`), `maxReadBandwidthMbs` / `maxWriteBandwidthMbs` / `quotaGib` (positive-integer numeric fields), and `encryptionEnabled` (checkbox). Submits `{ metadata: { name }, spec: { description, backends: [{ backendId, protocol, maxReadBandwidthMbs, maxWriteBandwidthMbs, quotaGib, encryptionEnabled }] } }` via `useCreateStorageTier()` — always exactly one entry in the array — then navigates back to `/admin/storage/tiers` on success.

**Confirmed on the 2026-08-04 call: the admin selects exactly one backend per tier today**, even though `spec.backends` is a list in both the data model and the wire payload. Rather than a repeatable-row component, Formik's initial value is `{ name: '', description: '', backends: [{ backendId: '', protocol: '', maxReadBandwidthMbs: '', maxWriteBandwidthMbs: '', quotaGib: '', encryptionEnabled: false }] }` — `backends` is a one-element array from the start, and every field binds directly to `backends[0].*` (Formik natively supports indexed array paths; no dynamic add/remove logic is needed since the index is always `0`). This keeps the Formik state and the submitted payload list-shaped and forward-compatible: enabling multi-select later means rendering more than one set of fields and adding Add/Remove controls, not migrating the state shape or the payload contract.

An earlier revision of this design built a full repeatable-row component (`BackendAssociationsArrayField`, modeled on `ClusterNodeSetsArrayField.tsx` — the codebase's only precedent for hand-rolled `setFieldValue`-based array manipulation) ahead of the server's `validateBackends` v0.1 restriction, which still rejects more than one `spec.backends` entry with `INVALID_ARGUMENT`. That component is **not built in this revision** — see Non-Goals and Risks and Mitigations. When multi-select is prioritized, `ClusterNodeSetsArrayField.tsx` remains the pattern to copy (hand-rolled `setFieldValue` array manipulation with `rowId`-keyed rows, not Formik's `FieldArray`/`useFieldArray`, which has no usage anywhere in `osac-ui`).

#### 8. Tier Edit Form

`StorageTierEditPage`, routed at `/admin/storage/tiers/:id/edit` — same page-not-modal rationale as §5. `name` renders disabled (immutable — enforced server-side in `validateStorageTierUpdate`, which rejects any `metadata.name` change with `INVALID_ARGUMENT`); `description` and the single backend association's fields (§7) remain editable, since only `metadata.name` is immutable. Prefill reads the tier's `spec.backends[0]` (today there is only ever one entry) directly into the same `backends[0].*`-bound fields the Create form uses.

Editing *anything* in the backend association — the backend selection, protocol, bandwidth, quota, or encryption — submits the *complete*, current `spec.backends` array (still a one-element array) with `update_mask: ["spec.backends"]`; there is no per-field partial update, since standard protobuf `FieldMask` has no syntax for addressing individual elements of a repeated field, even a single-element one. The form's Formik state always holds the full (one-element) array regardless of what changed, and submits it whole.

The backend `Select`'s option list is the union of the `READY`-filtered list and the tier's own currently-assigned backend (fetched via `usePrivateStorageBackend(backendId)` if it has since left `READY`) — this avoids the create form's simpler always-`READY` filter silently dropping the existing selection when its backend has moved out of `READY`. Changing any QoS field shows an inline info alert: "Bandwidth and quota changes take effect immediately for existing and new volumes. Changes to encryption or protocol require the associated StorageClass to be recreated before new volumes pick them up; existing volumes are unaffected." Submits via `useUpdateStorageTier()`, then navigates back to `/admin/storage/tiers` on success.

#### 9. Lifecycle State Labels

Both `StorageBackendStateLabel` and `StorageTierStateLabel` wrap the shared `ResourceStatusLabel`/`StatusKind` primitive rather than introducing standalone components: `StorageBackendStateLabel` maps `READY` to `status="ready"` (green, "Ready") and `UNSPECIFIED` to `status="unspecified"` (grey); `StorageTierStateLabel` maps `ACTIVE` to `status="ready"` (green, "Active") and `UNSPECIFIED` to `status="unspecified"` (grey). `StatusKind`'s remaining values (`failed`, `progressing`) describe runtime reconciliation states that neither resource — having no reconciler — ever reaches, so each mapping only ever produces two of the primitive's four possible renderings; `ResourceStatusLabel`'s `text` prop still carries resource-specific wording ("Ready", "Active") rather than reusing generic reconciliation text, keeping the semantic mismatch contained to two small, obvious mapping functions rather than exposed to callers.

#### 10. Data Model (as consumed by this UI)

Both `StorageBackend` and `StorageTier` use the standard OSAC `spec`/`status` object shape, not a flat structure:

```text
StorageBackend {
  id, metadata { name },                // name immutable after creation
  spec: {
    provider: string,                    // immutable after creation; constrained to vast | ceph | pure in this UI
    endpoint: string,
    description?: string,
    credentials: { username: string, password: string }
  },
  status: { state: READY, message?: string }   // READY is the only value defined today; UNSPECIFIED is the proto3 zero value
}

StorageTier {
  id, metadata { name },                // name immutable after creation
  spec: {
    description?: string,
    backends: [ BackendAssociation ]    // list-shaped in the model/wire payload; this UI only ever populates exactly one entry today, by product decision (see Risks) — the server also currently rejects >1
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

Both protos are already merged and generated: `storage_backend_type_pb`/`storage_backends_service_pb` and `storage_tier_type_pb`/`storage_tiers_service_pb` exist in `osac-ui`'s generated types (`libs/types`) and are already exported from `libs/types/src/index-private.ts` — verified directly against `fulfillment-service`'s `origin/main` (`StorageBackend`: PR #728, merged 2026-06-18; `StorageTier`: PR #832, merged 2026-07-02, restructured to `spec`/`status` by PR #887, merged 2026-07-12) and against `osac-ui`'s current `libs/types`. This design has no remaining external blocker to being built — see Risks and Mitigations for the two behaviors (multi-backend, tenant-reference-delete) that are ahead of current server capability.

#### 11. Validation Constraints

- `StorageBackend.metadata.name` and `StorageTier.metadata.name`: RFC 1035 DNS label (1–63 chars, lowercase alphanumeric plus hyphens, no leading/trailing hyphen), validated client-side before submission on both create forms. **Confirmed the server performs no format validation of its own for either**: `private_storage_backends_server.go`'s `validateStorageBackendCreate` and `private_storage_tiers_server.go`'s `validateStorageTierCreate` both only check that `metadata.name` is non-empty (the OSAC-1111 design's stated intent to reuse a generic DNS-label validator was not implemented this way). This client-side check is therefore the *only* validation preventing an incompatible name from being submitted, not a defensive duplicate of a server-side rule — OSAC-2872 (Storage Control Plane) generates the StorageClass name `osac-{tenant}-{tier}` directly from the tier name, so an invalid name here would surface as a failure much later, in volume provisioning.
- `StorageBackend.spec.endpoint`, `spec.credentials.username`, `spec.credentials.password`: required, non-empty, rejected client-side before submission on the Create form; the server is the final authority (its own validation is limited to non-empty checks per `validateStorageBackendCreate`).
- `StorageBackend.spec.credentials.username`/`spec.credentials.password` on the **Edit** form specifically: validated as an all-or-nothing pair — both blank or both filled are valid, exactly one filled is rejected client-side with a validation error. See §5 for why (whole-message `FieldMask` semantics, no partial-field merge to rely on).
- `maxReadBandwidthMbs`, `maxWriteBandwidthMbs`, `quotaGib`: positive integers, rejected client-side before submission; the server is the final authority.

### Security Considerations

`StorageBackend.spec.credentials` (`username`/`password`) are collected via a masked `TextInput type="password"` on create and never pre-filled on edit — the edit form's credential fields start blank with helper text ("Leave blank to keep the current credentials"), and are validated as an all-or-nothing pair: both blank omits `spec.credentials` from the `Update` payload entirely (credentials unchanged), both filled submits a complete replacement object, and filling in only one is rejected client-side (see §5 for why — `FieldMask` addresses the whole `spec.credentials` message, not its individual leaf fields, so there's no partial-field merge to rely on). Whether `GetStorageBackend`/`ListStorageBackends` return credentials in plaintext or redacted is unconfirmed; the blank-by-default convention is followed regardless of the answer, since displaying a stored secret in a form field is poor practice either way. Since neither resource has a public API, there is no risk of credential exposure to tenants through this UI — the private API's existing OPA-enforced admin-only access control is the sole gate. `StorageBackend.spec.provider` is constrained to a fixed `Select` (`vast`/`ceph`/`pure`) rather than free text, since OSAC-2872 resolves the vendor CSI controller via `{provider}.osac-csi-backend.svc.cluster.local` — a typo in a free-text field would silently break volume provisioning with no client-side signal.

More broadly than credential confidentiality: `StorageBackend` as a *concept* must stay invisible to tenants (confirmed on the 2026-08-04 call) — not just its credentials, but its existence, ID, provider, and endpoint. Today this holds trivially, since this entire UI is admin-only and neither resource has a public API. The constraint that matters going forward is on OSAC-3014's future public `StorageTier` Get/List API: it must omit `spec.backends` (and everything nested under it) from whatever it returns to tenants, exposing only tier-level, tenant-appropriate fields. This design doesn't build that API, but flags the requirement here since it's a direct consequence of this data model.

Write access (create/update/delete) to both resources is restricted to Cloud Provider Admins via the existing OPA-based authorization already enforced server-side; the UI's role-gated nav entry (§2) only hides the entry point for convenience — there is no route-level guard, matching current codebase convention — so the server-side OPA check is the sole actual enforcement, not a backstop to a UI-side one.

### Failure Handling and Recovery

| Scenario | UI behavior |
|---|---|
| Backend Create/Update: duplicate active backend name | Server's `ALREADY_EXISTS` shown as a form-level error. |
| Backend Update: attempt to change `metadata.name` or `spec.provider` | Not reachable through the UI (both render disabled on edit); if attempted via a stale client, server's `INVALID_ARGUMENT` shown verbatim. |
| Backend Delete: backend still referenced by an active `StorageTier` | Server's `FAILED_PRECONDITION` shown verbatim (enforced today — see §3). |
| Tier Create/Update: duplicate active tier name | Server's `ALREADY_EXISTS` shown as a form-level error. |
| Tier Create/Update: referenced `StorageBackend` does not exist (e.g., deleted between the picker's `List` call and submission) | Server's `NOT_FOUND` naming the invalid backend ID shown as a form-level error. |
| Tier Create/Update: server's v0.1 single-backend restriction | Not reachable through this UI — the form only ever submits one `spec.backends` entry (see Non-Goals). If a future, multi-select revision of this UI submits more than one before the server's restriction is lifted, the server's `INVALID_ARGUMENT` ("only one backend association is supported in v0.1") would need to be surfaced as a form-level error at that time. |
| Update (either resource): concurrent conflicting write | Server's `FAILED_PRECONDITION`/`ABORTED` (stale version) shown as a submission error; admin re-fetches and retries. |
| Tier Delete: tier still referenced by a Tenant | Server's `FAILED_PRECONDITION` shown verbatim. Not yet reachable in the current backend — the enforcing trigger is deferred to OSAC-2872 (see Workflow Description); build the handling now regardless, since it costs nothing extra and the trigger is expected before this UI ships. |
| Backend picker's `List` call fails or is slow (Tiers tab) | `Select` shows its loading state; on failure, no options render. |
| Tiers list table's backend-name lookup fails | BACKENDS column falls back to the raw `backendId`. |

### RBAC / Tenancy

Both `StorageBackend` and `StorageTier` are platform-scoped, non-tenant resources managed exclusively by Cloud Provider Admins. The "Storage" nav entry is visible only when `role === 'admin'` (the current `UserRole` type's platform-admin value) — `tenant-admin`, `tenant-idp-manager`, and `tenant-user` are all excluded, since none has legitimate access to either resource. This is the same nav-gating-only mechanism the existing `Tenant` admin feature already uses (§2); no new RBAC concept, and no new route-guard mechanism, is introduced. There is no tenant-facing visibility to reason about for either resource, since neither has a public API.

### Observability and Monitoring

No new observability changes. Existing monitoring mechanisms (fulfillment-service gRPC Prometheus metrics and structured logging) already cover the underlying API calls; this design adds no client-side telemetry beyond what any other page in `osac-ui` already emits (none, per current convention).

### Risks and Mitigations

**DNS-label name validity is enforced only by this UI, not by the server, for both resources.** §11 documents that neither `private_storage_backends_server.go` nor `private_storage_tiers_server.go` performs name-format validation — any direct `osac` CLI or API caller can persist a name that later breaks StorageClass generation in OSAC-2872, bypassing this UI's client-side check entirely. *Mitigation:* none available within this document's scope — this UI cannot enforce a constraint on callers that don't go through it. The fulfillment-service should add the same RFC 1035 validation to both resources' Create/Update RPCs server-side (matching the client-side rule this design already applies); that is a backend change to the respective `design.md`s, not this UI design, and is flagged here as a cross-team follow-up rather than implemented.

**`QueryErrorState` may not recognize an OPA role-rejection as "Unauthorized."** `connectErrorInterceptor` (`libs/ui-components/src/api/api-context.tsx`) only converts gRPC `Unauthenticated` into the `UnauthorizedError` that `QueryErrorState` renders specially; if the private API's OPA policy instead returns `PermissionDenied` for a non-admin's rejected request (the semantically correct code for "authenticated but not authorized," distinct from "not authenticated at all"), a non-admin who reaches `/admin/storage/*` directly would see `QueryErrorState`'s generic error state, not a clear "Unauthorized" message. *Mitigation:* none implemented by this design — this is an existing gap in the shared `QueryErrorState`/`connectErrorInterceptor` mapping, already present in the live `TenantListPage` today, not introduced here. A small, separate fix to `connectErrorInterceptor` (map `PermissionDenied` too) would benefit both features equally; flagged here rather than fixed unilaterally in a UI design document scoped to Storage.

**Backend-picker `List` calls remain unpaginated and unfiltered-by-ID, inheriting an app-wide gap.** Every list page in `osac-ui` today — not just this design's — calls `.list(params)` once and assumes the full result set is returned; no page implements `Pagination`, and every hook's `select: (data) => data.items` discards the `size`/`total` fields the list-response protos already carry (verified across `instance-types.ts`, `networking.ts`, `tenant.ts`). The Create/Edit Tier forms' backend picker inherits this: if the number of `READY` backends ever exceeds what a single unpaginated `List` call returns, the picker would silently omit some. *Mitigation:* the Tiers list page's own backend-name lookup avoids this by scoping its `List` call to exactly the referenced IDs via the new `storageBackendIdsFilter` `id in [...]` CEL filter (§1, §6) rather than fetching everything — but the picker itself still needs the *full* `READY` set as selectable options, so it cannot use the same technique. This is a known, pre-existing app-wide limitation this design does not fix (real pagination or infinite-scroll on every list page is out of scope for a UI design about Storage specifically), not a defect unique to Storage.

**This UI intentionally matches the server's current v0.1 single-backend capability, even though the data model is list-shaped.** OSAC-1110 FR-3 describes "one or more backend associations," and an earlier revision of this design built a full repeatable multi-row UI ahead of the server's `validateBackends` restriction, based on informal reviewer/PR-comment direction. That was superseded on the 2026-08-04 storage-scope call: product confirmed the admin should choose exactly one backend per tier for now, matching (not outrunning) the server's current restriction. *Mitigation:* none needed today — UI and server capability are aligned. The forward-looking risk is the reverse of before: the Formik state and payload are deliberately kept list-shaped (`spec.backends: [oneEntry]`, §7) specifically so that re-introducing multi-select later, once product and the server are both ready, is a UI-rendering change (add the repeatable rows and Add/Remove controls back, following `ClusterNodeSetsArrayField.tsx`'s pattern) rather than a data-model or payload migration.

**Delete-blocked-by-tenant-reference cannot be exercised until OSAC-2872 lands.** The UI implements this error-handling path (§ Failure Handling and Recovery) against a server behavior that does not exist yet — the DB trigger enforcing it is deferred to a follow-up migration shipping with OSAC-2872 (Storage Control Plane), the current live epic that owns tenant-to-tier assignment. *Mitigation:* none needed for this UI's correctness — the code path is inert until the trigger lands, not incorrect. Component/unit tests for this path must mock the `FAILED_PRECONDITION` response rather than relying on integration test coverage, since no real backend will produce it before OSAC-2872 ships.

**`StorageBackend`'s lifecycle-state enum may grow.** `STORAGE_BACKEND_STATE_MAINTENANCE`/`STORAGE_BACKEND_STATE_DECOMMISSIONED` were described as intended future values in the OSAC-1111 design but do not exist in the merged proto's enum today. *Mitigation:* `StorageBackendStateLabel` (§9) is written generically against `ResourceStatusLabel`'s `StatusKind` mapping so a new enum value only requires a new mapping line, not a new component; lifecycle-*action* UI (Mark maintenance, Decommission) is out of scope until those values actually exist (see Non-Goals) and should be designed fresh when they do, since there is no current contract to build against.

**Masked-credential input and immutable-field-on-edit are new UI primitives with no existing precedent.** Both are being introduced for the first time in this codebase. *Mitigation:* both are narrowly scoped (a single PatternFly `TextInput type="password"`; a `disabled` prop on specific `InputField`s) rather than new abstractions, keeping the risk of a poorly-generalized first implementation low.

### Drawbacks

Building full CRUD for `StorageBackend` — not just a read-only picker — adds real scope: a masked-credential-input primitive, an immutable-field-on-edit form pattern, and a second full list/create/edit/delete surface, none of which existed in an earlier, narrower revision of this design. This is a deliberate trade-off accepted on the OSAC-1111 design owner's explicit input that the admin workflow is incomplete without it (see Motivation) — the cost is real added implementation surface, weighed against an incomplete admin experience otherwise.

This design also does not anticipate OSAC-3014's future public `StorageTier` Get/List API. When that lands, a tenant-facing consumer (e.g., a tier picker in the VMaaS disk-configuration wizard for OSAC-1710) will need its own hook module and UI, following the existing public/private split pattern (e.g. `ClusterVersion`'s `api/v1/cluster-versions.ts` vs. `api/v1/private/cluster-versions.ts`). No changes to this admin design are anticipated as a result — the private CRUD surface this design builds and a future public read-only surface are independent — but this is called out as a known adjacent piece of work this design does not cover.

## Alternatives (Not Implemented)

**`StorageTier`-only UI, treating `StorageBackend` as read-only support data.** Pros: smaller scope — no masked-credential-input primitive, no second full CRUD surface, no immutable-`provider`-on-edit handling. Cons: leaves backend registration and credential rotation to the CLI/raw API mid-workflow, which the OSAC-1111 design owner identified in review as an incomplete admin experience — "a Cloud Admin will first configure the `StorageBackend` and will then configure the `StorageTier` for the backend," and it "seems incomplete... to create a `StorageTier` without having the ability to see information on the `StorageBackend`." Rejected on that direct product-workflow input from the resource's own design owner.

**Standalone `StorageBackendStateLabel`/`StorageTierStateLabel` with their own color maps, bypassing `ResourceStatusLabel` entirely.** Pros: no semantic mismatch to explain — resources with no reconciler never need a mapping to `StatusKind`'s reconciliation-oriented values. Cons: duplicates a component that already renders exactly the needed PatternFly `Label` shape, for enums that map onto `StatusKind` with no ambiguity. Rejected in favor of thin wrappers around `ResourceStatusLabel`: the semantic mismatch is real, but confining it to two small, explicit mapping functions is cheaper than two components duplicating `ResourceStatusLabel`'s rendering logic.

**Full repeatable multi-backend UI (`BackendAssociationsArrayField`), built ahead of the server's v0.1 single-backend restriction.** This was the previous revision's approach: a hand-rolled repeatable-row component (`ClusterNodeSetsArrayField.tsx`-style, `setFieldValue`-based array manipulation, not Formik's `FieldArray`/`useFieldArray` — which has no usage anywhere in `osac-ui`), justified by OSAC-1110 FR-3's "one or more" wording and informal reviewer/PR-comment direction. Pros: matches FR-3 literally, and is ready the moment the server lifts its restriction. Cons: lets an admin add a second backend row and hit a confusing server-side `INVALID_ARGUMENT` today, and — per the 2026-08-04 call — doesn't match the actual product decision to keep the interaction to one backend per tier for now regardless of what the data model allows. Rejected on that direct product input; revisit (using the same `ClusterNodeSetsArrayField.tsx` pattern) once multi-backend selection is prioritized.

**Do nothing (continue with Ansible extra vars and the `STORAGE_TIERS` env var).** Pros: zero UI work. Cons: this is the status quo both PRDs are replacing — no API-managed catalogs, no UI, blocks OSAC-2872. Rejected because both PRDs require API-managed catalogs with CRUD access and there is no other planned graphical interface for Cloud Provider Admins to manage either resource.

## Test Plan

**Unit and component tests** (Vitest + React Testing Library, mocked Connect transport per `osac-ui` convention — no fetch/REST mocks):
- Hook modules: correct RPC invoked per hook, cache invalidation on mutation success, `STORAGE_BACKEND_READY_LIST_FILTER`'s literal value.
- Nav/routing: `getAdminNav`'s "Storage" entry appears alongside "Tenants" only when `navRowsForRole` is called with `role === 'admin'`, and is absent for `tenant-admin`, `tenant-idp-manager`, and `tenant-user`. No test asserts a redirect for direct-URL access — there isn't one (§2) — but a mocked `PermissionDenied`/`Unauthenticated` response from each Storage page's data hook should render the existing `QueryErrorState` handling, matching `TenantListPage.test.tsx`'s existing coverage shape.
- Backends tab: table renders expected rows/columns, empty/loading states, delete success and `FAILED_PRECONDITION` (referenced-by-tier) handling.
- Backend create form: DNS-label validation, required-field validation (endpoint, credentials), the password field renders as `type="password"` and is never rendered as plain text, `ALREADY_EXISTS` error surfacing.
- Backend edit form: prefill, `name`/`provider` rendered disabled, credential fields render blank on open (never pre-filled from fetched data), both-blank omits `spec.credentials` from the submitted payload, both-filled submits a complete replacement `{ username, password }` object, username-only and password-only are each rejected client-side with a validation error before submission, stale-version conflict handling.
- Tiers tab: table renders expected rows/columns, backend-name resolution and its ID-fallback path, empty/loading states, delete success and `FAILED_PRECONDITION` handling.
- Tier create form: DNS-label and positive-integer validation, backend picker excludes non-`READY` backends, `ALREADY_EXISTS`/`NOT_FOUND` error surfacing, and the submitted payload wraps the single selection in a one-element `spec.backends` array (`[{ backendId, protocol, ... }]`), never a bare object.
- Tier edit form: prefill reads `spec.backends[0]` into the form's fields, `name` rendered disabled, the backend picker includes the tier's own non-`READY` currently-assigned backend, QoS-change alert triggers correctly, stale-version conflict handling, submitting an unchanged form still submits the complete one-element array with `update_mask: ["spec.backends"]`.
- Tiers list page's backend-name resolution: `storageBackendIdsFilter` is built from exactly the set of `backendId`s present on the rendered page (not a superset, not all registered backends).

**E2E tests** (owned by QE, authored in `osac-test-infra` via the `/e2e` workflow — `osac-ui` has no e2e tests of its own):
- Full backend register → edit → delete flow, including delete-blocked-by-tier-reference.
- Full tier create → list → edit → delete flow against a real (or kind-deployed) fulfillment-service, including duplicate-name rejection and delete-blocked-by-tenant-reference.
- Role gating: a non-admin does not see the "Storage" nav entry; direct-URL access is not blocked at the route level (no route guard exists — see §2), so this case exercises the same error-state handling as an API-level authorization rejection.

The tenant-reference-blocks-delete scenario cannot be exercised as a true e2e test until OSAC-2872's enforcing trigger lands (see Risks and Mitigations) — cover it with a mocked `FAILED_PRECONDITION` response in the meantime, and add the real e2e case once the trigger exists.

## Documentation

Admin-facing documentation should cover credential handling expectations for the Backends tab (the "leave blank to keep unchanged" convention on edit is not self-evident) — otherwise this remains a narrow, largely self-explanatory pair of CRUD screens, consistent with how other simple admin catalog resources (`NetworkClass`) have no dedicated user guide in the OSAC docs repo today. Revisit scope if user feedback indicates the QoS fields or backend-state semantics need additional written guidance.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages: Dev Preview -> Tech Preview -> GA based on production deployment feedback, tracking the graduation of the underlying `StorageBackend`/`StorageTier` APIs.

## Upgrade / Downgrade Strategy

This is new UI with no upgrade impact — it is additive to `osac-ui` and does not change behavior for any existing route or nav entry. Downgrade requires removing the "Storage" nav entry, its route, and the two new hook modules; no data migration is involved since all state lives in the fulfillment-service.

## Version Skew Strategy

Proto backward compatibility (additive-only field changes) covers schema-level version skew, but this UI depends on more than the schema: it also assumes the specific behaviors verified in this document — the `spec.backends` single-entry constraint (`validateBackends` rejecting more than one), the `status.state == READY` filter semantics, the `update_mask`/`FieldMask` handling, and the exact error codes in Failure Handling and Recovery. None of these are guaranteed by additive schema compatibility alone; a fulfillment-service version older than the one this design was verified against (StorageBackend PR #728, StorageTier PR #832/#887) may not exhibit them. **Minimum supported fulfillment-service version:** the commit introducing PR #887 (StorageTier `spec`/`status` restructuring, 2026-07-12) — this UI's payload shapes are written against that structure and will fail against an older, flat-shape server. There is no client-side capability gate or version check in this design; deploying this UI against an older fulfillment-service is a deployment-sequencing concern, not one this UI detects or handles at runtime.

## Support Procedures

**Detecting failures:** Browser console errors on the Storage admin page; fulfillment-service gRPC error-rate metrics for `StorageBackends`/`StorageTiers` RPCs (existing dashboards, no new ones added).

**Disabling the feature:** Remove the "Storage" route and nav entry (revert §2's changes). No impact on any other `osac-ui` page — this feature has no dependents.

**Recovery:** Re-enable by restoring the route and nav entry. No data loss risk, since all state lives in the fulfillment-service, not in `osac-ui`.

## Infrastructure Needed

None.

---

## Provenance

Authored: draft @ design 0.5.0 - 68284c8, workspace worktree-delightful-gliding-perlis @ 57ca666
Final: respond @ design 0.5.0 - 68284c8, workspace docs/OSAC-1110-1111-storage-ui-design @ 47288de (25 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.5.0","ai_workflows":"68284c8","source_repo":"47288de","source_repo_branch":"docs/OSAC-1110-1111-storage-ui-design","commits_behind_main":25,"commits_ahead_main":3,"main_ref":"main","phases":["draft","revise","respond","respond","respond","respond","respond","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true} -->
