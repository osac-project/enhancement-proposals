---
title: vn-subnet-connectivity
authors:
  - oamizur@redhat.com
creation-date: 2026-07-14
last-updated: 2026-07-19
tracking-link:
  - TBD
see-also:
  - "/enhancements/networking"
  - "/enhancements/inter-subnet-connectivity"
replaces:
  - "/enhancements/inter-subnet-connectivity"
superseded-by:
  - N/A
---

# VirtualNetwork Subnet Connectivity

## Summary

This enhancement provides L3 connectivity between subnets within a
VirtualNetwork for VMaaS. Today, each subnet is an isolated L2 segment
— VMs in different subnets of the same VirtualNetwork cannot
communicate. This enhancement introduces a router pod per
VirtualNetwork that forwards traffic between subnets, and migrates from
primary UDNs (namespace-per-subnet) to secondary UDNs
(namespace-per-VN) to enable the router pod architecture.

## Motivation

The current `udn-net` NetworkClass uses primary UDNs with one namespace
per subnet. This creates several limitations:

1. **No inter-subnet connectivity**: VMs in different subnets within the
   same VirtualNetwork cannot communicate. Each subnet is a fully
   isolated L2 segment with no routing between them.

2. **No egress path**: There is no NAT Gateway implementation for VMaaS.
   Without a routing layer, there is no place to apply SNAT for outbound
   traffic.

3. **Primary UDN constraints**: Primary UDNs replace the default pod
   network for the entire namespace. Only one primary UDN can exist per
   namespace, preventing multi-subnet architectures within a single
   namespace.

### User Stories

- As a tenant, I want VMs in different subnets of the same
  VirtualNetwork to communicate with each other so that I can build
  multi-tier applications (e.g., frontend subnet talking to backend
  subnet).

- As a tenant, I want my VMs to have a default gateway so that traffic
  destined for other subnets or external destinations is routed
  correctly.

- As a service provider, I want a routing layer per VirtualNetwork so
  that I can implement NAT Gateway for egress traffic in the future.

### Goals

- Provide L3 connectivity between subnets within the same
  VirtualNetwork via a router pod.
- Provide a default gateway for VMs to enable future NAT Gateway
  for egress traffic.
- Maintain backward compatibility with the existing API (VirtualNetwork,
  Subnet, ComputeInstance CRDs).

### Non-Goals

- Inter-VirtualNetwork connectivity (routing between different VNs).
- NAT Gateway implementation (future enhancement using the router pod
  as the egress point).
- High availability for the router pod (v1 uses a single pod; distributed
  routing via DaemonSet + smart ARP responder is Phase 2).
- Upstream contributions to OVN-Kubernetes.

## Proposal

Replace the current primary UDN model with secondary UDNs and a router
pod per VirtualNetwork:

1. **Namespace-per-VirtualNetwork**: When a VirtualNetwork is
   provisioned, create a single namespace for it (instead of creating a
   namespace per subnet). Multiple subnets within the VN share this
   namespace.

2. **Secondary CUDNs**: Each subnet creates a ClusterUserDefinedNetwork
   with `role: Secondary` (instead of `Primary`) targeting the VN
   namespace.

3. **Router pod**: The osac-operator deploys a router pod in the VN
   namespace. The router pod has one interface per subnet and acts as
   the default gateway (`.1` IP) for all VMs. It performs L3 forwarding
   between subnets and provides internet egress via SNAT to the cluster
   network — maintaining the same outbound connectivity that primary
   UDNs provide today via node masquerade.

4. **VM network attachment**: VMs attach only to the subnet's secondary
   UDN — they do not bind to the pod network. The VM gets its IP from
   OVN IPAM via DHCP. The default route to the router pod is injected
   via cloud-init.

### Workflow Description

#### VirtualNetwork Provisioning

1. Tenant creates a VirtualNetwork:

   ```bash
   osac create virtualnetwork --region us-east-1 \
     --ipv4-cidr 10.0.0.0/16 --name my-network
   ```

2. The fulfillment service creates a VirtualNetwork CR.
3. The osac-operator triggers AAP provisioning, which creates a
   namespace on the target cluster for this VirtualNetwork.
4. The osac-operator creates the router pod in the VN namespace. The
   router pod starts with the pod network only — subnet interfaces are
   added as subnets become Ready.
5. The VirtualNetwork is marked as Ready.

#### Subnet Provisioning

1. Tenant creates a Subnet referencing a VirtualNetwork:

   ```bash
   osac create subnet --virtual-network my-network \
     --ipv4-cidr 10.0.1.0/24 --name frontend-subnet
   ```

