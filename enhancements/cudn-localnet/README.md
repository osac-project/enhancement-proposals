---
title: cudn-localnet-fabric-integration
authors:
  - dmanor@redhat.com
creation-date: 2026-06-28
last-updated: 2026-06-28
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1511
see-also:
  - Unified Networking Architecture: /enhancements/unified-networking
  - Unified Networking PRD: /enhancements/unified-networking-prd
replaces:
  - N/A
superseded-by:
  - N/A
---

# CUDN Localnet: Connecting KubeVirt VMs to the Physical Fabric via VLANs

## Summary

This enhancement describes the first k8sManager backend for OSAC: CUDN
LocalNet. It bridges KubeVirt VMs to the physical fabric using
OVN-Kubernetes ClusterUserDefinedNetwork (CUDN) with Localnet topology
and 802.1Q VLAN tagging on br-ex. A single switch port per server
carries both node management (untagged) and VM tenant traffic (tagged
VLANs) in trunk mode — no BGP, VXLAN, or FRR-K8s required on the OCP
side.

## Motivation

OSAC VMs run inside KubeVirt pods on OVN-Kubernetes. By default, VM IP
addresses exist only within the OVN overlay and are not visible on the
physical fabric. For VMs to participate in infrastructure-agnostic
subnets alongside bare-metal servers and cluster nodes, the OVN overlay
must be bridged to the physical fabric. CUDN Localnet achieves this
using raw 802.1Q VLAN tags — the simplest approach that requires no
control-plane integration on the OCP side.

### User Stories

* As a Cloud Infrastructure Admin, I want to register CUDN LocalNet as
  a k8s manager so that regions with KubeVirt can bridge VMs to the
  physical fabric via VLAN tagging.

* As a Cloud Infrastructure Admin, I want the k8s manager to
  automatically configure NMState bridge-mappings on hosting clusters so
  that I don't need to manually set up OVN-to-fabric connectivity.

* As a Cloud Infrastructure Admin, I want multi-cluster IP partitioning
  so that VMs on different hosting clusters sharing the same subnet
  don't get conflicting IP assignments.

* As a Cloud Infrastructure Admin, I want bridge connectivity validation
  after subnet creation so that networking issues are caught at
  provisioning time rather than at VM creation.

* As a Cloud Infrastructure Admin, I want the system to reject subnets
  using the 10.0.2.0/24 CIDR so that KubeVirt masquerade collisions are
  prevented.

* As a Tenant User, I want VMs on a CUDN LocalNet subnet to be
  reachable from bare-metal servers and other clusters on the same
  fabric segment with L2 adjacency.

### Goals

- Bridge KubeVirt VMs to the physical fabric using CUDN Localnet
  topology with VLAN tagging, requiring no BGP, FRR-K8s, or VXLAN
  on the OCP side.
- Support multi-cluster deployments with IP range partitioning via
  `excludeSubnets` to prevent OVN IPAM collisions.
- Validate bridge connectivity after subnet creation.
- Guard against the 10.0.2.0/24 masquerade subnet collision.
- Provide L2 adjacency for VMs on the same virtual network across
  clusters.

### Non-Goals

- OVN EVPN, VRF-lite, or DPU-based bridging (future k8sManager
  implementations).
- Primary network CUDNs (Localnet is secondary only).
- NMState Operator installation (prerequisite, not managed by OSAC).
- Cross-subnet L3 routing automation (manual routes required on VMs for
  cross-virtual-network traffic within the same VPC/VRF).

## Proposal

### How It Works

Instead of tunneling (EVPN/VXLAN from the OCP node), localnet uses raw
802.1Q VLAN tags on the physical wire:

1. The fabric manager creates a virtual network with a VLAN ID.
2. The server's switch port trunks that VLAN alongside the existing
   management traffic.
3. On OCP, a CUDN with Localnet topology maps to br-ex via
   bridge-mappings, specifying the same VLAN ID.
4. OVN inserts/strips the VLAN tag at the br-ex port level.
5. Tagged frames exit the physical NIC, reach the leaf switch, get
   mapped to the fabric overlay (e.g., VXLAN/EVPN between switches),
   and are delivered to other ports on the same network.

