---
title: netris-fabric-manager
authors:
  - Dan Manor
creation-date: 2026-09-28
last-updated: 2026-10-05
tracking-link:
  - "https://redhat.atlassian.net/browse/OSAC-2434"
prd:
  - "prd.md"
see-also:
  - Unified Networking: /enhancements/OSAC-1433-unified-networking
  - Network Manager Integration Contract PRD: /enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/prd.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - Agentless VLAN Fabric Manager: /enhancements/OSAC-3664-agentless-vlan-fabric-manager-networking
---

# Fabric Manager — Netris

## Summary

This document specifies the technical target for the Netris Fabric Manager,
OSAC's production networking backend, against the
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).
It maps the contract operations to Netris controller resources and REST calls.
The current Netris tasks still have contract gaps documented below; the
implementation is not contract-v1 conformant until those gaps are closed and
the assigned operation and target set passes conformance validation.

See [PRD](prd.md) for the problem statement, user stories, and requirements.

## Motivation

OSAC networking relies on a pluggable fabric manager to translate
infrastructure-agnostic networking resources (VirtualNetwork, Subnet,
SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) into physical
network configuration. The Netris fabric manager is the first production
backend and serves as the reference backend. Its behavior is scattered
across Ansible roles, operator
controllers, and feature-level docs, making it difficult to reason about
correctness, validate new backends against a baseline, or identify enforcement
gaps.

This design documents the Netris-specific resource mapping, Ansible role
behavior, and failure recovery.

### Goals

- Map each OSAC networking resource to the specific Netris resources the
  backend creates, updates, and deletes.
- Describe how Netris Ansible tasks call the Netris controller API.
- Define failure modes, error surfaces, and recovery behavior.

### Non-Goals

- Operating or changing the Netris controller, SoftGate, switches, or fabric
  infrastructure. This design specifies OSAC's target use of the existing
  Netris roles and identifies the OSAC-side changes needed to meet it.
- Kubernetes-native implementation details; this document covers only the
  Netris fabric manager role.
- SecurityGroup API semantics and required manager behavior — a cross-backend concern defined by the Network Manager Integration Contract.
- Multiple Netris controllers, split-controller topologies, or Netris
  controller HA. One controller may manage multiple sites mapped to OSAC
  regions.

## Proposal

### Netris Implementation

The Netris backend implements the fabric-manager role through Ansible roles
in the `osac.templates.netris` collection, invoked by AAP.

#### Manager Registration

The target operator registration uses the Fabric role label, logical name
`netris`, implementationRef `osac.templates.netris`, contractVersion v1, and
capabilities `ipv4,evpn-vxlan`. It may declare
`compatibleK8sManagers: cudn_evpn` only after both the complete Fabric role
conformance suite and the pair integration suite pass for the recorded Netris
and `cudn_evpn` collection versions. Netris plus `cudn_evpn` is the first pair
targeted for certification, but is not certified now: SecurityGroup
conformance remains a blocker. Do not advertise the manager as contract v1 or
make it selectable until every assigned operation and target passes. A
different K8s Manager requires its own conformance and pair test. The Netris
registration never lists an operation subset. The registration format and operation identifiers are defined by the
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).
The resource mapping below documents Netris-specific backend behavior.

#### Netris Role Operations

The role tasks in `osac.templates.netris` call the Netris controller REST API
using its authentication configuration. Resource-specific task and API
mappings are listed below.

The Netris role implements fabric workload operations as follows:

- `move_network_attachment` moves a BaremetalInstance port between the
  provisioning V-Net and tenant Subnet V-Net according to the exact
  `context.attachment.action` (`ATTACH` or `DETACH`). The role checks current
  port membership, making repeat operations safe. CaaS physical workers use
  this through their BMaaS BaremetalInstance path; Cluster is not this
  operation's target.
  Attach returns `osac_result.data.attachment.state: ATTACHED`; detach returns
  `RESTORED`. Both include the stable binding UID and observed backend port
  identity.
