---
title: vmaas-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-10-13
last-updated: 2026-10-13
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1435-vmaas-networking/design.md"
  - "/enhancements/OSAC-1433-unified-networking/ui-design.md"
  - "/enhancements/OSAC-1436-caas-networking/ui-design.md"
  - "/enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md"
replaces:
superseded-by:
---

# VMaaS Networking — UI Design Addendum

## Summary

Documents the implemented `osac-ui` behavior for OSAC-1435 VMaaS networking:
provisioning-time network attachment selection via the VM wizard, post-provision
external IP attachment, and display of networking and IP information on VM list
and detail pages. This addendum covers the tenant-facing VM experience only;
Cloud Provider Admin networking management (ExternalIPPool) and shared
networking resource management (VirtualNetwork, Subnet, SecurityGroup,
ExternalIP) are covered by the
[Unified Networking UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md).

All networking resources and the VM `network_attachments` field follow the
unified create/read/delete contract: read uses List/Get, and changes require
delete and recreate. The `network_attachments` field is immutable after VM
creation — the UI does not provide an edit form for it.

## Proposal

### Tenant User

#### VM Provisioning Wizard — Networking Step (Step 4)

The VM provisioning wizard
([OSAC-1421](/enhancements/OSAC-1421-cluster-and-vm-provisioning-wizard/design.md))
defines a five-step flow (Catalog Item -> General -> Configuration -> Networking
-> Review). The Networking step (`VmNetworkingStep`,
`wizard/adapters/computeInstance/`) presents three cascading picker fields that
produce a single `network_attachments` entry in the create payload.

All three pickers are **required** — the wizard does not support omitting
network configuration. The tenant must explicitly select a Virtual Network,
Subnet, and at least one Security Group.

- **Virtual Network** (`SelectField`): loads from `useVirtualNetworks()` with
  `VIRTUAL_NETWORK_READY_LIST_FILTER` — only READY VirtualNetworks appear.
  Displays resource name via `resourceDisplayName()`. Required. Auto-selects
  when the list returns exactly one option.

- **Subnet** (`SelectField`): loads from `useSubnets()` filtered by
  `virtualNetworkFilterForSubnetList(virtualNetworkId)` — only READY Subnets
  belonging to the selected VirtualNetwork appear. Disabled until a
  VirtualNetwork is selected. Required. Auto-selects when the filtered list
  returns exactly one option.

- **Security Groups** (`MultiSelectField`): loads from `useSecurityGroups()`
  filtered by `securityGroupFilterForVirtualNetworkList(virtualNetworkId)` —
  only READY SecurityGroups belonging to the selected VirtualNetwork appear.
  Disabled until a VirtualNetwork is selected. At least one selection required.
  Auto-selects when the filtered list returns exactly one option.

**Cascade reset:** when the VirtualNetwork selection changes, the Subnet and
Security Groups values are cleared and the tenant must re-select them. This
prevents stale cross-VN references.

**Error handling:** if any networking list API call fails, an inline danger
`Alert` is shown with a **Retry** button that refetches all three lists.

**Validation:** Yup schema enforces that `virtualNetwork` (required string),
`subnet` (required string), and `securityGroups` (array, min 1) are populated.
Validation runs on the Networking step when the tenant clicks Next.

**Payload assembly** (`buildComputeInstanceCreatePayload`):

The wizard always sends a single-entry `networkAttachments` array containing
the selected Subnet ID and Security Group IDs. The VirtualNetwork ID is
**not** included in the payload — the fulfillment-service infers it from the
Subnet reference.

```json
{
  "spec": {
    "networkAttachments": [
      {
        "subnet": { "id": "<subnet-id>" },
        "securityGroups": [{ "id": "<sg-id>" }]
      }
    ]
  }
}
```

#### Default Network Behavior

The VM wizard currently requires explicit selection of all three networking
fields (VirtualNetwork, Subnet, Security Groups). Server-side defaulting
([PRD FR-3](prd.md), [Default Networking PRD](/enhancements/OSAC-1433-default-networking/prd.md))
supports omitting the `network_attachments` field entirely, in which case the
fulfillment-service populates it with the tenant's default Subnet and default
SecurityGroup. The VM wizard does not expose this server-side default path — it
always sends an explicit `network_attachments` entry.