VMs appear on the fabric virtual network as if they were bare-metal
servers on a tagged switch port. The fabric handles all inter-switch
forwarding via its native control plane. The OCP cluster doesn't need
to know anything about the fabric overlay.

The physical NIC on br-ex carries everything as a trunk. The leaf switch
differentiates traffic by VLAN tag. When multiple virtual networks are
assigned to the same port, each gets its own tagged VLAN. A single
switch port can carry the management network (native/untagged) plus many
tenant VLANs simultaneously.

### Workflow Description

**Cloud Infrastructure Admin** is a human user responsible for
configuring the fabric and OSAC networking.

**Tenant User** is a human user who creates VMs on provisioned subnets.

#### Subnet Provisioning (Admin)

1. The admin creates a VirtualNetwork in OSAC with a VLAN ID.
2. The fabric manager creates the corresponding virtual network on the
   physical fabric with the VLAN ID, adds switch port trunk membership,
   and sets an anycast/distributed gateway. DHCP is disabled (OVN IPAM
   handles IP assignment).
3. The k8s manager (CUDN LocalNet) runs an Ansible role that:
   a. Creates a namespace with the appropriate label.
   b. Applies an NNCP to add bridge-mappings (`localnet-physnet:br-ex`)
      on all worker nodes of the hosting cluster.
   c. Creates a CUDN with Localnet topology, matching the fabric VLAN
      ID and subnet CIDR.
   d. Configures `excludeSubnets` for multi-cluster IP partitioning.
4. The k8s manager validates that the bridge-mapping was applied and the
   CUDN reports `NetworkCreated: True`.

#### VM Creation (Tenant)

1. The tenant creates a ComputeInstance in OSAC, specifying the subnet.
2. OSAC creates a KubeVirt VM with two interfaces:
   - **default**: pod network (masquerade) for Kubernetes health probes.
   - **fabric**: the localnet CUDN for fabric connectivity.
3. OVN IPAM assigns an IP from the subnet range (respecting
   `excludeSubnets`).
4. The VM is reachable from the fabric with L2 adjacency.

#### SSH Access via Jump Pods

`virtctl ssh` connects via the pod network, which breaks if the VM's
default route is modified. Instead, a jump pod on the localnet provides
SSH access:

1. A jump pod is created in the same namespace with a multus annotation
   for the localnet network.
2. The user copies their SSH key into the jump pod and connects to VMs
   via their fabric IP.

### API Extensions

This enhancement does not introduce new CRDs. It implements a
k8sManager backend that operates on existing OCP resources:

- **NodeNetworkConfigurationPolicy (NNCP)**: Created by the k8s manager
  to add bridge-mappings on worker nodes.
- **ClusterUserDefinedNetwork (CUDN)**: Created by the k8s manager with
  Localnet topology, VLAN ID, subnets, and excludeSubnets.
- **Namespace**: Created with a label matching the CUDN's
  namespaceSelector.

The k8s manager is registered via a ConfigMap in the OSAC namespace,
referenced by the NetworkClass `k8sManager` field.

### Implementation Details/Notes/Constraints

#### Prerequisites

**Fabric Side:**
- Managed spine-leaf fabric with a controller (e.g., Netris, OpenStack).
- NAT gateway (e.g., SoftGate, Neutron router) for internet access.
- OCP nodes' physical NICs connected to leaf switch ports.
- Ability to create virtual networks with a VLAN ID, anycast gateway,
  switch port trunk membership, and DHCP disabled.

**OpenShift Side:**
- OpenShift 4.19+ (CUDN Localnet is GA in 4.19).
- OVN-Kubernetes as the CNI.
- NMState Operator installed.
- KubeVirt / OpenShift Virtualization for running VMs.

#### Bridge-Mappings (NNCP)

A bridge-mapping tells OVN-Kubernetes that the physical network named
`localnet-physnet` is reachable via the `br-ex` bridge:

```yaml
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: localnet-bridge-mapping
spec:
  nodeSelector:
    node-role.kubernetes.io/worker: ""
  desiredState:
    ovn:
      bridge-mappings:
        - localnet: localnet-physnet
          bridge: br-ex
          state: present
```

This is additive — it appends `localnet-physnet:br-ex` alongside the
existing `physnet:br-ex` mapping without modifying br-ex itself.

#### CUDN Configuration

