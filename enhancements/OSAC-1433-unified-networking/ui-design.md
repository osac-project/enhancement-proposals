---
title: unified-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-08-12
last-updated: 2026-08-12
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
unchanged by this design. This addendum also defines the NetworkACL experience
because ACLs are associated with Subnets rather than workload attachments.

## Proposal

### Cloud Provider Admin

#### External IP Pool Management

Pure consumer of the existing private `ExternalIPPools` service
(`internal/servers/private_external_ip_pools_server.go`) — no backend change.

- **List page** (`ExternalIpPoolsListPage`, `pages/admin/`) at
  `/admin/infrastructure/external-ip-pools` — alongside Storage and Instance types in the
  admin "Infrastructure" nav. Columns: **Name**, **IPv4 CIDRs**,
  **Available / Total** (`status.available`/`status.total`), **State**
  (`ExternalIpPoolStatusLabel`). Row actions: **Edit**, **Delete**. A "Create pool" button
  routes to the create form.
- **Create/update form** (`ExternalIpPoolFormPage`, one shared component for both
  `/admin/infrastructure/external-ip-pools/create` and
  `/admin/infrastructure/external-ip-pools/:id/edit`, Formik+Yup): **Name** (DNS label),
  **IPv4 CIDR** (exactly one value, submitted as a one-element `cidrs` list).
  Do not offer an **Add CIDR** control; client validation rejects empty or
  multiple values. In edit mode, all pool network fields are immutable
  server-side and render disabled for reference — only
  the resource metadata **Name** remains editable. Create submits
  `{ metadata: { name }, spec: { ipFamily: "IPv4", cidrs } }` via `useCreateExternalIPPool()`;
  metadata-only update submits via `useUpdateExternalIPPool()` with `lock=true`.
- **Delete:** row action with confirmation, `useDeleteExternalIPPool()`.

### Tenant User and Admin

#### Virtual Network Management (existing, for context)

- **List page** (`VirtualNetworksPage`) at `/networking/virtual-networks`. Columns:
  **Name**, **IPv4 CIDR**, **Subnets count**, **Status** (`VirtualNetworkStatusLabel`).
- **Create form:** modal (`VirtualNetworkCreateModal`) with **Name** and **IPv4 CIDR**.
  IPv6 and dual-stack networking are not supported. NetworkClass is assigned
  automatically, not exposed to tenants. Via `useCreateVirtualNetwork()`.
- **Detail page** (`VirtualNetworkDetailPage`) at `/networking/virtual-networks/:id`,
  with tabs for **Subnets**, **Network ACLs**, **Details**. The Subnets tab
  shows the effective ACL for each Subnet; the Network ACLs tab shows each ACL
  and its associated Subnets.
- **Delete:** header action, `useDeleteVirtualNetwork()`; blocked if the VN has subnets
  or network ACLs.

#### Network ACL Management

- **List page** (`NetworkAclsPage`) at `/networking/network-acls`. Columns:
  **Name**, **Virtual Network**, **Associated Subnets**, **Rule count**, and
  **Status**. The default ACL is marked with the default label and shows its
  explicit policy summary: **deny all ingress / allow all egress**.
- **Create form** (`NetworkAclCreatePage`) requires **Name**, **Virtual
  Network**, one or more **Subnets**, and at least one rule. A rule editor
  contains **Direction** (Ingress/Egress), **Action** (Allow/Deny),
  **Protocol**, **Source CIDR** for ingress or **Destination CIDR** for
  egress, and an optional port for TCP/UDP (omitted means all ports; ICMP and
  `any` omit the port). The form explains that rules are stateless and that
  return traffic is evaluated independently; a separate opposite-direction
  rule is required when the tenant needs to control the return path with
  tenant policy.
- **Detail page** (`NetworkAclDetailPage`) shows the immutable VirtualNetwork
  and Subnet associations, the complete ingress/egress rule set, the effective
  specificity ordering (CIDR, protocol, then port), and the provider-owned
  permit-all deployment baseline used when no tenant rule matches.
- **Subnet association:** a single ACL may be associated with multiple
  Subnets. The UI prevents selecting a Subnet that already has a custom ACL
  and displays the current effective ACL on the Subnet detail view.
- **No workload ACL selector:** ComputeInstance, Cluster, and BaremetalInstance
  network-attachment forms expose the Subnet and resource-specific interface
  fields only. They do not expose a NetworkACL selector.

#### NAT Gateway Field in Virtual Network

One NAT Gateway per VirtualNetwork (`design.md`, Resolved Question 4).
The absence of an attached gateway does not by itself mean that attachment is
available. The UI must first use the deployment's resolved networking
capability: `natGateway: true` permits the Attach action; `natGateway: false`
(including K8s-only OVN) hides or disables Attach and explains that NATGateway
is unsupported. A stale or unavailable capability must not enable the action;
the server's capability precondition remains authoritative.

- **VirtualNetworksPage table:** a **NAT Gateway** column showing the attached NAT
  Gateway's external IP address and status (`NatGatewayStatusLabel`) when present, or an
  empty-state dash when not. Row action depends on state:
  - **No NAT Gateway and `natGateway: true`:** **Attach NAT Gateway** — opens a modal to select an available
    External IP
    (`useExternalIPs({ filter: 'this.status.state == EXTERNAL_IP_STATE_ALLOCATED && this.status.attached == false' })`
    — only unattached allocated IPs, per the ownership rule in `design.md` that an
    ExternalIP serves either a NATGateway or an ExternalIPAttachment, not both) and creates
    the NAT Gateway for that row's VirtualNetwork via `useCreateNatGateway()`.
  - **NAT Gateway attached:** **Detach** — confirmation modal, calls
    `useDeleteNatGateway()`.
  - **No NAT Gateway and `natGateway: false` or unavailable:** no Attach action;
    show the unsupported/unavailable capability state.
