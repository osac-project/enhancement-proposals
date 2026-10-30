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
communicate. This enhancement introduces a **bridge pod** per subnet,
connected via a secondary transit CUDN, to forward traffic between
subnets directly (bridge-to-bridge). Primary Layer2 CUDNs and the
namespace-per-subnet model are preserved — fully aligned with the EVPN
and OKEP-5224 roadmap.

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
  VirtualNetwork via bridge pods (bridge-to-bridge routing).
- Provide a default gateway for VMs that supports inter-subnet
  routing, internet egress, and future NAT Gateway.
- Preserve primary Layer2 CUDNs and namespace-per-subnet model —
  aligned with EVPN and OKEP-5224 roadmap.
- Maintain backward compatibility with the existing API (VirtualNetwork,
  Subnet, ComputeInstance CRDs).

### Non-Goals

- Inter-VirtualNetwork connectivity (VPC peering is a future
  enhancement using the peering CUDN mechanism).
- NAT Gateway implementation (future enhancement using a dedicated
  NAT gateway pod with EgressIP on the default cluster network).
- High availability for bridge pods (Phase 1 uses single pods;
  DaemonSet + smart ARP responder is Phase 2).
- Upstream contributions to OVN-Kubernetes.

## Proposal

Keep primary Layer2 CUDNs (namespace-per-subnet) and introduce a
**bridge pod** per subnet, connected via a secondary **transit CUDN**:

1. **Primary CUDNs unchanged**: Each subnet keeps its primary Layer2
   CUDN with its own namespace — same as today. VMs use `l2bridge`
   binding with OVN DHCP.

2. **Bridge pod**: A pod in each subnet namespace with three interfaces
   — the primary CUDN (acting as the `.2` gateway for VMs), the
   transit CUDN (connecting to other bridge pods), and the default
   cluster network. The bridge pod runs an agent that uses ipset-based
   forwarding rules to classify traffic into three tiers: inter-subnet
   (→ destination bridge pod directly via transit CUDN), EVPN-reachable
   (→ `.1` gateway), and egress (→ cluster network with MASQUERADE).

3. **Transit CUDN**: A single secondary CUDN per VirtualNetwork
   (`role: Secondary`) targeting all subnet namespaces via a shared
   label. Provides L2 connectivity between all bridge pods. Uses a
   link-local CIDR (`169.254.100.0/24`) since the transit IPs are
   only used as next-hop addresses for routing — no data-plane packets
   carry transit IPs as source or destination. If OVN-K does not
   support link-local CIDRs on a secondary Layer2 CUDN, fall back to
   a regular private range (e.g., `10.200.0.0/24`).

4. **VM default gateway**: VMs use `.2` (bridge pod) as their default
   gateway via cloud-init. OVN's `.1` remains available on the logical
   switch but VMs route through `.2` for all traffic.

### Architecture

```text
Subnet-A NS                    Subnet-B NS
┌──────────────┐              ┌──────────────┐
│ VM-A         │              │ VM-B         │
│ primary CUDN │              │ primary CUDN │
│ 10.0.1.5     │              │ 10.0.2.5     │
│ gw: .2       │              │ gw: .2       │
│              │              │              │
│ Bridge Pod   │              │ Bridge Pod   │
│ pri: 10.0.1.2│              │ pri: 10.0.2.2│
│ trn: 169.254.│──transit─────│ trn: 169.254.│
│      100.2   │    CUDN      │      100.3   │
│ routes:      │  (link-local) │ routes:      │
│  10.0.2.0/24 │              │  10.0.1.0/24 │
│  via .100.3  │              │  via .100.2  │
└──────────────┘              └──────────────┘
```

### Workflow Description

#### VirtualNetwork Provisioning

1. Tenant creates a VirtualNetwork:

   ```bash
   osac create virtualnetwork --region us-east-1 \
     --ipv4-cidr 10.0.0.0/16 --name my-network
   ```

2. The fulfillment service creates a VirtualNetwork CR.
3. The osac-operator triggers AAP provisioning.
4. The osac-operator creates the transit CUDN.
5. The VirtualNetwork is marked as Ready.

#### Subnet Provisioning

1. Tenant creates a Subnet referencing a VirtualNetwork:

   ```bash
   osac create subnet --virtual-network my-network \
     --ipv4-cidr 10.0.1.0/24 --name frontend-subnet
   ```

2. The osac-operator triggers AAP provisioning, which creates the
   primary CUDN and subnet namespace (same as today).
