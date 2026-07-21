---
title: catalog-items-ui
authors:
  - eaharoni
creation-date: 2026-07-16
last-updated: 2026-07-20
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

### User Stories

- As a Cloud Provider Admin, I want to create and manage catalog items through the web console so that I can define curated offerings without using the CLI.
- As a Cloud Provider Admin, I want to configure field definitions with structured validation constraints so that I can enforce guardrails on tenant provisioning.
- As a Tenant Admin, I want to create organization-scoped catalog items from published global items so that I can tailor offerings to my organization's standards.
- As a Tenant Admin, I want to see which catalog items are global (read-only) vs. organization-scoped (manageable) so that I know what I can and cannot modify.
- As a Tenant User, I want the admin management screens to be hidden from my view so that I only see the catalog browsing and provisioning experience.

### Goals

- Enable Cloud Provider Admins and Tenant Admins to manage catalog items through the web console with full CRUD operations.
- Provide role-appropriate views: admins see management screens; tenant users see only the existing catalog browsing experience.
- Support the Tenant Admin "further restrict" create flow where field definitions are pre-populated from a global catalog item and can only be made more restrictive.
- Reuse existing osac-ui patterns and share common UI components across all three catalog item types using JSX composition.

### Non-Goals

- Drag-and-drop reordering of field definitions.
- Full visual JSON Schema editor (e.g., JSONJoy, react-json-schema-form-builder). The Advanced mode textarea is intentionally minimal — syntax highlighting only, no schema-aware autocomplete or visual builder.
- Changes to the existing CatalogProvisionWizard — that component already handles catalog items. Any alignment changes are tracked separately.
- Direct private API access from the browser. The Go proxy mediates all API access; CSP Admin requests are routed to private API endpoints (which return the `tenant` field), while Tenant Admin and Tenant User requests are routed to public API endpoints.

## Proposal

The design adds four new page types under a new "Administration > Catalog Management" sidebar section: a list page, a create page, an edit page, and a detail page. These pages are visible only to `providerAdmin` and `tenantAdmin` roles. The list page shows a PatternFly table with type filter, search, scope badges, and kebab row actions (edit, publish/unpublish, delete). The create page is a full-page form with sections for general information, template or base catalog item selection (role-dependent), and a field definitions editor. The edit page reuses the same form with the template/base selection locked. The detail page shows read-only configuration, field definitions, and related provisioned resources.

Shared components (`CatalogItemForm`, `FieldDefinitionsEditor`, `ValidationConstraintsEditor`, `CatalogItemTable`) are composed via JSX into kind-specific create/edit/detail pages. Each entry in the field definitions editor includes a path (selected from the resource spec), display name, an editable toggle, a default value input, and a validation constraints editor (Basic mode with structured form controls, or Advanced mode with a raw JSON Schema textarea).

### Workflow Description

#### Cloud Provider Admin — Create Catalog Item

1. CSP Admin navigates to **Administration > Catalog Management** in the sidebar.
2. The list page shows all catalog items across all tenants with a "Create catalog item" dropdown button (Cluster / Virtual Machine / Bare Metal).
3. CSP Admin selects a resource type from the dropdown and lands on the kind-specific create page (e.g., `/admin/catalog/cluster/create`).
4. **General section:** Admin enters name, description (Markdown), and selects scope (Global or a specific tenant). Resource type is derived from the route and displayed as read-only text.
5. **Template section:** The admin selects a template from a dropdown populated by the corresponding template list endpoint (e.g., `GET /v1/cluster_templates`).
6. **Field definitions section:** The `FieldDefinitionsEditor` displays the resource spec fields the admin wants to expose or constrain. Not all fields from the resource spec need to be included — fields not added to the field definitions are not exposed to the user. The admin configures each included field:
   - Select a path from the resource spec (e.g., `ComputeInstanceSpec` fields for a VM catalog item)
   - Enter an optional display name
   - Toggle editable on/off
   - Set an optional default value (required for non-editable fields)
   - Optionally configure validation constraints using structured form controls in Basic mode (numeric bounds, allowed values, string length, pattern, item count, nested properties), or switch to Advanced mode to write arbitrary JSON Schema directly
   The admin can add fields from the resource spec or remove fields they no longer want to expose.
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
3. Tenant Admin selects a resource type from the "Create catalog item" dropdown.
4. **General section:** Admin enters name and description. Resource type is derived from the route and displayed as read-only. Scope is automatically set to the tenant's organization (not editable).
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