Each virtual network gets a CUDN with Localnet topology. The VLAN ID
must match the fabric virtual network's VLAN:

```yaml
apiVersion: k8s.ovn.org/v1
kind: ClusterUserDefinedNetwork
metadata:
  name: tenant-alpha
spec:
  namespaceSelector:
    matchLabels:
      network: tenant-alpha
  network:
    topology: Localnet
    localnet:
      role: Secondary
      physicalNetworkName: localnet-physnet
      vlan:
        mode: Access
        access:
          id: 3
      subnets:
        - "10.0.1.0/24"
      excludeSubnets:
        - "10.0.1.0/32"
        - "10.0.1.1/32"
        - "10.0.1.255/32"
      ipam:
        mode: Enabled
        lifecycle: Persistent
```

#### Multi-Cluster IP Partitioning

When multiple clusters share the same virtual network, each cluster's
OVN IPAM allocates from the same subnet independently. Use
`excludeSubnets` to partition the range:

- **Cluster 1:** exclude `10.0.1.128/25` — allocates from 10.0.1.2–127
- **Cluster 2:** exclude `10.0.1.0/25` — allocates from 10.0.1.128–254

#### Masquerade Subnet Collision Guard

KubeVirt's masquerade interface always assigns 10.0.2.2/24 to VMs
internally on the default pod network interface (enp1s0). If a virtual
network uses the same subnet, both VM interfaces get IPs in 10.0.2.0/24,
breaking routing on the fabric interface. The k8s manager must reject
subnets overlapping with 10.0.2.0/24.

#### VM Configuration

Each VM gets two interfaces:
- **default**: pod network (masquerade) for Kubernetes health probes.
- **fabric**: the localnet CUDN for fabric connectivity.

```yaml
spec:
  template:
    spec:
      domain:
        devices:
          interfaces:
            - name: default
              masquerade: {}
            - name: fabric
              bridge: {}
      networks:
        - name: default
          pod: {}
        - name: fabric
          multus:
            networkName: tenant-alpha
```

#### CUDN Immutability

CUDNs cannot be modified after creation. Changes to VLAN ID, subnet, or
excludeSubnets require deleting the CUDN and recreating it. VMs must be
deleted first since the CUDN controller blocks deletion while workloads
are attached.

### Connectivity Model

Traffic behavior depends on virtual network placement:

| Virtual network placement | L2 (same subnet) | L3 (cross-subnet) |
|---|---|---|
| Same virtual network, same cluster | Direct switching within OVN (TTL=64) | N/A |
| Same virtual network, cross-cluster | L2 via fabric (TTL=64) | N/A |
| Different virtual networks, same VPC/VRF | No (different VLAN) | Routed via fabric gateway (TTL=63) — requires manual routes on VMs |
| Different virtual networks, different VPCs/VRFs | No | No (VRF isolation) |

For L3 routing between virtual networks in the same VPC/VRF, VMs need
explicit routes via the fabric gateway:

```bash
# On a VM in Alpha (10.0.1.0/24), to reach Beta (10.0.3.0/24):
sudo ip route add 10.0.3.0/24 via 10.0.1.1 dev enp2s0
```

#### SNAT via Fabric

VMs can access the internet through the fabric (not through the pod
network) by adding a default route via the fabric gateway. This uses the
fabric SNAT IP rather than the OVN masquerade IP, confirming two
distinct traffic paths.

### Comparison with Alternatives

| | Localnet (this EP) | EVPN | VRF-Lite |
|---|---|---|---|
| **OCP version** | 4.19+ | 4.22+ (TechPreview) | 4.19+ |
| **Fabric integration** | VLAN tags on wire | VXLAN tunnel from node | BGP route exchange |
| **FRR-K8s required** | No | Yes | Yes |
| **BGP peering** | No (fabric-only) | Node-to-Leaf EVPN | Node-to-Router VRF |
| **VM visibility** | Fabric sees VLAN, not individual MACs | Fabric sees VM MAC+IP via EVPN Type 2 | Fabric sees pod subnet via BGP |
| **VM network role** | Secondary | Primary | Primary |
| **L3 cross-subnet** | Manual routes on VMs | Automatic (OVN routing) | Automatic (BGP routing) |
| **Complexity** | Low | High | Medium |
| **BM + VM same segment** | Yes (same VLAN) | Yes (same VNI/EVPN) | No (separate routing) |

