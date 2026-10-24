---
title: unified-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-08-12
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2632
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking/design.md"
replaces:
superseded-by:
---

# Unified Networking — UI Design Addendum

## Contents

- [Summary](#summary)
- [Proposal](#proposal)
  - [Rules for every networking page](#rules-for-every-networking-page)
  - [Cloud Infrastructure Admin](#cloud-infrastructure-admin)
    - [NetworkClass view](#networkclass-view)
    - [ExternalIPPool management](#externalippool-management)
  - [Tenant Admin and Tenant User](#tenant-admin-and-tenant-user)
    - [VirtualNetwork management](#virtualnetwork-management)
    - [NATGateway field in VirtualNetwork](#natgateway-field-in-virtualnetwork)
    - [Subnet management](#subnet-management)
    - [SecurityGroup management](#securitygroup-management)
    - [ExternalIP management](#externalip-management)
    - [ExternalIPAttachment management](#externalipattachment-management)
    - [Workload network attachment pickers](#workload-network-attachment-pickers)
- [Failure Handling](#failure-handling)
- [Implementation Details](#implementation-details)
  - [Component tests](#component-tests)

## Summary

The `osac-ui` pages for the [Unified Networking](design.md) resources ([OSAC-2632](https://redhat.atlassian.net/browse/OSAC-2632); screen-level UX: [OSAC-2226](https://redhat.atlassian.net/browse/OSAC-2226)), covering [PRD FR-11](prd.md#fr-11-unified-networking-ui-and-documentation).

## Proposal

### Rules for every networking page

- The UI uses the fulfillment API calls of the [design](design.md#api-operation-constraint): List, Get, Create, Delete, and SecurityGroup Update. Its only edit form is **Edit rules** ([SecurityGroup management](#securitygroup-management)); any other change is delete and recreate.
- Status shows the API `state` and `message` ([Status](design.md#status)).
- Resources with the label `osac.openshift.io/default: "true"` show a **Default** badge; automatic resources show the **Auto** badge ([CaaS UI — Automatic resource indicators](/enhancements/OSAC-1436-caas-networking/ui-design.md#automatic-resource-indicators)). Delete is disabled for both, with a tooltip.
- Every Delete asks for confirmation; the server's [deletion guards](design.md#deletion-dependency-guards) decide.
- Pickers follow [Workload network attachment pickers](#workload-network-attachment-pickers).
- No page says or implies that an ExternalIP is reachable from the Internet. Address fields carry the help text "Reachable where your provider routes it."

### Cloud Infrastructure Admin

Both pages are in the admin **Infrastructure** navigation, next to Storage and Instance types, and use the private API.

#### NetworkClass view

Read-only page (`NetworkClassPage`) at `/admin/infrastructure/network-class`, from `NetworkClasses.List` (one record). It shows title, description, `state` and `message`, `fabric_manager`, `k8s_manager`, the resolved `network_managers` (name and Ansible role) and `network_type`, the defaults (CIDRs and SecurityGroup rules), the `address_plan` shares ([Subnet address plan](design.md#subnet-address-plan)), and `supports_east_west_ethernet`. It has no create or delete; the installer creates the NetworkClass ([NetworkClass](design.md#networkclass)).

#### ExternalIPPool management

- **List page** (`ExternalIpPoolsListPage`) at `/admin/infrastructure/external-ip-pools`. Columns: **Name**, **IPv4 CIDR**, **Available / Total** (`status.available` / `status.total`), **State** (`ExternalIpPoolStatusLabel`). Row action **Delete**; **Create pool** opens the create form.
- **Create form** (`ExternalIpPoolFormPage`, Formik and Yup): **Name** (DNS label) and one canonical **IPv4 CIDR**; client validation rejects IPv6, empty, malformed, and multiple CIDRs. Submits `{ metadata: { name }, spec: { ipFamily: "IP_FAMILY_IPV4", cidrs: [cidr] } }`.

### Tenant Admin and Tenant User

All pages are in the tenant **Networking** navigation.

#### VirtualNetwork management

- **List page** (`VirtualNetworksPage`) at `/networking/virtual-networks`. Columns: **Name**, **IPv4 CIDR**, **Subnets**, **NAT Gateway** (below), **Status** (`VirtualNetworkStatusLabel`).
- **Create modal** (`VirtualNetworkCreateModal`): **Name** and **IPv4 CIDR**; no NetworkClass field. The server checks the prefix limit, which depends on the deployment's address plan ([Subnet address layout](design.md#subnet-address-layout)); the form shows its error message.
- **Detail page** (`VirtualNetworkDetailPage`) at `/networking/virtual-networks/:id`, with the tabs **Subnets**, **Security Groups**, and **Details** (including the NAT Gateway field).
- **Delete:** header action; the confirmation lists the dependents the UI knows.

#### NATGateway field in VirtualNetwork

- The **NAT Gateway** column and detail field show the NATGateway's ExternalIP address and status (`NatGatewayStatusLabel`), or a dash.
- **Attach NAT Gateway** (no NATGateway; VirtualNetwork READY and not a tenant default) opens a modal listing ExternalIPs that are ALLOCATED, not automatic, not a tenant default, and have no consumer: `useExternalIPs({ filter: 'this.status.state == EXTERNAL_IP_STATE_ALLOCATED && !("osac.openshift.io/auto-created" in this.metadata.labels) && !("osac.openshift.io/default" in this.metadata.labels)' })`, minus every ExternalIP that a NATGateway or an ExternalIPAttachment references (from the lists the UI already holds). Confirm creates the NATGateway for that VirtualNetwork.
- **Detach** (NATGateway exists) deletes the NATGateway. Changing the ExternalIP is Detach, then Attach.
- The list page fetches NATGateways once (`NatGateways.List`, unfiltered) and indexes them by `spec.virtual_network.id`. The detail page uses `useNatGatewayForVirtualNetwork(vnId)` (`NatGateways.List` with filter `this.spec.virtual_network.id == "<vnId>"`, first result).

#### Subnet management

- The **Subnets** tab lists **Name**, **IPv4 CIDR**, **Status**.
- **Create** (VirtualNetwork READY): **Name** and **IPv4 CIDR**, inside the VirtualNetwork's CIDR. The server checks the prefix limit ([Subnet address layout](design.md#subnet-address-layout)); the form shows its error message.
- **Delete:** row action.

#### SecurityGroup management

- The **Security Groups** tab, and the list page at `/networking/security-groups`, list **Name**, **VirtualNetwork**, **Ingress rules**, **Egress rules**, **Status**.
- **Create** (VirtualNetwork READY): **Name**, and ingress and egress rule lists. Each rule has **Protocol** (TCP, UDP, ICMP, ALL), **Port from** and **Port to** (TCP and UDP only, required), and an **IPv4 CIDR** (ingress source or egress destination) ([SecurityGroup](design.md#securitygroup)).
- **Edit rules:** row action, also on the default SecurityGroup, never on an automatic one. It opens the create form's rule lists filled with the current rules; Save sends `SecurityGroups.Update` with the complete lists, which replace the old ones on every workload that uses the group ([rule updates](design.md#securitygroup)). While the update runs, a READY group stays READY with the message `Updating`, and a FAILED group shows PENDING ([Status](design.md#status)); **Edit rules** is disabled while the group is PENDING or `Updating`. A final failure shows FAILED with the manager's message, and **Edit rules** stays available to fix the rules.
- **Delete:** row action.

#### ExternalIP management

- **List page** (`ExternalIpsListPage`) at `/networking/external-ips`. Columns: **Name**, **Address**, **Pool**, **Used by** (the referencing NATGateway or ExternalIPAttachment), **Status** (`ExternalIpStatusLabel`). Row action **Delete**.
- **Create form:** **Name** and a pool select from `useExternalIPPools()` (public fields) showing each pool's `available`; pools with `available` 0 are disabled.

#### ExternalIPAttachment management

- **List page** (`ExternalIpAttachmentsListPage`) at `/networking/external-ip-attachments`. Columns: **Name**, **External IP** (address), **Target** (kind, name, and endpoint for a Cluster), **Status**. Row action **Delete**; it keeps the ExternalIP.
- **Create form:** an ExternalIP picker (the Attach NAT Gateway filter), the target kind (virtual machine, bare-metal instance, or Cluster), the target, and for a Cluster the endpoint (`API` or `INGRESS`). The server rejects a target that is not ready ([ExternalIPAttachment](design.md#externalipattachment)).
- The Cluster detail page manages a Cluster's attachments per endpoint ([CaaS UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md)).

#### Workload network attachment pickers

The VM, bare-metal, and Cluster create wizards have the **Use tenant default network** toggle. Toggle on: the attachment is omitted and the tenant defaults apply ([defaulting](design.md#network-attachment-field-presence-and-defaulting)). Toggle off: the shared `NetworkAttachmentPickers` component shows the pickers in the table below (bare-metal interface selection: [BMaaS UX Alignment](/enhancements/OSAC-1437-bmaas-networking/design.md#ux-alignment)). Pickers offer only READY resources of one VirtualNetwork, never an automatic SecurityGroup; the server checks the [gates](design.md#creation-readiness-gates) the UI cannot see, and the form shows its message. No wizard sets `auto_external_ip_attachment`.

`NetworkAttachmentPickers` (`libs/ui-components/`) renders the cascading VirtualNetwork → Subnet → SecurityGroup pickers for the VM, bare-metal, and Cluster wizard adapters:

| Aspect | Shared component | VM adapter | Bare-metal adapter | Cluster adapter |
|---|---|---|---|---|
| VirtualNetwork picker | `SelectField` from `useVirtualNetworks()`; shows Name and IPv4 CIDR | Required | Required | Optional |
| Subnet picker | `SelectField` from `useSubnets()`, filtered by the selected VirtualNetwork | Required | Required | Optional while no VirtualNetwork is selected; required once one is |
| SecurityGroup multi-select | `MultiSelectField` from `useSecurityGroups()`, filtered by the selected VirtualNetwork, without automatic SecurityGroups | Required | Required | Required only for a Subnet outside the tenant's default VirtualNetwork |
| Cascade reset | Clearing the VirtualNetwork clears Subnet and SecurityGroups | Same | Same | Same |
| Auto-select | A one-option list selects that option | Same | Same | Same |
| Other fields | — | — | **Interface** select of the BareMetalInstanceType's `fabric` ports, first selected | `pod_cidr`, `service_cidr` |
| Payload | — | `network_attachments: [{...}]` (array) | `network_attachments: [{...}]` (array, one item, with `interface`) | `network_attachment: {...}` (singular) |

```text
libs/ui-components/src/components/form/
  NetworkAttachmentPickers.tsx
  NetworkAttachmentPickers.test.tsx
```

```typescript
interface NetworkAttachmentPickersProps {
  /** Formik field path prefix. VM: "spec.network_attachments.0", Cluster: "spec.network_attachment" */
  fieldPrefix: string;
  /** When to require security group selection */
  sgRequired: 'always' | 'when-non-default-vn' | 'never';
  /** Default VN API ID for conditional SG validation (only for 'when-non-default-vn') */
  defaultVnId?: string;
  /** Whether all pickers are optional (cluster: true, VM: false) */
  allOptional?: boolean;
  /** Whether to show VN/Subnet IPv4 CIDR in picker options */
  showCidr?: boolean;
}
```

The component owns the pickers with data loading, cascade reset, auto-select, conditional SecurityGroup validation, and loading and error states. Each adapter owns its Formik prefix, Yup schema fragment, payload shape (`buildCreatePayload`) and other fields. The Cluster adapter: [CaaS UI design](/enhancements/OSAC-1436-caas-networking/ui-design.md).

## Failure Handling

The UI shows the server's message as a form-level or inline error, reads error reasons only from `ErrorInfo.reason`, and keeps the resource row listed. Codes and messages: [Error codes](design.md#error-codes).
- `ABORTED` or `INTERNAL`: the action stays available for retry.
- A failing backend delete task: the row shows DELETING with the message; OSAC retries, the UI does nothing.
- Any List or Get failure: `QueryErrorState`.

## Implementation Details

- **Tenant hooks** (`api/v1/networking.ts`, `api/v1/external-ip.ts`): `useNatGateways`, `useNatGatewayForVirtualNetwork`, `useCreateNatGateway`, `useDeleteNatGateway`, `useExternalIPs`, `useCreateExternalIP`, `useDeleteExternalIP`, `useExternalIPAttachments`, `useCreateExternalIPAttachment`, `useDeleteExternalIPAttachment`, `useExternalIPPools`, plus the VirtualNetwork, Subnet, and SecurityGroup hooks, including `useUpdateSecurityGroup`. Types from `@osac/types`; routes `v1/nat_gateways`, `v1/external_ips`, `v1/external_ip_attachments`.
- **Admin hooks** (`api/v1/private/external-ip-pools.ts`, `api/v1/private/network-classes.ts`): `usePrivateExternalIPPools`, `usePrivateExternalIPPool`, `useCreateExternalIPPool`, `useDeleteExternalIPPool`, `usePrivateNetworkClasses`. Types from `@osac/types/private`; routes `v1/private/external_ip_pools`, `v1/private/network_classes`.
- **Status labels:** `NatGatewayStatusLabel`, `ExternalIpStatusLabel`, `ExternalIpAttachmentStatusLabel`, `ExternalIpPoolStatusLabel`, `NetworkClassStatusLabel`: thin wrappers around `ResourceStatusLabel` and `StatusKind`, like `SecurityGroupStatusLabel`.
- **Test fixtures:** `createMockConnectTransport.ts` serves NATGateways, ExternalIPs, ExternalIPAttachments, private ExternalIPPools, and the private NetworkClass.

### Component tests

`NetworkAttachmentPickers.test.tsx`:

| Scenario | Assert |
|----------|--------|
| VirtualNetwork selection filters Subnet and SecurityGroup lists | Options update on VirtualNetwork change |
| Clearing VirtualNetwork resets Subnet and SecurityGroup values | Formik values cleared |
| Single-option list auto-selects | Value auto-selected |
| `sgRequired="always"` with empty SecurityGroup | Validation error |
| `sgRequired="when-non-default-vn"` with default VirtualNetwork, empty SecurityGroup | No error |
| `sgRequired="when-non-default-vn"` with non-default VirtualNetwork, empty SecurityGroup | Validation error |
| `allOptional={true}` with all pickers empty | No errors |
| `allOptional={false}` with VirtualNetwork empty | Validation error |
| Automatic SecurityGroups in the VirtualNetwork | Not offered in the SecurityGroup list |
| Loading and error states | Pickers disabled during load; error on failure |

---

## Provenance

Authored: commit @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 7b09375
Final: respond @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 18a72cb (dirty)

> Context changed between commit and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.3.0","ai_workflows":"1e226e0 (dirty)","source_repo":"18a72cb (dirty)","source_repo_branch":"design/OSAC-2632-ui","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["commit","respond"],"authoring_modes":["skill"],"context_changed":true} -->
