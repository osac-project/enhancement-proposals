---
title: catalog-items-ui
authors:
  - eaharoni
creation-date: 2026-07-16
last-updated: 2026-07-22
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

This design adds admin management screens to osac-ui for creating, editing, publishing, and deleting catalog items across all three resource types (Cluster, ComputeInstance, BareMetalInstance). It introduces role-gated navigation, a multi-step wizard for catalog item creation/editing, a field definitions editor component, and role-differentiated list/detail pages for Cloud Provider Admins and Tenant Admins. See the [catalog items EP](https://github.com/osac-project/enhancement-proposals/pull/115) for API and data model requirements.

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
- Support a unified admin creation flow where both Cloud Provider Admins and Tenant Admins use the same wizard to create catalog items from templates.
- Reuse existing osac-ui patterns and share common UI components across all three catalog item types using JSX composition.

### Non-Goals

- Drag-and-drop reordering of field definitions.
- Full visual JSON Schema editor (e.g., JSONJoy, react-json-schema-form-builder). The Advanced mode textarea is intentionally minimal — syntax highlighting only, no schema-aware autocomplete or visual builder.
- Changes to the existing CatalogProvisionWizard — that component already handles catalog items. Any alignment changes are tracked separately.
- Direct private API access from the browser. The Go proxy mediates all API access; CSP Admin requests are routed to private API endpoints (which return the `tenant` field), while Tenant Admin and Tenant User requests are routed to public API endpoints.

## Proposal

The design adds four new page types under a new "Administration > Catalog Management" sidebar section: a list page, a create wizard, an edit wizard, and a detail page. These pages are visible only to `providerAdmin` and `tenantAdmin` roles. The list page uses three tabs (Clusters, Virtual Machines, Bare Metal) — one per resource type — each showing a PatternFly `Gallery` of `CatalogItemCard` cards (the same card-based layout as the tenant user `CatalogPage`) with search, scope badges, publication status, and kebab actions (edit, publish/unpublish, delete). Each tab has its own "Create" button that navigates directly to the kind-specific create wizard, so the resource type is implicit and does not need to be selected in the wizard. The create flow uses a multi-step wizard whose steps mirror the provisioning wizard: General (name, description, scope, template) → Configuration (resource spec field definitions) → Networking (clusters only — pod_cidr, service_cidr) → Access (ssh_key, pull_secret). VM catalog items auto-include `network_attachments` in the API payload without showing it in the wizard; Bare Metal has no networking fields. The edit wizard reuses the same steps with template locked as read-only. The detail page shows read-only configuration, field definitions, and related provisioned resources.

Each wizard step is a separate per-kind component with static, hardcoded fields — the same pattern as the tenant user provisioning wizard. Individual fields reuse shared field definition primitives (`StringFieldDefinition`, `NumberFieldDefinition`, `ResourceSelectorFieldDefinition`, `BooleanFieldDefinition`) that each render an editable toggle, a type-appropriate default value input, and type-specific validation options. Complex fields like `node_sets` (a map of objects) use a dedicated `NodeSetsFieldEditor` that reuses the existing `ClusterNodeSetsArrayField` from the tenant user wizard. Shared page-level components (`CatalogItemGeneralFields`, `CatalogItemCard`, `CatalogItemActionsMenu`) are composed via JSX into kind-specific wizard/detail pages — each page explicitly owns its Formik wiring, validation, and submission logic.

### Workflow Description

#### Cloud Provider Admin — Create Catalog Item

1. CSP Admin navigates to **Administration > Catalog Management** in the sidebar.
2. The list page shows three tabs (Clusters, Virtual Machines, Bare Metal). Each tab shows a gallery of catalog item cards for that resource type across all tenants.
3. CSP Admin clicks the "Create" button on the active tab, which navigates to the kind-specific create wizard (e.g., `/admin/catalog/cluster/create`). The resource type is determined by the tab.
4. **Step 1 — General:** Admin enters name, description (Markdown), selects scope (Global or a specific tenant), and selects a template from a dropdown populated by the corresponding template list endpoint (e.g., `GET /v1/cluster_templates`). Selecting a template pre-populates field definitions with defaults from the template.
5. **Step 2 — Configuration:** A per-kind step component with static fields for the resource spec (excluding access and networking fields). Each field uses a shared field definition primitive (`StringFieldDefinition`, `NumberFieldDefinition`, `ResourceSelectorFieldDefinition`, `BooleanFieldDefinition`) that renders an editable toggle, a type-appropriate default value input, and type-specific validation options. Default values are pre-populated from the selected template. By default, fields are non-editable; non-editable fields require a default value. For Cluster, includes `NodeSetsFieldEditor` for configuring default node set entries (name, host type dropdown, size) and size constraints. For resource reference fields (`ResourceSelectorFieldDefinition`), the admin selects a default from a dropdown of existing resources — no validation constraints are configured.
6. **Step 3 — Networking** (clusters only): `ClusterNetworkingStep` with `pod_cidr` and `service_cidr` as `StringFieldDefinition` fields. This step is not shown for VM or Bare Metal catalog items.
7. **Step 4 — Access:** Per-kind access step component with `ssh_public_key`/`ssh_key` and `pull_secret` (clusters) as `StringFieldDefinition` fields. Both default to editable.
   For VM catalog items, the UI automatically includes `network_attachments` in the API payload as an editable field with no default or validation — it is not shown in any wizard step. Bare Metal catalog items have no networking fields.
8. Admin clicks "Create". The UI sends a POST to the appropriate catalog item endpoint with `published: false` (default).
8. The admin is redirected to the detail page for the newly created catalog item.
9. From the detail page or list page, the admin can publish the item via the kebab menu "Publish" action.

#### Cloud Provider Admin — Edit, Publish/Unpublish, Delete

- **Edit:** From the list page kebab menu or detail page, click "Edit". The edit page loads the existing catalog item data. Template selection is locked (displayed as read-only text). All other fields are editable. Save sends a PATCH with a FieldMask containing only changed fields.
- **Publish/Unpublish:** From the list page kebab menu, click "Publish" (if unpublished) or "Unpublish" (if published). This sends a PATCH with `published: true/false` and `update_mask: "published"`.
- **Delete:** From the list page kebab menu, click "Delete". A confirmation modal appears. If the catalog item has provisioned resources, the API returns an error and the UI displays an alert: "This catalog item cannot be deleted because resources have been provisioned from it. Unpublish it instead to hide it from users."

#### Tenant Admin — Create Catalog Item

The Tenant Admin uses the same wizard flow as the CSP Admin with one difference: scope is automatically set to the tenant's organization.

1. Tenant Admin navigates to **Administration > Catalog Management**.
2. The list page shows three tabs (Clusters, Virtual Machines, Bare Metal). Each tab shows a gallery of the tenant's catalog item cards alongside global items. Global items have a "Global" scope badge and no edit/delete actions in the kebab menu. Org-scoped items have an "Organization" scope badge and full actions.
3. Tenant Admin clicks the "Create" button on the active tab. The resource type is determined by the tab.
4. **Step 1 — General:** Admin enters name, description, and selects a template. Scope is automatically set to the tenant's organization (displayed as read-only text, not editable).
5. **Step 2 — Configuration:** Same as CSP Admin — resource spec field definitions (excluding access and networking fields).
6. **Step 3 — Networking** (clusters only): Same as CSP Admin — pod_cidr and service_cidr.
7. **Step 4 — Access:** Same as CSP Admin — ssh_public_key and pull_secret field definitions.
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

**Shared field definition primitives** (used by all per-kind step components):
- `StringFieldDefinition` — editable toggle, text input for default, optional regex pattern validation
- `NumberFieldDefinition` — editable toggle, number input for default, min/max validation
- `ResourceSelectorFieldDefinition` — editable toggle, dropdown of existing resources for default (from API endpoint), no validation constraints
- `BooleanFieldDefinition` — editable toggle, boolean toggle for default
- `NodeSetsFieldEditor` — dedicated editor for `node_sets` (Cluster only, see §8)

**Shared page-level components** (used by all three kinds):
- `CatalogItemGeneralFields` — name, description, scope, and template selector inputs (reused in create/edit)
- `CatalogItemCard` — reuses the existing tenant `CatalogItemCard` component, extended with scope badge, publication status, and admin kebab menu
- `CatalogItemActionsMenu` — kebab menu (publish/unpublish/delete)

**Per-kind step components** — each wizard step is a separate component with static, hardcoded fields (same pattern as the tenant user provisioning wizard). Individual fields use the shared field definition primitives above:
- `ClusterConfigurationStep`, `ClusterNetworkingStep`, `ClusterAccessStep`
- `VMConfigurationStep`, `VMAccessStep`
- `BMConfigurationStep`, `BMAccessStep`

**Kind-specific pages** compose the General fields and per-kind step components directly — Formik wiring, initial values, validation schema, submission logic, and data fetching are all explicit at the page level:

```tsx
// ClusterCatalogItemCreatePage.tsx — 4 steps (includes Networking)
const ClusterCatalogItemCreatePage = () => {
  const { data: templates, isLoading } = useClusterTemplates();
  const { mutateAsync: createClusterCatalogItem } = useCreateClusterCatalogItem();

  return (
    <Formik
      initialValues={clusterCatalogItemInitialValues}
      validationSchema={clusterCatalogItemSchema}
      onSubmit={(values) => createClusterCatalogItem(buildClusterPayload(values))}
    >
      <Wizard>
        <WizardStep name="General">
          <CatalogItemGeneralFields templates={templates} isLoading={isLoading} />
        </WizardStep>
        <WizardStep name="Configuration">
          <ClusterConfigurationStep />
        </WizardStep>
        <WizardStep name="Networking">
          <ClusterNetworkingStep />
        </WizardStep>
        <WizardStep name="Access">
          <ClusterAccessStep />
        </WizardStep>
      </Wizard>
    </Formik>
  );
};

// ComputeInstanceCatalogItemCreatePage.tsx — 3 steps (no Networking)
// Uses VMConfigurationStep and VMAccessStep.
// network_attachments is auto-included in the API payload for VM only.
// BareMetalInstanceCatalogItemCreatePage.tsx — 3 steps (no Networking, no network_attachments)
// Uses BMConfigurationStep and BMAccessStep.
```

Each kind-specific page calls its own typed hooks (`useClusterTemplates`, `useComputeInstanceTemplates`, `useBareMetalInstanceTemplates`) and passes data down to step components. Per-kind differences are explicit in each step component's static field list, not driven by configuration arrays.

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

Uses `ListPage` layout with a PatternFly `Gallery` — the same card-based layout as the tenant user `CatalogPage`. Each catalog item is rendered as a `CatalogItemCard` within a `Gallery` with `hasGutter`.

**Tabs:**

The list page uses three PatternFly `Tabs` — **Clusters**, **Virtual Machines**, **Bare Metal** — one per resource type. Each tab renders its own gallery querying the corresponding API endpoint. The active tab determines the resource type context, eliminating the need for a type filter or a resource type dropdown.

**Toolbar (per tab):**
- "Create" button — navigates to the kind-specific create route for the active tab's resource type (e.g., `/admin/catalog/cluster/create`)
- Search: `SearchInput` filtering by name (client-side via `filterCatalogItemsBySearch()`, same as tenant `CatalogPage`)
- Publication status filter: `ToggleGroup` — All / Published / Unpublished

**Card content (reuses `CatalogItemCard`):**

Each card shows:
- **Header:** Resource type icon (`CatalogItemIcon`) + catalog item title
- **Body:** Description (truncated), resource spec labels (e.g., "4 vCPU", "8 Memory"), scope badge ("Global" or "Organization"), publication status label ("Published" green / "Unpublished" gray)
- **Kebab menu:** Edit, Publish/Unpublish, Delete actions (see below)

Clicking a card opens the detail page (unlike tenant `CatalogPage` which uses a drawer).

**Kebab menu actions (per role):**

| Action | providerAdmin | tenantAdmin (org-scoped) | tenantAdmin (global) |
|--------|---------------|--------------------------|----------------------|
| Edit | Yes | Yes | No |
| Publish | Yes (if unpublished) | Yes (if unpublished) | No |
| Unpublish | Yes (if published) | Yes (if published) | No |
| Delete | Yes | Yes | No |

Tenant Admin sees global items as read-only cards with no kebab menu (or a kebab with only "View details").

**Scope display:**
- **CSP Admin:** The private API returns the `tenant` field in responses. Items with an empty `tenant` are global; items with a non-empty `tenant` are organization-scoped. The UI displays the appropriate scope badge directly from this field.
- **Tenant Admin:** The public API does not expose the `tenant` field, but scope is deterministic: items the Tenant Admin can update or delete are organization-scoped; items that return `PERMISSION_DENIED` on write operations are global. The UI derives scope from server-authored capability metadata or the item's `creators`/`tenants` fields. Global items show no edit/delete actions in the kebab menu.

#### 5. Create Pages (kind-specific wizard)

**Locations:** `libs/ui-components/src/pages/admin/cluster/ClusterCatalogItemCreatePage.tsx` (and equivalent for compute-instance, baremetal-instance)

Each kind-specific create page uses a PatternFly Wizard with Formik + Yup that explicitly composes shared step components (see §2). There is no shared `CatalogItemForm` wrapper — Formik wiring, initial values, validation schema, data fetching, and submission logic are all visible at the page level.

**Wizard steps — mirror the provisioning wizard structure:**

The wizard steps are kind-specific: VM and Bare Metal have three steps (General, Configuration, Access). Cluster has four steps (General, Configuration, Networking, Access). Resource type is not shown as a field — it is determined by the tab the admin clicked "Create" from and encoded in the route.

**Step 1: General**
- Name (`NameField`, required) — reuses the existing osac-ui `NameField` component with standard naming validation
- Description (`InputField` textarea, optional) — markdown-formatted long description
- Template (`SelectField`) — populated with templates from the corresponding template list endpoint (fetched by the page's typed hook). Selecting a template pre-populates field definitions with default values from the template's parameter definitions.
- Scope (providerAdmin only): `RadioButtonField` — Global or Tenant-scoped. If tenant-scoped, a tenant selector dropdown appears. For tenantAdmin, this step shows "Scope: Your organization" as read-only text.

**Step 2: Configuration** (per-kind step component, see §8)

Each resource type has its own configuration step component with static, hardcoded fields using shared field definition primitives. By default, fields are non-editable. Default values are pre-populated from the selected template when they exist. Non-editable fields require a default value.

- **Cluster (`ClusterConfigurationStep`):** `release_image` (`StringFieldDefinition`), `node_sets` (`NodeSetsFieldEditor`).
- **VM (`VMConfigurationStep`):** `instance_type` (`ResourceSelectorFieldDefinition`), `cores` (`NumberFieldDefinition`), `memory_gib` (`NumberFieldDefinition`), `image` (`ResourceSelectorFieldDefinition`), `boot_disk.size_gib` (`NumberFieldDefinition`), `additional_disks` (array of `NumberFieldDefinition` for size_gib), `run_strategy` (`StringFieldDefinition` with enum), `user_data` (`StringFieldDefinition` textarea), `is_windows` (`BooleanFieldDefinition`).
- **Bare Metal (`BMConfigurationStep`):** `run_strategy` (`StringFieldDefinition` with enum), `user_data` (`StringFieldDefinition` textarea).

**Step 3: Networking** (clusters only)

`ClusterNetworkingStep` with `pod_cidr` and `service_cidr` as `StringFieldDefinition` fields. This step is not shown for VM or Bare Metal catalog items. For VM catalog items, `network_attachments` is automatically included in the API payload as an editable field with no default or validation (not shown in any wizard step). Bare Metal catalog items have no networking fields.

**Step 4: Access** (per-kind step component)

- **Cluster (`ClusterAccessStep`):** `ssh_public_key` and `pull_secret` as `StringFieldDefinition` fields. Both default to editable. If the template does not provide defaults, the UI uses hardcoded defaults (empty string for both — the field definition is created with editable: true and no default value, allowing the tenant to provide their own).
- **VM (`VMAccessStep`):** `ssh_key` as `StringFieldDefinition`. Defaults to editable.
- **Bare Metal (`BMAccessStep`):** `ssh_public_key` as `StringFieldDefinition`. Defaults to editable.

**Hardcoded UI defaults:** When the selected template does not provide defaults for `pod_cidr`, `service_cidr`, `ssh_public_key`, or `pull_secret`, the UI pre-populates the default value input with hardcoded values so the admin always has a reasonable starting point:

| Field | Hardcoded Default | Notes |
|-------|------------------|-------|
| `pod_cidr` | `10.128.0.0/14` | Standard OpenShift pod CIDR |
| `service_cidr` | `172.30.0.0/16` | Standard OpenShift service CIDR |
| `ssh_public_key` | *(empty, editable)* | Tenant provides their own |
| `pull_secret` | *(empty, editable)* | Tenant provides their own |

Template-provided defaults take precedence over these hardcoded values. The hardcoded defaults are defined as constants in the per-kind step components.

**Wizard submission:**
- Validates all fields with Yup on each step transition and on final submit
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

#### 6. Edit Pages (kind-specific wizard)

**Locations:** `libs/ui-components/src/pages/admin/cluster/ClusterCatalogItemEditPage.tsx` (and equivalent for compute-instance, baremetal-instance)

Each kind-specific edit page reuses the same wizard steps as the create page with the following differences:

- Page heading shows "Edit catalog item"
- Template selection is displayed as read-only text (not editable after creation)
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
- **Field Definitions:** Read-only list showing all field definitions with: Path, Editable (Yes/No), Default Value, Validation Constraints. For `node_sets` (Cluster), shows the default node set entries (host type, size), the allow add/remove setting, and any size constraints.
- **Provisioned Resources:** Table of resources (Clusters, ComputeInstances, or BareMetalInstances) provisioned from this catalog item, fetched via the resource list endpoint with a `this.spec.catalog_item == "<id>"` CEL filter

**Header actions:**
- Edit button (navigates to edit page)
- Kebab menu with Publish/Unpublish and Delete actions
- Actions are hidden for Tenant Admins viewing global items

#### 8. Shared Field Definition Primitives and Per-Kind Step Components

**Location:** `libs/ui-components/src/components/catalogManagement/fieldDefinitions/`

Each wizard step is a separate per-kind component with static, hardcoded fields — the same pattern as the tenant user provisioning wizard. Individual fields reuse shared field definition primitives that each render an editable toggle, a type-appropriate default value input, and type-specific validation options. By default, fields are non-editable except `ssh_public_key`/`ssh_key` and `pull_secret`, which default to editable. Default values are pre-populated from the selected template when they exist. Both CSP Admin and Tenant Admin use the same step components.

**Shared field definition primitives:**

Each primitive renders a form section for a single field definition with the field path as the heading label:

| Component | Default Value Input | Validation Options | Use Cases |
|-----------|--------------------|--------------------|-----------|
| `StringFieldDefinition` | Text input (or textarea for long values) | Optional regex pattern (`pattern`) | `release_image`, `pod_cidr`, `service_cidr`, `ssh_public_key`, `ssh_key`, `pull_secret`, `user_data`, `run_strategy` (with enum) |
| `NumberFieldDefinition` | Number input | Min/max bounds | `cores`, `memory_gib`, `boot_disk.size_gib` |
| `ResourceSelectorFieldDefinition` | Dropdown of existing resources from API endpoint | None (backend validates at provisioning) | `instance_type`, `image` |
| `BooleanFieldDefinition` | Toggle switch | None | `is_windows` |

Each primitive renders:
- **Path** — read-only label (the field path from the resource spec, e.g., `cores`, `pod_cidr`)
- **Editable** — PatternFly `Switch` toggle
- **Default Value** — type-specific input. Required when `editable` is false.
- **Validation** — type-specific constraints (only for `StringFieldDefinition` and `NumberFieldDefinition`)

**Yup validation (shared across all primitives):**

```typescript
const fieldDefinitionSchema = Yup.object({
  path: Yup.string().required(),
  editable: Yup.boolean().required(),
  default: Yup.mixed().when('editable', {
    is: false,
    then: (schema) => schema.required('Default value is required for non-editable fields'),
  }),
  validationSchema: Yup.object().nullable(),
});
```

**Per-kind step components:**

Each step component is a static form that explicitly lists its fields using the shared primitives:

**Cluster:**
- `ClusterConfigurationStep` — `release_image` (`StringFieldDefinition`), `node_sets` (`NodeSetsFieldEditor`)
- `ClusterNetworkingStep` — `pod_cidr` (`StringFieldDefinition`), `service_cidr` (`StringFieldDefinition`)
- `ClusterAccessStep` — `ssh_public_key` (`StringFieldDefinition`, default editable), `pull_secret` (`StringFieldDefinition`, default editable)

**VM (ComputeInstance):**
- `VMConfigurationStep` — `instance_type` (`ResourceSelectorFieldDefinition`, endpoint: `/v1/instance_types`), `cores` (`NumberFieldDefinition`), `memory_gib` (`NumberFieldDefinition`), `image` (`ResourceSelectorFieldDefinition`), `boot_disk.size_gib` (`NumberFieldDefinition`), `additional_disks` (array of `NumberFieldDefinition` for `size_gib`), `run_strategy` (`StringFieldDefinition` with enum: "Always"/"Halted"), `user_data` (`StringFieldDefinition` textarea), `is_windows` (`BooleanFieldDefinition`)
- `VMAccessStep` — `ssh_key` (`StringFieldDefinition`, default editable)
- VM has no Networking step. `network_attachments` is auto-included in the API payload (not shown in wizard).

**Bare Metal (BareMetalInstance):**
- `BMConfigurationStep` — `run_strategy` (`StringFieldDefinition` with enum: "ALWAYS"/"HALTED"), `user_data` (`StringFieldDefinition` textarea)
- `BMAccessStep` — `ssh_public_key` (`StringFieldDefinition`, default editable)
- Bare Metal has no Networking step and no networking fields.

**Example — ClusterConfigurationStep:**

```tsx
const ClusterConfigurationStep = () => (
  <>
    <StringFieldDefinition path="release_image" label="Release Image" />
    <NodeSetsFieldEditor />
  </>
);
```

**Network attachments handling (VM only):** The `network_attachments` field is not shown in any wizard step. The UI automatically includes it in the API payload as an editable field with no default value and no validation schema. This allows tenant users to configure network attachments during VM provisioning without requiring the admin to explicitly manage them in the catalog item wizard.

**NodeSetsFieldEditor (Cluster only):**

**Location:** `libs/ui-components/src/components/catalogManagement/fieldDefinitions/NodeSetsFieldEditor.tsx`

The `node_sets` field is a `map<string, ClusterNodeSet>` where each entry has a `host_type` (string reference to a HostType resource) and a `size` (int32, number of nodes). The map key is auto-derived from the host type. Because this is a structured map of objects, it gets a dedicated editor within `ClusterConfigurationStep`.

**Default value — reuses `ClusterNodeSetsArrayField`:** The default node set entries are configured using the existing `ClusterNodeSetsArrayField` component from the tenant user cluster creation wizard. This component renders each node set as a `FormFieldGroup` with two fields: **Host Type** (`SelectField` dropdown from `useHostTypes()`) and **Nodes** (pool size, `ClusterPoolSizeField`). It supports adding entries via an "Add node set" link button and removing entries via a minus icon per row (except the first). Already-selected host types are disabled in other rows to prevent duplicates. The entries are pre-populated from the selected template's `node_sets` map.

**Admin-specific controls** (rendered above or alongside the `ClusterNodeSetsArrayField`):

- **Editable** toggle — controls whether tenant users can modify the size of existing node sets during provisioning. When non-editable, the default sizes are locked.
- **Allow add/remove** toggle — controls whether tenant users can add new node sets or remove existing ones. This is independent of the editable toggle: an admin can allow users to change sizes (editable: true) while preventing them from adding/removing node sets (allowAddRemove: false), or vice versa.
- **Size validation constraints** — minimum and maximum number inputs for the `size` field across all node sets.

**Formik state for node_sets:**

```typescript
interface NodeSetEntry {
  rowId: string;                // random UUID for React key (same as ClusterNodeSetRow)
  hostType: LabeledResourceRef; // { value: string, label: string }
  size: string;                 // number of nodes as string (same as ClusterNodeSetRow)
  sizeMin?: number;             // validation: minimum size
  sizeMax?: number;             // validation: maximum size
}

// Stored in Formik as:
// fieldDefinitions.node_sets.entries: NodeSetEntry[]
// fieldDefinitions.node_sets.editable: boolean
// fieldDefinitions.node_sets.allowAddRemove: boolean
```

On submission, the `node_sets` entries are serialized into the field definition:

```json
{
  "path": "node_sets",
  "editable": true,
  "allowAddRemove": false,
  "default": {
    "compute": { "host_type": "acme_1tb", "size": 3 },
    "gpu": { "host_type": "acme_1tb_h100", "size": 1 }
  },
  "validationSchema": {
    "type": "object",
    "additionalProperties": {
      "type": "object",
      "properties": {
        "size": { "minimum": 1, "maximum": 10 }
      }
    }
  }
}
```

**Yup validation for node_sets:**

```typescript
const nodeSetEntrySchema = Yup.object({
  rowId: Yup.string().required(),
  hostType: Yup.object({
    value: Yup.string().required('Host type is required'),
    label: Yup.string(),
  }).required(),
  size: Yup.string().required('Size is required'),
  sizeMin: Yup.number().integer().min(0).nullable(),
  sizeMax: Yup.number().integer().nullable(),
});

const nodeSetsSchema = Yup.object({
  editable: Yup.boolean().required(),
  allowAddRemove: Yup.boolean().required(),
  entries: Yup.array().of(nodeSetEntrySchema).min(1, 'At least one node set is required'),
});
```

#### 9. Validation Constraints

Validation constraints are built into each shared field definition primitive rather than being a separate component. Each primitive handles its own constraint type:

| Primitive | Validation Options | JSON Schema Output |
|-----------|-------------------|--------------------|
| `StringFieldDefinition` | Optional regex pattern text input | `{ "pattern": "regex" }` |
| `NumberFieldDefinition` | Min/max number inputs | `{ "minimum": N, "maximum": N }` |
| `ResourceSelectorFieldDefinition` | None (backend validates at provisioning) | — |
| `BooleanFieldDefinition` | None | — |
| `NodeSetsFieldEditor` | Per-entry size min/max | See §8 |

Each primitive constructs its JSON Schema from the structured inputs. When no constraints are configured, `validationSchema` is omitted from the payload (the API treats a missing or empty Struct as no validation).

**Unsupported constraint handling:**

When editing an existing catalog item (e.g., one created via CLI), each primitive inspects the field's `validationSchema`. If it contains only the keywords that primitive supports, the structured form controls are shown. If it contains unsupported keywords (e.g., `if/then/else`, `oneOf`, `$ref`), the primitive displays a read-only message: "This validation cannot be edited through the UI. Use the OSAC CLI to manage it." The existing schema is preserved unchanged.

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
      CatalogItemActionsMenu.tsx    # shared kebab menu (extends existing CatalogItemCard)
      CatalogItemGeneralFields.tsx  # shared name, description, scope inputs
      # TemplateSelector is integrated into CatalogItemGeneralFields
      CatalogItemScopeBadge.tsx
      CatalogItemStatusLabel.tsx
      catalogItemRoutes.ts          # CatalogItemKind route mapping
      fieldDefinitions/
        StringFieldDefinition.tsx   # string field with optional regex pattern
        NumberFieldDefinition.tsx   # number field with min/max validation
        ResourceSelectorFieldDefinition.tsx  # resource dropdown, no validation
        BooleanFieldDefinition.tsx  # boolean toggle
        NodeSetsFieldEditor.tsx     # node_sets map editor (Cluster only)
      steps/
        cluster/
          ClusterConfigurationStep.tsx
          ClusterNetworkingStep.tsx
          ClusterAccessStep.tsx
        compute-instance/
          VMConfigurationStep.tsx
          VMAccessStep.tsx
        baremetal-instance/
          BMConfigurationStep.tsx
          BMAccessStep.tsx
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
| Three parallel API calls for list page | Loading time increases if one of the three catalog item type endpoints is slow | Only the active tab's query is enabled; switching tabs triggers a new query. Use per-query loading states so the gallery populates when data arrives. |

### Drawbacks

Adding a catalog management section increases the UI surface area and introduces the first role-gated navigation in osac-ui. This creates a precedent that future admin features will follow, adding complexity to the navigation and routing system. The alternative — managing catalog items exclusively via CLI — avoids this complexity but provides a poor admin experience for non-technical cloud provider administrators.

Each wizard step is a per-kind component with static, hardcoded fields using shared field definition primitives (`StringFieldDefinition`, `NumberFieldDefinition`, `ResourceSelectorFieldDefinition`, `BooleanFieldDefinition`). This mirrors the tenant user provisioning wizard pattern but adds editable/default/validation controls per field. The `node_sets` field adds further complexity with its dedicated `NodeSetsFieldEditor` for map-of-objects structure. The implementation will require thorough testing to handle edge cases (validation state management, type-aware default inputs, node set add/remove). All fields from the resource spec are shown as static form fields, which simplifies the UX (no add/remove mechanism for fields) but means each per-kind step component must be kept in sync with the proto definitions.

The JSX composition approach shares common components across three sets of kind-specific pages. This avoids the indirection of a single config-driven component but introduces more files (three page sets instead of one). The shared components ensure consistency while allowing per-kind divergence where needed.

## Alternatives (Not Implemented)

### Full-page form for catalog item creation

A single full-page form with all sections visible at once (General, Template, Field Definitions) was considered. This approach was not selected because:
- The field definitions section is complex and benefits from being isolated in its own wizard step where the admin focuses on one concern at a time.
- The wizard pattern provides step-by-step guidance and validation at each step transition, catching errors early.
- The wizard aligns with the existing CatalogProvisionWizard pattern in osac-ui, providing a consistent admin experience.

### Raw JSON as the sole validation editor

Using a raw JSON textarea as the **only** way to configure validation schemas (with no structured form controls) was considered. This offers maximum expressiveness but was not selected because catalog item admins are infrastructure managers, not JSON Schema experts. The adopted approach provides structured form controls for simple constraint types, and for complex schemas that the UI cannot represent, it directs the admin to use the OSAC CLI instead. This avoids the need for a JSON textarea entirely — complex validation is a CLI concern, not a UI concern.

### Single config-driven component for all resource types

Using a single `CatalogItemKindConfig` map to drive all polymorphic behavior through one component set was considered. This minimizes file count but creates a monolithic component that handles all three types through configuration switches. It was not selected because JSX composition is more React-idiomatic, easier to read, and handles future per-kind divergence naturally. The shared component approach achieves the same code reuse through composition rather than configuration.

### Reuse CatalogPage instead of a separate admin list page

Reusing the existing tenant-facing `CatalogPage` as a unified admin+tenant catalog view was considered. This would share the exact same page component for both admin and tenant users. It was not selected because it couples admin and tenant views, making it harder to evolve admin-specific features (e.g., publication status filter, scope badges, kebab actions) independently. Instead, the admin list page reuses the `CatalogItemCard` component and `Gallery` layout from the tenant `CatalogPage` but wraps them in an admin-specific page with additional toolbar controls (publication status filter, create button) and per-card admin actions.

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

**E2E tests:**
- Role gating: verify "Administration" nav section is visible to providerAdmin and tenantAdmin, hidden for tenantUser
- Route guard: verify direct navigation to `/admin/catalog` by tenantUser redirects to `/catalog`
- CSP Admin create wizard: create a catalog item through wizard steps with field definitions, verify it appears in the list as unpublished
- Publish/unpublish: toggle publication status via kebab menu, verify status label updates
- Edit flow: modify name and field definitions, verify changes persist
- Delete flow: delete a catalog item with no provisioned resources, verify removal from list
- Delete blocked: attempt to delete a catalog item with provisioned resources, verify error message
- Tenant Admin create wizard: create a catalog item through the same wizard as CSP Admin, verify template selection and field definitions work identically
- Tenant Admin visibility: verify global items show as read-only, org-scoped items show full actions
- Tabs: verify switching between Clusters/VM/Bare Metal tabs shows the correct catalog items per type

**Unit tests:**
- Yup validation schemas: verify required fields, path format, default-required-when-non-editable rule
- FieldMask construction: verify diff-based update_mask includes only changed fields; verify field_definitions triggers whole-list replacement
- Validation constraints: verify each field definition primitive produces correct JSON Schema output (pattern for strings, min/max for numbers)
- Route mapping: verify CatalogItemKind → API endpoint resolution for all three types
- Unsupported schema detection: verify schemas with unsupported keywords show read-only "use CLI" message; schemas with only supported keywords show structured controls
- Network attachments auto-inclusion (VM only): verify `network_attachments` is excluded from VM wizard but included in API payload as editable with no default or validation; verify Bare Metal has no networking fields; verify Cluster uses pod_cidr/service_cidr in Networking step
- NodeSetsFieldEditor: verify node set entries pre-populate from template; verify add/remove; verify host type dropdown; verify size constraints serialization; verify at least one entry required

**Component-level tests (required):**
- Per-kind step components: verify each step renders correct static fields for its resource type; verify field definition primitives render editable toggle, default value, and validation; verify ssh_key/pull_secret default to editable in Access steps
- Field definition primitives: verify StringFieldDefinition renders regex pattern option; verify NumberFieldDefinition renders min/max; verify ResourceSelectorFieldDefinition renders dropdown from API; verify BooleanFieldDefinition renders toggle
- NodeSetsFieldEditor (Cluster only): verify node set entries pre-populate from template; verify add/remove entries; verify host type dropdown fetches from HostTypes API; verify size validation (min/max); verify at least one node set required; verify serialization to field definition payload
- Validation constraints per primitive: verify StringFieldDefinition produces correct pattern schema; verify NumberFieldDefinition produces correct min/max schema; verify empty constraints produce omitted validationSchema
- Unsupported schema handling: verify existing CLI-created items with complex schemas show read-only "use CLI" message; verify supported schemas show editable structured controls

## Documentation

Admin-facing documentation for catalog management screens will be added to the OSAC docs repo:
- A user guide covering CSP Admin and Tenant Admin workflows (create, edit, publish, delete)
- Field definitions configuration reference (available fields per resource type, constraint types)
- Troubleshooting section for common errors (delete blocked, validation failures, template not found)

The Cloud Infrastructure Admin persona is not applicable to catalog management — this feature is scoped to Cloud Provider Admins and Tenant Admins only.

## Graduation Criteria

The UI feature will be considered complete when:
- All four page types (list, create wizard, edit wizard, detail) are implemented and functional for all three resource types
- Role-gated navigation is working for all three roles
- All per-kind step components render the correct static fields with shared field definition primitives
- All E2E tests pass (scenarios listed in the Test Plan)
- Unit tests pass for Yup schemas, FieldMask construction, JSON Schema assembly, and network attachments auto-inclusion
- Component-level tests pass for per-kind step components and field definition primitives
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

None. The UI runs in the existing osac-ui build and deployment pipeline.