**Localnet** is the simplest option — use when VMs need fabric connectivity
without any control-plane integration on the OCP side.

**EVPN** is the most capable — use when per-VM MAC/IP visibility in the
fabric routing table, direct DNAT, or EVPN-based network services are
needed. Requires OCP 4.22+ and FRR-K8s.

**VRF-Lite** — use for routed (L3) connectivity between OCP pods/VMs and
an external router with per-tenant VRF isolation.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| CUDN immutability forces delete/recreate for config changes | Document the workflow; k8s manager handles teardown and recreation |
| IP collisions in multi-cluster deployments | `excludeSubnets` partitioning enforced by the k8s manager |
| Masquerade subnet collision (10.0.2.0/24) | k8s manager validates and rejects conflicting CIDRs |
| Same-node traffic bypasses fabric ACLs | Document as known limitation; fabric ACLs only apply to traffic that leaves the node |
| NNCP bridge-mapping destructive bug (OCPBUGS-18869) | Fixed in OCP 4.15+; minimum version requirement is 4.19 |
| Upgrade connectivity loss (OCPBUGS-66994) | Workaround: restart ovnkube-node pod or live-migrate affected VM |

### Drawbacks

- **Secondary network only**: VMs have two interfaces — the pod network
  for Kubernetes health probes and the fabric interface for tenant
  traffic. This dual-interface setup requires explicit routes for
  cross-subnet traffic via the fabric and careful default route
  management.

- **No per-VM fabric visibility**: Unlike EVPN, the fabric doesn't
  learn individual VM MAC addresses via control plane. MAC learning
  happens via data-plane flooding.

- **VLAN scale limit**: Each virtual network consumes a VLAN ID
  (1–4094). EVPN uses 24-bit VNIs (16M segments).

- **Manual IP coordination**: Cross-cluster deployments require manual
  IP range partitioning via `excludeSubnets`. No cross-cluster IPAM.

- **Same-node traffic isolation gap**: VM-to-VM traffic on the same node
  stays within OVN and never hits the fabric, so fabric ACLs don't
  apply.

## Alternatives (Not Implemented)

- **EVPN (OVN EVPN with FRR-K8s)**: Provides per-VM MAC/IP visibility
  in the fabric routing table and automatic L3 cross-subnet routing.
  Not chosen as the first k8sManager because it requires OCP 4.22+
  (TechPreview), FRR-K8s, and EVPN BGP peering configuration —
  significantly higher complexity. Planned as a future k8sManager
  implementation.

- **VRF-Lite (FRR-K8s with BGP VRF)**: Provides routed L3 connectivity
  with per-tenant VRF isolation. Not chosen because it does not provide
  L2 adjacency between VMs and bare-metal servers on the same fabric
  segment, and requires FRR-K8s with per-tenant VLAN+VRF configuration.

- **DPU-based bridging**: Hardware-accelerated bridging via Data
  Processing Units. Not chosen due to hardware requirements and early
  maturity. Potential future enhancement.

## Test Plan

Testing was performed with 2 SNO clusters on a managed fabric, 2
virtual networks (Alpha on VLAN 3, Beta on VLAN 5), 4 VMs total.

### Test Environment

```
Cluster 1 (OCP 4.22):
  vm-alpha  → Virtual Network Alpha (VLAN 3)  → fabric IP: 10.0.1.6
  vm-beta   → Virtual Network Beta  (VLAN 5)  → fabric IP: 10.0.3.2

Cluster 2 (OCP 4.21):
  vm-alpha  → Virtual Network Alpha (VLAN 3)  → fabric IP: 10.0.1.128
  vm-beta   → Virtual Network Beta  (VLAN 5)  → fabric IP: 10.0.3.128
```

### Test Matrix

