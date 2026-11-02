# Catalog Items v2: UI Design

See the [PRD](prd.md) for product requirements and the [backend design](design.md) for the field governance model this UI authors against.

## Summary

This design covers the first UI iteration for authoring Catalog Items under the v2 field governance model, for `ComputeInstanceCatalogItem`, `ClusterCatalogItem`, and `BareMetalInstanceCatalogItem`: Create, Edit, Delete, Provisioning, and the Details page. User data authoring supports either inline cloud-init content or a typed `USER_DATA` Secret reference, with the available Secret scope determined by the creator persona.

## Scope

**Personas:** Cloud Provider Admin (`admin` role) authoring shared Catalog Items, and Tenant Admin (`tenant-admin` role) authoring Catalog Items scoped to their own organization. Tenant User gets no new UI surface in this design, but provisioning is covered here (see [Provisioning](#provisioning-wizard)).

**In scope:** Create (wizard), Detail/Edit, Delete, and Publish/Unpublish actions. The List page's structure (`CatalogItemListSection`/`CatalogItemCard`/`CatalogItemTable`) already exists and is not rebuilt.

**Out of scope for this first iteration**

- `ssh_public_key`, pull secrets, `network_attachments` / `network_attachment`, and `auto_external_ip_attachment`. The first three require authoring-time resource pickers, and `auto_external_ip_attachment` belongs in the networking step; this iteration does not add that step for ComputeInstance or BareMetalInstance and does not expose the field in the Cluster networking step.
- Template parameter (`map<string, AnyField>`) governance. The Create wizard and edit view do not expose a step or section for template parameters in this iteration.
- Tenant User provisioning UI changes.


## Proposal

### Navigation and Routing

Create and Detail/Edit are new routes nested under `/catalog`, following the existing per-resource `Routes` pattern (e.g. `InstanceTypeRoutes.tsx`). The path includes the catalog item kind so the page queries the matching typed API:

```text
/catalog/(vm|bm|cluster)/create -> CatalogItemCreatePage
/catalog/(vm|bm|cluster)/:id    -> CatalogItemDetailPage (existing CatalogItemDetailPage, gains an Edit mode)
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

#### User data source selection

`user_data` is presented as a single governed field whose value is a source choice, not only a text scalar. The field reuses the provisioning wizard's `UserDataField` interaction: **Enter value** shows the multiline cloud-init input, and **Select secret** shows a Secret selector. The Editable switch applies to the complete source choice and its value; it is not duplicated for inline content and the Secret reference.

The Secret selector is filtered by the creator persona and always restricts results to `SecretType.USER_DATA`:

- **Cloud Provider Admin:** list Secrets in the shared tenant. This is the selector used when the provider configures a shared user-data Secret for a Catalog Item.
- **Tenant Admin:** list Secrets in the selected Catalog Item project. The selected project is the scope input from the General step; changing it clears the selected Secret and reloads the options so a reference from the previous project cannot be submitted.

The selector displays Secret metadata such as the name, never Secret data. If no project is selected for a Tenant Admin, the selector is disabled with guidance to select a project first. Existing inline content and Secret references are both preserved when an item is opened for Edit. A locked field requires a source value; an editable field may omit its default.

#### Resource selectors

Catalog Item resource selectors reuse the same searchable typeahead dropdowns as the provisioning wizard, with descriptive options following the UX prototype. Each dropdown option shows the resource name plus a short description of that resource; complex resources keep their existing provisioning-wizard controls. The only difference for authoring: Catalog Item resource selectors also include a **Not set** option, with its own description explaining that the tenant will choose the resource at provisioning time.

The user-data Secret selector follows the existing `SecretSelectionField` loading, empty, and error behavior, but supplies the persona-aware `Secrets.List` filter described above. It is not a generic resource selector: Secret data is never loaded into the form.

### Details Page

`CatalogItemDetailPage` uses this layout:

- **Resource header:** show the resource-type icon, Catalog Item name, description, breadcrumb back to Catalog, and page-level actions. Cloud Provider Admin sees **Edit**, **Publish**/**Unpublish**, and **Delete** as applicable. Tenant Admin sees **Edit**, **Publish**/**Unpublish**, and **Delete** as applicable for Catalog Items in their tenant, plus **Launch instance** when the item is published. Tenant User sees **Launch instance** for published items.
- **Overview:** show the status, created date and tenant
- **Configuration card:** show the complete type-specific configuration. Include the configured value or default for every governed field and a **Locked**/**Editable** indicator beside the field label. Omit fields that are not governed. Use the following type-specific content:
  - `ComputeInstance`: disk image, instance type, user data, run strategy, boot-disk size and storage tier, and additional disks. Inline user data shows **Configured** as an expandable value; expanding it reveals the configured text. Secret-backed user data shows the Secret name as a link to `/secrets/{secret.id}` and never exposes Secret data in the Catalog Item details page.
  - `Cluster`: version and node sets, followed by the applicable network CIDRs.
  - `BareMetalInstance`: instance type, disk image, user data, and run strategy. Inline user data shows **Configured** as an expandable value; expanding it reveals the configured text. Secret-backed user data shows the Secret name as a link to `/secrets/{secret.id}` and never exposes Secret data in the Catalog Item details page.

For user data, `CatalogUserDataDetailValue` branches on the source type. Inline content uses PatternFly's `ExpandableSection`, with an accessible toggle that changes between expanding and collapsing the configured text. A Secret-backed value uses the existing resource-name link pattern and navigates to the Secret details route (`/secrets/{secret.id}`). The link label is `metadata.name`; the Catalog Item response must provide the canonical Secret `id` and name. If an old or incomplete reference has no ID, render the name as plain text and do not construct a URL from the name.

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

`UserDataField` owns the inline-versus-Secret source cards and delegates Secret listing to `SecretSelectionField`. Catalog Item authoring supplies a persona-aware Secret scope, while provisioning supplies the workload project scope. The field must accept the selected project and the current source value as inputs so that it can clear stale project-local selections and preselect an existing Secret reference during Edit.

All wizard form field values use the same structure. Resource selector values retain both the resource ID and name:

```ts
{ editable: boolean, value: <value> }
{ editable: boolean, value: { id: string, name: string } }
```

User data uses a discriminated value so the form never converts a Secret-backed value into empty inline text:

```ts
type CatalogUserDataValue =
  | { source: 'inline'; value: string }
  | { source: 'secret'; value: { id: string; name: string } };

{ editable: boolean, value: CatalogUserDataValue }
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
  {({ valueName, isDisabled }) => (
    <StorageTierSelectField
      name={valueName}
      isDisabled={isDisabled}
    />
  )}
</CatalogField>
```

For user data, the wrapper also passes the creator persona and the selected project to `UserDataField`. The payload builder encodes the selected source as `UserDataSource.inline` or `UserDataSource.secret` inside the locked or editable policy arm. It omits an ungoverned field and permits an editable policy without a default.

#### Provisioning wizard

The provisioning wizard composes its resource-specific steps from `ProvisioningField` wrappers around the same shared field components. Its shared initial-values function receives the CatalogItem and creates the Formik values with each field's configured value and `editable` state. `ProvisioningField` receives the Formik field name and renders the `FormGroup` without the authoring switch. It applies the CatalogItem policy: `editable: false` makes the control disabled, while `editable: true` leaves it enabled and uses the CatalogItem value as an optional default. A disabled locked field does not need to be marked required because its value is already supplied by the CatalogItem.

```tsx
<ProvisioningField name="bootStorageTier" label="Boot storage tier">
  {({ valueName, isDisabled }) => (
    <StorageTierSelectField
      name={valueName}
      isDisabled={isDisabled}
    />
  )}
</ProvisioningField>
```

The field components and initial-values functions are shared; the wrappers provide wizard-specific presentation and policy behavior, while each wizard keeps its own step composition and submission flow.

### User data Secret data flow

The authoring UI reads only Secret metadata through the existing private API:

| UI state | API request | Filter | Returned fields | Behavior |
|---|---|---|---|---|
| Cloud Provider Admin selecting a shared Secret | `GET /api/private/v1/secrets` | `metadata.tenant == 'shared' && type == SECRET_TYPE_USER_DATA` | `id`, `metadata.name`, `metadata.tenant`, `metadata.project`, `type` | Populate the Secret selector; never request or display `data`. |
| Tenant Admin selecting a project Secret | `GET /api/private/v1/secrets` | `metadata.project == selectedProject && type == SECRET_TYPE_USER_DATA` | `id`, `metadata.name`, `metadata.tenant`, `metadata.project`, `type` | Refetch after project changes and clear a stale selection. |
| Details page rendering a Secret-backed value | Catalog Item GET response already required by the page | none | canonical Secret `id` and `metadata.name` from the stored reference | Render the Secret name as a link to `/secrets/{id}`; do not make a Secret-data request. |

The API's normal authorization remains authoritative; the UI does not broaden Secret visibility. The selected reference is stored in the Catalog Item policy, while the Secret contents remain server-side.

**API alignment required:** the current `UserDataSource.secret` contract uses `SecretLocalReference`, and the current fulfillment validation rejects references resolved in the shared tenant. The Cloud Provider Admin behavior above therefore requires the backend contract to permit a shared `USER_DATA` Secret reference, or to introduce an equivalent reference shape. This is an API gap for `/review-api` and must be resolved before the shared-Secret path is considered implementable.

### Additional details

- **Details page reuse:** Implement `CatalogItemDetailPage` by composing the shared `ResourceDetailsPage` component.
- **User data details:** Keep the source-aware rendering in `CatalogUserDataDetailValue`: inline values use an expandable **Configured** toggle, while Secret references use the existing resource-name link pattern to `/secrets/{id}`. The details page does not fetch or render Secret data.
- **Accessibility:** The inline toggle must be keyboard operable and expose expand/collapse state through its accessible label. Secret links use the Secret name as their accessible link text and remain normal in-app navigation links.
- Reuse `OsacForm`/Formik and shared field components already used by the application.
- Reuse `OsacFormFooter` for wizard navigation and submission; it also provides the shared form-level error handling and display behavior.
- Use the shared generic resource hooks for Catalog Item list, create, update, and delete operations rather than adding Catalog Item-specific CRUD hooks.

## Failure Handling

- **Create and update validation:** Use the existing Formik field validation for client-side errors and `OSACWizardFooter` for server errors. Server errors are shown in the footer's existing generic error message area on the final wizard step.
- **Unavailable references:** Reuse the existing resource-dropdown behavior. Resource-list failures show an inline error alert, and an empty resource list shows the existing warning with guidance to contact an administrator. Use this same behavior for CatalogItem resource selectors rather than adding a separate unavailable-reference flow.
- **User-data Secret selection:** Secret-list failures show the existing inline error alert. An empty filtered list shows the existing no-secret state. Tenant Admins cannot open the selector until a project is selected; changing the project clears the old Secret before fetching the new list.
- **Details-page loading and errors:** Reuse the shared resource-details pattern: show the standard loading skeleton while fetching, a retryable error state when loading fails, a not-found state when the CatalogItem does not exist, and the shared unauthorized state when access is denied.

## Test Plan

- Unit tests for the wizard cover Compute Instance, Cluster, and Bare Metal field controls, including Locked/Editable behavior, complex-field switches, and excluded fields.
- User-data tests cover inline versus Secret source selection, `USER_DATA` filtering for Cloud Provider Admins, project filtering for Tenant Admins, clearing a stale Secret when the project changes, loading an existing Secret reference in Edit mode, and encoding both source variants in locked and editable payloads.
- Details-page user-data tests verify that inline content renders as **Configured**, expands and collapses to show the text, and that Secret-backed content renders the Secret name as a link to `/secrets/{id}` without rendering or requesting Secret data. A reference without an ID renders as non-linked text.
- Secret-list tests verify that only metadata is rendered and that Secret data is never requested or displayed. Backend/API contract coverage must verify the shared-Secret behavior before enabling the Cloud Provider Admin path.
- Unit tests for routes and actions cover Create, Details/Edit, Publish/Unpublish, Delete, and role-appropriate actions.

---

---

## Provenance

Authored: revise @ ui-design 0.1.0 - 7b2b8de, workspace OSAC-6054-catalog-item-authoring @ 3a4b7cccd (7 behind origin/main)
Phases: revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"7b2b8de","source_repo":"3a4b7cccd","source_repo_branch":"OSAC-6054-catalog-item-authoring","commits_behind_main":7,"commits_ahead_main":89,"main_ref":"main","phases":["revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