When a tenant has only one VirtualNetwork, one Subnet, and one SecurityGroup
(the common single-default-network scenario), all three pickers auto-select
their sole option, effectively providing a one-click default experience without
requiring the tenant to manually browse the lists.

**Limitation — no "Use tenant default network" toggle:** the VM wizard does not
offer a toggle to skip the network pickers and rely on server-side defaults.
The [CaaS Networking UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md)
specifies a shared `NetworkAttachmentPickers` component with a "Use tenant
default network" toggle and optional pickers; that design also notes refactoring
the VM adapter to use the shared component. This refactor is not yet
implemented — the VM wizard retains its original inline picker implementation
with all-required validation.

#### Review Step — Networking Section

The review step (`VmReviewStep`) fetches resource names for display by calling
`useVirtualNetwork()`, `useSubnet()`, and `useSecurityGroups()` with the
selected IDs and renders:

- **Virtual network**: resolved name, falling back to ID
- **Subnet**: resolved name, falling back to ID
- **Security groups**: comma-separated resolved names, falling back to IDs

No "Auto External IP" field is shown in the review step (see
[Automatic External IP at Provisioning Time](#automatic-external-ip-at-provisioning-time)).

#### VM Detail Page

Extends `VmDetailsPage` at `/vms/:id`.

**Summary cards** (`VmDetailsSummary`): three cards displayed above the tab bar:

| Card | Icon | Data source | Empty state |
|------|------|-------------|-------------|
| **Instance type** | `ServerIcon` | `vm.spec.instanceType.id` via `VmInstanceTypeLabel` | — |
| **External IP** | `GlobeIcon` | `vm.status.externalIpAddress` | `—` (em dash) |
| **Internal IP** | `NetworkWiredIcon` | `vm.status.internalIpAddress` | `—` (em dash) |

IP address cards display the allocated address string when available. Before
provisioning completes or when no address is assigned, the card shows an em
dash. The Internal IP corresponds to the address discovered from the KubeVirt
VMI network status for the VM's sole network attachment
([design.md — IP Discovery](design.md)). The External IP is the address of an
ExternalIPAttachment targeting this VM, when one exists.

**Tabs:** Overview, Networking, Console.

**Networking tab** (`VmNetworkingTab`): displays the VM's network attachments
from `vm.spec.networkAttachments` in a table:

| Column | Data source |
|--------|-------------|
| **Virtual network** | Derived from the attachment's Subnet — the Subnet's parent VN is looked up via `useSubnets()` and `useVirtualNetworks()` |
| **Subnet** | `attachment.subnet.id`, resolved to name via `formatResourceIdForReview()` |
| **Security groups** | `attachment.securityGroups[].id`, resolved to comma-separated names |

When `vm.spec.networkAttachments` is empty, the tab shows "No virtual networks
configured."

Name resolution uses `useVmNetworkAttachmentRows()` which fetches the full
Subnet and VirtualNetwork lists to map IDs to display names.

**Action buttons** (`VmDetailsActionButtons`): Start, Stop, Restart, **Attach
external IP**, Delete. See
[Post-Provision External IP Attachment](#post-provision-external-ip-attachment)
for the attach workflow.

#### VM List Page

The VM list page (`VmTable`) at `/vms` includes networking columns:

| Column | Data source | Notes |
|--------|-------------|-------|
| **Name** | `vm.metadata.name` | Linked to `/vms/:id` (disabled when deleting) |
| **Status** | `vm.status.state` | `VmStatusLabel` component |
| **Instance type** | `vm.spec.instanceType.id` | `VmInstanceTypeLabel` component |
| **Internal IP** | `vm.status.internalIpAddress` | `—` when empty or deleting |
| **External IP** | `vm.status.externalIpAddress` | `—` when empty or deleting |
| **Created** | `vm.metadata.creationTimestamp` | `Timestamp` component |
| **Actions** | — | `VmActionsMenu` (hidden when deleting) |

When a VM is in `DELETING` state, both IP columns display `—` regardless of
their actual value.

#### Automatic External IP at Provisioning Time

The backend design ([design.md](design.md)) specifies an
`auto_external_ip_attachment` boolean field on `ComputeInstanceSpec` that
auto-provisions an ExternalIP and ExternalIPAttachment when a VM is created.

**The VM provisioning wizard does not expose this field.** The
`ComputeInstanceWizardValues` type has no `autoExternalIpAttachment` property,
the Networking step has no toggle for it, and `buildComputeInstanceCreatePayload`
does not include it in the request. Tenants who want external access for a VM
must attach an external IP after provisioning via the detail page action button
(see below), or use the CLI/API directly with the `--external-ip-attachment`
flag.

The [CaaS Networking UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md)
specifies an "Auto External IP Attachment" `SwitchField` toggle in the cluster
wizard's Infrastructure Networking section and notes that the shared
`NetworkAttachmentPickers` component will also be adopted by the VM adapter.
This shared component and the provisioning-time auto-external-IP toggle are not
yet implemented for VMs.

#### Post-Provision External IP Attachment

The VM detail page provides a post-creation workflow to attach an external IP
to a running VM. This is the primary UI path for giving a VM external
connectivity.

**Preconditions** (`canAttachExternalIp`):

- VM state is `RUNNING`
- VM does not already have an external IP (`!vm.status.externalIpAddress`)

When both conditions are met, the **Attach external IP** button (with
`GlobeIcon`) is enabled. Otherwise it is disabled.

**Attach External IP modal** (`AttachExternalIpModal`):

- Opens when the tenant clicks "Attach external IP"
- Displays a single **External IP pool** picker (`SelectField`) loaded from
  `useExternalIPPools()`, showing each pool's name and available count
  (e.g., "pool-name (3 available)")
- Auto-selects when only one pool is available
- Validates that a pool is selected (Yup required string)
- **No pools available:** warning `Alert` — "No external IP pools available.
  Contact your administrator to have an external IP pool provisioned."
- **Pool loading error:** danger `Alert` with error message

**Attachment workflow** (`useAttachExternalIp` mutation):

1. Creates an ExternalIP from the selected pool via `ExternalIPs.Create`
2. Polls the ExternalIP status at 500 ms intervals (max 20 attempts) until
   state reaches `EXTERNAL_IP_STATE_ALLOCATED`
3. On successful allocation: creates an ExternalIPAttachment via
   `ExternalIPAttachments.Create` with
   `target: { case: 'computeInstance', value: { id: vmId } }`
4. On success: invalidates ComputeInstance queries to refresh the detail page
   IP display
5. On allocation timeout or failure: deletes the created ExternalIP to avoid
   orphaned resources
6. On attachment creation failure: deletes the allocated ExternalIP to avoid
   orphaned resources
7. Errors are shown as inline danger `Alert` in the modal

**No detach workflow:** the VM detail page does not provide a "Detach" action
to remove an attached external IP. Once an external IP is attached to a VM
through the UI, the tenant must use the CLI/API to delete the
ExternalIPAttachment and then the ExternalIP through the CLI/API. Because
these resources are created directly by the UI (not auto-provisioned), a
manually created attachment blocks VM deletion until removed
([design.md](design.md) § Deletion). This is a one-way operation in
the current UI.

## Failure Handling

| Scenario | UI behavior |
|---|---|
| Networking step: VN/Subnet/SG list load failure | Inline danger `Alert` with Retry button; all three lists refetched on retry. |
| Networking step: no READY VirtualNetworks | VN picker shows empty dropdown; Next blocked by required-field validation. |
| Networking step: no READY Subnets in selected VN | Subnet picker shows empty dropdown; Next blocked by required-field validation. |
| Networking step: no READY SecurityGroups in selected VN | SG picker shows empty dropdown; Next blocked by required-field validation. |
| VM create: server rejects network config | Server error shown inline on Review step (existing wizard error handling). |
| Attach external IP: no pools available | Warning alert in modal; pool picker disabled; Attach button disabled. |
| Attach external IP: pool load error | Danger alert in modal with error message. |
| Attach external IP: allocation timeout | ExternalIP cleaned up; danger alert shown in modal. |
| Attach external IP: allocation failed | ExternalIP cleaned up; danger alert shown in modal with failure message. |
| Attach external IP: attachment creation failed | Allocated ExternalIP cleaned up; danger alert shown in modal. |
| VM list/detail: IP not yet available | `—` (em dash) shown in IP column/card. |
| VM deleting: IP display | `—` shown regardless of actual IP values. |
| Networking tab: no attachments | "No virtual networks configured." message. |

## Implementation Details

### Components

```text
libs/ui-components/src/components/
  catalogProvision/wizard/adapters/computeInstance/
    VmNetworkingStep.tsx          — Networking step with VN/Subnet/SG pickers
    VmReviewStep.tsx              — Review step with resolved network names
    fields.ts                     — ComputeInstanceNetworkingValues type
    schemas.ts                    — Yup validation (all networking required)
    payload.ts                    — buildComputeInstanceCreatePayload
  vm/
    VmTable.tsx                   — List page with Internal/External IP columns
    DetailsPage/
      VmDetailsSummary.tsx        — Summary cards (Instance type, External IP, Internal IP)
      VmDetailsActionButtons.tsx  — Action buttons including Attach external IP
      VmNetworkingTab.tsx         — Networking tab (VN, Subnet, SG table)
      useVmNetworkAttachmentRows.ts — Hook to resolve attachment IDs to names
      AttachExternalIpModal.tsx    — External IP pool selection and attach modal
```

### Hooks

**Reused from OSAC-1421 / OSAC-1433:**

- `useVirtualNetworks(params)` — list with CEL filter support
- `useVirtualNetwork(id)` — fetch single VN
- `useSubnets(params)` — list with CEL filter support
- `useSubnet(id)` — fetch single Subnet
- `useSecurityGroups(params)` — list with CEL filter support

**Reused from OSAC-1433 (Unified Networking UI):**

- `useExternalIPPools()` — list available pools with name and available count
- `useAttachExternalIp()` — mutation: create ExternalIP, poll until allocated,
  create ExternalIPAttachment; cleanup on failure

**Helper functions:**

- `virtualNetworkFilterForSubnetList(vnId)` — CEL filter for READY Subnets in
  a VirtualNetwork
- `securityGroupFilterForVirtualNetworkList(vnId)` — CEL filter for READY
  SecurityGroups in a VirtualNetwork
- `VIRTUAL_NETWORK_READY_LIST_FILTER` — CEL filter for READY VirtualNetworks
- `resourceDisplayName(metadata, id)` — display name with ID fallback
- `formatResourceIdForReview(id, resources)` — resolve ID to name for review
  display

### Data Flow

```text
VM Wizard Networking Step:
  VirtualNetworks.List (READY) → VN picker
  Subnets.List (filtered by VN, READY) → Subnet picker
  SecurityGroups.List (filtered by VN, READY) → SG multi-select
  → Formik values: { virtualNetwork, subnet, securityGroups[] }
  → Payload: { networkAttachments: [{ subnet: {id}, securityGroups: [{id}] }] }

VM Detail Page:
  ComputeInstance.Get → status.internalIpAddress → Internal IP card
  ComputeInstance.Get → status.externalIpAddress → External IP card
  ComputeInstance.Get → spec.networkAttachments → Networking tab table
  Subnets.List + VirtualNetworks.List → ID-to-name resolution

Post-Provision Attach:
  ExternalIPPools.List → pool picker in modal
  ExternalIPs.Create → poll until ALLOCATED → ExternalIPAttachments.Create
  → invalidate ComputeInstance queries → refreshed IP display
```

## Limitations and Future Work

| Area | Current state | Future direction |
|------|--------------|-----------------|
| **Default network toggle** | Not implemented; all networking pickers are required | [OSAC-1436 CaaS Networking UI](/enhancements/OSAC-1436-caas-networking/ui-design.md) specifies a shared `NetworkAttachmentPickers` component with a "Use tenant default network" toggle and notes it will also be adopted by the VM adapter |
| **Auto External IP at provisioning** | Not exposed in the VM wizard; available via CLI/API only | Same shared component design includes an "Auto External IP Attachment" toggle for the cluster wizard; adoption for VMs is planned as part of the shared component refactor |
| **External IP detach** | No detach action in the VM UI; one-way attach only | The CaaS networking design implements per-endpoint attach/detach for clusters; a similar pattern could be adopted for VMs |
| **Shared `NetworkAttachmentPickers`** | VM wizard uses inline picker implementation | CaaS design extracts pickers into a shared component; VM adapter refactor is specified but not yet implemented |
| **Networking tab IP display** | Networking tab shows spec-level VN/Subnet/SG only; IPs shown in summary cards | The `compute_network_attachment_statuses` field from [design.md](design.md) could surface per-attachment allocated IPs in the Networking tab |
