---
title: Unified Networking Requirements for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-10-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking
  - Network Manager Integration Contract PRD: /enhancements/OSAC-1433-network-manager-integration-contract/prd.md
  - Network Manager Integration Contract Design: /enhancements/OSAC-1433-network-manager-integration-contract/design.md
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
    [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api)).

- **VirtualNetwork**: A tenant's isolated network environment with its own
  address space (CIDR). Analogous to a cloud VPC or VNet.

- **Subnet**: A subdivision of a VirtualNetwork's IP address space. Resources
  are attached to subnets to receive IP addresses and network connectivity.

- **SecurityGroup**: A stateful firewall controlling inbound and outbound
  traffic for resources. Rules specify allowed protocols, ports, and
  source/destination addresses.

- **ExternalIPPool**: A provider-defined pool containing exactly one canonical
  IPv4 CIDR for addresses routable outside the VirtualNetwork. "External"
  means external to the VN — not necessarily internet-routable (see gap #8).
  The API's repeated `cidrs` field is retained for compatibility, but
  validation rejects zero or multiple entries.

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

- **K8s Manager**: Provides Kubernetes-native VM networking. With a fabric
  manager, it connects VM networking to the physical fabric. Without a fabric
  manager, it provides the primary Subnet network for VMs on the hub; it does
  not provide fabric connectivity.

- **Fabric**: The physical network infrastructure — switches, routers, and
  gateways — that connects bare-metal servers and provides external
  connectivity. Fabric-backed profiles can connect VMs to this network through
  a K8s manager. A K8s-only profile has no physical-fabric integration.

Provider-dependent connectivity and allocation in this document apply when
provider networking is enabled. FR-10 defines the installation/upgrade setting,
including the Enclave Wizard checkbox, and the disabled user experience.
Networking API authorization, validation, defaulting, reference checks, and
SecurityGroup rule schema and immutability apply in both modes. When disabled,
OSAC submits no provider operation to apply or remove SecurityGroup rules. Rules
already programmed in the backend may continue to affect traffic until
provider-side cleanup. [User]

## 1. Problem Statement

The OSAC Networking API must serve as a foundational service across all three
OSAC service types — VMaaS, CaaS, and BMaaS — with a single, consistent
resource model. The technical design that fulfills these requirements is
described in a companion enhancement:
[Unified Networking Design](/enhancements/OSAC-1433-unified-networking).

An earlier Networking API proposal was designed with VMaaS (ComputeInstance) as
the only consumer, explicitly listing CaaS and
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

### Supported Address-Family Boundary

All networking resources and traffic described by this PRD use canonical IPv4
CIDRs and IPv4 addresses. IPv6 and dual-stack networking are not supported;
requests that contain them are rejected before persistence or backend
dispatch.

> **Implementation status:** This is the normative target contract for the
> unified networking architecture. The current implementation still exposes
> legacy IPv6/dual-stack schema fields and accepts family-agnostic manager
> registrations and allocation defaults. Fulfillment-service and operator
> enforcement—including IPv4-only validation and `IP_FAMILY_IPV4` selection—
> must land before this contract is considered implemented.

### Gaps in the Current Design

#### Gap #1: CaaS and BMaaS have no networking API

The Networking API only supports ComputeInstance (VMaaS). The Cluster resource
has no network configuration — there is no way for a tenant to specify
which VirtualNetwork, Subnet, or SecurityGroup a cluster's nodes should use.
A tenant cannot place two clusters in the same VirtualNetwork to share an
address space, or isolate clusters in separate VirtualNetworks — the networking
is entirely opaque and managed ad-hoc by the CaaS template role.

The same applies to BMaaS. BaremetalInstance (defined in
the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api))
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

Manager profiles offer different workload targets and network
operations. A K8s-only profile supports VMs on the hub and inbound access for
those VMs, but does not support CaaS or bare-metal targets, inter-Subnet
routing, or outbound NAT. A fabric-backed profile can support shared VM, CaaS,
and bare-metal networks when its configured managers provide those operations.
The system needs machine-readable manager capabilities and validation that the
configured profile supports its assigned operations.

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

In fabric-backed deployments, VMs running on OpenShift use OVN networks and
their IP addresses are not visible on the physical fabric. When a Fabric
Manager must route external traffic directly to a VM, the K8s manager must
bridge the VM overlay to the fabric. K8s-only deployments use a primary CUDN
on the hub and intentionally do not require this physical-fabric bridge. The
design must support both profiles and make their different network behavior
explicit.