- `query_dhcp_lease` resolves exactly one Netris IPAM lease for each
  attachment using the authoritative MAC address and Subnet reference supplied
  in the contract input. Missing, stale, or ambiguous matches fail the task;
  it does not fall back to a workload display name. The result uses
  osac_result.data.leases. VM addresses come from OVN-Kubernetes status and do
  not use this Fabric Manager operation.

The collection role is invoked with the canonical v1 task entry points. This
crosswalk is the binding between the shared OSAC interface and the Netris
implementation; the tasks do not define a Netris-specific operation API.

| Contract operation | Contract `tasks_from` | Netris implementation task |
|---|---|---|
| `virtual_network.create` / `virtual_network.delete` | `create_virtual_network` / `delete_virtual_network` | `create_virtual_network.yaml` / `delete_virtual_network.yaml` |
| `subnet.create` / `subnet.delete` | `create_subnet` / `delete_subnet` | `create_subnet.yaml` / `delete_subnet.yaml` |
| `security_group.apply` / `security_group.delete` | `create_security_group` / `delete_security_group` | `create_security_group.yaml` / `delete_security_group.yaml` |
| `external_ip_pool.create` / `external_ip_pool.delete` | `create_external_ip_pool` / `delete_external_ip_pool` | `create_external_ip_pool.yaml` / `delete_external_ip_pool.yaml` |
| `external_ip.allocate` / `external_ip.release` | `create_external_ip` / `delete_external_ip` | `create_external_ip.yaml` / `delete_external_ip.yaml` |
| `external_ip_attachment.create` / `external_ip_attachment.delete` | `attach_external_ip` / `detach_external_ip` | `attach_external_ip.yaml` / `detach_external_ip.yaml` |
| `nat_gateway.create` / `nat_gateway.delete` | `create_nat_gateway` / `delete_nat_gateway` | `create_nat_gateway.yaml` / `delete_nat_gateway.yaml` |
| `workload_attachment.move` | `move_network_attachment` | `move_network_attachment.yaml` |
| `dhcp_lease.query` | `query_dhcp_lease` | `query_dhcp_lease.yaml` |

Every successful task returns the contract's `osac_result` artifact with the
operation, OSAC resource UID, and observed generation. For a Subnet in an `evpn-vxlan` profile, `create_subnet` writes or updates
the standard `osac-fabric-handoff-<subnet-uid>` ConfigMap in the OSAC operator
namespace. It includes the assigned L2 VNI, parent L3 VNI, actual L2/L3
import/export route targets, and every IPv4 range reserved by the fabric. The
role returns the normal `osac_result` envelope with `data: {}`. OSAC validates
and pins the ConfigMap identity; the compatible K8s Manager reads the same
contract-defined object. The Netris role does not use a private ConfigMap,
callback, or Netris-specific handoff schema. ExternalIP allocation and DHCP query
results use the schemas defined by the contract. Current task behavior is
called out separately in the resource mapping and implementation-gap text.

#### Resource Mapping

The following table describes the Netris-specific mapping.

