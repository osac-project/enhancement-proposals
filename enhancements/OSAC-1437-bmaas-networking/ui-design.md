---
title: bmaas-networking-ui
authors:
  - dmanor@redhat.com
creation-date: 2026-11-22
last-updated: 2026-11-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1437-bmaas-networking/ux-design.md"
  - "/enhancements/OSAC-1437-bmaas-networking/design.md"
  - "/enhancements/OSAC-1433-unified-networking/ui-design.md"
  - "/enhancements/OSAC-1435-vmaas-networking/ui-design.md"
  - "/enhancements/OSAC-1319-bare-metal-instance-ui/design.md"
  - "/enhancements/OSAC-3459-bmaas-provisioning-progress/ui-design.md"
replaces:
superseded-by:
---

# BMaaS Networking — UI Design Addendum

This addendum maps the [UX design](ux-design.md) to `osac-ui`. It changes no
UX decision; it records which component changes and which API field each UI
item reads or writes. The [rules for every networking page](/enhancements/OSAC-1433-unified-networking/ui-design.md#rules-for-every-networking-page)
apply. All fields exist in the public API; there are no protobuf, endpoint,
RBAC or persistence changes.

## Contents

- [1. Instance type network ports](#1-instance-type-network-ports)
- [2. Create wizard: Networking step](#2-create-wizard-networking-step)
- [3. Review step](#3-review-step)
- [4. Details page: Networking card](#4-details-page-networking-card)
- [5. Delete](#5-delete)
- [6. Instance type wizard: port roles (provider admin)](#6-instance-type-wizard-port-roles-provider-admin)
- [7. Field mapping](#7-field-mapping)
- [8. Failure handling](#8-failure-handling)
- [9. Component tests](#9-component-tests)
- [10. Out of scope and open questions](#10-out-of-scope-and-open-questions)

## 1. Instance type network ports

`BareMetalInstanceTypeDescription` (`components/BareMetalInstance/CreateWizard/fields/`)
adds a full-width **Network ports** `Card` after Disks with a compact `Table`:
**Port**, **Use**, **Type**, **Speed**. **Use** is "Tenant network" for
`role == "fabric"` (the first such port adds "(default)") and
"System (`<role>`)" otherwise. Ports keep the type's order.

## 2. Create wizard: Networking step

`BareMetalNetworkingStep` keeps `NetworkFields` (Tenant default / Custom
network cards, `DefaultNetworkSummary`, the VirtualNetwork, Subnet and
SecurityGroup fields, `AutoExternalIpField`) and adds
`BareMetalInterfaceField` between the network fields and the External IP
section, for both network choices:

- Options: `instanceType.spec.hardware.network_ports` with `role == "fabric"`,
  in order, labelled `name (speed)`, the first with "— default", description
  = `type`. The type is the one resolved by the Configuration step (the
  catalog item's when locked).
- Form state: `spec.interface` (`ProvisioningFieldValue<string>`) in
  `BareMetalInstanceWizardValues`, locked together with `spec.networkAttachment`
  (the catalog's `network_attachments` policy covers `interface`).
- Initial value and reset: the first fabric port; every instance type change
  selects the first fabric port of the new type.
- One fabric port: read-only text with helper "The only port of `<type>` that
  carries tenant networks."
- Catalog lock: the field is disabled with "Set by the catalog item." when the
  catalog item locks `network_attachments` (`ProvisioningField`).
- Helper: "The physical port that joins the subnet. Only ports of `<type>`
  that carry tenant networks are listed."
- The step description, the network choice and `AutoExternalIpField`
  (including its bare-metal helper text) stay as they are today.

Pickers: READY VirtualNetworks; Subnets and SecurityGroups of the selected
VirtualNetwork with `status.state == READY`. The VMaaS
`compute_instance_supported` Subnet filter and its helper text apply to the
VM wizard only; `NetworkFields` takes the workload kind and skips them for
bare metal.

**Payload** (`buildBareMetalInstanceCreatePayload`). Custom adds `interface`
to its one attachment, as the [Unified pickers table](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers)
says. Tenant default keeps sending `network_attachments: []` while the first
fabric port is selected, because the server picks that port itself (PRD
FR-5); only another port adds one attachment with just `interface` (the server
fills the tenant default Subnet and SecurityGroup). `primary` is never sent.
`auto_external_ip_attachment` and the catalog lock are unchanged.

```json
{ "network_attachments": [] }
{ "network_attachments": [{ "interface": "data-1" }] }
{ "network_attachments": [{ "subnet": { "id": "<id>" }, "security_groups": [{ "id": "<id>" }], "interface": "data-1" }] }
```

## 3. Review step

`BareMetalReviewStep` adds **Interface** after the network rows; the value is
the selected form value (`spec.interface`), even when the payload omits it,
with "(default)" when it is the first fabric port.

## 4. Details page: Networking card

`BareMetalNetworkingCard` replaces its table with a horizontal compact
`DescriptionList` (one attachment per server):

| Row | Value |
|---|---|
| Virtual network | VirtualNetwork of the Subnet, linked to its details page |
| Subnet | name, plain text (subnets have no details page) |
| Security groups | names, comma-separated, each linked |
| Interface | `status.network_attachment_statuses[].interface`, else the spec's; `name (speed)` from the type |
| Internal IP | see below |
| External IPs | one line per ExternalIP: `name (address)`, **Auto** `ResourceOriginBadge` for automatic ones; a dash when none |

The status entry is matched by `subnet_ref` equal to the attachment's Subnet
ID, not by index.

**Internal IP** reads `ip_address` and the `NETWORK_READY` condition through
the pure helper `bareMetalInternalIpState(instance)`, which returns
`address`, `pending`, `disabled` or `none` with the message:

- `NETWORK_READY` reason `Offboarding`, `NetworkDetaching` or
  `PowerOffFailed` (delete): the address, or a dash when none was found, with
  the cleanup message under it ("Network cleanup is in progress." or "Network
  cleanup did not complete.").
- Otherwise `ip_address` set: the address. Before offboarding starts the
  condition still reads "Network setup is complete.", which is not shown.
- `NETWORK_READY` False with reason `Progressing`, `PoweringOff`,
  `PoweringOn` or `LeasePending`: `SyncAltIcon` + "Pending" and the condition
  message under it.
- `NETWORK_READY` True with reason `ProvisioningDisabled`: "Not set up by
  OSAC" and the message.
- No condition while the server is PROVISIONING (host allocation, OS
  installation): "Pending" with no message.
- Otherwise (failed): a dash. The failure is shown by
  `BareMetalProvisioningProgress` (OSAC-3459), not repeated here.

**External IPs**: the hook `useBareMetalExternalIps(instanceId)`, shared by
the card, the Delete gate and the delete modal, loads `ExternalIPAttachments`
with `bareMetalInstanceAttachmentFilter(id)`
(`this.spec.baremetal_instance.id == "<id>"`, next to
`computeInstanceAttachmentFilter`; all pages, always, not only when
`auto_external_ip_attachment` is set), joined to `ExternalIPs` by ID, plus the
automatic ExternalIP by label `osac.openshift.io/auto-created-for == "<id>"`
when it has no attachment yet. An automatic ExternalIP without an attachment
adds "Attaches when the server is running with its internal IP." while the
server is PROVISIONING, RUNNING (the attachment follows within the 30-second
recheck) or STOPPED, and "Not attached." when the server or the ExternalIP is
FAILED (the ExternalIP also shows its Failed status). An attachment that is
DELETING shows `ExternalIpAttachmentStatusLabel` (Detaching). The card has no
attach or detach action.

## 5. Delete

`useBareMetalActions` / `BareMetalActionsMenu` gate **Delete**: when a loaded
ExternalIPAttachment that targets the server is not automatic, the item is
`isAriaDisabled` with the Tooltip "Delete the attachment of external IP
`<ExternalIP name>` first (Networking > External IPs > Attachments)." An
attachment is automatic only with creator `system`,
`osac.openshift.io/auto-created: "true"` and
`osac.openshift.io/auto-created-for: "<server id>"`
([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access));
tenant-set labels alone do not count. The same gate drives
`BareMetalActionsMenu` (list) and `BareMetalActionButtons` (details). The list
page loads the attachments once for all rows
(`has(this.spec.baremetal_instance)`), not one query per row. While the attachments load or fail to load, the
server's guard decides. The FabricDomain guard has no pre-check: the public
BareMetalInstance has no host name to match FabricDomain `servers`, so the
server's `FAILED_PRECONDITION` message shows in the modal.

`BareMetalDeleteConfirmModal` is unchanged.

## 6. Instance type wizard: port roles (provider admin)

`BareMetalNetworkPortsField` (`components/BareMetalInstanceType/CreatePage/fields/`):

- **Role** becomes a `Select` (was free text) with options and descriptions:
  `fabric` "Fabric" (Carries tenant networks), `management` "Management"
  (In-band control), `storage` "Storage", `lifecycle` "Lifecycle (BMC)" (BMC
  and provisioning). The stored value is the lowercase role. An existing type
  with another role shows it as a read-only extra option.
- **Name** validation (console guard) for ports with role `fabric`, the only
  ones a server can select: DNS label
  (`^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`), "Use lowercase letters, digits
  and hyphens.". The API accepts other names on the type but rejects a server
  that selects one, because the name is part of the NetworkAttachment name
  ([design](design.md#baremetalinstancetype-and-interface-selection)); the
  console stops it earlier.
- A type without a fabric port has no console check: the API rejects it
  (`hardware_spec.at_least_one_fabric_port`) and the wizard shows its message
  on submit, as for any create error.

## 7. Field mapping

| UI item | Screen | API field | Direction |
|---|---|---|---|
| Network ports card | Wizard, Configuration | `BareMetalInstanceType.spec.hardware.network_ports[]` | read |
| Tenant default / Custom | Wizard, Networking | `BareMetalInstance.spec.network_attachments[0].subnet` presence | write |
| VirtualNetwork, Subnet, SecurityGroups | Wizard, Networking | `spec.network_attachments[0].subnet`, `.security_groups` | write |
| Interface | Wizard, Networking; Review | `spec.network_attachments[0].interface` | write |
| Auto-attach external IP | Wizard, Networking | `spec.auto_external_ip_attachment` | write |
| Virtual network, Subnet, Security groups | Details | `spec.network_attachments[0]` resolved by ID | read |
| Interface | Details | `status.network_attachment_statuses[].interface` (matched by `subnet_ref`) | read |
| Internal IP | Details | `status.network_attachment_statuses[].ip_address` | read |
| Internal IP message | Details | condition `BARE_METAL_INSTANCE_CONDITION_TYPE_NETWORK_READY` `reason`, `message` | read |
| External IPs | Details | `ExternalIPAttachments` (target `baremetal_instance`), `ExternalIPs`, label `osac.openshift.io/auto-created-for` | read |
| Delete gate | Details, list | `ExternalIPAttachments` that are not automatic (creator `system` plus both `osac.openshift.io/auto-created` labels) | read |
| Port Role, Name | Admin type wizard | `BareMetalInstanceType.spec.hardware.network_ports[].role`, `.name` | write |

## 8. Failure handling

| Scenario | UI behavior |
|---|---|
| Create rejected (`INVALID_ARGUMENT` interface, `FAILED_PRECONDITION` gate or ExternalIPPool capacity) | Server message on the Review step, as today |
| Type has no fabric port (should not exist; API rejects it) | Interface field shows "This instance type has no port for tenant networks." and Next is blocked |
| Network setup in progress / failed / disabled / cleanup | [Internal IP rules](#4-details-page-networking-card) |
| Attachment or ExternalIP lists fail to load | Existing inline danger alert in the card; Delete is not pre-checked |
| Delete rejected by a guard | Server message in the delete modal, which stays open |

## 9. Component tests

Vitest + RTL with `createMockConnectTransport` (no fetch mocks). Fixtures: a
type with two fabric ports and two system ports, a type with one fabric port,
BMIs in each `NETWORK_READY` state (progress reasons, failed, `ProvisioningDisabled`,
cleanup), automatic and manual attachments.

| Suite | Coverage |
|---|---|
| `BareMetalInstanceTypeDescription` | Network ports card, Use text, default marker |
| `BareMetalInterfaceField` | fabric-only options in order; first selected; first port after every type change; one-port text; no-fabric-port error blocks Next; catalog lock |
| `useBareMetalExternalIps`, `bareMetalInternalIpState` | attachment filter and joins; automatic ExternalIP without attachment; manual vs automatic split; one case per row of the design's tenant message table |
| `buildBareMetalInstanceCreatePayload` | Custom with `interface`; Tenant default with the first port sends `[]`, with another port only `interface`; no `primary`; locked attachment omitted |
| `BareMetalReviewStep` | Interface row |
| `BareMetalNetworkingCard` | rows; status matched by `subnet_ref`; Internal IP for each `NETWORK_READY` case; manual and automatic external IPs; automatic ExternalIP without attachment text; no attach/detach |
| `BareMetalActionsMenu`, `BareMetalActionButtons` | Delete aria-disabled with the tooltip for a manual attachment, including one with tenant-set auto labels; enabled with only an automatic one; list page issues one attachment query |
| `BareMetalNetworkPortsField` | Role select values; name validation on fabric ports only |

## 10. Out of scope and open questions

- Attach and detach of external IPs on the server page ([UX decision](ux-design.md#product-decisions-this-release)).
- The 10-minute no-lease warning (PRD NFR-2) is administrator-visible only;
  the card keeps showing the tenant message "IP address discovery is in
  progress."
- FabricDomain delete pre-check: the public BareMetalInstance has no host name
  to match FabricDomain `servers`, so the server's guard decides.
- Shared components named here (`ResourceOriginBadge`,
  `ExternalIpAttachmentStatusLabel`) come from the
  [Unified UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md).