| From | To | Scenario | Expected | Result |
|------|----|----------|----------|--------|
| vm-alpha C1 | vm-alpha C1-2 | Same vnet, same cluster | L2 OK (TTL=64) | **PASS** |
| vm-alpha C1 | vm-alpha C2 | Same vnet, cross-cluster | L2 OK (TTL=64) | **PASS** |
| vm-beta C2 | vm-beta C1 | Same vnet, cross-cluster | L2 OK (TTL=64) | **PASS** |
| vm-alpha C1 | vm-beta C1 | Diff vnet, same VPC, same cluster | L3 OK (TTL=63) with routes | **PASS** |
| vm-alpha C1 | vm-beta C1 | Diff vnet, diff VPC, same cluster | Isolated | **PASS** |
| vm-alpha C1 | vm-beta C2 | Diff vnet, diff VPC, cross-cluster | Isolated | **PASS** |
| vm-beta C2 | vm-alpha C1 | Diff vnet, diff VPC, cross-cluster | Isolated | **PASS** |
| vm-alpha C1 | Beta GW | Diff vnet, diff VPC | Isolated | **PASS** |
| vm-alpha C1 | Internet (fabric) | SNAT | Fabric public IP | **PASS** |

### E2E Test Strategy

- Unit tests for subnet validation (masquerade collision guard,
  excludeSubnets calculation).
- Integration tests for the Ansible role: NNCP creation, CUDN creation,
  bridge-mapping validation.
- E2E tests on a fabric-connected cluster: VM creation, L2 connectivity
  within and across clusters, VRF isolation verification.

## Graduation Criteria

- **Dev Preview**: Ansible role for CUDN LocalNet provisioning, tested
  manually on a single fabric-connected cluster.
- **Tech Preview**: Multi-cluster IP partitioning, bridge connectivity
  validation, masquerade guard, automated E2E tests.
- **GA**: Production-hardened with upgrade testing, documented
  troubleshooting procedures, and support for multiple fabric
  controllers.

## Upgrade / Downgrade Strategy

The k8s manager creates standard Kubernetes resources (NNCP, CUDN,
Namespace). Upgrades to the k8s manager Ansible role do not affect
existing resources. CUDNs are immutable — any configuration changes
require delete/recreate regardless of upgrade path.

For OCP upgrades:
- CUDN Localnet is GA in OCP 4.19+. Upgrades within 4.19+ are
  transparent.
- Known connectivity loss during upgrades (OCPBUGS-66994): restart
  ovnkube-node pod or live-migrate affected VMs.

Downgrade: remove the CUDN and NNCP resources. VMs must be deleted
before removing the CUDN.

## Version Skew Strategy

The k8s manager operates on stable OCP APIs (NMState v1, CUDN v1).
Version skew between the k8s manager and OCP is handled by the minimum
OCP version requirement (4.19+). The Ansible role checks for NMState
Operator availability before applying NNCPs.

## Support Procedures

- **Bridge-mapping not applied**: Check NNCP status
  (`oc get nncp localnet-bridge-mapping -o yaml`). Verify OVS
  external_ids contain the bridge-mapping
  (`ovs-vsctl get open_vswitch . external_ids:ovn-bridge-mappings`).

- **CUDN not ready**: Check CUDN status conditions
  (`oc get clusteruserdefinednetwork <name> -o yaml`). Common issue:
  `physicalNetworkName` doesn't match any bridge-mapping.

- **VM has no fabric IP**: Verify namespace label matches CUDN selector,
  NAD exists in namespace, and IPAM is enabled. Check guest agent via
  `virsh domifaddr`.

- **Both VM interfaces show same subnet**: Masquerade collision —
  change the virtual network subnet to avoid 10.0.2.0/24.

- **Cross-cluster VMs unreachable**: Verify both clusters use the same
  VLAN ID, fabric virtual network includes both clusters' switch ports,
  and check OVS flow rules (`ovs-ofctl dump-flows br-ex`).

- **virtctl ssh timeout**: Likely caused by a fabric default route
  (metric 50) redirecting return SSH traffic. Use jump pods instead.

### Known Issues

- **OCPBUGS-43004**: Same-node connectivity issue in OCP < 4.19. Fixed
  in 4.19+.
- **OCPBUGS-18869**: NNCP bridge-mapping destructive bug in OCP 4.14.
  Fixed in 4.15+.
- **OCPBUGS-66994**: Upgrade connectivity loss. Workaround: restart
  ovnkube-node or live-migrate.

## Infrastructure Needed

- Access to a managed spine-leaf fabric with a controller (e.g., Netris)
  for E2E testing.
- At least 2 OCP clusters (4.19+) connected to the fabric for
  multi-cluster testing.
- CI integration for the Ansible role in osac-aap.
