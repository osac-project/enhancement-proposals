---
title: k8s-only-k8s-manager
authors:
  - Dan Manor
creation-date: 2026-09-28
last-updated: 2026-09-28
tracking-link:
  - "https://redhat.atlassian.net/browse/OSAC-2069"
prd:
  - "prd.md"
---

# K8s Manager — K8s-Only

## Summary

This design describes how the k8s-only K8s manager implements its assigned
networking operations using Kubernetes-native resources — CUDNs,
NetworkPolicies, and MetalLB — without requiring an external fabric controller.
The shared manager contract is defined in the
[Unified Networking design](../OSAC-1433-unified-networking/design.md#manager-contract).
See [PRD](prd.md) for full requirements.

## Motivation

OSAC's networking architecture assumes a two-manager model: a fabric manager for
physical networking and a K8s manager for bridging the Kubernetes OVN overlay to
the fabric. Not every deployment has a physical fabric controller. Sites with
only KubeVirt VMs on a single hub cluster need tenant networking without the
operational cost of deploying and maintaining a Netris controller or equivalent.

The k8s-only backend fills this role by using the dispatcher's K8sFallback
mechanism: when no fabric manager is configured on a NetworkClass, the K8s manager
handles both its own responsibilities and the fabric manager's responsibilities
for resource kinds that support fallback. This gives tenants a consistent
networking API regardless of backend, while limiting the scope to what
Kubernetes-native resources can provide.

The k8s-only backend is deployed and operational, but its Kubernetes
resource mapping, role behavior, and limitations have not been formally
documented. This design records the as-built implementation.

### Goals

- Describe how the k8s-only backend implements supported operations using
  Kubernetes-native resources (CUDNs, NetworkPolicies, MetalLB)
- Define how the k8s-only installation uses K8sFallback and which resource
  kinds it can handle in the fabric role
- Establish the supported and unsupported operation set with concrete rejection
  behavior

### Non-Goals

- NATGateway support — the k8s-only backend does not and will not provide SNAT
- Bare-metal networking — physical switch configuration requires a fabric manager
- Multi-hub CUDN coordination
- IPv6 or dual-stack

## Proposal

### K8s-Only Behavior

In the k8s-only installation, the manager fills the fabric role for
fallback-enabled resources using the `agentless_net` roles. VirtualNetwork create
and delete are no-ops; Subnet provisioning creates a Namespace and CUDN;
NATGateway is rejected before an AAP job because the k8s-only manager has no
implementation for it.

CUDN-based VM attachment does not move a physical fabric port, so this
manager does not implement `move_network_attachment`. The current k8s-only flow does
not request lease discovery and its roles do not implement
`query_dhcp_lease`; add a K8s task if a service later routes lease-discovery
requests to this manager.

### API Extensions

The k8s-only backend introduces no new CRDs or API changes. It operates within
the existing OSAC networking API (VirtualNetwork, Subnet, SecurityGroup,
ExternalIP, ExternalIPPool, ExternalIPAttachment, NATGateway) defined by the
unified networking work (OSAC-1433).

The backend registers itself via ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-only-manager
  namespace: osac-operator-system
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: k8s_only
  description: "K8s-only networking — no external fabric controller required"
  capabilities: "ipv4"
```

The backend creates the following Kubernetes resources on the hub cluster as
side effects of provisioning OSAC networking resources:

| OSAC Resource | K8s Resources Created |
|---|---|
| VirtualNetwork | (none — logical grouping) |
| Subnet | Namespace, ClusterUserDefinedNetwork |
| SecurityGroup | NetworkPolicy |
| ExternalIPPool | MetalLB IPAddressPool, L2Advertisement |
| ExternalIP | Service (type: LoadBalancer) in metallb-system |
| ExternalIPAttachment | Service (type: LoadBalancer) in VM namespace |

## Implementation Details/Notes/Constraints

### Ansible Role Architecture

The k8s-only backend uses the `agentless_net` / `agentless_net.steps` Ansible
roles, which delegate to composable sub-roles based on resource kind:

```
agentless_net.steps
├── cudn_net            # VirtualNetwork, Subnet, SecurityGroup
│   ├── create_virtual_network.yaml   # no-op (logs success)
│   ├── delete_virtual_network.yaml   # no-op
│   ├── create_subnet.yaml            # → Namespace + CUDN
│   ├── delete_subnet.yaml            # → delete CUDN + Namespace
│   ├── create_security_group.yaml    # → network_policy role
│   └── delete_security_group.yaml    # → delete NetworkPolicy
└── metallb_l2          # ExternalIPPool, ExternalIP, ExternalIPAttachment
    ├── create_external_ip_pool.yaml  # → IPAddressPool + L2Advertisement
    ├── delete_external_ip_pool.yaml
    ├── allocate_external_ip.yaml     # → parking LB Service
    ├── release_external_ip.yaml
    ├── attach_external_ip.yaml       # → LB Service in VM namespace
    └── detach_external_ip.yaml       # → reverse attach
```

### VirtualNetwork — No-Op

Unlike the Netris backend (which creates a VPC/VRF), the k8s-only backend treats
VirtualNetwork as a logical grouping with no infrastructure. The Ansible role
logs success and returns immediately. L3 routing isolation between
VirtualNetworks is provided by keeping their Subnet CUDNs isolated. Sharing a
VirtualNetwork does not connect its Subnets in this phase.

### Subnet — CUDN with EVPN

Subnet provisioning creates two Kubernetes resources:

**1. Namespace** with the label
`k8s.ovn.org/primary-user-defined-network: ""` and a label matching the
subnet's ID for CUDN namespace selection:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: osac-subnet-<subnet-uuid>
  labels:
    k8s.ovn.org/primary-user-defined-network: ""
    osac.openshift.io/subnet-id: "<subnet-uuid>"
```

**2. ClusterUserDefinedNetwork (CUDN)** with Layer2 topology and EVPN backend:

```yaml
apiVersion: k8s.ovn.org/v1
kind: ClusterUserDefinedNetwork
metadata:
  name: osac-subnet-<subnet-uuid>
spec:
  namespaceSelector:
    matchLabels:
      osac.openshift.io/subnet-id: "<subnet-uuid>"
  network:
    topology: Layer2
    layer2:
      role: Primary
      subnets:
        - "<subnet-ipv4-cidr>"
    transport: EVPN
    evpn:
      vtep: tenant-vtep
      macVRF:
        vni: 100  # Replace with the VNI allocated for this Subnet.
```

The hub must have the `tenant-vtep` VTEP and EVPN route-advertisement setup
installed before this CUDN is created. OVN-Kubernetes advertises the Layer 2
network as a MAC-VRF, providing L2 connectivity to the fabric. VMs attached to
the same CUDN communicate at L2. Different CUDNs remain isolated by default;
this manager does not create a `ClusterNetworkConnect` or provide routed
connectivity between Subnets. See the
[OVN-Kubernetes CUDN EVPN configuration](https://ovn-kubernetes.io/master/features/bgp-integration/evpn/)
and [ClusterNetworkConnect behavior](https://ovn-kubernetes.io/master/features/user-defined-networks/cluster-network-connect/).

Subnet deletion reverses the process: delete the CUDN, then delete the namespace.

### SecurityGroup — NetworkPolicy

SecurityGroup rules are translated into Kubernetes NetworkPolicy resources in the
subnet's namespace. The `osac.templates.network_policy` role maps OSAC's
ingress/egress rule model (sourceCidr, destinationCidr, protocol, port range)
to NetworkPolicy `ingress` and `egress` rules.

This is a semantic difference from the Netris backend, which uses Netris ACL
rules. NetworkPolicy enforcement depends on the CNI (OVN-Kubernetes in this case)
and may differ in rule evaluation order, stateful tracking, and default behavior.

### ExternalIPPool — MetalLB IPAddressPool

ExternalIPPool creates a MetalLB IPAddressPool and L2Advertisement:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: osac-pool-<pool-uuid>
  namespace: metallb-system
spec:
  addresses:
    - "<cidr-from-spec>"
  autoAssign: false
  avoidBuggyIPs: true
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: osac-pool-<pool-uuid>
  namespace: metallb-system
spec:
  ipAddressPools:
    - osac-pool-<pool-uuid>
```

`autoAssign: false` prevents MetalLB from assigning IPs to arbitrary Services —
only OSAC-managed Services get IPs from this pool. `avoidBuggyIPs: true` skips
.0 and .255 addresses.

### ExternalIP — Parking Service Pattern

ExternalIP allocation uses a "parking" Service pattern:

1. Create a Service of type `LoadBalancer` in `metallb-system` with:
   - No selector (does not route traffic)
   - `metallb.universe.tf/address-pool` annotation pointing to the pool
   - `spec.loadBalancerIP` left empty (MetalLB assigns from pool)
2. Wait for MetalLB to assign an IP (poll `status.loadBalancer.ingress`)
3. Write the allocated address to the `osac.openshift.io/allocated-address`
   annotation on the ExternalIP CR
4. Pin the parking Service to the assigned address and add a stable sharing key
   for this ExternalIP before allowing an attachment. Use the address field or
   annotation supported by the deployed MetalLB version.

The parking Service reserves the IP in MetalLB's allocation table without routing
any traffic. This IP is later migrated to a target namespace when an
ExternalIPAttachment is created.

### ExternalIPAttachment — IP Migration to VM Namespace

When attaching an ExternalIP to a ComputeInstance:

1. Create a new Service of type `LoadBalancer` in the VM's namespace while the
   parking Service still reserves the address. Configure it with
   `spec.loadBalancerIP` set to the allocated address (or the equivalent
   explicit-address field for the pinned MetalLB version), a selector targeting
   the KubeVirt VM pod, and the pool annotation. Both Services use the same
   per-ExternalIP MetalLB sharing key (`metallb.io/allow-shared-ip` on current
   versions), have non-conflicting ports, and use
   `externalTrafficPolicy: Cluster`.
2. Wait until MetalLB reports the allocated address on the VM Service, then
   delete the parking Service in `metallb-system`.

Creating the destination service before releasing the parking reservation
prevents the address from being reassigned during the handoff. If the deployed
MetalLB version does not support sharing this address across the two Services,
the manager must use an explicit reservation mechanism that holds the address
until the destination claims it. It must not delete the parking Service first.
The current delete-then-create task order has a reassignment window; restoring
the parking Service after a failed create is compensating cleanup, not an
atomic handoff.

See the [MetalLB IP-sharing rules](https://metallb.io/usage/) for the sharing
key, port, and traffic-policy constraints.

The OVN-K EndpointSlice workaround is applied: the role ensures the
EndpointSlice for the Service correctly references the VM pod's IP, working around
a known OVN-Kubernetes issue where EndpointSlices for KubeVirt VMs may not
populate correctly.

Detaching reverses the handoff: create a parking Service with the same address
and sharing key, wait until MetalLB reports that address, then delete the VM
Service. If reservation restoration fails, keep the VM Service and retry; do not
leave the address unreserved.

**Limitation**: ExternalIPAttachment only supports `spec.computeInstance` targets.
`spec.cluster` and `spec.baremetalInstance` targets are not implemented in the
k8s-only backend. The role must reject these targets with a clear unsupported
target error before creating a Kubernetes Service; the resource then reports
Failed status.

### NATGateway — Rejected at Dispatch

NATGateway is the only resource kind with `K8sFallback: false`. When a tenant
creates a NATGateway on a k8s-only NetworkClass:

1. The controller resolves the NetworkClass via the dispatcher
2. The dispatcher finds no fabric manager and checks K8sFallback for NATGateway
3. K8sFallback is false — the dispatcher returns an error
4. The controller sets the NATGateway's status phase to `Failed` with a condition
   message indicating NATGateway requires a fabric manager

No provisioning job is created. The rejection is deterministic and immediate.

### Subnet CIDR Allocation

The k8s-only backend allocates subnet CIDRs from a provider-configurable pool
(default `10.0.0.0/8`). The CIDR allocator:
- Tracks allocated CIDRs to prevent overlaps
- Assigns the next available CIDR of the requested size
- Releases CIDRs when subnets are deleted

CIDRs are immutable after creation — the CRD's CEL validation rule
`self == oldSelf` prevents modification.

### Security Considerations

The k8s-only backend inherits the existing OSAC security model:

- **Credential management**: No external credentials are required (unlike Netris,
  which requires controller credentials). MetalLB and OVN-Kubernetes are
  cluster-local services that use Kubernetes RBAC.
- **Tenant isolation**: EVPN Layer 2 CUDNs provide isolated subnet networks.
  VMs in different CUDNs cannot communicate unless a network connection is
  explicitly configured; this manager does not configure cross-Subnet
  connections. OVN-Kubernetes enforces the isolation at the OVS datapath level.
- **Input validation**: CRD CEL validation rejects invalid CIDRs, non-canonical
  formats, and IPv6 addresses. The operator validates parent-child relationships
  (Subnet within VirtualNetwork CIDR range).

### Failure Handling and Recovery

| Failure Mode | Behavior | Recovery |
|---|---|---|
| CUDN creation fails (OVN-K issue) | Subnet status: Failed, condition message names the CUDN and K8s error | Operator retries on next reconciliation; CUDN creation is idempotent |
| Namespace creation fails | Subnet status: Failed | Operator retries; namespace creation is idempotent |
| MetalLB IPAddressPool fails | ExternalIPPool status: Failed | Operator retries; pool creation is idempotent |
| MetalLB IP exhaustion | ExternalIP status: Failed, condition: pool exhausted | Cloud Infrastructure Admin provisions additional IP space |
| Parking Service never gets IP | ExternalIP status: Progressing (stuck) | Timeout triggers Failed status; admin investigates MetalLB |
| OVN-K EndpointSlice workaround fails | ExternalIPAttachment status: Failed | Operator retries; workaround is idempotent |
| NATGateway on k8s-only | NATGateway status: Failed, message: requires fabric manager | No recovery — NATGateway is unsupported |
| AAP unreachable | Resource status: Progressing (stuck) | Operator retries with backoff; recovers when AAP is available |

All provisioning and deprovisioning operations are idempotent. Re-reconciling a
resource that already has its backing Kubernetes resources does not create
duplicates.

### RBAC / Tenancy

No RBAC or tenancy changes from the unified networking model. Tenant isolation
is enforced by:

- CUDN namespace selectors — each CUDN targets only its own namespace
- OVN-Kubernetes EVPN — provides datapath isolation between CUDNs
- `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` annotations
  on networking resources
- Operator RBAC: the operator's service account requires permissions to create
  Namespaces, CUDNs, NetworkPolicies, MetalLB IPAddressPools, L2Advertisements,
  and Services in `metallb-system` and VM namespaces

### Observability and Monitoring

No new observability changes beyond the standard OSAC networking monitoring. The
k8s-only backend surfaces operational state through:

- Resource status phases and conditions (standard across all backends)
- Provisioning job tracking via the `ProvisioningJobs` array
- AAP job logs for Ansible role execution details
- Kubernetes events on CUDNs, NetworkPolicies, and MetalLB resources

## Risks and Mitigations

### CUDN API stability

The CUDN API (`k8s.ovn.org/v1 ClusterUserDefinedNetwork`) is an OVN-Kubernetes
feature. If the API changes in a future OVN-K release, the Ansible roles must be
updated. Mitigated by tracking upstream OVN-K releases and testing against each
new version.

### NetworkPolicy vs ACL semantic differences

SecurityGroup translation to NetworkPolicy may produce different enforcement
behavior than Netris ACL translation. Tenants moving workloads between
k8s-only and Netris-backed deployments may observe behavioral differences in
firewall rule evaluation. Mitigated by documenting the difference and
standardizing the SecurityGroup enforcement model in a separate enhancement.

### MetalLB L2 scalability

MetalLB L2 mode uses ARP/NDP to announce IPs. Large numbers of ExternalIPs may
cause ARP table pressure on the L2 segment. Mitigated by the fact that
ExternalIPPools have bounded CIDR ranges and `avoidBuggyIPs: true` reduces the
usable IP count slightly.

### ExternalIPAttachment target limitations

The k8s-only backend only supports `spec.computeInstance` targets for
ExternalIPAttachment. Cluster and bare-metal targets are not implemented.
Tenants attempting these will see a provisioning failure rather than an
upfront API rejection. Mitigated by documenting the limitation and potentially
adding admission validation in a future enhancement.

## Drawbacks

The k8s-only backend provides a reduced feature set compared to fabric-backed
backends:

- No NATGateway — tenants lose managed outbound NAT with stable source IPs
- No bare-metal networking — physical switch configuration requires a fabric
  manager
- ExternalIPAttachment limited to VMs — no cluster-level external access
- NetworkPolicy enforcement may differ from Netris ACL enforcement

These limitations are inherent to operating without an external fabric controller.
The trade-off is reduced operational complexity (no Netris controller to deploy
and maintain) at the cost of reduced networking capability.

## Alternatives (Not Implemented)

### Direct OVN-K integration (no AAP)

The operator could create CUDNs and MetalLB resources directly via Kubernetes
API calls, bypassing AAP and Ansible roles. This would reduce latency and
eliminate the AAP dependency. Rejected because the OSAC provisioning framework
is built around AAP as the execution engine, and all other managers use the same
pattern. Bypassing AAP for one manager would create a second provisioning path
with different failure modes, monitoring, and debugging characteristics.

### Calico/Cilium-based isolation

Instead of OVN-Kubernetes CUDNs with EVPN, tenant isolation could be implemented
using Calico or Cilium network policies and VXLAN overlays. Rejected because OSAC
deploys on OpenShift, which uses OVN-Kubernetes as the default CNI. CUDNs with
EVPN are the native isolation mechanism, reducing the dependency surface.

### NATGateway via OVN logical router SNAT

OVN supports SNAT on logical routers. The k8s-only backend could configure OVN
SNAT rules directly to provide NATGateway support. Rejected because this would
require direct OVN northbound DB access, bypassing the OVN-Kubernetes abstraction
layer. This is fragile, unsupported by OVN-K, and could conflict with OVN-K's own
NAT management.

## Test Plan

### Unit Tests

K8s-only role tests should cover:

- VirtualNetwork create and delete tasks succeed without creating Kubernetes
  resources
- Subnet tasks render the expected Namespace labels and Layer2/EVPN CUDN
- SecurityGroup rules map to the expected NetworkPolicy
- ExternalIPPool and ExternalIP tasks render the MetalLB pool, advertisement,
  and parking Service with the expected allocation annotations
- ExternalIPAttachment moves the allocated address between the parking Service
  and the VM namespace Service

### Integration Tests

- Creating a VirtualNetwork on a k8s-only NetworkClass transitions to Ready
  (no-op backend)
- Creating a Subnet creates a Namespace and CUDN on the hub cluster; CUDN has
  correct Layer2 topology and subnet CIDRs
- Deleting a Subnet deletes the CUDN and Namespace
- Deleting a VirtualNetwork is blocked while child Subnets exist
- Creating a SecurityGroup creates a NetworkPolicy in the subnet namespace
- Creating an ExternalIPPool creates a MetalLB IPAddressPool and L2Advertisement
- Creating an ExternalIP creates a parking Service and allocates an IP
- Creating an ExternalIPAttachment migrates the IP from parking to VM namespace
- Creating a NATGateway on k8s-only transitions to Failed with correct error
- Mutating immutable fields (CIDR, NetworkClass, region) is rejected by CRD
  validation

### E2E Tests

- Tenant creates a VirtualNetwork and two Subnets; VMs on the same Subnet
  communicate at L2; VMs on different Subnets remain isolated
- VMs on different VirtualNetworks cannot reach each other's private addresses,
  even with overlapping CIDRs
- Tenant creates an ExternalIPPool, allocates an ExternalIP, and attaches it to
  a VM; inbound traffic reaches the VM
- Tenant attempts NATGateway creation on k8s-only NetworkClass; the resource
  reaches Failed with the unsupported resource and backend named before any
  provisioning job starts
- Tenant creates a SecurityGroup with ingress/egress rules; traffic is filtered
  according to the rules
- Full lifecycle: create VN → create Subnet → attach VM → verify connectivity →
  detach VM → delete Subnet → delete VN — no orphaned Kubernetes resources remain
