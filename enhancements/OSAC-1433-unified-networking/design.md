---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-09-24
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - BareMetal Instance API: /enhancements/OSAC-1118-baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
  - VMaaS Networking: /enhancements/OSAC-1435-vmaas-networking
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - BMaaS Networking: /enhancements/OSAC-1437-bmaas-networking
  - Default Networking: /enhancements/OSAC-1433-default-networking
replaces:
  - OSAC-356 Networking API (legacy)
superseded-by:
  - N/A
---

# Unified Networking API for VMaaS, CaaS, and BMaaS

## Summary

This document describes the technical design for the OSAC unified
networking architecture. For the problem statement and requirements,
see the companion [Requirements Document (PRD)](prd.md).

### Deployment Support Boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected networking deployments are outside the supported
boundary and must not be advertised as supported profiles. A connected
deployment has reachability among the provider-owned hub, selected network
managers, provider-controlled networking services, and provider-controlled
address infrastructure. The provider owns this configuration; connectivity is
not tenant selectable, and these reachability prerequisites must hold before
the deployment's NetworkClass is accepted. The boundary applies to
Fabric-only, K8s-only, and combined manager profiles.

### Networking Hub Support Boundary

OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

OSAC runs VMs on OpenShift using KubeVirt, which encapsulates each VM in a
pod. Pod networking is managed by OVN-Kubernetes, meaning VMs live inside an
OVN overlay that is not directly visible on the physical fabric. The core
premise of this design is that **VMs are part of the fabric**. Through a
[K8s manager](#how-vms-join-the-fabric) that bridges the OVN overlay to the
physical network, VMs become first-class participants in the fabric alongside
bare-metal servers and cluster nodes. Once on the fabric, all resource types
are treated uniformly — the fabric manager handles isolation, security, IP
allocation, DNAT, and SNAT for everything.

The design introduces:

- **NetworkClass** with two fields: `fabricManager` (handles all physical
  networking) and optional `k8sManager` (bridges VMs to the fabric)
- **Infrastructure-agnostic subnets** where the same subnet can host VMs,
  BM servers, and cluster nodes
- **ExternalIP** (renamed from PublicIP) to clarify that addresses are
  external to the VirtualNetwork, not necessarily internet-routable
- **Uniform API** where the same networking resources (VirtualNetwork,
  Subnet, NetworkACL, ExternalIP, ExternalIPAttachment, NATGateway)
  serve VMaaS, CaaS, and BMaaS identically

The BMaaS integration is based on the `BaremetalInstance` resource defined in
the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api),
which provides a per-server resource aligned with ComputeInstance.

All networking resources and manager integrations in this design use IPv4.
IPv6 and dual-stack networking are not supported.

> **Implementation status:** This is the normative target contract. Current
> proto/CRD schemas and allocation paths still contain legacy IPv6/dual-stack
> support; implementation work must enforce this contract before rollout.

For user stories, goals, and non-goals, see the
[Requirements Document (PRD)](prd.md).

### API operation constraint

Networking resources support read, create, and delete; read includes `List`
and `Get`. NetworkACL rules and the Subnet's required `spec.network_acl`
association are immutable after creation. Changing policy or association
requires recreating the affected resources. NetworkACL identity,
VirtualNetwork scope, metadata, and other networking resource fields remain
immutable after creation. VirtualNetwork and Subnet address configuration and
workload network attachments are create-time-only. Controllers may update
status, conditions, readiness, and IP-discovery fields during reconciliation;
these internal writes are not additional tenant API operations. This is the
normative contract for the VMaaS, CaaS, and BMaaS designs that reference this
document.

## Proposal

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for the deployment. Tenants never interact with it. One
NetworkClass per deployment.

#### Two Managers

OSAC networking is handled by two managers:

- **Fabric Manager** — one configured implementation that manages
  all physical networking: tenant isolation, ACLs, IP allocation, DNAT, SNAT,
  and inter-subnet L3 routing within a VirtualNetwork. The physical fabric is
  one infrastructure — one controller manages it all. When a VN has multiple
  subnets, the fabric manager provides the L3 gateway for each subnet and
  routes between them automatically.

- **K8s Manager** (optional) — handles everything needed to make VMs part of
  the fabric: creates the K8s overlay (e.g., CUDN with LocalNet) and bridges
  it to the fabric segment. Needed for deployments that host VMs — once VMs
  are on the fabric, the fabric manager handles them identically to
  bare-metal servers. MetalLB IPAddressPool CRs for CaaS VIP allocation are
  created by the Subnet controller at subnet creation time (gated on
  `NetworkClass.spec.vip_prefix_length`), independent of the k8sManager.

#### Why Two Managers?

The physical network is managed as one provider-configured system. Splitting
its operations among independent per-action drivers creates inconsistent
ownership and validation. A single
`fabricManager` field captures this reality.

