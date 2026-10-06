# Catalog Items v2: UI Design

See the [PRD](prd.md) for product requirements and the [backend design](design.md) for the field governance model this UI authors against.

## Summary

This design covers the first UI iteration for authoring Catalog Items under the v2 field governance model, for `ComputeInstanceCatalogItem`, `ClusterCatalogItem`, and `BareMetalInstanceCatalogItem`: Create, Edit, Delete, Provisioning, and the Details page.

## Scope

**Personas:** Cloud Provider Admin (`admin` role) authoring shared Catalog Items, and Tenant Admin (`tenant-admin` role) authoring Catalog Items scoped to their own organization. Tenant User gets no new UI surface in this design, but provisioning is covered here (see [Provisioning](#provisioning-wizard)).

**In scope:** Create (wizard), Detail/Edit, Delete, and Publish/Unpublish actions. The List page's structure (`CatalogItemListSection`/`CatalogItemCard`/`CatalogItemTable`) already exists and is not rebuilt.

**Out of scope for this first iteration**

- `ssh_public_key`, pull secrets, `network_attachments` / `network_attachment`, and `auto_external_ip_attachment`. The first three require authoring-time resource pickers, and `auto_external_ip_attachment` belongs in the networking step; this iteration does not add that step for ComputeInstance or BareMetalInstance and does not expose the field in the Cluster networking step.
- Template parameter (`map<string, AnyField>`) governance. The Create wizard and edit view do not expose a step or section for template parameters in this iteration.
- Tenant User provisioning UI changes.


## Proposal

### Navigation and Routing

Create and Detail/Edit are new routes nested under `/catalog`, following the existing per-resource `Routes` pattern (e.g. `InstanceTypeRoutes.tsx`):

```text
/catalog/create  -> CatalogItemCreatePage
/catalog/:id     -> CatalogItemDetailPage (existing CatalogItemDetailPage, gains an Edit mode)
```

A single route pair serves both Cloud Provider Admin and Tenant Admin, scoped server-side by the caller's effective tenant — the same split already used for `CatalogItemTable`'s role-conditional columns. A "Create catalog item" primary action is added to the List page toolbar, visible only for `admin` and `tenant-admin`.

### List Page

No structural change: `CatalogItemListSection`, `CatalogItemCard`, and `CatalogItemTable` already exist and already serve `admin`/`tenant-admin`/`tenant-user` with role-appropriate columns (e.g. `CatalogItemTable`'s Visibility/Created columns for `admin`, Source/Added for `tenant-admin`). This design changes the following within that existing structure:

1. **Kebab menu actions** (`CatalogItemActionsMenu`, shared by `CatalogItemCard`'s header and `CatalogItemTable`'s action cell): add **Edit**, **Publish**/**Unpublish** (label depends on `item.published`), and **Delete**, visible for `admin` over any item and for `tenant-admin` over items in their own tenant (`item.metadata?.tenant` matches the caller's tenant). Delete opens a confirmation dialog stating that existing provisioned resources are unaffected (per [Failures](design.md#failures)). These sit alongside the existing "View details" item; "Launch instance" keeps showing only for `tenant-admin`/`tenant-user`, since Cloud Provider Admin doesn't provision from Catalog Items today.
2. **Resource type filter** (`CatalogServiceTierFilter`): change from a multi-select `ToggleGroup` to PatternFly's single-select `ToggleGroup` variant, so only one resource type (Bare Metal, Cluster, or VM) can be active at a time. This makes the resource type unambiguous when the admin clicks **Create catalog item**, since the wizard launches for the currently selected type.
3. **Remove resource type labels** from `CatalogItemCard` and `CatalogItemTable` — the resource type does not need to be repeated on each card or in a table column because the single-select resource-type `ToggleGroup` already makes the active type clear.

### Create/Edit Wizard

Each resource type has its own simple CatalogItem wizard, used for both Create and Edit. Define the steps directly through JSX composition, following the existing simple wizard pattern used by resources such as Secret, rather than sharing a central step registry or adapter-based step builder. In Edit mode, initialize the wizard from the existing CatalogItem and disable the name field; the CatalogItem name cannot be changed. The steps for each resource type are:

| Step | ComputeInstance | Cluster | BareMetalInstance |
|---|---|---|---|
| General | `tenant`/`project`, `name`, `description` | same | same |
| Configuration | `disk_image`, `instance_type`, `user_data`, `run_strategy` | `version`, `node_sets` | `instance_type`, `disk_image`, `user_data`, `run_strategy` |
| Storage | `boot_disk.size_gib`, `boot_disk.storage_tier`, `additional_disks` | — | — |
| Networking | *(omitted — only governable field here is `network_attachments`, out of scope)* | `network.pod_cidr`, `network.service_cidr` | — |
| Review | read-only summary | read-only summary | read-only summary |

All supported fields in the Configuration, Storage, and Networking steps reuse the corresponding form controls from the provisioning wizard, including Cluster's existing node-set control. The authoring form does not introduce alternate widgets for these fields. The Networking step is dropped entirely for ComputeInstance and BareMetalInstance in this iteration because their governable networking fields (`network_attachments` and `auto_external_ip_attachment`) are out of scope (see Scope). Cluster keeps a Networking step for `network.pod_cidr`/`network.service_cidr`, which are plain CIDR strings; `auto_external_ip_attachment` remains out of scope there as well.

The configuration forms reuse the provisioning wizard's existing field components and layout. Each governable field is rendered exactly as it is in the provisioning wizard, with one authoring-only addition:

- An **Editable** switch appears on the same line as the field label, aligned to the right. Off means the field is **Locked**: a value is required, and that value is what every provisioning resolves to. On means the field is **Editable**: a default value is optional, and the tenant may override it at provisioning time.
- Complex fields such as `node_sets` and `additional_disks` have one Editable switch for the entire field and its complete form control, not a separate switch for each nested item.
- The field-value component below the switch for entering the default value. It uses the appropriate shared control for the field type, such as a reference picker for `instance_type` or a typed input for `boot_disk.size_gib`.

A field the admin never touches stays ungoverned.

#### Resource selectors

Catalog Item resource selectors reuse the same searchable typeahead dropdowns as the provisioning wizard, with descriptive options following the UX prototype. Each dropdown option shows the resource name plus a short description of that resource; complex resources keep their existing provisioning-wizard controls. The only difference for authoring: Catalog Item resource selectors also include a **Not set** option, with its own description explaining that the tenant will choose the resource at provisioning time.

### Details Page

The current `CatalogItemDetailPage` is too sparse: it shows only a generic Details card and a flat list of configuration defaults. Redesign it using the existing `ResourceDetailsPage` pattern and the reference catalog UX in `/home/brotman/repos/osac-bmaas`.

The page has the following structure:

- **Resource header:** show the resource-type icon, Catalog Item name, description, breadcrumb back to Catalog, and page-level actions. Cloud Provider Admin sees **Edit**, **Publish**/**Unpublish**, and **Delete** as applicable. Tenant Admin sees **Edit**, **Publish**/**Unpublish**, and **Delete** as applicable for Catalog Items in their tenant, plus **Launch instance** when the item is published. Tenant User sees **Launch instance** for published items.
- **Overview:** show the status, created date and tenant
- **Configuration card:** show the complete type-specific configuration. Include the configured value or default for every governed field and a **Locked**/**Editable** indicator beside the field label. Omit fields that are not governed. Use the following type-specific content:
  - `ComputeInstance`: disk image, instance type, user data, run strategy, boot-disk size and storage tier, and additional disks.
  - `Cluster`: version and node sets, followed by the applicable network CIDRs.
  - `BareMetalInstance`: instance type, disk image, user data, and run strategy.

The Details page is read-only. **Edit** opens the same wizard structure used for Create, pre-populated from the Catalog Item. The edit form reuses the provisioning wizard's exact field components and layout, with the authoring-only Editable switch on the same line as each field label, aligned to the right. Existing provisioned resources are unaffected by edits, publish/unpublish, or deletion of the Catalog Item.

## Implementation details

### Wizard structure

The provisioning flow is refactored to use simple per-resource wizards, following the same structure as other resource wizards such as Instance Type and Secret. Remove the adapter pattern completely. Each resource (`ComputeInstance`, `Cluster`, and `BareMetalInstance`) owns its wizard steps, validation, payload construction, and submission flow directly. The CatalogItem and provisioning wizards keep separate step composition, while sharing the field components and initial-values functions described below.

`ssh_public_key` and `network_attachments`/`network_attachment` remain governable through the API even though the authoring UI does not expose them (see Scope). The provisioning wizard applies their CatalogItem values through the same shared field components, so API-authored CatalogItems with these fields governed still provision correctly. No new provisioning steps or fields are added.

### Form field architecture

The CatalogItem and provisioning wizards share two implementation pieces:

1. Resource-specific field components.
2. Resource-specific initial-values functions.

#### Shared field components

Each field has its own reusable component, such as `StorageTierSelectField`, `InstanceTypeField`, or `UserDataField`. Components that do not exist today should be added for fields that need them. A field component owns the field-specific control behavior: options, resource loading, descriptions, selection, validation, and Formik value updates. Its `FormGroup` is extracted out so the field can be rendered by either wizard wrapper without nested form groups.

All wizard form field values use the same structure. Resource selector values retain both the resource ID and name:

```ts
{ editable: boolean, value: <value> }
{ editable: boolean, value: { id: string, name: string } }
```

#### Shared initial-values functions

Each resource has a shared initial-values function that creates the Formik field-value structure before the wizard renders. For CatalogItem Create, it is called without a CatalogItem and returns empty values. For CatalogItem Edit and provisioning, it receives the CatalogItem and reads each field's configured value and `editable` state.

For example:

```ts
getComputeCatalogItemInitialValues(catalogItem)
getClusterCatalogItemInitialValues(catalogItem)
getBareMetalCatalogItemInitialValues(catalogItem)
```

#### CatalogItem wizard

The CatalogItem wizard composes its resource-specific steps from `CatalogField` wrappers around the shared field components. For CatalogItem Create, the wizard starts with empty Formik initial values. For CatalogItem Edit, the shared initial-values function receives the existing CatalogItem and initializes each field with its configured value and an `editable` boolean, for example:

```ts
{
  bootStorageTier: {
    editable: false,
    value: { id: 'premium-ssd', name: 'Premium SSD' },
  },
}
```

`CatalogField` receives the Formik field name, renders the surrounding `FormGroup`, and places the authoring-only **Editable** switch on the right side of the field label. It keeps the shared field component enabled for the CatalogItem author regardless of the switch state; the switch defines tenant behavior during later provisioning.

```tsx
<CatalogField name="bootStorageTier" label="Boot storage tier">
  <StorageTierSelectField />
</CatalogField>
```

#### Provisioning wizard

The provisioning wizard composes its resource-specific steps from `ProvisioningField` wrappers around the same shared field components. Its shared initial-values function receives the CatalogItem and creates the Formik values with each field's configured value and `editable` state. `ProvisioningField` receives the Formik field name and renders the `FormGroup` without the authoring switch. It applies the CatalogItem policy: `editable: false` makes the control disabled, while `editable: true` leaves it enabled and uses the CatalogItem value as an optional default. A disabled locked field does not need to be marked required because its value is already supplied by the CatalogItem.

```tsx
<ProvisioningField name="bootStorageTier" label="Boot storage tier">
  <StorageTierSelectField />
</ProvisioningField>
```

The field components and initial-values functions are shared; the wrappers provide wizard-specific presentation and policy behavior, while each wizard keeps its own step composition and submission flow.

### Additional details

- **Details page reuse:** Implement `CatalogItemDetailPage` by composing the shared `ResourceDetailsPage` component.
- Reuse `OsacForm`/Formik and shared field components already used by the application.
- Reuse `OsacFormFooter` for wizard navigation and submission; it also provides the shared form-level error handling and display behavior.
- Use the shared generic resource hooks for Catalog Item list, create, update, and delete operations rather than adding Catalog Item-specific CRUD hooks.

## Failure Handling

- **Create and update validation:** Use the existing Formik field validation for client-side errors and `OSACWizardFooter` for server errors. Server errors are shown in the footer's existing generic error message area on the final wizard step.
- **Unavailable references:** Reuse the existing resource-dropdown behavior. Resource-list failures show an inline error alert, and an empty resource list shows the existing warning with guidance to contact an administrator. Use this same behavior for CatalogItem resource selectors rather than adding a separate unavailable-reference flow.
- **Details-page loading and errors:** Reuse the shared resource-details pattern: show the standard loading skeleton while fetching, a retryable error state when loading fails, a not-found state when the CatalogItem does not exist, and the shared unauthorized state when access is denied.

## Test Plan

- Unit tests for the wizard cover Compute Instance, Cluster, and Bare Metal field controls, including Locked/Editable behavior, complex-field switches, and excluded fields.
- Unit tests for routes and actions cover Create, Details/Edit, Publish/Unpublish, Delete, and role-appropriate actions.

---
