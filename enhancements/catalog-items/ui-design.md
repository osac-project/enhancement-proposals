---
title: catalog-items-ui
authors:
  - eaharoni
creation-date: 2026-07-16
last-updated: 2026-07-16
tracking-link:
  - https://github.com/osac-project/enhancement-proposals/pull/115
prd:
  - "README.md"
see-also:
  - "/enhancements/catalog-items"
  - "/enhancements/cluster-and-vm-provisioning-wizard"
replaces:
superseded-by:
---

# Catalog Items — UI Management

## Summary

This design adds admin management screens to osac-ui for creating, editing, publishing, and deleting catalog items across all three resource types (Cluster, ComputeInstance, BareMetalInstance). It introduces role-gated navigation, a field definitions editor component, and role-differentiated list/create/edit/detail pages for Cloud Provider Admins and Tenant Admins. See the [catalog items EP](https://github.com/osac-project/enhancement-proposals/pull/115) for API and data model requirements.

## Motivation

The catalog items API is fully implemented in fulfillment-service with CRUD endpoints for all three resource types. The existing osac-ui has a tenant-facing CatalogPage for browsing published items and a CatalogProvisionWizard for provisioning resources. However, there is no admin interface for managing catalog items — admins currently have no way to create, edit, publish/unpublish, or delete catalog items through the UI. Additionally, osac-ui has never implemented role-gated navigation; all users see the same sidebar and routes regardless of their role.

This design addresses both gaps: it establishes the admin navigation pattern that future admin features will follow, and it builds the catalog management pages needed for the catalog items feature to be usable end-to-end through the UI.

### Goals

- Reuse existing osac-ui patterns (ListPage, OsacForm, Formik + Yup, TanStack React Query hooks, PatternFly table/kebab actions) wherever possible. [Codebase: libs/ui-components/]
- Establish a role-gated navigation pattern using the existing `navRowsForRole()` function and `useSession()` hook that future admin features can follow.
- Use a single polymorphic component set for all three catalog item types (Cluster, ComputeInstance, BareMetalInstance) rather than separate implementations per type.
- Support the Tenant Admin "further restrict" create flow where field definitions are pre-populated from a global catalog item and can only be made more restrictive.

### Non-Goals

- Drag-and-drop reordering of field definitions. Field order is set by the admin during creation and edited via move-up/move-down buttons.
- Full visual JSON Schema editor (e.g., JSONJoy, react-json-schema-form-builder) or raw JSON Schema text editing. All validation constraints are configured through dedicated structured form controls.
- Changes to the existing CatalogProvisionWizard — that component already handles catalog items. Any alignment changes are tracked separately.
- Private API access from the UI. All catalog management uses the public fulfillment API via the Go proxy.

## Proposal

The design adds four new page types under a new "Administration > Catalog Management" sidebar section: a list page, a create page, an edit page, and a detail page. These pages are visible only to `providerAdmin` and `tenantAdmin` roles. The list page shows a PatternFly table with type filter, search, scope badges, and kebab row actions (edit, publish/unpublish, delete). The create page is a full-page form with sections for general information, template or base catalog item selection (role-dependent), and a field definitions editor. The edit page reuses the same form with the template/base selection locked. The detail page shows read-only configuration, field definitions, and related provisioned resources.

A new `FieldDefinitionsEditor` component built on Formik FieldArray provides the repeatable list UI for configuring field definitions. Each entry includes path selection (from template parameters or manual input), display name, an editable toggle, a default value input, and a structured validation constraints form.

### Workflow Description

#### Cloud Provider Admin — Create Catalog Item

1. CSP Admin navigates to **Administration > Catalog Management** in the sidebar.
2. The list page shows all catalog items across all tenants with a "Create catalog item" button.
3. CSP Admin clicks "Create catalog item" and lands on the create page.
4. **General section:** Admin enters title, description (Markdown), selects resource type (Cluster, VM, Bare Metal), and selects scope (Global or a specific tenant).
5. **Template section:** Based on the selected resource type, the admin selects a template from a dropdown populated by the corresponding template list endpoint (e.g., `GET /v1/cluster_templates`).
6. **Field definitions section:** After selecting a template, the admin configures field definitions using the `FieldDefinitionsEditor`. For each field:
   - Select a path from template parameters or type a dot-notation path manually
   - Enter an optional display name
   - Toggle editable on/off
   - Set an optional default value (required for non-editable fields)
   - Optionally configure validation constraints using structured form controls (numeric bounds, allowed values, string length, pattern, item count, resource references, nested properties)
7. Admin clicks "Create". The UI sends a POST to the appropriate catalog item endpoint with `published: false` (default).
8. The admin is redirected to the detail page for the newly created catalog item.
9. From the detail page or list page, the admin can publish the item via the kebab menu "Publish" action.

#### Cloud Provider Admin — Edit, Publish/Unpublish, Delete

- **Edit:** From the list page kebab menu or detail page, click "Edit". The edit page loads the existing catalog item data. Template selection is locked (displayed as read-only text). All other fields are editable. Save sends a PATCH with a FieldMask containing only changed fields.
- **Publish/Unpublish:** From the list page kebab menu, click "Publish" (if unpublished) or "Unpublish" (if published). This sends a PATCH with `published: true/false` and `update_mask: "published"`.
- **Delete:** From the list page kebab menu, click "Delete". A confirmation modal appears. If the catalog item has provisioned resources, the API returns an error and the UI displays an alert: "This catalog item cannot be deleted because resources have been provisioned from it. Unpublish it instead to hide it from users."

#### Tenant Admin — Create Catalog Item

1. Tenant Admin navigates to **Administration > Catalog Management**.
2. The list page shows the tenant's catalog items alongside global items. Global items have a "Global" scope badge and no edit/delete actions in the kebab menu. Org-scoped items have an "Organization" scope badge and full actions.
3. Tenant Admin clicks "Create catalog item".
4. **General section:** Admin enters title, description, and selects resource type. Scope is automatically set to the tenant's organization (not editable).
5. **Base catalog item section:** Instead of a template selector, the admin selects a published global catalog item of the selected resource type. The UI fetches the base item's field definitions.
6. **Field definitions section:** The `FieldDefinitionsEditor` is pre-populated with the base item's field definitions. The admin can:
   - Change editable fields to non-editable (but not the reverse — the toggle is disabled for fields already marked non-editable in the base)
   - Change or tighten default values for editable fields
   - Add or tighten validation constraints (cannot remove or loosen constraints from the base)
   - Change display names
   - Cannot add new fields or change paths
7. Admin clicks "Create". The UI sends a POST. The server auto-sets the `tenant` field.
8. The admin is redirected to the detail page.

#### Tenant User — Browse and Provision

No changes to the existing flow. Tenant Users continue to use the CatalogPage for browsing and the CatalogProvisionWizard for provisioning. The "Administration" nav section is not visible to Tenant Users.

### API Extensions

This design introduces no new API extensions. All catalog item CRUD endpoints already exist in fulfillment-service. The UI consumes the existing public API via the Go proxy:

- `GET/POST/PATCH/DELETE /api/fulfillment/v1/cluster_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/v1/compute_instance_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/v1/baremetal_instance_catalog_items`
- `GET /api/fulfillment/v1/cluster_templates` (read-only, for template selection)
- `GET /api/fulfillment/v1/compute_instance_templates` (read-only)
- `GET /api/fulfillment/v1/baremetal_instance_templates` (read-only)

### Implementation Details/Notes/Constraints

#### 1. Navigation and Routing Changes

**File: `apps/app-frontend/src/shell/shellNav.ts`**

The `navRowsForRole()` function gains role-conditional logic:

```typescript
export function navRowsForRole(role: DemoShellRole, t: TFunction): NavRow[] {
  const rows: NavRow[] = [
    // existing Services section (unchanged)
    { type: 'section', label: t('Services'), id: 'services' },
    { type: 'item', label: t('Catalog'), id: 'catalog', path: '/catalog' },
    // ... existing items ...

    // existing Networking section (unchanged)
    { type: 'section', label: t('Networking'), id: 'networking' },
    // ... existing items ...
  ];

  if (role === 'providerAdmin' || role === 'tenantAdmin') {
    rows.push(
      { type: 'section', label: t('Administration'), id: 'administration' },
      { type: 'item', label: t('Catalog management'), id: 'catalog-management', path: '/admin/catalog' },
    );
  }

  return rows;
}
```

**File: `apps/app-frontend/src/shell/AppShell.tsx`**

New routes for admin pages:

```
/admin/catalog               → CatalogManagementListPage
/admin/catalog/create         → CatalogItemCreatePage
/admin/catalog/:type/:id      → CatalogItemDetailPage
/admin/catalog/:type/:id/edit → CatalogItemEditPage
```

The `:type` parameter is one of `cluster`, `compute-instance`, or `baremetal-instance`, mapping to the correct API endpoint. This avoids ID collision across types.

A route guard component `AdminRoute` wraps admin pages and redirects `tenantUser` to `/catalog` (the default route).

**File: `libs/ui-components/src/icons.tsx`**

Add an icon mapping for the `catalog-management` nav item ID (e.g., `CogIcon` or `CatalogIcon` from PatternFly icons).

#### 2. Catalog Item Type Abstraction

To avoid tripling the UI code for three nearly identical resource types, a type-keyed configuration map drives all polymorphic behavior:

```typescript
type CatalogItemKind = 'cluster' | 'compute-instance' | 'baremetal-instance';

interface CatalogItemKindConfig {
  apiRoute: ApiRoute;
  templateApiRoute: ApiRoute;
  label: string;                    // e.g., "Cluster"
  pluralLabel: string;              // e.g., "Clusters"
  protoSchema: GenericSchema;       // @osac/types schema for decode
  templateProtoSchema: GenericSchema;
}

const CATALOG_ITEM_KINDS: Record<CatalogItemKind, CatalogItemKindConfig> = {
  'cluster': {
    apiRoute: 'v1/cluster_catalog_items',
    templateApiRoute: 'v1/cluster_templates',
    label: 'Cluster',
    pluralLabel: 'Clusters',
    protoSchema: ClusterCatalogItemSchema,
    templateProtoSchema: ClusterTemplateSchema,
  },
  'compute-instance': { /* ... */ },
  'baremetal-instance': { /* ... */ },
};
```

All pages and hooks reference this config rather than hardcoding resource-specific logic.

#### 3. API Hooks

New hooks in `libs/ui-components/src/api/v1/`:

**`catalog-item-admin.ts`** — Admin-specific hooks that aggregate all three types:

```typescript
// Fetches all catalog items across all three types, merging results
function useAllCatalogItems(): UseQueryResult<CatalogItemWithKind[]>

// Mutations per kind
function useCreateCatalogItem(kind: CatalogItemKind): UseMutationResult
function useUpdateCatalogItem(kind: CatalogItemKind): UseMutationResult
function useDeleteCatalogItem(kind: CatalogItemKind): UseMutationResult
```

The `useAllCatalogItems` hook fires three parallel queries (one per kind) and merges results into a unified list with a `kind` discriminator. Each item is tagged with its `CatalogItemKind` so the list page can route to the correct detail/edit URLs and the correct API endpoint for mutations.

The update hook builds the `update_mask` FieldMask from the diff between original and modified values. The publish/unpublish action is a specialized update that sends only `{ published: true/false }` with `update_mask: "published"`.

#### 4. List Page (`CatalogManagementListPage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogManagementListPage.tsx`

Uses `ListPage` + `ListPageBody` layout with a PatternFly `Table`.

**Toolbar:**
- "Create catalog item" primary action button
- Type filter: toggle group with All / Cluster / VM / Bare Metal
- Search: text input filtering by title and description (client-side)
- Publication status filter: All / Published / Unpublished

**Table columns:**

| Column | Content |
|--------|---------|
| Title | Catalog item title as a link to the detail page |
| Type | Resource type badge (Cluster / VM / Bare Metal) |
| Template | Name of the backing template |
| Scope | "Global" badge or organization name badge (see § Scope Display) |
| Status | "Published" (green) or "Unpublished" (gray) label |
| Actions | Kebab menu |

**Kebab menu actions (per role):**

| Action | providerAdmin | tenantAdmin (org-scoped) | tenantAdmin (global) |
|--------|---------------|--------------------------|----------------------|
| Edit | Yes | Yes | No |
| Publish | Yes (if unpublished) | Yes (if unpublished) | No |
| Unpublish | Yes (if published) | Yes (if published) | No |
| Delete | Yes | Yes | No |

Tenant Admin sees global items as read-only rows with no kebab menu (or a kebab with only "View details").

**Scope display:** The public API does not include the `tenant` field in responses. To display scope, the UI uses the following heuristic:
- If the caller is a Tenant Admin, items they can edit are org-scoped; items they cannot edit (no Update/Delete actions available — the server returns permission errors) are global. The list page can attempt a lightweight approach: items in the caller's tenant are fetched via the standard list (which returns both global and tenant-scoped items). The UI marks items as "Organization" if the caller has write permissions (determined by the presence of the item's metadata indicating the caller's tenant created it), and "Global" otherwise.
- If the caller is a CSP Admin, scope can be derived from annotations or metadata. [Assumption: the API provides enough context in public responses to distinguish global from tenant-scoped items — e.g., via `metadata.annotations["osac.openshift.io/tenant"]` or a `creators`/`tenants` field. If not, a backend change to expose scope through the public API is needed.]

#### 5. Create Page (`CatalogItemCreatePage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogItemCreatePage.tsx`

A full-page form (not a wizard) using Formik + Yup + `OsacForm`.

**Form sections:**

**Section 1: General**
- Title (`InputField`, required, maxLength: 255)
- Description (`InputField` textarea, optional, Markdown). All consumers that render this field must use a sanitizing Markdown renderer that strips unsafe HTML tags, `javascript:` URL schemes, and other XSS vectors.
- Resource type (`SelectField`: Cluster, Virtual Machine, Bare Metal, required)
- Scope (providerAdmin only): `RadioButtonField` — Global or Tenant-scoped. If tenant-scoped, a tenant selector dropdown appears. For tenantAdmin, this section shows "Scope: Your organization" as read-only text.

**Section 2: Template / Base Selection** (role-dependent)

- **providerAdmin:** After selecting resource type, a `SelectField` populates with templates from the corresponding template list endpoint. Selecting a template fetches its details and populates the field definitions section with the template's parameter definitions as a starting point.
- **tenantAdmin:** After selecting resource type, a `SelectField` populates with published global catalog items of that type. Selecting a base item fetches its details and pre-populates the field definitions section.

**Section 3: Field Definitions** (see § FieldDefinitionsEditor)

**Form submission:**
- Validates all fields with Yup
- Constructs the create payload:
  ```json
  {
    "title": "...",
    "description": "...",
    "template": "<template-id>",
    "published": false,
    "field_definitions": [...]
  }
  ```
- Sends POST to the appropriate endpoint based on the selected resource type
- On success, navigates to the detail page
- On error, displays an inline `Alert` with the server error message

#### 6. Edit Page (`CatalogItemEditPage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogItemEditPage.tsx`

Reuses the same form component as the create page with the following differences:

- Title shows "Edit catalog item"
- Template/base selection is displayed as read-only text (not editable after creation)
- Resource type is displayed as read-only text
- Scope is displayed as read-only text
- The form tracks which fields have changed from their original values
- On submit, constructs a PATCH payload with only changed fields and the corresponding `update_mask`

#### 7. Detail Page (`CatalogItemDetailPage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogItemDetailPage.tsx`

Uses `ResourceDetailHeader` with breadcrumb (Administration > Catalog Management > {title}) and a publication status badge.

**Tabs:**
- **Overview:** Read-only display of general information (title, description, resource type, scope, template name, publication status, creation date)
- **Field Definitions:** Table showing all field definitions with columns: Path, Display Name, Editable (Yes/No), Default Value, Validation Constraints
- **Provisioned Resources:** Table of resources (Clusters, ComputeInstances, or BareMetalInstances) provisioned from this catalog item, fetched via the resource list endpoint with a `this.spec.catalog_item == "<id>"` CEL filter

**Header actions:**
- Edit button (navigates to edit page)
- Kebab menu with Publish/Unpublish and Delete actions
- Actions are hidden for Tenant Admins viewing global items

#### 8. FieldDefinitionsEditor Component

**Location:** `libs/ui-components/src/components/catalogManagement/FieldDefinitionsEditor.tsx`

The most complex new component. Built on Formik `FieldArray` with the field name `fieldDefinitions`.

**Each field definition row renders:**

| Control | Field | Type | Notes |
|---------|-------|------|-------|
| Path | `fieldDefinitions.${i}.path` | `SelectField` or `InputField` | Dropdown populated from template parameters when available; falls back to free-text input for arbitrary dot-notation paths |
| Display Name | `fieldDefinitions.${i}.displayName` | `InputField` | Optional; derived from path if empty |
| Editable | `fieldDefinitions.${i}.editable` | `Switch` (PatternFly) | Toggle; for Tenant Admin, disabled if base item marks field as non-editable |
| Default Value | `fieldDefinitions.${i}.default` | `InputField` | Type-aware input (text, number, boolean toggle) based on template parameter type when available; falls back to text input for `google.protobuf.Value`. Required when `editable` is false. |
| Validation | `fieldDefinitions.${i}.validationSchema` | `ValidationConstraintsEditor` | Expandable sub-form (see below) |
| Actions | — | Buttons | Remove (trash icon), Move Up/Down (arrow icons) |

**Add button:** Below the list, an "Add field definition" button calls FieldArray's `push()` with an empty field definition.

**Yup validation schema for each field definition:**

```typescript
const fieldDefinitionSchema = Yup.object({
  path: Yup.string().required('Path is required')
    .matches(/^[a-z_][a-z0-9_.]*$/, 'Path must be dot-notation (e.g., spec.network.pod_cidr)'),
  displayName: Yup.string(),
  editable: Yup.boolean().required(),
  default: Yup.mixed().when('editable', {
    is: false,
    then: (schema) => schema.required('Default value is required for non-editable fields'),
  }),
  validationSchema: Yup.string().nullable(),
});
```

**Tenant Admin restriction behavior:**

When the create page is in Tenant Admin mode (base catalog item selected):
- Fields from the base item are pre-populated and cannot be removed
- The `editable` toggle is disabled (grayed out) for fields that are non-editable in the base
- For editable fields, the toggle can be switched from editable to non-editable (but not the reverse)
- Default values can be changed but the UI does not enforce "tighter" constraints — the server validates that Tenant Admin constraints are equal or more restrictive
- New fields cannot be added (the "Add field definition" button is hidden)
- Paths cannot be changed

#### 9. ValidationConstraintsEditor Component

**Location:** `libs/ui-components/src/components/catalogManagement/ValidationConstraintsEditor.tsx`

An expandable sub-form within each field definition row, shown when the "Validation" column is clicked or expanded. All constraints — including nested object validation — are configured through dedicated structured form controls. There is no raw JSON Schema editor toggle.

**Scalar constraints:**

| Constraint | Input Type | JSON Schema Mapping |
|-----------|-----------|---------------------|
| Minimum | Number input | `{ "minimum": N }` |
| Maximum | Number input | `{ "maximum": N }` |
| Min Length | Number input | `{ "minLength": N }` |
| Max Length | Number input | `{ "maxLength": N }` |
| Pattern | Text input | `{ "pattern": "regex" }` |
| Allowed Values | Tag input (multi-value) | `{ "enum": [...] }` |

**Resource reference constraints:**

| Constraint | Input Type | JSON Schema Mapping |
|-----------|-----------|---------------------|
| Resource Type | Select dropdown | `{ "resourceRef": "InstanceType" }` |
| Restrict to subset | Checkbox multi-select of available resources | `{ "resourceRef": "InstanceType", "enum": ["cx3.xlarge", ...] }` |

For fields with a `resourceRef` constraint, the UI fetches available resources from the corresponding API endpoint and presents them as selectable options. `resourceRef` is an OSAC-specific custom keyword within the JSON Schema `validation_schema`; standard JSON Schema validators ignore it.

**List and map constraints:**

| Constraint | Input Type | JSON Schema Mapping |
|-----------|-----------|---------------------|
| Min Items | Number input | `{ "minItems": N }` |
| Max Items | Number input | `{ "maxItems": N }` |
| Min Properties | Number input | `{ "minProperties": N }` |
| Max Properties | Number input | `{ "maxProperties": N }` |

Setting `minItems` and `maxItems` to the same value locks the list length — users can edit each item but cannot add or remove entries.

**Complex object constraints:**

| Constraint | Input Type | JSON Schema Mapping |
|-----------|-----------|---------------------|
| Nested Properties | Nested constraint form per sub-field | `{ "properties": { "field": { ... } } }` |
| Required Fields | Checkbox list of sub-fields | `{ "required": ["field1", ...] }` |
| Item Schema | Nested constraint form | `{ "items": { "properties": { ... } } }` |

For nested properties and item schemas, the editor renders a recursive constraint form for each sub-field, allowing admins to set constraints on complex objects without writing JSON by hand.

The component constructs a JSON Schema object from these structured inputs. When no constraints are configured, `validationSchema` is set to an empty string (the API treats empty string as no validation).

#### 10. Component File Structure

```
libs/ui-components/src/
  pages/
    admin/
      CatalogManagementListPage.tsx
      CatalogItemCreatePage.tsx
      CatalogItemEditPage.tsx
      CatalogItemDetailPage.tsx
  components/
    catalogManagement/
      CatalogItemTable.tsx
      CatalogItemActionsMenu.tsx
      CatalogItemForm.tsx           # shared form body for create/edit
      CatalogItemScopeBadge.tsx
      CatalogItemStatusLabel.tsx
      FieldDefinitionsEditor.tsx
      FieldDefinitionRow.tsx
      ValidationConstraintsEditor.tsx
      catalogItemKinds.ts           # CatalogItemKind config map
  api/v1/
    catalog-item-admin.ts           # admin CRUD hooks
```

### Security Considerations

This design introduces no new authentication or authorization mechanisms. All catalog management operations use the existing fulfillment public API, which enforces role-based access on the server side:

- Tenant Users receive `PERMISSION_DENIED` if they attempt to call Create/Update/Delete on catalog items through the API directly. The UI prevents this by hiding the admin navigation and routes, but the server is the enforcement boundary.
- Tenant Admins cannot modify global catalog items — the server returns `PERMISSION_DENIED` for Update/Delete on items where `tenant` is empty or belongs to another tenant. The UI disables these actions in the kebab menu.
- The `tenant` field is auto-set by the server for Tenant Admin creates; the UI does not send it.

Input validation is performed client-side (Yup) for UX responsiveness and server-side (fulfillment-service) for enforcement. The client-side validation is a convenience — it does not replace server-side validation.

The `description` field accepts Markdown authored by admins. All rendering surfaces (detail page, catalog browsing, list tooltips) must use a sanitizing Markdown renderer that strips unsafe HTML tags, `javascript:` URL schemes, and other stored-XSS vectors. The server stores the raw Markdown as provided; sanitization is a rendering-time responsibility.

The validation schema field accepts a JSON string from the admin. This string is stored as-is and used by the server for field validation during resource provisioning. The UI does not execute or eval the JSON Schema — it is treated as data, not code.

### Failure Handling and Recovery

| Failure Mode | What Happens | User Experience | Recovery |
|-------------|-------------|-----------------|----------|
| API unreachable | Fetch hooks return error state | List page shows `QueryErrorState` with retry button; form pages show inline alert | User retries; React Query auto-retries once |
| Create fails (validation) | Server returns `INVALID_ARGUMENT` | Form page shows inline alert with field-specific error message from server | User corrects input and resubmits |
| Delete blocked (resources provisioned) | Server returns error with code `Z0003` | Delete confirmation modal shows alert: "Cannot delete — resources provisioned from this item. Unpublish instead." | User unpublishes instead |
| Publish fails | Server returns error | Kebab action shows error toast notification | User retries |
| Stale data on edit | User edits a catalog item that was concurrently modified | PATCH returns version conflict error | User refreshes and re-edits |
| Template list empty | No templates exist for the selected resource type | Template dropdown shows "No templates available" message | CSP Admin must create templates via CLI/API first |

### RBAC / Tenancy

This design does not introduce new RBAC roles or tenancy mechanisms. It consumes the existing catalog item tenancy model:

- `providerAdmin`: Full CRUD on all catalog items (global and tenant-scoped). The server does not restrict based on tenant.
- `tenantAdmin`: Full CRUD over their own organization-scoped catalog items. Read-only on global items. The server enforces tenant scoping — the UI disables write actions on global items as a UX convenience.
- `tenantUser`: Read-only on published items visible to their tenant. No access to admin pages. The UI hides the admin nav section; the server enforces `PERMISSION_DENIED` on write operations.

No new `osac.openshift.io/tenant` or `osac.openshift.io/owner-reference` annotations are introduced by this design — the API layer handles tenant metadata.

### Observability and Monitoring

No new observability changes. The UI is a frontend application — observability for catalog item operations is handled by the fulfillment-service backend (metrics, events, structured logs for CRUD operations). The Go proxy logs request/response status codes for all API calls.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scope not visible in public API responses | CSP Admin list page cannot show Global vs Tenant-scoped badges | Check whether `metadata.annotations` or `creators`/`tenants` fields expose scope. If not, request a backend change to include a `scope` field in public responses, or route CSP Admin requests through the private API. |
| Template parameter enumeration insufficient for path picker | Field definitions editor cannot offer a dropdown of valid paths | Fall back to free-text path input with validation feedback on save. Document available paths in the catalog management docs. |
| FieldArray stale values after remove | Formik FieldArray has a known issue where `values` is stale immediately after `remove()` | Do not read `values` synchronously after `remove()`. Use the FieldArray render callback which provides the updated array. |
| Three parallel API calls for list page | Loading time increases if one of the three catalog item type endpoints is slow | Show partial results as each query resolves (progressive rendering). Use `useQueries` with per-query loading states so the table populates incrementally. |

### Drawbacks

Adding a catalog management section increases the UI surface area and introduces the first role-gated navigation in osac-ui. This creates a precedent that future admin features will follow, adding complexity to the navigation and routing system. The alternative — managing catalog items exclusively via CLI — avoids this complexity but provides a poor admin experience for non-technical cloud provider administrators.

The field definitions editor is a complex custom component with no precedent in the existing UI. It combines Formik FieldArray, dynamic type-aware inputs, and nested validation — patterns that are individually well-supported but have not been combined at this scale in osac-ui. The implementation will require thorough testing to handle edge cases (empty lists, reordering, validation state management).

The polymorphic approach (one component set for three catalog item types) adds indirection through the `CatalogItemKindConfig` abstraction. The alternative — three separate implementations — would be more straightforward to read but would triple the maintenance burden and risk divergence.

## Alternatives (Not Implemented)

### Wizard for catalog item creation

A PatternFly Wizard with three steps (General → Template → Field Definitions) was considered. [Research: §Architecture Patterns — Pattern 3] This approach provides step-by-step guidance and is appropriate for 3-7 step processes. It was not selected because:
- The general and template sections are short (3-5 fields total) and do not benefit from wizard navigation overhead.
- The field definitions section is the only complex section; isolating it in a wizard step does not reduce its complexity.
- Existing osac-ui create forms for similar-complexity resources (VirtualNetwork) use modals or full-page forms, not wizards. The wizard pattern is reserved for the multi-step provisioning flow (CatalogProvisionWizard).

If field definitions configuration proves too complex for a single form section during implementation, the design can be revised to use a wizard.

### Raw JSON editor for validation schemas

Providing a raw JSON textarea for `validation_schema` (either as the sole editor or as a "Show raw JSON" toggle alongside structured inputs) was considered. This offers maximum expressiveness since `validation_schema` is a JSON Schema draft 2020-12 object. It was not selected because:
- Catalog item admins are infrastructure managers, not JSON Schema experts.
- From experience with these types of toggles, raw/structured bidirectional sync adds significant complexity (parsing, validation, conflict resolution) with limited benefit.
- The structured constraint form covers all supported constraint types (scalar, resource reference, list/map, complex object) through dedicated form controls, making raw editing unnecessary for the defined use cases.

### Separate pages per resource type

Building separate list/create/edit/detail pages for ClusterCatalogItems, ComputeInstanceCatalogItems, and BareMetalInstanceCatalogItems was considered. This would be straightforward to implement but triples the page count and maintenance surface. Since all three types share the same data structure (`title`, `description`, `template`, `published`, `fieldDefinitions`), a polymorphic approach using a `CatalogItemKindConfig` map was selected. The only variation is the template selection endpoint, which is handled by the config map.

### Modal for create/edit instead of full page

Using a PatternFly Modal (like VirtualNetworkCreateModal) was considered. This works well for simple forms with 3-5 fields but the field definitions editor requires significant vertical space and would be cramped inside a modal. A full-page form provides enough room for the repeatable field definitions list and the expandable validation constraints editor.

## Open Questions

### 1. Scope visibility in public API responses

How does the CSP Admin determine whether a catalog item is global or tenant-scoped when the public API strips the `tenant` field? Is scope derivable from `metadata.annotations`, `creators`, or `tenants` fields in the public response? If not, does the Go proxy need to forward private API endpoints for CSP Admin users, or should the API add a `scope` field to public responses?

**Owner:** API team
**Impact:** Without scope visibility, the CSP Admin list page cannot show a "Scope" column. The current design assumes scope is derivable from public API responses and will need revision if it is not.

### 2. Template parameter enumeration for field path picker

Do the template GET endpoints return enough structured information about available field paths (parameter definitions with names, types, and descriptions) to populate a dropdown in the field definitions editor? Or are template parameters unstructured enough that admins must type dot-notation paths manually?

**Owner:** API team
**Impact:** Determines whether the field definitions editor shows a path dropdown (better UX) or a free-text input with server-side validation (adequate but less discoverable). The current design supports both: dropdown when template parameters are available, free-text fallback otherwise.

### 3. Querying resources by catalog item reference

Can the resource list endpoints (Clusters, ComputeInstances, BareMetalInstances) be filtered by `this.spec.catalog_item == "<id>"` using the CEL filter parameter? This is needed for the detail page's "Provisioned Resources" tab.

**Owner:** API team
**Impact:** If the filter is not supported, the detail page cannot show provisioned resources without fetching all resources and filtering client-side (poor performance at scale).

## Test Plan

Testing strategy for the catalog management UI:

**E2E tests (Cypress):**
- Role gating: verify "Administration" nav section is visible to providerAdmin and tenantAdmin, hidden for tenantUser
- Route guard: verify direct navigation to `/admin/catalog` by tenantUser redirects to `/catalog`
- CSP Admin create flow: create a catalog item with field definitions, verify it appears in the list as unpublished
- Publish/unpublish: toggle publication status via kebab menu, verify status label updates
- Edit flow: modify title and field definitions, verify changes persist
- Delete flow: delete a catalog item with no provisioned resources, verify removal from list
- Delete blocked: attempt to delete a catalog item with provisioned resources, verify error message
- Tenant Admin create flow: create from a global catalog item, verify restrictions (cannot make non-editable field editable)
- Tenant Admin visibility: verify global items show as read-only, org-scoped items show full actions
- Type filter: verify filtering by Cluster/VM/Bare Metal updates the table

**Component-level testing (if adopted):**
- FieldDefinitionsEditor: add, remove, reorder field definitions; verify Formik state management
- ValidationConstraintsEditor: set scalar, resource reference, list/map, and nested constraints; verify correct JSON Schema output

## Graduation Criteria

The UI feature will be considered complete when:
- All four page types (list, create, edit, detail) are implemented and functional
- Role-gated navigation is working for all three roles
- The field definitions editor supports all FieldDefinition properties
- CSP Admin and Tenant Admin workflows are tested end-to-end
- The "Provisioned Resources" tab on the detail page shows related resources (dependent on Open Question 3)

## Upgrade / Downgrade Strategy

This is a new UI feature with no upgrade impact. Downgrading the UI to a version without catalog management pages simply removes the admin screens — catalog items remain manageable via CLI. No data migration is required.

## Version Skew Strategy

The UI depends on the catalog item API endpoints being available in fulfillment-service. If the UI is deployed before the catalog item API is available, the admin pages will show API error states. The Go proxy must be updated to forward the catalog item API paths if not already configured.

Since the catalog item API is already implemented, no version skew is expected for initial deployment.

## Support Procedures

- **Failure detection:** API errors surface as inline alerts on pages and toast notifications for async actions. The Go proxy logs all API call failures with status codes and response bodies.
- **Disabling:** The admin nav section can be removed by reverting the `navRowsForRole()` change. This hides the admin pages without affecting the tenant-facing catalog browse or provisioning flows.
- **Recovery:** Re-enabling the nav section restores full functionality. No state is stored in the UI — all catalog item data is in the fulfillment-service database.

## Infrastructure Needed

None. The UI runs in the existing osac-ui build and deployment pipeline. No new test infrastructure is required beyond what Cypress E2E tests already use.
