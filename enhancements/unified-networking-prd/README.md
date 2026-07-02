---
title: Unified Networking Requirements for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-06-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1029
see-also:
  - Unified Networking Design: /enhancements/unified-networking
  - Original Networking API: /enhancements/networking
  - BareMetal Instance API: /enhancements/baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
replaces:
  - N/A
superseded-by:
  - N/A
---

# Unified Networking Requirements for VMaaS, CaaS, and BMaaS

## Summary

The OSAC Networking API must serve as a foundational service across all three
OSAC service types — VMaaS, CaaS, and BMaaS — with a single, consistent
resource model. This document defines the requirements, identifies gaps in the
current design, and establishes acceptance criteria. The technical design that
fulfills these requirements is described in a companion enhancement:
[Unified Networking Design](/enhancements/unified-networking).

## Terminology

This section defines key terms used throughout this document.

- **Tenant**: An organization or user consuming OSAC services. Tenants create
  and manage their own networking resources (VirtualNetworks, Subnets,
  SecurityGroups, ExternalIPs) and place workloads on them.

- **Provider**: The cloud administrator who deploys and configures OSAC
  infrastructure. Providers define regions, install networking managers,
  configure NetworkClasses, and manage ExternalIPPools. Tenants do not see
  provider-level configuration.

- **Region**: A management boundary representing a deployment location (e.g.,
  a data center). Networking resources are scoped to a region. Each region has
  its own networking infrastructure and manager configuration.

- **Service Types**: The three workload types OSAC supports:
  - **VMaaS** (Virtual Machine as a Service): Provisions virtual machines.
    The API resource is `ComputeInstance`.
  - **CaaS** (Cluster as a Service): Provisions managed clusters. The API
    resource is `Cluster`.
  - **BMaaS** (Bare Metal as a Service): Provisions physical bare-metal
    servers. The API resource is `BaremetalInstance` (defined in the
    [BareMetal Instance API enhancement](/enhancements/baremetal-instance-api)).