#### Gap #7: VMs and bare metal cannot share a network

OVN VM networks and physical VLANs are different L2 domains. In a
fabric-backed profile, a K8s manager using LocalNet can bridge VMs to the
physical fabric so VMs and bare-metal servers can share a VirtualNetwork.
A K8s-only profile supports hub-hosted VMs and does not provide cross-type
placement with bare-metal servers. The design must state which profile offers
each behavior.

#### Gap #8: Deployment connectivity boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected networking deployments are outside the supported
boundary. In a supported deployment, the provider-owned hub, selected network
managers, and OSAC networking services must be able to reach one another and
the provider-controlled address infrastructure. "External" still means
external to the VirtualNetwork; it does not by itself imply Internet
reachability.

#### Gap #9: CaaS has unique prerequisite ordering

~~Cluster worker nodes reach the hosted control plane API server via hairpin
NAT through ExternalIPs, requiring ExternalIPs and NATGateway to exist before
provisioning.~~ **Resolved:** The CaaS design eliminates hairpin NAT — workers
access the API server via the MetalLB VIP directly on the same subnet. The
pre-provisioning ordering constraint is eliminated. ExternalIPs are for
external (off-subnet) access only, not for intra-cluster communication.
ExternalIPAttachments for a cluster are created only after the cluster is Ready
and the ExternalIP is Allocated, in accordance with the shared resource
lifecycle rules (see [CaaS Networking](/enhancements/OSAC-1436-caas-networking)).

## 2. Goals and Non-Goals

### 2.0 Current workload attachment constraint

VMaaS, BMaaS, and CaaS support at most one tenant network attachment per
workload. VMaaS and BMaaS retain their repeated `network_attachments` fields
for wire and API compatibility; the API validates that the list contains zero
or one entry. CaaS retains its existing singular `network_attachment` field.
With exactly one attachment, it is the default route/primary attachment. The
BMaaS attachment retains its existing optional `primary` field; with one
attachment, omitting it has the same meaning as `primary: true`, while
`primary: false` is rejected. VMaaS has no primary field, and CaaS has no
primary concept. Omitted or empty attachment lists receive tenant defaults;
partial supplied attachments receive defaults only for missing fields. A
missing or explicitly empty `security_groups` list is treated as missing; the
default SecurityGroup applies only when the resolved Subnet belongs to the
tenant's default VirtualNetwork, otherwise the caller must provide
SecurityGroups from the resolved Subnet's VirtualNetwork. The resolved
attachment list and fields are immutable after creation.
Multi-NIC workload networking is future scope and is not enabled by the
plural field shape.

### 2.1 Goals

- Provide a unified networking API across VMaaS, CaaS, and BMaaS with a single, consistent resource model
- Enable tenants to manage networking resources (VirtualNetworks, Subnets, SecurityGroups, ExternalIPs) without choosing implementation backends
- Support pluggable networking backends that can be added without API changes
- Enable VMs, clusters, and bare-metal servers to coexist in the same
  VirtualNetwork in fabric-backed profiles; provide hub-hosted VM networking
  through a K8s-only profile without physical-fabric integration
- Support connected deployments using provider-routable IPs
- Support one tenant network attachment per workload, with an optional physical-interface selector for BMaaS

### Deployment support boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected networking deployments are not supported and must
not be advertised as supported deployment profiles. The provider owns the
connectivity configuration: the hub, selected network managers,
provider-controlled networking services, and provider-controlled address
infrastructure must have connected reachability before the deployment's
NetworkClass is accepted. Connectivity is not tenant selectable, and this
boundary applies to Fabric-only, K8s-only, and combined manager profiles.

### Networking hub support boundary

OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

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
  supported for the sole attachment via the `interface` field on
  BareMetalNetworkAttachment)
- Load Balancer API
- Internet Gateway API
- Quota enforcement for networking resources

## 3. User Stories

### Tenant Stories (Shared Networking API)

- As a tenant, I want to create isolated VirtualNetworks and Subnets for my
  workloads without choosing a networking backend
- As a tenant, I want to define SecurityGroups to control traffic to and
  from my resources
- As a tenant, I want to update a SecurityGroup's ingress and egress
  rules so that the effective policy can change without recreating the group
