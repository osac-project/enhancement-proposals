# Catalog Items v2: UI Design

See the [PRD](prd.md) for product requirements and the [backend design](design.md) for the field governance model this UI authors against.

## Summary

This design covers the first UI iteration for authoring Catalog Items under the v2 field governance model, for `ComputeInstanceCatalogItem`, `ClusterCatalogItem`, and `BareMetalInstanceCatalogItem`. The list/browse layer already exists and already reads the new typed `fields` policy (`libs/ui-components/src/components/catalog/`: `CatalogItemListSection`, `CatalogItemCard`, `CatalogItemTable`, `CatalogItemActionsMenu`, and the per-type `*CatalogItemResources` summaries, which already use `catalogFieldPolicyBehavior`/`CatalogFieldEditabilityLabel` to show Locked/Editable). What's missing is authoring: there is no Create, Edit, Delete, or Publish/Unpublish action anywhere yet — `CatalogItemActionsMenu` today only has "View details" and, for Tenant Admin/Tenant User, "Launch instance". This design adds those, a Create wizard, and a Detail/Edit page, and updates the per-type card/table summaries to show governance-relevant content for the admin personas. It also updates the existing tenant provisioning wizard to resolve field display from the new typed `fields` policy instead of the current `field_definitions`, which it still reads.

## Scope

