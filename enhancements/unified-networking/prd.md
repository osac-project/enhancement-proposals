# Unified Networking Requirements for VMaaS, CaaS, and BMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1029 |
| Date        | 2026-06-03 |

## Terminology

This section defines key terms used throughout this document.

- **Tenant**: An organization or user consuming OSAC services. Tenants create
  and manage their own networking resources (VirtualNetworks, Subnets,
  SecurityGroups, ExternalIPs) and place workloads on them.

- **Provider**: The cloud administrator who deploys and configures OSAC
  infrastructure. Providers install networking managers, configure
  NetworkClasses, and manage ExternalIPPools. Tenants do not see
  provider-level configuration.

- **Service Types**: The three workload types OSAC supports:
  - **VMaaS** (Virtual Machine as a Service): Provisions virtual machines.
    The API resource is `ComputeInstance`.
  - **CaaS** (Cluster as a Service): Provisions managed clusters. The API
    resource is `Cluster`.
  - **BMaaS** (Bare Metal as a Service): Provisions physical bare-metal
    servers. The API resource is `BaremetalInstance` (defined in the
    [BareMetal Instance API enhancement](/enhancements/baremetal-instance-api)).

- **VirtualNetwork**: A tenant's isolated network environment with its own
  address space (CIDR). Analogous to a cloud VPC or VNet.

- **Subnet**: A subdivision of a VirtualNetwork's IP address space. Resources
  are attached to subnets to receive IP addresses and network connectivity.

- **SecurityGroup**: A stateful firewall controlling inbound and outbound
  traffic for resources. Rules specify allowed protocols, ports, and
  source/destination addresses.

