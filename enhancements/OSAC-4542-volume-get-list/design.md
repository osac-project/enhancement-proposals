---
title: volume-get-list-public-api
authors:
  - Zoltan Szabo
creation-date: 2026-08-27
last-updated: 2026-08-27
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4542
prd:
  - "prd.md"
see-also:
  - "OSAC-2872 (storage control plane — private Volume API)"
  - "OSAC-984 (public Volume API epic)"
---

# Volume Get/List Public API

## Summary

Add a read-only public projection of the existing private Volume API: a public
`Volumes` service exposing only `List` and `Get` over gRPC and REST at
`/api/fulfillment/v1/volumes`. The public server wraps the already-shipped
`PrivateVolumesServer`, reusing its DAO, tenancy enforcement, and CEL filtering,
and maps private→public so that internal routing fields never leave the service.
See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC-2872 delivered the private Volume API, the volume inventory, and tier→backend
resolution, but volumes are only reachable through the internal API. The console
and tenants cannot read the inventory, so the storage UI is blocked and tenants
have no operational visibility. This enhancement adds the minimal read surface —
`Get` and `List` — needed to unblock the console, without touching provisioning.

### Goals

- Reuse the established public-wraps-private server pattern (as in
  `external_ips_server.go`), adding no new data path.
- Inherit tenant scoping and CEL filtering from the private server / generic DAO
  rather than reimplementing them.
- Expose only tenant-meaningful fields; keep internal routing (backend, protocol,
  hub, vendor volume id) private.
- Introduce no schema change — reuse the OSAC-2872 `volumes` table.

### Non-Goals

- Volume lifecycle through the public API (create/update/delete/resize) — deferred
  to later OSAC-984 phases.
- Per-user (owner-level) visibility for Tenant Users — deferred to a platform-wide
  tenancy feature (see RBAC / Tenancy and Open Questions).
- Volume attach/detach, snapshots/clones, file storage (OSAC-4515), object storage.

## Proposal

Enumerated changes, all in `fulfillment-service`:

1. **Public proto (generated from private via cleanapi).** Opt the private
   `Volumes` service and `Volume` type into public generation; expose only `List`
   and `Get`; strip the internal status fields (`backend`, `protocol`, `hub`,
   `vendor_volume_id`). `StorageProtocol`/`storage_common_type` stay fully private.
2. **Public `VolumesServer`** (`internal/servers/volumes_server.go`): delegates
   `List`/`Get` to `PrivateVolumesServer`, maps private→public (dropping internal
   fields), and sets the CEL filter descriptor to the public `Volume` so callers
   can only filter on visible fields.
3. **Private server adjustment** (`private_volumes_server.go`): make the tier
   resolver optional (it is used only by `Create`) so the read-only delegate can be
   built without one; add `SetFilterDesc`.
4. **Wiring**: register the public `Volumes` gRPC service (`register_servers.go`)
   and REST handler (`start_rest_gateway_cmd.go`).
5. **Authorization** (`authz.rego`): allow tenant clients on the public
   `Volumes/Get` and `Volumes/List` methods.

### Workflow Description

Actors: **Tenant User / Tenant Admin** (read their tenant's volumes via console or
CLI), **Cloud Provider Admin** (read across assigned tenants). Starting state:
volumes already exist and are inventoried by OSAC-2872.

Request path:

```
HTTP/gRPC client
  -> REST gateway (grpc-gateway mux)            [REST callers only]
  -> gRPC interceptors: authn (JWT) -> authz (OPA) -> tenancy
  -> public VolumesServer.List/Get
  -> PrivateVolumesServer.List/Get
  -> GenericServer[Volume] (tenant scoping + CEL filter) -> GenericDAO -> PostgreSQL
```

Steps (List): the caller requests `GET /api/fulfillment/v1/volumes` (optionally
with filter/order/offset/limit); OPA authorizes the method; the private delegate
scopes rows to the caller's visible tenants and applies the CEL filter; the public
server maps each row to the public shape and returns items + size + total. Get is
the same by id, returning `NotFound` when the id is not visible/absent.