This design introduces no new API extensions. All catalog item CRUD endpoints already exist in fulfillment-service. The Go proxy routes requests to the appropriate API based on the caller's role:

**Cloud Provider Admin** (private API — returns `tenant` field, no publication/tenant filtering):
- `GET/POST/PATCH/DELETE /api/fulfillment/private/v1/cluster_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/private/v1/compute_instance_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/private/v1/baremetal_instance_catalog_items`
- `GET /api/fulfillment/private/v1/cluster_templates` (read-only, for template selection)
- `GET /api/fulfillment/private/v1/compute_instance_templates` (read-only)
- `GET /api/fulfillment/private/v1/baremetal_instance_templates` (read-only)

**Tenant Admin / Tenant User** (public API — `tenant` stripped, scoped by caller's tenant):
- `GET/POST/PATCH/DELETE /api/fulfillment/v1/cluster_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/v1/compute_instance_catalog_items`
- `GET/POST/PATCH/DELETE /api/fulfillment/v1/baremetal_instance_catalog_items`
- `GET /api/fulfillment/v1/cluster_templates` (read-only)
- `GET /api/fulfillment/v1/compute_instance_templates` (read-only)
- `GET /api/fulfillment/v1/baremetal_instance_templates` (read-only)

The Go proxy selects the API tier based on the caller's role from the session token. The browser never accesses private API endpoints directly.

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
/admin/catalog                → CatalogManagementListPage
/admin/catalog/:type/create   → kind-specific create page (e.g., ClusterCatalogItemCreatePage)
/admin/catalog/:type/:id      → kind-specific detail page
/admin/catalog/:type/:id/edit → kind-specific edit page
```

The `:type` parameter is one of `cluster`, `compute-instance`, or `baremetal-instance`, mapping to the correct kind-specific page and API endpoint. This avoids ID collision across types and eliminates the ambiguity between a single generic create page and three pre-bound pages — each kind has its own route and page component.

A route guard component `AdminRoute` wraps admin pages and requires the caller's role to be `providerAdmin` or `tenantAdmin`. Any other role (including `tenantUser` and any future or unexpected authenticated role) is redirected to `/catalog`. Unauthenticated users are redirected to the login page.

**File: `libs/ui-components/src/icons.tsx`**

Add an icon mapping for the `catalog-management` nav item ID (e.g., `CogIcon` or `CatalogIcon` from PatternFly icons).

#### 2. Catalog Item Type Abstraction — Shared Components via JSX Composition

Rather than a single monolithic component driven by a configuration map, the design uses shared building blocks that each kind-specific page composes via JSX. This is more React-idiomatic and handles future per-kind divergence naturally:

**Shared components** (used by all three kinds):
- `CatalogItemGeneralFields` — name, description, scope inputs (reused in create/edit)
- `TemplateSelector` — template dropdown, receives already-fetched templates and loading state as props (presentational only — does not fetch data)
- `FieldDefinitionsEditor` — the field definitions table (§8), parameterized by `specFields`
- `CatalogItemTable` — PatternFly table with shared columns, actions, and scope badges
- `CatalogItemActionsMenu` — kebab menu (publish/unpublish/delete)

**Kind-specific pages** compose these shared components directly — Formik wiring, initial values, validation schema, submission logic, and data fetching are all explicit at the page level, not hidden inside a shared form abstraction:

```tsx
// ClusterCatalogItemCreatePage.tsx
const ClusterCatalogItemCreatePage = () => {
  const { data: templates, isLoading } = useClusterTemplates();
  const { mutateAsync: createClusterCatalogItem } = useCreateClusterCatalogItem();

  return (
    <Formik
      initialValues={clusterCatalogItemInitialValues}
      validationSchema={clusterCatalogItemSchema}
      onSubmit={(values) => createClusterCatalogItem(buildClusterPayload(values))}
    >
      <CatalogItemGeneralFields />
      <TemplateSelector templates={templates} isLoading={isLoading} />
      <FieldDefinitionsEditor fields={CLUSTER_SPEC_FIELDS} />
    </Formik>
  );
};
```

Each kind-specific page calls its own typed hooks (`useClusterTemplates`, `useComputeInstanceTemplates`, `useBareMetalInstanceTemplates`) and passes data down to shared presentational components. Per-kind differences (extra sections, different validation, different submission) are natural JSX additions, not config flags.

A lightweight `CatalogItemKind` type remains for URL routing:

```typescript
type CatalogItemKind = 'cluster' | 'compute-instance' | 'baremetal-instance';
```

#### 3. API Hooks

New hooks in `libs/ui-components/src/api/v1/`:

**`catalog-item-admin.ts`** — Admin-specific hooks that aggregate all three types:

```typescript
// Fetches catalog items across all three types with pagination
interface UseAllCatalogItemsResult {
  items: CatalogItemWithKind[];
  isLoading: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  isFetchingNextPage: boolean;
  error: Error | null;
}
function useAllCatalogItems(filters?: CatalogItemFilters): UseAllCatalogItemsResult

// Single item fetch
function useCatalogItem(kind: CatalogItemKind, id: string): UseQueryResult<CatalogItem>

// Mutations per kind
function useCreateCatalogItem(kind: CatalogItemKind): UseMutationResult
function useUpdateCatalogItem(kind: CatalogItemKind): UseMutationResult
function useDeleteCatalogItem(kind: CatalogItemKind): UseMutationResult
```

The `useAllCatalogItems` hook fires three parallel queries (one per kind) and merges results into a unified list with a `kind` discriminator. Each query passes server-side pagination parameters (`page_size`, `page_token`) and any active filters (type, publication status) to the API so that the client never fetches unbounded result sets. Each item is tagged with its `CatalogItemKind` so the list page can route to the correct detail/edit URLs and the correct API endpoint for mutations. The list page uses infinite scroll or a "Load more" button to fetch additional pages.

The update hook builds the `update_mask` FieldMask from the diff between original and modified values. The publish/unpublish action is a specialized update that sends only `{ published: true/false }` with `update_mask: "published"`.

#### 4. List Page (`CatalogManagementListPage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogManagementListPage.tsx`

Uses `ListPage` + `ListPageBody` layout with a PatternFly `Table`.

**Toolbar:**
- "Create catalog item" dropdown button (Cluster / Virtual Machine / Bare Metal) — each option navigates to the kind-specific create route
- Type filter: toggle group with All / Cluster / VM / Bare Metal (drives which API endpoints are queried)
- Search: text input filtering by name (server-side via API filter parameter)
- Publication status filter: All / Published / Unpublished (server-side via API filter parameter)

**Table columns:**

| Column | Content |
|--------|---------|
| Name | Catalog item name as a link to the detail page |
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

**Scope display:**
- **CSP Admin:** The private API returns the `tenant` field in responses. Items with an empty `tenant` are global; items with a non-empty `tenant` are organization-scoped. The UI displays the appropriate scope badge directly from this field.
- **Tenant Admin:** The public API does not expose the `tenant` field, but scope is deterministic: items the Tenant Admin can update or delete are organization-scoped; items that return `PERMISSION_DENIED` on write operations are global. The UI derives scope from server-authored capability metadata or the item's `creators`/`tenants` fields. Global items show no edit/delete actions in the kebab menu.

#### 5. Create Pages (kind-specific)

**Locations:** `libs/ui-components/src/pages/admin/cluster/ClusterCatalogItemCreatePage.tsx` (and equivalent for compute-instance, baremetal-instance)

Each kind-specific create page is a full-page form using Formik + Yup that explicitly composes shared section components (see §2). There is no shared `CatalogItemForm` wrapper — Formik wiring, initial values, validation schema, data fetching, and submission logic are all visible at the page level.

**Form sections:**

**Section 1: General**
- Name (`NameField`, required) — reuses the existing osac-ui `NameField` component with standard naming validation
- Description (`InputField` textarea, optional) — markdown-formatted long description
- Resource type (read-only text, derived from the route — e.g., "Cluster")
- Scope (providerAdmin only): `RadioButtonField` — Global or Tenant-scoped. If tenant-scoped, a tenant selector dropdown appears. For tenantAdmin, this section shows "Scope: Your organization" as read-only text.

**Section 2: Template / Base Selection** (role-dependent)

- **providerAdmin:** A `SelectField` populates with templates from the corresponding template list endpoint (fetched by the page's typed hook). Selecting a template fetches its details and populates the field definitions section with the template's parameter definitions as a starting point.
- **tenantAdmin:** A `SelectField` populates with published global catalog items of the matching resource type. Selecting a base item fetches its details and pre-populates the field definitions section.

**Section 3: Field Definitions** (see § FieldDefinitionsEditor)

**Form submission:**
- Validates all fields with Yup
- Constructs the create payload with `name` (not `title`, consistent with osac-ui conventions). For CSP Admin (private API), the `tenant` field is included — empty string for global items, or the selected tenant ID for tenant-scoped items. For Tenant Admin (public API), `tenant` is omitted (auto-set by server):

  ```json
  {
    "name": "...",
    "description": "...",
    "template": "<template-id>",
    "tenant": "",
    "published": false,
    "field_definitions": [...]
  }
  ```

- Sends POST to the appropriate endpoint (determined by the kind-specific page and caller's role)
- On success, navigates to the detail page
- On error, displays an inline `Alert` with the server error message

#### 6. Edit Pages (kind-specific)

**Locations:** `libs/ui-components/src/pages/admin/cluster/ClusterCatalogItemEditPage.tsx` (and equivalent for compute-instance, baremetal-instance)

Each kind-specific edit page reuses the same shared section components as the create page with the following differences:

- Page heading shows "Edit catalog item"
- Template/base selection is displayed as read-only text (not editable after creation)
- Resource type is displayed as read-only text
- Scope is displayed as read-only text
- The form tracks which fields have changed from their original values
- On submit, constructs a PATCH payload with only changed fields and the corresponding `update_mask`
- `field_definitions` is treated as a whole-list replacement in the `update_mask` — if any field definition is added, removed, reordered, or modified, the entire `field_definitions` array is sent. Item-level PATCH semantics for repeated fields are not supported by the API.

#### 7. Detail Page (`CatalogItemDetailPage`)

**Location:** `libs/ui-components/src/pages/admin/CatalogItemDetailPage.tsx`

Uses `ResourceDetailHeader` with breadcrumb (Administration > Catalog Management > {name}) and a publication status badge.

**Tabs:**
- **Overview:** Read-only display of general information (name, description, resource type, scope, template name, publication status, creation date)
- **Field Definitions:** Table showing all field definitions with columns: Path, Display Name, Editable (Yes/No), Default Value, Validation Constraints
- **Provisioned Resources:** Table of resources (Clusters, ComputeInstances, or BareMetalInstances) provisioned from this catalog item, fetched via the resource list endpoint with a `this.spec.catalog_item == "<id>"` CEL filter

**Header actions:**
- Edit button (navigates to edit page)
- Kebab menu with Publish/Unpublish and Delete actions
- Actions are hidden for Tenant Admins viewing global items

#### 8. FieldDefinitionsEditor Component

**Location:** `libs/ui-components/src/components/catalogManagement/FieldDefinitionsEditor.tsx`

The most complex new component. Built on Formik `FieldArray` with the field name `fieldDefinitions`. The admin selects which fields from the resource spec to include in the catalog item's field definitions. Not all fields need to be included — fields not in the list are not exposed to the user. For Tenant Admin, the field list comes from the base catalog item's field definitions.

**Each field definition row renders:**

| Control | Field | Type | Notes |
|---------|-------|------|-------|
| Path | `fieldDefinitions.${i}.path` | Read-only text | Selected from the resource spec; not editable once added |
| Display Name | `fieldDefinitions.${i}.displayName` | `InputField` | Optional; derived from the field path if not set |
| Editable | `fieldDefinitions.${i}.editable` | `Switch` (PatternFly) | Toggle; for Tenant Admin, disabled if base item marks field as non-editable |
| Default Value | `fieldDefinitions.${i}.default` | `InputField` | Type-aware input (text, number, boolean toggle) based on template parameter type. Required when `editable` is false. |
| Validation | `fieldDefinitions.${i}.validationSchema` | `ValidationConstraintsEditor` | Expandable sub-form (see below) |

The admin adds fields from the resource spec using an "Add field" button that shows a dropdown of available (not yet added) spec fields. Fields can be removed with a "Remove" button on each row.

**Yup validation schema for each field definition:**

```typescript
const fieldDefinitionSchema = Yup.object({
  path: Yup.string().required('Path is required'),  // selected from resource spec, read-only once added
  displayName: Yup.string(),
  editable: Yup.boolean().required(),
  default: Yup.mixed().when('editable', {
    is: false,
    then: (schema) => schema.required('Default value is required for non-editable fields'),
  }),
  validationSchema: Yup.object().nullable(),  // serialized as google.protobuf.Struct
});
```

**Tenant Admin restriction behavior:**

When the create page is in Tenant Admin mode (base catalog item selected), the field list is pre-populated from the base catalog item's field definitions. The admin can:
- Toggle editable fields to non-editable (but not the reverse — the toggle is disabled for fields already marked non-editable in the base)
- Change or tighten default values for editable fields
- Add or tighten validation constraints (cannot remove or loosen constraints from the base)
- Change display names

The admin cannot add or remove fields, change paths, or make non-editable fields editable.

**Tighten-only enforcement (0.2 — UI only):** In Basic mode, the UI prevents loosening constraints by disabling controls that would violate the tighten-only rule (e.g., graying out the minimum input if the value would go below the base's minimum). In Advanced mode, the UI shows the base schema as a read-only reference panel so the admin can manually ensure their schema is more restrictive. The following comparison rules apply in Basic mode:

- **Numeric bounds:** `minimum` can only increase; `maximum` can only decrease.
- **String constraints:** `minLength` can only increase; `maxLength` can only decrease. `pattern` can only be made more restrictive (added, not removed).
- **Enum:** values can only be removed from the base set, never added.
- **Item/property counts:** `minItems`/`minProperties` can only increase; `maxItems`/`maxProperties` can only decrease.
- **Editable toggle:** can change from `true` to `false` (lock a field), never `false` to `true`.

**Tighten-only enforcement (0.3 — server-side, future):** Server-side enforcement of the tighten-only rule is deferred to 0.3. When implemented, the server will compare the Tenant Admin's schema against the base and return `INVALID_ARGUMENT` for loosened constraints. For 0.2, the server accepts any valid JSON Schema — tighten-only is enforced as a UI convenience only.

#### 9. ValidationConstraintsEditor Component

**Location:** `libs/ui-components/src/components/catalogManagement/ValidationConstraintsEditor.tsx`

An expandable sub-form within each field definition row, shown when the "Validation" column is clicked or expanded. The editor supports two modes:

- **Basic mode** (default): structured form controls for each supported constraint type. Recommended for most admins.
- **Advanced mode**: a raw JSON Schema textarea with syntax highlighting. Used when editing schemas that contain keywords beyond the Basic editor's supported set, or when the admin prefers to write JSON directly.

**Mode auto-detection on load:** When editing an existing catalog item, the editor inspects each field's `validationSchema`. If it contains only Basic-supported keywords (`minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `enum`, `minItems`, `maxItems`, `minProperties`, `maxProperties`, `properties`, `required`, `items`), the field opens in Basic mode. If it contains any other keywords, it opens in Advanced mode with a label: "This field uses advanced validation."

