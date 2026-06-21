---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-06-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1029
see-also:
  - Requirements (PRD): /enhancements/unified-networking-prd
  - Networking API: /enhancements/networking
  - BareMetal Instance API: /enhancements/baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
replaces:
  - /enhancements/networking
superseded-by:
  - N/A
---

# Unified Networking API for VMaaS, CaaS, and BMaaS

## Summary

This enhancement describes the technical design for the OSAC unified
networking architecture. For the problem statement, gaps analysis, and
requirements, see the companion
[Requirements Document (PRD)](/enhancements/unified-networking-prd).

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
  Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway)
  serve VMaaS, CaaS, and BMaaS identically

The BMaaS integration is based on the `BaremetalInstance` resource defined in
the [BareMetal Instance API enhancement](/enhancements/baremetal-instance-api),
which provides a per-server resource aligned with ComputeInstance.

For user stories, goals, and non-goals, see the
[Requirements Document (PRD)](/enhancements/unified-networking-prd).

## Proposal

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for a region. Tenants never interact with it. One NetworkClass
per region.

#### Two Managers

OSAC networking is handled by two managers:

- **Fabric Manager** — a single product (e.g., Netris, Neutron) that manages
  all physical networking: tenant isolation, ACLs, IP allocation, DNAT, SNAT.
  The physical fabric is one infrastructure — one controller manages it all.

- **K8s Manager** (optional) — handles everything needed to make VMs part of
  the fabric: creates the K8s overlay (e.g., CUDN with LocalNet) and bridges
  it to the fabric segment. Only needed for regions that host VMs. Once VMs
  are on the fabric, the fabric manager handles them identically to
  bare-metal servers.

#### Why Two Managers?

The fabric is one product. You cannot have Netris handling isolation and
Neutron handling ACLs on the same switches — splitting into per-action
drivers does not reflect how physical networking works. A single
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

**Netris + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: moc-region-1
spec:
  region: moc-region-1
  fabricManager: netris
  k8sManager: cudn_localnet
status:
  capabilities:
    addressFamily: dualStack
```

**Neutron + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: bos-region-1
spec:
  region: bos-region-1
  fabricManager: neutron
  k8sManager: cudn_localnet
status:
  capabilities:
    addressFamily: ipv4
```

**BM-only region (no VMs):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: gpu-region-1
spec:
  region: gpu-region-1
  fabricManager: netris
status:
  capabilities:
    addressFamily: ipv4
```

#### Capabilities

Capabilities are **inferred from the assigned managers** and published in
the NetworkClass status — the provider does not set them manually. The
operator computes the intersection of capabilities declared by the fabric
manager and k8sManager ConfigMaps and populates `status.capabilities`
automatically.

If the provider needs to restrict a capability that the managers support
(e.g., disable IPv6 in a region even though the fabric manager supports
it), they can set `spec.disableCapabilities`:

```yaml
spec:
  fabricManager: netris
  k8sManager: cudn_localnet
  disableCapabilities:
    - ipv6
```

| Capability | Type | Meaning |
|-----------|------|---------|
| `addressFamily` | enum | `ipv4`, `ipv6`, or `dualStack` |
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
  name: fabric-manager-netris
  namespace: osac
  labels:
    osac.openshift.io/network/fabric-manager: "true"
data:
  name: netris
  description: "Netris SDN — tenant isolation, ACL, IPAM, DNAT, SNAT"
  capabilities: "addressFamily:ipv4"
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fabric-manager-neutron
  namespace: osac
  labels:
    osac.openshift.io/network/fabric-manager: "true"
data:
  name: neutron
  description: "OpenStack Neutron — tenant isolation, IPAM, floating IPs"
  capabilities: "addressFamily:ipv4"
```

**K8s managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-cudn-localnet
  namespace: osac
  labels:
    osac.openshift.io/network/k8s-manager: "true"
data:
  name: cudn_localnet
  description: "CUDN with LocalNet — bridges OVN overlay to physical fabric"
  capabilities: "addressFamily:dualStack"
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
a working lab example.

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
and (if the region has a k8sManager) the K8s overlay for every subnet. Any
resource type can be placed on any subnet.

At subnet creation, the dispatcher runs:

1. **Fabric manager** — creates fabric segment (e.g., VLAN, VPC)
2. **K8s manager** (if present) — creates K8s overlay on each hosting
   cluster in the region and bridges it to the fabric segment

VMs are placed in the K8s overlay (which is bridged to the fabric), BM
servers and cluster nodes are placed directly on the fabric segment. The
fabric is the single source of truth for multi-tenancy and routing — all
resources, regardless of type, are on the fabric.

### Dispatcher (Operator Composition Logic)

