---
title: Configuration Wizard for Cluster and VM Resources
authors:
  - brotman@redhat.com
creation-date: 2026-06-14
last-updated: 2026-07-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1421
see-also:
  - Catalog Items: /enhancements/catalog-items
  - VM Instance Types: /enhancements/vm-instance-types
replaces:
  - N/A
superseded-by:
  - N/A
---

# Configuration Wizard for Cluster and VM Resources

## 1. Goals and Non-Goals

### 1.1 Goals

- Tenants provision VMs and clusters by selecting a catalog offering and completing a guided wizard with a **fixed field set per resource type** ([§2.1.1](#211-static-wizard-fields)).
- Both resource types use the same five steps: **Catalog Item → General → Configuration → Networking → Review** (submit from Review). **General** collects name and credentials; **Configuration** collects image/release, sizing, and platform parameters — not networking placement.
- Catalog `field_definitions` overlay matching static paths on **Configuration**, **Networking**, and **General basics** fields (`spec.ssh_key`, `spec.ssh_public_key`, `spec.pull_secret`) for **display name**, **editability**, and **validation_schema**; picker-backed paths ignore overlay in v1 ([§2.1.2](#212-catalog-overlay-and-defaults)).

### 1.2 Non-Goals

- **BareMetalInstance** provisioning (separate PRD)
- **Template parameters**
- **Multi-NIC** — wizard submits one `network_attachments` entry (one VN, one subnet, security groups); no add/remove NIC rows
- **Cluster template `node_sets` defaults** — the wizard does **not** load, display, or apply `ClusterTemplate.spec.node_sets` (`host_type` or `size` defaults)
- **`spec.additional_disks`** — wizard scope undecided ([§5](#5-open-decisions)); default: boot disk only

## 2. Requirements

### 2.1 Field model

#### 2.1.1 Static wizard fields

Fields are hardcoded per resource type, not discovered from `field_definitions`. **General** step always shows the static paths below; catalog `field_definitions` overlay **basics** fields only (`ssh_key` / `ssh_public_key` / `pull_secret`) for label, editability, and validation — not Configuration or Networking paths ([§2.1.2](#212-catalog-overlay-and-defaults)). **Required** column: **?** = resolved in [§5](#5-open-decisions) where noted.

**ComputeInstance**


| Step            | Path                      | Label                                    | Widget                                 | Required |
| --------------- | ------------------------- | ---------------------------------------- | -------------------------------------- | -------- |
| General         | `metadata.name`           | Name                                     | Text                                   | Required |
| General         | `spec.ssh_key`            | SSH public key                           | Text (multiline)                       | Optional |
| Configuration   | `spec.image.source_ref`   | VM image (OCI reference)                 | Text                                   | Required |
| Configuration   | `spec.is_windows`         | OS family                                | Radio (`Linux`, `Windows`)             | Required |
| Configuration   | `spec.instance_type`      | Instance type                            | Picker ([§2.1.5](#215-vm-instance-type-picker-api)) | Required |
| Configuration   | `spec.user_data`          | User data (cloud-init / Ignition)        | Text (multiline)                       | Optional |
| Configuration   | `spec.boot_disk.size_gib` | Boot disk size (GiB)                     | Number                                 | ?        |
| Configuration   | `spec.run_strategy`       | Run strategy                             | Select (`Always`, `Halted`)            | Required |
| Networking      | `spec.network_attachments` | Virtual network, subnet, security groups | Pickers ([§2.1.4](#214-vm-networking-picker-apis)) | Required |

**Notes:**

- **`spec.user_data`**: plain multiline string (cloud-init or Ignition); omit from payload when empty. Stored as Secret → KubeVirt `cloudInitNoCloud`.
- **`spec.image`**: wizard collects `source_ref` only; payload always sets `spec.image.source_type` to **`registry`**. Future: ComputeImage list picker ([OSAC-979](https://redhat.atlassian.net/browse/OSAC-979)).
- **`spec.is_windows`**: Configuration-step **OS family** radio — **Linux** → `is_windows: false`; **Windows** → `is_windows: true`. Maps to the optional boolean added in [fulfillment-service PR #734](https://github.com/osac-project/fulfillment-service/pull/734) ([OSAC-13](https://redhat.atlassian.net/browse/OSAC-13)); the reconciler maps this to CR `guestOSFamily` for AAP provisioning. Required on the wizard; default selection **Linux** when no catalog `default` ([§2.1.2](#212-catalog-overlay-and-defaults)). The wizard always sends an explicit value.
- **`spec.instance_type`**: Configuration-step **instance type** picker — tenant selects a named compute bundle (cores + memory) from [§2.1.5](#215-vm-instance-type-picker-api). Payload sends **`spec.instance_type` only** (instance type name); the wizard does **not** collect or send `spec.cores` or `spec.memory_gib` ([VM Instance Types EP](/enhancements/vm-instance-types), [fulfillment-service PR #735](https://github.com/osac-project/fulfillment-service/pull/735) / OSAC-1217). The API validates the name and state; the reconciler resolves cores/memory on the CR. Catalog `field_definitions` for this path are **ignored** in v1 ([§2.1.2](#212-catalog-overlay-and-defaults)).
- **Disks**: wizard collects `spec.boot_disk.size_gib` only unless [§5](#5-open-decisions) chooses `spec.additional_disks`.
- **`spec.ssh_key`**: optional on the General step — prefill from catalog `default` when defined ([§2.1.2](#212-catalog-overlay-and-defaults)); tenant may edit when `editable: true` or clear the field. Omit from the client create payload only when the field is blank after catalog selection or user edits. Include the parsed plain string in the payload when the wizard holds a value (prefilled default or user entry).
- **Networking**: pickers assemble a single `spec.network_attachments` entry; raw JSON not shown. Catalog `field_definitions` for this path (including nested paths) are **ignored** in v1 ([§2.1.2](#212-catalog-overlay-and-defaults)). APIs: [§2.1.4](#214-vm-networking-picker-apis).

**Cluster**


| Step            | Path                        | Label                                                         | Widget                               | Required |
| --------------- | --------------------------- | ------------------------------------------------------------- | ------------------------------------ | -------- |
| General         | `metadata.name`             | Name                                                          | Text                                 | Required |
| General         | `spec.ssh_public_key`       | SSH public key                                                | Text (multiline)                     | Optional |
| General         | `spec.pull_secret`          | Pull secret                                                   | Text (multiline, masked)             | Required |
| Configuration   | `spec.release_image`        | OpenShift version (release image)                             | Text                                 | Required |
| Configuration   | `spec.node_sets`            | Worker node sets                                              | Editable table (add/remove rows) | Required |
| Networking      | `spec.network.pod_cidr`     | Pod network CIDR                                              | Text                                 | ?        |
| Networking      | `spec.network.service_cidr` | Service network CIDR                                          | Text                                 | ?        |

**Notes:**

- **`spec.node_sets`**: tenant-managed node sets on the Configuration step. The wizard **does not** read `ClusterTemplate.spec.node_sets`. Tenants **add** and **remove** rows. Each row collects only **`host_type`** (picker — [§2.1.6](#216-cluster-host-type-picker-api)) and **`size`** (number of nodes, must be > 0) per `ClusterNodeSet` — no separate name or map-key field in the UI. At least one row is required before leaving Configuration. **Each `host_type` may appear on at most one row** — duplicate host types are blocked by validation. The create payload is `spec.node_sets` as a map keyed by **host type id** (the map key equals `host_type` on each entry); each value is `{ host_type, size }` only. **v1:** catalog item `field_definitions` defaults for `spec.node_sets` (including `host_type` and `size`) **do not apply** — the node-sets table starts empty on catalog selection; tenants compose all rows manually ([§2.1.2](#212-catalog-overlay-and-defaults)).

**Create payload:** Only paths in [§2.1.1](#211-static-wizard-fields) plus catalog item reference; VM hardcodes `spec.image.source_type` = `registry`; VM sends `spec.instance_type` and `spec.is_windows` explicitly, not `spec.cores` or `spec.memory_gib`.

#### 2.1.2 Catalog overlay and defaults

For each static **non-picker** field, match `field_definitions` by `path` (spec-relative paths such as `ssh_key`, `boot_disk.size_gib`, or `spec.image.source_ref` — fulfillment accepts both forms). **General basics** paths (`spec.ssh_key`, `spec.ssh_public_key`, `spec.pull_secret`) and **Configuration** / **Networking** non-picker paths participate in overlay. Non-matching paths are **ignored** (not on Review, not in payload).

**Picker-backed fields (v1):** `spec.instance_type`, `spec.network_attachments` (including nested paths such as `spec.network_attachments.subnet`), and cluster `spec.node_sets` **host type** (per-row dropdown) load options from list APIs ([§2.1.5](#215-vm-instance-type-picker-api), [§2.1.4](#214-vm-networking-picker-apis), [§2.1.6](#216-cluster-host-type-picker-api)). Matching catalog `field_definitions` for these paths are **ignored** — wizard labels, editability, validation, and **defaults** come from wizard defaults and list-API behavior only. **Cluster `spec.node_sets` (v1):** no catalog item defaults apply — the wizard does not prefill node set rows from `field_definitions` on catalog selection; the table starts empty. Catalog overlay on picker fields is **deferred** to a later release ([§5](#5-open-decisions)).

| Aspect     | Matching entry (non-picker fields, including General basics)                | No matching entry     |
| ---------- | --------------------------------------------------------------------------- | --------------------- |
| Label      | `display_name` or wizard default                                            | Wizard default        |
| Editable   | `editable: false` → read-only on wizard step; blank when no catalog `default` | `true`                |
| Default    | Catalog `default` if set; else blank                                        | Blank                 |
| Validation | `validation_schema` maps to integer/enum/text widgets; inline errors on blur; full step validation on Next (see [§2.2](#22-wizard-behavior)) | API/wizard validation |

**General basics and fulfillment create:** On catalog selection, the wizard prefills General basics fields (`ssh_key`, `ssh_public_key`, `pull_secret`) from catalog `default` when defined, using the same overlay rules as Configuration/Networking. The client create payload includes a basics value when the wizard field is non-blank (catalog default and/or user edit). When the tenant clears an optional basics field, omit it from the client payload; fulfillment may still apply the catalog `default` server-side via `applyFieldDefinitions` if one is defined.

Non-editable fields (`editable: false`) are **read-only** on the wizard step (Configuration or Networking), not hidden. With a catalog `default`, the value is included in the payload. Without a catalog `default`, the field is **blank and read-only**. Read-only fields use disabled/read-only controls (same widget type as editable fields where applicable).

**Default rules:** Fields start **blank** unless catalog `default` is set or a **special case** applies:


| Case                | Behavior                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `spec.run_strategy` | Pre-select `Always` when no catalog `default`                                                                            |
| OS family (VM)      | Pre-select **Linux** (`is_windows: false`) when no catalog `default`                                                     |
| Instance type (VM)  | **Auto-select** when `InstanceTypes.List` returns exactly one option |
| Networking pickers  | **Auto-select** when a list returns exactly one option (VN → subnet → SGs) |

#### 2.1.3 Open required fields

Fields marked **?** in [§2.1.1](#211-static-wizard-fields) — resolve Required vs Optional before implementation ([§5](#5-open-decisions)).

### 2.1.4 VM networking picker APIs

The wizard loads picker options from the **public** fulfillment APIs (`osac.public.v1`). The UI uses the generated OpenAPI client (REST); gRPC equivalents are listed for reference.

| Picker | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Virtual network | `VirtualNetworks.List` | `GET /api/fulfillment/v1/virtual_networks` | Tenant-visible virtual networks |
| Subnet | `Subnets.List` | `GET /api/fulfillment/v1/subnets` | Subnets in the selected virtual network |
| Security groups | `SecurityGroups.List` | `GET /api/fulfillment/v1/security_groups` | Security groups in the selected virtual network |

**List request parameters** (all three): optional query `filter` (CEL), `limit`, `offset`, `order`. Tenant scope is implicit from the authenticated session.

**Subnet and security group filters** (after virtual network selection):

```text
this.spec.virtual_network == "<vn-id>"
```

**Picker display and values:**

| Picker | Option label | Selected value |
| ------ | ------------ | -------------- |
| Virtual network | `metadata.name` (fallback `id`) | VirtualNetwork `id` — drives subnet/SG list filters only |
| Subnet | `metadata.name` (fallback `id`) | Subnet `id` |
| Security group | `metadata.name` (fallback `id`) | SecurityGroup `id` (multi-select) |

**Create payload assembly** — one `spec.network_attachments` element:

```json
{
  "subnet": "<subnet-id>",
  "security_groups": ["<security-group-id>"]
}
```

Per `NetworkAttachment` in `compute_instance_type.proto`. The wizard does not send virtual network ID in `network_attachments`; placement is implied by the subnet (security groups must belong to the same virtual network).

**Load order:** virtual network list → on selection, load filtered subnet and security group lists → auto-select when a list returns exactly one item ([§2.1.2](#212-catalog-overlay-and-defaults)).

### 2.1.5 VM instance type picker API

The Configuration step loads instance type options from the **public** fulfillment API (`osac.public.v1`). The UI uses the generated OpenAPI client (REST); gRPC equivalent listed for reference.

| Picker | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Instance type | `InstanceTypes.List` | `GET /api/fulfillment/v1/instance_types` | Tenant-visible instance types (ACTIVE and DEPRECATED by default) |

**List request parameters:** optional query `filter` (CEL), `limit`, `offset`, `order`. Tenant scope is implicit from the authenticated session. The default list excludes **OBSOLETE** instance types (not selectable for new VMs).

**Picker display and values:**

| Picker | Option label | Selected value |
| ------ | ------------ | -------------- |
| Instance type | `metadata.name` plus `spec.cores` and `spec.memory_gib` (e.g. `standard-4-16 — 4 vCPU, 16 GiB`); indicate **DEPRECATED** state in the label when `spec.state` is DEPRECATED | Instance type name (`metadata.name` / `id`) → `spec.instance_type` on create |

**Create payload:** send only the instance type **name** string:

```json
{
  "instance_type": "standard-4-16"
}
```

Do **not** send `cores` or `memory_gib` — they are mutually exclusive with `instance_type` at the API ([PR #735](https://github.com/osac-project/fulfillment-service/pull/735)).

**Deprecation handling:** if the selected type is DEPRECATED, create may succeed with **warnings** in the response; the wizard surfaces those warnings after submit (non-blocking). OBSOLETE types are not offered in the picker.

**Load order:** load instance type list when entering Configuration → auto-select when the list returns exactly one item ([§2.1.2](#212-catalog-overlay-and-defaults)).

### 2.1.6 Cluster host type picker API

The Configuration step loads host type options from the **public** fulfillment API (`osac.public.v1`). The UI uses the generated OpenAPI client (REST); gRPC equivalent listed for reference.

| Picker | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Host type | `HostTypes.List` | `GET /api/fulfillment/v1/host_types` | Tenant-visible host types for node set selection |

**List request parameters:** optional query `filter` (CEL), `limit`, `offset`, `order`. Tenant scope is implicit from the authenticated session.

**Picker display and values:**

| Picker | Option label | Selected value |
| ------ | ------------ | -------------- |
| Host type | `title` or `metadata.name` (fallback `id`) | Host type `id` — used as both the row selection and the `spec.node_sets` **map key**; `host_type` on the entry value matches the key |

**Create payload** — one map entry per wizard row; **map key = host type id** (same as `host_type` on the value):

```json
{
  "node_sets": {
    "acme_1tb": {
      "host_type": "acme_1tb",
      "size": 3
    },
    "acme_1tb_h100": {
      "host_type": "acme_1tb_h100",
      "size": 2
    }
  }
}
```

Per `ClusterNodeSet` in `cluster_type.proto` — each value has **`host_type`** and **`size`** only. The wizard enforces **unique host types** across rows (no duplicate keys). **v1:** catalog item `field_definitions` defaults for node sets do not apply — no prefill from the selected `ClusterCatalogItem`. Catalog `field_definitions` for `spec.node_sets` paths are **ignored** in v1 ([§2.1.2](#212-catalog-overlay-and-defaults)) — node set composition is API-driven via the host type list, not template- or catalog-default-driven.

**Load order:** load host type list when entering Configuration (or when the node-sets table mounts). No auto-select from `ClusterTemplate`; tenants choose host type per row from the dropdown. Host types already selected on another row are excluded from (or blocked in) remaining row pickers.

### 2.2 Wizard behavior

```mermaid
flowchart LR
  A[Catalog Item] --> B[General]
  B --> C[Configuration]
  C --> D[Networking]
  D --> E[Review and Submit]
```

- **Catalog Item:** Require catalog item selection.
- **Review:** Shows the same values the user sees on wizard step fields (General, Configuration, Networking) — blank, catalog- or wizard-defaulted, or user-entered — with the same labels as on each step. Submit from Review.
- **Step navigation:** Next is always enabled. On click, validate every field on the current step — including fields that have not yet blurred and therefore have no inline error shown. Surface any hidden errors inline; if validation fails, show an alert asking the user to fix the errors and do not advance.

## 3. Acceptance Criteria

- Wizard provisions VM or Cluster using only [§2.1.1](#211-static-wizard-fields) payload paths plus hardcoded VM `source_type` and catalog item reference.
- Five-step flow: Catalog Item → General → Configuration → Networking → Review; submit from Review.
- Review shows the same values as on wizard step fields (blank, default-driven, or user-entered).
- Catalog overlay and default rules per [§2.1.2](#212-catalog-overlay-and-defaults) on Configuration and Networking **non-picker** fields and General **basics** fields; picker-backed paths ignore `field_definitions` in v1; catalog `default` prefills matching wizard fields on catalog selection; non-editable fields without `default` appear blank and read-only; non-editable fields with `default` appear read-only with value and are included in the client payload.
- VM: single `network_attachments` entry assembled from picker APIs; instance type picker sets `spec.instance_type` (not `cores`/`memory_gib`); OS family radio sets `spec.is_windows` (default **Linux**); optional `user_data` omitted when empty; create warnings for deprecated instance types are shown to the user.
- Cluster: `node_sets` is tenant-composed on Configuration — add/remove rows; each row has `host_type` from `HostTypes.List` and `size` > 0 only (`ClusterNodeSet`); **unique host type per row**; map key = host type id; wizard does not load or apply `ClusterTemplate.spec.node_sets`; **catalog item defaults for `spec.node_sets` do not apply in v1** (empty table on catalog selection).
- All **?** requiredness decisions resolved before release ([§5](#5-open-decisions)).
- On Next click, validate all fields on the current step (including untouched fields); surface hidden inline errors; show an alert if invalid; do not advance until the step is valid.

## 4. Dependencies

- `ComputeInstanceCatalogItem`, `ClusterCatalogItem` (with `field_definitions`)
- `HostTypes.List` (cluster Configuration step — host type picker per node set row)
- `VirtualNetworks.List`, `Subnets.List`, `SecurityGroups.List` (gRPC `osac.public.v1`) / REST `GET /api/fulfillment/v1/virtual_networks`, `.../subnets`, `.../security_groups` ([§2.1.4](#214-vm-networking-picker-apis))
- `InstanceTypes.List` (gRPC `osac.public.v1`) / REST `GET /api/fulfillment/v1/instance_types` ([§2.1.5](#215-vm-instance-type-picker-api))
- ComputeInstance and Cluster create APIs
- `spec.instance_type` on ComputeInstance ([OSAC-1217](https://redhat.atlassian.net/browse/OSAC-1217), [fulfillment-service PR #735](https://github.com/osac-project/fulfillment-service/pull/735)) — required for VM instance type picker
- `spec.is_windows` on ComputeInstance ([OSAC-13](https://redhat.atlassian.net/browse/OSAC-13), [fulfillment-service PR #734](https://github.com/osac-project/fulfillment-service/pull/734)) — required for VM OS family in the wizard

## 5. Open decisions

Resolve before implementation.

### Required vs optional (`?`)

| Path | Resource |
| ---- | -------- |
| `spec.ssh_key` / `spec.ssh_public_key` | **Resolved:** Optional — prefill catalog `default` when defined; omit from client payload only when blank after catalog selection or user clears the field |
| `spec.boot_disk.size_gib` | ComputeInstance |
| `spec.network.pod_cidr`, `spec.network.service_cidr` | Cluster |

### Catalog overlay on picker-backed fields (deferred)

**Resolved for v1:** Ignore catalog `field_definitions` for picker-backed paths (`spec.instance_type`, `spec.network_attachments`, and nested networking paths). Picker UX is API-driven only; see [§2.1.2](#212-catalog-overlay-and-defaults).

**Deferred:** Catalog overlay on picker fields (including `display_name`, `editable`, `default`, `validation_schema`, catalog-default vs auto-select precedence, and defaults not present in list API options) is out of scope for v1 and may be addressed in a later release.

### Cluster `node_sets` composition

**Resolved:** Tenant-managed node sets on Configuration. The wizard ignores `ClusterTemplate.spec.node_sets` entirely. Tenants add/remove rows; each row collects `host_type` (dropdown from `HostTypes.List`) and `size` only. Map key = host type id; duplicate host types are not allowed. **v1:** catalog item `field_definitions` defaults for `spec.node_sets` do not apply — node set rows are not prefilled from the selected catalog item. See [§2.1.1](#211-static-wizard-fields) and [§2.1.6](#216-cluster-host-type-picker-api).

### Additional disks

Not in [§2.1.1](#211-static-wizard-fields) today. **Unknown** whether v1 needs wizard UI for `spec.additional_disks[]` or boot disk + API/CLI is enough.

| Option | Outcome |
| ------ | ------- |
| **No (default)** | Out of scope ([§1.2](#12-non-goals)); boot disk only |
| **Yes** | Add repeatable `size_gib` rows on Configuration; add to §2.1.1 |
