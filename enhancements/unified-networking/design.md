---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-06-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1029
prd: "prd.md"
see-also:
  - Networking API: /enhancements/networking
  - BareMetal Instance API: /enhancements/baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
  - VMaaS Networking: /enhancements/vmaas-networking
  - CaaS Networking: /enhancements/caas-networking
  - BMaaS Networking: /enhancements/bmaas-networking
  - Default Networking: /enhancements/default-networking
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
[Requirements Document (PRD)](prd.md).

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
[Requirements Document (PRD)](prd.md).

## Proposal

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for the deployment. Tenants never interact with it. One
NetworkClass per deployment.

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

The dispatch table above covers **networking resources only**. Compute
resources (ComputeInstance, BaremetalInstance, Cluster) handle per-instance
network attachment through their provisioning operators — see per-service
designs at [VMaaS](/enhancements/vmaas-networking),
[CaaS](/enhancements/caas-networking),
[BMaaS](/enhancements/bmaas-networking).

### Resource Hierarchy

```text
NetworkClass (per deployment, provider-only)

VirtualNetwork (tenant-managed, infrastructure-agnostic)
  ├── Subnet              → fabricManager + k8sManager
  ├── SecurityGroup       → fabricManager
  └── NATGateway          → fabricManager

ExternalIPPool (deployment-scoped, provider-managed)
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

ExternalIPPools are provider-managed and deployment-scoped. The fabric
manager handles ExternalIP allocation — one pool serves all resource types.

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
available interfaces via the HostType API — each BM HostType lists its
physical interfaces with name, role, and description (see
[HostType](#hosttype)). Given the interface identifiers, the tenant specifies which
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
- The `interface` must reference a valid interface name from the HostType's
  NetworkInterface list
- Multiple attachments without `interface` is invalid — if more than one
  attachment is specified, each must have an explicit `interface`
- The number of attachments cannot exceed the number of available interfaces

**Cluster:**

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --node-set workers=large,size=3 --name my-cluster
```

For v0.2, **CaaS supports BM node sets only**. VM-based cluster node sets
are architecturally possible but deferred. The fulfillment-service resolves
the interface from the HostType (`fabric_interface` — first interface with
role `fabric`). The operator handles agent selection and network attachment
(switch port configuration) before triggering the provisioning template.
See [CaaS Networking](/enhancements/caas-networking) for the detailed flow.

Cluster nodes have multiple physical interfaces. Unlike BaremetalInstance
(where the tenant specifies interfaces directly), for clusters the
**system** resolves the interface from the HostType's NetworkInterface list.
The tenant specifies which subnet to use (one per cluster); the system maps it to the
correct physical interfaces based on each node set's host type.

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

**Auto-provisioning lifecycle (external_ip_mode / nat_gateway_mode):**

Auto ExternalIP and NATGateway provisioning (described in per-service
EPs and [Default Networking](/enhancements/default-networking)) is a
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
| ComputeInstance | `VirtualMachineReference` set on CI CR | VM's IP from KubeVirt VMI status (OVN DHCP) |
| Cluster | `status.apiEndpoint` or `status.ingressEndpoint` populated on ClusterOrder CR | MetalLB allocates VIP from IPAddressPool, template discovers and writes to ClusterOrder status |
| BaremetalInstance | `status.networkAttachments[].ipAddress` populated for the primary interface | IP discovered from host/inventory system after DHCP assignment |

The controller uses the existing requeue pattern: if the precondition
is not met, it returns `ctrl.Result{RequeueAfter: interval}` and
retries until the target IP appears. This is the same pattern used
today for the `VirtualMachineReference` check on ComputeInstance
targets.

*IP discovery — DHCP-based host networking:*

All host-side IP assignment uses DHCP. The fabric's DHCP server (managed
by the fabric manager as part of the V-Net infrastructure) assigns IPs
to hosts when they boot on the subnet. OSAC does not pre-allocate IPs
or configure host-side networking — DHCP handles IP address, gateway,
prefix, and DNS automatically.

After the host receives its IP via DHCP, the IP is discovered and
written to the resource's CR status for two purposes:
- ExternalIPAttachment controller reads the primary IP for DNAT target
- Tenant visibility (API response includes the allocated IP)

IP discovery mechanism per service type:

| Service | Discovery mechanism | Source |
|---------|-------------------|--------|
| VMaaS | KubeVirt VMI status | OVN DHCP on CUDN overlay (existing pattern) |
| CaaS | Agent CR status | Assisted Installer agent reports network config |
| BMaaS | Host/inventory system | Ironic/Metal3 reports IP after provisioning |

The fabric manager's `create_network_attachment` role adds the host's
port to the V-Net (switch-side only). Once on the V-Net, the host
receives an IP from the fabric's DHCP server automatically.

*NATGateway controller preconditions:*

The NATGateway controller has one precondition before dispatching the
SNAT rule creation:

| Precondition | Source |
|-------------|--------|
| Referenced ExternalIP must be Allocated (have an allocated address) | ExternalIP CR status |

