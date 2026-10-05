---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-10-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - BareMetal Instance API: /enhancements/OSAC-1118-baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
  - VMaaS Networking: /enhancements/OSAC-1435-vmaas-networking
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - BMaaS Networking: /enhancements/OSAC-1437-bmaas-networking
  - Network Manager Integration Contract PRD: /enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/prd.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md
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

OSAC runs VMs on OpenShift using KubeVirt. In fabric-backed deployments, a
[K8s manager](#how-vms-join-the-fabric) connects the OVN overlay to the
physical fabric so VMs can share tenant subnets with fabric-connected
workloads. In K8s-only deployments, the K8s manager creates the primary
Subnet network directly on the hub cluster; there is no physical fabric
segment or bridge. The selected manager profile determines which resource
types and network operations the deployment supports.

The design introduces:

- **NetworkClass** with two fields: `fabricManager` (handles physical
  networking when configured) and `k8sManager` (provides Kubernetes-native VM
  networking, either alongside a fabric manager or as the sole manager in a
  K8s-only deployment)
- **Infrastructure-agnostic subnets** with a common API; fabric-backed profiles
  can place VMs, BM servers, and supported cluster nodes on the same subnet,
  while K8s-only support is limited to VM workloads on the hub
- **ExternalIP** (renamed from PublicIP) to clarify that addresses are
  external to the VirtualNetwork, not necessarily internet-routable
- **Uniform API** where the shared networking resource model serves VMaaS,
  CaaS, and BMaaS; every registered manager implements the complete operations
  and workload targets assigned to its role by the selected fixed profile.
  The normative operation and target matrix is in the
  [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

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

### Resource lifecycle enforcement

The fulfillment-service enforces strict dependency constraints on both
creation and deletion of networking resources at the API layer. Invalid
operations are rejected immediately — the system never accepts a request and
defers validation to asynchronous operator reconciliation.

- **Creation:** A resource referencing another resource can only be created
  when every referenced resource is in its terminal ready state. See
  [Creation Readiness Gates](#creation-readiness-gates) for the full table.
  There are no exceptions — internal flows (auto-provisioning and default
  networking) follow the same rules by creating resources in dependency
  order and waiting for each to reach its ready state before creating the
  next.
- **Deletion:** A resource can only be deleted when no other active resource
  references it (only dependency-graph leaves are deletable). See
  [Deletion Dependency Guards](#deletion-dependency-guards) for the full
  table and dependency chain. Auto-provisioned resources are the only
  resources subject to cascade deletion on parent removal.

### API operation constraint

Networking resources support create, read, and delete; read includes `List` and
`Get`. SecurityGroup additionally supports updating ingress and egress rules.
Its VirtualNetwork reference, metadata, and other immutable fields cannot be
changed after creation. Other networking resource specifications and metadata
are immutable and require delete/recreate to change. Workload network
attachments on `ComputeInstance`, `Cluster`, and `BaremetalInstance` are also
create-time-only. Controller status, conditions, readiness, and IP-discovery
updates remain internal reconciliation.

OSAC dispatches SecurityGroup rule updates to the role selected by the fixed
profile and supplies the desired resource state and current binding snapshot.
The manager's required policy semantics and convergence behavior are defined
by the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).
This design covers the API's update allowance and OSAC dispatch lifecycle; it
does not restate manager packet-policy requirements.

## Proposal

The core proposal describes provider-backed networking with the setting enabled. The feature-gated disabled mode is specified in the final subsection of this Proposal. [PRD: FR-10] [User]

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for the deployment. Tenants never interact with it. One
NetworkClass per deployment.

#### Manager Roles

OSAC networking has two manager roles, which can be combined or used in a
K8s-only profile:

- **Fabric Manager** — a single product (e.g., Netris, Neutron) that manages
  all physical networking: tenant isolation, ACLs, IP allocation, DNAT, SNAT,
  and inter-subnet L3 routing within a VirtualNetwork. The physical fabric is
  one infrastructure — one controller manages it all. When a VN has multiple
  subnets, the fabric manager provides the L3 gateway for each subnet and
  routes between them automatically.

- **K8s Manager** — provides Kubernetes-native VM networking. When paired with
  a fabric manager, it creates an overlay and connects it to the tenant fabric
  segment. When selected without a fabric manager, it creates the primary
  Subnet network on the hub cluster; no physical-fabric bridge is involved.
  MetalLB IPAddressPool CRs for CaaS VIP allocation are created by the Subnet
  controller at subnet creation time (gated on
  `NetworkClass.spec.vip_prefix_length`), independent of the k8sManager.

#### Why Two Managers?

The fabric is one product. You cannot have Netris handling isolation and
Neutron handling ACLs on the same switches — splitting into per-action
drivers does not reflect how physical networking works. A single
`fabricManager` field captures this reality.

The K8s manager serves two profiles: in a combined deployment it connects
the OVN overlay to the physical fabric; in a K8s-only deployment it provides
the primary Subnet network without fabric integration. The fabric-connection
mechanisms are described in [How VMs Join the
Fabric](#how-vms-join-the-fabric). A single `k8sManager` field selects the
Kubernetes implementation.

Only fabric-backed deployments place VMs on the physical fabric and apply the
fabric manager's behavior uniformly to fabric-connected workloads. K8s-only deployments use the fixed operation and target set defined for that profile; managers do not declare per-registration operation or target subsets.

#### NetworkClass Examples

**Netris + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: moc-region-1
fabricManager: netris
k8sManager: cudn_evpn
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

**Agentless VLAN + CUDN (invalid pair):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: vlan-region-1
fabricManager: agentless_net
k8sManager: cudn_evpn
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

OSAC rejects this selection before AAP: Agentless VLAN is VLAN-based, does not
declare `evpn-vxlan`, and does not mutually declare `cudn_evpn` as a tested
compatible K8s Manager. A different Fabric/K8s pair is eligible only when its
registrations mutually name one another and its exact release versions have
passed the pair integration suite.

**K8s-only deployment (VMs on the hub; no physical fabric):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: k8s-region-1
k8sManager: k8s_only
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
fabricManager: netris
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

#### Manager Capabilities and Registration

The operator resolves provider-selected Fabric and K8s manager names from
role-labeled ConfigMaps in the operator namespace. The selected manager
declarations determine the effective NetworkClass capabilities: when both
roles are configured, OSAC intersects their address-family capabilities; a
single-role profile uses that role's declarations. The supported deployment
boundary remains IPv4-only. [Codebase: osac-operator/pkg/networkmanager]

Manager registration identifies the implementation and its role; it does not
declare an operation or workload-target subset. A combined Fabric/K8s profile
requires the roles to mutually declare each other's logical manager name as a
tested compatible peer, in addition to declaring the required technical
capabilities. Shared capabilities alone do not make a pair compatible. OSAC
validates the pair and every request against the selected profile's fixed
dispatch plan before starting AAP, and every implementation must provide the
complete operation and target set assigned to its role. The complete
registration schema, compatibility rules, operation vocabulary, and
validation behavior are defined in the
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md);
this design describes how OSAC consumes the registration.

#### Manager discovery during Enclave installation

The Enclave installation flow obtains manager choices from the same validated
registration inventory the OSAC dispatcher uses. For a combined profile, it
shows only mutually declared Fabric/K8s pairs and gives the registration
diagnostic when no pair is eligible. OSAC exposes each valid
registration's logical name, role, description, contract version,
capabilities, and peer-compatibility declarations to the installer. The UI
does not maintain a product-specific list. It filters a combined profile to
mutually declared Fabric/K8s pairs that meet the required capabilities; a
capability match alone is not enough. A newly installed conforming manager
becomes selectable with its declared, tested peers when its registration is
available, without an Enclave UI code change. If no
valid registration meets a required role and profile, installation cannot
select that profile and must show the registration or compatibility
diagnostic. The selected logical manager names are written to the provider's
NetworkClass configuration. Registration validation and profile requirements
remain defined by the
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

### How VMs Join the Fabric

OSAC runs VMs on OpenShift using KubeVirt. Each VM is encapsulated in a pod
whose networking is managed by OVN-Kubernetes. By default, VM IP addresses
exist only within the OVN overlay and are not visible on the physical
fabric. The k8sManager bridges this overlay to the fabric so that VMs
become first-class fabric participants — reachable at their subnet IP from
any other resource on the same fabric segment.

Several mechanisms can achieve this bridging. The Fabric Manager and K8s
Manager are independent implementations selected as a pair only when both
registrations declare mutual compatibility and the pair has passed its
release-specific integration suite. In the EVPN profile, Fabric creates the
physical segment and writes the shared contract ConfigMap containing its
Subnet VNIs, route targets, and reserved address ranges; the K8s Manager reads
that object to configure the overlay. OSAC validates the object and controls
its lifecycle between the two AAP jobs. The exact schema and pair rules are in
the [Network Manager Integration
Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).
Implementations are selectable only through a standardized contract v1
profile. Contract v1 defines Fabric-only IPv4, Fabric-backed EVPN, and K8s-only
IPv4 profiles. Other
mechanisms listed below are technical alternatives, not selectable contract v1
profiles until their registration capability and cross-manager handoff are
standardized.

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
[CUDN with VRF-lite setup guide](https://github.com/osac-project/docs/blob/main/networking/setup-bpg-vrf-lite/README.md)
for a working example.

**DPU-based bridging.** SmartNICs (DPUs) offload the OVN-to-fabric bridging
to hardware. The DPU handles packet encapsulation/decapsulation between OVN
and the physical network, providing line-rate bridging without host CPU
overhead.

These mechanisms apply only when a fabric manager is configured. In that
profile, the provider configures the selected mechanism as part of the
k8sManager installation, and VMs on the Subnet become reachable from the
fabric. K8s-only deployments use a primary CUDN and do not use this
fabric-connection path.

### Infrastructure-Agnostic Subnets

`VirtualNetwork` and `Subnet` provide a common resource model; the selected
manager profile determines how they are realized.

- **Fabric-backed profile:** the fabric manager provisions the tenant segment.
  If a K8s manager is selected, it also creates the VM overlay and bridges it
  to that fabric segment. Bare-metal workloads and supported cluster nodes use
  the fabric network.
- **K8s-only profile:** the K8s manager creates a namespace and primary CUDN
  for the Subnet. It does not create or bridge to a physical fabric segment.
  This profile provides VM networking on the hub cluster; bare-metal and
  fabric-dependent cluster networking are outside its scope.

### Dispatcher (Operator Composition Logic)

NetworkClass selects the provider-configured Fabric Manager and optional K8s
Manager. For each networking operation, the operator resolves the exact
registration and uses the fixed OSAC dispatch rules to select its manager role.
In a fabric-backed profile, the Fabric Manager handles physical-fabric
operations and a configured K8s Manager also handles the K8s Subnet operation.
In a K8s-only profile, the fixed dispatcher routes only its supported fallback
operations to the K8s Manager; NATGateway and physical port movement require a
Fabric Manager.

Before creating an AAP job, the operator checks the requested operation and
workload target against the selected profile's fixed dispatch matrix and
resolves the required manager registration. Every conforming implementation
must support the complete operation and target set assigned to its role; a
registration does not declare a backend-specific subset. Work unavailable in
the selected profile fails with a diagnostic and is not sent to another
manager. The only K8s fallback is the one explicitly defined for a K8s-only
profile by the dispatch rules. A registered implementation missing a required
task is nonconforming and its AAP job fails.

The NATGateway reconciler must resolve and validate its dispatch plan before
provisioning. Its current path inherits the strategy from the parent
VirtualNetwork without checking the Fabric-only requirement, so K8s-only
NATGateway requests can reach AAP; contract enforcement closes this wiring gap
and rejects the profile-operation mismatch before a job starts.

For supported work, the controller sends the full resource to the shared AAP
provider. In the EVPN Subnet create flow it first invokes Fabric, validates
the standard handoff ConfigMap, then invokes K8s with a version-pinned ConfigMap
reference; the K8s role reads the same object. Delete runs K8s cleanup before
Fabric cleanup, and OSAC removes the ConfigMap only after both succeed. Other
operations use the fixed operation playbook and selected collection task. AAP
job state and defined result artifacts return through the existing
provisioning provider, and the operator updates resource status and job
history. The manager owns backend-specific reconciliation; OSAC owns the API
resource lifecycle, pair validation, handoff validation, and status.

The [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md)
is normative for manager registration, mandatory role operations and targets,
AAP task inputs and outputs, retry behavior, and implementation conformance.
This design owns the profile composition and OSAC-to-AAP orchestration flow.
ComputeInstance, BaremetalInstance, and Cluster attachment provisioning also
uses the shared manager contract through their service-specific operators; see
[VMaaS](/enhancements/OSAC-1435-vmaas-networking),
[CaaS](/enhancements/OSAC-1436-caas-networking), and
[BMaaS](/enhancements/OSAC-1437-bmaas-networking).

### Resource Hierarchy

`NetworkClass` (per deployment, provider-only)

`VirtualNetwork` (tenant-managed)
  ├── `Subnet`              → fabric manager + optional K8s manager; or primary CUDN in K8s-only
  ├── `SecurityGroup`       → fabric manager, or K8s fallback
  └── `NATGateway`          → fabric manager only

`ExternalIPPool` (deployment-scoped, provider-managed)
  └── `ExternalIP` (tenant-managed) → fabric manager, or K8s fallback

`ExternalIPAttachment` (tenant-managed)
  → fabric manager, or K8s fallback for ComputeInstance targets

### ExternalIPPool

"External" in ExternalIPPool/ExternalIP means **external to the
VirtualNetwork**. In the supported connected deployment boundary, the
provider creates pools with addresses routable in the provider's connected
network. The API does not require Internet reachability, but air-gapped and
disconnected networking deployments are not supported.

ExternalIPPools are provider-managed and deployment-scoped. The NetworkClass
profile selects the manager that handles ExternalIP allocation and release;
the profiles defined in this design assign those operations to the Fabric
Manager. One pool serves all resource types.
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

#### ExternalIP Address Selection and Ownership

The ExternalIPPool defines the eligible range; it does not choose the concrete
address. For `external_ip.allocate`, OSAC supplies the ExternalIP UID and the
resolved pool UID and canonical IPv4 CIDR to the manager selected by the
NetworkClass profile. The manager chooses a free address in that pool and
durably reserves it under the ExternalIP UID. Allocations from the same pool
must be unique, and retrying the same UID must return the same reservation.
The selection order is implementation-specific; the contract does not require
first-fit or any other particular algorithm.

After confirming the reservation, the manager writes the address to the
`osac.openshift.io/allocated-address` annotation on the same ExternalIP CR.
The patch must be guarded by the supplied resource UID and generation, and
must not change the spec, status, or other annotations. The manager reports
success only after the provider reservation and annotation write succeed. The
common `osac_result` envelope identifies the operation, resource UID, and
generation; it carries no address payload.

After AAP reports success, OSAC validates the result envelope against the
current ExternalIP, reads the annotation, and validates canonical IPv4 form
and membership in the selected pool. Only then does OSAC write
`ExternalIP.status.address` and report the ExternalIP as **Allocated**. OSAC
does not write the allocated-address annotation. A missing or invalid
annotation leaves the ExternalIP non-ready with no accepted address. A retry
for the same UID reuses the provider reservation and retries the annotation
write. If the pool has no free address, the manager returns a failure with a
diagnostic and no success result.

The fulfillment-service reserves API-side pool capacity in the transaction
that creates the ExternalIP. On deletion while provider networking is enabled,
OSAC first requires dependent ExternalIPAttachments and NATGateways to be
removed, then invokes `external_ip.release`. The manager removes the UID-owned
provider reservation and reports success only after the address is absent.
OSAC returns API-side pool capacity only after successful AAP completion and
validation of an `osac_result` with `schemaVersion: "v1"`,
`operation: external_ip.release`, the current ExternalIP UID in `resourceUID`,
the dispatched generation in `observedGeneration`, and empty `data`. The
successful result asserts that the UID-owned provider reservation is absent;
no separate `RELEASED` data field is required. A failed job or missing,
malformed, stale, or mismatched envelope keeps capacity held for
reconciliation.

While provider networking is disabled, deleting an ExternalIP completes its
OSAC object deletion without dispatching `external_ip.release`, and releases
its API-side pool-capacity reservation when the logical object is deleted. If
the manager had confirmed an allocation before disablement, its provider
reservation may remain after OSAC deletion and require manual or provider-side
cleanup. Releasing the OSAC capacity slot does not release that address in the
provider or guarantee that the provider can allocate it again. [User]

### End-to-End Flows

This section shows how the unified networking API works from the tenant's
perspective. The API flow is shared, while the resource provisioning path and operation/target assignments depend on the fixed manager profile. K8s-only
behavior is called out where it differs from fabric-backed behavior.

These provider setup, networking setup, attachment, and external access flows
describe `global.networking.provisioningEnabled=true`. The disabled branch is
defined in [Provider Networking Control](#provider-networking-control); API
readiness, validation, and deletion constraints apply in both modes. [User]

#### Provider Setup

1. Provider deploys the hub, selected networking managers, and any provider-owned
   networking services required by the chosen profile. Fabric-backed profiles
   install a fabric controller; K8s-only uses the K8s manager without one.
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

For a fabric-backed profile, the fabric manager registers the IP range in its
IPAM. For K8s-only, the K8s manager provisions the provider's ExternalIPPool
through MetalLB.

#### Networking Setup (Fabric-Backed Profiles)

The following VirtualNetwork, Subnet, and SecurityGroup realization describes
fabric-backed profiles. The tenant-facing resource API is shared. The K8s-only
realization uses a logical VirtualNetwork, a primary CUDN per Subnet, and
NetworkPolicy; its Kubernetes-native mappings are summarized below.

**Create VirtualNetwork:**

```bash
osac create virtualnetwork --network-class moc-region-1 --cidr 10.0.0.0/16 \
  --name my-net
```

A fabric-backed manager creates an isolated tenant segment. The K8s-only
manager treats the VirtualNetwork as a logical grouping and creates no
VirtualNetwork Kubernetes object.

**Create Subnet:**

```bash
osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 \
  --name my-subnet
```

The fabric manager creates a subnet segment. If the profile has
a K8s manager, it also creates a VM overlay and connects it to that segment.
In a fabric-backed profile, VMs on the overlay and supported fabric-connected
workloads can share the Subnet. In K8s-only, the K8s manager creates a primary
Layer2 CUDN and namespace on the hub; no physical segment is created.

**Create SecurityGroup:**

```bash
osac create security-group --virtual-network my-net --name my-sg \
  --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
```

OSAC sends SecurityGroup creation, rule updates, binding additions/removals, and
deletion to the manager role assigned by the selected profile. It supplies the
complete current binding snapshot, gates attachment readiness on successful
policy application, and removes a workload from the network before dispatching
the snapshot that omits it. The selected manager applies policy and returns the
contract result; the Network Manager Integration Contract defines the exact
policy semantics, inputs, targets, task entry points, results, and retry
behavior.

#### Resource Creation (Fabric-Backed Profiles)

The following VM, bare-metal, and cluster examples apply to profiles that
support those workload targets. The shared API steps remain the same, while
manager profiles limit which targets can be placed on a Subnet.

**ComputeInstance (VM):**

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --name my-vm
```

In a combined profile, the VM is placed in the K8s overlay and its network
is connected to the fabric subnet. In K8s-only, the VM launcher pod uses the
primary CUDN in its Subnet namespace on the hub and receives an address from
OVN-Kubernetes DHCP.

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
  --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
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
  --network-attachment subnet=my-subnet,security-groups=my-sg \
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

In the fabric-backed profiles shown here, supported workloads are connected
to the fabric subnet and the fabric manager applies its network behavior to
them. K8s-only VMs remain on their primary CUDN on the hub and use the
Kubernetes-native services described in this design.

#### External Access (Fabric-Backed Profiles)

The fabric-backed path below describes DNAT and SNAT for workload targets
supported by that profile. K8s-only uses MetalLB for VM ExternalIP attachments
and does not support NATGateway.

**Allocate ExternalIP:**

```bash
osac create externalip --pool external-pool-1 --name my-ip
```

The manager selected by the NetworkClass profile reserves a free address from
the selected pool and writes it to the ExternalIP annotation. OSAC validates
that annotation and writes status as defined in [ExternalIP Address Selection
and Ownership](#externalip-address-selection-and-ownership) (e.g.,
203.0.113.45).

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

ExternalIPAttachments for clusters follow the same creation readiness
rules as all other resources: the cluster must be in Ready state before
an ExternalIPAttachment targeting it can be created. Auto-provisioned
ExternalIPAttachments (via `auto_external_ip_attachment`) also follow
the readiness rules — they are created by the fulfillment-service
internal reconciler only after both the ExternalIP is Allocated and the
cluster is Ready (see below).

**Auto-provisioning lifecycle (auto_external_ip_attachment):**

Auto ExternalIP attachment provisioning (described in per-service
EPs and [Default Networking](/enhancements/OSAC-1433-default-networking)) is a
multi-step process that follows the same creation readiness rules as
tenant-initiated operations. The fulfillment-service controls the
timing and creates each resource only after its dependencies are ready.

*Step 1 — synchronous (during the create API call):*

The fulfillment-service validates pool capacity, creates ExternalIP
records in PostgreSQL, and decrements pool capacity — within the same
API transaction as the workload creation. If the pool is exhausted, the
call fails and no resources are persisted (including the parent
workload). The ExternalIP starts in **Pending** state. For clusters,
two ExternalIPs are created (one for API, one for ingress). For
ComputeInstances and BaremetalInstances, one ExternalIP is created.

ExternalIPAttachments are **not** created at this point — their
dependencies (ExternalIP Allocated + target Ready) are not yet met.

*Step 2 — asynchronous (ExternalIP reconciliation):*

The fulfillment-service reconciler pushes ExternalIP CRs to the hub
cluster. The osac-operator dispatches `external_ip.allocate` to the manager
selected by the NetworkClass profile. The manager durably reserves an address
and writes the standard allocated-address annotation. OSAC validates the job
result and annotation, then writes status under [ExternalIP Address Selection
and Ownership](#externalip-address-selection-and-ownership). The ExternalIP
then transitions to **Allocated**, and the fulfillment-service receives the
status update via Signal RPC.

*Step 3 — asynchronous (deferred ExternalIPAttachment creation):*

Once both prerequisites are met — the ExternalIP is **Allocated** and
the target workload is **Ready** — a fulfillment-service parent-resource
reconciler creates the ExternalIPAttachment. This new reconciler is separate
from the existing ExternalIP and ExternalIPAttachment synchronization
controllers. It follows the standard creation readiness gate: the attachment
is only persisted when
its ExternalIP is Allocated and its target is Ready. The
ExternalIPAttachment starts in **Pending** state and is pushed to the
hub cluster by the reconciler.

*Step 4 — asynchronous (ExternalIPAttachment reconciliation):*

The osac-operator ExternalIPAttachment controller verifies its
preconditions (ExternalIP Allocated + target has a known IP) and
dispatches to AAP → fabric manager creates the DNAT rule →
ExternalIPAttachment transitions to **Ready**.

*ExternalIPAttachment controller preconditions per target type:*

| Target type | Required precondition | Source of target IP |
|-------------|----------------------|---------------------|
| ComputeInstance | `compute_network_attachment_statuses` populated with primary attachment's `ip_address` | Feedback controller reads KubeVirt VMI network status, writes `ComputeNetworkAttachmentStatus` per attachment |
| Cluster | `status.apiEndpoint` or `status.ingressEndpoint` populated on ClusterOrder CR | MetalLB allocates VIP from IPAddressPool, template discovers and writes to ClusterOrder status |
| BaremetalInstance | `status.networkAttachmentStatuses[].ipAddress` populated for the primary interface | BMaaS calls the contract's `dhcp_lease.query` with the authoritative interface MAC and SubnetRef, requires exactly one lease, and writes the address to CR status |

The controller uses the existing requeue pattern: if the precondition
is not met, it returns `ctrl.Result{RequeueAfter: interval}` and
retries until the target IP appears. This is the same pattern used
today for the `VirtualMachineReference` check on ComputeInstance
targets.

*IP discovery — DHCP-based host networking:*

IP assignment follows the selected manager profile. K8s-only VM addresses
come from OVN-Kubernetes DHCP on the primary CUDN. Fabric-managed BM servers
and CaaS agents receive addresses from the fabric DHCP server on the Subnet.
OSAC does not pre-allocate host addresses or configure host-side networking;
the selected DHCP service supplies the address, gateway, prefix, and DNS.

After the host receives its IP via DHCP, the IP is discovered and
written to the resource's CR status for two purposes:
- ExternalIPAttachment controller reads the primary IP for DNAT target
- Tenant visibility (API response includes the allocated IP)

IP discovery mechanism per service type:

| Service | Discovery source | Who writes status | Status field |
|---------|-----------------|-------------------|-------------|
| VMaaS | KubeVirt VMI `status.interfaces[].ipAddress` | osac-operator feedback controller → Signal RPC → fulfillment-service | `ComputeInstanceStatus.compute_network_attachment_statuses[].ip_address` |
| CaaS | BMaaS discovers each worker's lease for its BaremetalInstance attachment through the Fabric Manager's `dhcp_lease.query` operation. The CaaS BareMetalWorkerReconciler correlates the Agent to that BaremetalInstance by MAC. | BMaaS writes the BaremetalInstance attachment status; the CaaS worker flow owns Agent/ClusterOrder correlation and status. | BaremetalInstance attachment status is the authoritative worker address; Agent identity is correlated by MAC. |
| BMaaS | Operator queries the Fabric Manager's DHCP lease API through the contract's `dhcp_lease.query` operation after provisioning completes; matches the authoritative interface MAC and SubnetRef to exactly one lease. A missing or ambiguous match fails with a diagnostic. | bare-metal-fulfillment-operator dispatches `dhcp_lease.query` → writes to CR status → feedback controller → Signal RPC → fulfillment-service | `BareMetalInstanceStatus.network_attachment_statuses[].ip_address` |

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
automatically. One AAP task entry point serves both directions. OSAC supplies
the contract-defined `context.attachment.action` value (`ATTACH` or `DETACH`);
the manager does not infer the action from `deletionTimestamp`. See
[BMaaS — Provisioning Network and Port
Moves](/enhancements/OSAC-1437-bmaas-networking/design.md#provisioning-network-and-port-moves).

IP discovery for BMaaS is a separate contract operation. After
`reconcileProvisioning` completes and the host has received a DHCP
lease, the operator dispatches `dhcp_lease.query` with the attachment's
authoritative interface MAC and SubnetRef. The Fabric Manager queries its
lease source and returns exactly one lease for that binding. The operator
supplies the MAC from the host's `osac.openshift.io/interface-macs`
BareMetalHost annotation. Display names and provider server names are not
lease identity and must not be used as a fallback.

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

The fabric manager creates a SNAT rule for the VN: egress from the VN's CIDR
is source-NATted to the ExternalIP. This applies to workloads supported by
that fabric-backed profile. K8s-only does not support NATGateway.

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
(`subnet`, `security_groups`) are shared, but each type adds
resource-specific fields. `network_attachments` are immutable after
resource creation — changing network attachment requires recreating the
resource. VMaaS and BMaaS keep repeated fields for wire/API compatibility but
enforce a maximum of one entry. CaaS uses its existing singular field.

**ComputeNetworkAttachment** (for ComputeInstance):

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
}
```

The repeated field is retained for compatibility, but at most one entry is
accepted. The sole entry is the VM's default route/primary attachment; the
VMaaS attachment message has no primary field.

**BareMetalNetworkAttachment** (for BaremetalInstance):

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
  string interface = 3;                 // optional, immutable: physical port name from BareMetalInstanceType
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
  SubnetLocalReference subnet = 1;                         // Required after resolution; immutable after creation
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
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
| One attachment with no Subnet | Default only the Subnet; preserve supplied SecurityGroups and, for BMaaS, the supplied interface. |
| One attachment with no SecurityGroups | Do not add SecurityGroups. An empty list is allowed on the tenant's default VirtualNetwork; a non-default VirtualNetwork requires caller-supplied SecurityGroups from that VirtualNetwork. |
| One BMaaS attachment with no interface | Default only the interface to the first `fabric` port from `BareMetalInstanceType.network_ports`. |
| One complete attachment | Preserve all supplied values and validate readiness, tenant scope, and VirtualNetwork relationships. |

An explicitly empty `security_groups` list remains empty. SecurityGroups are
never created or injected by attachment resolution. If a required default
Subnet or BMaaS fabric interface is absent or not Ready, creation fails with a
validation or precondition error. The fully resolved attachment is stored
with the workload and is immutable after creation.

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

#### Deletion Dependency Guards

The fulfillment-service enforces resource dependency constraints at the API
layer. A delete request is rejected immediately with a `FailedPrecondition`
error if any active resource still references the target. Only
dependency-graph leaves — resources with no active dependents — are
deletable. The error response includes the blocking resource type so the
caller knows what to remove first.

**API-layer deletion guards (fulfillment-service):**

| Resource | Reject delete if active … exist |
|---|---|
| VirtualNetwork | Subnets, SecurityGroups, NATGateways, or FabricDomains referencing this VirtualNetwork |
| Subnet | ComputeInstances, Clusters, or BaremetalInstances with network attachments referencing this Subnet |
| SecurityGroup | ComputeInstances, Clusters, or BaremetalInstances with network attachments referencing this SecurityGroup |
| ExternalIP | ExternalIPAttachments or NATGateways referencing this ExternalIP |
| ExternalIPPool | ExternalIPs referencing this pool |
| ExternalIPAttachment | (leaf — no dependents, always deletable) |
| NATGateway | (leaf — no dependents, always deletable) |
| ComputeInstance / Cluster / BaremetalInstance | Manually-created ExternalIPAttachments targeting this resource |
| NetworkClass | VirtualNetworks referencing this NetworkClass |

"Active" means the resource exists and has not been fully deleted (i.e., is
not archived). A resource that is itself being deleted (has
`deletion_timestamp` set but is still being deprovisioned) counts as active
for the purpose of these guards — the parent cannot be deleted until the
child is fully gone, not merely marked for deletion.

**Exception — auto-provisioned resources:** Resources created by the system
via `auto_external_ip_attachment` (labeled
`osac.openshift.io/auto-created`) are cascade-deleted when their parent
workload is deleted. The parent workload's delete handler in
fulfillment-service initiates the cascade, and the operator-side finalizer
executes it in dependency order (ExternalIPAttachment first, then
ExternalIP). Because the system created these resources and controls the
full dependency chain, cascade deletion is safe. Manually-created
ExternalIPAttachments targeting the same workload are NOT cascade-deleted —
they block the workload's deletion until the tenant removes them.

**Operator-side guards (defense in depth):** The operator controllers retain
their existing child-CR gates as a safety net. Each parent controller lists
child CRs before triggering the AAP deprovision job; if any children still
exist, the controller requeues instead of dispatching. This is defense in
depth — the fulfillment-service API-layer rejection is the primary
enforcement point.

The full dependency chain (delete order, leaf first):

```text
ExternalIPAttachment (leaf)
  must be gone before --> ExternalIP
  must be gone before --> target ComputeInstance / Cluster / BaremetalInstance
                          (only manually-created attachments block target deletion;
                           auto-created attachments are cascade-deleted)

NATGateway (leaf)
  must be gone before --> ExternalIP
  must be gone before --> VirtualNetwork

FabricDomain (leaf)
  must be gone before --> VirtualNetwork

SecurityGroup
  must be gone before --> VirtualNetwork
  (blocked by ComputeInstances / Clusters / BaremetalInstances referencing it)

ComputeInstance / Cluster / BaremetalInstance
  must be gone before --> Subnet
  (blocked by manually-created ExternalIPAttachments targeting it)

Subnet
  must be gone before --> VirtualNetwork

ExternalIP
  must be gone before --> ExternalIPPool

VirtualNetwork
  must be gone before --> NetworkClass

NetworkClass (provider-managed, delete last)
```

#### Creation Readiness Gates

The fulfillment-service enforces that every referenced resource is in its
terminal ready state before allowing creation. A create request is rejected
immediately with a `FailedPrecondition` error if any referenced resource
does not exist, is not ready, or is being deleted.

**API-layer creation gates (fulfillment-service):**

| Created resource | Referenced resource | Required state |
|---|---|---|
| VirtualNetwork | NetworkClass | Ready |
| Subnet | VirtualNetwork | Ready |
| SecurityGroup | VirtualNetwork | Ready |
| NATGateway | VirtualNetwork | Ready |
| NATGateway | ExternalIP | Allocated |
| ExternalIP | ExternalIPPool | Ready |
| ExternalIPAttachment | ExternalIP | Allocated |
| ExternalIPAttachment | Target (ComputeInstance / Cluster / BaremetalInstance) | Ready |
| ComputeInstance | Subnet | Ready |
| ComputeInstance | SecurityGroup(s) | Ready |
| Cluster | Subnet | Ready |
| Cluster | SecurityGroup(s) | Ready |
| BaremetalInstance | Subnet | Ready |
| BaremetalInstance | SecurityGroup(s) | Ready |
| FabricDomain | VirtualNetwork | Ready |

The fulfillment-service checks these conditions synchronously during the
create API call. If any referenced resource is in Pending, Failed, or
Deleting state, the request is rejected before persistence. The error
response includes the referenced resource and its current state.

There are no exceptions to the creation readiness rule. Internal
fulfillment-service flows — `auto_external_ip_attachment` and default
networking tenant onboarding — follow the same readiness gates by
creating resources in dependency order and waiting for each to reach its
ready state before creating the next. See
[Auto-provisioning lifecycle](#auto-provisioning-lifecycle-auto_external_ip_attachment)
and [Default Resource Lifecycle](/enhancements/OSAC-1433-default-networking/design.md#default-resource-lifecycle)
for the stepped creation flows.

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

**IP assignment:** Workload IP assignment follows the selected network
profile. For VMs on a K8s-only primary CUDN, OVN provides DHCP. For
fabric-managed BM servers and CaaS agents, the fabric's DHCP server assigns
IPs on the network segment. The provisioning
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

Multiple hosting clusters are supported for fabric-backed deployments where
the networking feature explicitly supports them. At subnet creation, the
k8sManager creates an overlay on each hosting cluster and bridges it to the
fabric segment. K8s-only networking targets the hub cluster and does not
provide this cross-hosting-cluster path.

#### Hub Selection (CR Placement)

The fulfillment-controller creates K8s CRs on the single registered hub
cluster in a supported networking deployment. All networking resources
(VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP,
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
| K8s-to-fabric bridge failure (fabric-backed profile) | VMs unreachable from fabric | The selected k8sManager validates bridge connectivity at subnet creation; subnet stays Pending until bridge is confirmed |
| CaaS endpoint sequencing | ExternalIPAttachments wait for both an Allocated ExternalIP and a Ready cluster | The fulfillment-service creates auto-provisioned attachments after both dependencies are ready; status updates trigger the internal reconciler |
| Attachment target lifecycle | A target can be deleted while attachment cleanup is still in progress | API guards block deletion for manually created attachments; auto-created attachments cascade in dependency order, with operator child checks as defense in depth |
| CIDR overlap | Overlapping subnets cause routing ambiguity | Operator validates at creation time; rejected with clear error |

### Drawbacks

Fabric-backed deployments that host VMs require K8s-to-fabric connectivity.
K8s-only deployments instead use a primary CUDN and do not require a physical
fabric bridge. BM-only deployments can use the fabric manager without a K8s
manager. MetalLB IPAddressPool creation for CaaS VIP allocation is handled by
the Subnet controller, not the k8sManager.

The trade-off is a shared tenant-facing resource model with profile-specific
realization. Fabric-backed deployments provide cross-service subnet
placement; K8s-only deployments provide VM networking through a primary CUDN
without physical-fabric integration. Each profile must expose and enforce its
supported target set.

### Provider Networking Control

`global.networking.provisioningEnabled` is the shared Helm boolean and
defaults to `true`. Enclave Wizard presents the same setting during
installation and upgrade. Both operator areas use that value; a change takes
effect after the coordinated rollout completes. This is an installation or
upgrade setting, not a live OSAC console toggle.
[PRD: FR-10] [User]

The setting controls provider-network operations only. Networking APIs and
OSAC object lifecycle remain available in both modes, with the same
authorization, tenant isolation, validation, defaulting, supported operations,
and dependency rules. Logical resource status continues to reflect the OSAC
object lifecycle; it does not claim a provider change occurred. The setting
does not change the enabled-services list. [PRD: FR-10] [User]

When disabled, OSAC submits no provider-network operations for any supported
network resource, regardless of the selected manager profile. No network
configuration, address allocation, routing, cleanup, DHCP discovery, or port
movement is performed, and OSAC submits no substitute or no-op work. Ordinary
VM and cluster provisioning, host provisioning, inventory, hardware, and power
management remain available. [User]

#### Resource operation behavior

API create/read/delete semantics, immutable fields, readiness preconditions,
and deletion dependency guards apply in both modes. All networking specification
and metadata updates remain rejected, including SecurityGroup rule changes; the
switch does not add an Update/Patch operation. OSAC object status continues to
reflect logical lifecycle and unmet prerequisites. [PRD: FR-8, FR-9, FR-10]

| Resource | Enabled provider create / rejected update / delete | Disabled provider create / rejected update / delete |
|----------|---------------------------------------------------|----------------------------------------------------|
| VirtualNetwork | Create and remove the manager's tenant network; specification updates rejected | OSAC object create/delete remains available; no provider network is created or removed; specification updates rejected |
| Subnet | Create/remove the selected managers' subnet/network resources; specification updates rejected | No provider segment, overlay, namespace, or pool is provisioned or removed; specification updates rejected |
| SecurityGroup | Create/delete the manager policy; specification and metadata updates rejected | OSAC create/delete remains available; no provider policy operation; existing backend rules may remain effective until provider-side cleanup; updates rejected |
| ExternalIPPool | Create/remove provider pool integration; specification updates rejected | Logical create/delete remains available without creating or removing a provider pool; specification updates rejected |
| ExternalIP | The selected manager durably reserves an address and writes the allocated-address annotation; OSAC validates the result and annotation before recording the address. On deletion, OSAC returns pool capacity only after confirmed provider release; specification updates rejected | No provider allocation or release occurs. Without a confirmed allocation it remains Pending with an empty address; a previously confirmed allocation retains its real validated address and Allocated state, marked last-known while disabled. Logical deletion releases OSAC capacity but may leave a provider reservation for manual cleanup. Specification updates rejected |
| ExternalIPAttachment | Create/remove inbound routing for an Allocated IP and Ready target; specification updates rejected | No inbound routing is configured; creation still requires the existing API prerequisites, so a newly unallocated ExternalIP cannot satisfy them; specification updates rejected |
| NATGateway | Create/remove outbound routing for the supported profile; specification updates rejected | No outbound routing is configured; creation retains the VirtualNetwork Ready and ExternalIP Allocated gates; specification updates rejected |

Read (List/Get) continues to expose persisted desired state and conditions.
While provider networking is disabled, VirtualNetwork, Subnet, SecurityGroup,
ExternalIPPool, ExternalIPAttachment, and NATGateway report `Ready=True`, reason
`ProvisioningDisabled`, and a message identifying the unavailable provider
operation, but only after the existing logical
preconditions are satisfied. Dependency checks remain specific to the
existing API gates: an ExternalIPAttachment or NATGateway requires ExternalIP
`state=Allocated`; references such as VirtualNetwork, ExternalIPPool, and
workload targets require `Ready`. A backend-confirmed ExternalIP that remains
`Allocated` during disablement satisfies an `Allocated` reference gate even
though its own condition is `Ready=False`/`ProvisioningDisabled`; its last-known
address does not imply provider reachability. If an existing resource's logical
prerequisite is unmet, it remains in its ordinary waiting state, and new create
requests retain their existing API precondition errors. This is logical OSAC
readiness only; it does not claim provider connectivity, policy enforcement, or
routing. `Skipped` describes the message/result and is not a Kubernetes
condition status.

If a legacy ExternalIPAttachment points to an ExternalIP whose fake
`0.0.0.0` address is cleared during migration, it remains
`phase=Progressing` with `Ready=False`, reason `ExternalIPNotAllocated`, and a
message that routing is waiting for a real allocation. It launches no routing
job while disabled. This waiting case does not weaken API validation: new
ExternalIPAttachments still require an Allocated ExternalIP and a Ready target.

ExternalIP is the allocation exception. If no real manager-confirmed
allocation has completed, it remains `state=Pending`, `phase=Progressing`, with an empty
`address` and `Ready=False`, reason `ProvisioningDisabled`; the message says
allocation is waiting for provider networking to be enabled. The backend remains
the address allocator when enabled; OSAC does not select an address from the
pool CIDR. If a real allocation completed before the setting was disabled,
retain its last manager-confirmed `state=Allocated` and address from the
validated allocated-address annotation, set
`phase=Progressing` while provider networking is disabled, and set
`Ready=False`, reason `ProvisioningDisabled`. The message identifies the
address as last-known information that is not being reconciled or guaranteed
reachable. If an allocation already in progress finishes while networking is
being disabled, OSAC waits for terminal job state and records the allocation
only after validating the successful result envelope and the real IPv4 address
in the manager-written annotation. It does not dispatch a new allocation or
compensating operation. Never write `0.0.0.0` or another placeholder. On rollout
to this behavior, convert
existing disabled-mode `0.0.0.0` records to Pending with an empty address;
attachments that depended on the placeholder remain waiting until a real
allocation is confirmed. [User]

#### In-Flight Provider Work and Deletion

Any provider-network operation already in progress must reach a terminal
state before OSAC reports work skipped or completes deletion. If an operation
cannot be confirmed terminal, the resource remains pending and deletion stays
incomplete so the operation can be checked again. If the operation completes
before disablement takes effect, OSAC records that confirmed result and does not
start a compensating cleanup operation. This applies to work spanning multiple
manager targets, network configuration, address allocation, host port moves,
and DHCP discovery. [User]

Once in-progress provider work is terminal, live resources report provider
work skipped. Live resources with unmet logical prerequisites remain waiting as
specified above. Deletes still respect dependency guards and auto-created child
deletion order, then complete OSAC object deletion without provider cleanup.
Logical cascade deletion does not imply provider cleanup. Turning the setting
off also does not withdraw existing provider state or public exposure. Existing
ExternalIPAttachment DNAT and NATGateway SNAT routes, allocated addresses,
segments, security rules, overlays, and port placements may remain effective
until manual/provider-side cleanup. Disabled reconciliation does not remove
them. Existing hosts are not moved back to provisioning connectivity. [User]

When the setting is enabled again after rollout, Pending ExternalIPs may proceed
to provider allocation. An automatic attachment is created only after a real
allocation and workload readiness are confirmed. Deleted OSAC objects are not recreated to
clean up provider leftovers; those leftovers require provider/manual cleanup.

#### Workload flow boundary

The manager-backed flows below apply when the setting is enabled. When it is
disabled, ordinary workload provisioning remains available for API-valid
requests:

- VMaaS provisions VMs on platform default networking; disabled mode does not
  require or apply tenant subnet placement.
- BMaaS provisions new hosts on baseline provisioning connectivity, skips
  tenant port movement and networking handoff reboots, and performs no tenant
  DHCP queries or tenant-IP feedback. Each incomplete network phase skipped
  after disablement uses `Status=Unknown`, reason `ProvisioningDisabled`, and a
  message identifying the skipped operation. Confirmed phases from before
  disablement retain `True`; legacy `True`/`Skipped` conditions from the current
  disabled path are normalized to `Unknown`/`ProvisioningDisabled`. A skipped
  network phase counts as complete only when its condition is `True` or
  `Unknown` with that exact reason;
  normal power control remains active, so `--auto-up` still powers
  the host on and it remains on provisioning connectivity. Workload Ready means
  host provisioning completed, not tenant connectivity.
- CaaS continues cluster and worker provisioning on baseline platform/
  provisioning connectivity. That connectivity must already support
  assisted-service/control-plane access, required DNS and address services,
  and installation/image dependencies. Tenant-network routing, OSAC-managed
  tenant VIP pools, and public ExternalIP routing are not supplied by OSAC in
  disabled mode; an environment that relies on those resources must provide
  adequate baseline connectivity before cluster installation can succeed.

Tenant defaulting and all API validation remain in force. Disabled mode is
not an exemption for missing defaults, invalid interfaces, unsupported
workload types, or allocation prerequisites. Automatic ExternalIP requests
retain pool/capacity validation; a persisted request whose IP stays unallocated
does not create an ExternalIPAttachment; one is created only after its ExternalIP
is Allocated and the workload is Ready. Ordinary workload provisioning does
not wait for skipped provider work to produce an address. [User]

For default tenant networking, onboarding creates the logical default
VirtualNetwork, Subnet, and SecurityGroup through their normal API paths. It
does not create the default ExternalIP or NATGateway while provider networking
is disabled: no ExternalIP can be allocated, and NATGateway creation retains
the existing `Allocated` prerequisite. Once those logical defaults are ready,
`DefaultNetworkingReady` is true with reason `ProvisioningDisabled`, allowing
VM, BM, and cluster resources to use the same default attachment resolution
and API validation. This readiness does not assert provider connectivity or
outbound NAT. When provider networking is enabled again, default networking
creates the missing ExternalIP and NATGateway through the normal allocation
and readiness gates. [User]

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

1. **Infrastructure-agnostic subnets.** Fabric-backed VMs participate in
   the fabric via k8sManager; K8s-only VMs use a primary CUDN on the hub.
   No scope/service field on VN. Manager profiles define which workloads each
   subnet can host.

2. **Cluster endpoint types:** `api` and `ingress` — enum
   `ExternalIPAttachmentEndpoint`.

3. **ExternalIP ownership:** An ExternalIP can only be consumed by one
   resource (either ExternalIPAttachment or NATGateway, not both).

4. **One NATGateway per VN.** Multiple gateways are ambiguous. Per-subnet
   NAT is a future enhancement.

5. **ExternalIPPool shared.** The selected manager provisions ExternalIP
   pools for the workload targets its profile supports. One provider-owned pool
   is shared within the deployment.

6. **Multiple hosting clusters.** Fabric-backed profiles may provision a
   K8s overlay on each supported hosting cluster so VMs can share a subnet
   through the physical network. K8s-only networking targets the single hub
   cluster.

7. **Internal IP pools.** Managed by managers with sensible defaults. Not
   part of the tenant API or NetworkClass spec.

8. **ExternalIP naming.** "External" means external to the VirtualNetwork —
   not necessarily Internet-routable. This applies within the supported
   connected deployment boundary.

9. **network_attachments immutability and cardinality.** Network attachments
   are immutable after resource creation, and VMaaS/BMaaS accept at most one
   entry even though the fields remain repeated for compatibility. Changing
   network attachment requires recreating the resource.

10. **Security enforcement.** Fabric-backed profiles use the fabric
    manager for SecurityGroup enforcement across fabric-connected workloads.
    K8s-only profiles use the K8s manager's NetworkPolicy implementation for
    the workloads and namespaces it manages.

11. **Per-resource NetworkAttachment types.** Separate proto messages
    (`ComputeNetworkAttachment`, `BareMetalNetworkAttachment`,
    `ClusterNetworkAttachment`) instead of one shared type. Each resource
    type has a different selector concept (virtual NIC, physical interface,
    node set) — a shared type with optional fields would accumulate
    dead weight per resource type.

12. **Networking resource mutability.** Resource specifications and workload
    network attachments are immutable after creation, except that SecurityGroup
    ingress and egress rules may be updated. SecurityGroup rule updates must
    reconcile the backend to the requested rules; status reconciliation is
    internal and does not add a tenant update operation.

## Test Plan

### Enclave manager discovery

- Register an additional valid Fabric Manager and K8s Manager using new names
  and contract-compatible capabilities. Verify the Enclave installation UI
  discovers each from OSAC registration data, shows it for the matching role
  and profile, and writes the selected logical name into NetworkClass
  configuration without a product-specific UI change.
- Register an invalid or profile-incompatible manager. Verify it cannot be
  selected, the installer shows the registration or compatibility reason, and
  no invalid manager name is written to NetworkClass configuration.

### Unit and API Validation

- `osac-operator/pkg/dispatcher` unit tests cover every resource kind in
  fabric-only, combined, and K8s-only profiles, including deterministic target
  order and the absence of K8s fallback for NATGateway.
- NetworkClass capability tests cover fabric-only declarations, the
  fabric/K8s intersection, and K8s-only capability sourcing. The current
  reconciler skips K8s-only NetworkClasses; the new K8s-only test must expose
  that gap until the reconciler is fixed.
- Controller tests verify that unsupported NATGateway dispatch is surfaced as a
  Failed resource condition before provisioning is invoked. A dispatch-table
  unit test alone does not verify this controller path; the current
  NATGatewayReconciler does not resolve its dispatch plan.
- Fulfillment Service unit tests cover NetworkClass assignment, immutable
  fields, and the shared lifecycle gates: reject creates with missing,
  non-Ready, or deleting dependencies; reject deletes with active dependents;
  allow operations after dependencies reach Ready or Allocated; and defer
  auto-created ExternalIPAttachment creation until both dependencies are
  ready. Verify auto-created attachment cleanup precedes ExternalIP release.
  Manager-specific validation and service tests are listed in
  the [Netris design](../OSAC-2434-netris-fabric-manager-networking/design.md).
  K8s-native behavior is covered by the shared contract and integration checks
  in this design.

### Component Integration

AAP Kind tests verify that supported resource operations reach the selected
manager role and produce the expected Kubernetes objects. They do not validate
OVN dataplane behavior or Netris controller REST behavior. K8s-only CUDN and
MetalLB role tests require the fixtures and role targets described in the
K8s-only design; no Netris REST integration test is planned without a Netris
mock server.

### As-a-Service E2E

Use the existing manager-specific service flows to verify backend behavior:
the BMaaS networking flow exercises Netris, and the VMaaS/as-a-service flow
exercises K8s-only networking. These tests verify user-visible connectivity,
address allocation, external access, and cleanup for the operations each flow
uses. Include a rejected create with a dependency that is not ready and a
rejected parent delete while an active dependent exists. These flows do not
replace unit tests for dispatch selection, validation, or capability
calculation.

### Provider Networking Control Coverage (FR-10)

- Verify enabled and disabled create/delete for each of the seven resource
  kinds, including resources carrying legacy
  implementation-strategy annotations. Disabled paths launch zero provider
  jobs; Create/List/Get/Delete retain API semantics and every networking
  specification/metadata update remains rejected, including SecurityGroup rules.
- Verify in-progress provider-network operations reach terminal state before
  skipped status or deletion completion. Include multi-target Subnet work,
  completion races, and retryable status errors.
- Verify non-allocating Networking API resources report `Ready=True`, reason
  `ProvisioningDisabled`, and a skipped-work message while preserving dependency
  ordering. Verify an unallocated ExternalIP has an empty address, never reports
  Allocated, and cannot satisfy attachment/NATGateway creation gates. Verify a
  previously allocated ExternalIP retains only its confirmed backend address
  while Ready is False, and that a legacy attachment referencing a cleared
  sentinel waits without submitting routing work.
- Verify VM jobs use platform default networking; BM provision/deprovision jobs
  stay active while port moves, handoff reboots, and DHCP queries are skipped;
  and core CaaS ClusterOrder jobs run with baseline connectivity while
  tenant VIP allocation, IPAM, routing, public DNS, and provider cleanup do not
  run while disabled.
- Verify that the same selected setting governs both operator areas after
  rollout, while networking API and reconciliation remain available.
- Verify logical deletion/cascade ordering does not claim provider cleanup;
  existing provider resources may remain after the rollout or deletion.

## Graduation Criteria

*Section to be completed when targeted at a release.*

## Upgrade / Downgrade Strategy

*Section to be completed when targeted at a release.*

The provider gate defaults to enabled, preserving the current osac-operator
umbrella default. BMF deployments that previously inherited the standalone
chart's disabled default change behavior unless their existing profile or
upgrade values select and set the desired combined state. When the previous
operator settings differ, the shared setting necessarily changes one of them.
Changing the gate requires a
Helm/Enclave upgrade and rollout of both operators; it is read at startup.
Disabled behavior is established after both operators use the new
value and tracked network jobs are terminal. Older pods may still submit work
during a rolling upgrade, so the disabled contract must not be claimed before
rollout completes. API availability is independent of this rollout. Previously active provider
network operations must reach terminal state before disabled status or deletion
completion is reported. [User]

A downgrade to an operator/chart that does not support the gate restores its
older provider behavior. Provider resources left by disabled cleanup require
manual/provider-side reconciliation before re-enabling or downgrading; the
setting does not reverse previous provider changes. No schema migration is
introduced by this setting. [User]

## Version Skew Strategy

*Section to be completed when targeted at a release.*

Both operator versions and their charts must support the same global startup
setting. Mixed operator versions/settings do not provide the disabled-mode
guarantee; complete the coordinated rollout before treating provider work as
disabled. The fulfillment API has no new field or registration dependency.
[User]

## Support Procedures

*Section to be completed when targeted at a release.*

Inspect the global Helm value, both operators' startup environments, resource
conditions, and tracked AAP job states. `Ready=True` with reason
`ProvisioningDisabled` means only that a non-allocating OSAC object completed
its logical lifecycle. BM networking-phase conditions with `Status=Unknown` and
reason `ProvisioningDisabled` identify work that was skipped; neither form proves
provider connectivity, allocation, or cleanup. Cancellation errors require restoring AAP access and
waiting for terminal state. Delete provider leftovers or restore host port
placement using provider/manual procedures before assuming cleanup or baseline
connectivity. Change the setting through Helm/Enclave rollout. [User]

## Infrastructure Needed

No additional infrastructure beyond existing OSAC components and managers.

---

## Provenance

Authored: revise @ design 0.11.3 - 2bd6607, workspace worktree-netris-k8sonly-prd-design @ 0f51a81 (1 behind origin/main, dirty)
Phases: revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"e97b06357","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond","revise","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","manual-edit","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