**Mode switching:** An admin can switch from Basic to Advanced at any time — the structured inputs are serialized to JSON Schema and shown in the textarea. Switching from Advanced to Basic parses the JSON and populates the structured controls, but warns if unsupported keywords will be stripped: "Switching to Basic mode will remove the following constraints: [list]. Continue?"

**Scalar constraints:**

| Constraint | Input Type | JSON Schema Mapping |
|-----------|-----------|---------------------|
| Minimum | Number input | `{ "minimum": N }` |
| Maximum | Number input | `{ "maximum": N }` |
| Min Length | Number input | `{ "minLength": N }` |
| Max Length | Number input | `{ "maxLength": N }` |
| Pattern | Text input | `{ "pattern": "regex" }` |
| Allowed Values | Tag input (multi-value) | `{ "enum": [...] }` |

**Resource field enum population:**

For fields that reference platform resources (e.g., instance types, availability zones), the admin uses `enum` constraints. The UI fetches available values from the corresponding API endpoint and populates the `enum` list as a selectable set in Basic mode. The resulting JSON Schema uses standard `enum`:

```json
{ "enum": ["cx3.xlarge", "cx3.2xlarge", "cx3.4xlarge"] }
```

This approach uses standard JSON Schema keywords only — no custom keywords are needed.

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