The K8s side is a separate concern: it bridges the OVN overlay to the
physical fabric. The mechanism depends on the deployment — see
[How VMs Join the Fabric](#how-vms-join-the-fabric) for the available
options. The goal is always the same: make VMs part of the fabric. A single
`k8sManager` field captures this.

Once VMs are on the fabric, the fabric manager handles everything for all
resource types uniformly. There is no VM-vs-BM distinction for security,
ExternalIP, DNAT, or SNAT.

#### NetworkClass Examples

**Fabric manager + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: moc-region-1
spec:
  fabricManager: fabric-manager
  k8sManager: cudn_localnet
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

**BM-only deployment (no VMs):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: gpu-region-1
spec:
  fabricManager: fabric-manager
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

#### Capabilities

Capabilities are **inferred from the assigned managers** and published in
the NetworkClass `capabilities` field — the provider does not set them
manually. The operator computes the intersection of capabilities declared by
the assigned manager ConfigMaps and populates `capabilities` automatically. For
a BM-only NetworkClass without a `k8sManager`, the absent manager is excluded
from this intersection; only the configured `fabricManager` contributes
capabilities.

The supported deployment boundary is IPv4-only. Managers must advertise the
`ipv4` capability. IPv6 and dual-stack manager registrations are rejected,
and NetworkClass capability output must be `supportsIpv4: true` with
`supportsIpv6: false` and `supportsDualStack: false`.

| Capability | Type | Meaning |
|-----------|------|---------|
| `supportsIpv4` | bool | IPv4 addressing is available; `true` for OSAC networking |
| `supportsIpv6` | bool | IPv6 addressing; always `false` |
| `supportsDualStack` | bool | IPv4 + IPv6 addressing; always `false` |
| `dpuSupport` | bool | DPU-accelerated networking available |

The set of capabilities is defined by the operator and is fixed — adding a
new capability requires an operator update. Managers declare which
capabilities they support; they cannot define custom capabilities.

#### Manager Registration (ConfigMap)

Each manager ships a ConfigMap declaring its type and capabilities. These
ConfigMaps are deployed as part of the OSAC installation alongside the
manager's Ansible roles.

**Fabric managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fabric-manager-example
  namespace: osac
  labels:
    osac.openshift.io/network-fabric-manager: "true"
data:
  name: fabric-manager
  description: "Tenant isolation, network ACLs, IP allocation, and address translation"
  capabilities: "ipv4"
```

**K8s managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-cudn-localnet
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: cudn_localnet
  description: "CUDN with LocalNet — bridges OVN overlay to physical fabric"
  capabilities: "ipv4"
```

The operator discovers managers by listing ConfigMaps with the appropriate
labels. When a NetworkClass is created, the operator validates each manager
assignment against the corresponding ConfigMap. Adding a new manager means
deploying a new ConfigMap and Ansible role — no API or operator changes
needed.

### How VMs Join the Fabric

OSAC runs VMs on OpenShift using KubeVirt. Each VM is encapsulated in a pod
whose networking is managed by OVN-Kubernetes. By default, VM IP addresses
exist only within the OVN overlay and are not visible on the physical
fabric. The k8sManager bridges this overlay to the fabric so that VMs
become first-class fabric participants — reachable at their subnet IP from
any other resource on the same fabric segment.

Several mechanisms can achieve this bridging. The k8sManager is pluggable —
different deployments use different mechanisms depending on their
infrastructure and requirements:

**CUDN with LocalNet.** The k8sManager creates a ClusterUserDefinedNetwork
(CUDN) with LocalNet topology, mapping the OVN network directly to a
physical VLAN on the hosting cluster's trunk interface. VMs in this network
are bridged to the fabric at L2 — they share a broadcast domain with
bare-metal servers on the same VLAN. This is the simplest mechanism and
provides full L2 adjacency.

**OVN EVPN.** OVN advertises VM routes to the fabric via BGP EVPN. The
fabric learns VM MAC/IP bindings and can route to them. VMs remain in the
OVN overlay but are reachable from the fabric at L3. This preserves OVN's
per-VM isolation on the same hypervisor while still making VMs fabric
participants. Note: OVN EVPN is not yet GA in OpenShift.

**CUDN with VRF-lite.** The hosting cluster uses VRF (Virtual Routing and
Forwarding) instances to route between the OVN overlay and the fabric. Each
tenant VN maps to a VRF on the host, which peers with the fabric via BGP.
VMs are reachable from the fabric via L3 routing through the VRF. See the
[CUDN with VRF-lite setup guide](/docs/networking/setup-bpg-vrf-lite) for
a working example.

**DPU-based bridging.** SmartNICs (DPUs) offload the OVN-to-fabric bridging
to hardware. The DPU handles packet encapsulation/decapsulation between OVN
and the physical network, providing line-rate bridging without host CPU
overhead.

The choice of mechanism is transparent to tenants — it is configured by the
provider as part of the k8sManager installation. The networking API and
resource model are identical regardless of which mechanism is used. All that
matters is the contract: once the k8sManager has bridged a subnet, VMs on
that subnet are reachable from the fabric at their subnet IP.

### Infrastructure-Agnostic Subnets

VirtualNetwork and Subnet do not carry a scope or service field. Subnets are
infrastructure-agnostic — the dispatcher provisions both the fabric segment
and (if the NetworkClass has a k8sManager) the K8s overlay for every subnet.
Any resource type can be placed on any subnet.

At subnet creation, the dispatcher runs:

1. **Fabric manager** — creates fabric segment (e.g., VLAN, VPC)
2. **K8s manager** (if present) — creates K8s overlay on each hosting
   cluster in the deployment and bridges it to the fabric segment

VMs are placed in the K8s overlay (which is bridged to the fabric), BM
servers and cluster nodes are placed directly on the fabric segment. The
fabric is the single source of truth for multi-tenancy and routing — all
resources, regardless of type, are on the fabric.

### Dispatcher (Operator Composition Logic)

The osac-operator acts as a **dispatcher**: when reconciling any networking
resource, it resolves the NetworkClass and calls the
appropriate managers. Each manager corresponds to an Ansible role — the
dispatcher triggers the appropriate AAP playbook, passing the resource and
context as the event payload.

| Operation | Managers called |
|-----------|----------------|
| VN create/delete | `fabricManager` |
| Subnet create/delete | `fabricManager` + `k8sManager` (per hosting cluster) |
| NetworkACL create/delete | `fabricManager` |
| ExternalIP alloc/release | `fabricManager` |
| ExternalIPAttachment create/delete | `fabricManager` |
| NATGateway create/delete | `fabricManager` |

Everything except subnet creation is handled by the fabric manager alone.
The k8sManager is only involved at subnet creation (to bridge the overlay)
— after that, VMs are on the fabric and the fabric manager handles them
like any other resource.

The dispatch table above covers **networking resources only**. Compute
resources (ComputeInstance, BaremetalInstance, Cluster) handle per-instance
network attachment through their provisioning operators — see per-service
designs at [VMaaS](/enhancements/OSAC-1435-vmaas-networking),
[CaaS](/enhancements/OSAC-1436-caas-networking),
[BMaaS](/enhancements/OSAC-1437-bmaas-networking).

### Resource Hierarchy

```text
NetworkClass (per deployment, provider-only)

VirtualNetwork (tenant-managed, infrastructure-agnostic)
  ├── NetworkACL          → fabricManager
  ├── Subnet              → fabricManager + k8sManager
  │     └── one NetworkACL association
  └── NATGateway          → fabricManager

ExternalIPPool (deployment-scoped, provider-managed)
  └── ExternalIP (tenant-managed) → fabricManager

ExternalIPAttachment (tenant-managed)
                          → fabricManager
                            references an ExternalIP and a target resource
```

### NetworkACL — Stateless Subnet Policy

`NetworkACL` is a tenant-managed resource scoped to one VirtualNetwork. It
contains ordered ingress and egress rules. A Subnet references exactly one
NetworkACL in its parent VirtualNetwork; an ACL can be reused by multiple
Subnets in that VirtualNetwork. The policy is enforced at the Subnet boundary
and applies uniformly to every workload attached to the Subnet. [PRD: FR-2,
FR-4]

Each direction is evaluated independently. Rules are sorted by ascending
priority, where `1` is evaluated first and `32766` last. Priorities must be
unique within an ingress list or an egress list. The first matching rule
decides the packet: `ALLOW` permits it and `DENY` drops it. If no rule matches,
the packet is denied. Because the ACL is stateless, reply packets need their
own matching rule in the reverse direction. [Locked: D2]

For ingress rules, `ipv4_cidr` matches the packet source address; for egress
rules it matches the destination address. A rule may match any supported
protocol or a specific protocol. TCP and UDP rules may include a destination
port range; when omitted, the rule matches all destination ports for that
protocol. A port range is invalid for other protocols. CIDRs are canonical
IPv4. [PRD: FR-2]

Traffic between workloads on the same Subnet is not filtered by that Subnet's
NetworkACL. Traffic crossing Subnet boundaries is evaluated twice: first by
the source Subnet's egress rules, then by the destination Subnet's ingress
rules. Both decisions must allow the packet. [Locked: D4]

```protobuf
message NetworkACLSpec {
  VirtualNetworkLocalReference virtual_network = 1; // required, immutable
  repeated NetworkACLRule ingress = 2;              // immutable after creation
  repeated NetworkACLRule egress = 3;               // immutable after creation
}

message NetworkACLRule {
  NetworkACLAction action = 1;       // ALLOW or DENY
  uint32 priority = 2;               // unique per direction, 1..32766
  Protocol protocol = 3;             // ALL, TCP, UDP, or ICMP
  optional int32 port_from = 4;      // optional; TCP/UDP only
  optional int32 port_to = 5;        // optional; TCP/UDP only
  string ipv4_cidr = 6;              // ingress source or egress destination
}

message SubnetSpec {
  VirtualNetworkLocalReference virtual_network = 1; // required, immutable
  string ipv4_cidr = 2;                             // required, immutable
  NetworkACLLocalReference network_acl = 3;          // required, immutable
}
```

The schema sketch shows the tenant-facing resource relationship. The
`network_acl` reference is required at Subnet creation and is immutable after
creation. There is never more than one active ACL association for a Subnet.
ACL rule lists are also immutable after creation. An ACL cannot be deleted
while a Subnet references it, and the ACL's VirtualNetwork scope cannot be
changed. Changing policy requires recreating the affected networking resources.

### NetworkACL API and Validation

The public `NetworkACLs` service provides `List`, `Get`, `Create`, and `Delete`
at `/api/fulfillment/v1/network_acls`. The public `Subnets` service provides
`List`, `Get`, `Create`, and `Delete`; the required `spec.network_acl` reference
is supplied at creation. Neither service exposes `Update`. `NetworkACL`
creation requires a READY parent VirtualNetwork, and Subnet creation must
reference a READY NetworkACL in the same VirtualNetwork.

Validation rejects duplicate priorities within a direction, priorities
outside 1..32766, unknown actions or protocols, incomplete or reversed port
ranges, port ranges with non-TCP/UDP protocols, malformed or non-canonical
IPv4 CIDRs, and references across VirtualNetworks. Rule priority order is
direction-local, so the same number can appear once in ingress and once in
egress. For TCP/UDP, either both port endpoints are supplied or neither is;
an omitted range matches all destination ports for that protocol. [PRD:
FR-2, FR-4]

The current deployment-level ACL policy is hard-coded to permit all traffic.
That deployment policy is separate from tenant-managed NetworkACL rules and
from the tenant default ACL provisioned at onboarding. Tenant default ACL
behavior is deny-by-default for ingress and permit-by-default for egress; the
stateless tenant ACL still requires explicit reverse-direction ingress rules
for any egress replies that must pass.

Creating a tenant-managed NetworkACL does not seed default rules. An ACL with
empty ingress and egress lists denies all traffic that reaches its Subnet
boundary; users must provide every required flow, including reverse-direction
rules for replies. The tenant default ACL policy is materialized separately by
default networking.

Deleting a NetworkACL that is associated with one or more Subnets fails with
`FAILED_PRECONDITION`. Deleting a VirtualNetwork is blocked until its Subnets,
NetworkACLs, and NATGateway have been removed. ACL rule lists and the Subnet
association are fixed at creation; neither resource exposes an Update method.
To change policy, delete dependent Subnets and the ACL, then recreate them with
the desired rule set and association. A Subnet remains Pending until its
network segment and its associated ACL policy are active.

### ExternalIPPool

"External" in ExternalIPPool/ExternalIP means **external to the
VirtualNetwork**. In the supported connected deployment boundary, the
provider creates pools with addresses routable in the provider's connected
network. The API does not require Internet reachability, but air-gapped and
disconnected networking deployments are not supported.

ExternalIPPools are provider-managed and deployment-scoped. The fabric
manager handles ExternalIP allocation — one pool serves all resource types.
Each pool uses exactly one canonical IPv4 CIDR. The API's repeated `cidrs`
field is retained for compatibility, but validation rejects an empty list or
more than one entry; IPv6 and dual-stack pools are not supported.
Pool creation requires `spec.ipFamily` to be `IP_FAMILY_IPV4`;
`IP_FAMILY_UNSPECIFIED`, IPv6, and dual-stack values are rejected before
persistence.

#### Address-Family and CIDR Contract

All user-supplied network CIDRs use canonical dotted-decimal IPv4 notation
(`a.b.c.d/prefix`) with host bits zero. A Subnet CIDR must be contained by its
parent VirtualNetwork and sibling Subnet CIDRs must not overlap. Provider and
controller-produced addresses are canonical IPv4 addresses without a CIDR
suffix. Any IPv6, dual-stack, malformed, or non-canonical value is rejected
before persistence or backend dispatch.
All explicit and automatic ExternalIP allocation paths, including per-service
auto-provisioning, must request `IP_FAMILY_IPV4`; `IP_FAMILY_UNSPECIFIED` is
not a valid default for this contract.

### End-to-End Flows

This section shows how the unified networking API works from the tenant's
perspective. The flows are the same regardless of which fabric manager or
K8s manager the provider has deployed.

#### Provider Setup

1. Provider deploys hosting cluster(s) and fabric controller
2. Provider creates NetworkClass for the deployment (provider-only,
   tenants never see it)
3. Provider creates ExternalIPPool:

```bash
osac admin create externalippool \
  --network-class moc-region-1 \
  --cidrs 203.0.113.0/24 \
  --ip-family ipv4 \
  --name external-pool-1
```

The fabric manager registers the IP range in its IPAM for allocation.

#### Networking Setup (Same for All Resource Types)

The tenant creates networking resources. This workflow is identical
regardless of whether the tenant plans to run VMs, clusters, or bare-metal
servers.

**Create VirtualNetwork:**

```bash
osac create virtualnetwork --network-class moc-region-1 --cidr 10.0.0.0/16 \
  --name my-net
```

The fabric manager creates an isolated tenant segment on the fabric.

**Create NetworkACL:**

```bash
osac create network-acl --virtual-network my-net --name web-acl \
  --ingress-rule "action=ALLOW,priority=100,protocol=TCP,ports=443,cidr=198.51.100.0/24" \
  --ingress-rule "action=ALLOW,priority=110,protocol=TCP,ports=1024-65535,cidr=203.0.113.0/24" \
  --egress-rule "action=ALLOW,priority=100,protocol=TCP,ports=443,cidr=203.0.113.0/24" \
  --egress-rule "action=ALLOW,priority=110,protocol=TCP,ports=1024-65535,cidr=198.51.100.0/24"
```

The example allows HTTPS from the illustrative client range and to the
illustrative external endpoint range. The higher destination-port rules allow
the corresponding replies in each reverse direction. These documentation
CIDRs must be replaced with the deployment's actual trusted client and
endpoint ranges. Rules are stateless: omitting either reverse rule blocks that
flow's replies.

**Create Subnet and associate the ACL:**

```bash
osac create subnet --virtual-network my-net --network-acl web-acl \
  --cidr 10.0.1.0/24 --name my-subnet
```

The fabric manager creates the network segment and installs the Subnet's ACL
policy. If the NetworkClass has a K8s manager, it also creates an overlay on
each hosting cluster and bridges it to the segment. VMs on that overlay and
bare-metal servers on the segment share the same Subnet policy.

#### Resource Creation (Differs by Type)

The networking setup above is shared. Only the resource creation step
differs internally — the tenant CLI experience is the same for all types.

**ComputeInstance (VM):**

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet \
  --name my-vm
```

VM is placed in the K8s overlay namespace on a hosting cluster. Because the
overlay is bridged to the fabric, the VM is directly on the fabric segment
and gets an IP from the subnet CIDR.

**BaremetalInstance:**

Bare-metal servers have multiple physical interfaces. The tenant discovers
available network ports via the BareMetalInstanceType API — each
BareMetalInstanceType lists its network ports with name, role, type, speed,
and description (see
[HostType and BareMetalInstanceType](#hosttype-and-baremetalinstancetype)). Given the port identifiers, the tenant specifies which
interface to attach to the subnet. The current BMaaS contract accepts one
entry in the repeated `network_attachments` field, mapping one physical
interface to one subnet. If `interface` is omitted, fulfillment defaults to
the first `fabric` port from `BareMetalInstanceType.network_ports`.

Single interface (simple case):

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=my-subnet \
  --name my-server
```

The API retains the repeated field for compatibility, but only one attachment
is supported. The fabric manager configures the selected host switch port on
the corresponding fabric segment and the interface gets an IP from the
subnet's CIDR.

Validation rules:
- At most one attachment is accepted
- All referenced subnets must belong to the same VirtualNetwork
- The `interface` must reference a valid port name from the BareMetalInstanceType's
  network ports list

**Cluster:**

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet \
  --node-set workers=large,size=3 --name my-cluster
```

For v0.2, **CaaS supports BM node sets only**. VM-based cluster node sets
are architecturally possible but deferred. The fulfillment-service resolves
the interface from the BareMetalInstanceType (`fabric_interface` — first port
with role `fabric`) and stores it on the node set. The worker controller passes
that stored value to BMaaS; BMaaS handles the host's network attachment as part
of its provisioning lifecycle.
See [CaaS Networking](/enhancements/OSAC-1436-caas-networking) for the detailed flow.

Cluster nodes have multiple physical interfaces. Unlike BaremetalInstance
(where the tenant specifies interfaces directly), for clusters the
**system** resolves the interface from each node set's BareMetalInstanceType
`network_ports` list.
The tenant specifies which subnet to use (one per cluster); the system maps it to the
correct physical interfaces based on each node set's BareMetalInstanceType.

In all cases, the resource ends up on the fabric. The fabric manager sees
all resources equally — there is no VM-vs-BM distinction.

#### External Access (Same for All Resource Types)

Since all resources are on the fabric, external access operations are
uniform. There is no VM-vs-BM distinction — the fabric manager handles
DNAT and SNAT identically for all resource types.

**Allocate ExternalIP:**

```bash
osac create externalip --pool external-pool-1 --name my-ip
```

The fabric manager allocates an IP from its IPAM (e.g., 203.0.113.45).

**Attach for inbound access (DNAT):**

```bash
# Attach to a VM
osac create externalipattachment --externalip my-ip \
  --compute-instance my-vm --name vm-att

# Attach to a BM server (new target type)
osac create externalipattachment --externalip my-ip \
  --baremetal-instance my-server --name bm-att

# Attach to a cluster API server (new target type + endpoint)
osac create externalipattachment --externalip my-ip \
  --cluster my-cluster --target-endpoint api --name api-att
```

The fabric manager creates a DNAT rule: external IP → resource's subnet IP.
Each resource (ComputeInstance, BaremetalInstance) is associated with one
tenant subnet and has one fabric IP — the DNAT targets that IP directly. The
ExternalIP is attached to the resource, not to a specific interface; the
fabric manager routes to the resource's sole/primary subnet IP.

**Cluster ExternalIPAttachment flow:**

For VMs and BM, the DNAT target is the resource's fabric IP —
straightforward. For clusters, the DNAT target is a service-level VIP
(API server or ingress) that is discovered during cluster provisioning.
The VIP allocation is decoupled from the networking layer:

1. CaaS template creates MetalLB LoadBalancer Services for API server
   and ingress. MetalLB allocates VIPs from its IPAddressPool (created
   by k8s_manager at subnet creation).
2. Template discovers the allocated VIPs and writes them to ClusterOrder
   CR status (`apiEndpoint`, `ingressEndpoint`)
3. Feedback controller syncs VIPs to the Cluster object in the
   fulfillment service as `api_endpoint` and `ingress_endpoint` fields
4. ExternalIPAttachment controller reads the VIP from ClusterOrder
   status → calls fabric manager to create DNAT: external IP →
   internal VIP
5. ExternalIPAttachment transitions to Ready

The tenant can inspect the allocated VIPs:

```bash
osac get cluster my-cluster -o yaml
# api_endpoint: 10.0.5.20
# ingress_endpoint: 10.0.1.50
```

ExternalIPAttachments can be created before or after the cluster. If
created before (Pending state), the controller activates them once the
cluster's endpoint VIPs are available. If created after, the DNAT rule
is configured immediately.

**Auto-provisioning lifecycle (auto_external_ip_attachment):**

Auto ExternalIP attachment provisioning (described in per-service
EPs and [Default Networking](/enhancements/OSAC-1433-default-networking)) is a
two-phase process:

*Phase 1 — synchronous (during the create API call):*

The fulfillment-service validates pool capacity, creates ExternalIP and
ExternalIPAttachment records in PostgreSQL, and decrements pool capacity
— all within the same API transaction. If the pool is exhausted, the
call fails and no resources are persisted (including the parent
resource). Both the ExternalIP and ExternalIPAttachment start in
**Pending** state. The ExternalIPAttachment's target reference is set at
creation time, but the DNAT target IP may not yet be known (the target
resource may still be provisioning).

The fulfillment-service creates the ExternalIPAttachment with the
ExternalIP in Pending state (not yet Allocated). This bypasses the
normal ExternalIPAttachment server validation that requires the
ExternalIP to be Allocated — the auto-provisioning codepath in the
fulfillment-service creates both resources atomically within the same
transaction, so the Allocated check is not needed (the ExternalIP is
guaranteed to exist and will be reconciled by the operator).

*Phase 2 — asynchronous (controller reconciliation):*

Each resource type has an independent fulfillment-service reconciler.
The ExternalIP and ExternalIPAttachment CRs are pushed to the hub
cluster independently — there is no cross-resource ordering in the
reconcilers. The operator-side controllers handle ordering via
precondition checks and requeue:

- fulfillment-service reconcilers push ExternalIP and
  ExternalIPAttachment CRs to the hub cluster (independently, around
  the same time)
- osac-operator ExternalIP controller dispatches to AAP → fabric
  manager allocates an IP address → ExternalIP transitions to
  **Allocated**
- osac-operator ExternalIPAttachment controller checks two
  preconditions before dispatching:
  - **ExternalIP must be Allocated** (have an allocated address). If
    not, the controller requeues.
  - **Target resource must have a known IP.** The required IP depends
    on the target type (see below). If not yet available, the
    controller requeues.
- Once both preconditions are met, the controller dispatches to AAP →
  fabric manager creates the DNAT rule → ExternalIPAttachment
  transitions to **Ready**

*ExternalIPAttachment controller preconditions per target type:*

| Target type | Required precondition | Source of target IP |
|-------------|----------------------|---------------------|
| ComputeInstance | `compute_network_attachment_statuses` populated with primary attachment's `ip_address` | Feedback controller reads KubeVirt VMI network status, writes `ComputeNetworkAttachmentStatus` per attachment |
| Cluster | `status.apiEndpoint` or `status.ingressEndpoint` populated on ClusterOrder CR | MetalLB allocates VIP from IPAddressPool, template discovers and writes to ClusterOrder status |
| BaremetalInstance | `status.networkAttachmentStatuses[].ipAddress` populated for the primary interface | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches port MAC (from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to assigned IP; operator writes to CR status |

The controller uses the existing requeue pattern: if the precondition
is not met, it returns `ctrl.Result{RequeueAfter: interval}` and
retries until the target IP appears. This is the same pattern used
today for the `VirtualMachineReference` check on ComputeInstance
targets.

*IP discovery — DHCP-based host networking:*

All host-side IP assignment uses DHCP. The fabric's DHCP server (managed
by the fabric manager as part of the network segment infrastructure) assigns IPs
to hosts when they boot on the subnet. OSAC does not pre-allocate IPs
or configure host-side networking — DHCP handles IP address, gateway,
prefix, and DNS automatically.

After the host receives its IP via DHCP, the IP is discovered and
written to the resource's CR status for two purposes:
- ExternalIPAttachment controller reads the primary IP for DNAT target
- Tenant visibility (API response includes the allocated IP)

IP discovery mechanism per service type:

| Service | Discovery source | Who writes status | Status field |
|---------|-----------------|-------------------|-------------|
| VMaaS | KubeVirt VMI `status.interfaces[].ipAddress` | osac-operator feedback controller → Signal RPC → fulfillment-service | `ComputeInstanceStatus.compute_network_attachment_statuses[].ip_address` |
| CaaS | Agent CR network status | osac-operator feedback controller → Signal RPC → fulfillment-service | `ClusterOrderStatus.nodeSets[].agents[].ipAddress` (operator-internal) |
| BMaaS | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches port MAC — from the BareMetalHost `osac.openshift.io/interface-macs` annotation — to the DHCP-assigned IP, falling back to server name for named fabric servers (see [BMaaS OQ#4 — Resolved](/enhancements/OSAC-1437-bmaas-networking/design.md#4-how-is-the-hosts-runtime-ip-discovered-after-network-reconfiguration)) | bare-metal-fulfillment-operator dispatches `query_dhcp_lease` → writes to CR status → feedback controller → Signal RPC → fulfillment-service | `BareMetalInstanceStatus.network_attachment_statuses[].ip_address` |

The fabric manager's `move_network_attachment` role is switch-side
only — it moves a host's fabric port from one network segment to another
(`from_vnet_name` → `to_vnet_name`, either side optional). Attach and
detach are the **same primitive**: on provision the port moves from a
**provisioning network** to the tenant subnet's network segment; on deletion it
moves back to the provisioning network. The role operates purely against the
fabric (no Subnet CR lookup) and is keyed on plain segment names, so the caller
resolves a `subnetRef` → tenant segment name and supplies the provisioning
network name from configuration. Detach is a no-op if the port is not on the
named segment, so re-runs and unexpected states are safe.

One role handles both BMaaS (fabric NIC on the provisioning network while the
server is idle so it has internet during metal3 inspection) and CaaS (agent
moving from a provisioning network to the tenant network). The **timing** of the
move differs per service:

- **BMaaS:** Move happens **POST-provisioning** (provision on the provisioning
  network → move to tenant network → reboot so the OS re-DHCPs on the tenant
  network). This achieves isolation-until-ready: the tenant cannot reach the
  server during imaging/first-boot.
- **CaaS:** BMaaS moves the port **POST-OS-provisioning** (the host is provisioned
  on the provisioning network, then the port moves to the tenant network and the
  host reboots before it joins the cluster installation flow).

Once on the tenant network, the host receives an IP from the fabric's DHCP server
automatically. A single AAP job template serves both directions, deriving onboard
(provisioning network → tenant) vs. offboard (tenant → provisioning network) from
the resource's `deletionTimestamp`. See [BMaaS — Provisioning Network and Port
Moves](/enhancements/OSAC-1437-bmaas-networking/design.md#provisioning-network-and-port-moves).

IP discovery for BMaaS is a separate dispatcher call. After
`reconcileProvisioning` completes and the host has received a DHCP
lease, the operator dispatches `query_dhcp_lease` — this role queries
the fabric manager's DHCP lease API for the subnet and matches the
server's port MAC address to find the corresponding DHCP-assigned IP.
Bare-metal hosts are not named fabric servers, so the lease is matched
by NIC MAC, which the operator supplies from the host's
`osac.openshift.io/interface-macs` BareMetalHost annotation; named
fabric servers such as CaaS agents fall back to matching by server name.

*NATGateway controller preconditions:*

The NATGateway controller has two preconditions before dispatching the
SNAT rule creation:

| Precondition | Source |
|-------------|--------|
| Referenced VirtualNetwork must be Ready (fabric segment provisioned) | VirtualNetwork CR status |
| Referenced ExternalIP must be Allocated (have an allocated address) | ExternalIP CR status |

If either precondition is not met, the NATGateway controller requeues.
This prevents dispatching to AAP before the VN's fabric segment exists
(no segment to attach the SNAT rule to) or without a valid SNAT source
address.

*Auto-provisioned resource labeling:*

All auto-created resources receive the label
`osac.openshift.io/auto-created: "true"`. Auto-provisioned
ExternalIPs also receive a parent-resource label
`osac.openshift.io/auto-created-for: <resource-id>` so that the
cleanup logic can find orphaned ExternalIPs directly, even if the
intermediate ExternalIPAttachment has already been deleted.

*Auto-provisioned resource cleanup on parent deletion:*

The parent resource's finalizer uses a phased requeue approach to
ensure correct ordering:

1. Query ExternalIPAttachments labeled `auto-created` targeting
   this resource. Issue delete for each. Requeue.
2. On next reconcile: check if all ExternalIPAttachments are fully
   deleted (including their own finalizers completing the DNAT rule
   removal). If not, requeue.
3. Once all ExternalIPAttachments are gone: query ExternalIPs labeled
   `auto-created-for: <this-resource>`. Issue delete for each.
   Requeue.
4. On next reconcile: check if all ExternalIPs are fully deleted. If
   not, requeue.
5. Once all ExternalIPs are gone: proceed with parent resource
   deletion.

If cleanup fails permanently (after N retries): finalizer is removed,
parent resource deleted, orphaned resources left in cluster. Orphaned
resources are identifiable by the `auto-created-for` label.

**Enable outbound NAT (SNAT):**

```bash
osac create externalip --pool external-pool-1 --name nat-ip
osac create natgateway --virtual-network my-net --externalip nat-ip \
  --name my-nat
```

The fabric manager creates a SNAT rule for the VN: all egress traffic from
the VN's CIDR is source-NATted to the ExternalIP. Applies to all resources
in the VN — VMs, BM servers, cluster nodes — since all are on the fabric.

### API Extensions

#### VirtualNetwork

```protobuf
message VirtualNetworkSpec {
  string network_class = 1; // required, immutable
  string ipv4_cidr = 2;     // required canonical IPv4 CIDR, immutable
}
```

No scope or service field — subnets are infrastructure-agnostic.

#### HostType and BareMetalInstanceType

**HostType** is a legacy system-level inventory resource. New BMaaS and CaaS
network attachment resolution uses the tenant-facing `BareMetalInstanceType`
and its `network_ports`; the workload networking contract does not use
`HostType` as a second source of truth.

```protobuf
message NetworkInterface {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0" — unique within the type
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string description = 3; // e.g., "100GbE fabric interface"
}
```

Existing HostType records may still expose `interfaces` for inventory and
legacy consumers, but that list does not expand the tenant attachment
cardinality or override `BareMetalInstanceType.network_ports`.

Interfaces are ordered. When multiple interfaces share the same role
(e.g., two `fabric` interfaces), the first one in the list is the default
for that role — used by CaaS for automatic interface resolution.

**BareMetalInstanceType** is a tenant-facing catalog resource defined in
the [BareMetalInstanceType EP](/enhancements/OSAC-1201-baremetal-instance-types).
It provides a richer hardware discovery catalog for BMaaS, including
structured network ports with additional type and speed information:

```protobuf
message BareMetalNetworkPortSpec {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0" — unique within the type
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string type = 3;        // e.g., Ethernet, InfiniBand
  string speed = 4;       // e.g., 1Gbps, 100Gbps
  string description = 5; // e.g., "100GbE fabric interface"
}
```

`BareMetalInstanceType` is the authoritative tenant-facing hardware and
network-port catalog. Its `BareMetalNetworkPortSpec` entries provide the
names, roles, types, and speeds used for BMaaS validation and CaaS interface
resolution; no HostType reverse lookup is required for the workload contract.

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) — not tenant-attachable |

Roles are conventions, not enforced enums. Ports/interfaces with role
`lifecycle` are used by the provisioning system (Ironic, Metal3) and
should not appear in `network_attachments`.

**CaaS** uses BareMetalInstanceType: the fulfillment-service resolves the
interface automatically (first `fabric`-role port → stored as immutable
`fabric_interface` on the node set definition).

**BMaaS** uses BareMetalInstanceType: the tenant discovers interfaces
from BareMetalInstanceType and specifies port names directly on
`BareMetalNetworkAttachment.interface`, validated against the
`BareMetalInstanceType.network_ports` list. The `interface` field references
a port name from that list.

#### Network Attachment Types

Each resource type has its own network attachment message. The core fields
(`subnet`) are shared, but each type adds resource-specific fields.
Subnet policy is inherited from the Subnet's NetworkACL association and is
not copied into a workload attachment. `network_attachments` are immutable after
resource creation — changing network attachment requires recreating the
resource. VMaaS and BMaaS keep repeated fields for wire/API compatibility but
enforce a maximum of one entry. CaaS uses its existing singular field.

**ComputeNetworkAttachment** (for ComputeInstance):

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1; // Optional on input; immutable after resolution
  reserved 2;
}
```

The repeated field is retained for compatibility, but at most one entry is
accepted. The sole entry is the VM's default route/primary attachment; the
VMaaS attachment message has no primary field.

**BareMetalNetworkAttachment** (for BaremetalInstance):

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1; // Optional on input; immutable after resolution
  reserved 2;
  string interface = 3;            // optional, immutable: physical port name from BareMetalInstanceType
  optional bool primary = 4;            // omitted or true: implicit primary; false is rejected
}
```

The repeated field is retained for compatibility, but at most one entry is
accepted. The `interface` field, when supplied, references a port name from
the BareMetalInstanceType's network ports list; if omitted, the system picks
the default fabric interface. Omitted or empty attachment lists receive
defaults, and a supplied entry receives defaults only for missing fields. The
sole entry is the default route/primary attachment. A `primary: true` value is
accepted for compatibility and is redundant; `primary: false` is rejected.

**ClusterNetworkAttachment** (for Cluster):

```protobuf
message ClusterNetworkAttachment {
  SubnetLocalReference subnet = 1; // Required after resolution; immutable after creation
  reserved 2;
}
```

A single attachment applies to the whole cluster — all node sets share the same subnet.
The `fabric_interface` is resolved by the fulfillment-service at creation time for each
node set from its BareMetalInstanceType (first port with role `fabric`)
and stored on the node set definition. The tenant does not set this field.

#### Attachment Presence and Defaulting

The API distinguishes an omitted attachment from a supplied attachment, but
both an omitted attachment and an empty attachment list/message mean that the
caller requested the normal tenant defaults. Defaulting is field-level for a
single supplied attachment:

| Input | Resolution |
|---|---|
| VMaaS attachment omitted or empty | Add the tenant's default Subnet. |
| BMaaS attachment list omitted or empty | Add the tenant's default Subnet and the first `fabric` port from `BareMetalInstanceType.network_ports`. |
| CaaS attachment omitted or empty | Add the tenant's default Subnet; resolve the first `fabric` port from each node set's `BareMetalInstanceType` for the BM worker handoff. |
| One attachment with no Subnet | Default only the Subnet and, for BMaaS, preserve the supplied interface. |
| One BMaaS attachment with no interface | Default only the interface to the first `fabric` port from `BareMetalInstanceType.network_ports`. |
| One complete attachment | Preserve all supplied values and validate readiness, tenant scope, and VirtualNetwork relationships. |

Every Subnet already has one NetworkACL association, so resolving a workload
attachment does not choose or copy an ACL. If the selected Subnet or its ACL
is absent or not Ready, workload creation fails with a validation or
precondition error. The fully resolved attachment is stored with the workload
and is immutable after creation.

#### Resource Specs

**ComputeInstance**:

```protobuf
message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 14; // max 1 for compatibility
  optional bool auto_external_ip_attachment = 18;
}
```

The repeated `network_attachments` field is retained for API compatibility, but the
fulfillment-service and operator accept at most one entry. VMaaS has no separate
primary field; the sole entry is implicitly the default route.

**BaremetalInstance** (new — defined in the
[BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api)):

```protobuf
message BareMetalInstanceSpec {
  string catalog_item = 1;
  optional string ssh_public_key = 2;
  optional string user_data = 3;
  optional BareMetalInstanceRunStrategy run_strategy = 4;
  int64 restart_trigger = 5;
  map<string, google.protobuf.Any> template_parameters = 6;
  optional BareMetalInstanceImage image = 7;

  // NEW: OSAC networking; repeated for compatibility, max 1
  repeated BareMetalNetworkAttachment network_attachments = 8;
}
```

**Cluster** (new):

```protobuf
message ClusterSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;

  // NEW: networking
  ClusterNetworkAttachment network_attachment = 9;  // singular, one per cluster
}
```

- Cluster-internal CNI (pod/service CIDRs) uses platform defaults.
- The cluster's template determines whether nodes are VMs or BM. Both
  types are placed on the same subnet — VMs via the K8s overlay (already
  bridged to the fabric), BM nodes directly on the fabric.

The Cluster resource also gains two fields populated by the system
during provisioning:

```protobuf
message ClusterStatus {
  string api_endpoint = X;      // set by CaaS template, internal API server VIP
  string ingress_endpoint = Y;  // set by CaaS template, internal ingress VIP
}
```

These are used by the ExternalIPAttachment controller as the DNAT backend
IP when the target is a cluster (see
[Cluster ExternalIPAttachment flow](#cluster-externalipattachment-flow)).

#### Resource Status — Discovered IPs

After provisioning, resources receive IPs via DHCP. Feedback controllers
discover these IPs and write them to status for two purposes: tenant
visibility and ExternalIPAttachment DNAT target resolution.

**ComputeInstanceStatus:**

```protobuf
message ComputeNetworkAttachmentStatus {
  string subnet_ref = 1;               // Subnet ID (echoed from spec)
  string ip_address = 2;               // Discovered from KubeVirt VMI network status
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = N;
}
```

Feedback controller watches KubeVirt VMI `status.interfaces[].ipAddress`,
maps each interface to the corresponding attachment by CUDN NAD reference,
and fires Signal RPC to fulfillment-service.

**BaremetalInstanceStatus:**

```protobuf
message BareMetalNetworkAttachmentStatus {
  string interface = 1;                 // Physical interface name (echoed from spec)
  string subnet_ref = 2;               // Subnet ID (echoed from spec)
  string ip_address = 3;               // Discovered via query_dhcp_lease role after provisioning (matches port MAC to DHCP lease)
  bool primary = 4;                     // true for the sole resolved attachment; normalized from spec
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachment_statuses = N;
}
```

IP discovered after DHCP assignment on the tenant network. After
`reconcileProvisioning` completes, the operator dispatches
`query_dhcp_lease` to the fabric manager's DHCP lease API, matching
the server's port MAC address to find the assigned IP (see
[BMaaS OQ#4 — Resolved](/enhancements/OSAC-1437-bmaas-networking/design.md#4-how-is-the-hosts-runtime-ip-discovered-after-network-reconfiguration)).
The operator writes the discovered IP to CR status, and the feedback
controller syncs to fulfillment-service.

**ClusterStatus** does not have per-attachment IP status — CaaS uses
service-level VIPs (`api_endpoint`, `ingress_endpoint`) rather than
per-node IPs. Per-agent IPs are tracked on the ClusterOrder CR's
`NodeSetStatus.AgentStatus.IPAddress` (operator-internal, not surfaced
to tenant).

#### ExternalIPAttachment — Inbound Traffic (DNAT)

Handles **inbound traffic only**. Does not affect egress (that is
NATGateway's job).

```protobuf
enum ExternalIPAttachmentEndpoint {
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_UNSPECIFIED = 0;
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_API         = 1;  // Cluster API server
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_INGRESS     = 2;  // Cluster ingress wildcard
}