| OSAC Resource | Netris Resources | Ansible Role / Task | Details |
|---------------|-----------------|---------------------|---------|
| VirtualNetwork | VPC (ipVRF) + IPAM allocation | `netris.controller.vpc` → `create`, `netris.controller.ipam` → `create_allocation` | VPC provides isolated routing domain. IPAM allocation with `purpose=common` reserves the VN CIDR. Region is mapped to Netris site ID via `netris_region_site_map`. |
| Subnet | IPAM subnet + VNet (macVRF) | `netris.controller.ipam` → `create_subnet`, `netris.controller.vnet` → `create` | IPAM subnet under parent VPC. VNet with gateway (first usable IP), DHCP enabled, range = second usable to last usable. VXLAN VNI auto-assigned by Netris. Target: use the parent VirtualNetwork's resolved site. Current task passes `netris_site_id` directly instead. |
| SecurityGroup | ACL/endpoint policy | `netris.controller.acl` → `create` | Contract target: apply policy only to each binding in the complete `context.securityGroup.attachments` snapshot, trigger apply on group/rule/binding changes, and implement per-binding multi-group union semantics. Current tasks expand rules across Subnet CIDRs and do not establish binding-level isolation; they also skip same-name ACLs and do not remove obsolete ACLs. Missing lookup data defaults to VPC ID 1 and `0.0.0.0/0`. |
| ExternalIPPool | Provider-owned NAT IPAM allocation + common subnet | `netris.controller.ipam` → `create_allocation`, `create_subnet` | The current API permits one CIDR. The allocation has no Netris `purpose` field; its common subnet uses `purpose=common`. Target ownership uses an exact Netris name derived from the pool UID; current tasks identify allocations by pool name (or a numeric suffix if multiple CIDRs are supplied). |
| ExternalIP | IPAM /32 subnet (`purpose=nat`) | `netris.controller.ipam` → `create_subnet` | Target ownership uses an exact Netris name derived from the ExternalIP UID and reuses that reservation. The manager returns the address in `osac_result`; OSAC validates it and writes the annotation and status. Current tasks find an existing /32 by ExternalIP metadata name, scan pool allocations by name, and patch the annotation directly. That current behavior violates the contract, and those name matches do not prove ownership. The /32 subnet uses `purpose=nat`. |
| ExternalIPAttachment | DNAT rule | `netris.controller.nat` → `create` | `nat_action: dnat`, destination = ExternalIP allocated address, DNAT-to = target internal IP. Target: workload targets use the resolved tenant VPC and its site; use the management VPC only for an explicitly supported cluster endpoint. Current tasks default to the management VPC when the tenant VPC annotation is missing or lookup does not resolve, and pass `netris_site_id`. |
| NATGateway | SNAT rule (NAT) | `netris.controller.nat` → `create` | `nat_action: snat`, source = VN CIDR, SNAT-to = ExternalIP allocated address. Target: use the resolved tenant VPC and its site; fail closed if either cannot be resolved. Current tasks default to the management VPC when the tenant VPC annotation is missing or lookup does not resolve, and pass `netris_site_id`. |

#### Deletion Mapping

Each create operation has a corresponding delete task that reverses it:

| OSAC Resource | Delete Task | Netris Resources Removed |
|---------------|-------------|--------------------------|
| VirtualNetwork | `delete_virtual_network.yaml` | IPAM allocation + VPC |
| Subnet | `delete_subnet.yaml` | VNet + IPAM subnet |
| SecurityGroup | `delete_security_group.yaml` | All ACL rules owned by the SecurityGroup, including obsolete rules |
| ExternalIPPool | `delete_external_ip_pool.yaml` | Common subnets + IPAM allocations |
| ExternalIP | `delete_external_ip.yaml` | /32 IPAM subnet |
| ExternalIPAttachment | `detach_external_ip.yaml` | DNAT rule |
| NATGateway | `delete_nat_gateway.yaml` | SNAT rule |

The current Netris ACL task mapping does not establish how order-preserving
allow-rule and stateful-return SecurityGroup behavior is realized on same-Subnet and routed
paths. Treat Netris contract conformance as unproven until implementation and
end-to-end tests demonstrate the complete contract behavior, including DNAT
and SNAT paths.

The operator deletion guard must retain an ExternalIP while either an
ExternalIPAttachment or NATGateway still references it. The SNAT rule must be
removed before the ExternalIP is released; the shared dependency is defined by
the Unified Networking design.

### API Extensions

No new API extensions. The Netris backend implements the existing
networking API defined by the unified networking design (OSAC-1433). The
backend is selected through provider-level configuration (NetworkClass
`fabricManager` field), not through API changes visible to tenants.

Under the contract, the manager returns an ExternalIP address in
`osac_result`; OSAC writes the
`osac.openshift.io/allocated-address` annotation and resource status only after
validating that result. The target ownership model
uses deterministic Netris object names derived from immutable OSAC object UIDs;
it does not require extra CRD fields or assume Netris supports custom metadata.
Current resource tasks instead find and delete objects by human-readable
metadata name, which does not prove which OSAC object owns a Netris object.