2. The osac-operator triggers AAP provisioning, which creates a
   secondary CUDN targeting the VN namespace.
3. The osac-operator reserves the `.1` gateway IP and updates the
   router pod with a new interface on this subnet.
4. The Subnet is marked as Ready.

#### ComputeInstance (VM) Creation

1. Tenant creates a ComputeInstance with a subnet attachment:

   ```bash
   osac create computeinstance --template ocp_virt_vm \
     --network-attachment subnet=frontend-subnet \
     --name my-vm
   ```

2. The osac-operator resolves the target namespace (VN namespace) and
   triggers AAP provisioning.
3. The VM is created on the subnet's secondary UDN. It receives its IP
   from OVN IPAM via DHCP, and the default route to the router pod is
   configured via cloud-init.
4. The VM can communicate with VMs on other subnets within the same
   VirtualNetwork via the router pod.

#### Traffic Flows

Inter-subnet (east-west):

```text
VM-A (subnet-a, 10.0.1.5)
  → default gw 10.0.1.1 (router pod)
  → router pod forwards
  → VM-B (subnet-b, 10.0.2.5)
```

Internet egress (north-south):

```text
VM-A (subnet-a, 10.0.1.5)
  → default gw 10.0.1.1 (router pod)
  → router pod SNATs to cluster network IP (eth0)
  → node masquerade → internet
```

This preserves the same egress behavior as primary UDNs. When NAT
Gateway is implemented, the generic SNAT is replaced with a specific
SNAT to the NAT Gateway's public IP — no VM reconfiguration needed.

### API Extensions

No new CRDs are introduced. Existing CRDs are unchanged:

- **VirtualNetwork**: No spec changes.
- **Subnet**: No spec changes. The CUDN role changes from Primary to
  Secondary (provisioning-side change).
- **ComputeInstance**: No spec changes. The `networkAttachments` field
  works as before. The VM binding changes (bridge instead of l2bridge)
  are provisioning-side.

The router pod Deployment is an internal resource managed by the
operator — not exposed in the API.

### Implementation Details/Notes/Constraints

- **Secondary UDNs are required** because the router pod must be
  multi-homed across subnets within a single namespace. Primary UDNs
  only allow one per namespace.
- **OVN port security** must be patched on the router pod's logical
  switch ports to allow forwarding of traffic with destination IPs
  outside the router's own address. The operator patches the OVN NB
  database to allow the VN CIDR.
- **Gateway IP** (`.1` on each subnet) is reserved via IPAMClaim to
  ensure deterministic addressing. The router pod recovers the same
  IPs after restart via `ipam.lifecycle: Persistent`.
- **Cloud-init** is required for the default route because secondary
  UDNs do not provide DHCP gateway options. VM images must support
  cloud-init.
- **VM IP assignment** uses OVN IPAM via the KubeVirt `bridge`
  binding's built-in DHCP server. No manual IP configuration needed.
- **Tenant isolation**: The router pod and VN namespace carry the
  `osac.openshift.io/tenant` label per OSAC convention, ensuring
  tenant-scoped resource ownership.

### Router Pod Lifecycle

- **Created** by the VirtualNetwork controller when the VN reaches
  Ready. Starts with the pod network only.
- **Updated** by the subnet controller when subnets are added or
  removed (new interfaces, IPAMClaims, port security patches).
- **Deleted** by the VirtualNetwork controller on VN deletion.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Router pod is a SPOF | Inter-subnet traffic lost during pod failure | Kubernetes restarts quickly; Phase 2 distributed routing eliminates SPOF |
| Router pod restart on subnet changes | Brief traffic interruption; OVN port security resets to default on new pod | Subnet addition is a rare operation; IPAMClaim preserves gateway IPs; operator re-patches port security after restart |
| Cloud-init dependency | VMs without cloud-init have no default route | Document cloud-init requirement; consider upstream OVN-K DHCP for secondary UDNs |
| MAC address changes on router restart | Up to 60s ARP convergence | Gratuitous ARP on startup (Phase 1); targeted unicast ARP updates (Phase 2) |
| Live migration untested | VMs on secondary UDNs with bridge binding may not support live migration | Needs testing before GA |

### Drawbacks

- **Cloud-init dependency**: VMs depend on cloud-init for the default
  route. This is a trade-off of using secondary UDNs, which lack native
  DHCP gateway support.

- **OVN NB database access**: The operator must patch port security
  directly in the OVN NB database. There is no Kubernetes-level API
  for this. A future upstream contribution (e.g., an
  `allowedAddresses` annotation on the UDN spec) would eliminate this
  dependency.