- As a tenant, I want to allocate ExternalIPs and attach them to supported
  VM, cluster, or bare-metal targets for inbound access
- As a tenant in a fabric-backed deployment, I want to create a NATGateway
  for outbound access from my VirtualNetwork
- As a tenant in a K8s-only deployment, I want to attach VMs to primary
  Subnets on the hub so I can use Kubernetes-native networking without a
  physical fabric manager [User]
- As a tenant, I want resource creation to fail immediately if a referenced
  resource is not fully ready, so that I do not end up with resources stuck
  waiting for prerequisites
- As a tenant, I want resource deletion to fail immediately if other
  resources still depend on the one I am deleting, so that I do not
  accidentally break running workloads

### CaaS-Specific Stories

- As a tenant in a fabric-backed deployment, I want to place my cluster's
  worker nodes on a Subnet in my VirtualNetwork
- As a tenant in a fabric-backed deployment, I want to attach ExternalIPs
  to my cluster's API server and ingress endpoints after the cluster is ready
- As a tenant in a fabric-backed deployment, I want my cluster to work in
  the provider's connected network using provider-routable IPs

### BMaaS-Specific Stories

- As a tenant in a fabric-backed deployment, I want to place my
  BaremetalInstance on Subnets in my VirtualNetwork
- As a tenant, I want to see the available physical interfaces on a bare-metal
  template so I can decide how to attach networks
- As a tenant, I want to select the physical interface used by my
  BaremetalInstance's single tenant network attachment
- As a tenant in a fabric-backed deployment, I want to attach an ExternalIP
  to my bare-metal server for inbound access

### Provider Stories

- As a provider, I want to configure networking backends without exposing
  implementation details to tenants
- As a provider, I want to add new networking backends without modifying
  the API
- As a provider, I want to add new networking backends through
  configuration, not code changes
- As a provider, I want to be able to provision ExternalIP pools for tenants

- As a Cloud Provider Admin, I want to disable OSAC network-provider operations through Helm or an Enclave Wizard checkbox during installation or upgrade while retaining networking APIs and ordinary workload provisioning [User]

## 4. Requirements

### 4.1 Functional Requirements

#### FR-1: Network isolation and connectivity (R1)

VirtualNetworks provide tenant isolation. Subnets provide Layer 2 connectivity
for workloads supported by the selected manager profile. Fabric-backed
profiles provide Layer 3 routing between Subnets in the same VirtualNetwork.
K8s-only networking supports hub-hosted VMs and does not provide routed
connectivity between Subnets. These guarantees apply to supported workload
targets; requests for unsupported targets or operations must fail clearly.

#### FR-2: Infrastructure-agnostic subnets (R2)

In fabric-backed profiles, the same Subnet can host supported VMs, bare-metal
servers, and cluster nodes, regardless of physical location or hosting
infrastructure. The tenant does not declare the resource type when creating a
VirtualNetwork or Subnet. A K8s-only profile supports VM workloads on the hub
cluster and does not claim cross-hosting-cluster or cross-service placement.

#### FR-3: Uniform networking across all service types (R3)

VMaaS, CaaS, and BMaaS consume the same tenant-facing networking resource
model. The selected manager profile determines which workload targets and
network operations are available; a K8s-only profile supports VMs on the hub,
while fabric-backed profiles can support the workload types implemented by
their configured managers. [User]

#### FR-4: ExternalIP is external to the VirtualNetwork (R4)

"External" means external to the VirtualNetwork — OSAC does not prescribe
whether the IPs are internet-routable, intranet-only, or data-center-local.
The provider defines the pools; the API is the same regardless.

#### FR-5: Clear ingress/egress separation (R5)

The API must clearly separate inbound and outbound external access.

#### FR-6: Pluggable networking backends with transparent selection (R6)

Providers configure the networking manager profile for a deployment. Tenants
never choose networking backends; the system selects them based on provider
configuration. Each Fabric Manager and K8s Manager role may use any
implementation that conforms to the published OSAC Network Manager Integration
Contract, regardless of who builds, publishes, or distributes it; implementations
distributed with OSAC follow the same contract. The configured profile
determines supported workload targets and operations. Requests for an
unsupported target or operation fail with a clear diagnostic instead of being
silently sent to another manager. [User]

#### FR-7: Single network attachment per workload (R7)

