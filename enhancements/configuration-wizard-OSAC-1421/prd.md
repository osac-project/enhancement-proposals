# Configuration Wizard for Cluster and VM Resources

| Field     | Value |
|-----------|-------|
| Author(s) | Bat-Zion ROtman |
| Date      | 2026-06-14 |

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant users provision VMs and clusters by selecting a catalog offering, completing a short guided wizard, and submitting — without seeing the full resource spec.
- All configurable fields and select options are driven by the selected catalog item's `field_definitions`; the wizard adds no resource-specific form fields beyond the fixed Basics step.
- A single wizard implementation flow for both ComputeInstance and Cluster catalog item types.

### 2.2 Non-Goals

- Dynamic Template parameters - not supported for 0.1
- Fetching select or list options from separate fulfillment list APIs (`virtual_networks`, `subnets`, etc.) when not defined in the catalog item's `field_definitions`.
- Admin, fulfillment API, or publish-time validation that catalog items include required credential paths in `field_definitions`.
- Specialized form widgets for JSON Schema types beyond integer (number input), enum (select), and plain text for all other types.

## 3. Requirements

### 3.1 Functional Requirements

#### Wizard structure

The wizard guides tenant users from catalog selection through submit in four steps.

```mermaid
flowchart LR
  A[Catalog Selection] --> B[Basics]
  B --> C[Configuration]
  C --> D[Review]
  D --> E[Submit Create]
```

- **FR-1:** The OSAC UI must provide a catalog-item-driven provisioning wizard for ComputeInstance and Cluster resources.
- **FR-2:** After the user opens the wizard, the flow must consist of four steps in order: (1) catalog selection, (2) Basics, (3) Configuration, (4) Review — then submit.

#### Catalog selection (step 1)

- **FR-4:** Step 1 must present published catalog items for the target resource type (ComputeInstance or Cluster) and require the user to select one catalog item before proceeding.

#### Basics (step 2)

- **FR-5:** Step 2 (Basics) must always collect `metadata.name`. 
- **FR-6:** Step 2 must collect SSH credentials per resource type: cluster — `spec.ssh_public_key`; VM — `spec.ssh_key`.
- **FR-7:** Step 2 must collect `spec.pull_secret` for cluster catalog items; pull secret must be omitted for VM catalog items where not applicable.

#### Configuration (step 3)

- **FR-8:** Step 3 must render every **editable** entry in the selected catalog item's `field_definitions` array in array order, excluding fields already collected in Basics (`metadata.name`, SSH key, pull secret when shown).
- **FR-9:** Step 3 must not render **non-editable** `field_definitions`; their `default` values must be included silently in the create payload.
- **FR-10:** The Configuration step must include only fields defined in the selected catalog item's `field_definitions`.

#### Review (step 4)

- **FR-11:** Step 4 (Review) must display every entry from `field_definitions`: non-editable fields with their default values, and editable fields with the values the user configured in Basics and Configuration.
- **FR-12:** Review must not display fields that are not present in `field_definitions`.

#### Field rendering

- **FR-14:** For each editable field in Configuration, the wizard must derive the input widget from the field's `validation_schema` (JSON Schema draft 2020-12): `type: integer` → number input; `enum` present → select; all other types → plain text input.
- **FR-15:** Select and list options for every select field must come from the `enum` values in that field's `validation_schema` within `field_definitions`. The wizard must not call separate fulfillment list APIs to populate options.
- **FR-18:** When a field fails `validation_schema` validation, the wizard must show the error inline on that field. The user must not be able to proceed to the next step (Next) until all validation errors on the current step are resolved. 

#### Create payload

- **FR-16:** On submit, the create request must include tenant-provided values from Basics and Configuration plus default values for all non-editable `field_definitions`.
- **FR-17:** Field paths in the payload must match the `path` values defined in `field_definitions` (dot-notation spec paths).

### 3.2 Non-Functional Requirements

- **NFR-1:** The wizard must consume catalog item data from the fulfillment catalog item APIs (`ComputeInstanceCatalogItem`, `ClusterCatalogItem`) including `field_definitions`, `display_name`, `editable`, `default`, and `validation_schema`.
- **NFR-2:** Client-side field validation must honor each editable field's `validation_schema`. Validation failures must be shown inline per field and must block Next on the current step until all errors are cleared; the same rule applies before submit from Review.
- **NFR-3:** The wizard must not expose spec fields, API surfaces, or fulfillment list endpoints beyond what `field_definitions` defines, except for the fixed Basics fields in FR-5 through FR-7.

## 4. Acceptance Criteria

- [ ] Selecting a ComputeInstance or Cluster catalog item and completing the wizard creates the resource without exposing spec fields outside `field_definitions` (except Basics fields per FR-5–FR-7).
- [ ] The wizard presents four steps in order: catalog selection → Basics → Configuration → Review → submit.
- [ ] Basics collects `metadata.name`, SSH key, and pull secret (cluster only; omitted for VM when not applicable).
- [ ] Configuration shows only editable `field_definitions` in array order, excluding Basics fields; non-editable defaults are applied to the payload without appearing in the form.
- [ ] Review displays every `field_definitions` entry: non-editable fields with defaults, editable fields with configured values; no fields outside `field_definitions` appear.
- [ ] Integer fields render as number inputs; enum fields render as selects whose options match `validation_schema` enum values; all other field types render as plain text inputs.
- [ ] No select field options are sourced from fulfillment list APIs (`virtual_networks`, `subnets`, etc.).
- [ ] The wizard supports provisioning for both ComputeInstance and Cluster catalog item types.
- [ ] Validation errors from `validation_schema` appear inline on the offending field; Next is disabled until every error on the current step is resolved.
- [ ] Submitting from Review sends a create request that merges tenant inputs and non-editable defaults.

## 5. Dependencies

- **Catalog item APIs:** Published `ComputeInstanceCatalogItem` and `ClusterCatalogItem` resources with populated `field_definitions` must be available via fulfillment REST/gRPC APIs consumed by the OSAC UI.
- **Create APIs:** ComputeInstance and Cluster create endpoints must accept payloads shaped by catalog item `field_definitions` paths.

## 6. Open Questions

### 6.1 How should required fields be specified?

Each `FieldDefinition` carries its own `validation_schema` string — JSON Schema draft 2020-12 scoped to **that field's value** (the data at `path`), not to the full resource spec object. The `FieldDefinition` message has no separate `required` flag; requiredness must be inferred from how the wizard and schema are used.

Because of that shape, **object-level JSON Schema `required` (a list of property names) is not a meaningful way to mark a catalog field as required.** The `required` keyword applies when validating an object with multiple `properties`; here the UI validates one value at a time against one schema. Admins cannot express “this field is mandatory” by adding `"required": ["spec.foo"]` to `validation_schema`.

Per-field constraints can still enforce non-emptiness or bounds — for example `minLength`, `minimum`, or `enum` — but that is value validation, not a first-class “required field” declaration on the catalog item.

**Basics fields** (`metadata.name`, SSH key, pull secret when applicable) are required by wizard rules (FR-5–FR-7), independent of `field_definitions`.

**Still open:** For editable Configuration fields, should the wizard treat every shown field as required by default (empty blocks Next), require admins to encode requiredness only via per-value schema constraints (`minLength`, etc.), or should a future API change add an explicit required indicator on `FieldDefinition`?

- **Owner:** API / catalog authoring
- **Impact:** FR-8, FR-14, NFR-2, and client validation for Configuration-step fields
