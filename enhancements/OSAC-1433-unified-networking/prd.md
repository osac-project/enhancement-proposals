---
title: Unified Networking Requirements for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-06-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking
  - Original Networking API: OSAC-356 proposal (retired)
  - BareMetal Instance API: /enhancements/OSAC-1118-baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
replaces:
  - N/A
superseded-by:
  - N/A
---

# Unified Networking Requirements for VMaaS, CaaS, and BMaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-06-03 |

## Terminology

This section defines key terms used throughout this document.

- **Tenant**: An organization or user consuming OSAC services. Tenants create
  and manage their own networking resources (VirtualNetworks, Subnets,
  NetworkACLs, ExternalIPs) and place workloads on them.

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
    [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api)).

- **VirtualNetwork**: A tenant's isolated network environment with its own
  address space (CIDR). Analogous to a cloud VPC or VNet.

- **Subnet**: A subdivision of a VirtualNetwork's IP address space. Resources
  are attached to subnets to receive IP addresses and network connectivity.

- **NetworkACL**: A stateless, subnet-associated policy controlling inbound
  and outbound traffic. One NetworkACL belongs to a VirtualNetwork and may be
  associated with multiple Subnets; each Subnet has at most one effective ACL.
  Tenant rules specify an action (`allow` or `deny`), protocol, optional
  single port, direction, and IPv4 source/destination CIDR. Return traffic is
  evaluated independently; an opposite-direction tenant rule is required for
  tenant-specific control, otherwise the provider-owned deployment baseline
  applies.

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
  is implemented. It specifies the available fabric and/or K8s manager for the
  deployment. There is exactly one NetworkClass per deployment; tenants do not
  select it per VirtualNetwork.

- **Fabric Manager**: An optional single provider-configured implementation
  that manages physical networking: tenant isolation, ACLs, IP allocation,
  DNAT, and SNAT.

- **K8s Manager**: A provider-registered networking manager. It may bridge a
  K8s overlay to a fabric when paired with a Fabric Manager, or provide the
  complete supported networking surface for eligible workloads in a K8s-only
  deployment. Service-specific designs determine workload eligibility.
  NATGateway is unsupported in the K8s-only OVN mode.

- **Fabric**: The physical network infrastructure — switches, routers,
  gateways — that connects bare-metal servers and provides external
  connectivity. In this design, VMs also participate in the fabric through
  a K8s manager that bridges the OVN overlay to the physical network.

### Address-family scope

All networking resources and traffic described by this PRD use IPv4 CIDRs.
IPv6 and dual-stack networking are not supported.

### Network operation contract

The user/API contract for network-owned data is create, read, and delete only.
Network resources and the networking fields on `ComputeInstance`, `Cluster`,
and `BaremetalInstance` do not support update, patch, or replace operations.
All network-owned `spec` fields and all network-attachment fields are fixed at
creation time; changing them requires deleting and recreating the resource (or
the workload for an attachment field). Deletion may be delayed or rejected
while dependencies or finalizers remain.

East-west networking (`OSAC-1382`) is excluded from this shared contract because
it is not implemented. Its design may define update and resize operations until
that feature has its own implementation and tested contract.

This restriction does not change standard resource metadata semantics or
Catalog Item definitions and metadata. It also does not restrict updates to
non-network fields on workload resources. Controllers may update status,
conditions, readiness, IP-discovery results, and finalizers during
reconciliation.

## 1. Problem Statement

The OSAC Networking API must serve as a foundational service across all three
OSAC service types — VMaaS, CaaS, and BMaaS — with a single, consistent
resource model. The technical design that fulfills these requirements is
described in a companion enhancement:
[Unified Networking Design](/enhancements/OSAC-1433-unified-networking).

The original OSAC-356 Networking API enhancement was designed
with VMaaS (ComputeInstance) as the only consumer, explicitly listing CaaS and
BMaaS as non-goals. As OSAC grows and new teams onboard, this limitation forces
each service type to implement networking independently:

- **CaaS** manages networking entirely through fabric-specific Ansible roles,
  bypassing the OSAC API. Tenants ordering a Cluster have no way to specify
  which VirtualNetwork or Subnet their cluster nodes should use.
- **BMaaS** calls inventory backends directly for network configuration,
  bypassing the OSAC API. Tenants ordering a BaremetalInstance have no
  networking integration at all (deferred in
  the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api)).
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
has no network configuration — there is no way for a tenant to specify
which VirtualNetwork, Subnet, or NetworkACL a cluster's nodes should use.
A tenant cannot place two clusters in the same VirtualNetwork to share an
address space, or isolate clusters in separate VirtualNetworks — the networking
is entirely opaque and managed ad-hoc by the CaaS template role.

