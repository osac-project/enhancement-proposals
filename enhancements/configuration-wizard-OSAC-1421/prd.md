# Configuration Wizard for Cluster and VM Resources

| Field     | Value |
|-----------|-------|
| Author(s) | Bat-Zion ROtman |
| Date      | 2026-06-14 |

## 2. Goals and Non-Goals

### 2.1 Goals

- Tenant users provision VMs and clusters by selecting a catalog offering, completing a guided wizard with a **fixed field set per resource type**, and submitting — without exposing the full resource spec or internal-only API fields.
- The wizard always renders the same static fields for each resource type (see §3.1.1). Catalog items do **not** determine which fields appear.
- For each static field, when the selected catalog item defines a matching `field_definitions` entry (same `path`), the wizard uses that entry for **display name**, **editability**, **default**, **required**, and **validation_schema**. When no matching entry exists, the field is still shown and remains editable with wizard/API defaults.
- Networking is a dedicated wizard step: ComputeInstance uses virtual network, subnet, and security group pickers; Cluster collects pod and service CIDRs.
- A single five-step wizard flow for both ComputeInstance and Cluster catalog item types.

### 2.2 Non-Goals

The following are explicitly out of scope and **will not be supported** in this release:

- **BareMetalInstance** provisioning (separate PRD)
- **Template parameters** — dynamic fields from the catalog item's referenced template (`Templates.Get` / `ParameterDefinition`); planned for a follow-on release
- Exposing internal-only or provider-managed spec fields directly in the wizard
- Specialized widgets for arbitrary JSON Schema types beyond: number input, enum select, plain text, and the dedicated networking pickers defined in this PRD

## 3. Requirements

### 3.1 Functional Requirements

#### 3.1.1 Static wizard fields

The wizard must always present the fields below for the selected resource type. These fields are **not** discovered from `field_definitions`; they are hardcoded in the UI per resource type.

**ComputeInstance**

| Wizard step | Path | Label | Widget | Options source | Required |
|-------------|------|-------|--------|----------------|----------|
| General | `metadata.name` | Name | Text | — | Yes |
| General | `spec.ssh_key` | SSH public key | Text (multiline) | — | Yes |
| Compute | `spec.cores` | vCPUs | Number | — | Yes |
| Compute | `spec.memory_gib` | Memory (GiB) | Number | — | Yes |
| Compute | `spec.image.source_ref` | Image | Text | — | Yes |
| Compute | `spec.boot_disk.size_gib` | Boot disk size (GiB) | Number | — | Yes |
| Compute | `spec.run_strategy` | Run strategy | Select | `Always`, `Halted` | Yes |
| Networking | Networking | Virtual network, subnet, security groups | Dedicated pickers (see FR-20) | List APIs (see §5) | Yes |

The Networking row does not map to a single spec path. The wizard collects virtual network, subnet, and security group selections on the Networking step and **assembles** `spec.network_attachments` in the create payload (see FR-20).

**Cluster**

| Wizard step | Path | Label | Widget | Required |
|-------------|------|-------|--------|----------|
| General | `metadata.name` | Name | Text | Yes |
| General | `spec.ssh_public_key` | SSH public key | Text (multiline) | Yes |
| General | `spec.pull_secret` | Pull secret | Text (multiline, masked) | Yes |
| Compute | `spec.release_image` | OpenShift version (release image) | Text | Yes |
| Networking | `spec.network.pod_cidr` | Pod network CIDR | Text | Yes (default allowed) |
| Networking | `spec.network.service_cidr` | Service network CIDR | Text | Yes (default allowed) |

Cluster wizard always collects pull secret on General; ComputeInstance wizard never collects pull secret.

#### 3.1.2 Catalog overlay (`field_definitions`)

For each static wizard field, the wizard looks up a `field_definitions` entry in the selected catalog item with a matching `path`:

| Aspect | When matching `field_definitions` entry exists | When no matching entry |
|--------|-----------------------------------------------|-------------------------|
| Display label | `display_name` if set; else wizard default label | Wizard default label |
| Editable | `editable` (default `false` in API → treat as non-editable) | `true` |
| Default | `default` when user does not supply a value | Wizard/API default for that field |
| Required | `required` on `FieldDefinition` when present; else wizard static required table | Wizard static required table |
| Validation | `validation_schema` (JSON Schema draft 2020-12, per-field value) | API/wizard validation only |