ComputeInstance, BaremetalInstance, and Cluster each support at most one
tenant network attachment. Bare-metal tenants may select the physical
interface for that attachment based on the interface descriptions provided by
the template. The VMaaS and BMaaS repeated fields remain repeated for API
compatibility, but requests containing more than one entry are rejected.

#### FR-8: Networking resource operations (R8)

The networking resources defined by this PRD — `NetworkClass`,
`VirtualNetwork`, `Subnet`, `SecurityGroup`, `ExternalIPPool`, `ExternalIP`,
`ExternalIPAttachment`, and `NATGateway` — support create, read, and delete
operations. Read includes `List` and `Get`. SecurityGroup ingress and egress
rules also support update. An update replaces the effective rule set with the
requested rules: omitted rules are removed, and repeating the same update
leaves the same effective policy. This desired-state update behavior is
required for retries. Other SecurityGroup fields, metadata, all other
networking resource specifications and metadata, and workload network
attachments remain immutable after creation; changing them requires deleting
and recreating the resource or parent workload. [User]

Controller-owned status, condition, readiness, and IP-discovery updates are
internal reconciliation and do not add a tenant/provider update operation.
This is the normative contract for the VMaaS, CaaS, and BMaaS proposals that
reference this PRD; those proposals inherit it and do not redefine networking
operations.

#### FR-9: Strict resource lifecycle enforcement (R9)

The fulfillment-service must enforce resource dependency constraints at the
API layer, rejecting invalid operations immediately rather than accepting
them and relying on asynchronous operator-side reconciliation to handle
ordering.

**Creation:** A resource that references another resource may only be created
when every referenced resource is in its terminal ready state (Ready or
Allocated, depending on the resource type). If a referenced resource does not
exist, is not ready, or is being deleted, the create request must be rejected
with a precondition error. There are no exceptions to this rule. Internal
fulfillment-service flows — `auto_external_ip_attachment` and default
networking tenant onboarding — follow the same readiness gates by creating
resources in dependency order and waiting for each to reach its ready state
before creating the next (e.g., the auto-provisioned ExternalIPAttachment is
created only after the ExternalIP is Allocated and the target workload is
Ready).

**Deletion:** A resource may only be deleted when no other active resource
references it — only dependency-graph leaves are deletable. If active
dependents exist, the delete request must be rejected with a precondition
error listing the blocking resource type. Auto-provisioned resources (labeled
`osac.openshift.io/auto-created`) are cascade-deleted when their parent
workload is deleted, because the system created them and controls the full
dependency chain. Even for auto-provisioned resources, cascade deletion must
follow dependency order (ExternalIPAttachment before ExternalIP).

Default networking resources (labeled `osac.openshift.io/default`) follow the
same rules — they cannot be deleted while any workload or networking resource
references them.

#### FR-10: Provider networking control at installation or upgrade

A Cloud Provider Admin can enable or disable OSAC network-provider operations
with one installation/upgrade setting in Helm or an Enclave Wizard checkbox. The setting
defaults to enabled and takes effect through rollout; it is not a live console
control. Networking APIs remain available through API, CLI, and UI, with the
same authorization, tenant isolation, validation, defaulting, supported
operations, and dependency constraints. [User]

When disabled, valid networking requests still manage OSAC objects, but no
provider network configuration, address allocation, routing, or cleanup runs.
This applies to VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool,
ExternalIP, ExternalIPAttachment, and NATGateway. All networking
specification and metadata updates, including SecurityGroup rule changes,
remain rejected under the published create/read/delete contract. With the
setting disabled, OSAC submits no provider operation to apply, change, or remove
SecurityGroup rules. Rules already programmed in the backend may continue to
affect traffic until provider-side cleanup. Existing network operations are
cancelled and awaited before status reports skipped or deletion releases a
finalizer. Cancellation is not rollback: a job that completes before
cancellation takes effect remains a confirmed provider outcome, and OSAC does
not launch a compensating cleanup job while disabled. After logical
preconditions pass, VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool,
ExternalIPAttachment, and NATGateway report `Ready=True`, reason
`ProvisioningDisabled`, with a message naming the skipped provider operation.
This is logical OSAC readiness only; it does not assert provider connectivity,
policy enforcement, or routing. An object whose dependency or target is not
ready remains in its ordinary waiting state.