The osac-operator acts as a **dispatcher**: when reconciling any networking
resource, it resolves the NetworkClass for the region and calls the
appropriate managers. Each manager corresponds to an Ansible role — the
dispatcher triggers the appropriate AAP playbook, passing the resource and
context as the event payload.

| Operation | Managers called |
|-----------|----------------|
| VN create/delete | `fabricManager` |
| Subnet create/delete | `fabricManager` + `k8sManager` (per hosting cluster) |
| SecurityGroup create/delete | `fabricManager` |
| ExternalIP alloc/release | `fabricManager` |
| ExternalIPAttachment create/delete | `fabricManager` |
| NATGateway create/delete | `fabricManager` |

Everything except subnet creation is handled by the fabric manager alone.
The k8sManager is only involved at subnet creation (to bridge the overlay)
— after that, VMs are on the fabric and the fabric manager handles them
like any other resource.

### Resource Hierarchy

```text
NetworkClass (per region, provider-only)

VirtualNetwork (tenant-managed, infrastructure-agnostic)
  ├── Subnet              → fabricManager + k8sManager
  ├── SecurityGroup       → fabricManager
  └── NATGateway          → fabricManager

ExternalIPPool (region-scoped, provider-managed)
  └── ExternalIP (tenant-managed) → fabricManager

ExternalIPAttachment (tenant-managed)
                          → fabricManager
                            references an ExternalIP and a target resource
```

### ExternalIPPool

"External" in ExternalIPPool/ExternalIP means **external to the
VirtualNetwork** — not necessarily internet-routable. In air-gapped
environments, the provider creates pools with data-center-routable IPs. In
internet-connected environments, the pools contain internet-routable IPs.
The API and flow are identical regardless of the deployment topology.

ExternalIPPools are provider-managed and region-scoped. The fabric manager
handles IP allocation — one pool serves all resource types.

### End-to-End Flows

This section shows how the unified networking API works from the tenant's
perspective. The flows are the same regardless of which fabric manager or
K8s manager the provider has deployed. Annotations mark what is **new** or
**changed** compared to the current design.

#### Provider Setup

1. Provider deploys hosting cluster(s) and fabric controller
2. Provider creates NetworkClass for the region (**new** — provider-only,
   tenants never see it)
3. Provider creates ExternalIPPool (**renamed** from PublicIPPool):

```bash
osac admin create externalippool \
  --region moc-region-1 \
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
osac create virtualnetwork --region moc-region-1 --cidr 10.0.0.0/16 \
  --name my-net
```

The fabric manager creates an isolated tenant segment on the fabric.

**Create Subnet:**

```bash
osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 \
  --name my-subnet
```

The fabric manager creates a fabric segment (e.g., VLAN) for the subnet.
If the region has a K8s manager, it also creates a K8s overlay on each
hosting cluster and bridges it to the fabric segment. After this step, VMs placed in the
overlay and BM servers with switch ports on the fabric segment are in the
same L2 domain.

**Create SecurityGroup:**

```bash
osac create security-group --virtual-network my-net --name my-sg \
  --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
```

The fabric manager creates ACL rules on the fabric.

#### Resource Creation (Differs by Type)

The networking setup above is shared. Only the resource creation step
differs internally — the tenant CLI experience is the same for all types.

**ComputeInstance (VM):**

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --name my-vm
```

VM is placed in the K8s overlay namespace on a hosting cluster. Because the
overlay is bridged to the fabric, the VM is directly on the fabric segment
and gets an IP from the subnet CIDR.

**BaremetalInstance:**

Bare-metal servers have multiple physical interfaces. The tenant discovers
available interfaces through BMaaS (the exact discovery mechanism — e.g.,
host type metadata, template, or inventory query — is defined by the BMaaS
design). Given the interface identifiers, the tenant specifies which
interface to attach to which subnet. Each
`network_attachment` maps one physical interface to one subnet. If
`interface` is omitted, the fabric manager picks a default.

Single interface (simple case):

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
  --name my-server
```

Multiple interfaces (e.g., east-west traffic on one subnet, north-south
on another):

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=east-west-subnet,security-groups=my-sg \
  --network-attachment interface=data-1,subnet=north-south-subnet \
  --name my-server
```

The fabric manager configures each host switch port on the corresponding
fabric segment. Each interface gets an IP from its subnet's CIDR.

Validation rules:
- All referenced subnets must belong to the same VirtualNetwork
- The same interface cannot appear in multiple attachments
- The `interface` must reference a valid interface identifier from BMaaS
- Multiple attachments without `interface` is invalid — if more than one
  attachment is specified, each must have an explicit `interface`
- The number of attachments cannot exceed the number of available interfaces

**Cluster:**

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --node-set workers=large,size=3 --name my-cluster
```

The template determines whether nodes are VMs or BM. BM nodes get switch
ports configured on the fabric segment. VM nodes are placed in the K8s
overlay. Either way, all nodes end up on the same fabric segment.