- **FR-3:** Non-editable static fields (`editable: false` in matching `field_definitions`) must not appear as inputs in the wizard; their `default` values must appear on Review and be included in the create payload.
- **FR-3a:** If a static field has a matching non-editable `field_definitions` entry **without** a `default` value, the wizard must block proceeding past catalog selection and show an error — the catalog item is not provisionable through this wizard.

`field_definitions` entries whose `path` does not match any static wizard field are **not rendered** in the wizard for this release. Non-editable entries still apply their `default` to the create payload silently; editable entries for non-static paths are out of scope until template-parameter support (see Non-Goals).

#### Wizard structure

The wizard guides tenant users from catalog selection through submit in five steps.

```mermaid
flowchart LR
  A[Catalog] --> B[General]
  B --> C[Compute]
  C --> D[Networking]
  D --> E[Review]
  E --> F[Submit Create]
```

- **FR-1:** The OSAC UI must provide a provisioning wizard for ComputeInstance and Cluster resources that uses the static field sets in §3.1.1, with catalog overlay per §3.1.2.
- **FR-2:** After the user opens the wizard, the flow must consist of five steps in order: (1) Catalog, (2) General, (3) Compute, (4) Networking, (5) Review. Submit is an action from Review, not a separate step.

#### Catalog (step 1)

- **FR-4:** Step 1 (Catalog) must present published catalog items for the target resource type (ComputeInstance or Cluster) and require the user to select one catalog item before proceeding.

#### General (step 2)

- **FR-5:** Step 2 (General) must collect identity and access fields for the resource type:
  - **ComputeInstance:** `metadata.name`, `spec.ssh_key`
  - **Cluster:** `metadata.name`, `spec.ssh_public_key`, `spec.pull_secret`

#### Compute (step 3)

- **FR-6:** Step 3 (Compute) must collect compute and platform-sizing fields for the resource type, honoring catalog overlay editability (§3.1.2):
  - **ComputeInstance:** `spec.cores`, `spec.memory_gib`, `spec.image.source_ref`, `spec.boot_disk.size_gib`, `spec.run_strategy`
  - **Cluster:** `spec.release_image`

#### Networking (step 4)

- **FR-7:** Step 4 (Networking) must collect networking fields for the resource type, honoring catalog overlay editability (§3.1.2):
  - **ComputeInstance:** virtual network, subnet, and security groups (FR-20)
  - **Cluster:** `spec.network.pod_cidr`, `spec.network.service_cidr`
- **FR-8:** General, Compute, and Networking steps must not render static fields that are non-editable per catalog overlay; their defaults apply per FR-3.

#### Review (step 5)

- **FR-9:** Step 5 (Review) must display every static wizard field for the resource type with the value that will be sent in the create request: user-entered values for editable fields, and `default` values for non-editable fields (including Networking assembled per FR-20).
- **FR-10:** Review must also display non-editable `field_definitions` entries for non-static paths with their default values (so tenants can see catalog-preset values they did not configure).
- **FR-11:** Review must not display spec fields beyond the static wizard field set and non-editable catalog defaults in FR-10.

#### Field rendering

- **FR-14:** For editable static fields with a `validation_schema` in the matching `field_definitions` entry: `type: integer` → number input; `enum` present → select; all other types → plain text input (unless FR-20 applies).
- **FR-15:** Select options from `validation_schema` `enum` values apply only to fields using enum-based selects (e.g., `spec.run_strategy` when not overridden by catalog schema).
- **FR-18:** When a field fails `validation_schema` validation, the wizard must show the error inline on that field. The user must not be able to proceed to the next step until all validation errors on the current step are resolved.
- **FR-20:** On the ComputeInstance Networking step, the wizard must present:
  1. **Virtual network** — select from `VirtualNetworks.List`
  2. **Subnet** — select from `Subnets.List`, filtered to the chosen virtual network
  3. **Security groups** — multi-select from `SecurityGroups.List`, filtered to the chosen virtual network

  The wizard must assemble these selections into `spec.network_attachments` in the create payload. The raw `network_attachments` structure must not be shown to the user.

