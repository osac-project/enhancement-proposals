---
title: Configuration Wizard for Cluster and VM Resources
authors:
  - brotman@redhat.com
creation-date: 2026-06-14
last-updated: 2026-06-21
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1421
see-also:
  - Catalog Items: /enhancements/catalog-items
replaces:
  - N/A
superseded-by:
  - N/A
---

# Configuration Wizard for Cluster and VM Resources

## 1. Goals and Non-Goals

### 1.1 Goals

- Tenants provision VMs and clusters by selecting a catalog offering and completing a guided wizard with a **fixed field set per resource type** ([§2.1.1](#211-static-wizard-fields)).
- Both resource types use the same five steps: **Catalog → Access → Configuration → Networking → Review** (submit from Review). **Access** collects identity and credentials; **Configuration** collects image/release, sizing, and platform parameters — not networking placement.
- Catalog `field_definitions` overlay matching static paths for **display name**, **editability**, **default**, and **validation_schema** only — they do not add fields or payload paths ([§2.1.2](#212-catalog-overlay-and-defaults)).

### 1.2 Non-Goals

- **BareMetalInstance** provisioning (separate PRD)
- **Template parameters**
- **Multi-NIC** — wizard submits one `network_attachments` entry (one VN, one subnet, security groups); no add/remove NIC rows
- **Cluster pool add/remove** — tenants edit **size** only for template-defined `spec.node_sets` pools; no add/remove pools or `host_type` changes
- **`spec.additional_disks`** — wizard scope undecided ([§5](#5-open-decisions)); default: boot disk only

## 2. Requirements

### 2.1 Field model

#### 2.1.1 Static wizard fields

Fields are hardcoded per resource type, not discovered from `field_definitions`. **Required** column: **?** = required vs optional not yet decided ([§5](#5-open-decisions)).

**ComputeInstance**


| Step            | Path                      | Label                                    | Widget                                 | Required |
| --------------- | ------------------------- | ---------------------------------------- | -------------------------------------- | -------- |
| Access          | `metadata.name`           | Name                                     | Text                                   | Required |
| Access          | `spec.ssh_key`            | SSH public key                           | Text (multiline)                       | ?        |
| Configuration   | `spec.image.source_ref`   | VM image (OCI reference)                 | Text                                   | Required |
| Configuration   | `spec.user_data`          | User data (cloud-init / Ignition)        | Text (multiline)                       | Optional |
| Configuration   | `spec.cores`              | vCPUs                                    | Number                                 | ?        |
| Configuration   | `spec.memory_gib`         | Memory (GiB)                             | Number                                 | ?        |
| Configuration   | `spec.boot_disk.size_gib` | Boot disk size (GiB)                     | Number                                 | ?        |
| Configuration   | `spec.run_strategy`       | Run strategy                             | Select (`Always`, `Halted`)            | Required |
| Networking      | `spec.network_attachments` | Virtual network, subnet, security groups | Pickers ([§2.1.4](#214-vm-networking-picker-apis)) | Required |


**Cluster**


| Step            | Path                        | Label                                                         | Widget                               | Required |
| --------------- | --------------------------- | ------------------------------------------------------------- | ------------------------------------ | -------- |
| Access          | `metadata.name`             | Name                                                          | Text                                 | Required |
| Access          | `spec.ssh_public_key`       | SSH public key                                                | Text (multiline)                     | ?        |
| Access          | `spec.pull_secret`          | Pull secret                                                   | Text (multiline, masked)             | Required |
| Configuration   | `spec.release_image`        | OpenShift version (release image)                             | Text                                 | Required |
| Configuration   | `spec.node_sets`            | Worker node pools ([§2.1.1 notes](#211-static-wizard-fields)) | Table ([§2.2](#22-wizard-behavior)) | Required |
| Networking      | `spec.network.pod_cidr`     | Pod network CIDR                                              | Text                                 | ?        |
| Networking      | `spec.network.service_cidr` | Service network CIDR                                          | Text                                 | ?        |


**Notes (apply where relevant):**

- **`spec.user_data`** (VM only): plain multiline string (cloud-init or Ignition); omit from payload when empty. Stored as Secret → KubeVirt `cloudInitNoCloud`.
- **`spec.image`**: wizard collects `source_ref` only; payload always sets `spec.image.source_type` to **`registry`** ([§2.2](#22-wizard-behavior)). Future: ComputeImage list picker (OSAC-979).
- **Disks**: wizard collects `spec.boot_disk.size_gib` only unless [§5](#5-open-decisions) chooses `spec.additional_disks`.
- **Networking (VM)**: pickers assemble a single `spec.network_attachments` entry; raw JSON not shown. Catalog `field_definitions` for this path are ignored ([§2.1.2](#212-catalog-overlay-and-defaults)). APIs: [§2.1.4](#214-vm-networking-picker-apis).
- **Node sets (Cluster)**: after catalog selection, load `ClusterTemplates.Get` → one table row per `node_sets` key. Columns: pool name and `host_type` (read-only, from template + `HostTypes.Get`); **Nodes** = `size` input. Block if template `node_sets` is empty. Payload: template `host_type` + tenant/catalog `size` per pool.
- **Pull secret**: Cluster Access only; VM wizard never collects it, since the pull_secret field is not in the API spec of ComputeInstance.

#### 2.1.2 Catalog overlay and defaults

For each static field, match `field_definitions` by `path`. Non-matching paths are **ignored** (not on Review, not in payload).

**Exception — `spec.network_attachments`:** Catalog `field_definitions` matching `spec.network_attachments` or nested paths (e.g. `spec.network_attachments.subnet`) are **ignored**. VM networking is always driven by list APIs and picker UX ([§2.1.4](#214-vm-networking-picker-apis)); the catalog overlay does not apply display name, editability, default, or validation to networking pickers or payload assembly.


| Aspect     | Matching entry                                                              | No matching entry     |
| ---------- | --------------------------------------------------------------------------- | --------------------- |
| Label      | `display_name` or wizard default                                            | Wizard default        |
| Editable   | `editable: false` → read-only on wizard step (requires `default`; see [§2.2](#22-wizard-behavior)) | `true`                |
| Default    | Catalog `default` if set; else blank                                        | Blank                 |
| Validation | `validation_schema`                                                         | API/wizard validation |


**Default rules:** Fields start **blank** unless catalog `default` is set or a **special case** applies:


| Case                | Behavior                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `spec.run_strategy` | Pre-select `Always` when no catalog `default`                                                                            |
| Optional fields     | `spec.user_data` (and SSH if Optional per [§5](#5-open-decisions)): omit from payload when empty                         |
| Cluster node table  | Pool name / `host_type` from template; `size` blank unless catalog `default`                                             |
| Networking pickers  | Blank until chosen; **auto-select** when list API returns exactly one option (VN → subnet → SGs). Catalog `field_definitions` for `spec.network_attachments` are ignored ([§2.1.2](#212-catalog-overlay-and-defaults)). |

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

### 2.2 Wizard behavior

```mermaid
flowchart LR
  A[Catalog] --> B[Access]
  B --> C[Configuration]
  C --> D[Networking]
  D --> E[Review and Submit]
```

- Provisioning wizard for ComputeInstance and Cluster using [§2.1.1](#211-static-wizard-fields) with catalog overlay ([§2.1.2](#212-catalog-overlay-and-defaults)).
- **Catalog overlay:** Non-editable fields (`editable: false`) with a catalog `default` are **read-only** on the appropriate wizard step (Access, Configuration, or Networking), not hidden; value is included in the payload and on Review. Read-only fields use disabled/read-only controls (same widget type as editable fields where applicable). Non-editable without `default` → block after catalog selection.
- **Catalog step:** Require catalog item selection; Cluster must validate non-empty template `node_sets`.
- **Review:** Shows every static field value that will be sent (entered, catalog-defaulted, or assembled); no extra spec paths. Submit from Review.
- **Validation:** `validation_schema` maps to integer/enum/text widgets; inline errors block Next.
- **VM networking:** `GET /api/fulfillment/v1/virtual_networks`, `GET /api/fulfillment/v1/subnets`, `GET /api/fulfillment/v1/security_groups` ([§2.1.4](#214-vm-networking-picker-apis)) → assemble one `network_attachments` entry; auto-select when a list returns a single option ([§2.1.2](#212-catalog-overlay-and-defaults)).
- **Cluster Configuration:** Worker pool table per template `node_sets`; assemble `spec.node_sets`; each `size` > 0.
- **Create payload:** Contains only static wizard values, assembled networking/node sets, catalog item reference, and hardcoded `spec.image.source_type` = `registry` (VM). Dot-notation API paths.
- **APIs:** Consume `ComputeInstanceCatalogItem` / `ClusterCatalogItem` including `field_definitions`.

## 3. Acceptance Criteria

- Wizard provisions VM or Cluster using only [§2.1.1](#211-static-wizard-fields) payload paths plus hardcoded VM `source_type` and catalog item reference.
- Five-step flow: Catalog → Access → Configuration → Networking → Review; submit from Review.
- Catalog overlay and default rules per [§2.1.2](#212-catalog-overlay-and-defaults); non-editable fields without `default` block the wizard; non-editable fields with `default` appear read-only on their wizard step and on Review.
- VM: single `network_attachments` entry assembled from picker APIs; catalog `field_definitions` for `spec.network_attachments` are ignored; optional `user_data` omitted when empty.
- Cluster: `node_sets` matches template pool keys with template `host_type` and tenant `size` > 0; empty template `node_sets` blocks.
- All **?** requiredness decisions resolved before release ([§5](#5-open-decisions)).
- Inline validation; Next disabled until current step is valid.

## 4. Dependencies

- `ComputeInstanceCatalogItem`, `ClusterCatalogItem` (with `field_definitions`)
- `ClusterTemplates.Get`, `HostTypes.Get` (cluster Configuration step)
- `VirtualNetworks.List`, `Subnets.List`, `SecurityGroups.List` (gRPC `osac.public.v1`) / REST `GET /api/fulfillment/v1/virtual_networks`, `.../subnets`, `.../security_groups` ([§2.1.4](#214-vm-networking-picker-apis))
- ComputeInstance and Cluster create APIs

## 5. Open decisions

Resolve before implementation. Fields marked **?** in [§2.1.1](#211-static-wizard-fields) - should they be required or optional?

### Required vs optional (`?`)

| Path | Resource |
| ---- | -------- |
| `spec.ssh_key` / `spec.ssh_public_key` | Both — **one decision**: Required (block Next) vs Optional (omit when empty, like `spec.user_data`) |
| `spec.cores`, `spec.memory_gib`, `spec.boot_disk.size_gib` | ComputeInstance |
| `spec.network.pod_cidr`, `spec.network.service_cidr` | Cluster |

### Additional disks

Not in [§2.1.1](#211-static-wizard-fields) today. **Unknown** whether v1 needs wizard UI for `spec.additional_disks[]` or boot disk + API/CLI is enough.

| Option | Outcome |
| ------ | ------- |
| **No (default)** | Out of scope ([§1.2](#12-non-goals)); boot disk only |
| **Yes** | Add repeatable `size_gib` rows on Configuration; add to §2.1.1 |