For clusters with BM nodes, the nodes also have multiple physical
interfaces — the same reality as BaremetalInstance. The difference is that
the **template** handles the interface-to-subnet mapping, not the tenant.
The cluster template is created by the provider who knows the node hardware
(e.g., which interface is for data traffic, which is for management). The
tenant specifies which subnet(s) to use; the template maps them to the
correct physical interfaces for each node type.

Different node sets can be placed on different subnets using the `node-set`
field (see [ClusterNetworkAttachment](#network-attachment-types)):

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment node-set=compute,subnet=standard-subnet,security-groups=my-sg \
  --network-attachment node-set=gpu,subnet=gpu-subnet \
  --node-set compute=large,size=3 --node-set gpu=h100,size=2 \
  --name my-cluster
```

In all cases, the resource ends up on the fabric. The fabric manager sees
all resources equally — there is no VM-vs-BM distinction.

#### External Access (Same for All Resource Types)

Since all resources are on the fabric, external access operations are
uniform. There is no VM-vs-BM distinction (**changed** — the current design
has separate K8s-side steps for VMs).

**Allocate ExternalIP:** (**renamed** from PublicIP)

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
subnet and has one fabric IP — the DNAT targets that IP directly. For
bare-metal servers with multiple interfaces, the ExternalIP is attached to
the resource, not to a specific interface — the fabric manager routes to
the resource's primary subnet IP.

**Cluster ExternalIPAttachment flow:**

For VMs and BM, the DNAT target is the resource's fabric IP —
straightforward. For clusters, the DNAT target is a service-level VIP
(API server or ingress) that is discovered during cluster provisioning.
The VIP allocation is decoupled from the networking layer:

1. CaaS template provisions the cluster
2. Template provisions internal VIPs via MetalLB LoadBalancer Services:
   - **API VIP**: MetalLB allocates an IP for the kube-apiserver Service
     on the management cluster
   - **Ingress VIP**: MetalLB allocates an IP for the ingress controller
     Service on the hosted cluster (from the tenant's subnet)
3. Template writes VIPs to the ClusterOrder CR status
4. Feedback controller syncs VIPs to the Cluster object in the
   fulfillment service as `api_endpoint` and `ingress_endpoint` fields
5. ExternalIPAttachment controller reads the VIP from the Cluster →
   calls fabric manager to create DNAT: external IP → internal VIP
6. ExternalIPAttachment transitions to Ready

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
  string region = 1;       // required, immutable
  string ipv4_cidr = 2;    // optional, immutable
  string ipv6_cidr = 3;    // optional, immutable
}
```

No scope or service field — subnets are infrastructure-agnostic.

#### Network Attachment Types

Each resource type has its own network attachment message. The core fields
(`subnet`, `security_groups`) are shared, but each type adds
resource-specific fields. `network_attachments` are immutable after
resource creation — changing network attachment requires recreating the
resource.

**ComputeNetworkAttachment** (for ComputeInstance):

```protobuf
message ComputeNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, optional, mutable
  bool primary = 3;                     // optional, immutable: designates default gateway
}
```

Each entry maps one virtual NIC to one subnet. Multiple entries create
a multi-homed VM. See [Multi-NIC Behavior](#multi-nic-behavior) for
primary designation and default gateway semantics.

**BareMetalNetworkAttachment** (for BaremetalInstance):

```protobuf
message BareMetalNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, optional, mutable
  string interface = 3;                 // optional, immutable: physical interface identifier from BMaaS
  bool primary = 4;                     // optional, immutable: designates default gateway
}
```

Each entry maps one physical interface to one subnet. The `interface`
field references an interface identifier provided by BMaaS.
If omitted, the fabric manager picks a default. Multiple entries create
a multi-homed BM server. See [Multi-NIC Behavior](#multi-nic-behavior)
for primary designation and default gateway semantics, and
[Resource Creation](#resource-creation-differs-by-type) for interface
discovery and multi-interface examples.

**ClusterNetworkAttachment** (for Cluster):

```protobuf
message ClusterNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, optional, mutable
  string node_set = 3;                  // optional, immutable: node set name from cluster spec
}
```

Each entry maps one node set to one subnet. If `node_set` is omitted,
all node sets use this subnet. Multiple entries place different node sets
on different subnets (e.g., GPU workers on a high-bandwidth subnet,
compute workers on a standard one).

#### Resource Specs

**ComputeInstance** (existing — field already exists, type changes):

```protobuf
message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 14;
}
```

**BaremetalInstance** (new — defined in the
[BareMetal Instance API enhancement](/enhancements/baremetal-instance-api)):

```protobuf
message BaremetalInstanceSpec {
  string template = 1;
  optional string ssh_key = 2;
  optional string user_data = 3;
  optional BaremetalInstanceRunStrategy run_strategy = 4;
  optional google.protobuf.Timestamp restart_requested_at = 5;

  // NEW: OSAC networking
  repeated BareMetalNetworkAttachment network_attachments = 6;
}
```

**Cluster** (new):

```protobuf
message ClusterSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;

  // NEW: networking
  repeated ClusterNetworkAttachment network_attachments = 4;
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

#### NATGateway Scope

One NATGateway per VirtualNetwork. All subnets in the VN use the gateway.
Per-subnet NAT association is a future enhancement.

#### Multi-NIC Support

ComputeInstance supports multiple `network_attachments` (virtual NICs). All
subnets must belong to the same VN. BaremetalInstance supports multiple
`network_attachments` with the `interface` field to map physical NICs to
subnets. Cluster supports multiple `network_attachments` with the
`node_set` field to place different node sets on different subnets. All
subnets must belong to the same VN across all resource types.

#### Multi-NIC Behavior

When a resource has multiple network attachments, the tenant designates
one as **primary** via `primary: true` on the attachment. The primary
attachment determines:

- Which subnet provides the **default gateway** for the resource
- Which subnet IP is used as the **DNAT target** for ExternalIPAttachment
- Which subnet IP is used as the **source** for NATGateway SNAT

**Validation:**
- If only one attachment exists, it is primary by default
- If multiple attachments exist, exactly one must be marked `primary: true`
- If multiple attachments exist and none is marked primary, the request is
  rejected
- `primary` is immutable after creation

**IPAM and DHCP:** The responsible manager (k8sManager for VMs, fabric
manager for BM) configures DHCP per subnet based on the primary
designation:

| Subnet role | DHCP provides |
|-------------|--------------|
| Primary | IP address + default gateway + DNS |
| Secondary | IP address + connected route only (no gateway) |

This ensures the resource has exactly one default route. Secondary subnets
are reachable via directly connected routes.

**ExternalIPAttachment:** When targeting a multi-homed resource, the fabric
manager creates a DNAT rule to the resource's primary subnet IP. The tenant
does not need to specify which interface — the primary designation
determines the target.

**Cluster multi-NIC:** `ClusterNetworkAttachment` uses `node_set` rather
than per-NIC attachment. Multi-NIC for individual cluster nodes is handled
by the CaaS template (provider-configured). The `primary` field does not
apply to `ClusterNetworkAttachment`.

#### Multiple Hosting Clusters Per Region

Multiple hosting clusters are supported per region. At subnet creation, the
k8sManager creates a K8s overlay on each hosting cluster and bridges it to
the fabric segment. VMs on different hosting clusters share the same subnet
via the fabric.

#### Cross-VN Communication

VirtualNetworks are isolated. Cross-VN communication (VN Peering) is a
separate enhancement.

#### DNS

DNS is a service-integration concern, not part of the networking API. CaaS
template roles create DNS records. A DNS API is a separate enhancement.

#### BM-Only Regions

If a region's NetworkClass has no k8sManager, the region does not support
VMs. ComputeInstance creation is rejected if the target region has no
k8sManager — there is no K8s overlay to place the VM on.

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
fabric for VMs to participate. In BM-only deployments, the k8sManager is
not needed and the design reduces to fabric-manager-only.

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

5. **ExternalIPPool shared.** The fabric manager handles allocation for all
   resource types. One pool per region.

6. **Multiple hosting clusters.** Subnet creation provisions K8s overlay
   on each hosting cluster. VMs on different clusters share the subnet
   via the fabric.

7. **Internal IP pools.** Managed by managers with sensible defaults. Not
   part of the tenant API or NetworkClass spec.

8. **ExternalIP naming.** "External" means external to the VirtualNetwork —
   not necessarily internet-routable. Applies equally to air-gapped and
   internet-connected deployments.

9. **network_attachments immutability.** Network attachments are immutable
   after resource creation. Changing network attachment requires recreating
   the resource.

10. **Security enforcement.** The fabric is the single enforcement point
    for SecurityGroups. No separate K8s-level ACL needed — VMs are on the
    fabric.

11. **Per-resource NetworkAttachment types.** Separate proto messages
    (`ComputeNetworkAttachment`, `BareMetalNetworkAttachment`,
    `ClusterNetworkAttachment`) instead of one shared type. Each resource
    type has a different selector concept (virtual NIC, physical interface,
    node set) — a shared type with optional fields would accumulate
    dead weight per resource type.

## Test Plan

*Section to be completed when targeted at a release.*

## Graduation Criteria

*Section to be completed when targeted at a release.*

## Upgrade / Downgrade Strategy

*Section to be completed when targeted at a release.*

## Version Skew Strategy

*Section to be completed when targeted at a release.*

## Support Procedures

*Section to be completed when targeted at a release.*

## Infrastructure Needed

No additional infrastructure beyond existing OSAC components and managers.