In Basic mode, the component constructs a JSON Schema object from the structured inputs. In Advanced mode, the textarea content is parsed as JSON. Both paths produce a `google.protobuf.Struct` (JSON object) for the API. The serialization boundary is at form submission: the form's `onSubmit` handler serializes each field definition's `validationSchema` to a Struct before sending the request. The Advanced mode textarea validates that its content is well-formed JSON on blur; malformed JSON prevents form submission with an inline error. When no constraints are configured (Basic mode with no inputs, or Advanced mode with an empty textarea), `validationSchema` is omitted from the payload (the API treats a missing or empty Struct as no validation).

#### 10. Component File Structure

```
libs/ui-components/src/
  pages/
    admin/
      CatalogManagementListPage.tsx
      cluster/
        ClusterCatalogItemCreatePage.tsx
        ClusterCatalogItemEditPage.tsx
        ClusterCatalogItemDetailPage.tsx
      compute-instance/
        ComputeInstanceCatalogItemCreatePage.tsx
        ComputeInstanceCatalogItemEditPage.tsx
        ComputeInstanceCatalogItemDetailPage.tsx
      baremetal-instance/
        BareMetalInstanceCatalogItemCreatePage.tsx
        BareMetalInstanceCatalogItemEditPage.tsx
        BareMetalInstanceCatalogItemDetailPage.tsx
  components/
    catalogManagement/
      CatalogItemTable.tsx          # shared table (columns, row rendering)
      CatalogItemActionsMenu.tsx    # shared kebab menu
      CatalogItemGeneralFields.tsx  # shared name, description, scope inputs
      TemplateSelector.tsx          # shared template dropdown (presentational)
      CatalogItemScopeBadge.tsx
      CatalogItemStatusLabel.tsx
      FieldDefinitionsEditor.tsx    # shared field definitions table
      FieldDefinitionRow.tsx
      ValidationConstraintsEditor.tsx
      catalogItemRoutes.ts          # CatalogItemKind route mapping
      specFields.ts                 # per-kind SpecFieldDefinition arrays
  api/v1/
    catalog-item-admin.ts           # admin CRUD hooks
```