The same applies to BMaaS. BaremetalInstance (defined in
the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api))
explicitly defers networking integration. A tenant cannot specify
which Subnet a bare-metal server should be placed on, cannot apply
NetworkACLs, and cannot share a VirtualNetwork between bare-metal servers
and other resources. Both service types build ad-hoc networking outside the
API.

#### Gap #2: Tenants must choose networking backends — resolved

The provider's infrastructure determines the backend. The single deployment
NetworkClass is resolved by the platform, and tenants provide only the
tenant-owned network fields such as the VirtualNetwork CIDR. No tenant-facing
NetworkClass selection or implementation-backend choice is exposed.

#### Gap #3: No manager capability discovery or registration — resolved

Manager registration and capability declarations determine which manager
combination is valid. A K8s-only manager must declare support for all shared
networking resources except NATGateway; the operator rejects unsupported
resource creation rather than leaving it Pending.

#### Gap #4: ExternalIPAttachment only supports VMs

ExternalIPAttachment only supports VMs as a target.
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

#### Gap #9: CaaS has unique prerequisite ordering

~~Cluster worker nodes reach the hosted control plane API server via hairpin
NAT through ExternalIPs, requiring ExternalIPs and NATGateway to exist before
provisioning.~~ **Resolved:** The CaaS design eliminates hairpin NAT —
workers access the API server via the MetalLB VIP directly on the same
subnet. The pre-provisioning ordering constraint is eliminated. ExternalIPs
are for external (off-subnet) access only, not for intra-cluster
communication. ExternalIPAttachments start in Pending state and activate once
the cluster's VIPs are discovered (see
[CaaS Networking](/enhancements/OSAC-1436-caas-networking)).

## 2. Goals and Non-Goals

### 2.1 Goals

- Provide a unified networking API across VMaaS, CaaS, and BMaaS with a single, consistent resource model
- Enable tenants to manage networking resources (VirtualNetworks, Subnets, NetworkACLs, ExternalIPs) without choosing implementation backends
- Support pluggable networking backends that can be added without API changes
- Enable VMs, clusters, and bare-metal servers to coexist in the same
  VirtualNetwork where the selected manager and service-specific placement
  contract support the workload
- Support one tenant network attachment for each bare-metal server, selected from the BareMetalInstanceType's physical network ports
- Provide IPv4-only networking; IPv6 and dual-stack networking are not supported

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
  bonding, VLAN trunking, or multiple tenant attachments; BMaaS uses one
  physical NIC selected through the `interface` field)
- Load Balancer API
- Internet Gateway API
- Quota enforcement for networking resources

## 3. User Stories

### Tenant Stories (All Services)

- As a tenant, I want to create isolated VirtualNetworks and Subnets for my
  workloads without choosing a networking backend
- As a tenant, I want to define NetworkACLs to control traffic to and
  from my resources
- As a tenant, I want to allocate ExternalIPs and attach them to my VMs,
  clusters, or bare-metal servers for inbound access
- As a tenant, I want to create a NATGateway for outbound access from my
  VirtualNetwork when the deployment's configured managers support it

### CaaS-Specific Stories

- As a tenant, I want to place my cluster's worker nodes on a Subnet in my
  VirtualNetwork
- As a tenant, I want to attach ExternalIPs to my cluster's API server and
  ingress endpoints before provisioning

### BMaaS-Specific Stories

- As a tenant, I want to place my BaremetalInstance on Subnets in my
  VirtualNetwork
- As a tenant, I want to see the available physical interfaces on a bare-metal
  template so I can select the one interface used for my tenant network
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

The same subnet may host VMs, BM servers, and cluster nodes when the selected
manager combination supports each workload's placement contract. The tenant
does not declare the resource type when creating a VirtualNetwork or Subnet;
service-specific validation rejects unsupported placement before workload
persistence. Multiple deployment locations are supported — VMs on different
infrastructure share the same subnet.

#### FR-3: Uniform networking across all service types (R3)

All three service types (VMaaS, CaaS, BMaaS) must consume the networking API
using the same resource model: VirtualNetwork, Subnet, NetworkACL,
ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway.

#### FR-4: ExternalIP is external to the VirtualNetwork (R4)

"External" means external to the VirtualNetwork. In the supported connected
boundary, the provider defines pools of addresses routable from the deployment;
air-gapped and disconnected operation is not supported.