message ExternalIPAttachmentSpec {
  string external_ip = 1;          // required, immutable

  oneof target {
    string compute_instance = 2;
    string cluster = 3;
    string baremetal_instance = 4;
  }
  ExternalIPAttachmentEndpoint target_endpoint = 5;
  // Required when target=cluster; must be UNSPECIFIED otherwise.
}
```

All fields are immutable after creation.

#### NATGateway — Outbound Traffic (SNAT)

Handles **outbound traffic only**.

```protobuf
message NATGatewaySpec {
  string virtual_network = 1;  // parent VN ID, required, immutable
  string external_ip = 2;      // required, immutable
}
```

An ExternalIP can only be used by one consumer (either an
ExternalIPAttachment or a NATGateway, not both). One NATGateway per
VirtualNetwork. NATGateway is optional — it provides a dedicated egress
identity. Without it, resources may still have default egress but without a
controlled source IP.

All fields are immutable after creation.

**Direction summary:**

| Resource | Direction | Mechanism |
|----------|-----------|-----------|
| ExternalIPAttachment | Inbound (DNAT) | External IP → resource |
| NATGateway | Outbound (SNAT) | Resource → external IP |

### Implementation Details

#### NetworkACL Reconciliation and Readiness

The operator creates and deletes each NetworkACL through the manager assigned
to the VirtualNetwork's NetworkClass. Subnet creation supplies the required
`spec.network_acl` reference, which remains fixed for that Subnet's lifetime.
An ACL may be reused by multiple Subnets in its VirtualNetwork. [PRD: FR-4]

A Subnet is READY only after its network segment and its associated ACL are
active. ACLs and Subnet associations are create-time configuration; changes
require deleting and recreating the affected resources. The controller must
not report a Subnet READY without an active ACL. [PRD: FR-4]

The ACL operates at Subnet boundaries. Traffic between resources on the same
Subnet bypasses that ACL. Traffic between Subnets must pass source egress and
destination ingress evaluation. Cross-VirtualNetwork traffic remains
unsupported. [PRD: FR-4]

#### Tenant-Assisted Policy Migration

The workload API no longer carries traffic-policy references. Existing
per-workload policies cannot always map one-to-one to a subnet-wide stateless
ACL: workloads on one Subnet may have different policies, and established
connections previously allowed return traffic without a reverse rule.
After the ACL-aware release is deployed, tenants group workloads by intended
policy, create a NetworkACL for each policy group, associate the appropriate
ACL with each Subnet, and add explicit reverse-direction rules where return
traffic is needed. If workloads on one
Subnet require different policies, the tenant moves them to separate Subnets;
changing a workload's Subnet requires recreating the workload because its
attachment is immutable. This migration is tenant-assisted and does not
promise exact automatic policy conversion. [PRD: FR-14]

#### Deletion Dependency Guards

When the API layer (fulfillment-service) soft-deletes networking resources,
it accepts the delete as soon as child resources are themselves soft-deleted.
On the operator side, each controller triggers its AAP deprovision job when
it sees a `deletionTimestamp`. If a parent and its children are deleted
near-simultaneously, the parent's deprovision job fires before children
have been fully removed from the infrastructure backend, causing the backend
to reject the parent deletion.

To prevent unnecessary failed jobs and backoff delays, each parent
controller gates its deprovision on the complete removal of child CRs.
The controller lists child CRs referencing the parent before triggering the
AAP deprovision job. If any children still exist on the cluster (regardless
of their own deletion state), the controller requeues with a short interval
(10 seconds) instead of dispatching a doomed job.

| Controller | Gate deprovision on |
|---|---|
| VirtualNetwork | No Subnet, NetworkACL, or NATGateway CRs with `spec.virtualNetwork` referencing this VNet |
| Subnet | No ComputeInstance CRs with `spec.networkAttachments[].subnetRef` referencing this Subnet; no BareMetalInstance CRs with `spec.networkAttachments[].subnetRef` referencing this Subnet (see [BMaaS Networking](/enhancements/OSAC-1437-bmaas-networking/design.md)) |
| NetworkACL | No Subnet CRs with `spec.networkACL` referencing this ACL |
| ExternalIP | No ExternalIPAttachment or NATGateway CRs with `spec.externalIP` referencing this EIP |
| ExternalIPPool | No ExternalIP CRs with `spec.pool` referencing this pool |

The full dependency chain (delete order, leaf first):

```text
ComputeInstance / BareMetalInstance (leaf)
  must be gone before --> Subnet
  must be gone before --> ExternalIPAttachment (via auto-cleanup)

