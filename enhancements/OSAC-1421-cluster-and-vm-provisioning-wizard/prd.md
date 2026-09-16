---
title: Configuration Wizard for Cluster and VM Resources
authors:
  - brotman@redhat.com
creation-date: 2026-06-14
last-updated: 2026-07-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1421
see-also:
  - Catalog Items: /enhancements/OSAC-1002-catalog-items
  - VM Instance Types: /enhancements/OSAC-46-vm-instance-types
replaces:
  - N/A
superseded-by:
  - N/A
---

# Configuration Wizard for Cluster and VM Resources

All wizard networking flows inherit the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
the wizard supports connected deployments only and does not support or expose
air-gapped or disconnected networking deployments.

## 1. Goals and Non-Goals

### 1.1 Goals

- Tenants provision VMs and clusters by selecting a catalog offering and completing a guided wizard with a **fixed field set per resource type** ([§2.1.1](#211-static-wizard-fields)).
- Both resource types use the same five steps: **Catalog Item → General → Configuration → Networking → Review** (submit from Review). **General** collects name and credentials; **Configuration** collects image/release, sizing, and platform parameters — not networking placement.
- Catalog Items v2 typed `fields` policies provide locked/editable/default behavior for supported resource fields, including the typed networking policies; the wizard does not consume the legacy `FieldDefinition`, dot-path, or JSON-Schema model ([§2.1.2](#212-catalog-policy-and-defaults)).

### 1.2 Non-Goals

- **BareMetalInstance** provisioning (separate PRD)
- **Template parameters**
- **VM networking** — wizard submits one list-shaped `network_attachments` entry carrying a `ComputeNetworkAttachment` with one Subnet and an optional SecurityGroup selection. The selected Subnet and SecurityGroup must share a VirtualNetwork; the tenant default SecurityGroup is used only for the default VirtualNetwork. The effective ACL is inherited from that Subnet and must be Ready before placement; there are no add/remove NIC rows
- **Tenant-defined cluster hardware** — the wizard does not create, remove, or replace node sets or their `baremetal_instance_type`; the resolved ClusterTemplate owns that structure. The wizard may collect node-set sizes according to Catalog Item policy.
- **`spec.additional_disks`** — wizard scope undecided ([§5](#5-open-decisions)); default: boot disk only

## 2. Requirements

### 2.1 Field model

#### 2.1.1 Static wizard fields

Fields are hardcoded per resource type, not discovered from Catalog policy messages. **General** step always shows the static paths below; Catalog Items v2 typed policies apply only to supported fields and preserve the normal field types and validation ([§2.1.2](#212-catalog-policy-and-defaults)). **Required** column: **?** = resolved in [§5](#5-open-decisions) where noted.

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
| Networking      | `spec.network_attachments` | Subnet and optional SecurityGroups; effective NetworkACL inherited from the Subnet | Pickers ([§2.1.4](#214-vm-networking-picker-apis)) | Required |

**Notes:**

- **`spec.user_data`**: plain multiline string (cloud-init or Ignition); omit from payload when empty. Stored as Secret → KubeVirt `cloudInitNoCloud`.
- **`spec.image`**: wizard collects `source_ref` only; payload always sets `spec.image.source_type` to **`registry`**. Future: ComputeImage list picker ([OSAC-979](https://redhat.atlassian.net/browse/OSAC-979)).
- **`spec.is_windows`**: Configuration-step **OS family** radio — **Linux** → `is_windows: false`; **Windows** → `is_windows: true`. Maps to the optional boolean added in [fulfillment-service PR #734](https://github.com/osac-project/fulfillment-service/pull/734) ([OSAC-13](https://redhat.atlassian.net/browse/OSAC-13)); the reconciler maps this to CR `guestOSFamily` for AAP provisioning. Required on the wizard; default selection is **Linux**. The wizard always sends an explicit value.
- **`spec.instance_type`**: Configuration-step **instance type** picker — tenant selects a named compute bundle (cores + memory) from [§2.1.5](#215-vm-instance-type-picker-api). Payload sends **`spec.instance_type` only** as a typed reference containing the selected name; the wizard does **not** collect or send `spec.cores` or `spec.memory_gib` ([VM Instance Types EP](/enhancements/OSAC-46-vm-instance-types), [fulfillment-service PR #735](https://github.com/fulfillment-service/pull/735) / OSAC-1217). The API validates the name and state; the reconciler resolves cores/memory on the CR. A supported Catalog Items v2 policy may lock or default this typed reference; no legacy generic path policy is accepted.
- **Disks**: wizard collects `spec.boot_disk.size_gib` only unless [§5](#5-open-decisions) chooses `spec.additional_disks`.
- **`spec.ssh_key`**: optional on the General step; it is not a Catalog Items v2 governed field. The tenant may edit or clear it. Omit from the client create payload when blank, and include the parsed plain string when the wizard holds a value.
- **Networking**: pickers assemble a single `spec.network_attachments` entry; raw JSON not shown. The typed Catalog Items v2 `network_attachments` policy may lock, default, or leave the attachment editable; the final value still obeys the shared zero-or-one attachment contract, same-VirtualNetwork and Ready typed SecurityGroup references, ACL readiness, and defaulting rules. The wizard must not silently apply the default-VN SecurityGroup to a Subnet in another VirtualNetwork. APIs: [§2.1.4](#214-vm-networking-picker-apis).
- The direct VM API permits an omitted or empty attachment list and applies the
  normal tenant-default resolution. The v1 wizard intentionally requires a
  picker selection and always emits one entry; it does not expose a separate
  “use defaults” choice. This UI requirement does not change the API's zero-or-
  one attachment contract.

**Cluster**


| Step            | Path                        | Label                                                         | Widget                               | Required |
| --------------- | --------------------------- | ------------------------------------------------------------- | ------------------------------------ | -------- |
| General         | `metadata.name`             | Name                                                          | Text                                 | Required |
| General         | `spec.ssh_public_key`       | SSH public key                                                | Text (multiline)                     | Optional |
| General         | `spec.pull_secret`          | Pull secret                                                   | Text (multiline, masked)             | Required |
| Configuration   | `spec.release_image`        | OpenShift version (release image)                             | Text                                 | Required |
| Configuration   | `spec.node_sets`            | Template-defined worker node sets                             | Template-backed table (size only) | Required |
| Networking      | `spec.network.pod_cidr`     | Pod network CIDR                                              | Text                                 | Optional |
| Networking      | `spec.network.service_cidr` | Service network CIDR                                          | Text                                 | Optional |

**Notes:**

- **`spec.node_sets`**: after Catalog Item and Template resolution, the wizard loads `ClusterTemplate.spec.node_sets` with `ClusterTemplates.Get`. The template owns the node-set map keys and each node set's typed `baremetal_instance_type` reference; the wizard displays those values read-only. The Catalog Item may govern only the `size` value for an existing template node-set, using the policy defined in Catalog Items v2. The tenant may edit a size only when the effective policy permits it; the tenant cannot add/remove node sets or replace their hardware type. The create payload preserves the template node-set names and sends each `baremetal_instance_type` as a typed reference object, not a raw ID string.

- **Cluster tenant networking:** the wizard does not expose the CaaS
  `spec.network_attachment` or `spec.auto_external_ip_attachment` controls in
  v1. It omits both fields from the create payload. The server applies the
  normal Catalog/Template/default resolution for `network_attachment` (so the
  tenant default Subnet and SecurityGroup are used when no higher-precedence
  value exists), and the
  normal omitted-value behavior for `auto_external_ip_attachment` (normally
  `false`). Tenants that need to select an explicit CaaS Subnet,
  manage NetworkACLs, or request automatic external access use the direct
  API/CLI.

**Create payload:** Only paths in [§2.1.1](#211-static-wizard-fields) plus catalog item reference; VM hardcodes `spec.image.source_type` = `registry`; VM sends `spec.instance_type` and `spec.is_windows` explicitly, not `spec.cores` or `spec.memory_gib`.

#### 2.1.2 Catalog policy and defaults

For each supported field, the wizard reads the typed Catalog Items v2 policy from `fields`. There are no free-form paths, generic values, or JSON-Schema overlays. Unsupported fields are ungoverned and retain their ordinary wizard and API behavior.

**Picker-backed fields:** `spec.instance_type` and
`spec.network_attachments` load options from list APIs
([§2.1.5](#215-vm-instance-type-picker-api),
[§2.1.4](#214-vm-networking-picker-apis)). Cluster `spec.node_sets` is
template-backed: `ClusterTemplates.Get` supplies the map and typed
`baremetal_instance_type` references, while Catalog Item policy governs only
the `size` values. There is no per-row BareMetalInstanceType picker and no
tenant composition of node sets.

| Aspect     | Governed by a typed `fields` policy | Ungoverned |
| ---------- | --------------------------------------------------------------------------- | --------------------- |
| Label      | Wizard-defined translated label | Wizard-defined translated label |
| Editable   | `locked` → read-only; `editable` → tenant input | Normal wizard behavior |
| Default    | Typed Catalog default when present | Template/resource default or blank |
| Validation | Normal typed wizard/API validation; full step validation on Next (see [§2.2](#22-wizard-behavior)) | API/wizard validation |

**General basics and fulfillment create:** On Catalog selection, the wizard prefills supported typed Catalog defaults when defined. `spec.ssh_key` remains an ordinary optional wizard field and is not governed by Catalog Items v2. The client create payload includes a value when the field is non-blank; when the tenant clears an optional field, the client omits it and fulfillment applies the v2 policy, Template defaults, and normal resource defaults in the documented precedence order.

Locked fields are **read-only** on the wizard step (Configuration or Networking), not hidden, and their typed locked value is included in the payload. Editable fields may show a typed Catalog default; ungoverned fields use the normal wizard behavior. Read-only fields use disabled/read-only controls.

**Default rules:** Fields start **blank** unless a typed Catalog default is set or a **special case** applies:


| Case                | Behavior                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `spec.run_strategy` | Pre-select `Always` when no typed Catalog default                                                                         |
| OS family (VM)      | Pre-select **Linux** (`is_windows: false`)                                                                              |
| Instance type (VM)  | **Auto-select** when `InstanceTypes.List` returns exactly one option |
| Networking pickers  | **Auto-select** when a list returns exactly one option (VN → subnet) |

#### 2.1.3 Open required fields

Fields marked **?** in [§2.1.1](#211-static-wizard-fields) — resolve Required vs Optional before implementation ([§5](#5-open-decisions)).

### 2.1.4 VM networking picker APIs

The wizard loads picker options from the **public** fulfillment APIs (`osac.public.v1`). The UI uses the generated OpenAPI client (REST); gRPC equivalents are listed for reference.

| Picker | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Virtual network | `VirtualNetworks.List` | `GET /api/fulfillment/v1/virtual_networks` | Tenant-visible virtual networks |
| Subnet | `Subnets.List` | `GET /api/fulfillment/v1/subnets` | Subnets in the selected virtual network |
| SecurityGroup | `SecurityGroups.List` | `GET /api/fulfillment/v1/security_groups` | SecurityGroups in the selected virtual network |
| NetworkACL handling | No picker API | None | The effective ACL is inherited from the selected Subnet and must be Ready before placement. The wizard does not select or send an ACL reference |

**List request parameters** (all three list APIs): optional query `filter` (CEL), `limit`, `offset`, `order`. Tenant scope is implicit from the authenticated session.

**Subnet filter** (after virtual network selection):

```text
this.spec.virtual_network.name == "<vn-name>"
```

**SecurityGroup filter** (after virtual network selection):

```text
this.spec.virtual_network.name == "<vn-name>"
```

**Picker display and values:**

| Picker | Option label | Selected value |
| ------ | ------------ | -------------- |
| Virtual network | `metadata.name` | VirtualNetwork name — drives the Subnet list filter only |
| Subnet | `metadata.name` | `SubnetLocalReference` containing `name` |
| SecurityGroup | `metadata.name` | `SecurityGroupLocalReference` containing `name` |

**Create payload assembly** — one `spec.network_attachments` element:

```json
{
  "subnet": { "name": "<subnet-name>" },
  "security_groups": [{ "name": "<security-group-name>" }]
}
```

Per `ComputeNetworkAttachment` in `compute_instance_type.proto` and the
typed-reference contract in OSAC-1330. The wizard does not send virtual
network ID in `network_attachments`; placement is implied by the
Subnet reference. The selected Subnet determines the effective ACL, which must
be Ready before placement. An omitted `security_groups` list receives the
tenant default SecurityGroup; explicit references are typed and validated by
the shared contract.

**Load order:** virtual network list → on selection, load the filtered Subnet and
SecurityGroup lists → auto-select the Subnet when a list returns exactly one
item; SecurityGroup selection is optional and an empty selection invokes the
tenant default ([§2.1.2](#212-catalog-policy-and-defaults)).

### 2.1.5 VM instance type picker API

The Configuration step loads instance type options from the **public** fulfillment API (`osac.public.v1`). The UI uses the generated OpenAPI client (REST); gRPC equivalent listed for reference.

| Picker | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Instance type | `InstanceTypes.List` | `GET /api/fulfillment/v1/instance_types` | Tenant-visible instance types (ACTIVE and DEPRECATED by default) |

**List request parameters:** optional query `filter` (CEL), `limit`, `offset`, `order`. Tenant scope is implicit from the authenticated session. The default list excludes **OBSOLETE** instance types (not selectable for new VMs).

**Picker display and values:**

| Picker | Option label | Selected value |
| ------ | ------------ | -------------- |
| Instance type | `metadata.name` plus `spec.cores` and `spec.memory_gib` (e.g. `standard-4-16 — 4 vCPU, 16 GiB`); indicate **DEPRECATED** state in the label when `spec.state` is DEPRECATED | Instance type name (`metadata.name`) → typed `spec.instance_type` reference on create |

**Create payload:** send only the typed instance-type reference, with the
selected **name**:

```json
{
  "instance_type": { "name": "standard-4-16" }
}
```

The reference must contain `name`; identifier-only references are rejected by
OSAC-1330. Do **not** send `cores` or `memory_gib` — they are mutually
exclusive with `instance_type` at the API ([PR #735](https://github.com/osac-project/fulfillment-service/pull/735)).

**Deprecation handling:** if the selected type is DEPRECATED, create may succeed with **warnings** in the response; the wizard surfaces those warnings after submit (non-blocking). OBSOLETE types are not offered in the picker.

**Load order:** load instance type list when entering Configuration → auto-select when the list returns exactly one item ([§2.1.2](#212-catalog-policy-and-defaults)).

### 2.1.6 Cluster template node-set API

After the Catalog Item resolves its ClusterTemplate, the Configuration step
loads that template from the **public** fulfillment API (`osac.public.v1`).
The UI uses the generated OpenAPI client (REST); the gRPC equivalent is listed
for reference.

| Request | gRPC | REST | Purpose |
| ------ | ---- | ---- | ------- |
| Cluster template | `ClusterTemplates.Get` | `GET /api/fulfillment/v1/cluster_templates/{name}` | Resolve the authoritative node-set names, sizes, and typed BareMetalInstanceType references |

The response's `spec.node_sets` map is the complete set of rows shown by the
wizard. The wizard does not call `BareMetalInstanceTypes.List` for node-set
hardware selection and does not permit a tenant to add, remove, or replace a
template node set.

**Create payload** — preserve the Template node-set map keys and use typed
references for the hardware profile:

```json
{
  "node_sets": {
    "workers": {
      "baremetal_instance_type": { "name": "bm-standard" },
      "size": 3
    },
    "infra": {
      "baremetal_instance_type": { "name": "bm-infra" },
      "size": 1
    }
  }
}
```

Per `ClusterNodeSet` in `cluster_type.proto`, each value has the Template's
typed `baremetal_instance_type` and the effective `size`. Catalog Item
`node_sets` policies can default, lock, or permit editing of `size` only;
they cannot change the map keys or `baremetal_instance_type` references.

**Load order:** resolve the Catalog Item, fetch its ClusterTemplate, then load
the template-defined node sets and apply the Catalog Item size policies. A
missing or malformed template node set blocks Configuration and the create
request; there is no fallback to a tenant-composed row or a separate hardware
picker.

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
- Catalog policy and default rules per [§2.1.2](#212-catalog-policy-and-defaults) apply to supported typed fields, including the VM and Cluster networking policies. Locked fields are read-only, editable fields accept tenant input, and typed defaults prefill the wizard. No legacy generic field path or JSON-Schema policy is accepted.
- VM: single `network_attachments` entry assembled from picker APIs; instance type picker sets `spec.instance_type` (not `cores`/`memory_gib`); OS family radio sets `spec.is_windows` (default **Linux**); optional `user_data` omitted when empty; create warnings for deprecated instance types are shown to the user.
- Cluster: `node_sets` comes from the resolved ClusterTemplate; the wizard displays template node-set names and typed `baremetal_instance_type` references read-only and applies Catalog Item policies only to `size`; it does not add/remove rows or select hardware from `BareMetalInstanceTypes.List`.
- All **?** requiredness decisions resolved before release ([§5](#5-open-decisions)).
- On Next click, validate all fields on the current step (including untouched fields); surface hidden inline errors; show an alert if invalid; do not advance until the step is valid.

## 4. Dependencies

- `ComputeInstanceCatalogItem`, `ClusterCatalogItem` (with Catalog Items v2 `fields` policies)
- `ClusterTemplates.Get` (cluster Configuration step — authoritative node-set names, typed BareMetalInstanceType references, and template sizes)
- `VirtualNetworks.List`, `Subnets.List` (gRPC `osac.public.v1`) / REST `GET /api/fulfillment/v1/virtual_networks`, `.../subnets` ([§2.1.4](#214-vm-networking-picker-apis))
- `InstanceTypes.List` (gRPC `osac.public.v1`) / REST `GET /api/fulfillment/v1/instance_types` ([§2.1.5](#215-vm-instance-type-picker-api))
- ComputeInstance and Cluster create APIs
- `spec.instance_type` on ComputeInstance ([OSAC-1217](https://redhat.atlassian.net/browse/OSAC-1217), [fulfillment-service PR #735](https://github.com/osac-project/fulfillment-service/pull/735)) — required for VM instance type picker
- `spec.is_windows` on ComputeInstance ([OSAC-13](https://redhat.atlassian.net/browse/OSAC-13), [fulfillment-service PR #734](https://github.com/osac-project/fulfillment-service/pull/734)) — required for VM OS family in the wizard

## 5. Open decisions

Resolve before implementation.

### Required vs optional (`?`)

| Path | Resource |
| ---- | -------- |
| `spec.ssh_key` / `spec.ssh_public_key` | **Resolved:** Optional — `spec.ssh_public_key` may use its typed Catalog policy; `spec.ssh_key` is ordinary wizard input; omit from client payload when blank |
| `spec.boot_disk.size_gib` | ComputeInstance |

### Catalog policy on picker-backed fields

**Resolved:** Apply Catalog Items v2 typed policies to VM picker-backed paths (`spec.instance_type` and `spec.network_attachments`) and to the Cluster `network_attachment` field. Cluster `spec.node_sets` is template-backed; its Catalog policy applies only to `size` as defined by Catalog Items v2.

Catalog Items v2 does not support generic picker overlays, arbitrary display-name overrides, or JSON-Schema validation. A locked typed reference must resolve through the relevant list API, and an editable typed default is subject to the same readiness, scope, cardinality, and IPv4 validation as direct creation.

### Cluster `node_sets` ownership

**Resolved:** The resolved `ClusterTemplate.spec.node_sets` is authoritative.
The wizard fetches it with `ClusterTemplates.Get`, preserves each map key and
typed `baremetal_instance_type`, and exposes only the effective `size` under
the Catalog Item policy. Tenants cannot add/remove node sets or select a
different BareMetalInstanceType. See [§2.1.1](#211-static-wizard-fields) and
[§2.1.6](#216-cluster-template-node-set-api).

### Additional disks

Not in [§2.1.1](#211-static-wizard-fields) today. **Unknown** whether v1 needs wizard UI for `spec.additional_disks[]` or boot disk + API/CLI is enough.

| Option | Outcome |
| ------ | ------- |
| **No (default)** | Out of scope ([§1.2](#12-non-goals)); boot disk only |
| **Yes** | Add repeatable `size_gib` rows on Configuration; add to §2.1.1 |
