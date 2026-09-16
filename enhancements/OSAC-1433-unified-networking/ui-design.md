---
title: unified-networking-ui
authors:
  - brotman@redhat.com
creation-date: 2026-08-12
last-updated: 2026-09-16
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
unchanged by this design. Subnet and SecurityGroup management
([OSAC-1899](https://redhat.atlassian.net/browse/OSAC-1899)) are unchanged and not
covered here. All networking resources and workload network attachment fields follow
the unified create/read/delete contract: read uses List/Get, and changes require
delete and recreate.

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
  with tabs for **Subnets**, **Security Groups**, **Details**.
- **Delete:** header action, `useDeleteVirtualNetwork()`; blocked if the VN has subnets
  or security groups.

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
  `ExternalIpPoolStatusLabel` — thin wrappers around `ResourceStatusLabel`/`StatusKind`,
  matching `SecurityGroupStatusLabel`'s shape.
- **Test fixtures:** add `NATGateways`, `ExternalIPs`, and private `ExternalIPPools` to
  `createMockConnectTransport.ts`.

---

## Provenance

Authored: commit @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 7b09375
Final: respond @ design 0.3.0 - 1e226e0 (dirty), workspace design/OSAC-2632-ui @ 18a72cb (dirty)

> Context changed between commit and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.3.0","ai_workflows":"1e226e0 (dirty)","source_repo":"18a72cb (dirty)","source_repo_branch":"design/OSAC-2632-ui","commits_behind_main":0,"commits_ahead_main":2,"main_ref":"main","phases":["commit","respond"],"authoring_modes":["skill"],"context_changed":true} -->