3. The osac-operator creates a bridge pod in the subnet namespace
   with primary CUDN (`.2` via IPAMClaim) and transit CUDN interfaces.
4. The operator updates ConfigMaps for all bridge pods in the VN with
   the new subnet's CIDR and transit IP.
5. OVN port security is opened on the bridge pod's primary and transit
   CUDN ports.
6. The Subnet is marked as Ready.

#### ComputeInstance (VM) Creation

1. Tenant creates a ComputeInstance with a subnet attachment:

   ```bash
   osac create computeinstance --template ocp_virt_vm \
     --network-attachment subnet=frontend-subnet \
     --name my-vm
   ```

2. The osac-operator resolves the target namespace (subnet namespace)
   and triggers AAP provisioning.
3. The VM is created with `l2bridge` binding on the primary CUDN
   (same as today). OVN DHCP assigns the IP.
4. Cloud-init sets the default gateway to `.2` (bridge pod).
5. The VM can communicate with VMs on other subnets via the bridge
   pods (bridge-to-bridge routing over the transit CUDN).

#### Bridge Pod Interfaces

The bridge pod has three interfaces:

- **eth0** — primary CUDN (the subnet's L2 segment, shared with
  VMs and the OVN `.1` gateway)
- **net1** — transit CUDN (secondary, connecting to other bridge pods)
- **cluster network interface** — the default cluster network,
  present on all pods (unlike VMs which use
  `autoattachPodInterface: false`)

OVN port security on the bridge pod's primary CUDN port is opened
to the VN CIDR (e.g., `<MAC> 10.0.0.0/16`), allowing the bridge pod
to forward packets with any source IP within the VN. The transit CUDN
port is opened similarly. VM ports retain their default port security.

#### Bridge Pod Agent

The bridge pod runs an **agent** as its main process (replacing
`sleep infinity`). The agent sets up the forwarding rules on startup
and watches a **ConfigMap** for configuration changes. The operator
updates the ConfigMap when subnets are added/removed, EVPN CIDRs
change, or NAT Gateway is configured.

The agent classifies forwarded traffic into three tiers using
**ipsets** and **iptables marking**:

1. **VN subnets** (ipset `vn-subnets`): traffic destined for other
   subnets in the VN → forwarded directly to the destination bridge
   pod via transit CUDN
2. **EVPN-reachable CIDRs** (ipset `evpn-cidrs`): traffic destined
   for networks reachable via the EVPN fabric → forwarded to `.1`
   (primary CUDN gateway)
3. **Everything else**: internet, DNS, Kubernetes API → forwarded to
   cluster network with MASQUERADE

#### Bridge Pod Forwarding Rules

```text
sysctl -w net.ipv4.ip_forward=1

# === ipsets (populated by agent from ConfigMap) ===
ipset create vn-subnets hash:net       # e.g., 10.0.1.0/24, 10.0.2.0/24
ipset create evpn-cidrs hash:net       # e.g., 172.16.0.0/16 (when connected)

# === iptables: classify traffic arriving from VMs on eth0 ===
# Priority 1: VN subnets → mark 1
iptables -t mangle -A PREROUTING -i eth0 \
  -m set --match-set vn-subnets dst -j MARK --set-mark 1
# Priority 2: EVPN CIDRs → mark 2 (only if not already marked)
iptables -t mangle -A PREROUTING -i eth0 -m mark --mark 0 \
  -m set --match-set evpn-cidrs dst -j MARK --set-mark 2
# Priority 3: everything else stays mark 0 → default route

# === policy routing ===
# Mark 1 → destination bridge pod via transit CUDN (per-subnet routes)
ip rule add fwmark 1 table 100
ip route add 10.0.2.0/24 via 169.254.100.3 dev net1 table 100
ip route add 10.0.3.0/24 via 169.254.100.4 dev net1 table 100

# Mark 2 → .1 (OVN/EVPN gateway) via primary CUDN
ip rule add fwmark 2 table 200
ip route add default via 10.0.1.1 dev eth0 table 200

# Mark 0 → cluster network (main table default route)
ip route replace default via <cluster-gw> dev <cluster-iface>

# === NAT ===
# MASQUERADE only egress traffic on cluster network
iptables -t nat -A POSTROUTING -o <cluster-iface> -j MASQUERADE
```

