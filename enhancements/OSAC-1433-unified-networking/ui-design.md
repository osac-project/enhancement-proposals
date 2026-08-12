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
field on VirtualNetwork, and tenant-facing **External IP** management. VirtualNetwork,
Subnet, and SecurityGroup management (OSAC-1898, OSAC-1899) are otherwise unchanged by
this design.

## Proposal

### Cloud Provider Admin

#### External IP Pool Management

Pure consumer of the existing private `ExternalIPPools` service
(`internal/servers/private_external_ip_pools_server.go`) — no backend change.

- **List page** (`ExternalIpPoolsListPage`, `pages/admin/`) at
  `/admin/infrastructure/external-ip-pools` — alongside Storage and Instance types in the
  admin "Infrastructure" nav. Columns: **Name**, **IP family**, **CIDRs**,
  **Available / Total** (`status.available`/`status.total`), **State**
  (`ExternalIpPoolStatusLabel`). Row actions: **Edit**, **Delete**. A "Create pool" button
  routes to the create form.
- **Create/update form** (`ExternalIpPoolFormPage`, one shared component for both
  `/admin/infrastructure/external-ip-pools/create` and
  `/admin/infrastructure/external-ip-pools/:id/edit`, Formik+Yup): **Name** (DNS label),
  **IP family** (`IPv4`/`IPv6`), **CIDRs** (repeatable, ≥1, `FieldArray`). In edit mode,
  IP family and CIDRs are immutable server-side and render disabled for reference — only
  **Name** is editable. Create submits
  `{ metadata: { name }, spec: { ipFamily, cidrs } }` via `useCreateExternalIPPool()`;
  update submits via `useUpdateExternalIPPool()` with `lock=true`.
- **Delete:** row action with confirmation, `useDeleteExternalIPPool()`.

### Tenant User and Admin

#### NAT Gateway Field in Virtual Network

One NAT Gateway per VirtualNetwork (`design.md`, Resolved Question 4).

- **VirtualNetworksListPage table:** a **NAT Gateway** column showing the attached NAT
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
| NAT Gateway attach: selected ExternalIP already consumed | Server rejection shown as a form-level error in the attach modal. |
| NAT Gateway detach fails | Server error shown in the confirmation modal; row's Detach stays available for retry. |
| External IP create: pool exhausted | Server's `RESOURCE_EXHAUSTED`/`FAILED_PRECONDITION` shown as a form-level error. |
| External IP delete fails | Server error shown inline; row's Delete stays available for retry. |
| Pool create: invalid/overlapping CIDR | Server's `INVALID_ARGUMENT`/`ALREADY_EXISTS` shown as a form-level error. |
| Pool update: concurrent write | Server's `FAILED_PRECONDITION`/`ABORTED` shown; admin re-fetches and retries. |
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
  `useCreateExternalIPPool`, `useUpdateExternalIPPool` (name-only, `lock=true`),
  `useDeleteExternalIPPool`. Types from `@osac/types/private`. Add
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