### Security Considerations

This design introduces no new authentication or authorization mechanisms. The Go proxy routes CSP Admin requests to the private API and Tenant Admin/User requests to the public API. The fulfillment-service enforces role-based access on the server side:

- Tenant Users receive `PERMISSION_DENIED` if they attempt to call Create/Update/Delete on catalog items through the API directly. The UI prevents this by hiding the admin navigation and routes, but the server is the enforcement boundary.
- Tenant Admins cannot modify global catalog items — the server returns `PERMISSION_DENIED` for Update/Delete on items where `tenant` is empty or belongs to another tenant. The UI disables these actions in the kebab menu.
- The `tenant` field is auto-set by the server for Tenant Admin creates; the UI does not send it. CSP Admins set `tenant` explicitly via the private API — `tenant = ""` creates a global item.

Input validation is performed client-side (Yup) for UX responsiveness and server-side (fulfillment-service) for enforcement. The client-side validation is a convenience — it does not replace server-side validation.

The `description` field accepts Markdown authored by admins and is rendered using the existing sanitizing Markdown renderer.

The validation schema field accepts a JSON Schema object from the admin (constructed from Basic mode form controls or entered directly in the Advanced mode textarea). The schema is stored as a `google.protobuf.Struct` and used by the server for field validation during resource provisioning. The UI does not execute or eval the JSON Schema — it is treated as data, not code. The Advanced mode textarea is a plain text input; the JSON is parsed and validated as well-formed before submission.

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
| Per-kind page divergence | Three sets of kind-specific pages may diverge over time | Shared components enforce consistency for common behavior; code review must verify shared component usage when adding kind-specific features. |
| Constraint editor complexity | Recursive nested constraint forms may become unwieldy for deeply nested objects | Limit nesting depth to 3 levels; show a warning when approaching the limit. |
| Three parallel API calls for list page | Loading time increases if one of the three catalog item type endpoints is slow | Show partial results as each query resolves (progressive rendering). Use `useQueries` with per-query loading states so the table populates incrementally. |