### Implementation Details/Notes/Constraints

#### Configuration

The Netris backend requires the following configuration, deployed as part
of the OSAC installation:

| Variable | Source | Description |
|----------|--------|-------------|
| `netris_controller_url` | Kubernetes Secret (required target; currently installer AAP ConfigMap) | Netris controller REST API base URL |
| `netris_username` | Kubernetes Secret (required target; currently installer AAP ConfigMap) | Netris controller username |
| `netris_password` | Kubernetes Secret / AAP credential | Netris controller password |
| `netris_site_id` | `global.networking.netris.siteId` → AAP environment ConfigMap | Default Netris site ID used only when a VirtualNetwork omits its region, and for provider-scoped resources without a VirtualNetwork region. |
| `netris_tenant_id` | `global.networking.netris.tenantId` → AAP environment ConfigMap | Netris tenant ID for OSAC resources |
| `netris_region_site_map` | Not currently exposed by the installer or passed to AAP | Required mapping from supported OSAC VirtualNetwork regions to Netris site IDs. An explicitly configured but unmapped region is an error; use `netris_site_id` only when region is omitted. Subnets inherit their parent VirtualNetwork's resolved site. |
| `netris_mgmt_vpc_id` | `global.networking.netris.mgmtVpcId` → AAP environment ConfigMap | Management VPC ID for explicitly supported cluster-endpoint DNAT rules; never a fallback for tenant NATGateway rules. |
| `netris_mgmt_vpc_name` | `global.networking.netris.mgmtVpcName` → AAP environment ConfigMap | Management VPC name for explicitly supported cluster-endpoint DNAT rules. |

#### Idempotency

Every Ansible task checks for existing resources before creating:

- VPC: checks `vpc_already_existed` from `netris.controller.vpc.create`
- IPAM: checks `ipam_already_existed` from `netris.controller.ipam.create_*`
- VNet: checks `vnet_already_existed` from `netris.controller.vnet.create`
- NAT: checks `nat_already_existed` from `netris.controller.nat.create`
- ACL: checks existing ACL by name before creating

Idempotent reconciliation is also required for update requests: when a mutable
spec changes, provisioning must update the existing Netris objects until they
match the new desired state. Merely finding an existing object and returning
success would leave stale configuration; retrying the update must not create
duplicates. This desired-state convergence is essential for update requests,
not just duplicate prevention. Delete tasks treat an already absent Netris
resource as successfully deleted. Resource lookups and deletes use exact
Netris IDs or stable UID-derived owner keys; they do not infer ownership from a
human-readable name pattern alone.

#### ExternalIP Allocation Algorithm

ExternalIP allocation must be serialized across AAP jobs for each pool, either
by using an atomic Netris allocation operation or by holding a shared
pool-scoped lock across selection and reservation. The current role scans
existing /32 subnets, selects the first free address, then creates a /32
reservation. It has no shared lock or atomic reservation, so concurrent jobs
can select the same address. It finds pool allocations by pool name (or a
numeric suffix for multiple CIDRs) and existing reservations by ExternalIP
name; neither lookup proves UID ownership.

1. Resolve the provider pool's single Netris allocation by an exact,
   deterministic Netris name derived from the ExternalIPPool UID, not by a
   human-readable pool name or suffix pattern.
2. Before selecting an address, look up the exact /32 reservation name derived
   from the ExternalIP UID within that pool allocation. If found, reuse it and
   return its address in `osac_result.data.externalIP.address`. OSAC validates
   that result and repairs its annotation/status if necessary. The manager does
   not patch the ExternalIP CR. The current role instead uses human-readable
   names for both lookups and cannot prove ownership.
3. If no reservation exists, read current reservations while holding the
   pool allocator lock and select a free host address, skipping network and
   broadcast addresses.