ExternalIPAttachment
  must be gone before --> ExternalIP

NATGateway
  must be gone before --> ExternalIP
  must be gone before --> VirtualNetwork

NetworkACL
  must be gone before --> VirtualNetwork

Subnet
  must be gone before --> NetworkACL

Subnet
  must be gone before --> VirtualNetwork

ExternalIP
  must be gone before --> ExternalIPPool

VirtualNetwork (delete last)
```

This is the same pattern used during provisioning (e.g., the NATGateway
controller gates provisioning on ExternalIP readiness and VirtualNetwork
readiness) -- applied symmetrically to the deprovision path.

#### NATGateway Scope

One NATGateway per VirtualNetwork. All subnets in the VN use the gateway.
Per-subnet NAT association is a future enhancement.

#### Single-NIC Workload Attachment Constraint

VMaaS, BMaaS, and CaaS currently support at most one tenant network
attachment per workload. VMaaS and BMaaS retain repeated attachment fields
for wire/API compatibility, while CaaS retains its singular field. Requests
with more than one VM or BM attachment are rejected by API validation and by
the corresponding operator CRD. Multi-NIC workload networking is future
scope.

With exactly one attachment, the attachment is the **primary** attachment by
default and determines:

- Which subnet provides the **default gateway** for the resource
- Which subnet IP is used as the **DNAT target** for ExternalIPAttachment
- Which subnet IP is used as the **source** for NATGateway SNAT

**Validation and compatibility:**
- Zero or one attachment is valid
- If one BMaaS attachment exists, its existing `primary` field may be omitted
  or set to `true`; both mean the same default-route behavior. `primary: false`
  is rejected. VMaaS has no primary field, and CaaS has no primary concept.
- Omitted or empty attachment lists receive the resource-specific defaults
  described in [Attachment Presence and Defaulting](#attachment-presence-and-defaulting);
  a supplied attachment receives defaults only for missing fields.
- The complete resolved attachment list and every network-owned field are
  immutable after creation; changing them requires deleting and recreating the
  workload.

**IP assignment:** All resource types receive IPs via DHCP. For VMs,
OVN provides DHCP on the CUDN overlay. For BM servers and CaaS agents,
the fabric's DHCP server assigns IPs on the network segment. The provisioning
template does NOT configure host-side networking (no static IP, gateway,
or DNS configuration) — DHCP handles it automatically.

| Subnet role | IP assignment provides (via DHCP) |
|-------------|---------------------------------------------|
| Sole/primary attachment | IP address + default gateway + DNS |

This ensures the resource has exactly one default route. Additional workload
attachments are not supported in the current API contract.

**ExternalIPAttachment:** The fabric manager creates a DNAT rule to the
resource's sole/primary subnet IP. The tenant does not need to specify an
interface; the single-attachment contract determines the target.

**Cluster networking:** `ClusterNetworkAttachment` is a single attachment
(one subnet for the whole cluster). Multi-NIC for individual cluster nodes is
not supported by the current CaaS contract. The `primary` field does not
apply to `ClusterNetworkAttachment`.

#### Multiple Hosting Clusters Per Deployment

Multiple hosting clusters are supported per deployment. At subnet creation, the
k8sManager creates a K8s overlay on each hosting cluster and bridges it to
the fabric segment. VMs on different hosting clusters share the same subnet
via the fabric.

#### Hub Selection (CR Placement)

The fulfillment-controller creates K8s CRs on the single registered hub
cluster in a supported networking deployment. All networking resources
(VirtualNetwork, Subnet, NetworkACL, ExternalIPPool, ExternalIP,
ExternalIPAttachment, NATGateway) use that hub. Multi-hub networking
placement, cross-hub resource coordination, and cross-hub network connectivity
are unsupported. The hub assignment remains sticky through `status.hub` for
resource lifecycle and reconciliation.

This boundary applies only to the networking area and does not define hub
behavior for other OSAC areas. The fabric can still span multiple hosting
clusters where the relevant networking feature supports that topology.

#### Cross-VN Communication

VirtualNetworks are isolated. Cross-VN communication (VN Peering) is a
separate enhancement.

#### DNS

DNS is a service-integration concern, not part of the networking API. CaaS
template roles create DNS records. A DNS API is a separate enhancement.

#### BM-Only Deployments

If a NetworkClass has no k8sManager, the deployment does not support VMs.
ComputeInstance creation is rejected if the target NetworkClass has no
k8sManager — there is no K8s overlay to place the VM on.

CaaS clusters work without a k8sManager. MetalLB IPAddressPool creation
is handled by the Subnet controller (gated on
`NetworkClass.spec.vip_prefix_length`), not by the k8sManager. BM-only
CaaS deployments provision clusters with fabric-level networking and
MetalLB VIP allocation without requiring a K8s overlay.

#### CIDR Overlap

The operator validates that Subnet CIDRs do not overlap within a
VirtualNetwork at creation time.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fabric manager complexity | One Ansible role handles all networking concerns | Clear interface contract per operation; tested independently per manager |
| K8s-to-fabric bridge failure | VMs unreachable from fabric | k8sManager validates bridge connectivity at subnet creation; subnet stays Pending until bridge is confirmed |
| CaaS prerequisite ordering | ExternalIPs may be needed before cluster | Pending state for attachments; template validates its own prerequisites |
| ExternalIPAttachment target validation | Target may not exist yet (CaaS) or may be deleted | Pending state for forward references; attachment tracks target lifecycle |
| CIDR overlap | Overlapping subnets cause routing ambiguity | Operator validates at creation time; rejected with clear error |

### Drawbacks

This design requires K8s-to-fabric connectivity in every deployment that
hosts VMs. The k8sManager must bridge the OVN overlay to the physical
fabric for VMs to participate. In deployments without VMs (BM-only, with
or without CaaS), the k8sManager is not needed and the design reduces to
fabric-manager-only. MetalLB IPAddressPool creation for CaaS VIP
allocation is handled by the Subnet controller, not the k8sManager.

The trade-off is justified by infrastructure-agnostic subnets: any resource
type on any subnet, uniform security enforcement via the fabric, and no
per-resource-type dispatcher logic for ExternalIP or NATGateway.

## Alternatives (Not Implemented)

**Original NetworkClass model.** Tenants select a NetworkClass per VN.
Exposes implementation details. Not viable for multi-service support.

**Per-action driver composition.** Separate drivers for each networking
concern (network, acl, ingress, egress, publicIP) with independent
registration and composition. Over-engineered — the fabric is one product,
and splitting it into per-action drivers does not reflect how physical
networking works. Also creates complexity in the dispatcher and validation.

**Separate k8s ACL driver.** A dedicated k8s.acl driver (e.g.,
NetworkPolicy) alongside fabric ACLs. Redundant — when VMs are on the
fabric, the fabric enforces security for all traffic including VM traffic.
Adding a k8s ACL layer creates dual enforcement with no clear benefit.

**VN scope field (vm/bm).** Require tenants to declare what a network is
for at creation time. Makes subnets service-specific, prevents mixed
workloads, and leaks infrastructure details.

**Lazy subnet provisioning.** Defer manager selection to resource placement
time. Creates ambiguous subnet state and complicates the tenant experience.

## Resolved Questions

1. **Infrastructure-agnostic subnets.** VMs participate in the fabric via
   k8sManager. No scope/service field on VN. Any resource on any subnet.

2. **Cluster endpoint types:** `api` and `ingress` — enum
   `ExternalIPAttachmentEndpoint`.

3. **ExternalIP ownership:** An ExternalIP can only be consumed by one
   resource (either ExternalIPAttachment or NATGateway, not both).

4. **One NATGateway per VN.** Multiple gateways are ambiguous. Per-subnet
   NAT is a future enhancement.

5. **ExternalIPPool shared.** The fabric manager handles ExternalIP allocation
   for all resource types. One pool per deployment.

6. **Multiple hosting clusters.** Subnet creation provisions K8s overlay
   on each hosting cluster. VMs on different clusters share the subnet
   via the fabric.

7. **Internal IP pools.** Managed by managers with sensible defaults. Not
   part of the tenant API or NetworkClass spec.

8. **ExternalIP naming.** "External" means external to the VirtualNetwork —
   not necessarily Internet-routable. This applies within the supported
   connected deployment boundary.

9. **network_attachments immutability and cardinality.** Network attachments
   are immutable after resource creation, and VMaaS/BMaaS accept at most one
   entry even though the fields remain repeated for compatibility. Changing
   network attachment requires recreating the resource.

10. **Traffic enforcement.** NetworkACL is enforced at the Subnet boundary
    for all workloads. No separate K8s-level ACL is required because VMs are
    connected to the same Subnet network as bare-metal servers and cluster
    nodes.

11. **Per-resource NetworkAttachment types.** Separate proto messages
    (`ComputeNetworkAttachment`, `BareMetalNetworkAttachment`,
    `ClusterNetworkAttachment`) instead of one shared type. Each resource
    type has a different selector concept (virtual NIC, physical interface,
    node set) — a shared type with optional fields would accumulate
    dead weight per resource type.

12. **Networking API lifecycle.** Networking resources use read, create, and
    delete operations. NetworkACL rules and the Subnet's `network_acl`
    association are immutable after creation; changing them requires deleting
    and recreating affected resources. Workload attachments also remain
    immutable after creation; status reconciliation remains internal.

## Test Plan

*Section to be completed when targeted at a release.*

## Graduation Criteria

*Section to be completed when targeted at a release.*

## Upgrade / Downgrade Strategy

### Upgrade

This is a coordinated, breaking cutover of the networking API and workload
attachment contract. The prior release cannot represent `NetworkACL` resources
or `Subnet.spec.network_acl`; tenants must not create ACL resources or
associations before the ACL-aware API is deployed. Existing policy is
tenant-mapped. There is no automatic or lossless conversion from existing
per-workload policy to a Subnet-wide ACL.

#### Pre-upgrade inventory and preparation

- Inventory affected tenants' VirtualNetworks, Subnets, workload attachments,
  and existing traffic policies. Identify Subnets whose workloads require
  different policies.
- With each tenant, prepare a mapping from existing policy to the intended
  Subnet policy. A Subnet has exactly one associated ACL; compatible rules may
  share an ACL among Subnets in the same VirtualNetwork. Where policies on a
  Subnet conflict, plan separate Subnets and workload recreation. Include
  explicit reverse-direction rules for required return traffic.
- Prepare the NetworkACL rule definitions and Subnet-to-ACL mapping as a
  migration plan only; do not submit ACL resources through the prior release.
  Snapshot API/database state, networking CRs, NetworkClass configuration,
  attachment specs, and the current release versions. Agree on a restore plan
  and schedule a maintenance window.

#### Coordinated cutover

1. Freeze tenant network and workload writes that can affect the cutover,
   including network resource changes, workload creation/deletion, and
   attachment changes. Permit only the designated migration operations while
   the freeze is in effect.
2. Deploy the ACL-aware fulfillment-service, API and CRD schemas,
   osac-operator, networking controllers, configured networking manager, and
   compatible clients as one coordinated release.
3. For each VirtualNetwork, use the new API to create the planned
   VirtualNetwork-scoped NetworkACLs. Wait for each ACL to become READY, then
   create replacement Subnets with an explicit `spec.network_acl` in the same
   VirtualNetwork. Existing Subnets cannot be reassociated in place; recreate
   affected Subnets and workloads as required by their deletion dependencies.
4. Keep each affected Subnet and workload creation using it gated until its
   associated ACL policy is active. A Subnet becomes READY only when its
   associated policy is active. If policy mapping requires moving a workload
   to a different Subnet, recreate it only after the destination Subnet is
   READY; attachments remain immutable.
5. Validate the tenant-approved policy mapping, ACL readiness, Subnet
   associations, and representative connectivity. Reopen network and workload
   writes only after every affected Subnet has an active policy. Keep any
   incomplete tenant migration gated.

The tenant-approved mapping is authoritative: the service does not infer one
Subnet-wide policy from workloads that previously had different policies.
Tenants retain responsibility for policy grouping and for deciding whether
workloads must be recreated.

### Downgrade

The prior release cannot parse, manage, or enforce `NetworkACL` resources and
Subnet associations. Rolling back only the API server or only the operator is
unsupported. If rollback is required after cutover begins:

1. Freeze network and workload writes.
2. Restore the coordinated pre-upgrade database, CR, NetworkClass, and workload
   attachment state, ensuring no ACL-only objects or Subnet references remain.
   A tenant-managed reverse mapping or a separately tested restore procedure
   is required; automatic policy conversion is not provided.
3. Roll back fulfillment-service, API/CRD schemas, osac-operator, networking
   controllers, configured networking manager, and clients together.

If the pre-upgrade state cannot be restored, downgrade is unsupported; retain
the ACL-aware release and fix forward. Do not assume existing workload or
default-networking resources make an in-place binary rollback safe.

## Version Skew Strategy

### Control plane

The API service, persistence schema, CRDs, controllers, and configured
networking manager must use the same ACL-aware release. Mixed prior and new
versions are unsupported during migration: the prior release does not
understand NetworkACL resources or `Subnet.spec.network_acl`, and the new
release requires that policy contract for Subnet readiness and workload
placement. Keep affected writes frozen until all components are upgraded and
each migrated Subnet has active policy.

### Clients

Prior clients cannot create NetworkACLs or submit explicit Subnet ACL
associations, and may still construct workload attachments using the prior
wire contract. New clients require the ACL-aware API and cannot use its
NetworkACL or Subnet association operations against the prior server. Upgrade
clients with the control plane and block prior-client network/workload writes
during cutover. Reopen writes only when clients and services use the same
contract; no mixed-version write compatibility is promised.

## Support Procedures

*Section to be completed when targeted at a release.*

## Infrastructure Needed

No additional infrastructure beyond existing OSAC components and managers.

---

## Provenance

Authored: respond @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Phases: revise, respond

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":43,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