### Drawbacks

Adding a catalog management section increases the UI surface area and introduces the first role-gated navigation in osac-ui. This creates a precedent that future admin features will follow, adding complexity to the navigation and routing system. The alternative — managing catalog items exclusively via CLI — avoids this complexity but provides a poor admin experience for non-technical cloud provider administrators.

The field definitions editor is a complex custom component with no precedent in the existing UI. It combines Formik FieldArray, dynamic type-aware inputs, and nested validation — patterns that are individually well-supported but have not been combined at this scale in osac-ui. The implementation will require thorough testing to handle edge cases (validation state management, type-aware default inputs, constraint editor interactions). The admin selects which fields to include from the resource spec, which requires an add/remove mechanism but avoids forcing all fields to be configured.

The JSX composition approach shares common components across three sets of kind-specific pages. This avoids the indirection of a single config-driven component but introduces more files (three page sets instead of one). The shared components ensure consistency while allowing per-kind divergence where needed.

## Alternatives (Not Implemented)

### Wizard for catalog item creation

A PatternFly Wizard with three steps (General → Template → Field Definitions) was considered. [Research: §Architecture Patterns — Pattern 3] This approach provides step-by-step guidance and is appropriate for 3-7 step processes. It was not selected because:
- The general and template sections are short (3-5 fields total) and do not benefit from wizard navigation overhead.
- The field definitions section is the only complex section; isolating it in a wizard step does not reduce its complexity.
- Existing osac-ui create forms for similar-complexity resources (VirtualNetwork) use modals or full-page forms, not wizards. The wizard pattern is reserved for the multi-step provisioning flow (CatalogProvisionWizard).