An ExternalIP with no confirmed provider allocation reports
`state=Pending`, `phase=Progressing`, an empty address, and `Ready=False`, reason
`ProvisioningDisabled`. A confirmed allocation retains its real assigned
address and `state=Allocated`, but reports `phase=Progressing` and
`Ready=False`, reason `ProvisioningDisabled`, with a message that the address
is last-known and is not being reconciled or guaranteed reachable. OSAC never
selects an address from the pool CIDR and never writes a placeholder such as
`0.0.0.0`. Existing sentinel records are cleared to Pending/empty; attachments
that depended on a sentinel wait for a real allocation. Automatic ExternalIP
requests still undergo the same pool/capacity validation, but the workload
continues while the ExternalIP is Pending. Creating the Pending ExternalIP
reserves its selected pool capacity in OSAC until that logical ExternalIP is
deleted; this is not a provider address allocation. No automatic
ExternalIPAttachment is created until a real allocation and a Ready target are
both confirmed. Deleting an OSAC object may leave provider resources requiring
manual or provider-side cleanup. If an already allocated ExternalIP is deleted
while provider networking is disabled, OSAC releases its logical pool-capacity
slot when the object is deleted, while the old provider reservation may remain
until manual cleanup. Re-enabling resumes reconciliation for resources that
still exist; deleted objects do not trigger provider cleanup after the fact.
[User]

During tenant onboarding with provider networking disabled, the default
VirtualNetwork, Subnet, and SecurityGroup remain available for default
attachment resolution. The default ExternalIP and NATGateway are omitted until
provider networking is enabled. Once those logical defaults are ready, the
tenant becomes READY for workload provisioning without a promise of provider
connectivity or outbound NAT. [User]

Ordinary VM, cluster, and bare-metal host provisioning remains available when
its unchanged API prerequisites are met. VMs use platform default networking;
new bare-metal hosts remain on provisioning connectivity, without tenant port
moves or tenant IP discovery. Each incomplete BM
`NetworkAttachmentsReady`, `NetworkHandoffComplete`, and
`IPDiscoveryComplete` phase skipped after disablement reports
`Unknown`/`ProvisioningDisabled`; phases confirmed before disablement retain
their `True` result. Legacy `True`/`Skipped` conditions from the current
disabled path are normalized to `Unknown`/`ProvisioningDisabled`. Progress
derivation treats only `True` or `Unknown` with that exact reason as complete.
A BM Ready state then means OS provisioning completed, not tenant connectivity.
CaaS requires baseline platform/provisioning
connectivity, including access to control-plane services and installation
dependencies; OSAC provides no tenant routing or public ExternalIP routing in
this mode. Network-dependent behavior elsewhere in this PRD describes the
enabled mode. [User]

### 4.2 Non-Functional Requirements

_No non-functional requirements were specified in the original document._

## 5. Acceptance Criteria

The connectivity, allocation, and provider cleanup criteria below apply when
provider networking is enabled. API validation, create/read/delete semantics,
SecurityGroup immutability, and lifecycle constraints apply in both modes.
[User]

### Core Networking

- [ ] Resources in different VirtualNetworks cannot communicate
- [ ] Resources in the same Subnet have Layer 2 connectivity for the workload types supported by the selected profile
- [ ] Fabric-backed profiles route between Subnets in the same VirtualNetwork; K8s-only networking does not provide inter-Subnet routing
- [ ] SecurityGroups control permitted traffic for workload targets supported by the selected profile
- [ ] Fabric-backed profiles can place supported VM, bare-metal, and cluster workloads on shared Subnets regardless of physical location
- [ ] K8s-only networking supports hub-hosted VMs on primary Subnets and does not claim fabric connectivity
- [ ] The system provisions the networking resources required by the selected manager profile
- [ ] Fabric-backed profiles support the workload targets implemented by their configured managers; a K8s-only profile supports VM workloads on the hub, and a fabric-only profile without a K8s manager does not support VMs
- [ ] SecurityGroup and ExternalIP behavior applies to every workload target supported by the selected profile
- [ ] Each workload supports at most one tenant network attachment
- [ ] Fabric-backed profiles support ExternalIPAttachment targets for VMs, clusters, and bare-metal servers; K8s-only networking supports VM targets only
- [ ] Tenants use the shared networking resource model across service types; available operations and targets depend on the provider-configured profile
- [ ] Networking resources support Create, List/Get, and Delete; SecurityGroup ingress and egress rules also support Update. Other networking resource fields and workload network attachments remain immutable after creation
- [ ] Updating SecurityGroup ingress or egress rules sets the effective policy to exactly the requested rule set, removes rules omitted from the update, and repeated identical updates leave the same result