#### FR-5: Clear ingress/egress separation (R5)

The API must clearly separate inbound and outbound external access.

#### FR-6: Pluggable networking backends with transparent selection (R6)

Providers configure which networking backends handle network operations.
Tenants never choose networking backends — the system selects them based
on the provider's configuration.

At least one of Fabric Manager or K8s Manager must be configured. A K8s-only
deployment supports VirtualNetwork, Subnet, NetworkACL, ExternalIPPool,
ExternalIP, and ExternalIPAttachment for workloads eligible for that manager
mode; NATGateway creation is rejected because of the current OVN limitation.

#### FR-6a: Stateless NetworkACL policy

NetworkACLs are associated with Subnets rather than workload resources. A
NetworkACL may be associated with multiple Subnets, but a Subnet has at most
one effective ACL. Each packet is evaluated independently; the ACL does not
track connections and does not automatically permit response traffic.

Each rule has an explicit `allow` or `deny` action. When rules overlap, the
most-specific matching rule wins. Specificity is ordered by the longest
matching remote CIDR prefix, exact protocol over `any`, and exact port over an
omitted port. Conflicting rules with equal specificity are rejected. If no
tenant rule matches, evaluation falls through to the provider-owned deployment
default ACL policy (the deployment baseline), which is currently hard-coded to
`permit` all traffic. The baseline is the least-specific policy and is not
stored in or configurable through a tenant NetworkACL.

Each tenant receives a tenant default NetworkACL associated with its default
Subnet. It contains the default ACL policy: deny all ingress and allow all
egress.
This is an ordinary, visible NetworkACL policy and can be replaced only through
the documented default-resource workflow. It is distinct from the
provider-owned deployment baseline, which remains the least-specific fallback.

#### FR-7: Single network attachment for bare metal (R7)

BareMetalInstanceTypes may expose multiple physical network ports. The
`BaremetalInstance.network_attachments` API field remains repeated for
compatibility, but accepts at most one tenant attachment, selected from the
network ports provided by the BareMetalInstanceType. The selected attachment
supplies the server's tenant IP, default route, and ExternalIP DNAT target.

### 4.2 Non-Functional Requirements

- Networking resources, attachments, external IPs, and security rules use IPv4
  only. IPv6 and dual-stack networking are not supported.

## 5. Acceptance Criteria

### Core Networking

- [ ] VirtualNetworks, Subnets, ExternalIPs, and NetworkACL rules accept and
  provision IPv4 CIDRs only; IPv6 and dual-stack requests are rejected
- [ ] Resources in different VirtualNetworks cannot communicate (full isolation)
- [ ] Resources in the same Subnet are in the same L2 broadcast domain
- [ ] Resources in different Subnets within the same VirtualNetwork can communicate via Layer 3 routing
- [ ] NetworkACLs control which traffic is permitted within these boundaries — enforced uniformly for all resource types
- [ ] A NetworkACL can be associated with multiple Subnets, while each Subnet has at most one effective ACL
- [ ] NetworkACL rules are stateless: response traffic is evaluated independently; a tenant-specific opposite-direction rule is required for a tenant-specific decision, otherwise the deployment baseline applies
- [ ] The default ACL policy is explicit deny-all ingress and allow-all egress on each tenant's default NetworkACL
- [ ] The provider-owned deployment baseline is the least-specific fallback and is hard-coded to permit all traffic; it is not tenant-configurable or serialized in tenant NetworkACLs
- [ ] Tenant-created NetworkACLs contain at least one explicit rule with a supported action, direction, protocol, and IPv4 CIDR
- [ ] Overlapping rules resolve by documented specificity, and equal-specificity contradictory rules are rejected
- [ ] Bare-metal servers in the same Subnet are in the same broadcast domain regardless of their physical location (rack, switch)
- [ ] VMs in the same Subnet are in the same broadcast domain regardless of which infrastructure they run on
- [ ] VMs are reachable at their subnet IP alongside bare-metal servers and cluster nodes
- [ ] The system provisions all necessary networking infrastructure for each subnet automatically
- [ ] Any resource type (ComputeInstance, Cluster, BaremetalInstance) can be placed on any subnet for which the selected manager and service-specific placement contract report support; unsupported placement is rejected before persistence
- [ ] VMs, BM servers, and cluster nodes receive uniform networking treatment — NetworkACL and ExternalIP operations work identically regardless of resource type
- [ ] NetworkACL enforcement is uniform across all resource types
- [ ] Workload network attachments contain Subnet and resource-specific interface fields only; NetworkACL membership is resolved from the Subnet
- [ ] Each resource type has its own network attachment configuration appropriate to the resource (e.g., BMaaS uses one physical attachment, clusters use one shared subnet and one tenant-facing physical interface per node)
- [ ] ExternalIPAttachment supports all three service types as targets
- [ ] The tenant workflow for creating networking resources is identical regardless of service type
- [ ] NetworkClass manager combinations are resolved by the provider; tenants do not select a NetworkClass per VirtualNetwork
- [ ] K8s-only deployments reject NATGateway creation and support the other shared networking resources through the registered K8s manager