Traffic from net1 (inter-subnet return from another bridge pod) is
not affected by the PREROUTING rules (they specify `-i eth0`). Return
traffic uses the main table's connected route (`10.0.1.0/24 dev
eth0`) to reach the local VM directly. Without the `-i eth0`
qualifier, return traffic would be re-marked and sent back to the
transit CUDN, creating a loop.

When the operator updates the ConfigMap (e.g., a new subnet is
added), the agent updates both the ipset and the routing table:

```text
ipset add vn-subnets 10.0.4.0/24
ip route add 10.0.4.0/24 via 169.254.100.5 dev net1 table 100
```

#### Traffic Flows

Inter-subnet (east-west):

```text
VM-A (10.0.1.5) → bridge-A (.2) on eth0 → ipset vn-subnets match
  → mark 1 → table 100 (10.0.2.0/24 via 169.254.100.3)
  → net1 → transit CUDN → bridge-B net1
  → connected route → eth0 → VM-B (10.0.2.5)
```

EVPN-reachable destination:

```text
VM-A (10.0.1.5) → bridge-A (.2) on eth0 → ipset evpn-cidrs match
  → mark 2 → table 200 → eth0 → .1 → EVPN fabric → destination
```

Internet egress:

```text
VM-A (10.0.1.5) → bridge-A (.2) on eth0 → no ipset match
  → mark 0 → main table → cluster-iface → MASQUERADE → internet
```

#### Configuration Delivery

The operator delivers configuration to bridge pod agents via
**ConfigMaps** — one per bridge pod. The ConfigMap contains the
desired state (subnet CIDRs with transit IPs, EVPN CIDRs). The
agent watches for ConfigMap changes and applies updates to ipsets
and routes without pod restart.

**Open question**: The exact interface names and default route
behavior when a primary CUDN coexists with the default cluster
network need to be verified on a live cluster. The agent must
enforce the correct routing regardless of OVN-K's default route
assignment.

### API Extensions

No new CRDs are introduced. Existing CRDs are unchanged:

- **VirtualNetwork**: No spec changes.
- **Subnet**: No spec changes. Primary CUDNs unchanged.
- **ComputeInstance**: No spec changes. VM binding unchanged (`l2bridge`).

The bridge pods, transit CUDN, and ConfigMaps are internal resources
managed by the operator — not exposed in the API.

### Implementation Details/Notes/Constraints

- **Primary UDNs preserved** — fully aligned with EVPN roadmap and
  OVN-K direction. No migration needed when OKEP-5224 or EVPN becomes
  available.
- **OVN port security** must be opened on the bridge pod's ports:
  the primary CUDN port is opened to the VN CIDR (allowing forwarding
  of packets with any VM source IP), and the transit CUDN port is
  opened similarly. VM ports retain their default port security.
- **Gateway IP** (`.2` on each subnet) is reserved via IPAMClaim.
- **Cloud-init** sets `.2` as the default gateway. OVN DHCP still
  provides the IP and DNS configuration.
- **VM binding unchanged** — `l2bridge` on primary CUDN, same as
  today.
- **Bridge pod agent** — each bridge pod runs a lightweight agent
  (replaces `sleep infinity`) that manages forwarding rules (ipsets,
  routes, iptables) and watches a ConfigMap for configuration updates.
  The operator never execs into pods.
- **Tenant isolation**: Bridge pods and transit CUDN carry the
  `osac.openshift.io/tenant` label.

### Component Lifecycle

- **Transit CUDN**: Created with the first subnet, deleted with the
  last subnet or VN deletion.
- **Bridge pod**: Created per subnet when the subnet reaches Ready.
  The agent configures forwarding rules on startup. Deleted on subnet
  deletion.
- **ConfigMaps**: The operator creates a ConfigMap per bridge pod.
  When subnets are added/removed, the operator updates all ConfigMaps
  in the VN. The agents detect changes and update ipsets/routes — no
  pod restart needed.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bridge pod is a SPOF per subnet | All traffic for that subnet lost during pod failure | Kubernetes restarts quickly; Phase 2 DaemonSet + ARP responder eliminates SPOF |
| Cloud-init dependency | VMs without cloud-init have no default route via `.2` | Document cloud-init requirement |
| OVN port security on bridge pod ports | Bridge pods can't forward without patching | Operator patches bridge pod ports on both primary and transit CUDNs; VM ports untouched |

### Drawbacks

- **Cloud-init dependency**: VMs depend on cloud-init to set `.2` as
  the default gateway. Without it, VMs use OVN's `.1` and have no
  inter-subnet connectivity (but egress and DNS still work via `.1`).

- **OVN NB database access**: The operator must patch port security on
  bridge pod ports (primary and transit CUDNs).

## Alternatives (Not Implemented)

### OVN-K native inter-UDN routing (OKEP-5224)

OVN-Kubernetes is developing ClusterNetworkConnect, which would allow
connecting UDNs via a distributed OVN connect-router. This would
provide native inter-subnet routing without bridge or router pods.

**Why not selected**: OKEP-5224 is a design proposal that has not been
implemented yet. Waiting for upstream is not viable for near-term
delivery. See OSAC-3071 for tracking.

When OKEP-5224 is implemented, the bridge pods can be retired — the
migration is straightforward since this proposal uses the same primary
UDNs that OKEP-5224 targets.

### Comparison: Bridge Pod vs OKEP-5224

| | Bridge Pod (this proposal) | OKEP-5224 |
|---|---|---|
| **Availability** | Works today with existing OVN-K | Design proposal, not implemented |
| **Architecture** | Bridge pod per subnet, bridge-to-bridge via transit CUDN | Distributed OVN connect-router across all nodes |
| **UDN type** | Primary (aligned with OKEP-5224) | Primary |
| **Network path** | Bridge → bridge (one extra hop) | OVN routes locally on each node — no extra hops |
| **Gateway** | `.2` via cloud-init | OVN handles DHCP gateway natively |
| **Port security** | Patched on bridge pod ports | No workaround needed |
| **Egress** | Three-tier: VN subnets / EVPN / cluster network | Native via OVN GR |
| **NAT Gateway** | Future: dedicated NAT gateway pod | OKEP-5224's gateway use case requires Layer3 tenant UDNs; not applicable to Layer2 CUDNs |
| **VPC Peering** | Future: dedicated peering pod | Depends on CUDN model |
| **Migration path** | Remove bridge pods when OKEP-5224 ships | N/A |

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
  with bridge-to-bridge routing.

#### Key differences

| | PR 107 | This proposal |
|---|---|---|
| **Layer** | API and provisioning flows | L3 routing implementation |
| **Inter-subnet routing** | Fabric manager (physical router) | Bridge pods, bridge-to-bridge (software) |
| **UDN model** | Primary UDNs, `l2bridge`, namespace-per-subnet | Same — primary UDNs, `l2bridge`, namespace-per-subnet |
| **Target deployment** | `phys-net` with physical fabric | `udn-net` without physical fabric |

#### Integration path

The bridge pods fit into PR 107's dispatcher architecture as a
**k8s_manager** for `udn-net` inter-subnet routing. Since this
proposal uses the same UDN model as PR 107 (primary UDNs, `l2bridge`,
namespace-per-subnet), there is no alignment needed — the proposals are
directly complementary.

## Phase 2: Distributed Bridge Pods with Smart ARP Responder

Phase 1 uses a single bridge pod per subnet. Phase 2 replaces each
bridge pod with a **DaemonSet** — one bridge pod per node per subnet —
providing both HA and load distribution.

### Architecture

```text
                    ARP Responder (control plane)
                    - Receives ARP broadcasts for .2
                    - Maps VM → node → local bridge pod MAC
                    - Responds with the local bridge pod's MAC