- **Subnet addition restarts the router pod**: Adding a subnet to an
  existing VN causes a brief interruption to all inter-subnet traffic
  in that VN while the router pod restarts with the new interface.

## Alternatives (Not Implemented)

### OVN-K native inter-UDN routing (OKEP-5224)

OVN-Kubernetes is developing ClusterNetworkConnect, which would allow
connecting UDNs via a distributed OVN connect-router. Unlike the router
pod approach, OKEP-5224 would not require secondary UDNs — its design
targets primary UDNs initially, which would eliminate the trade-offs
introduced by the move to secondary UDNs (cloud-init dependency, port
security patching, bridge binding). Secondary UDN support is listed as
future work in the OKEP.

**Why not selected**: OKEP-5224 is a design proposal that has not been
implemented yet. Waiting for upstream is not viable for near-term
delivery.

When OKEP-5224 is implemented, we should evaluate migrating to it based
on the trade-offs below.

### Comparison: Router Pod vs OKEP-5224

| | Router Pod (this proposal) | OKEP-5224 |
|---|---|---|
| **Availability** | Works today with existing OVN-K | Design proposal, not implemented |
| **Architecture** | Single router pod per VN (Phase 1); DaemonSet + smart ARP responder (Phase 2) | Distributed OVN connect-router across all nodes |
| **Network path** | Inter-subnet traffic always traverses the router pod's node — extra hops even when VMs are co-located | OVN routes locally on each node — no extra hops |
| **UDN type** | Requires secondary UDNs (router pod must be multi-homed in one namespace) | Design targets primary UDNs initially; secondary UDN support is future work |
| **Gateway** | Requires cloud-init `runcmd` for default route | OVN handles DHCP gateway natively |
| **Port security** | Requires `ovn-nbctl` patching per subnet | No workaround needed — OVN's own router |
| **Operational complexity** | Router image, IPAMClaims, Deployment lifecycle, OVN NB client | Zero — managed by OVN-K |
| **NAT Gateway** | Easy — add SNAT rules to the existing router pod | OKEP-5224's gateway use case requires Layer3 tenant UDNs; not applicable to Layer2 CUDNs used by VMaaS |
| **VPC Peering** | Simple — router pods connect via a shared peering CUDN; peering is just adding routes on each router | Depends on UDN model — simple with per-VN CUDNs, O(N×M) with per-subnet CUDNs |
| **ARP convergence** | Router pod restart changes MAC addresses; up to 60s connectivity gap without gratuitous ARP | Stable MAC across nodes — no ARP convergence delay |
| **Live migration** | Untested with bridge binding on secondary UDNs | Likely supported natively |

### Relationship to Unified Networking (PR 107 / OSAC-1029)