### API Extensions

- New **public gRPC service** `osac.public.v1.Volumes` with `List` and `Get`, and
  REST transcoding at `/api/fulfillment/v1/volumes` and `/{id}`.
- New public `Volume` message (subset of the private one).
- No CRDs, webhooks, aggregated API servers, or finalizers. No change to any
  externally-owned resource.

## UX Alignment

The `osac-ux` repo (whose hand-written `@temp-api` files an earlier draft of this
section referenced) is **deprecated** (osac-project/osac-workspace#224) and is no
longer a source of truth for UI types. The authoritative UI types live in
**`osac-ui`** (`libs/types`) and are **generated directly from the backend proto**
via `pnpm gen-types`.

The public Volume API is net-new: `osac-ui` currently has only the *private*
Volume types (generated from OSAC-2872) — no *public* Volume types exist yet,
because this EP is what introduces them. Once this EP's public proto merges and
`osac-ui` runs `gen-types`, the public `Volume` types are generated straight from
this proto, so there are **no deviations to reconcile** by construction. The only
UI-side action is regenerating types after this lands. (Confirmed with the UI owner.)

### Implementation Details/Notes/Constraints

- The private→public field hiding is done by a `GenericMapper` with
  `SetStrict(false)` — the copy silently omits fields absent from the public type
  (the same mechanism `external_ips_server.go` uses). There is no `inMapper`
  because there are no write RPCs.
- `SetFilterDesc((*publicv1.Volume)(nil).ProtoReflect().Descriptor())` restricts
  CEL filters to public fields, so a caller cannot filter on hidden fields such as
  `status.backend`.
- **cleanapi import pruning (tooling note):** cleanapi v0.0.8 copies imports
  verbatim and does not prune those that become unused after fields/methods are
  stripped (`storage_common_type` in the public `volume_type`, `field_mask` in the
  public `volumes_service`); `buf lint` (`IMPORT_USED`) then rejects them. The two
  unused imports are pruned by hand in the generated public protos, matching the
  committed state of other read-only public resources (e.g.
  `baremetal_instance_types_service`). A follow-up to automate this in
  `dev.py build protos` (or bump cleanapi) is a candidate.

### Security Considerations

Read-only endpoints; no new secrets or data-mutation paths. Tenant isolation is
enforced by the existing tenancy layer (below). Internal routing fields that could
leak backend topology are excluded from the public type by construction. Input is
limited to an id and standard list parameters; CEL filters are constrained to the
public field set.

### Failure Handling and Recovery

- **Not found / not visible:** `Get` returns `NotFound`; `List` excludes rows
  outside the caller's visible tenants.
- **Invalid CEL filter / order:** returns `InvalidArgument` from the existing
  filter translator.
- **Mapping error:** returns `Internal` (logged); no partial data is returned.
- **Delegate/DB errors:** propagated unchanged from the private server. No retries
  or side effects (reads are idempotent).

### RBAC / Tenancy

Scoping is inherited, not reimplemented. OPA (`authz.rego`) gates *method* access —
this EP adds `Volumes/Get` and `Volumes/List` to the tenant-client allowlist.
*Row* scoping comes from `GenericServer`/`GenericDAO` via
`DefaultTenancyLogic.DetermineVisibleTenants`, which restricts results to the
caller's tenants (plus shared). This is **tenant-level** scoping — the same model
every other resource uses; role does not change which rows are visible, only which
methods may be called.

The PRD DoD's "Tenant User sees only their own volumes" is a **per-creator**
boundary that no OSAC resource implements today (`creator` is an attribution field
and an optional filter, never an enforced boundary). Implementing it requires
new, cross-cutting tenancy plumbing (a role-aware `creator` predicate) and should
apply uniformly across resources; it is therefore **deferred to a platform tenancy
feature**. This EP ships tenant-level scoping, which is consistent and unblocks the
console. No new tenant-isolation metadata is introduced (reads reuse the existing
`tenant` column and visibility logic).

### Observability and Monitoring

No new observability changes. Existing gRPC metrics, structured request logging,
and the interceptor chain apply to the new methods automatically.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| DoD "own only" not met by tenant-level scoping | A Tenant User sees all volumes in their tenant, not just their own | Explicitly scoped out to a platform tenancy feature; flagged on the PR for the team to own or delegate; no migration needed later (`creator` column + index exist) |
| cleanapi leaves unused imports in generated public protos | `buf lint` fails on regeneration | Prune the two imports (documented); follow-up to automate in tooling |

### Drawbacks

Read-only is a partial capability — the console can display but not manage volumes
until later phases. Tenant-level (not owner-level) visibility is a deliberate
narrowing of the stated DoD for this release.

## Alternatives (Not Implemented)

- **Hand-write the public proto.** Rejected — public protos are generated from
  private via cleanapi by convention; hand-writing would diverge from every other
  resource and drift on regeneration.
- **Expose `protocol` (and thus `storage_common_type`) publicly** to avoid the
  dangling-import problem. Rejected — protocol is an internal routing detail; the
  import is pruned instead.
- **Publish an empty public `storage_common_type`** so the import resolves.
  Rejected — `buf lint IMPORT_USED` still fails, and it publishes a meaningless
  type.

## Open Questions [optional]

1. **Ownership of the deferred owner-level visibility feature.** Tenant-level
   scoping ships here; per-creator visibility is a platform-wide tenancy
   capability. Team decision: own it in this WG or delegate to a platform/tenancy
   owner.

## Test Plan

### Unit Tests
- Public `Get` returns the public projection; `List` returns items with size/total.
- Field mapping: public `Volume` carries spec (tier/size/access mode) and status
  (state/message); internal fields are absent by type.
- CEL filter over a public field (`status.state`) returns the expected subset.
- `Get` on a nonexistent id returns an error.
- Authz: a tenant client is allowed on `Volumes/Get` + `/List` and denied on
  (nonexistent) public `Volumes/Create` + `/Delete`.
- Private server: builds without a tier resolver; `Create` without a resolver fails.

### Integration Tests
- Against the kind `osac-dev` cluster: list/get standalone volumes created via the
  private path through the public gRPC endpoint, asserting the public shape and
  tenant scoping (a subject in tenant A does not see tenant B's volumes).

### E2E Tests
- Add a read-path check to the osac-test-infra vmaas suite: provision a volume via
  the existing path, then Get/List it through the public API and assert the public
  representation and tenant-scoped visibility.

## Graduation Criteria

Ships as part of the public Volume API (v0.2). No separate maturity ladder; the
read endpoints graduate with the rest of the public API. Later OSAC-984 phases add
the mutating lifecycle.

## Upgrade / Downgrade Strategy

Additive, read-only API surface with no schema change. Upgrade adds the new
endpoints; downgrade removes them with no data migration. No existing client must
change to keep working.

## Version Skew Strategy

The public API is generated from the private API and served by the same process;
there is no cross-component skew. An older console simply does not call the new
endpoints. The public `Volume` is a strict subset of the private type, so proto
evolution follows the standard additive-field rules.

## Support Procedures

Failures surface as standard gRPC/REST errors (`NotFound`, `InvalidArgument`,
`PermissionDenied`, `Internal`) visible in request logs. The endpoints can be
effectively disabled by removing the `Volumes/Get`+`/List` entries from the OPA
allowlist (callers then receive `PermissionDenied`); this affects only read access
and has no effect on provisioning or running workloads.

## Infrastructure Needed [optional]

None.

---

## Provenance

Committed: commit @ design 0.9.0 - f7f8c6d, workspace main @ b177ce9 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.9.0","ai_workflows":"f7f8c6d","source_repo":"b177ce9 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit","commit","commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