- **VirtualNetworkDetailPage:** a **NAT Gateway** field showing the same external IP +
  status, with the same capability- and state-dependent action next to it:
  **Attach NAT Gateway** only when empty and `natGateway: true`, no Attach
  action when the capability is false or unavailable, or **Detach** when a NAT
  Gateway exists.

**Fetching:** the list page fetches NAT Gateways once (`NatGateways.List`, unfiltered) and
indexes the results by `spec.virtual_network.name` for row rendering, avoiding an N+1 request
per row. The detail page uses `useNatGatewayForVirtualNetwork(vnName)` (`NatGateways.List`,
filtered `this.spec.virtual_network.name == "<vnName>"`, first result). This follows the
canonical local-reference and CEL examples; the resolved `id` may still be displayed but is
not the UI's reference filter key.

`NATGatewaySpec.external_ip` is immutable server-side, and `NatGateways.Update` only covers
metadata (labels/annotations) — changing a VirtualNetwork's NAT Gateway to a different
External IP is Detach (delete) followed by Attach (create) with the new External IP, not an
in-place edit.

#### External IP Management

- **List page** (`ExternalIpsListPage`) at `/networking/external-ips`, under the existing
  shared tenant "Networking" nav section. Columns: **Name**, **Address**, **Pool**,
  **Status** (`ExternalIpStatusLabel`).
- **Create form:** pool select (`useExternalIPPools()`) + Name, via `useCreateExternalIP()`.
- **Delete:** row action, `useDeleteExternalIP()`.

## Failure Handling

| Scenario | UI behavior |
|---|---|
| NAT Gateway unsupported or capability unavailable | Attach is hidden/disabled before submission; explain that the deployment does not advertise NATGateway support. |
| NAT Gateway attach: selected ExternalIP already consumed | Server rejection shown as a form-level error in the attach modal. |
| NAT Gateway detach fails | Server error shown in the confirmation modal; row's Detach stays available for retry. |
| External IP create: pool exhausted | Server's `RESOURCE_EXHAUSTED`/`FAILED_PRECONDITION` shown as a form-level error. |
| External IP delete fails | Server error shown inline; row's Delete stays available for retry. |
| Pool create: invalid/overlapping CIDR | Server's `INVALID_ARGUMENT`/`ALREADY_EXISTS` shown as a form-level error. |
| Pool update: concurrent write | Server's `FAILED_PRECONDITION`/`ABORTED` shown; admin re-fetches and retries. |
| Pool delete: `status.allocated > 0` | Server's `FAILED_PRECONDITION` shown verbatim; row stays listed. |
| Any List/Get failure | Existing `QueryErrorState` handling. |
| NetworkACL has no Subnet association | Create form blocks submission and identifies the required Subnet field. |
| Subnet already has a custom NetworkACL | Subnet is disabled in the association picker with an explanation. |
| Invalid overlapping rule | Form identifies the equal-specificity conflict and explains the specificity order. |
| Stateless return rule missing | Form guidance explains that the reverse flow is evaluated independently; an opposite-direction tenant rule is needed to impose tenant-specific control, otherwise the deployment baseline applies. |

## Required UI Tests

- Render the Attach action only when the resolved deployment capability contains
  `natGateway: true` and the VirtualNetwork has no NATGateway.
- Render no Attach action, with an explanatory unsupported state, for K8s-only
  OVN (`natGateway: false`) and while the capability is unavailable.
- Verify that a capability-precondition response from a stale Attach attempt is
  shown as a form-level error and does not create a NATGateway.
- Verify that NAT Gateway list indexing and detail filtering use the canonical
  `spec.virtual_network.name` local-reference path.
- Verify that changing the NAT Gateway ExternalIP is represented as delete plus
  create, never as an Update of the immutable network binding.
- Render NetworkACLs under the VirtualNetwork detail page and in the dedicated
  Network ACL list/detail views.
- Verify the default ACL displays explicit deny-all ingress and allow-all
  egress rules.
- Verify the NetworkACL detail view explains the provider-owned permit-all
  deployment baseline fallback and exposes no control to modify it.
- Verify the NetworkACL detail view renders specificity in the documented order:
  longest matching remote CIDR prefix, exact protocol over `any`, then exact
  port over an omitted port.
- Verify Subnet association supports one ACL-to-many-Subnets, rejects a
  Subnet with an existing custom ACL, and shows the effective ACL on the
  Subnet view.
- Verify workload attachment forms contain no NetworkACL selector.
- Verify the rule editor enforces direction-specific CIDR fields and renders
  the stateless return-traffic and deployment-baseline guidance.

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
  `useCreateExternalIPPool`, `useUpdateExternalIPPool` (name-only, `lock=true`),
  `useDeleteExternalIPPool`. Types from `@osac/types/private`. Add
  `'v1/private/external_ip_pools'` to `ApiRoute`.
- **Status labels:** `NatGatewayStatusLabel`, `ExternalIpStatusLabel`,
  `ExternalIpPoolStatusLabel` — thin wrappers around `ResourceStatusLabel`/`StatusKind`,
  matching `NetworkACLStatusLabel`'s shape.
- **Test fixtures:** add `NATGateways`, `ExternalIPs`, and private `ExternalIPPools` to
  `createMockConnectTransport.ts`.

---

## Provenance

Authored: commit @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 7b09375
Final: respond @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 18a72cb (dirty)

> Context changed between commit and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.3.0","ai_workflows":"1e226e0 (dirty)","source_repo":"18a72cb (dirty)","source_repo_branch":"design/OSAC-2632-ui","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["commit","respond"],"authoring_modes":["skill"],"context_changed":true} -->