The [Unified Networking per-service EPs](https://github.com/osac-project/enhancement-proposals/pull/107)
define the API layer for VMaaS, CaaS, and BMaaS networking. This
proposal and PR 107 are **complementary** — they address different
layers of the stack.

#### What PR 107 provides (that this proposal does not)

- **Multi-NIC API**: `ComputeNetworkAttachment` proto with `primary`
  field for multi-NIC VM provisioning
- **Auto external access**: `auto_external_ip_attachment` flag for
  single-call ExternalIP + ExternalIPAttachment creation
- **Dispatcher pattern**: Routes AAP calls to the correct fabric/k8s
  manager based on NetworkClass
- **Per-service flows**: Detailed provisioning flows for VMaaS, CaaS,
  BMaaS with IP discovery feedback

#### What this proposal provides (that PR 107 does not)

- **Inter-subnet L3 routing for OVN-only deployments**: PR 107
  delegates inter-subnet routing to the fabric manager ("the fabric
  manager provides the L3 gateway for each subnet and routes between
  them automatically"). For `phys-net` deployments with a physical
  router (e.g., Netris SoftGate), this works. For `udn-net`
  deployments (pure OVN overlay, no physical fabric), there is no
  fabric manager providing L3 routing. This proposal fills that gap
  with the router pod.

#### Key differences

| | PR 107 | This proposal |
|---|---|---|
| **Layer** | API and provisioning flows | L3 routing implementation |
| **Inter-subnet routing** | Fabric manager (physical router) | Router pod (software) |
| **UDN model** | Primary UDNs, `l2bridge`, namespace-per-subnet | Secondary UDNs, `bridge`, namespace-per-VN |
| **Target deployment** | `phys-net` with physical fabric | `udn-net` without physical fabric |

#### Integration path

The router pod could fit into PR 107's dispatcher architecture as a
**k8s_manager** for `udn-net` inter-subnet routing. The namespace model
(namespace-per-VN vs namespace-per-tenant) and UDN type (primary vs
secondary) need alignment. PR 107's multi-NIC for VMaaS has the same
namespace constraint that drove this proposal to secondary UDNs — NADs
from other subnets are not available in the VM's namespace with
namespace-per-subnet.

## Phase 2: Distributed Router with Smart ARP Responder

Phase 1 (this proposal) uses a single router pod per VirtualNetwork.
Phase 2 replaces it with a DaemonSet of router pods — one per node —
providing both HA and load distribution.

### Architecture

```text
                    ARP Proxy Pod (control plane)
                    - Receives ARP broadcasts for .1
                    - Maps VM → node → local router MAC
                    - Responds with the local router's MAC

Node-1                          Node-2
┌─────────────────────┐        ┌─────────────────────┐
│ Router Pod (DS)     │        │ Router Pod (DS)      │
│ - Own IP from IPAM  │        │ - Own IP from IPAM   │
│ - Forwards traffic  │        │ - Forwards traffic   │
│                     │        │                      │
│ VM-A ──→ Router ──→ │ ─OVN─ │ ──→ VM-B             │
│  (local, no tunnel) │        │   (delivered by OVN) │
└─────────────────────┘        └─────────────────────┘
```

### How It Works

1. **DaemonSet router pods**: One per node, each with its own IP on
   each subnet (from OVN IPAM, not `.1`). Each pod enables `ip_forward`
   and has interfaces on all subnets via Multus.

2. **Gateway IP reservation**: The `.1` IP on each subnet is reserved
   via an IPAMClaim (same as Phase 1) but not referenced by any pod.
   This prevents OVN IPAM from assigning `.1` to a VM or other pod,
   while ensuring no OVN port has `.1` registered — so OVN does not
   respond to ARP for it.

3. **Smart ARP responder pod**: A single lightweight pod on the
   secondary UDN that handles ARP requests for the gateway IP (`.1`).
   The ARP responder:
   - Watches the Kubernetes API for VMI locations (which node each VM
     runs on) and DaemonSet pod MACs (which MAC each router has per node)
   - When a VM ARPs for `.1`, the responder looks up the VM's node and
     replies with the MAC of the router pod on that same node
   - The VM caches this MAC and sends all traffic to the local router

4. **Traffic flow**: VM traffic goes to the local router (zero extra
   hops on the same node), which forwards to the destination via OVN.
   Each direction of a TCP connection may use different router pods
   (asymmetric), which is fine for stateless L3 forwarding.

5. **Targeted ARP updates on restart**: GARPs cannot be used because
   they are broadcast — a GARP from one router would pollute ARP caches
   on VMs on other nodes. Instead, the ARP responder detects router pod
   restarts (via API watch) and sends **unicast ARP responses** to each
   VM on the affected node with the new router's MAC. Convergence in
   seconds.

### Key Properties

- **HA**: If a router pod on a node dies, the ARP responder detects it
  and sends unicast ARP updates to affected VMs with a different
  router's MAC. No SPOF, convergence in seconds.
- **Load distribution**: Each node handles its own VMs' traffic. No
  single bottleneck node.
- **No extra hops**: VM traffic reaches the local router without
  crossing the OVN tunnel. Only the forwarded traffic crosses the
  tunnel (same as OKEP-5224's distributed model).
- **NAT Gateway compatible**: NAT Gateway traffic routes through a
  designated router (the node with the public IP). Conntrack is on
  that router. Return traffic arrives at the same router. Active
  connections are lost on that specific router's failure (standard
  NAT failover behavior, mitigated by `conntrackd` if needed).

### Migration from Phase 1

1. Deploy DaemonSet router pods alongside the single router pod.
2. Deploy the ARP responder pod.
3. Remove the IPAMClaim for `.1` from pod references — OVN stops
   responding to ARP for it.
4. The ARP responder takes over ARP for `.1`, directing VMs to local
   routers.
5. VMs re-ARP on cache expiry and start using local routers.
6. Remove the single router pod Deployment.

No VM downtime required — the transition is gradual as ARP caches
refresh.

## Implementation Option: Tenant-Scoped Namespaces

With namespace-per-VN, a VM cannot have interfaces from multiple
VirtualNetworks — each VN's NADs are in a separate namespace, and a
pod can only reference NADs in its own namespace. To enable multi-VN
interfaces, all NADs must be in the same namespace. Using the existing
**tenant namespace** (`tenant.status.namespace`) achieves this while
aligning with the cloud provider model where VPCs are networking
constructs within an account, not isolation boundaries.

### Cloud Provider Alignment

In AWS, Azure, and GCP, VPCs/VNets are networking constructs within an
account — not hard isolation boundaries. An EC2 instance can have ENIs
in different VPCs. The account is the security boundary, not the VPC.

Tenant-scoped namespaces match this model: the tenant namespace is the
security boundary, VirtualNetworks are networking constructs within it.

### How It Works

- The tenant controller already creates a namespace per tenant on the
  target cluster (`tenant.status.namespace`). No new namespace creation
  needed.
- All subnet CUDNs target the tenant namespace (via tenant label)
  instead of a VN-specific namespace.
- All VMs, router pods, and NADs for a tenant share the tenant
  namespace.
- VN provisioning no longer creates or deletes namespaces.

### Comparison

| | Namespace-per-VN | Namespace-per-tenant |
|---|---|---|
| Multi-VN interfaces | Not possible — NADs in different namespaces | Natural — all NADs in same namespace |
| VPC peering (within tenant) | Peering CUDN targets VN namespaces via shared label | Peering CUDN targets tenant namespace — same complexity |
| Namespaces created | One per VN | Zero (reuses existing tenant namespace) |
| VN isolation within tenant | Namespace-level | Routing/policy only |

### Trade-offs

**Advantage**: Multi-VN interfaces, fewer namespaces, simpler
implementation, aligns with cloud provider model.

**Trade-off**: VN-level namespace isolation within a tenant is lost.
VMs could technically attach to any VN's subnet within the tenant.
For most cloud use cases this is acceptable — tenants manage their own
VN boundaries, and the real security boundary is between tenants, not
between VNs.

## Open Questions

1. **Live migration**: Does KubeVirt support live migration with the
   `bridge` binding on secondary UDN interfaces? This needs testing.

2. **IPv6 support**: The bridge binding's built-in DHCP server only
   supports DHCPv4. IPv6 is deferred.

3. **NAT Gateway integration**: The router pod is a natural place to
   implement SNAT for egress traffic. Design deferred to a future
   enhancement.

4. **Upstream OVN-K contribution for port security**: Propose an
   annotation to control port security at the Kubernetes level,
   eliminating the need for direct OVN NB access.

## Test Plan

### Unit Tests

- Router pod Deployment generation: verify correct Multus annotations,
  IPAMClaim references, sysctl settings.
- Router pod update on subnet add/remove.
- Target namespace resolution: verify VN name is returned.

### Integration Tests

1. Create a VirtualNetwork → verify namespace created.
2. Create two Subnets → verify two secondary CUDNs created, NADs
   auto-generated.
3. Verify router pod created with interfaces on both subnets.
4. Create VMs in different subnets → verify IP assignment.
5. Verify inter-subnet connectivity (VM-A ↔ VM-B via router).
6. Verify intra-subnet connectivity (same subnet, direct L2).
7. Add a third subnet → verify router pod updated, connectivity.
8. Delete a subnet → verify router pod updated, remaining connectivity.

### Edge Cases

- Router pod failure → verify restart and connectivity resumption.
- VirtualNetwork deletion → verify cleanup order.

## Graduation Criteria

- **Dev Preview (Phase 1)**: Single VN with two subnets, inter-subnet
  connectivity validated, single router pod.
- **Tech Preview (Phase 1)**: Multi-VN support, subnet add/remove
  lifecycle, cloud-init integration, automated test coverage.
- **GA (Phase 2)**: Distributed router with DaemonSet + smart ARP
  responder, NAT Gateway integration, live migration validation.

## Upgrade / Downgrade Strategy

### Upgrade from current model (primary UDN, namespace-per-subnet)

Migration requires downtime per VirtualNetwork:

1. Stop all VMs in the VirtualNetwork.
2. Record VM-to-IP mappings.
3. Create the VN namespace (new).
4. Create secondary CUDNs for each subnet.
5. Delete old per-subnet namespaces and primary CUDNs.
6. Deploy the router pod.
7. Recreate VMs with the new binding configuration.
8. Verify connectivity.

A detailed migration plan will be developed separately.

### Downgrade

Reverse the migration: recreate per-subnet namespaces with primary
CUDNs, recreate VMs with l2bridge binding. Requires downtime.

## Version Skew Strategy

*Not required until targeted at a release.*

## Support Procedures

*Not required until targeted at a release.*

## Infrastructure Needed

No additional infrastructure is required. The router pod runs on the
existing target cluster. The operator and AAP use existing access
patterns.