4. Reserve the address as a /32 IPAM subnet with `purpose=nat`, using the
   deterministic UID-derived Netris name as its ownership binding. Do not
   assume that the Netris API supports custom metadata fields. If reservation
   conflicts, refresh the full pool state and retry a bounded number of times.
   Current tasks name the subnet after the ExternalIP and have no explicit
   bounded conflict retry.
5. Return the allocated address in `osac_result.data.externalIP.address` only
   after the Netris reservation is confirmed. OSAC validates the operation,
   ExternalIP UID, generation, canonical address, and pool membership before
   writing `osac.openshift.io/allocated-address` and `ExternalIP.status.address`.
   If OSAC cannot persist that result, retry returns the same UID-owned Netris
   reservation. The manager never writes OSAC annotations or status.
6. Release the exact owned reservation on deletion; an already-absent
   reservation is successful.

Pool CIDRs must be /30 or wider — /31 (RFC 3021) produces an empty
candidate range and is not supported. The current role assumes this minimum
but does not validate it before scanning.

#### SecurityGroup Binding Policy

Contract v1 supplies a complete current attachment snapshot to every
`security_group.apply` invocation. The backend must enforce policy only for
those bindings, remove policy from bindings absent in a later snapshot, and
compute each binding's effective allow set as the union of its attached
SecurityGroups. Two endpoints on the same Subnet can have different groups;
Subnet-CIDR-wide permits alone cannot satisfy that requirement because they
may expose one endpoint's rules to another. The Netris implementation must
identify a backend mechanism that enforces per-binding membership, default
deny, updates/removals, and established return traffic across same-Subnet,
routed, DNAT, and SNAT paths.

Current tasks expand rules across Subnet CIDRs, generate ACL names from the
SecurityGroup name and rule/Subnet indexes, skip same-name ACLs, and do not
remove obsolete ACLs. This does not implement the contract's binding snapshot,
multi-group union, or lifecycle dispatch requirements. Missing VPC or Subnet
lookup data also defaults to VPC ID 1 and `0.0.0.0/0` rather than failing closed.
SecurityGroup conformance is therefore unproven and blocks claiming that the
current Netris manager implements contract v1.

### Security Considerations

#### Credential Handling

The target stores Netris controller credentials
(`netris_controller_url`, `netris_username`, `netris_password`) in Kubernetes
Secrets and injects them into AAP as credential types. They are never written
to the manager registration ConfigMap, resource status, events, or tenant-visible output. The current installer writes the URL and username to the AAP
environment ConfigMap and supplies the password as an AAP credential; the
URL/username placement does not meet the target Secret boundary. AAP task output,
job status, resource
conditions, and events may expose only allowlisted diagnostic fields such as
operation, resource kind, sanitized Netris error code, request ID, and AAP job
ID. Redact credentials, authorization data, secret-bearing response fields,
raw response bodies, and tenant or network identifiers before surfacing
diagnostics. Current tasks emit resource names and network addresses in debug
output; the ACL create task also includes Netris error message/content in its
failure output. The current task output does not meet this redaction target.

#### Tenant Isolation

Different VirtualNetworks map to separate Netris VPCs (VRFs). Traffic
isolation between VPCs is enforced by the Netris controller at the fabric
level. A workload in one VPC cannot reach another VPC's private addresses,
even when CIDRs overlap. Cross-VN traffic is only possible via ExternalIPs,
which traverse the external path through DNAT/SNAT rules.

#### Input Validation

- CIDR fields are validated at the CRD level (CEL validation for canonical
  IPv4 format, no IPv6).
- The Netris Ansible roles validate required annotations before proceeding
  (e.g., `osac.openshift.io/externalip-name` on NATGateway).
- An explicitly configured VirtualNetwork region should resolve to one Netris
  site before provisioning; only an omitted region may use `netris_site_id`.
  Subnets, NATGateway rules, and tenant-workload DNAT should use the resolved
  site associated with their parent VirtualNetwork. Current VirtualNetwork
  tasks fall back to `netris_site_id` for an unmapped region; Subnet, NATGateway,
  and ExternalIPAttachment tasks pass `netris_site_id` directly. The installer
  does not expose `netris_region_site_map`.