- **ExternalIPPool**: A provider-defined pool of IP addresses that are
  routable outside the VirtualNetwork. "External" means external to the VN —
  not necessarily internet-routable (see gap #8).

- **ExternalIP**: An IP address allocated from an ExternalIPPool. Persists
  independently of the resources it's attached to.

- **ExternalIPAttachment**: The binding between an ExternalIP and a target
  resource for inbound traffic (DNAT).

- **NATGateway**: Optionally provides a dedicated outbound NAT (SNAT) for
  resources in a VirtualNetwork, giving them a known, stable source IP for
  egress traffic. Without a NATGateway, resources may still have default
  egress but without a controlled source identity.

- **NetworkClass**: A provider-configured resource that defines how networking
  is implemented. Specifies which fabric manager and K8s manager handle
  networking. In the current design, tenants select it when creating a
  VirtualNetwork (this is one of the gaps — see #2).

- **Fabric Manager**: A single product (e.g., Netris, Neutron) that manages
  all physical networking: tenant isolation, ACLs, IP allocation, DNAT,
  SNAT. The physical fabric is one infrastructure — one controller manages
  it all.

- **K8s Manager**: Handles everything needed to make VMs part of the fabric:
  creates the K8s overlay and bridges it to the fabric segment. Only needed
  for deployments that host VMs.

- **Fabric**: The physical network infrastructure — switches, routers,
  gateways — that connects bare-metal servers and provides external
  connectivity. In this design, VMs also participate in the fabric through
  a K8s manager that bridges the OVN overlay to the physical network.

## 1. Problem Statement

The OSAC Networking API must serve as a foundational service across all three
OSAC service types — VMaaS, CaaS, and BMaaS — with a single, consistent
resource model. The technical design that fulfills these requirements is
described in a companion enhancement:
[Unified Networking Design](/enhancements/unified-networking).

The original [Networking API enhancement](/enhancements/networking) was designed
with VMaaS (ComputeInstance) as the only consumer, explicitly listing CaaS and
BMaaS as non-goals. As OSAC grows and new teams onboard, this limitation forces
each service type to implement networking independently:

- **CaaS** manages networking entirely through fabric-specific Ansible roles,
  bypassing the OSAC API. Tenants ordering a Cluster have no way to specify
  which VirtualNetwork or Subnet their cluster nodes should use.
- **BMaaS** calls inventory backends directly for network configuration,
  bypassing the OSAC API. Tenants ordering a BaremetalInstance have no
  networking integration at all (deferred in
  the [BareMetal Instance API enhancement](/enhancements/baremetal-instance-api)).
- **Tenants** have no unified way to manage networking across service types.
  A tenant running VMs, clusters, and bare-metal servers must use three
  different networking models.
- **Providers** cannot swap network managers without API changes. Adding a
  new fabric manager or changing the active one requires modifying the
  fulfillment service and operator.

The result is fragmented networking with no consistency, no reuse, and no
tenant-facing abstraction.

### Gaps in the Current Design

#### Gap #1: CaaS and BMaaS have no networking API

The Networking API only supports ComputeInstance (VMaaS). The Cluster resource
has no `network_attachments` field — there is no way for a tenant to specify
which VirtualNetwork, Subnet, or SecurityGroup a cluster's nodes should use.
A tenant cannot place two clusters in the same VirtualNetwork to share an
address space, or isolate clusters in separate VirtualNetworks — the networking
is entirely opaque and managed ad-hoc by the CaaS template role.

The same applies to BMaaS. BaremetalInstance (defined in
the [BareMetal Instance API enhancement](/enhancements/baremetal-instance-api))
explicitly defers networking integration. A tenant cannot specify
which Subnet a bare-metal server should be placed on, cannot apply
SecurityGroups, and cannot share a VirtualNetwork between bare-metal servers
and other resources. Both service types build ad-hoc networking outside the
API.

#### Gap #2: Tenants must choose networking backends

NetworkClass is modeled after Kubernetes StorageClass — tenants select it when
creating a VirtualNetwork. But unlike StorageClass (where "fast" vs "cheap" is
a meaningful tenant choice about capability), NetworkClass exposes network
backend implementation details ("udn-net" vs "phys-net") that tenants should
not need to understand. The provider's infrastructure determines the backend,
not the tenant's preference.

#### Gap #3: No manager capability discovery or registration

There is no registry of which networking managers are installed or what each
supports. A K8s manager like `cudn_localnet` handles VM overlay and bridging
but not IP allocation or ACLs. A fabric manager like Netris handles
everything on the physical side. The system has no way to know this — there
is no machine-readable declaration of manager capabilities, and no validation
that a manager is assigned to a role it can handle.

#### Gap #4: ExternalIPAttachment only supports VMs

The ExternalIPAttachment target is a `oneof` with only `compute_instance`.
CaaS needs ExternalIPs for cluster API server and ingress endpoints (two
separate IPs for two different purposes on the same Cluster). BMaaS needs
ExternalIPs for bare-metal servers. Neither can use the existing
ExternalIPAttachment.

#### Gap #5: Ingress and egress are not clearly separated

ExternalIPAttachment is described as "routes traffic to the resource" —
ambiguous about whether it handles inbound traffic only or is bidirectional.
NATGateway is described as "outbound NAT" but the relationship between the
two is undefined. If a resource has both an ExternalIPAttachment and a
NATGateway, which takes precedence for egress? The current implementation is
ingress-only, but this is not documented.

#### Gap #6: VMs are not part of the fabric

VMs running on OpenShift use OVN (User Defined Networks) for isolation. Their
IP addresses exist only within the OVN overlay and are not visible on the
physical fabric. When a fabric manager needs to perform DNAT to route
external traffic to a VM, it cannot reach the VM's OVN-internal IP directly.
A K8s manager (e.g., CUDN with LocalNet) is needed to bridge VMs to the
fabric. The current design does not address this, and there is no way for a
provider to configure which bridging mechanism to use.

#### Gap #7: VMs and bare metal cannot share a network

VMs use OVN for isolation — a software-defined overlay on the OpenShift
cluster. Bare-metal servers use physical VLANs configured on switches in the
fabric. These are fundamentally different L2 domains. A K8s manager using
LocalNet mode can bridge OVN to the physical fabric, making VMs first-class
participants alongside BM servers. The current design does not address how
VMs and bare-metal servers coexist in the same deployment, whether they can share
a VirtualNetwork, or how traffic flows between them.

#### Gap #8: Air-gapped environments not considered

ExternalIPPool and ExternalIP must work in air-gapped deployments where there
are no internet-routable IPs. Tenants still need the same API primitives (IP
allocation, inbound DNAT, outbound SNAT) for data-center-internal external
access. "External" means external to the VirtualNetwork, not
internet-routable.

#### Gap #9: CaaS has unique prerequisite ordering

~~Cluster worker nodes reach the hosted control plane API server via hairpin
NAT through ExternalIPs, requiring ExternalIPs and NATGateway to exist before
provisioning.~~ **Resolved:** The CaaS design eliminates hairpin NAT —
workers access the API server via the MetalLB VIP directly on the same
subnet. The pre-provisioning ordering constraint is eliminated. ExternalIPs
are for external (off-subnet) access only, not for intra-cluster
communication. ExternalIPAttachments start in Pending state and activate once
the cluster's VIPs are discovered (see
[CaaS Networking](/enhancements/caas-networking)).

## 2. Goals and Non-Goals

### 2.1 Goals

- Provide a unified networking API across VMaaS, CaaS, and BMaaS with a single, consistent resource model
- Enable tenants to manage networking resources (VirtualNetworks, Subnets, SecurityGroups, ExternalIPs) without choosing implementation backends
- Support pluggable networking backends that can be added without API changes
- Enable VMs, clusters, and bare-metal servers to coexist in the same VirtualNetwork
- Work in air-gapped environments using data-center-routable IPs
- Support per-interface network attachment for bare-metal servers with multiple physical interfaces

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| Service types using networking API | 3/3 (VMaaS, CaaS, BMaaS) | 1/3 (VMaaS only) |
| Service types bypassing networking API for network configuration | 0/3 | 2/3 (CaaS, BMaaS) |
| API changes required to add a new manager | 0 | Requires API + operator changes |

### 2.3 Non-Goals

- VPC Peering / cross-VN communication (separate enhancement)
- DNS API for tenant-managed DNS zones (separate enhancement)
- Advanced per-physical-interface configuration for BaremetalInstance (NIC
  bonding, VLAN trunking, etc. — basic per-interface subnet attachment is
  supported via the `interface` field on NetworkAttachment)
- Load Balancer API
- Internet Gateway API
- Quota enforcement for networking resources

## 3. User Stories

### Tenant Stories (All Services)

- As a tenant, I want to create isolated VirtualNetworks and Subnets for my
  workloads without choosing a networking backend
- As a tenant, I want to define SecurityGroups to control traffic to and
  from my resources
- As a tenant, I want to allocate ExternalIPs and attach them to my VMs,
  clusters, or bare-metal servers for inbound access
- As a tenant, I want to create a NATGateway for outbound access from my
  VirtualNetwork

### CaaS-Specific Stories

- As a tenant, I want to place my cluster's worker nodes on a Subnet in my
  VirtualNetwork
- As a tenant, I want to attach ExternalIPs to my cluster's API server and
  ingress endpoints before provisioning
- As a tenant, I want my cluster to work in air-gapped environments using
  data-center-routable IPs

### BMaaS-Specific Stories

- As a tenant, I want to place my BaremetalInstance on Subnets in my
  VirtualNetwork
- As a tenant, I want to see the available physical interfaces on a bare-metal
  template so I can decide how to attach networks
- As a tenant, I want to attach different physical interfaces of my
  BaremetalInstance to different Subnets (e.g., data interface to a data
  subnet, management interface to a management subnet)
- As a tenant, I want to attach an ExternalIP to my bare-metal server for
  inbound access

### Provider Stories

- As a provider, I want to configure networking backends without exposing
  implementation details to tenants
- As a provider, I want to add new networking backends without modifying
  the API
- As a provider, I want to add new networking backends through
  configuration, not code changes
- As a provider, I want to be able to provision ExternalIP pools for tenants

## 4. Requirements

### 4.1 Functional Requirements

#### FR-1: Network isolation and connectivity (R1)

VirtualNetworks must provide tenant isolation. Subnets within a VirtualNetwork
must provide L2 and L3 connectivity. These guarantees must hold regardless of
the physical location of the resource or the infrastructure it runs on. The
system enforces isolation uniformly across all resource types.

#### FR-2: Infrastructure-agnostic subnets (R2)

The same subnet must be able to host VMs, BM servers, and cluster nodes.
The tenant does not declare the resource type when creating a VirtualNetwork
or Subnet. Multiple deployment locations are supported — VMs on different
infrastructure share the same subnet.

#### FR-3: Uniform networking across all service types (R3)

All three service types (VMaaS, CaaS, BMaaS) must consume the networking API
using the same resource model: VirtualNetwork, Subnet, SecurityGroup,
ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway.

#### FR-4: ExternalIP is external to the VirtualNetwork (R4)

"External" means external to the VirtualNetwork — OSAC does not prescribe
whether the IPs are internet-routable, intranet-only, or data-center-local.
The provider defines the pools; the API is the same regardless.

#### FR-5: Clear ingress/egress separation (R5)

The API must clearly separate inbound and outbound external access.

#### FR-6: Pluggable networking backends with transparent selection (R6)

Providers configure which networking backends handle network operations.
Tenants never choose networking backends — the system selects them based
on the provider's configuration.

#### FR-7: Per-interface network attachment for bare metal (R7)

Bare-metal servers have multiple physical interfaces. Tenants must be able to
attach different interfaces to different Subnets based on the interface
descriptions provided by the template.

### 4.2 Non-Functional Requirements

_No non-functional requirements were specified in the original document._

## 5. Acceptance Criteria

### Core Networking

- [ ] Resources in different VirtualNetworks cannot communicate (full isolation)
- [ ] Resources in the same Subnet are in the same L2 broadcast domain
- [ ] Resources in different Subnets within the same VirtualNetwork can communicate via Layer 3 routing
- [ ] SecurityGroups control which traffic is permitted within these boundaries — enforced uniformly for all resource types
- [ ] Bare-metal servers in the same Subnet are in the same broadcast domain regardless of their physical location (rack, switch)
- [ ] VMs in the same Subnet are in the same broadcast domain regardless of which infrastructure they run on
- [ ] VMs are reachable at their subnet IP alongside bare-metal servers and cluster nodes
- [ ] The system provisions all necessary networking infrastructure for each subnet automatically
- [ ] Any resource type (ComputeInstance, Cluster, BaremetalInstance) can be placed on any subnet
- [ ] VMs, BM servers, and cluster nodes receive uniform networking treatment — SecurityGroup and ExternalIP operations work identically regardless of resource type
- [ ] SecurityGroup enforcement is uniform across all resource types
- [ ] Each resource type has its own network attachment configuration appropriate to the resource (e.g., bare-metal servers support per-interface attachment, clusters use a single shared attachment)
- [ ] ExternalIPAttachment supports all three service types as targets
- [ ] The tenant workflow for creating networking resources is identical regardless of service type

### External Access

- [ ] ExternalIP semantics do not depend on internet reachability
- [ ] The API and workflow are identical for all deployment topologies (air-gapped, internet-connected, intranet-only)
- [ ] CaaS clusters can provision using any routable ExternalIPs for API server and ingress
- [ ] ExternalIPAttachment handles inbound traffic only
- [ ] NATGateway handles outbound traffic only — it is optional and provides a dedicated egress identity, not a prerequisite for basic connectivity
- [ ] Inbound and outbound external access works uniformly for all resource types — VMs, BM servers, and cluster nodes

### Provider Architecture

- [ ] Networking backend configuration is not exposed in the tenant API
- [ ] A single networking backend handles all physical networking operations (isolation, access control, IP allocation, inbound routing, outbound routing)
- [ ] VM networking is integrated into the same networking layer as bare-metal servers
- [ ] Networking backends are registered through configuration deployed with the OSAC installation
- [ ] The system validates that a networking backend supports its assigned role
- [ ] A new networking backend can be added through configuration — no API changes needed

### Resource-Specific (Bare Metal)

- [ ] Host types describe available interfaces (name, role, description) for bare-metal servers
- [ ] Bare-metal network attachments include an optional interface reference that identifies a named interface from the host type
- [ ] Multiple network attachments are supported for bare-metal servers — one per physical interface
- [ ] The same interface cannot appear in multiple attachments
- [ ] All referenced subnets must belong to the same VirtualNetwork

## 6. Dependencies

- **Unified Networking Design**: [/enhancements/unified-networking](/enhancements/unified-networking) — Technical design document fulfilling these requirements
- **Default Networking**: [/enhancements/default-networking](/enhancements/default-networking) — Related enhancement for resource ordering workflow
- **Original Networking API**: [/enhancements/networking](/enhancements/networking) — VMaaS-only networking API (superseded for multi-service scenarios)
- **BareMetal Instance API**: [/enhancements/baremetal-instance-api](/enhancements/baremetal-instance-api) — Defines BaremetalInstance resource
- **Three-Layer Networking Model**: [Google Doc](https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM) — Architectural reference
