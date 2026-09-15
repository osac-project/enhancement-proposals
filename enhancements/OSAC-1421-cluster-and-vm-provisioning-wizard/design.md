---
title: cluster-and-vm-provisioning-wizard
authors:
  - brotman@redhat.com
creation-date: 2026-06-22
last-updated: 2026-07-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1421
prd:
  - prd.md
see-also:
  - /enhancements/OSAC-1002-catalog-items
  - /enhancements/OSAC-46-vm-instance-types
replaces:
  - N/A
superseded-by:
  - N/A
---

# Configuration Wizard for Cluster and VM Resources

## Summary

Rewrite the osac-ui catalog provision wizard with static fields per resource type, a fixed five-step flow (Catalog Item → General → Configuration → Networking → Review), catalog overlay on Configuration and Networking non-picker fields only, Formik/Yup validation with validate-all-on-Next, `OsacForm` layout wrapper, i18n for all user-visible strings, and dedicated create pages (`/vms/create`, `/clusters/create`) with list-page breadcrumbs. Each adapter supplies its own Configuration and Networking step components. See [PRD](prd.md) for field-level requirements.

### Goals

- Rewrite `catalogProvision/` with Formik/Yup, PatternFly Wizard, `OsacForm`, i18n (`useTranslation`), shared Formik-connected field components, and per-adapter Configuration/Networking step components.
- Host the wizard on routed create pages; list **Create** navigates to `/vms/create` or `/clusters/create`.
- Implement the cluster adapter end-to-end (catalog, ClusterTemplate-backed `node_sets` table, create).
- Next always enabled; validate every field on the current step when Next is clicked, including fields that have not blurred.
- On successful create, navigate to the VM or cluster Details page using `id` from the POST response (`/vms/{id}`, `/clusters/{id}`).
- Component tests (Vitest + jsdom + Testing Library) cover step validation, Back navigation with preserved values, Cancel/discard guard, and submit error paths for both VM and cluster adapters (see [Test Plan](#test-plan)).

## Proposal

Rewrite under `osac-ui/apps/app-frontend/src/components/catalogProvision/`. `CatalogProvisionWizard` embeds in create pages and owns shared steps (Catalog Item, General, Review). **Configuration** and **Networking** are adapter components — VM pickers and cluster `node_sets`/CIDR fields are not shareable.

Static field paths are hardcoded per resource type (PRD §2.1.1). Catalog `field_definitions` overlay matching static paths on **Configuration**, **Networking** non-picker fields, and **General basics** fields (`ssh_key`, `ssh_public_key`, `pull_secret`) for `display_name`, `editable`, and `validation_schema`. VM picker-backed paths (`spec.instance_type`, `spec.network_attachments` and nested paths) remain API-driven in v1. Cluster `spec.node_sets` is template-backed: the wizard loads the resolved ClusterTemplate and applies Catalog policy only to node-set sizes. Create payloads include only PRD §2.1.1 paths plus catalog item reference; VM hardcodes `spec.image.source_type` = `registry`.

New hooks in `libs/ui-components/src/api/v1/`: instance types, virtual networks, subnets, cluster catalog items, ClusterTemplates.Get, and cluster create. VM picker fields depend on fulfillment-service `spec.instance_type` and `spec.is_windows` (PRs #735, #734). Cluster Configuration uses `ClusterTemplates.Get` for the authoritative node-set map and typed BareMetalInstanceType references; it does not offer a separate hardware picker.

### Workflow Description

Tenant user on `/vms` or `/clusters` clicks **Create** → navigates to the create route → wizard with breadcrumb (list label → **Create**). Cancel or breadcrumb back uses an unsaved-progress guard.

```mermaid
sequenceDiagram
  participant User
  participant ListPage as List page
  participant CreatePage as Create page
  participant DetailsPage as Details page
  participant Wizard
  participant API as fulfillment-service

  User->>ListPage: Create
  ListPage->>CreatePage: navigate /vms/create or /clusters/create
  User->>Wizard: Select catalog item
  Wizard->>API: GET catalog_items
  User->>Wizard: Next (validate step)
  User->>Wizard: Submit
  Wizard->>API: POST compute_instances or clusters
  API-->>Wizard: 200 + created object (id)
  CreatePage->>DetailsPage: navigate /vms/{id} or /clusters/{id}
```

| Step | Owner | Content |
|------|-------|---------|
| Catalog Item | Shared | `adapter.useCatalogItems()` |
| General | Shared | Name (required), optional SSH key (catalog `ssh_key` overlay); cluster adds required pull secret and optional `ssh_public_key` overlay |
| Configuration | Adapter | VM: image, OS family, instance type, user data, boot disk, run strategy. Cluster: release image, template-defined `node_sets` table with Catalog-governed sizes |
| Networking | Adapter | VM: VN → subnet → SG pickers (single `network_attachments` entry carrying `ComputeNetworkAttachment`). Cluster: pod/service CIDR; the optional `network_attachment` field carries a `ClusterNetworkAttachment` and is omitted by the v1 wizard |
| Review | Shared | `adapter.getReviewSections()` — same labels and values as wizard steps; submit via `buildCreatePayload` |

Register `/vms/create` and `/clusters/create` before `:id` routes. On failure: inline errors on the step; any non-2xx create response stays on Review; deprecated instance type warnings from create response are non-blocking and surfaced after submit.

**Catalog overlay (non-picker Configuration/Networking fields and General basics):**

| Aspect | Matching `field_definitions` entry | No matching entry |
|--------|-----------------------------------|-------------------|
| Label | `display_name` or wizard default | Wizard default |
| Editable | `editable: false` → read-only control | Editable |
| Default | Catalog `default` when set; else blank (Configuration, Networking, and General basics) | Blank |
| Validation | `validation_schema` merged into Yup | API/wizard validation |

Non-editable fields without a catalog `default` render blank and read-only (disabled control, same widget type). Fields with a catalog `default` render with the parsed default on catalog selection — read-only when `editable: false`, editable when `editable: true` — and include the wizard value in the client payload when non-blank.

**Fulfillment create (`applyFieldDefinitions`):** The wizard prefills and sends basics values from catalog `default` when present. If the tenant clears an optional basics field, the client omits it from the POST body; fulfillment may still apply the catalog `default` server-side when defined.

**Wizard defaults** (when no catalog `default`):

| Field | Default |
|-------|---------|
| `spec.run_strategy` | `Always` |
| VM OS family (`spec.is_windows`) | Linux (`false`); wizard always sends an explicit value |
| Instance type picker | Auto-select when `InstanceTypes.List` returns exactly one option |
| Networking pickers | Auto-select when a list returns exactly one option (VN → subnet) |

**VM Configuration specifics:** `spec.user_data` and `spec.boot_disk.size_gib` are optional — omit from payload when empty. `spec.is_windows` (OS family) uses `RadioButtonField` (Linux / Windows); wizard always sends an explicit value. `spec.instance_type` sends the type name only (not `cores`/`memory_gib`). Instance type labels show `metadata.name`, cores, memory, and **DEPRECATED** when applicable; OBSOLETE types excluded from the picker.

**VM General specifics:** `spec.ssh_key` is optional — prefill catalog `default` on catalog selection when defined; merge catalog `ssh_key` `field_definition` for label, `editable`, and `validation_schema`. Omit from client payload only when blank (tenant cleared or no catalog default). When non-blank, send the parsed plain string (prefilled default or user edit).

**VM Networking specifics:** Load the VN list first; on selection, filter the Subnet list with `this.spec.virtual_network.name == "<vn-name>"`. The picker stores the selected Subnet name and assembles one `network_attachments` element using the OSAC-1330 typed local reference: `{ "subnet": { "name": "<subnet-name>" } }`. The effective NetworkACL is inherited from the selected Subnet; the wizard does not select or send an ACL reference. The virtual network name is not sent in the attachment payload. Although the direct VM API permits omission or an empty list and then applies tenant defaults, the v1 wizard requires an explicit picker selection and always sends one entry; “use defaults” is not a separate wizard option.

**VM instance-type specifics:** The picker stores the selected instance-type
name and the payload emits `spec.instance_type: { "name": "<type-name>" }`.
Identifier-only values are not accepted under OSAC-1330; `cores` and
`memory_gib` are not emitted.

**Cluster Configuration specifics:** After Catalog Item selection resolves the ClusterTemplate, call `ClusterTemplates.Get` and render exactly the template's `spec.node_sets` map. The map key and each typed `baremetal_instance_type` reference are read-only; no **Add node set**, **Remove**, hardware picker, or alternate hardware selection is available. The `size` field is editable only when the effective Catalog Item policy permits it and must remain > 0. `buildClusterCreatePayload` preserves the template node-set names and emits each `baremetal_instance_type` as a typed reference object such as `{ "name": "bm-standard" }`. Review shows the template node-set name, hardware reference, and effective node count. A missing or malformed template node set blocks create; there is no tenant-composed fallback.

**Cluster General specifics:** `spec.ssh_public_key` and `spec.pull_secret` follow the same General basics overlay rules as VM `spec.ssh_key` (prefill catalog `default`, label, editable, validation). `spec.pull_secret` remains required on the wizard when no catalog rule makes it optional.

**Cluster Networking specifics:** `spec.network.pod_cidr` and
`spec.network.service_cidr` are optional cluster-internal network settings —
omit them from the payload when empty, and validate format only when a value is
present. The wizard does not expose the CaaS tenant-facing
`spec.network_attachment` (`ClusterNetworkAttachment`) or
`spec.auto_external_ip_attachment` controls in
v1, so it sends neither field. The server applies the normal
Catalog/Template/default resolution for the omitted attachment (using tenant
defaults when no higher-precedence value exists) and the normal omitted-value
behavior for automatic external access (normally `false`). Explicit CaaS
Subnet selection or automatic external access remains available through the
direct API/CLI. NetworkACL association is managed by the NetworkACL resource
and is inherited from the selected Subnet.

**Step validation:** Next is always enabled. On click, run the step Yup schema, `setTouched` for all step fields, surface inline errors for untouched fields, and show an alert if invalid; do not advance until the step passes.

### API Extensions

No API extensions to create payloads. The wizard consumes existing `ComputeInstanceCatalogItems`, `ClusterCatalogItems`, `ClusterTemplates.Get`, `InstanceTypes`, networking list APIs (`GET /api/fulfillment/v1/virtual_networks`, `.../subnets`), and create APIs. Server-side catalog validation (`catalog_item_validation.go` / `applyFieldDefinitions`) still applies Catalog size policies on create. The wizard does not call `BareMetalInstanceTypes.List` for cluster node-set hardware.

### Implementation Details/Notes/Constraints

**Routing and pages:** `VmCreatePage` / `ClusterCreatePage` host the wizard, breadcrumbs, and provision handler. List pages drop the embedded wizard and `wizardRef.open()`. The wizard drops portal (`createPortal`), imperative handle, and overlay CSS.

**Post-submit navigation:** On successful `POST`, read `id` from the response body. Navigate to `/vms/{id}` or `/clusters/{id}`. If `id` is missing, stay on Review with an error. Surface create warnings (e.g. deprecated instance type) via transient alert before navigation or on the Details page.

**Adapter interface:**

```typescript
interface CatalogProvisionAdapter<TItem, TValues, TPayload> {
  kind: CatalogProvisionKind;
  useCatalogItems: () => UseQueryResult<TItem[]>;
  getInitialValues: (catalogItem: TItem | null) => TValues;
  buildCreatePayload: (values: TValues, catalogItem: TItem) => TPayload;
  ConfigurationStep: ComponentType<{ catalogItem: TItem | null }>;
  NetworkingStep: ComponentType<{ catalogItem: TItem | null }>;
  generalFields: GeneralFieldDescriptor[];
  resolveGeneralFields?: (catalogItem: TItem | null) => GeneralFieldDescriptor[];
  getWizardSchema: (fieldDefinitions: FieldDefinition[]) => AnyObjectSchema;
  getStepFieldPaths: (stepId: WizardStepId) => string[];
  getReviewSections: (values: TValues, catalogItem: TItem) => ReviewSection[];
  onCatalogItemSelected?: (item: TItem, helpers: FormikHelpers<TValues>) => void | Promise<void>;
}
```

**Module layout:**

```text
libs/ui-components/src/components/form/
  InputField, SelectField, RadioButtonField — shared Formik-connected controls (reusable outside wizard)
wizard/
  adapters/
    computeInstanceAdapter.ts, clusterAdapter.ts, types.ts
    computeInstance/  VmConfigurationStep, VmNetworkingStep, fields.ts, schemas.ts
    cluster/            ClusterConfigurationStep, ClusterNetworkingStep, fields.ts, schemas.ts
```

**Shared form field components:** Wizard steps render inputs through shared components under `libs/ui-components/src/components/form/` that bind to the parent `<Formik>` context — not local `useState` or manual `value`/`onChange` props. These live in `@osac/ui-components` so other forms can reuse them. At minimum:

| Component | PatternFly control | Formik binding |
|-----------|-------------------|----------------|
| `InputField` | `TextInput`, `TextArea` | `name` → `useField` (or `<Field>`); `value`, `onChange`, `onBlur` from Formik; `meta.error` / `meta.touched` for inline validation |
| `SelectField` | `FormSelect` | Same; `options` prop for `FormSelectOption` list |
| `RadioButtonField` | `Radio`, `RadioGroup` | Same; `options` prop for labeled choices (e.g. VM OS family: Linux / Windows → `spec.is_windows`) |

Each component wraps a PatternFly `FormGroup` (label, `fieldId`, `isRequired`, helper text for errors). Props include `name` (Formik path), `label` (already-translated string from the step), `isRequired`, `isDisabled` / `readOnly` (catalog `editable: false`), and widget-specific options (e.g. `multiline`, `type="number"`, `isPassword` for pull secret; `options` with `value` / `label` for `SelectField` and `RadioButtonField`). Adapter and shared steps compose these components inside `OsacForm`; picker-backed fields may use `SelectField` or thin wrappers (e.g. `PickerSelectField`) that still source value and errors from Formik.

**`OsacForm` wrapper:** Every wizard step that renders editable fields wraps its field list in `OsacForm` from `@osac/ui-components` (`libs/ui-components/src/components/Form/OsacForm.tsx`) — not raw PatternFly `Form`. `OsacForm` provides responsive grid layout and blocks native submit; wizard navigation stays on PatternFly Wizard footer buttons. ESLint already requires `OsacForm` over direct `Form` imports in osac-ui.

**i18n:** All user-visible wizard copy uses i18next via `useTranslation` from `@osac/ui-components/hooks/useTranslation` (never import from `react-i18next` directly). Use hardcoded string keys in `t('...')` so `pnpm i18n` can extract keys into `libs/i18n/locales/en/translation.json` (committed with source changes; CI fails if out of sync). Apply to step titles, intros, field labels (wizard defaults), buttons, validation alert text, template-node-set loading/validation and size-policy messages, and Review section headings. Catalog `display_name` from `field_definitions` overrides the wizard default label when present and is shown as-is (server-provided, not passed through `t()`). Pure helpers (e.g. `getReviewSections`, static field descriptors) accept `t: TFunction` from the calling component rather than calling `useTranslation` internally.

Adapter steps use Formik context, own API hooks and loading UI, and export Yup fragments. Shared helpers: `buildWizardSchema` (compose adapter fragments + overlay merge for non-picker Configuration/Networking paths and General basics), `applyCatalogOverlay`, `validateStepFields` (subset validation for the current step). Paths use PRD `spec.*` notation; wire builders output camelCase OpenAPI shapes.

**Formik/Yup:** Single `<Formik>` in the orchestrator with one wizard-level Yup schema from `adapter.getWizardSchema(fieldDefinitions)` — not per-step schemas. A single schema lets future cross-step rules reference values from any step (e.g. Networking validation depending on Configuration choices) without re-plumbing. Validate-on-Next runs Yup against only the current step's field paths via `adapter.getStepFieldPaths(stepId)` while the full schema retains access to all `values`. Each step body: `OsacForm` → shared `InputField` / `SelectField` / `RadioButtonField` from `@osac/ui-components` bound to Formik state — no raw PatternFly `Form` and no duplicated error wiring. Overlay merge applies to General basics and non-picker Configuration and Networking fields. `editable: false` passes `isDisabled` to field components; catalog `default` is applied to Formik on catalog selection when present; merge `validation_schema` into Yup for the supported JSON Schema subset. Validate-on-Next uses the same Formik `errors` / `touched` state those components display. Yup validation messages that surface to the user should use i18n keys where the schema supports message overrides.

**Catalog item change:** Do not use `enableReinitialize` — it would reset user edits whenever `initialValues` changes. Instead, `onCatalogItemSelected` explicitly calls `resetForm({ values: getInitialValues(item) })`, fetches the resolved ClusterTemplate for a cluster, and applies Catalog defaults so reinitialization happens only on intentional catalog selection, not on unrelated parent re-renders. The ClusterTemplate supplies the node-set names and typed hardware references; Catalog policy supplies only the permitted size behavior.

**PRD §5 decisions (v1):** Ignore catalog `field_definitions` on VM picker-backed paths (`spec.instance_type`, `spec.network_attachments`, and nested networking paths). Cluster `node_sets` are template-owned; Catalog policy can govern only node-set `size`. No wizard UI for `spec.additional_disks` — boot disk only. PRD `?` fields are **optional**: `spec.boot_disk.size_gib`, `spec.network.pod_cidr`, and `spec.network.service_cidr` — omit from payload when blank. `spec.ssh_key` / `spec.ssh_public_key` are optional basics fields — prefill catalog `default` when defined; omit from client payload only when blank.

**Removed:** `partitionFieldDefinitions`, generic `ConfigurationStep`/`CatalogFieldInput`, `canProceedWizardStep`, text-based networking rows, catalog-driven field discovery. Replaced by static field tables, `OsacForm`, and Formik-connected `InputField` / `SelectField` / `RadioButtonField` components.

Update `docs/specs/ui-flows/catalog-provision-wizard.yaml` for routed create pages and the five-step flow. Run `pnpm i18n` after adding or changing wizard strings.

### Security Considerations

No auth changes. Session-scoped REST via the generated OpenAPI client; tenant isolation is enforced server-side. Sensitive fields (pull secret) are masked on the General step; no localStorage persistence of draft values.

### Failure Handling and Recovery

| Failure | User sees |
|---------|-----------|
| Catalog / template / picker API error | Step or field error; refetch |
| Step validation | Inline errors on all invalid fields + alert; no advance |
| Create non-2xx | Error on Review |
| Create 2xx without `id` | Error on Review |
| Create 2xx with `id` | Navigate to Details page; show non-blocking warnings if present |
| Cancel / browser back with draft | Discard confirmation → list |

No server writes until create succeeds.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Large rewrite vs incremental patch | Fixed PRD field set and step model make incremental patching brittle; adapters isolate VM/cluster divergence; component tests lock navigation, validation, and state-retention flows |
| PatternFly modal / picker behavior in jsdom | Shared `wizardFlow.helpers.ts`; test-setup mocks (`matchMedia`, `ResizeObserver`); manual smoke for visual regressions |
| fulfillment-service version skew (`instance_type`, `is_windows`) | Coordinate osac-installer image pins; document in Version Skew Strategy |
| Catalog overlay edge cases on read-only fields without defaults | PRD defines blank read-only UX; test with catalog items that lock fields without defaults |
| Cluster provision with no node sets defined | Configuration validation requires at least one row before Next; surface inline errors on the table |

## Test Plan

### Unit tests (existing pattern)

Keep pure-logic coverage in colocated `*.test.ts` files under `libs/ui-components/src/components/catalogProvision/wizard/`:

- `validateStep.test.ts` — Yup subset validation, nested `errors` / `touched` mapping.
- `wizardBuild.test.ts` — step ordering, `buildCreatePayload` shape, catalog overlay on non-picker fields.
- Adapter `schemas.ts` / `payload.ts` — Yup fragments and payload omission rules for optional fields.

Run with `pnpm test` from `osac-ui/`; CI must pass.

### Component tests (new)

Vitest + jsdom + `@testing-library/react` + `@testing-library/user-event`. Config in `apps/app-frontend/vitest.config.ts`; run with `pnpm test` from `osac-ui/`.

Render the wizard (or a step) in a shared harness: `QueryClientProvider`, i18n provider, mock `ApiFetch`, and mocked list/create responses. Query by **role/label** (accessible names from field labels / i18n). Use `await userEvent.*` for interactions.

**Shared helpers** (`catalogProvision/test/`):

```text
fixtures.ts              — catalog items, templates, picker list responses
wizardFlow.helpers.ts    — fillGeneralStep, clickWizardNext/Back/Cancel, advanceTo*Step
renderWizard.tsx         — RTL render + providers
createMockApiFetch.ts    — protobuf-aware API fixtures
```

**File layout:**

```text
libs/ui-components/src/components/catalogProvision/
  test/                                    — shared fixtures + flow helpers
  CatalogProvisionWizard.test.tsx          — validation, navigation, cancel, submit
  wizard/adapters/computeInstance/
    VmConfigurationStep.test.tsx
    VmNetworkingStep.test.tsx
    schemas.test.ts
  wizard/adapters/cluster/
    ClusterConfigurationStep.test.tsx
    ClusterNetworkingStep.test.tsx
apps/app-frontend/src/pages/
  VmCreatePage.test.tsx
  ClusterCreatePage.test.tsx
```

#### Validation and step gating

| Scenario | Assert |
|----------|--------|
| Next on Catalog Item with no selection | Inline error + step alert; remain on Catalog Item |
| Next on General with empty required name (and cluster pull secret) | Errors on all required fields **without prior blur**; alert visible; no advance |
| Next on Configuration with missing required VM fields (`source_ref`, instance type, etc.) | Field-level errors; step does not change |
| Invalid CIDR format on cluster Networking (value present) | Format error on offending field; no advance |
| Invalid catalog `validation_schema` on overlay field | Merged Yup rule fires on Next |
| Valid step after errors | Fix values → Next advances; errors clear on corrected fields |
| ClusterTemplate fetch fails or returns no valid `node_sets` | Configuration blocks Next; template error is shown and no tenant-composed fallback is offered |
| Cluster node-set hardware differs from the resolved Template | Read-only hardware value cannot be changed; create is blocked if the Template reference is invalid |
| Catalog size policy locks or defaults a Template node set | Size control reflects the policy and the emitted payload preserves the Template map key and typed hardware reference |

#### Back navigation and form state

| Scenario | Assert |
|----------|--------|
| General → Configuration → Back | Name, SSH key, pull secret (cluster) unchanged in inputs |
| Configuration → Networking → Back | Release image, template node-set names, typed hardware references, and sizes preserved |
| Networking → Review → Back | Picker selections and CIDR values preserved |
| Review → Back through all steps | Every field still matches values entered earlier |
| Change catalog item after editing | `onCatalogItemSelected` resets to `getInitialValues`; prior edits discarded |
| Catalog overlay read-only field | Value from catalog `default` shown; input disabled; value still present after Back |

#### Cancel, breadcrumb, and discard guard

| Scenario | Assert |
|----------|--------|
| Cancel with pristine wizard | Navigate to list (`/vms` or `/clusters`); no confirmation modal |
| Cancel after editing any field | Discard confirmation modal; **Stay** closes modal and keeps wizard + edits |
| Cancel → **Discard** | Navigate to list; no create API call |
| Breadcrumb list link with dirty form | Same confirmation as Cancel; confirm returns to list |
| Browser/history back with dirty form | Same guard (if wired on create page) |

#### Forward navigation and Review

| Scenario | Assert |
|----------|--------|
| Happy path VM | Select catalog item → fill required fields on each step → Review shows same labels/values as steps |
| Happy path cluster | Catalog resolves a ClusterTemplate; wizard loads its node sets, applies size policy, and Review lists each template node-set name, typed BareMetalInstanceType, and size |
| Optional basics / config fields left blank | Review shows empty/omitted state; client payload omits those keys (assert via mocked create handler) |
| Catalog ssh_key default on select | General SSH field prefilled with parsed catalog default; create payload includes plain-string `ssh_key` unless tenant clears the field |
| Single-option picker lists | Instance type / VN / subnet / SG auto-selected; value visible on Review after Back |

#### Submit and API errors

| Scenario | Assert |
|----------|--------|
| Review Submit success (mock 2xx + `id`) | Create called once with `buildCreatePayload` shape; navigate to `/vms/{id}` or `/clusters/{id}` |
| Create non-2xx | Remain on Review; error message surfaced; form values unchanged |
| Create 2xx without `id` | Remain on Review; error surfaced |
| Catalog / template / picker hook error | Step-level error state; refetch control or message (per adapter step test) |
| Deprecated instance type warning in create response | Non-blocking warning shown; navigation still proceeds when `id` present |

#### Adapter-specific component tests

- **VM Configuration:** OS family radio toggles `spec.is_windows`; obsolete instance types excluded from picker options.
- **VM Networking:** The Subnet list filters after VN selection; changing VN clears the dependent Subnet unless auto-select applies. The effective NetworkACL is inherited from the selected Subnet and is not an attachment picker.
- **Cluster Configuration:** `ClusterTemplates.Get` supplies the node-set map; node-set names and typed `baremetal_instance_type` references are read-only; Catalog policy controls only `size`; invalid/missing template node sets block progression; payload preserves template map keys and nested reference objects.
- **Cluster Networking:** Optional CIDR fields — empty allowed; invalid format blocked on Next only when non-empty.

Component tests are required for merge; add cases when fixing wizard regressions.

### i18n and lint

- `pnpm lint` and `pnpm i18n` pass after wizard string changes.
- Component tests use the same i18n provider as the app so labels resolve consistently in queries.

### Manual smoke

End-to-end VM and cluster provision via `/vms/create` and `/clusters/create`; cluster wizard with a resolved ClusterTemplate and Catalog size policy; verify typed nested network references and template-owned node sets in the create request and Details page after successful create.