#### Create payload

- **FR-16:** On submit, the create request must include: tenant-provided values for editable static fields; `default` values for non-editable static fields and non-editable `field_definitions`; and silently merged defaults for non-static non-editable `field_definitions` (§3.1.2).
- **FR-17:** Field paths in the payload must use the API spec paths from §3.1.1 (dot notation). The selected catalog item must be referenced per existing create API conventions.

### 3.2 Non-Functional Requirements

- **NFR-1:** The wizard must consume catalog item data from `ComputeInstanceCatalogItem` and `ClusterCatalogItem` APIs, including `field_definitions` (`path`, `display_name`, `editable`, `default`, `required`, `validation_schema`).
- **NFR-2:** Client-side validation must honor `validation_schema` on matching `field_definitions` entries. Failures are inline per field and block Next until resolved.
- **NFR-3:** The wizard must not expose spec fields beyond the static wizard field set (§3.1.1), except non-editable catalog defaults shown on Review (FR-10).

## 4. Acceptance Criteria

- [ ] Selecting a ComputeInstance or Cluster catalog item and completing the wizard creates the resource using only the static field set (§3.1.1) plus non-editable catalog defaults.
- [ ] The wizard presents five steps in order: Catalog → General → Compute → Networking → Review; submit is triggered from Review.
- [ ] General collects name and credentials (`spec.ssh_key` for VM; `spec.ssh_public_key` and `spec.pull_secret` for cluster).
- [ ] Compute collects sizing and platform fields (`spec.cores`, `spec.memory_gib`, `spec.image.source_ref`, `spec.boot_disk.size_gib`, `spec.run_strategy` for VM; `spec.release_image` for cluster).
- [ ] Networking collects network configuration (virtual network, subnet, and security groups for VM; pod and service CIDRs for cluster).
- [ ] Non-editable catalog overlays hide inputs on General, Compute, and Networking; defaults appear on Review and in the payload.
- [ ] ComputeInstance Networking uses list APIs; payload contains assembled `spec.network_attachments`, not user-edited raw JSON.
- [ ] Review shows every static field value (entered or defaulted) and non-editable non-static catalog defaults.
- [ ] Catalog overlay: matching `field_definitions` control display name, editability, default, required, and validation; static fields without a matching entry remain editable with wizard defaults.
- [ ] Selecting a catalog item with a non-editable static field lacking `default` blocks the wizard with a clear error.
- [ ] Validation errors appear inline; Next is disabled until the current step is valid.
- [ ] The wizard supports both ComputeInstance and Cluster catalog item types.

## 5. Dependencies

- **Catalog item APIs:** `ComputeInstanceCatalogItem` and `ClusterCatalogItem` with `field_definitions`.
- **Networking list APIs:** `VirtualNetworks.List`, `Subnets.List`, `SecurityGroups.List` (tenant-scoped, for ComputeInstance Networking step).
- **Create APIs:** ComputeInstance and Cluster create endpoints accepting the static spec paths in §3.1.1.
- **API extension:** `required` boolean on `FieldDefinition` (backend; coordinates with catalog authoring).

## 6. Resolved Decisions

### 6.1 Required fields

- **Static wizard fields** are required per §3.1.1 unless a matching `field_definitions` entry sets `required: false` or marks the field non-editable with a default.
- **Catalog overlay:** Add a `required` boolean to `FieldDefinition`. When present on a matching entry, it controls whether an editable static field blocks Next when empty. Per-field `validation_schema` constraints (`minLength`, `minimum`, etc.) provide additional validation.
- **Backend follow-up:** API/catalog authoring owns the `FieldDefinition.required` schema addition (per review feedback).

### 6.2 Field source model (review alignment)

| Source | Role in this PRD |
|--------|------------------|
| **Static wizard field set** (§3.1.1) | Determines which fields always appear and on which step |
| **Catalog `field_definitions`** | Overrides display, editability, default, required, validation for matching paths |
| **Template parameters** | Out of scope — follow-on release |

### 6.3 Wizard step model

Five steps: **Catalog → General → Compute → Networking → Review**. Networking is a dedicated step so list APIs and network validation are isolated from compute sizing and platform configuration.