- NATGateway and tenant-workload DNAT should resolve the referenced tenant
  VirtualNetwork and Netris VPC. The management VPC is reserved for an
  explicitly supported cluster-endpoint DNAT request. Current NAT/DNAT tasks
  begin with the management VPC as a fallback, without distinguishing cluster
  endpoints from tenant workloads.

### Failure Handling and Recovery

| Failure Mode | Behavior | User Observation | Recovery |
|-------------|----------|-----------------|----------|
| Netris controller unreachable | AAP job fails with a connection error | Resource transitions to `Failed` with a sanitized diagnostic | Retry with bounded exponential backoff; it recovers when the controller is reachable |
| Netris API returns error (e.g., VPC name conflict) | Target: capture a sanitized error code and request ID. Current ACL task failure includes Netris message or response content | Resource transitions to `Failed`; diagnostics must omit credentials and unfiltered response data | Operator retries with exponential backoff; user may need to resolve the conflict in Netris |
| Parent VPC not found when creating Subnet | Ansible task fails with explicit error message | Subnet transitions to `Failed`: "Parent VPC not found in Netris controller" | Re-reconcile after parent VirtualNetwork is provisioned |
| VirtualNetwork region has no Netris site mapping | Target: fail before creating a VPC or IPAM resource. Current role falls back to `netris_site_id` | Current behavior may create resources at the default site for an unmapped region | Configure an explicit mapping or omit the region; update the role to fail closed for unmapped values |
| Tenant VPC cannot be resolved for NATGateway | Target: fail before creating a NAT rule. Current role retains its management-VPC default | A tenant SNAT rule can be created in the management VPC | Resolve the tenant VPC and update the role to fail closed |
| ExternalIP pool exhausted | Ansible task fails: "No available IPs in ExternalIPPool" | ExternalIP transitions to `Failed` with pool exhaustion message | Cloud Infrastructure Admin provisions additional IPAM capacity in Netris |
| Concurrent ExternalIP allocation selects the same candidate | Current scan-then-reserve tasks have no cross-job lock or bounded conflict retry | Allocation can fail or be ambiguous under concurrent jobs | Refresh pool state; implement atomic reservation or a shared pool lock |
| AAP job times out | Job transitions to `Failed` after AAP timeout | Resource shows `Failed` with timeout message | Automatic retry on next reconciliation |
| Partial provisioning (e.g., VPC created but IPAM allocation fails) | AAP job fails; VPC remains in Netris | Resource shows `Failed`; re-reconciliation will find existing VPC and retry IPAM allocation (idempotent) | Automatic convergence on retry |

The provisioning lifecycle uses `DesiredConfigVersion` hashing to avoid
redundant reprovisioning. When a resource's spec changes, the version hash
changes and triggers a new provisioning cycle. A successful job for the same
version may be skipped only while its managed Netris state is known to match
desired state. A failed or incomplete job for the same version is retried after
exponential backoff (2 to 30 minutes), and detected missing Netris resources
must trigger repair even when the version is unchanged. This desired-state
convergence, including mutable SecurityGroup rule updates, is not implemented
by the current Netris ACL tasks.

### RBAC / Tenancy

No RBAC changes are introduced by the Netris backend. Tenant isolation is
inherited from the unified networking model:

- VirtualNetworks are namespaced resources scoped to tenants via
  `osac.openshift.io/tenant` annotations.
- Tenants can only see and manage their own networking resources.
- Provider-level resources (NetworkClass, ExternalIPPool) are cluster-scoped
  and managed by Cloud Infrastructure Admins.
- The Netris backend enforces fabric-level isolation through VPC separation —
  each VirtualNetwork maps to a dedicated VPC.

### Observability and Monitoring