If the ExternalIP is not yet Allocated, the NATGateway controller
requeues. This prevents dispatching to AAP without a valid SNAT source
address.

*Auto-provisioned resource labeling:*

All auto-provisioned resources receive the label
`osac.openshift.io/auto-provisioned: "true"`. Auto-provisioned
ExternalIPs also receive a parent-resource label
`osac.openshift.io/auto-provisioned-for: <resource-id>` so that the
cleanup logic can find orphaned ExternalIPs directly, even if the
intermediate ExternalIPAttachment has already been deleted.

*Auto-provisioned resource cleanup on parent deletion:*

The parent resource's finalizer uses a phased requeue approach to
ensure correct ordering:

1. Query ExternalIPAttachments labeled `auto-provisioned` targeting
   this resource. Issue delete for each. Requeue.
2. On next reconcile: check if all ExternalIPAttachments are fully
   deleted (including their own finalizers completing the DNAT rule
   removal). If not, requeue.
3. Once all ExternalIPAttachments are gone: query ExternalIPs labeled
   `auto-provisioned-for: <this-resource>`. Issue delete for each.
   Requeue.
4. On next reconcile: check if all ExternalIPs are fully deleted. If
   not, requeue.
5. Once all ExternalIPs are gone: proceed with parent resource
   deletion.

NATGateway is NOT cleaned up — it is a shared per-VN resource that
may serve other resources on the same VirtualNetwork.

If cleanup fails permanently (after N retries): finalizer is removed,
parent resource deleted, orphaned resources left in cluster. Orphaned
resources are identifiable by the `auto-provisioned-for` label.

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

#### HostType

The `HostType` resource describes a class of hardware. For networking,
BM host types include a structured interface list:

```protobuf
message HostType {
  string id = 1;
  Metadata metadata = 2;
  string title = 3;
  string description = 4;
  repeated NetworkInterface interfaces = 5;  // BM only, empty for VM host types
}

message NetworkInterface {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0"
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string description = 3; // e.g., "100GbE fabric interface"
}
```

The `interfaces` list is only populated for BM host types. VM host types
have an empty list — VMs get virtual NICs from the CUDN overlay, not
physical interfaces. This serves as the BM-vs-VM discriminator: if a
HostType has interfaces → BM; if empty → VM.

Interfaces are ordered. When multiple interfaces share the same role
(e.g., two `fabric` interfaces), the first one in the list is the default
for that role — used by CaaS for automatic interface resolution.

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) — not tenant-attachable |

Roles are conventions, not enforced enums. The `lifecycle` interface is
used by the provisioning system (Ironic, Metal3) and should not appear
in `network_attachments`.

BMaaS: the tenant specifies interface names directly on
`BareMetalNetworkAttachment.interface`, validated against the HostType's
interface list. CaaS: the fulfillment-service resolves the interface
automatically (first `fabric`-role interface → stored as
`fabric_interface` on the node set definition).

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
  string interface = 3;                 // optional, immutable: physical interface from HostType
  bool primary = 4;                     // optional, immutable: designates default gateway
}
```

Each entry maps one physical interface to one subnet. The `interface`
field references a name from the HostType's NetworkInterface list.
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
}
```

A single attachment applies to the whole cluster — all node sets share the same subnet.
The `fabric_interface` is resolved by the fulfillment-service at creation time for each
node set from its host type (first interface with role `fabric` — see [HostType](#hosttype))
and stored on the node set definition. The tenant does not set this field.

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
  optional string ssh_public_key = 2;
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
  ClusterNetworkAttachment network_attachment = 4;  // singular, one per cluster
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
subnets. Cluster supports a single `network_attachment` — one subnet for all
node sets. Per-node-set subnet placement is not supported in v0.2. All
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

**IP assignment:** All resource types receive IPs via DHCP. For VMs,
OVN provides DHCP on the CUDN overlay. For BM servers and CaaS agents,
the fabric's DHCP server assigns IPs on the V-Net. The provisioning
template does NOT configure host-side networking (no static IP, gateway,
or DNS configuration) — DHCP handles it automatically.

| Subnet role | IP assignment provides (via DHCP) |
|-------------|---------------------------------------------|
| Primary | IP address + default gateway + DNS |
| Secondary | IP address + connected route only (no gateway) |

This ensures the resource has exactly one default route. Secondary subnets
are reachable via directly connected routes.

**ExternalIPAttachment:** When targeting a multi-homed resource, the fabric
manager creates a DNAT rule to the resource's primary subnet IP. The tenant
does not need to specify which interface — the primary designation
determines the target.

**Cluster networking:** `ClusterNetworkAttachment` is a single attachment
(one subnet for the whole cluster). Multi-NIC for individual cluster nodes
is handled by the CaaS template (provider-configured). The `primary` field
does not apply to `ClusterNetworkAttachment`.

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

5. **ExternalIPPool shared.** The fabric manager handles ExternalIP allocation
   for all resource types. One pool per deployment.

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