- **VirtualNetwork**: A tenant's isolated network environment with its own
  address space (CIDR). Analogous to a cloud VPC or VNet. Scoped to a
  region.

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
  is implemented in a region. Specifies which fabric manager and K8s manager
  handle networking for the region. In the current design, tenants select it
  when creating a VirtualNetwork (this is one of the gaps — see #2).

- **Fabric Manager**: A single product (e.g., Netris, Neutron) that manages
  all physical networking for a region: tenant isolation, ACLs, IP
  allocation, DNAT, SNAT. The physical fabric is one infrastructure — one
  controller manages it all.

- **K8s Manager**: Handles everything needed to make VMs part of the fabric:
  creates the K8s overlay and bridges it to the fabric segment. Only needed
  for regions that host VMs.

- **Fabric**: The physical network infrastructure — switches, routers,
  gateways — that connects bare-metal servers and provides external
  connectivity. In this design, VMs also participate in the fabric through
  a K8s manager that bridges the OVN overlay to the physical network.

## Problem Statement

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
  new fabric manager or changing the one for a region requires modifying the
  fulfillment service and operator.

The result is fragmented networking with no consistency, no reuse, and no
tenant-facing abstraction.

## Gaps in the Current Design

### 1. CaaS and BMaaS have no networking API

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

### 2. Tenants must choose networking backends

NetworkClass is modeled after Kubernetes StorageClass — tenants select it when
creating a VirtualNetwork. But unlike StorageClass (where "fast" vs "cheap" is
a meaningful tenant choice about capability), NetworkClass exposes network
backend implementation details ("udn-net" vs "phys-net") that tenants should
not need to understand. The provider's infrastructure determines the backend,
not the tenant's preference.

### 3. No manager capability discovery or registration

There is no registry of which networking managers are installed or what each
supports. A K8s manager like `cudn_localnet` handles VM overlay and bridging
but not IP allocation or ACLs. A fabric manager like Netris handles
everything on the physical side. The system has no way to know this — there
is no machine-readable declaration of manager capabilities, and no validation
that a manager is assigned to a role it can handle.

### 4. ExternalIPAttachment only supports VMs

The ExternalIPAttachment target is a `oneof` with only `compute_instance`.
CaaS needs ExternalIPs for cluster API server and ingress endpoints (two
separate IPs for two different purposes on the same Cluster). BMaaS needs
ExternalIPs for bare-metal servers. Neither can use the existing
ExternalIPAttachment.

### 5. Ingress and egress are not clearly separated

ExternalIPAttachment is described as "routes traffic to the resource" —
ambiguous about whether it handles inbound traffic only or is bidirectional.
NATGateway is described as "outbound NAT" but the relationship between the
two is undefined. If a resource has both an ExternalIPAttachment and a
NATGateway, which takes precedence for egress? The current implementation is
ingress-only, but this is not documented.

### 6. VMs are not part of the fabric

VMs running on OpenShift use OVN (User Defined Networks) for isolation. Their
IP addresses exist only within the OVN overlay and are not visible on the
physical fabric. When a fabric manager needs to perform DNAT to route
external traffic to a VM, it cannot reach the VM's OVN-internal IP directly.
A K8s manager (e.g., CUDN with LocalNet) is needed to bridge VMs to the
fabric. The current design does not address this, and there is no way for a
provider to configure which bridging mechanism to use.

### 7. VMs and bare metal cannot share a network

VMs use OVN for isolation — a software-defined overlay on the OpenShift
cluster. Bare-metal servers use physical VLANs configured on switches in the
fabric. These are fundamentally different L2 domains. A K8s manager using
LocalNet mode can bridge OVN to the physical fabric, making VMs first-class
participants alongside BM servers. The current design does not address how
VMs and bare-metal servers coexist in the same region, whether they can share
a VirtualNetwork, or how traffic flows between them.

### 8. Air-gapped environments not considered

ExternalIPPool and ExternalIP must work in air-gapped deployments where there
are no internet-routable IPs. Tenants still need the same API primitives (IP
allocation, inbound DNAT, outbound SNAT) for data-center-internal external
access. For example, CaaS cluster worker nodes reach the API server via
hairpin NAT through an ExternalIP regardless of whether that IP is
internet-routable. "External" means external to the VirtualNetwork, not
internet-routable.

### 9. CaaS has unique prerequisite ordering

Cluster worker nodes reach the hosted control plane API server via hairpin
NAT — egress traffic SNATs to an ExternalIP, then DNATs back in through
another ExternalIP to reach the API server. This means ExternalIPs and
NATGateway must exist before the cluster is provisioned, not after. The
current design assumes ExternalIPs are attached post-creation (as they are
for VMs), which does not work for CaaS.

## User Stories

### Tenant Stories (All Services)

- As a tenant, I want to create isolated VirtualNetworks and Subnets for my
  workloads without choosing a networking backend
- As a tenant, I want to define SecurityGroups to control traffic to and
  from my resources
- As a tenant, I want to allocate ExternalIPs and attach them to my VMs,
  clusters, or bare-metal servers for inbound access
- As a tenant, I want to create a NATGateway for outbound access from my
  VirtualNetwork
- As a tenant, I want to create a resource (VM, cluster, or bare-metal
  server) without pre-creating networking resources, so that the system
  provides sensible defaults and I can get started quickly
- As a tenant, I want to create a resource with `--external-ip=auto` and
  have it externally reachable in a single API call, without manually
  creating ExternalIP and ExternalIPAttachment resources
- As a tenant, I want to inspect and customize my default networking
  resources (e.g., modify SecurityGroup rules) after they are auto-created
- As a tenant, I want auto-provisioned ExternalIPs to be automatically
  cleaned up when I delete the parent resource, so that I do not accumulate
  orphaned resources

### CaaS-Specific Stories

- As a tenant, I want to place my cluster's worker nodes on a Subnet in my
  VirtualNetwork
- As a tenant, I want to attach ExternalIPs to my cluster's API server and
  ingress endpoints before provisioning
- As a tenant, I want my cluster to work in air-gapped environments using
  data-center-routable IPs
- As a tenant, I want to create a Cluster with `--external-ip=auto` and
  have the system automatically provision ExternalIPs for both the API
  server and ingress endpoints before cluster provisioning begins
- As a tenant, I want to create a Cluster with `--nat-gateway=auto` and
  have the system automatically provision a NATGateway on the VirtualNetwork
  so that cluster nodes have outbound connectivity without manual setup

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

- As a provider, I want to configure a fabric manager and K8s manager per
  region without exposing implementation details to tenants
- As a provider, I want to register new managers without modifying the API
  or the operator
- As a provider, I want to add new networking managers by deploying a
  ConfigMap and an Ansible role
- As a provider, I want to be able to provision ExternalIP pools for tenants
- As a provider, I want to configure a default CIDR range and default
  SecurityGroup rules, so that the system can auto-create default
  networking resources for tenants on first use

## Non-Goals

- VPC Peering / cross-VN communication (separate enhancement)
- DNS API for tenant-managed DNS zones (separate enhancement)
- Advanced per-physical-interface configuration for BaremetalInstance (NIC
  bonding, VLAN trunking, etc. — basic per-interface subnet attachment is
  supported via the `interface` field on NetworkAttachment)
- Load Balancer API
- Internet Gateway API
- Quota enforcement for networking resources
- Region-scoped networking (region is not yet a fully defined concept in
  OSAC — this design assumes a single-region deployment)

## Requirements

### Core Networking

#### R1: Network isolation and connectivity

VirtualNetworks must provide tenant isolation. Subnets within a VirtualNetwork
must provide L2 and L3 connectivity. These guarantees must hold regardless of
the physical location of the resource or the infrastructure it runs on. The
fabric is the single source of truth for isolation across all resource types.

**Acceptance criteria:**
- Resources in different VirtualNetworks cannot communicate (full isolation)
- Resources in the same Subnet are in the same L2 broadcast domain
- Resources in different Subnets within the same VirtualNetwork can
  communicate via Layer 3 routing
- SecurityGroups control which traffic is permitted within these boundaries
  — enforced by the fabric for all resource types
- Bare-metal servers in the same Subnet are in the same broadcast domain
  regardless of their physical location (rack, switch)
- VMs in the same Subnet are in the same broadcast domain regardless of
  which hypervisor host or hosting cluster they run on

#### R2: Infrastructure-agnostic subnets

The same subnet must be able to host VMs, BM servers, and cluster nodes.
The tenant does not declare the resource type when creating a VirtualNetwork
or Subnet. Multiple hosting clusters per region are supported — VMs on
different hosting clusters share the same subnet via the fabric.

**Acceptance criteria:**
- VMs participate in the fabric via the K8s manager — once bridged, VMs
  are reachable from the fabric at their subnet IP
- The dispatcher provisions both K8s overlay and fabric segments for each
  subnet
- Any resource type (ComputeInstance, Cluster, BaremetalInstance) can be
  placed on any subnet
- The fabric manager handles VMs uniformly alongside BM servers — no
  intermediary bridge needed per ExternalIP or SecurityGroup operation
- SecurityGroup enforcement for VMs is handled by the fabric, not by a
  separate K8s-level ACL

#### R3: Uniform networking across all service types

All three service types (VMaaS, CaaS, BMaaS) must consume the networking API
using the same resource model: VirtualNetwork, Subnet, SecurityGroup,
ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway.

**Acceptance criteria:**
- ComputeInstance, Cluster, and BaremetalInstance all have a
  `network_attachments` field using the same `NetworkAttachment` message
- ExternalIPAttachment supports all three as targets
- The tenant workflow for creating networking resources is identical
  regardless of service type

### External Access

#### R4: ExternalIP is external to the VirtualNetwork

"External" means external to the VirtualNetwork — OSAC does not prescribe
whether the IPs are internet-routable, intranet-only, or data-center-local.
The provider defines the pools; the API is the same regardless.

**Acceptance criteria:**
- ExternalIP semantics do not depend on internet reachability
- The API and workflow are identical for all deployment topologies
  (air-gapped, internet-connected, intranet-only)
- CaaS clusters can provision using any routable ExternalIPs for API server
  and ingress

#### R5: Clear ingress/egress separation

The API must clearly separate inbound and outbound external access.

**Acceptance criteria:**
- ExternalIPAttachment handles inbound traffic only (DNAT)
- NATGateway handles outbound SNAT only — it is optional and provides a
  dedicated egress identity, not a prerequisite for basic connectivity
- The fabric manager handles both DNAT and SNAT uniformly for all resource
  types — VMs, BM servers, and cluster nodes are all on the fabric

### Provider Architecture

#### R6: Pluggable managers with transparent selection

Providers configure which fabric manager and K8s manager handle networking
for a region. Tenants never choose networking managers — the system selects
them based on the provider's NetworkClass configuration.

**Acceptance criteria:**
- NetworkClass is not exposed in the tenant API
- The fabric manager handles all physical networking (isolation, ACLs, IP
  allocation, DNAT, SNAT) as a single product
- The K8s manager handles VM-to-fabric bridging as a single product
- Managers are self-registering via ConfigMaps deployed with the OSAC
  installation
- The system validates that a manager supports its assigned role
- A new manager can be added by deploying a ConfigMap and an Ansible role —
  no API or operator changes needed

### Resource-Specific

#### R7: Per-interface network attachment for bare metal

Bare-metal servers have multiple physical interfaces. Tenants must be able to
attach different interfaces to different Subnets based on the interface
descriptions provided by the template.

**Acceptance criteria:**
- `BaremetalInstanceTemplate` describes available interfaces (name,
  description)
- `NetworkAttachment` includes an optional `interface` field that references
  a named interface from the template
- Multiple `network_attachments` are supported — one per physical interface
- The same interface cannot appear in multiple attachments
- All referenced subnets must belong to the same VirtualNetwork

### Simplified Resource Creation

#### R8: Default networking resources per tenant

At tenant onboarding, the system provisions a set of default networking
resources (VirtualNetwork, Subnet, SecurityGroup) per tenant, eliminating
the need for tenants to understand the networking resource model before
creating their first resource.

**Acceptance criteria:**
- Default VirtualNetwork, Subnet, and SecurityGroup are created at tenant
  onboarding, before the tenant creates any resources
- The tenant transitions to READY only after all default networking
  resources are also READY
- Default VirtualNetwork is created per tenant using the
  provider-configured default CIDR on the NetworkClass
- Default Subnet is created within the default VirtualNetwork
- Default SecurityGroup is created within the default VirtualNetwork with
  provider-configured default rules
- When a resource is created without `network_attachments`, the system
  resolves the tenant's defaults
- Default resources are labeled with `osac.openshift.io/default: "true"`
  and are visible in List/Get operations
- Default resources can be modified by the tenant (e.g., adding
  SecurityGroup rules) but cannot be deleted while resources depend on them
- Creating custom VirtualNetworks does not affect default resources — both
  coexist
- Two CIDR modes are supported, configured per NetworkClass: `shared_cidr`
  (default — all tenants receive the same CIDR range, fabric-level
  isolation separates them) and `isolated_cidr` (each tenant gets a unique
  CIDR slice from the provider's supernet)

#### R9: Optional network_attachments for simplified resource creation

The `network_attachments` field on ComputeInstance, Cluster, and
BaremetalInstance is optional. When omitted, the system resolves defaults:
default Subnet and default SecurityGroup for the tenant.

**Acceptance criteria:**
- ComputeInstance, Cluster, and BaremetalInstance can be created without
  specifying `network_attachments`
- The system populates `network_attachments` using the tenant's default
  Subnet and default SecurityGroup
- The resolved `network_attachments` are stored in the resource spec (the
  resource spec is self-describing after creation)
- If the resource is created with explicit `network_attachments`, no
  defaults are applied
- If defaults cannot be resolved (e.g., no defaults configured on the
  NetworkClass), the create request fails with a clear error

#### R10: Auto ExternalIP provisioning

Resources can request automatic ExternalIP allocation at creation time. The
system auto-selects the READY ExternalIPPool with the most available
capacity, creates an ExternalIP and ExternalIPAttachment, and establishes
ownership so that auto-created resources are garbage-collected when the
parent is deleted.

**Acceptance criteria:**
- ComputeInstance and BaremetalInstance support an `external_ip_mode` field
  with values `NONE` (default) and `AUTO`
- Cluster supports a `external_ip_mode` field with values `NONE`
  (default), `AUTO_API`, `AUTO_INGRESS`, and `AUTO_ALL` (both API and
  ingress)
- All resource types support a `nat_gateway_mode` field with values `NONE`
  (default) and `AUTO`
- When `AUTO` is requested, the system auto-selects the READY pool with
  the most available capacity, creates an ExternalIP and an
  ExternalIPAttachment binding it to the resource
- For clusters with `AUTO_ALL`, two ExternalIPs and two
  ExternalIPAttachments are created (one for API, one for ingress)
- For clusters, ExternalIPs are allocated before provisioning is dispatched,
  resolving the CaaS prerequisite ordering requirement
- Auto-created ExternalIP and ExternalIPAttachment resources have an
  owner-reference annotation pointing to the parent resource
- When the parent resource is deleted, auto-created ExternalIPs and
  ExternalIPAttachments are garbage-collected
- Auto-created resources are visible in List/Get operations and are labeled
  with `osac.openshift.io/auto-provisioned: "true"`
- If no ExternalIPPool has available capacity, the resource creation fails
  with a clear error
- When `nat_gateway_mode=AUTO`, the system auto-selects an ExternalIP
  from the best available pool and creates a NATGateway on the resource's
  VirtualNetwork using that ExternalIP as the SNAT source; if a NATGateway
  already exists on the VN, it is reused (one NATGateway per VN)

## Success Metrics

- All three service types consume the same networking API (R3)
- No service type bypasses the networking API for network configuration (R3)
- A new manager can be added without modifying existing managers or the API (R6)
- Tenant experience is uniform across service types — same resources, same
  workflow, same CLI patterns (R3, R4)
- A tenant can create a reachable VM with a single API call, without
  pre-creating any networking resources (R8, R9, R10)
- A tenant can create a fully connected cluster (API + ingress + outbound)
  with a single API call (R8, R9, R10)

## Technical Design

The technical design fulfilling these requirements is described in:
[Unified Networking Design](/enhancements/unified-networking)