- **AAP job status**: Each provisioning and deprovisioning operation is
  tracked as a job in `status.provisioningJobs[]`, with state, message,
  start time, end time, and sanitized error details only.
- **Kubernetes conditions**: Standard conditions report detailed status
  (e.g., `Ready`, `Progressing`, `Degraded`).
- **Ansible task output**: AAP job output includes operation summaries and
  sanitized diagnostics. Raw Netris response bodies, credentials, and
  authorization data are not copied into tenant-visible status or unfiltered
  logs.
- **Existing monitoring**: The Netris controller has its own monitoring
  and alerting for fabric health. OSAC does not duplicate this.

### Risks and Mitigations

#### Netris controller availability

If the Netris controller is unavailable, all provisioning and
deprovisioning operations fail. Resources transition to `Failed` with a
connection error message. Recovery is automatic through reconciliation
when the controller becomes reachable. Mitigation: the Netris controller
should be deployed with appropriate availability guarantees by the Cloud
Infrastructure Admin.

#### Drift between OSAC state and Netris state

Manual changes in the Netris controller (e.g., deleting a VPC that OSAC
manages) create drift from OSAC's desired state. The target behavior is to
detect and repair missing managed resources; the current hash-based lifecycle
does not reliably trigger that repair after a successful job. Manual changes
that create conflicting state (e.g., a VPC name collision) require operator
intervention. Mitigation: document that OSAC-managed Netris resources should
not be modified manually and implement the recovery trigger above.

#### Netris API breaking changes

The backend depends on the Netris controller REST API. Breaking changes
to the API require updating the Ansible roles. Mitigation: pin the
supported Netris controller version range and validate compatibility
before upgrades.

#### SecurityGroup rule explosion

The Cartesian product expansion (rules × subnets) can produce a large
number of ACL rules. For a SecurityGroup with 10 rules on a VirtualNetwork
with 5 subnets, the backend creates 50 ACL rules per direction (100 total).
Mitigation: document the expansion behavior and recommend keeping
SecurityGroup rules focused. Future work may introduce a VPC-level ACL
abstraction in Netris to avoid per-subnet expansion.

### Drawbacks

- **AAP dependency**: The Netris backend requires AAP for provisioning,
  adding operational complexity. A direct Netris API client in the
  operator would reduce this dependency but would require maintaining
  a Go SDK for the Netris controller API.
- **Eventual consistency**: The provisioning model is asynchronous (operator
  → AAP → Netris). Resource status reflects the last known state from AAP
  job polling, not real-time Netris state. A resource may show `Ready`
  while the underlying Netris configuration has been manually modified.

## Alternatives (Not Implemented)

### Direct Netris API integration in the operator

Instead of dispatching through AAP, the operator could call the Netris
controller REST API directly from Go code. This would eliminate AAP as a
dependency and provide synchronous provisioning. Rejected because:
- The AAP-based model is the established pattern for all OSAC provisioning.
- Ansible roles are easier to test and iterate on than compiled Go code.
- AAP provides job tracking, retry logic, and audit logging.

### Per-VPC ACL rules instead of per-subnet expansion

SecurityGroup rules could be applied at the VPC level instead of expanding
per subnet. Rejected because the Netris ACL API operates on specific CIDR
prefixes and does not support VPC-level wildcard rules.

## Test Plan

### Unit and Envtest

The OSAC-side test plan is explicit about what can run without a Netris server.
These tests cover registration discovery, dispatch, job input, status, retry,
and deletion guards; they do not assert the resulting Netris controller state.