Subnet-A NS:
Node-1                          Node-2
┌─────────────────────┐        ┌─────────────────────┐
│ VM-A                │        │ VM-C                 │
│  gw .2 → local      │        │  gw .2 → local       │
│  bridge MAC         │        │  bridge MAC          │
│                     │        │                      │
│ Bridge Pod (DS)     │        │ Bridge Pod (DS)       │
│ pri: IPAM (.3)      │        │ pri: IPAM (.4)        │
│ trn: 169.254.100.2 │──trn───│ trn: 169.254.100.3   │
└─────────────────────┘  CUDN  └─────────────────────┘
                       (link-local)
```

### How It Works

1. **DaemonSet bridge pods**: One per node per subnet, each with its
   own IP from IPAM (not `.2`). Each pod has primary CUDN + transit
   CUDN interfaces, `ip_forward`, iptables marking, and policy routing.

2. **Gateway IP reservation**: The `.2` IP on each subnet is reserved
   via an IPAMClaim but not assigned to any pod. OVN does not respond
   to ARP for `.2`.

3. **Smart ARP responder pod**: A lightweight pod on the primary CUDN
   that handles ARP requests for `.2`:
   - Watches VMI locations (which node each VM is on) and DaemonSet
     pod MACs (which MAC each bridge pod has per node)
   - When a VM ARPs for `.2`, responds with the local bridge pod's MAC
   - The VM sends all traffic to the local bridge pod

4. **Traffic flow**: VM traffic goes to the local bridge pod (same
   node, no tunnel). The bridge pod forwards inter-subnet traffic via
   the transit CUDN directly to the destination bridge pod, and egress
   via the cluster network.

5. **Targeted ARP updates on failure**: GARPs are broadcast and would
   pollute other nodes' ARP caches. Instead, the ARP responder detects
   bridge pod failures and sends **unicast ARP responses** to affected
   VMs with a different node's bridge pod MAC. Convergence in seconds.

### Key Properties

- **HA**: If a bridge pod on a node dies, the ARP responder redirects
  affected VMs to a bridge pod on another node. No SPOF.
- **Load distribution**: Each node handles its own VMs' traffic.
- **Local forwarding**: VM traffic reaches the local bridge pod
  without crossing the OVN tunnel.
- **NAT Gateway compatible**: Bridge pods MASQUERADE to the cluster
  network. EgressIP on the default cluster network provides the
  specific public IP.

### Migration from Phase 1

1. Deploy bridge DaemonSets alongside the single bridge pods.
2. Deploy the ARP responder pod.
3. Remove the IPAMClaim for `.2` from single pod references.
4. The ARP responder takes over ARP for `.2`, directing VMs to local
   bridge pods.
5. VMs re-ARP on cache expiry and start using local bridge pods.
6. Remove the single bridge pod Deployments.

No VM downtime required — the transition is gradual as ARP caches
refresh.


## Open Questions

1. **Live migration**: Does KubeVirt support live migration with the
   `bridge` binding on secondary UDN interfaces? This needs testing.

2. **IPv6 support**: The bridge binding's built-in DHCP server only
   supports DHCPv4. IPv6 is deferred.

3. **NAT Gateway integration**: A dedicated NAT gateway pod per VN
   would centralize SNAT for egress traffic. Design deferred to a
   future enhancement.

4. **Upstream OVN-K contribution for port security**: Propose an
   annotation to control port security at the Kubernetes level,
   eliminating the need for direct OVN NB access.

## Test Plan

### Unit Tests

- Bridge pod ConfigMap generation: verify correct subnet CIDRs,
  transit IPs, EVPN CIDRs.
- ConfigMap update on subnet add/remove.
- Target namespace resolution: verify VN name is returned.

### Integration Tests

1. Create a VirtualNetwork → verify transit CUDN created.
2. Create two Subnets → verify bridge pods created with correct
   ConfigMaps, ipsets, and routes.
3. Create VMs in different subnets → verify IP assignment.
4. Verify inter-subnet connectivity (VM-A ↔ VM-B via bridge pods).
5. Verify intra-subnet connectivity (same subnet, direct L2).
6. Add a third subnet → verify all ConfigMaps updated, connectivity.
7. Delete a subnet → verify ConfigMaps updated, remaining connectivity.

### Edge Cases

- Bridge pod failure → verify restart and connectivity resumption.
- VirtualNetwork deletion → verify cleanup order.

## Graduation Criteria

- **Dev Preview (Phase 1)**: Single VN with two subnets, inter-subnet
  connectivity validated, single bridge pod per subnet.
- **Tech Preview (Phase 1)**: Multi-VN support, subnet add/remove
  lifecycle, cloud-init integration, egress via cluster network,
  automated test coverage.
- **GA (Phase 2)**: DaemonSet bridge pods + smart ARP responder for
  HA, NAT Gateway via EgressIP, VPC peering via peering CUDN.

## Upgrade / Downgrade Strategy

### Upgrade from current model (primary UDN, namespace-per-subnet)

Migration requires downtime per VirtualNetwork:

1. Stop all VMs in the VirtualNetwork.
2. Record VM-to-IP mappings.
3. Create the transit CUDN.
4. Deploy bridge pods with ConfigMaps.
5. Patch OVN port security on bridge pod ports.
6. Recreate VMs with cloud-init default gateway set to `.2`.
7. Verify connectivity.

A detailed migration plan will be developed separately.

### Downgrade

Reverse the migration: recreate per-subnet namespaces with primary
CUDNs, recreate VMs with l2bridge binding. Requires downtime.

## Version Skew Strategy

*Not required until targeted at a release.*

## Support Procedures

*Not required until targeted at a release.*

## Infrastructure Needed

No additional infrastructure is required. Bridge pods run on the
existing target cluster. The operator and AAP use existing access
patterns.