If field definitions configuration proves too complex for a single form section during implementation, the design can be revised to use a wizard.

### Raw JSON as the sole validation editor

Using a raw JSON textarea as the **only** way to configure validation schemas (with no structured form controls) was considered. This offers maximum expressiveness but was not selected because catalog item admins are infrastructure managers, not JSON Schema experts. The Basic/Advanced dual-mode approach adopted in this design provides structured controls for common constraints (Basic mode) while still allowing power users to write arbitrary JSON Schema (Advanced mode). The Advanced mode is opt-in — Basic mode is the default experience.

### Single config-driven component for all resource types

Using a single `CatalogItemKindConfig` map to drive all polymorphic behavior through one component set was considered. This minimizes file count but creates a monolithic component that handles all three types through configuration switches. It was not selected because JSX composition is more React-idiomatic, easier to read, and handles future per-kind divergence naturally. The shared component approach achieves the same code reuse through composition rather than configuration.

### Reuse CatalogPage with per-kind tabs instead of a separate admin list page

Reusing the existing tenant-facing `CatalogPage` as a unified admin+tenant catalog view with per-resource-type tabs (Cluster / VM / Bare Metal) was considered. In this model, the "Create catalog item" button would only render for admin roles, and the active tab would determine the resource type — eliminating both the type selector ambiguity and the three-way `useAllCatalogItems` merge. This also has the advantage of using a card layout (matching the existing tenant browsing experience) rather than a table for the management view. It was not selected for this iteration because it couples admin and tenant views, making it harder to evolve admin-specific features (e.g., bulk operations, advanced filtering) independently. However, it remains a viable simplification if the separate admin list page proves unnecessary during implementation.

### Modal for create/edit instead of full page

Using a PatternFly Modal (like VirtualNetworkCreateModal) was considered. This works well for simple forms with 3-5 fields but the field definitions editor requires significant vertical space and would be cramped inside a modal. A full-page form provides enough room for the repeatable field definitions list and the expandable validation constraints editor.

## Open Questions

### 1. Scope visibility in public API responses

How does the CSP Admin determine whether a catalog item is global or tenant-scoped when the public API strips the `tenant` field? Is scope derivable from `metadata.annotations`, `creators`, or `tenants` fields in the public response? If not, does the Go proxy need to forward private API endpoints for CSP Admin users, or should the API add a `scope` field to public responses?

**Owner:** API team
**Impact:** Without scope visibility, the CSP Admin list page cannot show a "Scope" column. The current design assumes scope is derivable from public API responses and will need revision if it is not.

### 2. ~~Template parameter enumeration for field path picker~~ (Resolved)