| Case | Requirements | Owner | Scenario |
|---|---|---|---|
| N-UT-1 — Manager discovery and dispatch | FR-2, FR-3 | `osac-operator` | Verify duplicate manager names are rejected, a NetworkClass selecting `netris` resolves its registration, and resource operations select the expected role. |
| N-UT-2 — Desired configuration and retry | FR-11, NFR-4 | `osac-operator` | Verify unchanged successful configuration does not launch duplicate work; SecurityGroup create, rule update, and binding changes produce a new desired configuration version with the complete current binding snapshot; failed or incomplete work retries with the same spec hash. This checks operator scheduling and job input, not Netris ACL convergence. |
| N-UT-3 — Status and deletion guards | FR-12–14, FR-17–18 | `osac-operator` | Use controlled AAP job results to verify failure status, sanitized diagnostics, bounded retry behavior, and dependency guards before deletion. Netris API response parsing and backend cleanup are not covered here. |
| N-UT-4 — Lease discovery request and result | FR-10, FR-23 | `bare-metal-fulfillment-operator`, `osac-operator/pkg/provisioning` | Verify `osac_job_vars.context.attachments` carries each binding UID, Subnet UID/reference, interface, and authoritative MAC; verify exactly one matching entry is returned in `osac_result.data.leases` with `subnetRef`, `interface`, `ipAddress`, and `macAddress`, and OSAC publishes it to the corresponding BaremetalInstance attachment status. Missing, stale, or ambiguous matches fail. |
| N-UT-5 — SecurityGroup binding lifecycle dispatch | FR-11, Contract | `osac-operator` | Verify group creation, rule changes, and binding add/remove dispatch `security_group.apply` with the full current `context.securityGroup.attachments` snapshot; verify attach policy gates readiness and detach removes the workload before the next snapshot omits it. This verifies dispatch order and inputs, not Netris enforcement. |
| N-CHART-1 — Registration and credentials | FR-1, FR-19, NFR-2 | `osac-installer` | Run `make helm-networking-test`; after the Netris and cudn_evpn conformance and pair gates pass, verify the labeled registration ConfigMap declares ipv4 and evpn-vxlan capabilities plus compatibleK8sManagers=cudn_evpn; before the gates pass, verify that peer declaration is absent. Also verify Netris credentials are rendered into AAP Secrets and wired to network jobs. |

There is no Netris mock REST suite in the operator unit/envtest tier. A separate deployed pair integration test is required in CI for the pinned Netris and `cudn_evpn` collection versions. It uses the real Netris and OpenShift/CUDN path to verify mutual registration, the standard handoff ConfigMap, route-target/VNI consumption, and VM-to-fabric reachability. It is cross-manager coverage owned by the CUDN pair test plan; the operator Kind test is not a substitute. Until the pair test passes, the Netris registration must not advertise `compatibleK8sManagers: cudn_evpn`.

### As-a-Service E2E

End-to-end journeys belong to the owning as-a-service flows under
`tests/e2e/`, not to a duplicate Netris-specific E2E suite. The existing BMaaS
networking flow at
`tests/e2e/bmaas/regression/networking/test_bmaas_networking.py` is the current
Netris-backed example. Service flows should provision the provider-owned NAT
pool as setup, then test the tenant journey: create networking resources,
verify DHCP and connectivity or external NAT behavior, and clean up. Add
equivalent coverage to VMaaS or CaaS flows only where those services expose the
corresponding feature. These E2E checks verify the user-visible service path;
they cover only the operations exercised by those service flows. The existing
BMaaS flow covers pool allocation, VirtualNetwork/Subnet and SecurityGroup
provisioning, NAT egress, DHCP-based BareMetalInstance status, ExternalIP
attachment and ingress, connectivity/isolation, and deletion. Extend that flow
to verify concurrent ExternalIP allocations from one pool get distinct
addresses and retries reuse the same ExternalIP reservation. Also verify
SecurityGroup rules are isolated per binding when endpoints with different
groups share a Subnet, multiple groups union only on their own binding, and
attach/detach/update/remove operations converge with stateful return traffic
on same-Subnet, routed, DNAT, and SNAT paths. Include removal of obsolete
backend policy. These checks exercise real Netris-backed
service flows and do not create a separate integration suite. The current flow can be run
from the OSAC repository root with
`uv run pytest tests/e2e/bmaas/regression/networking/test_bmaas_networking.py`.

---

## Provenance

Authored: revise @ design 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ e97b06357

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"e97b06357","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