**Personas:** Cloud Provider Admin (`admin` role) authoring shared Catalog Items, and Tenant Admin (`tenant-admin` role) authoring Catalog Items scoped to their own organization. Tenant User gets no new UI surface in this design, but their existing provisioning flow (`CatalogProvisionWizard`) is covered here because it must read the new typed `fields` shape instead of `field_definitions` to keep working (see [Provisioning](#provisioning)).

**In scope:** Create (wizard), Detail/Edit, Delete and Publish/Unpublish actions, the admin-facing content of the existing List page's cards and table rows, and the tenant provisioning wizard's field-resolution logic (display only — no new provisioning steps). The List page's structure (`CatalogItemListSection`/`CatalogItemCard`/`CatalogItemTable`) already exists and is not rebuilt.

**Out of scope for this first iteration** (per [Initial UI scope](design.md#initial-ui-scope) in the backend design):

- `ssh_public_key`, and `network_attachments` / `network_attachment`, on any of the ComputeInstance, Cluster, or BareMetalInstance field tables. These fields are supported by the backend policy model, but governing them requires picking a tenant-managed resource at authoring time — an SSH key for `ssh_public_key`, and a VirtualNetwork/Subnet for the network attachment fields — and this iteration does not add those pickers. Rather than offer a degraded lock-only control for these fields, the wizard does not expose them at all: an admin cannot govern them (locked or editable) through the UI in this iteration. They remain governable through the API directly.
- Template parameter (`map<string, AnyField>`) governance. The Create wizard and edit view do not expose a step or section for template parameters in this iteration.
- Tenant User provisioning UI changes.

All other governed fields in the [ComputeInstance](design.md#computeinstance), [Cluster](design.md#cluster), and [BareMetalInstance](design.md#baremetalinstance) tables are included, for both `locked` and `editable` behavior — including whole-reference fields such as `disk_image`, `instance_type`, `version`, and `pull_secret_secret`.

## Proposal

### Navigation and Routing

The existing `/catalog` route and nav entry (`getCatalogNav` in `apps/app-frontend/src/shell/shellNav.ts`) already lists Catalog Items for every role, including `admin` and `tenant-admin` — that's the List page referenced throughout this design. Create and Detail/Edit are new routes nested under it, following the existing per-resource `Routes` pattern (e.g. `InstanceTypeRoutes.tsx`):

```text
/catalog/create  -> CatalogItemCreatePage
/catalog/:id     -> CatalogItemDetailPage (existing CatalogItemDetailPage, gains an Edit mode)
```

A single route pair serves both Cloud Provider Admin and Tenant Admin, scoped server-side by the caller's effective tenant — the same split already used for `CatalogItemTable`'s role-conditional columns. A "Create catalog item" primary action is added to the List page toolbar, visible only for `admin` and `tenant-admin`.

### List Page

No structural change: `CatalogItemListSection`, `CatalogItemCard`, and `CatalogItemTable` already exist and already serve `admin`/`tenant-admin`/`tenant-user` with role-appropriate columns (e.g. `CatalogItemTable`'s Visibility/Created columns for `admin`, Source/Added for `tenant-admin`). This design changes two things within that existing structure:

1. **Kebab menu actions** (`CatalogItemActionsMenu`, shared by `CatalogItemCard`'s header and `CatalogItemTable`'s action cell): add **Edit**, **Publish**/**Unpublish** (label depends on `item.published`), and **Delete**, visible for `admin` over any item and for `tenant-admin` over items in their own tenant (`item.metadata?.tenant` matches the caller's tenant). Delete opens a confirmation dialog stating that existing provisioned resources are unaffected (per [Failures](design.md#failures)). These sit alongside the existing "View details" item; "Launch instance" keeps showing only for `tenant-admin`/`tenant-user`, since Cloud Provider Admin doesn't provision from Catalog Items today.
2. **Card/table detail content**: today's per-type summaries (`ComputeCatalogItemResources`, `ClusterCatalogItemResources`, `BareMetalCatalogItemResources`) show a tenant-browsing-oriented subset — e.g. Compute shows only vCPU, Memory, Storage, and Disk image. For `admin`/`tenant-admin`, replace that subset with the full set of fields this iteration can govern (see Scope), each still paired with the existing `CatalogFieldEditabilityLabel` Locked/Editable badge, so an admin can see everything they configured — including fields with no tenant-facing hardware analog, such as `run_strategy`, `user_data`, and `auto_external_ip_attachment`. `tenant-user` keeps the current curated subset unchanged.

### Create Page

The Create wizard reuses the same step breakdown as the existing tenant provisioning wizard (`getWizardOrderedSteps` in `catalogProvision/wizard/stepIds.ts`) for the selected resource type, minus the `catalog` step (authoring defines the item; it does not select one) and minus the fields excluded from this iteration:

| Step | ComputeInstance | Cluster | BareMetalInstance |
|---|---|---|---|
| General | `name`, `description`, `tenant`/`project` | same | same |
| Configuration | `instance_type`, `user_data`, `run_strategy` | `version`, `pull_secret_secret` | `run_strategy`, `image` |
| Storage | `boot_disk.size_gib` | — | — |
| Networking | *(omitted — only governable field here is `network_attachments`, out of scope)* | `network.pod_cidr`, `network.service_cidr` | — |
| Review | read-only summary | read-only summary | read-only summary |

Cluster's `node_sets` map is governed as part of Configuration, one row per Template-defined node set. The Networking step is dropped entirely for ComputeInstance and BareMetalInstance in this iteration because their only governable networking field is `network_attachments`, which is out of scope (see Scope); Cluster keeps a Networking step because `network.pod_cidr`/`network.service_cidr` are plain CIDR strings, not resource pickers.

Each governable field is rendered as a row with:

- An **Editable** switch at the top of the row. Off means the field is **Locked**: a value is required, and that value is what every provisioning resolves to. On means the field is **Editable**: a default value is optional, and the tenant may override it at provisioning time.
- A field-appropriate input below the switch for entering that value or default (reference picker for whole-reference fields such as `instance_type`, typed input for scalars such as `boot_disk.size_gib`).

A field the admin never touches stays ungoverned (`fields.<name>` absent from the request), identical to today's "field not in `field_definitions`" behavior.

### Detail/Edit Page

`CatalogItemDetailPage` already exists for viewing; this design adds an Edit mode reusing the Create wizard's per-field rows (Editable switch, value/default input) pre-populated from the item, plus the same **Edit**/**Publish**/**Unpublish**/**Delete** actions as the List page's kebab menu, placed as page-level actions for when an admin navigates in via "View details" instead of the kebab.

### Provisioning

`CatalogProvisionWizard` already resolves a per-field overlay from the Catalog Item and applies it uniformly — `getCatalogFieldOverlay` in `catalogProvision/wizard/catalogOverlay.ts` returns `{ editable, defaultValue }`, and step components consume it as a prefilled value plus `isDisabled={!overlay.editable}` (e.g. `VmStorageStep.tsx`'s boot-disk and storage-tier fields). This design keeps that pattern and updates its source of truth:

- `catalogOverlay.ts` resolves the overlay from the new typed `fields` (`locked`/`editable` policy, per [Policy model](design.md#policy-model)) instead of the freeform `field_definitions` list. The resolved shape consumers see (`editable`, `defaultValue`) is unchanged, so step components such as `VmStorageStep` and `VmConfigurationStep` need no behavior change beyond reading the new resolver.
- A **Locked** field renders prefilled with the Catalog Item's locked value and disabled, exactly as today's `isDisabled={!overlay.editable}` fields — the tenant cannot change it, consistent with [Tenant UI](design.md#tenant-ui) in the backend design.
- An **Editable** field with a default renders prefilled with that default and enabled; an Editable field with no default renders empty and enabled.
- `ssh_public_key` and `network_attachments`/`network_attachment` are governable through the API even though the authoring UI does not expose them (see Scope). The provisioning wizard still applies the same overlay to these fields — `VmGeneralStep`'s `SshKeyField` and `VmNetworkingStep`'s network fields render locked/prefilled exactly like any other overlaid field — so a Catalog Item authored via the API with these fields governed still provisions correctly through the UI.
- No new provisioning steps or fields are added; this is a resolver swap behind the existing overlay contract.

## Field naming

Field labels in the UI match the proto field names in Title Case with their resource-appropriate unit, consistent with existing resource forms (e.g. `Boot disk size (GiB)` for `boot_disk.size_gib`). The per-field switch is labeled **Editable**; its two states are presented as **Locked** (switch off, value required) and **Editable** (switch on, default value optional), matching the backend design's terminology rather than introducing UI-only synonyms. A field the admin leaves untouched is ungoverned and shows no switch state.

## Implementation details

- Reuse `OsacForm`/Formik conventions and shared field components (`NameField`, `InputField`) already used by other admin create pages rather than generating a form from the proto schema, consistent with [Authoring UI](design.md#authoring-ui) in the backend design ("the UI owns field labels, sections, order, help text, and widgets").
- Add new hooks for Catalog Item CRUD (e.g. `useCreateCatalogItem`, `useCatalogItems`) distinct from the existing tenant-facing `catalogProvision` hooks, since those serve a different (read/provision) use case against the current `field_definitions` shape.
- Reference pickers for `disk_image`, `instance_type`, `version`, and `pull_secret_secret` reuse the existing resource-picker components already used elsewhere in the app for those resource types, rather than new one-off pickers.

## Security and RBAC

The UI is not a security boundary; the server enforces scope and locked-field rejection (per [Security](design.md#security) in the backend design). The UI hides actions a role cannot perform (e.g. a Tenant Admin never sees another tenant's items, and never sees a "shared" toggle), but authorization is re-checked server-side.

## Failure Handling

Create/Update surface server validation errors inline on the relevant wizard step or field (mapping the `InvalidArgument` conditions in [Failures](design.md#failures) back to the field that caused them) rather than a single generic banner. A referenced object becoming unavailable after authoring (`FailedPrecondition`) is surfaced as a banner on the Detail page prompting the admin to re-select the field's value.

## Test Plan

- Unit tests for the wizard step components per resource type (Compute/Cluster/Bare Metal), covering the Editable switch's two states per field (Locked requires a value, Editable makes the default optional) and that an untouched field stays ungoverned.
- Unit tests confirming `ssh_public_key` and `network_attachments`/`network_attachment` render nowhere in the wizard (not even as a Locked-only control) for any resource type, and that the wizard omits a template-parameter step.
- Route tests for `/catalog/create` and `/catalog/:id` (including edit mode), mirroring `InstanceTypeRoutes.test.tsx`.
- Unit tests for `CatalogItemActionsMenu` confirming Edit/Publish/Unpublish/Delete appear only for `admin` (any item) and `tenant-admin` (own-tenant items only), and that "Launch instance" is unaffected.
- Unit tests for the per-type card/table summaries confirming `admin`/`tenant-admin` see the full governed-field set while `tenant-user` keeps today's curated subset.
- Unit tests for the updated `catalogOverlay.ts` resolver against the new `fields` policy shape: a Locked field resolves disabled and prefilled with the locked value; an Editable field with a default resolves enabled and prefilled; an Editable field without a default resolves enabled and empty.
- Regression tests on `VmGeneralStep`/`VmNetworkingStep` confirming `ssh_public_key` and network-attachment fields still render correctly disabled/prefilled when governed via the API, even though the authoring UI cannot set them.
- E2E coverage tracked separately per the PRD's Definition of Done.
