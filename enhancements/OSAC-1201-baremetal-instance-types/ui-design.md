---
title: bare-metal-instance-types-ui
authors:
  - rawagner@redhat.com
creation-date: 2026-08-24
last-updated: 2026-08-24
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2677
prd:
  - Bare Metal Instance Types PRD: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1201-baremetal-instance-types/prd.md
see-also:
  - https://redhat.atlassian.net/browse/OSAC-1201
  - Backend design: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1201-baremetal-instance-types/design.md
  - VM Instance Types UI: https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-46-vm-instance-types/ui-design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# Bare Metal Instance Types UI

## Summary

This design adds `osac-ui` console support for the `BareMetalInstanceType`
resource defined by the Bare Metal Instance Types feature
([OSAC-1201](https://redhat.atlassian.net/browse/OSAC-1201)). It covers two
user-facing surfaces:

1. A **Cloud Provider Admin** surface to create, edit, and delete
   `BareMetalInstanceType`s, including the private host label selector
   [PRD: FR-4].
2. A **Tenant User** selection control in the BareMetalInstance provisioning
   wizard that lists available types, shows their hardware for comparison, and
   sets the instance's `instance_type` [PRD: FR-1, FR-2, FR-3].

`BareMetalInstanceType` is architecturally separate from the VM `InstanceType`
resource — a separate resource with a separate (empty) lifecycle
[Locked: D1]. The admin surface reuses the structural pattern already shipped
for VM instance types (`components/InstanceType/`, private CRUD hooks,
`/admin/infrastructure/*` routing) but does **not** copy its
ACTIVE/DEPRECATED/OBSOLETE lifecycle actions — `BareMetalInstanceTypeStatus`
is empty [Codebase: libs/types/src/osac/private/v1/baremetal_instance_type_type_pb.ts].
As with VM instance types, there is no standalone tenant browse page; tenants
encounter types at the point of use, in the provisioning wizard.

The `BareMetalInstanceType` resource, its public (`List`, `Get`) and private
(`List`, `Get`, `Create`, `Update`, `Delete`) services, and
`BareMetalHardwareSpec` are already generated in `@osac/types`. The tenant
selection surface (#2) additionally depends on an `instance_type` field being
added to `BareMetalInstanceSpec`, which the backend design specifies but which
is **not yet in the proto** [User]. That surface is drafted here in full and
decomposed as a story gated on that proto change.

## Scope

In scope:

- A provider-only `BareMetalInstanceType` list page.
- A provider-only create and edit flow, including the private
  `host_label_selector`.
- A provider-only delete action.
- A tenant instance-type selection control in the existing BareMetalInstance
  provisioning wizard, which lists available types and shows their hardware
  metadata for comparison [PRD: FR-1, FR-3] and sets `instance_type`
  [PRD: FR-2] (gated on the forthcoming `instance_type` field). The control is
  enabled/disabled/pre-filled based on the catalog item's `field_definitions`,
  consistent with how the wizard's other fields are gated.
- New public and private `BareMetalInstanceTypes` API hooks in `osac-ui`.

Out of scope:

- **A standalone tenant browse page.** Consistent with VM instance types,
  tenants do not get a separate list/detail area; discovery and hardware
  display [PRD: FR-1, FR-3] happen in the wizard selector. FR-1/FR-3 also
  remain served at the CLI/API level by the public service, which is outside
  the UI scope.
- **Type lifecycle management** (deprecate/obsolete/reactivate). The resource
  has no lifecycle — `BareMetalInstanceTypeStatus` is empty and complex
  lifecycle is an explicit backend Non-Goal [Locked: D1].
- **Operator label-based host selection** during provisioning [PRD: FR-5] —
  backend-only, no console surface.
- **Inventory backend configuration** (`inventory.yaml`) — a Cloud
  Infrastructure Admin task with no console surface today.
- **Host-count / capacity display** — tracking available hosts per type is a
  backend Non-Goal deferred to a later PRD.
- **Provisioned BareMetalInstance hardware display** — whether an instance's
  detail view shows its actual (`BareMetalInstanceStatus.hardware`) and/or
  requested hardware is a separate follow-up, not part of the type surfaces
  here [User].
- Any change to `osac-ux`, which is a read-only UX reference only.

## Proposal

Add two surfaces to `osac-ui`: a provider-admin management area and a wizard
selection control. Both consume the `BareMetalInstanceTypes` services already
defined in `@osac/types` (the wizard additionally uses the forthcoming
`instance_type` field on `BareMetalInstanceSpec`).

### Data model

`BareMetalInstanceType` carries a required `spec.hardware`
(`BareMetalHardwareSpec`) and an optional `spec.description`
[Codebase: proto/public/osac/public/v1/baremetal_instance_type_type.proto].
The private spec adds a required `host_label_selector` with a `match_labels`
map of at least one pair [Codebase: proto/private]. The hardware spec is:

| Field | Shape | Notes |
|-------|-------|-------|
| `cpu` | object | `cores`, `architecture`, `model`, `threads_per_core` |
| `memory` | object | `total_gb` (int64), `type` |
| `disks[]` | repeated object | `type`, `capacity_gb` (int64), `interface` |
| `accelerators[]` | repeated object | `type`, `model`, `vendor?`, `memory_gb?` |
| `network_ports[]` | repeated object | `name`, `role`, `type`, `speed` |
| `capabilities` | `map<string,string>` | freeform |
| `host_label_selector.match_labels` | `map<string,string>` | **private only**, ≥1 pair |

Hardware metadata is informational — the label selector, not the metadata,
governs which inventory hosts a type claims. Incorrect metadata is an admin
error, not a correctness or security risk [Locked: D2].

### Navigation and Routing

Admin surface — mirror the VM instance-type mount
[Codebase: apps/app-frontend/src/shell/InstanceTypeRoutes.tsx]:

- Add a `Bare Metal Instance Types` nav item under the existing admin
  `Infrastructure` section (`shellNav.ts`), guarded by a `providerAdmin`
  `RoleRoute` in `AppShell.tsx`.
- Add admin routes via a new `BareMetalInstanceTypeRoutes.tsx`:
  - `/admin/infrastructure/baremetal-instance-types` — list (index)
  - `/admin/infrastructure/baremetal-instance-types/create` — create
  - `/admin/infrastructure/baremetal-instance-types/:id` — detail
  - `/admin/infrastructure/baremetal-instance-types/:id/edit` — edit

No new tenant routes are added; the tenant surface is the existing
provisioning wizard.

### Admin List Page

- Columns: Name, CPU (cores + architecture), Memory (GiB), Accelerators
  (count, or `—`), Description.
- Row actions via `ActionsColumn`: `Edit`, `Delete`. **No lifecycle actions**
  [Locked: D1].
- Distinguish a failed list request (non-loading error state) from a
  successful empty result (empty state), following the existing list-page
  convention [Codebase: components/InstanceType].

### Admin Create / Edit Page

A single `OsacForm`-based form backing both create and edit. Create calls
the private `Create` RPC; edit loads the existing type and submits an update
with a field mask [Codebase: api/v1/private/instance-type.ts]. Fields:

- **Name** — shared `NameField` for `metadata.name` (RFC 1035 DNS-label
  validation, immutable on edit).
- **Description** — optional multiline input for `spec.description`.
- **CPU** `FormSection` — `cores` (required integer > 0), `architecture`,
  `model`, `threads_per_core` (optional integer > 0).
- **Memory** `FormSection` — `total_gb` (required integer > 0), `type`.
- **Disks** — repeatable group of `{ type, capacity_gb, interface }`;
  add/remove rows; `capacity_gb` a required integer > 0 within each row.
- **Accelerators** — repeatable group of
  `{ type, model, vendor?, memory_gb? }`; add/remove rows.
- **Network ports** — repeatable group of `{ name, role, type, speed }`;
  add/remove rows.
- **Capabilities** — key/value map editor for `capabilities` (add/remove
  pairs; keys unique and non-empty).
- **Host label selector** — key/value map editor for
  `host_label_selector.match_labels`; **required, at least one pair**
  [Codebase: proto/private]. This targets the private API and is never shown on
  tenant surfaces.

The repeatable groups and key/value map editors have no VM precedent and are
new shared building blocks. The form follows the existing interaction pattern:
submit stays enabled and clicking it surfaces schema validation errors rather
than pre-emptively disabling the action
[Codebase: components/InstanceType/CreatePage].

### Admin Detail Page

Read-only `DescriptionList` rendering of the full spec — CPU, memory, disks,
accelerators, network ports, capabilities, and the host label selector (admin
context only). No lifecycle metadata is shown; the resource has none
[Locked: D1].

### Tenant Wizard Selection (gated on `instance_type`)

Extend the BareMetal provisioning wizard's configuration step
[Codebase: components/catalogProvision/wizard/adapters/bareMetalInstance/BareMetalConfigurationStep.tsx]
with an instance-type `SelectField`, mirroring the VM wizard's
`VmConfigurationStep.tsx`:

- The catalog item and the instance type are **independent selections**: the
  wizard presents both controls, and choosing one does not filter the other.
  `catalog_item` remains its existing immutable field; `instance_type` is added
  alongside it [User].
- Populate options from the public `BareMetalInstanceTypes` list; each option
  label shows the type name plus a hardware **summary** (CPU cores, memory,
  accelerator count) so tenants discover and choose on capability, not an
  opaque string [PRD: FR-1, FR-3].
- On selection, render the selected type's **full** hardware spec (disks,
  network ports, capabilities, and the rest) inline so the tenant can review
  the requested hardware before submitting [PRD: FR-3].
- On selection, set `spec.instance_type` to the chosen type's
  `metadata.name` [PRD: FR-2].
- Selection is **mandatory**: the backend design specifies `min_len = 1` on
  `instance_type`, so the wizard must block submit until a type is chosen
  [design.md].
- The choice and its hardware summary appear in the wizard Review step.
- The tenant surface consumes only the public service, so the host label
  selector is never fetched or shown [Locked: D3].

This surface is **blocked** until `instance_type` is added to
`BareMetalInstanceSpec` and `@osac/types` is regenerated (`pnpm gen-types`)
[User]. It is decomposed as a separate, dependency-gated story that delivers
FR-1, FR-2, and FR-3 together in the UI.

## Field naming

Admin form and detail labels:

- `metadata.name` -> Name
- `spec.description` -> Description
- `spec.hardware.cpu.cores` -> CPU cores
- `spec.hardware.cpu.architecture` -> Architecture
- `spec.hardware.cpu.model` -> CPU model
- `spec.hardware.cpu.threads_per_core` -> Threads per core
- `spec.hardware.memory.total_gb` -> Memory (GiB)
- `spec.hardware.memory.type` -> Memory type
- `spec.hardware.disks[].type` / `.capacity_gb` / `.interface` -> Disk type / Capacity (GiB) / Interface
- `spec.hardware.accelerators[].type` / `.model` / `.vendor` / `.memory_gb` -> Accelerator type / Model / Vendor / Memory (GiB)
- `spec.hardware.network_ports[].name` / `.role` / `.type` / `.speed` -> Port name / Role / Type / Speed
- `spec.hardware.capabilities` -> Capabilities
- `spec.host_label_selector.match_labels` -> Host label selector (admin only)

Wizard:

- `spec.instance_type` (on `BareMetalInstance`) -> Instance type

## Security and RBAC

`BareMetalInstanceType` is a provider-defined resource. Create, edit, and
delete are restricted to Cloud Provider Admin users through the existing
private API and a `providerAdmin` `RoleRoute`; this design adds only a UI
client for those existing permissions [design.md Security].

The `host_label_selector` is structurally private: the public spec omits it
(`reserved 2`) and only the private spec defines it [Locked: D3]. The wizard
selector consumes only the public service, so it can never read or display the
selector. Types are globally visible — the public `List` returns all types to
any authenticated tenant [Locked: D4].

## Failure Handling

- The admin list-page fetch failure uses the shared non-loading error state,
  distinct from the successful empty-result state
  [Codebase: components/InstanceType].
- Create, edit, and delete failures surface as a dismissible inline alert at
  the top of the page, rendering the backend error message directly. Titles:
  - Create: `Failed to create bare metal instance type`
  - Edit: `Failed to update bare metal instance type`
  - Delete: `Failed to delete bare metal instance type`
- Invalid input is normally caught by schema validation before the request is
  sent. If the backend still returns field-specific validation errors, map
  them onto the matching field (including within repeatable-group rows) rather
  than only the top-level alert.
- Delete uses a `DeleteConfirmModal` before issuing the request.
- Wizard (gated story): if the type list fails to load, the step shows a
  non-loading error and blocks progression, since selection is mandatory.

## Test Plan

Vitest + RTL + jsdom; mock the Connect transport via `ApiProvider`
(`createMockConnectTransport`) — never mock fetch/REST. Cover
happy/loading/empty/error for each surface; use accessible queries, no
`data-testid` [Codebase: testing conventions].

- Unit-test the new public and private hooks (list, get, create, update with
  field mask, delete, query invalidation).
- Unit-test the admin list (loading/empty/error), including that a failed
  request is distinct from an empty result, and that no lifecycle actions are
  offered.
- Unit-test the admin create/edit form: required-integer validation (reject
  decimals/zero/negatives) for CPU cores, memory, accelerator's memory and disk capacity;
  add/remove for each repeatable group; capabilities and host-label-selector
  map editors, including the ≥1-pair requirement on the selector; conversion
  of validated numerics before the request body is built; backend field errors
  mapping onto the matching field/row.
- Unit-test (gated story) the wizard: options list available types with a
  hardware summary, mandatory selection blocks submit, the selected type's
  hardware renders inline and in Review, the correct `spec.instance_type`
  payload is built, and the host label selector is never fetched or shown.
- Unit-test the delete confirm-modal flow and list invalidation.
