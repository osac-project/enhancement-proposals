---
title: vm-instance-types-ui
authors:
  - brotman@redhat.com
creation-date: 2026-08-05
last-updated: 2026-08-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3586
prd:
  - Backend instance types proposal: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/vm-instance-types/README.md
see-also:
  - https://redhat.atlassian.net/browse/OSAC-46
  - https://redhat.atlassian.net/browse/OSAC-1205
  - https://redhat.atlassian.net/browse/OSAC-2917
replaces:
  - N/A
superseded-by:
  - N/A
---

# VM Instance Types UI

## Summary

This design adds a Cloud Provider Admin UI for the existing `InstanceType`
backend API. It builds on the backend instance-types proposal already defined
under [OSAC-46](https://redhat.atlassian.net/browse/OSAC-46) and implemented
under [OSAC-1205](https://redhat.atlassian.net/browse/OSAC-1205). No proto or
backend changes are part of this work.

This phase is intentionally narrow: it is only for the cloud provider admin
experience. Tenant-facing instance type selection and display already exist and
are out of scope here.

## Scope

In scope:

- A provider-only instance type list page.
- A provider-only create flow for new instance types.
- Lifecycle state management from the list page using predefined row actions.
- Use of the existing private `InstanceTypes` API from `osac-ui`.

Out of scope:

- Tenant-facing UX changes.
- GPU-related instance type fields. UI design for that work will be added
  alongside
  [the OSAC-2917 GPU instance types PRD](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-2917-gpu-instance-types/prd.md).

## Proposal

Add a new provider-admin UI surface in `osac-ui` for `InstanceType`
management.

### Navigation and Routing

- Add a new `Infrastructure` nav item under the admin area.
- Add a new `Instance Types` nav item under `Infrastructure`.
- Add admin routes for:
  - `/admin/infrastructure/instance-types` for the list page
  - `/admin/infrastructure/instance-types/new` for the create page

### List Page

- Add a list page that shows existing instance types with basic columns:
  name, cores, memory (GiB), description, and `Lifecycle State`.
- If fetching instance types fails, show the same non-loading error state used
  by other list pages.
- Distinguish a failed `useAdminInstanceTypes` request from a successful empty
  result; the latter remains the normal empty state.
- The `Lifecycle State` column should use the same visual treatment as
  ClusterVersions: `ACTIVE` in green, `DEPRECATED` in gold, and `OBSOLETE` in
  grey.

### Create Page

- Add a create page with fields for name, description, CPU cores, and Memory
  (GiB). `cores` and `memory_gib` should be required integer values greater
  than zero.
- The create form should follow the existing wizard interaction pattern:
  submit remains enabled, and clicking submit surfaces validation errors from
  the schema instead of pre-emptively disabling the action.

### Lifecycle Actions

- Add table row actions for lifecycle management using the same approach as the
  ClusterVersion design: `Mark deprecated`, `Mark obsolete`, and
  `Reactivate`.
- Compute available lifecycle actions from the current backend state. For
  example, an `OBSOLETE` instance type offers `Reactivate` and
  `Mark deprecated`, but not `Mark obsolete`.

This design does not add a general edit form for lifecycle metadata. State
transitions happen through explicit row actions, while timestamps remain
system-managed by the backend.

This design also does not add a details page. `InstanceType` currently has no
conditions or additional read-only detail data that would provide value beyond
the list and create flows in this phase.

This design intentionally omits a delete action from the UI. Deletion is not
the recommended lifecycle for instance types; admins should generally use
`DEPRECATED` and `OBSOLETE` state transitions instead. Hard delete remains
available through the CLI for exceptional cleanup cases.

## Field naming

- `metadata.name` -> Name
- `spec.description` -> Description
- `spec.cores` -> CPU cores
- `spec.memory_gib` -> Memory (GiB)

## Implementation details

- **Name field**: use the shared `NameField` for `metadata.name`. `InstanceType`
reuses the common backend `Metadata.name` validation (RFC 1035 DNS-label
restrictions) — the same validation that already backs `NameField` for
resources such as `ComputeInstance`, so no new field component is needed.

- **Numeric fields**: use the shared `InputField` with `type="number"` for
`spec.cores` and `spec.memory_gib`.

- **API hooks**: add `libs/ui-components/src/api/v1/private/instance-type.ts`,
following the existing `private/tenant.ts` pattern (private `InstanceTypes`
client from `@osac/types/private`) together with the update-mask pattern
already used by `usePatchComputeInstance` in `compute-instance.ts`. Register a
new `'v1/private/instance_types'` entry in `ApiRoute`
(`libs/ui-components/src/api/types.ts`) first. Hooks needed:
  - `useAdminInstanceTypes` — list, via the private client, returning all
    lifecycle states. The codebase already has a tenant-facing
    `useInstanceTypes` in `v1/instance-types.ts`, so the provider/admin flow
    should use a distinct hook name rather than introducing a second
    `useInstanceTypes`.
  - `useCreateInstanceType` — create mutation for the create page, invalidating
    the list query on success (same shape as `useCreateTenant`).
  - `useUpdateInstanceTypeState` — one mutation hook parameterized by a
    `InstanceTypeLifecycleAction = 'deprecate' | 'obsolete' | 'reactivate'`
    input, mirroring how `usePatchComputeInstance` is parameterized by
    `ComputeInstancePowerAction`. It builds the `spec.state` update body and the
    corresponding `updateMask` via `buildUpdateMaskPaths`, and invalidates the
    list query on success. Each row action (`Mark deprecated`, `Mark obsolete`,
    `Reactivate`) calls this one hook with its action, rather than each needing
    a separate mutation hook.


## Security and RBAC

`InstanceType` is a provider-defined resource. Write operations remain
restricted to Cloud Provider Admin users through the existing private API. This
design adds only a UI client for those existing permissions.

## Failure Handling

- List-page fetch failures should use the same pattern as other list pages: a
  non-loading error state for failed `useAdminInstanceTypes` requests. This is
  distinct from the empty-result state returned by a successful request with no
  instance types.
- Create and lifecycle-operation failures surface as a dismissible inline alert
  at the top of the page. The alert body should render the backend error
  message directly.
- Create failures use the title `Failed to create instance type`.
- Deprecation failures use the title `Failed to deprecate instance type`.
- Obsolete-transition failures use the title
  `Failed to mark instance type as obsolete`.
- Reactivation failures use the title `Failed to reactivate instance type`.
- Invalid create input surfaces standard validation errors. In particular, the
  backend rejects `spec.cores <= 0` with `field 'spec.cores' must be greater
  than zero` and rejects `spec.memory_gib <= 0` with
  `field 'spec.memory_gib' must be greater than zero`.

## Test Plan

- Unit-test the new private API hooks.
- Unit-test the provider list and create flows, including loading, empty, and
  error states.
- Unit-test lifecycle state rendering and action availability for `ACTIVE`,
  `DEPRECATED`, and `OBSOLETE`.
- Unit-test lifecycle row actions so the correct update request is sent for
  `Mark deprecated`, `Mark obsolete`, and `Reactivate`.

No new backend or E2E coverage is required for this design.

---

## Provenance

Authored: respond @ design 0.3.0 - 1e226e0, workspace main @ 8f899d5
Phases: draft, revise, revise, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.3.0","ai_workflows":"1e226e0","source_repo":"8f899d5","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":347,"main_ref":"main","phases":["draft","revise","revise","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false} -->