The field definitions editor derives available fields from the resource spec (e.g., `ComputeInstanceSpec`), which is known at build time from the proto definitions. No template API enumeration is required — the admin selects which fields to include from the full resource spec.

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
- Edit flow: modify name and field definitions, verify changes persist
- Delete flow: delete a catalog item with no provisioned resources, verify removal from list
- Delete blocked: attempt to delete a catalog item with provisioned resources, verify error message
- Tenant Admin create flow: create from a global catalog item, verify restrictions (cannot make non-editable field editable)
- Tenant Admin visibility: verify global items show as read-only, org-scoped items show full actions
- Type filter: verify filtering by Cluster/VM/Bare Metal updates the table

**Unit tests:**
- Yup validation schemas: verify required fields, path format, default-required-when-non-editable rule
- FieldMask construction: verify diff-based update_mask includes only changed fields; verify field_definitions triggers whole-list replacement
- JSON Schema assembly: verify ValidationConstraintsEditor output for each constraint type (scalar, enum, list/map, nested)
- Route mapping: verify CatalogItemKind → API endpoint resolution for all three types
- Tighten-only comparison: verify constraint comparison logic rejects loosened constraints (Basic mode UI enforcement)
- Mode auto-detection: verify schemas with only Basic-supported keywords are detected as Basic; schemas with unsupported keywords are detected as Advanced
- Advanced mode JSON parsing: verify well-formed JSON is accepted; malformed JSON shows validation error

**Component-level tests (required):**
- FieldDefinitionsEditor: verify admin-selected field list renders correctly; toggle editable, set defaults, configure constraints; verify Formik state management
- ValidationConstraintsEditor: set scalar, enum, list/map, and nested constraints; verify correct JSON Schema Struct output; verify empty constraints produce omitted validationSchema
- ValidationConstraintsEditor mode switching: verify Basic→Advanced serializes structured inputs to JSON; verify Advanced→Basic parses JSON and strips unsupported keywords with warning; verify auto-detection opens correct mode based on schema content
- Advanced mode: verify well-formed JSON is accepted; verify malformed JSON shows validation error and prevents submission; verify existing CLI-created items with advanced schemas open in Advanced mode

## Documentation

Admin-facing documentation for catalog management screens will be added to the OSAC docs repo:
- A user guide covering CSP Admin and Tenant Admin workflows (create, edit, publish, delete)
- Field definitions configuration reference (available fields per resource type, constraint types, tighten-only rules)
- Troubleshooting section for common errors (delete blocked, validation failures, template not found)

The Cloud Infrastructure Admin persona is not applicable to catalog management — this feature is scoped to Cloud Provider Admins and Tenant Admins only.

## Graduation Criteria

The UI feature will be considered complete when:
- All four page types (list, create, edit, detail) are implemented and functional for all three resource types
- Role-gated navigation is working for all three roles
- The field definitions editor supports all FieldDefinition properties
- All E2E tests pass (10 Cypress scenarios listed in the Test Plan)
- Unit tests pass for Yup schemas, FieldMask construction, JSON Schema assembly, and tighten-only comparison
- Component-level tests pass for FieldDefinitionsEditor and ValidationConstraintsEditor
- The "Provisioned Resources" tab on the detail page shows related resources (dependent on Open Question 3)
- Admin user guide is published to the docs repo

## Upgrade / Downgrade Strategy

This is a new UI feature with no upgrade impact. Downgrading the UI to a version without catalog management pages simply removes the admin screens — catalog items remain manageable via CLI. No data migration is required.

## Version Skew Strategy

The UI depends on the catalog item API endpoints being available in fulfillment-service. If the UI is deployed before the catalog item API is available, the admin pages will show API error states. The Go proxy must be updated to forward the catalog item API paths if not already configured.

Since the catalog item API is already implemented, no version skew is expected for initial deployment.

## Support Procedures

- **Failure detection:** API errors surface as inline alerts on pages and toast notifications for async actions. The Go proxy logs API call failures with status code, request ID, and a sanitized error code — response bodies are redacted by default to prevent leaking tenant data, field defaults, or validation schemas.
- **Disabling:** The admin nav section can be removed by reverting the `navRowsForRole()` change. This hides the admin pages without affecting the tenant-facing catalog browse or provisioning flows.
- **Recovery:** Re-enabling the nav section restores full functionality. No state is stored in the UI — all catalog item data is in the fulfillment-service database.

## Infrastructure Needed

None. The UI runs in the existing osac-ui build and deployment pipeline. No new test infrastructure is required beyond what Cypress E2E tests already use.
