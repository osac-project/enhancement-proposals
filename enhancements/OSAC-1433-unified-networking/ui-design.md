---
title: unified-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-08-12
last-updated: 2026-09-30
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

## Summary

Extends the accepted backend design in [design.md](design.md) with the remaining `osac-ui`
work for OSAC-1433 (tracked as [OSAC-2632](https://redhat.atlassian.net/browse/OSAC-2632)):
Cloud Provider Admin management of **ExternalIPPool**, a tenant-facing **NAT Gateway**
field on VirtualNetwork, and tenant-facing **External IP** management. Existing
VirtualNetwork management (shipped under
[OSAC-1898](https://redhat.atlassian.net/browse/OSAC-1898), per the
[OSAC-1425](https://redhat.atlassian.net/browse/OSAC-1425) PRD) is summarized below for
context, since the NAT Gateway field extends its list and detail pages — it is otherwise
unchanged by this design. NetworkACL management and Subnet association are added below.
Workload network attachments refer to a Subnet only; the Subnet's ACL is shown as
read-only context during workload creation. NetworkACL rules and Subnet associations
are fixed at creation; VirtualNetwork/Subnet address configuration and workload
attachments also remain immutable after creation.

## Proposal

### Cloud Provider Admin

#### External IP Pool Management

Pure consumer of the existing private `ExternalIPPools` service
(`internal/servers/private_external_ip_pools_server.go`) — no backend change.

- **List page** (`ExternalIpPoolsListPage`, `pages/admin/`) at
  `/admin/infrastructure/external-ip-pools` — alongside Storage and Instance types in the
  admin "Infrastructure" nav. Columns: **Name**, **IPv4 CIDR**,
  **Available / Total** (`status.available`/`status.total`), **State**
  (`ExternalIpPoolStatusLabel`). Row action: **Delete**. A "Create pool" button
  routes to the create form.
- **Create form** (`ExternalIpPoolFormPage`, Formik+Yup): **Name** (DNS label) and
  one canonical **IPv4 CIDR**. The IP family is fixed to `IP_FAMILY_IPV4`; IPv6,
  empty CIDRs, malformed CIDRs, and multiple CIDRs are rejected by client and
  server validation. All fields are immutable after creation. Create submits
  `{ metadata: { name }, spec: { ipFamily: "IP_FAMILY_IPV4", cidrs: [cidr] } }`
  via `useCreateExternalIPPool()`; changes require deleting and recreating the
  pool.
- **Delete:** row action with confirmation, `useDeleteExternalIPPool()`.

### Tenant User and Admin

#### Virtual Network Management (existing, for context)

- **List page** (`VirtualNetworksPage`) at `/networking/virtual-networks`. Columns:
  **Name**, **IPv4 CIDR**, **Subnets count**, **Status** (`VirtualNetworkStatusLabel`).
- **Create form:** modal (`VirtualNetworkCreateModal`) with **Name**, **IPv4 CIDR**,
  — NetworkClass is assigned automatically, not exposed to tenants. Via
  `useCreateVirtualNetwork()`.
- **Detail page** (`VirtualNetworkDetailPage`) at `/networking/virtual-networks/:id`,
  with stacked cards for **Details**, **Subnets**, and **Network ACLs**.
- **Delete:** header action, `useDeleteVirtualNetwork()`; blocked if the VN has
  Subnets, NetworkACLs, or NATGateways.

#### NetworkACL Management

- **List:** the **Network ACLs** card on the VirtualNetwork detail page lists the
  ACLs scoped to that VirtualNetwork. Columns: **Name**, **Associated Subnets**,
  **Ingress Rules**, **Egress Rules**, and **Status** (`NetworkACLStatusLabel`).
  There is no system-created or tenant default ACL resource.
- **Create wizard:** Step 1 (**General**) collects **Project**, **Name**, and
  **Description**. Step 2 (**Configuration**) has separate **Ingress** and
  **Egress** sections. Each section uses repeatable rule form groups, following
  the Cluster node-set form pattern, with **Action** (ALLOW or DENY),
  **Protocol** (ALL, TCP, UDP, ICMP), optional TCP/UDP **Destination Port
  Range**, and IPv4 **CIDR** fields. Users add or remove rule groups; rules are
  not entered in tables.
- A rule is unique within its direction by its CIDR, protocol, and optional
  destination-port range; action does not make an otherwise identical match
  unique. Explicit TCP/UDP port ranges for the same direction, canonical CIDR,
  and protocol may not overlap, including shared endpoints, even when their
  actions match. Disjoint ranges such as TCP ports 443 and 8443 are valid. A
  port-specific TCP/UDP rule may coexist with a no-range rule for the same
  CIDR and protocol because the port-specific rule is more specific. Protocol-
  specific rules may coexist with an ALL rule for the same CIDR; the protocol-
  specific match is evaluated first. An identical match tuple in one direction
  is rejected.
- Rule precedence is derived from match specificity: longest CIDR prefix
  first, then protocol (`ICMP`, `UDP`, `TCP`, `ALL`), then port-specific rules
  before no-port rules that match all ports. Disjoint explicit ranges are
  displayed by numeric `port_from` then `port_to`; this display order does not
  break ties for overlapping ranges because those rules are rejected. Action
  and input order do not affect precedence. For example, for the same
  CIDR, `DENY TCP/22` is evaluated before `ALLOW TCP on any port`, so port 22
  is denied and other TCP ports are allowed regardless of entry order. For
  ingress, `ALLOW TCP/443 from 192.0.2.64/26` is evaluated before `DENY ALL
  from 192.0.2.0/24`; matching HTTPS traffic from that `/26` is allowed and
  other traffic in the `/24` is denied. The UI displays rules in effective
  evaluation order, and the rule set is immutable after creation.
- If no rule matches, the required deployment default ACL policy decides the
  result. Ingress and egress are evaluated independently, including return
  traffic. For example, with a `DENY` fallback, an ingress `ALLOW ALL` from
  `198.51.100.0/24` does not authorize a reply to that CIDR; a separate egress
  `ALLOW ALL` to `198.51.100.0/24` is required. With a `PERMIT` fallback, an
  unmatched reply passes unless a matching egress `DENY` applies. ACL details
  show rules read-only.
- **Delete:** an ACL can be deleted only when no Subnet references it; the
  server returns `FAILED_PRECONDITION` while a reference remains.

#### Subnet NetworkACL Association

- **Subnet create wizard:** Step 1 (**General**) collects **Project**,
  **Name**, and **Description**. Step 2 (**Configuration**) selects the
  READY VirtualNetwork, configures the IPv4 CIDR, and optionally selects an ACL
  scoped to that VirtualNetwork. Leaving the ACL empty creates an unassociated
  Subnet; the deployment default ACL policy applies when there is no matching
  rule. Depending on the deployment policy, required outbound traffic may be
  denied. To allow specific outbound traffic, associate an ACL with the needed
  egress and return rules when creating the Subnet; the association cannot be
  added later. A selected ACL must already be READY and belong to that
  VirtualNetwork.
  Multiple and cross-VirtualNetwork ACL references are rejected. The API
  rejects Subnet creation while its VirtualNetwork is not READY, whether or not
  an ACL is selected.
- **Subnet list/detail:** show the associated ACL name and status when present.
  In both associated and unassociated cases, show generic guidance that
  unmatched traffic follows the deployment policy. Do not display the configured
  provider-only `PERMIT` or `DENY` value.
- **Association lifecycle:** the optional association is selected during
  Subnet creation and cannot be changed later. Subnet details show the
  association read-only. Create the ACL before the Subnet when using one.
- **Policy boundary:** same-Subnet traffic is not filtered by the ACL.
  Cross-Subnet traffic must pass source egress and destination ingress rules;
  the deployment default action decides whenever the relevant ACL has no
  matching rule or no ACL is associated. Workload forms show the selected
  Subnet's ACL, if any, but do not provide an ACL picker.

#### NAT Gateway Field in Virtual Network

One NAT Gateway per VirtualNetwork (`design.md`, Resolved Question 4).

- **VirtualNetworksPage table:** a **NAT Gateway** column showing the attached NAT
  Gateway's external IP address and status (`NatGatewayStatusLabel`) when present, or an
  empty-state dash when not. Row action depends on state:
  - **No NAT Gateway:** **Attach NAT Gateway** — opens a modal to select an available
    External IP
    (`useExternalIPs({ filter: 'this.status.state == EXTERNAL_IP_STATE_ALLOCATED && this.status.attached == false' })`
    — only unattached allocated IPs, per the ownership rule in `design.md` that an
    ExternalIP serves either a NATGateway or an ExternalIPAttachment, not both) and creates
    the NAT Gateway for that row's VirtualNetwork via `useCreateNatGateway()`.
  - **NAT Gateway attached:** **Detach** — confirmation modal, calls
    `useDeleteNatGateway()`.
- **VirtualNetworkDetailPage:** a **NAT Gateway** field showing the same external IP +
  status, with the same state-dependent action next to it: **Attach NAT Gateway** when
  empty (same attach modal as the list page's row action, scoped to this VirtualNetwork),
  or **Detach** when a NAT Gateway exists.

**Fetching:** the list page fetches NAT Gateways once (`NatGateways.List`, unfiltered) and
indexes the results by `spec.virtual_network.id` for row rendering, avoiding an N+1 request
per row. The detail page uses `useNatGatewayForVirtualNetwork(vnId)` (`NatGateways.List`,
filtered `this.spec.virtual_network.id == "<vnId>"`, first result).

`NATGatewaySpec.external_ip` and NAT Gateway metadata are immutable after creation —
changing a VirtualNetwork's NAT Gateway to a different External IP is Detach (delete)
followed by Attach (create) with the new External IP, not an in-place edit.

#### External IP Management

- **List page** (`ExternalIpsListPage`) at `/networking/external-ips`, under the existing
  shared tenant "Networking" nav section. Columns: **Name**, **Address**, **Pool**,
  **Status** (`ExternalIpStatusLabel`).
- **Create form:** pool select (`useExternalIPPools()`) + Name, via `useCreateExternalIP()`.
- **Delete:** row action, `useDeleteExternalIP()`.

## Failure Handling

| Scenario | UI behavior |
|---|---|
| NAT Gateway attach: selected ExternalIP already consumed | Server rejection shown as a form-level error in the attach modal. |
| NAT Gateway detach fails | Server error shown in the confirmation modal; row's Detach stays available for retry. |
| External IP create: pool exhausted | Server's `RESOURCE_EXHAUSTED`/`FAILED_PRECONDITION` shown as a form-level error. |
| External IP delete fails | Server error shown inline; row's Delete stays available for retry. |
| Pool create: non-IPv4 address family | Server's `INVALID_ARGUMENT` shown as a form-level error. |
| Pool create: empty, malformed, multiple, or overlapping CIDRs | Server's `INVALID_ARGUMENT`/`ALREADY_EXISTS` shown as a form-level error. |
| Pool delete: `status.allocated > 0` | Server's `FAILED_PRECONDITION` shown verbatim; row stays listed. |
| NetworkACL create has duplicate match fields, an invalid port range, or another invalid rule | Validation error is shown beside the rule form group; no create is submitted. |
| NetworkACL create has overlapping TCP/UDP ranges for the same direction, CIDR, and protocol | Inline validation identifies the conflicting ranges; no create is submitted. Adjacent disjoint ranges and a no-range rule alongside a port-specific rule are accepted. |
| Subnet creation omits an ACL | Subnet creation proceeds without an ACL association; unmatched traffic uses the deployment default ACL policy. |
| Subnet creation references an ACL in another VirtualNetwork or a non-READY ACL | Server's `INVALID_ARGUMENT` or `FAILED_PRECONDITION` is shown in the form; no Subnet is created. |
| NetworkACL delete while associated with a Subnet | Delete action reports the server's `FAILED_PRECONDITION`; the ACL remains listed. |
| Any List/Get failure | Existing `QueryErrorState` handling. |

## Implementation details

- **Barrel export fix (prerequisite):** `libs/types/src/index.ts` re-exports every public
  networking type except `nat_gateway_type_pb`/`nat_gateways_service_pb` — add those two
  exports so tenant-facing hooks can import `NATGateway`/`NATGateways` from `@osac/types`
  (this is a hand-maintained barrel, not a `pnpm gen-types` output).
- **Tenant hooks** (`api/v1/networking.ts`, `api/v1/external-ip.ts`):
  `useNatGateways` (unfiltered, for the VirtualNetwork list page),
  `useNatGatewayForVirtualNetwork` (filtered, for the detail page), `useCreateNatGateway`,
  `useDeleteNatGateway`, `useExternalIPs`, `useCreateExternalIP`, `useDeleteExternalIP`.
  Add `'v1/nat_gateways'` to the `ApiRoute` union (`'v1/external_ips'` already exists
  there).
- **Admin hooks** (new `api/v1/private/external-ip-pools.ts`, following
  `storage-backends.ts`'s shape): `usePrivateExternalIPPools`, `usePrivateExternalIPPool`,
  `useCreateExternalIPPool`, `useDeleteExternalIPPool`. Types from
  `@osac/types/private`. Add
  `'v1/private/external_ip_pools'` to `ApiRoute`.
- **Status labels:** `NatGatewayStatusLabel`, `ExternalIpStatusLabel`,
  `ExternalIpPoolStatusLabel`, and `NetworkACLStatusLabel` — wrappers around
  `ResourceStatusLabel`/`StatusKind`.
- **Hooks and fixtures:** add NetworkACL list/create/delete hooks, plus
  `NetworkACLs`, `NATGateways`, `ExternalIPs`, and
  private `ExternalIPPools` to `createMockConnectTransport.ts`.

---

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ 1f3b63b82

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"1f3b63b82","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond","revise","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","manual-edit","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