### Network Operations and Immutability

- [ ] Network resources expose create, read/list, and delete operations only; user/API update, patch, and replace requests for network-owned `spec` fields are rejected or not exposed
- [ ] All network-owned `spec` fields on NetworkClass, VirtualNetwork, Subnet, NetworkACL, ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway are immutable after creation
- [ ] `ComputeInstance.network_attachments` is immutable as a complete list, including every attachment field
- [ ] `ComputeInstance.network_attachments` retains a list-shaped API but accepts zero or one entry only; requests with more than one entry are rejected
- [ ] `Cluster.network_attachment` and `BaremetalInstance.network_attachments` are immutable, including every attachment field
- [ ] `auto_external_ip_attachment` is immutable after workload creation; changing it requires delete and recreate
- [ ] Every network-owned field documents its wire type, format, presence/default behavior, allowed values, reference scope, and cross-field validation
- [ ] Unsupported, unknown, or otherwise undefined network field values are rejected rather than inferred by clients or agents
- [ ] The CLI exposes create, read/list, and delete for network-owned resources only; network-owned update, patch, and replace operations are not exposed or are rejected
- [ ] The CLI maps one optional `--network-attachment` to VM and BM list-shaped `network_attachments` fields and to the singular CaaS `network_attachment` field
- [ ] The CLI accepts only canonical IPv4 CIDRs, typed reference values, supported enums, and the documented NetworkACL rule grammar
- [ ] The CLI rejects repeated workload attachment options, unsupported `interface`/`primary` fields, IPv6 or multi-CIDR values, invalid target combinations, and non-Ready dependencies
- [ ] `--external-ip-attachment` maps to the create-time `auto_external_ip_attachment` field for VM, BM, and Cluster and cannot be changed later
- [ ] Changing any network-owned field requires deleting and recreating the affected resource or workload
- [ ] Controllers can update status, conditions, readiness, IP-discovery results, and finalizers without changing network-owned `spec` fields
- [ ] Non-network workload fields and Catalog Item definitions and metadata remain governed by their existing designs
- [ ] East-west networking (`OSAC-1382`) is excluded from this shared operation and field contract until it is implemented and tested

### External Access

- [ ] ExternalIP semantics do not depend on internet reachability
- [ ] The supported deployment boundary is connected only; air-gapped requests are rejected before provisioning
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

- [ ] BareMetalInstanceTypes describe available network ports (name, role, type, speed) for bare-metal servers
- [ ] Bare-metal network attachments include an optional interface reference that identifies a named port from the BareMetalInstanceType
- [ ] Bare-metal servers accept at most one `network_attachments` entry, using one valid physical interface
- [ ] All referenced subnets must belong to the same VirtualNetwork

### Resource-Specific (VMaaS)

- [ ] `ComputeInstance.network_attachments` remains a repeated/list field but accepts zero or one entry only
- [ ] A single VM attachment is implicitly primary when `primary` is omitted; explicit `primary: false` and more than one entry are rejected
- [ ] Multi-interface VM requests are unsupported and rejected by the current contract

## 6. Dependencies

- **Unified Networking Design**: [/enhancements/OSAC-1433-unified-networking](/enhancements/OSAC-1433-unified-networking) — Technical design document fulfilling these requirements
- **Default Networking**: [/enhancements/OSAC-1433-default-networking](/enhancements/OSAC-1433-default-networking) — Related enhancement for resource ordering workflow
- **Original Networking API**: OSAC-356 proposal (retired) — VMaaS-only networking API (superseded for multi-service scenarios)
- **BareMetal Instance API**: [/enhancements/OSAC-1118-baremetal-instance-api](/enhancements/OSAC-1118-baremetal-instance-api) — Defines BaremetalInstance resource
- **Three-Layer Networking Model**: [Google Doc](https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM) — Architectural reference