### Provider Networking Control (FR-10)

- [ ] A Cloud Provider Admin can disable or enable provider networking during installation or upgrade through Helm or the Enclave Wizard checkbox, with the same setting applying across services after rollout
- [ ] With provider networking disabled, API, CLI, and UI networking operations retain their existing authorization, validation, defaulting, immutability, and dependency errors
- [ ] Valid creates and deletes for all seven network resource kinds complete their OSAC object lifecycle without configuring or cleaning up provider networking; specification and metadata updates remain rejected, including SecurityGroup rule changes
- [ ] After logical prerequisites pass, non-allocating Networking API resources report `Ready=True` with reason `ProvisioningDisabled`; resources with unmet dependencies remain waiting
- [ ] An ExternalIP without a confirmed provider allocation remains `Pending`/`Progressing`, has an empty address, and reports `Ready=False`/`ProvisioningDisabled`; a confirmed real allocation retains its assigned address and `Allocated` state but reports `Ready=False`/`ProvisioningDisabled` while the provider is disabled
- [ ] Automatic ExternalIP requests retain synchronous pool/capacity validation and reserve capacity while Pending, without blocking workload provisioning; an attachment is created only after a real allocation and a Ready target are confirmed
- [ ] Deleting an ExternalIP while disabled releases its OSAC capacity slot with the logical object, submits no provider release, and may leave a prior provider reservation for manual cleanup
- [ ] Disabled tenant onboarding makes default VirtualNetwork, Subnet, and SecurityGroup available for workload defaulting, omits the provider-dependent ExternalIP and NATGateway, and does not promise outbound NAT
- [ ] Previously active network operations are cancelled and awaited before skipped status or deletion-finalizer release; a job that completes first remains a real provider outcome and does not trigger disabled-mode rollback; provider resources may remain for manual or provider-side cleanup
- [ ] Ordinary VM, cluster, and bare-metal host provisioning remains available with the stated platform/provisioning connectivity limitations and unchanged API prerequisites
- [ ] Core ClusterOrder install/delete jobs remain active while tenant VIP allocation, IPAM, public DNS/routing, and provider cleanup are absent when networking is disabled
- [ ] Incomplete BM network phases skipped after disablement use `Unknown`/`ProvisioningDisabled`, confirmed earlier phases retain `True`, and legacy disabled `True`/`Skipped` conditions are normalized; progress accepts only the exact Unknown/ProvisioningDisabled skip and BM Ready does not claim tenant networking
- [ ] Enabling provider networking preserves the manager-profile behavior described by FR-1 through FR-9

### Resource Lifecycle Enforcement

- [ ] Creating a Subnet when the referenced VirtualNetwork is not Ready is rejected by the API
- [ ] Creating a SecurityGroup when the referenced VirtualNetwork is not Ready is rejected by the API
- [ ] Creating a NATGateway when the referenced VirtualNetwork is not Ready is rejected by the API
- [ ] Creating a NATGateway when the referenced ExternalIP is not Allocated is rejected by the API
- [ ] Creating an ExternalIP when the referenced ExternalIPPool is not Ready is rejected by the API
- [ ] Creating an ExternalIPAttachment when the referenced ExternalIP is not Allocated is rejected by the API
- [ ] Creating an ExternalIPAttachment when the referenced target resource (ComputeInstance, Cluster, or BaremetalInstance) is not Ready is rejected by the API
- [ ] Creating a VirtualNetwork when the referenced NetworkClass is not Ready is rejected by the API
- [ ] Auto-provisioned ExternalIPAttachments (via `auto_external_ip_attachment`) are created by the fulfillment-service internal reconciler only after the ExternalIP is Allocated and the target workload is Ready — no exception to readiness rules
- [ ] Deleting a VirtualNetwork that has active Subnets, SecurityGroups, NATGateways, or FabricDomains is rejected by the API
- [ ] Deleting a Subnet that has active ComputeInstances, Clusters, or BaremetalInstances attached is rejected by the API
- [ ] Deleting an ExternalIP that has active ExternalIPAttachments or NATGateways is rejected by the API
- [ ] Deleting an ExternalIPPool that has active ExternalIPs is rejected by the API
- [ ] Deleting a ComputeInstance, Cluster, or BaremetalInstance that has active manually-created ExternalIPAttachments is rejected by the API
- [ ] Deleting a SecurityGroup that is referenced by active ComputeInstances, Clusters, or BaremetalInstances is rejected by the API
- [ ] Auto-provisioned resources (labeled `osac.openshift.io/auto-created`) are cascade-deleted when their parent workload is deleted, following dependency order
- [ ] Rejection errors include the blocking resource type so the tenant knows what to delete first

