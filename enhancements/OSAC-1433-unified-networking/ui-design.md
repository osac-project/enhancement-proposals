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
unchanged by this design. This addendum also defines the SecurityGroup and
NetworkACL experiences. SecurityGroups are selected by workload network
attachments; NetworkACLs are associated with Subnets rather than workload
attachments.

These UI flows inherit the [Unified Networking deployment support
boundary](design.md#deployment-support-boundary): they describe connected
deployments only, and do not provide or advertise air-gapped networking.

## Proposal

### Cloud Provider Admin

#### External IP Pool Management

Pure consumer of the existing private `ExternalIPPools` service
(`internal/servers/private_external_ip_pools_server.go`) — no backend change.

- **List page** (`ExternalIpPoolsListPage`, `pages/admin/`) at
  `/admin/infrastructure/external-ip-pools` — alongside Storage and Instance types in the
  admin "Infrastructure" nav. Columns: **Name**, **IPv4 CIDRs**,
  **Available / Total** (`status.available`/`status.total`), **State**
  (`ExternalIpPoolStatusLabel`). Row actions: **Delete**. A "Create pool" button
  routes to the create form.
- **Create form** (`ExternalIpPoolFormPage` at
  `/admin/infrastructure/external-ip-pools/create`, Formik+Yup): **Name** (DNS
  label), **Display name** (optional), **Description** (optional), and **IPv4
  CIDR** (exactly one value, submitted as a one-element `cidrs` list).
  Do not offer an **Add CIDR** control; all pool network fields are immutable
  after creation. Standard metadata remains editable through a metadata-only
  edit action after creation; the name is read-only. Client validation rejects
  empty or multiple CIDR values. Create submits `{ metadata: { name,
  displayName, description }, spec: { ipFamily: "IPV4", cidrs } }` via
  `useCreateExternalIPPool()`.
- **Edit metadata:** row/detail action edits only `displayName`, `description`,
  labels, and annotations. It calls the provider metadata-only update path and
  never sends a pool network field or a network-field update mask.
- **Delete:** row action with confirmation, `useDeleteExternalIPPool()`.

### Tenant User and Admin

#### Virtual Network Management (existing, for context)

- **List page** (`VirtualNetworksPage`) at `/networking/virtual-networks`. Columns:
  **Name**, **IPv4 CIDR**, **Subnets count**, **SecurityGroups count**, **Status**
  (`VirtualNetworkStatusLabel`).
- **Create form:** modal (`VirtualNetworkCreateModal`) with **Name** and **IPv4 CIDR**.
  IPv6 and dual-stack networking are not supported. NetworkClass is assigned
  automatically, not exposed to tenants. Via `useCreateVirtualNetwork()`.
- **Detail page** (`VirtualNetworkDetailPage`) at `/networking/virtual-networks/:id`,
  with tabs for **Subnets**, **Network ACLs**, **Details**. The Subnets tab
  shows the effective ACL for each Subnet, and the Network ACLs tab shows each
  ACL and its associated Subnets. NetworkACL is part of the complete networking
  contract, so the UI does not hide it or branch on a manager-specific support
  advertisement. If its provider operation is still under development, the
  normal operation may complete as a successful no-op; that is reported through
  resource status rather than as an unsupported API surface. Kubernetes
  NetworkPolicy is not presented as an ACL substitute.
- **Delete:** header action, `useDeleteVirtualNetwork()`; blocked if the VN has
  Subnets, SecurityGroups, NetworkACLs, or a NATGateway. The error lists every direct blocker
  and the required delete-first action.

#### SecurityGroup Management

SecurityGroups are shown as part of the complete networking contract. The UI
presents one OSAC resource and the backend reconciles it to every configured
manager target. If the provider-side policy adapter is unfinished, the normal
operation may complete as a successful no-op and its result is shown through
resource status; the UI does not hide the API or branch on manager support.

- **List page** (`SecurityGroupsPage`) at `/networking/security-groups`. Columns:
  **Name**, **Virtual Network**, **Attached workload count**, **Rule count**, and
  **Status**. The system-created tenant default group is marked as default.
- **Create form** (`SecurityGroupCreatePage`) requires **Name**, **Virtual
  Network**, and at least one rule. A rule editor contains **Direction**
  (Ingress/Egress), **Protocol** (`tcp`, `udp`, `icmp`, or `any`), an optional
  TCP/UDP **Port** from `1..65535`, and exactly one direction-appropriate IPv4
  CIDR. SecurityGroup rules have no Allow/Deny action field: every rule allows
  matching traffic, return traffic is stateful, and unmatched traffic is denied.
- **Detail page** (`SecurityGroupDetailPage`) shows the immutable VirtualNetwork,
  all rules, the workloads that reference the group, and the default-group
  status. The system-created default group may have an empty rule list, which
  means default deny; tenant-created groups may not.
- **Delete:** detail-page and row actions call `useDeleteSecurityGroup()` after
  confirmation. Deletion is rejected while any workload attachment, Catalog
  Item/Template policy, or required default relationship references the group.
  The error lists every blocking workload/reference and the required delete-first
  action. Deleting a SecurityGroup never deletes or edits a workload, Subnet, or
  VirtualNetwork.
- **Workload attachment:** Direct ComputeInstance, Cluster, and BaremetalInstance
  create/detail forms expose a repeatable SecurityGroup reference selector.
  The v1 cluster/VM provisioning wizard is a documented specialized exception:
  it may omit explicit CaaS networking controls and rely on server-side
  defaults. Missing or empty
  selection means the tenant default group when it exists; explicit references
  are preserved and must be Ready, same-tenant, same-VirtualNetwork, and unique.
  No primary toggle or update operation is exposed. If the selected Subnet is
  outside the tenant default VirtualNetwork, the form does not silently apply
  the tenant default SecurityGroup; it requires a compatible group in the
  selected VirtualNetwork and renders the server's cross-VirtualNetwork
  validation detail when one is missing.

#### Network ACL Management

The following NetworkACL pages and actions are always rendered as part of the
complete networking contract. Every configured manager is a target for the
normal NetworkACL operation. Kubernetes NetworkPolicy alone is not sufficient;
an unfinished provider-side ACL adapter may complete its normal operation as a
successful no-op and reports that result through resource status.

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
  tenant policy. The Subnet picker is filtered to Ready Subnets in the
  selected VirtualNetwork, rejects duplicate selections, and disables a
  Subnet that already has any effective ACL. This includes the system-created
  default ACL. The picker explains that replacing the default ACL uses the
  default-resource replacement workflow rather than a second custom
  association.
- **Detail page** (`NetworkAclDetailPage`) shows the immutable VirtualNetwork
  and Subnet associations, the complete ingress/egress rule set, the effective
  specificity ordering (CIDR, protocol, then port), and the provider-owned
  permit-all deployment baseline used when no tenant rule matches.
- **Delete:** detail-page and row actions call `useDeleteNetworkACL()` after
  confirmation. Deleting an ACL removes only the ACL and its backend rule
  state; it never detaches or deletes the associated Subnets or VirtualNetwork.
  A Subnet or VirtualNetwork delete is blocked until the ACL has disappeared.
- **Subnet association:** a single ACL may be associated with multiple
  Subnets. The UI prevents selecting a Subnet that already has any effective
  ACL, including the default ACL, and displays the current effective ACL on
  the Subnet detail view. A custom ACL cannot replace the default ACL through
  the ordinary create form.
- **No workload ACL selector:** ComputeInstance, Cluster, and BaremetalInstance
  network-attachment forms expose the Subnet and SecurityGroup selectors plus
  resource-specific interface fields where applicable. They do not expose a
  NetworkACL selector; the effective ACL is inherited from the selected Subnet.

#### NAT Gateway Field in Virtual Network

One NAT Gateway per VirtualNetwork (`design.md`, Resolved Question 4).
The absence of an attached gateway means the Attach action is available. The
UI submits the normal create request and displays provider readiness, failure,
or successful no-op status after submission. No manager-specific capability
flag controls whether the action is shown.

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
  - **No NAT Gateway:** the Attach action remains available through the normal
    create flow; provider readiness or a successful no-op is shown in resource
    status.
- **VirtualNetworkDetailPage:** a **NAT Gateway** field showing the same external IP +
  status, with the same state-dependent action next to it: **Attach NAT Gateway**
  when empty, or **Detach** when a NAT Gateway exists. Provider implementation
  readiness is reported after submission and does not hide the API action.

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

#### External IP Attachment Management

Manual `ExternalIPAttachment` create/read/delete is an API and CLI workflow in
this UI addendum; no standalone UI form is exposed. Automatically created
attachments are visible through the target workload's external-access status
and are read-only. The UI must never expose an edit or retarget operation: a
binding change is delete followed by create, subject to the shared readiness,
scope, endpoint, and dependency validations.

## Failure Handling

| Scenario | UI behavior |
|---|---|
| NAT Gateway provider operation is unfinished | The normal create flow remains available; the provider reports its normal pending, failed, or successful no-op operation status. The UI does not expose a manager-capability branch. |
| NAT Gateway attach: selected ExternalIP already consumed | Server rejection shown as a form-level error in the attach modal. |
| NAT Gateway detach fails | Server error shown in the confirmation modal; row's Detach stays available for retry. |
| External IP create: pool exhausted | Server's `RESOURCE_EXHAUSTED`/`FAILED_PRECONDITION` shown as a form-level error. |
| External IP delete fails | Server error shown inline; row's Delete stays available for retry. |
| Pool create: invalid/overlapping CIDR | Server's `INVALID_ARGUMENT`/`ALREADY_EXISTS` shown as a form-level error. |
| Pool delete: `status.allocated > 0` | Server's `FAILED_PRECONDITION` shown verbatim; row stays listed. |
| SecurityGroup delete has workload, Catalog/Template, or default-group blockers | Server's `FAILED_PRECONDITION` details are rendered as a blocker list containing kind, ID/name, relationship, and required remediation; no workload or network resource is changed. |
| VirtualNetwork delete has Subnet, SecurityGroup, NetworkACL, or NATGateway blockers | Server's `FAILED_PRECONDITION` details are rendered as a blocker list containing kind, ID/name, relationship, and required remediation; no child is detached or deleted. |
| NetworkACL delete is requested | Confirmation is shown; after success only the ACL disappears. Associated Subnets and VirtualNetwork remain unchanged. |
| Subnet or VirtualNetwork delete is blocked by a NetworkACL | The blocker details identify the ACL and the association field, with the action to delete the ACL first. |
| Any List/Get failure | Existing `QueryErrorState` handling. |
| NetworkACL has no Subnet association | Create form blocks submission and identifies the required Subnet field. |
| Subnet already has an effective NetworkACL, including the default ACL | Subnet is disabled in the association picker with an explanation; replacing the default uses the default-resource replacement workflow. |
| Selected Subnet has no effective NetworkACL | The Subnet is shown as not workload-ready and the workload form explains that a Ready ACL must be associated before placement. |
| Explicit Subnet is outside the default VN and no compatible SecurityGroup is selected | Submission is blocked with a same-VirtualNetwork explanation; the default SecurityGroup is not offered as a fallback. |
| Invalid overlapping rule | Form identifies the equal-specificity conflict and explains the specificity order. |
| Stateless return rule missing | Form guidance explains that the reverse flow is evaluated independently; an opposite-direction tenant rule is needed to impose tenant-specific control, otherwise the deployment baseline applies. |

## Required UI Tests

- Render the Attach action whenever the VirtualNetwork has no NATGateway;
  provider readiness is evaluated by the server after submission.
- Verify that an unfinished provider operation remains a normal resource
  lifecycle/status result and is not converted into a manager-capability UI
  branch.
- Verify that NAT Gateway list indexing and detail filtering use the canonical
  `spec.virtual_network.name` local-reference path.
- Verify that changing the NAT Gateway ExternalIP is represented as delete plus
  create, never as an Update of the immutable network binding.
- Verify NetworkACLs are rendered under the VirtualNetwork detail page and in
  the dedicated Network ACL list/detail views for the complete networking
  contract.
- Verify SecurityGroups are rendered and can be created through the complete
  networking contract; verify the UI still presents one resource when both
  managers are configured.
- Verify the SecurityGroup form requires at least one rule for tenant-created
  groups, omits an Allow/Deny action control, validates direction/protocol/port/
  canonical IPv4 CIDR fields, and displays the default group's empty-list
  default-deny behavior.
- Verify workload forms offer SecurityGroup selection, default omitted/empty
  selection correctly, preserve explicit references, and reject duplicate,
  NotReady, cross-tenant, or cross-VirtualNetwork references.
- Verify SecurityGroup delete is available, removes only the group, and is
  blocked with every referencing workload/default dependency listed.
- Verify the default ACL displays explicit deny-all ingress and allow-all
  egress rules in the complete networking contract.
- Verify the NetworkACL detail view explains the provider-owned permit-all
  deployment baseline fallback and exposes no control to modify it.
- Verify the NetworkACL detail view renders specificity in the documented order:
  longest matching remote CIDR prefix, exact protocol over `any`, then exact
  port over an omitted port.
- Verify Subnet association supports one ACL-to-many-Subnets, rejects a
  Subnet with an existing custom ACL, and shows the effective ACL on the
  Subnet view.
- Verify NetworkACL delete is available, removes only the ACL, and does not
  detach or delete any associated Subnet or VirtualNetwork.
- Verify rejected Subnet and VirtualNetwork deletes render every direct
  blocker, including SecurityGroup, NetworkACL, and NATGateway, with the relationship and
  required remediation; verify no partial deletion or detachment occurs.
- Verify NetworkACL pages/actions are present in every deployment, call the
  normal NetworkACL APIs for every configured manager target, never render
  Kubernetes NetworkPolicy as an ACL substitute, and show provider status when
  the operation is a development no-op.
- Verify workload attachment forms contain no NetworkACL selector, while they
  do contain the SecurityGroup selector.
- Verify the rule editor enforces direction-specific CIDR fields and renders
  the stateless return-traffic and deployment-baseline guidance.
- Verify ExternalIPPool has a metadata-only edit action for display name,
  description, labels, and annotations; verify the name and every network
  field remain read-only and no network-field update request is issued.
- Verify the NetworkACL Subnet picker lists only Ready Subnets in the selected
  VirtualNetwork, disables Subnets that already have any effective ACL
  (including the default ACL), and renders server validation details for a
  stale or invalid selection. Verify workload forms identify a
  Subnet with no effective ACL as not workload-ready, and verify a non-default
  Subnet does not silently inherit the default-VN SecurityGroup.
- Verify manual ExternalIPAttachment management is not presented as an edit or
  retarget flow; automatic attachments are shown read-only and link to the
  documented CLI/API workflow.

## Implementation details

- **Barrel export fix (prerequisite):** `libs/types/src/index.ts` re-exports every public
  networking type except `nat_gateway_type_pb`/`nat_gateways_service_pb` — add those two
  exports so tenant-facing hooks can import `NATGateway`/`NATGateways` from `@osac/types`
  (this is a hand-maintained barrel, not a `pnpm gen-types` output).
- **Tenant hooks** (`api/v1/networking.ts`, `api/v1/external-ip.ts`):
  `useNatGateways` (unfiltered, for the VirtualNetwork list page),
  `useNatGatewayForVirtualNetwork` (filtered, for the detail page), `useCreateNatGateway`,
  `useDeleteNatGateway`, `useCreateNetworkACL`, `useDeleteNetworkACL`,
  `useCreateSecurityGroup`, `useDeleteSecurityGroup`,
  `useExternalIPs`, `useCreateExternalIP`, `useDeleteExternalIP`.
  Add `'v1/nat_gateways'` to the `ApiRoute` union (`'v1/external_ips'` already exists
  there).
- **Admin hooks** (new `api/v1/private/external-ip-pools.ts`, following
  `storage-backends.ts`'s shape): `usePrivateExternalIPPools`, `usePrivateExternalIPPool`,
  `useCreateExternalIPPool`,
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