### External Access

- [ ] ExternalIP semantics do not depend on internet reachability
- [ ] The supported deployment topology is connected only; air-gapped and disconnected networking deployments are rejected before provisioning
- [ ] ExternalIPPool creation requires `spec.ipFamily` to be `IP_FAMILY_IPV4` and rejects `IP_FAMILY_UNSPECIFIED`, IPv6, and dual-stack values before persistence
- [ ] ExternalIPPool validation accepts exactly one canonical IPv4 CIDR in the repeated `cidrs` field and rejects empty or multiple entries
- [ ] Supported networking deployments use exactly one provider-owned hub; multi-hub networking placement, cross-hub resource coordination, and cross-hub network connectivity are unsupported
- [ ] Fabric-backed CaaS clusters can use provider-routable ExternalIPs for API server and ingress endpoints after the cluster is Ready
- [ ] ExternalIPAttachment handles inbound traffic only, with supported targets determined by the selected profile
- [ ] NATGateway is optional and provides a dedicated egress identity in profiles with a fabric manager; K8s-only profiles reject NATGateway requests clearly
- [ ] Fabric-backed external access applies to workload targets supported by the profile; K8s-only networking provides inbound VM access without managed outbound NAT

### Provider Architecture

- [ ] Networking backend configuration is not exposed in the tenant API
- [ ] In fabric-backed profiles, one fabric manager handles physical networking operations; a K8s manager may connect VM networking to the fabric
- [ ] A K8s-only profile provides VM networking on the hub without physical-fabric integration
- [ ] VM and bare-metal networking share the fabric when the configured profile supports both
- [ ] Networking managers are registered through configuration deployed with the OSAC installation
- [ ] The system validates that the configured profile supports its assigned workload targets and operations
- [ ] A Cloud Infrastructure Admin can select a manager implementation from any source for each configured role when it conforms to the published Network Manager Integration Contract; implementations distributed with OSAC use the same contract
- [ ] A Cloud Infrastructure Admin can make a new conforming manager available while tenants continue to use the same OSAC networking API

### Resource-Specific (Bare Metal)

- [ ] BareMetalInstanceTypes describe available network ports (name, role, type, speed) for bare-metal servers
- [ ] Bare-metal network attachments include an optional interface reference that identifies a named port from the BareMetalInstanceType
- [ ] A bare-metal network attachment may select one named port from the BareMetalInstanceType
- [ ] Requests containing more than one bare-metal network attachment are rejected
- [ ] The referenced subnet belongs to the same VirtualNetwork as its security groups

## 6. Dependencies

- **Unified Networking Design**: [/enhancements/OSAC-1433-unified-networking](/enhancements/OSAC-1433-unified-networking) — Technical design document fulfilling these requirements
- **Network Manager Integration Contract PRD**: [/enhancements/OSAC-1433-network-manager-integration-contract/prd.md](/enhancements/OSAC-1433-network-manager-integration-contract/prd.md) — Defines source-neutral manager requirements
- **Network Manager Integration Contract Design**: [/enhancements/OSAC-1433-network-manager-integration-contract/design.md](/enhancements/OSAC-1433-network-manager-integration-contract/design.md) — Defines the normative manager interface
- **Default Networking**: [/enhancements/OSAC-1433-default-networking](/enhancements/OSAC-1433-default-networking) — Related enhancement for resource ordering workflow
- **BareMetal Instance API**: [/enhancements/OSAC-1118-baremetal-instance-api](/enhancements/OSAC-1118-baremetal-instance-api) — Defines BaremetalInstance resource
- **Three-Layer Networking Model**: [Google Doc](https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM) — Architectural reference

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"1f3b63b82","source_repo_branch":"main","commits_behind_main":52,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","manual-edit","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
