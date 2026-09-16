---
title: Unified Networking Requirements for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-09-16
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
see-also:
  - Unified Networking Design: /enhancements/OSAC-1433-unified-networking
  - K8s-only Networking Manager: /enhancements/OSAC-1433-k8s-only-k8s-manager
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
  SecurityGroups, NetworkACLs, ExternalIPs) and place workloads on them.

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
  applies. Every selected manager receives the complete NetworkACL lifecycle.
  A temporary unfinished backend may use a successful no-op AAP role; this is
  not an API capability gate. Native Kubernetes NetworkPolicy alone is not a
  substitute for the OSAC stateless ACL contract.

- **SecurityGroup**: A stateful, VirtualNetwork-scoped policy selected by a
  workload's network attachment. SecurityGroup rules are allow-only: they
  specify direction, protocol, optional single port, and one IPv4
  source/destination CIDR, with no `allow`/`deny` action field. Unmatched
  traffic is denied, and return traffic for an allowed flow is stateful. A
  tenant-created SecurityGroup requires at least one valid rule; the
  auto-created tenant default SecurityGroup may have an empty rule list and
  therefore denies traffic by default. Every selected manager receives the
  complete SecurityGroup lifecycle.

- **ExternalIPPool**: A provider-defined pool of IP addresses that are
  routable outside the VirtualNetwork. "External" means external to the VN —
  not necessarily internet-routable. Multiple deployment-scoped pools are
  supported, but each pool has exactly one IPv4 CIDR. Allocation ranges must
  not overlap unless the selected manager explicitly provides disjoint
  allocation ownership; the provider must never expose two pools that can
  allocate the same address.

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
  complete networking surface for all three workload services in a K8s-only
  deployment. The current K8s-only registration and backend entrypoints are
  defined in the [K8s-only Networking Manager proposal](/enhancements/OSAC-1433-k8s-only-k8s-manager).
  Native Kubernetes NetworkPolicy by itself is not sufficient for either OSAC
  policy contract.

- **Fabric**: The physical network infrastructure — switches, routers,
  gateways — that connects bare-metal servers and provides external
  connectivity. In this design, VMs also participate in the fabric through
  a K8s manager that bridges the OVN overlay to the physical network.

### Address-family scope

All networking resources and traffic described by this PRD use IPv4 CIDRs.
IPv6 and dual-stack networking are not supported.

### Deployment support boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected deployments are not supported. The provider must
configure a deployment with exactly one active hub and connected reachability
between the hub, the selected networking managers, and the provider-controlled
network services required by the deployment. This is deployment-level
configuration, not a tenant-selectable networking mode.

The provider must validate this boundary before the deployment NetworkClass is
accepted. Networking resources and workload attachments must not be admitted
through a deployment that does not satisfy the connected-only requirement.
This rule applies to Fabric-only, K8s-only, and combined-manager deployments.

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

### Deletion and dependency order

Deletion is leaf-first. A delete request is checked against every direct
reverse reference before the target is marked for deletion. The service
returns `FAILED_PRECONDITION` when a tenant-managed dependent still exists and
identifies each blocker by resource kind, ID/name, relationship field, and the
action required to remove it. The same details are available as
machine-readable status details for CLI and UI clients. A rejected request
does not set a deletion timestamp and does not partially delete another
resource.

The check uses indexed direct-reference queries inside the same transaction as
deletion admission. It does not recursively scan the entire dependency graph.
A child that is already deleting but has not been archived or otherwise
confirmed absent continues to block its parent. This prevents backend cleanup
from racing parent deletion. Concurrent creation of a reference is
serialized against deletion and is rejected if the target is no longer
active.

After admission, deletion follows the resource's soft-deletion lifecycle: the
target is marked `Deleting`, its own finalizers complete external cleanup, and
the resource is archived/removed only after that cleanup succeeds. A deletion
timestamp is not equivalent to absence for dependency checks, and a failed
cleanup does not justify removing the finalizer or deleting the parent.

The dependency order is:

```text
ExternalIPAttachment -> target workload and ExternalIP
NATGateway -> ExternalIP and VirtualNetwork
SecurityGroup -> VirtualNetwork, workload attachments, and Catalog Item/Template policy references
NetworkACL -> associated Subnets and VirtualNetwork
Workload network attachment -> Subnet
Subnet -> VirtualNetwork
ExternalIP -> ExternalIPPool
VirtualNetwork -> deployment NetworkClass resolution (provider-only)
```

Therefore, tenants delete workload attachments, SecurityGroups, NetworkACLs,
NATGateways, and ExternalIPAttachments before the Subnet, VirtualNetwork,
ExternalIP, or pool they reference. A SecurityGroup cannot be deleted while a
workload attachment or Catalog Item/Template policy references it. Deleting a
NetworkACL never deletes or detaches its Subnets;
deleting a Subnet never deletes its NetworkACLs or workloads; and deleting a
VirtualNetwork never deletes Subnets, SecurityGroups, NetworkACLs, or NATGateways.
The provider cannot delete or replace a NetworkClass while deployment resources
or manager integrations depend on its resolved manager targets; this is a
provider-only dependency and is not a tenant deletion workflow.

The only cascade exceptions are allowlisted OSAC-owned resources carrying an
exact immutable owner relationship. For workload external access, OSAC deletes
the owned ExternalIPAttachment first, waits for it to disappear, then deletes
the owned ExternalIP. For an onboarding-created default NATGateway, OSAC may
delete only its owned automatic ExternalIP after NATGateway backend cleanup;
VirtualNetwork deletion never directly cascades to the NATGateway or its IP.
Neither exception cascades to the ExternalIPPool or to tenant-created
resources. If a tenant-managed blocker exists, the deletion is rejected
without partially cleaning auto-created resources. Failed auto-cleanup retains
the parent finalizer and leaves the parent in `Deleting` until cleanup
succeeds.

### Creation and dependency readiness

Creation is also leaf/order constrained. Before any network resource, workload,
Catalog/Template materialization, or private service request is persisted, the
service resolves all references and requires each dependency to be usable. A
Subnet or policy resource cannot be created while its VirtualNetwork is
Pending; a workload cannot be created while its resolved Subnet, SecurityGroup,
effective NetworkACL, or service profile is Pending; and an ExternalIP,
ExternalIPAttachment, or NATGateway cannot be created while its pool, target,
VirtualNetwork, or ExternalIP is not in the state required by the shared
design. The API returns `FailedPrecondition` with the dependent field,
blocker identity, observed state, required state, and remediation. It writes
no dependent object, reserves no capacity, creates no CR, and dispatches no
backend job for a rejected request.

This rule does not prohibit a resource from becoming Pending while its own
manager provisions it after successful admission. The sole dependency
exception is OSAC-owned automatic external access: after a Ready pool and
capacity are validated, the workload transaction may create its owned
ExternalIP and ExternalIPAttachment in Pending state. No tenant-created
resource and no default NATGateway may use this exception; the default NAT
gateway waits for its auto-created ExternalIP to become Allocated.

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

### Historical Gaps Addressed by This Proposal

The following gaps describe the pre-unified-networking baseline. They are kept
to explain the motivation for this proposal; they are not current limitations
of the contract defined below.

#### Gap #1: CaaS and BMaaS had no networking API — resolved

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
and other resources. Both service types previously built ad-hoc networking
outside the API. The current contract gives Cluster and BaremetalInstance
resource-specific network attachment fields and applies the shared
VirtualNetwork, Subnet, SecurityGroup, NetworkACL, readiness, cardinality, and
immutability rules.

#### Gap #2: Tenants must choose networking backends — resolved

The provider's infrastructure determines the backend. The single deployment
NetworkClass is resolved by the platform, and tenants provide only the
tenant-owned network fields such as the VirtualNetwork CIDR. No tenant-facing
NetworkClass selection or implementation-backend choice is exposed.

#### Gap #3: No complete manager registration contract — resolved

Manager registration identifies a complete implementation target. Every
configured manager must implement the complete OSAC networking lifecycle,
including all canonical resources, both policy types, and VMaaS, BMaaS, and
CaaS. If both managers are configured, the operator reconciles one internal
target per manager for every operation. A backend operation that is still
under development may use a successful no-op AAP role; it is not represented
as an unsupported resource, scope, or service.

#### Gap #4: ExternalIPAttachment only supported VMs — resolved

Before this proposal, ExternalIPAttachment supported only VMs as a target.
CaaS needs ExternalIPs for cluster API server and ingress endpoints (two
separate IPs for two different purposes on the same Cluster). BMaaS needs
ExternalIPs for bare-metal servers. The unified ExternalIPAttachment target is
now a typed oneof supporting ComputeInstance, Cluster, and BaremetalInstance.
Cluster additionally requires an API or ingress endpoint.

#### Gap #5: Ingress and egress were not clearly separated — resolved

The current contract separates the two operations: ExternalIPAttachment is
inbound DNAT to one Ready workload endpoint, while NATGateway is outbound SNAT
for one VirtualNetwork. An ExternalIP is single-consumer, so an address cannot
be used by both resources and there is no precedence ambiguity.

#### Gap #6: VMs were not part of the fabric — resolved for the supported path

VMs running on OpenShift use OVN (User Defined Networks) for isolation. Their
IP addresses exist only within the OVN overlay and are not visible on the
physical fabric. When a fabric manager needs to perform DNAT to route
external traffic to a VM, it cannot reach the VM's OVN-internal IP directly.
A K8s manager (e.g., CUDN with LocalNet) is needed to bridge VMs to the
fabric. The supported current path resolves the provider implementation
strategy from the deployment managers. A VM attachment is accepted only when
the deployment's complete manager contract and VM placement prerequisites are
present; the tenant does not select a bridge or backend. Future east-west
FabricDomain behavior remains outside this shared north-south contract.

#### Gap #7: VMs and bare metal could not share a network — resolved for the supported path

VMs use OVN for isolation — a software-defined overlay on the OpenShift
cluster. Bare-metal servers use physical VLANs configured on switches in the
fabric. These are fundamentally different L2 domains. A K8s manager using
LocalNet mode can bridge OVN to the physical fabric, making VMs first-class
participants alongside BM servers. The current shared VirtualNetwork/Subnet
contract allows the supported VM and bare-metal attachment paths to use the
same network. The resolved manager combination owns the complete workload
lifecycle.
Manager-specific topology limits remain authoritative; east-west FabricDomain
enhancements are not implied by this shared contract.

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
- Enable tenants to manage networking resources (VirtualNetworks, Subnets, SecurityGroups, NetworkACLs, ExternalIPs) without choosing implementation backends
- Support pluggable networking backends that can be added without API changes
- Enable VMs, clusters, and bare-metal servers to coexist in the same
  VirtualNetwork where service-specific placement prerequisites are Ready
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
- As a tenant, I want to define stateful, allow-only SecurityGroups and attach
  them to my workloads
- As a tenant, I want to allocate ExternalIPs and attach them to my VMs,
  clusters, or bare-metal servers for inbound access
- As a tenant, I want to create a NATGateway for outbound access from my
  VirtualNetwork through the deployment's configured networking managers

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
manager combination implements each workload's placement contract. The tenant
does not declare the resource type when creating a VirtualNetwork or Subnet;
service-specific validation rejects invalid placement before workload
persistence. Multiple deployment locations are supported — VMs on different
infrastructure share the same subnet.

#### FR-3: Uniform networking across all service types (R3)

All three service types (VMaaS, CaaS, BMaaS) must consume the networking API
using the same resource model: VirtualNetwork, Subnet, SecurityGroup,
NetworkACL, ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway.

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

At least one of Fabric Manager or K8s Manager must be configured. Every
configured manager is a complete implementation target for VirtualNetwork,
Subnet, SecurityGroup, NetworkACL, ExternalIPPool, ExternalIP,
ExternalIPAttachment, NATGateway, and all three workload services. A tenant
resource Create is admitted against the complete contract and dispatched to
every configured manager. A backend operation that is still under development
may use a successful no-op AAP role; this does not create a tenant-visible
unsupported path. Native Kubernetes NetworkPolicy alone is not sufficient for
the OSAC policy contracts.

#### FR-6a: Stateful SecurityGroup policy

SecurityGroups are VirtualNetwork-scoped and selected by the workload's
network attachment. A SecurityGroup contains one or more allow-only rules for
tenant-created groups; the auto-created tenant default group may contain zero
rules and therefore means default deny. Rules specify direction, protocol,
optional single port, and exactly one IPv4 source or destination CIDR. They do
not contain an action field, and deny rules, priorities, and update operations
are rejected. SecurityGroups are stateful, so return traffic for an allowed
flow is allowed automatically. Multiple attached groups aggregate their allow
rules; a flow allowed by any attached group passes the SecurityGroup layer.

Every selected manager receives the SecurityGroup operation. A tenant default
SecurityGroup is always created for the tenant default VirtualNetwork.
A workload always has the SecurityGroup layer: an omitted attachment resolves
the tenant default group, and an explicitly selected group must be Ready. The
effective workload decision is the conjunction of the SecurityGroup result
and the Subnet's NetworkACL result.

The tenant default SecurityGroup belongs only to the tenant default
VirtualNetwork. If a workload selects a Subnet in another VirtualNetwork and
does not provide a compatible SecurityGroup, the request is rejected rather
than receiving the default-VN group. The selected Subnet must have a Ready
effective ACL before workload placement; a Subnet without one is not
workload-ready. The deployment permit baseline is not a substitute for the
tenant default ACL.

#### FR-6b: Stateless NetworkACL policy

NetworkACLs are associated with Subnets rather than workload resources. A
NetworkACL may be associated with multiple Subnets, but a Subnet has at most
one effective ACL, including the system-created default ACL. Each packet is evaluated independently; the ACL does not
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
egress. This is an ordinary, visible NetworkACL policy and can be replaced
only through the documented default-resource workflow. It is distinct from
the provider-owned deployment baseline, which remains the least-specific
fallback. Every configured manager receives the default ACL operation.

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

- [ ] VirtualNetworks, Subnets, ExternalIPs, SecurityGroup rules, and
  NetworkACL rules accept and
  provision IPv4 CIDRs only; IPv6 and dual-stack requests are rejected
- [ ] Resources in different VirtualNetworks cannot communicate (full isolation)
- [ ] Resources in the same Subnet are in the same L2 broadcast domain
- [ ] Resources in different Subnets within the same VirtualNetwork can communicate via Layer 3 routing
- [ ] In every accepted NetworkClass, NetworkACLs control which traffic is permitted within
  these boundaries — enforced uniformly for all resource types
- [ ] SecurityGroups are stateful, VirtualNetwork-scoped, allow-only, and
  selected on workload attachments; unmatched traffic is denied and return
  traffic for an allowed flow is permitted automatically
- [ ] A tenant-created SecurityGroup contains at least one valid allow rule;
  the auto-created tenant default SecurityGroup may be empty and means deny
- [ ] SecurityGroup rules reject an action field, deny rules, invalid direction,
  protocol, port, CIDR, duplicate rule, or non-Ready/cross-tenant reference
- [ ] When both policy types apply, a flow must pass both the workload's
  SecurityGroup evaluation and the Subnet's NetworkACL evaluation
- [ ] A NetworkACL can be associated with multiple Subnets, while each Subnet has at most one effective ACL
- [ ] NetworkACL rules are stateless: response traffic is evaluated independently; a tenant-specific opposite-direction rule is required for a tenant-specific decision, otherwise the deployment baseline applies
- [ ] Each tenant receives a default NetworkACL with explicit deny-all ingress
  and allow-all egress rules, and every configured manager receives its
  lifecycle operation
- [ ] Every configured manager is a complete implementation target for all
  canonical networking resources and VMaaS, BMaaS, and CaaS; no resource,
  policy, scope, or service subset declaration is exposed
- [ ] A backend operation still under development may use a successful no-op
  AAP role, but the API does not expose an unsupported-resource or
  unsupported-service branch
- [ ] The provider-owned deployment baseline is the least-specific fallback and is hard-coded to permit all traffic; it is not tenant-configurable or serialized in tenant NetworkACLs
- [ ] Tenant-created NetworkACLs contain at least one explicit rule with a supported action, direction, protocol, and IPv4 CIDR
- [ ] Overlapping rules resolve by documented specificity, and equal-specificity contradictory rules are rejected
- [ ] Bare-metal servers in the same Subnet are in the same broadcast domain regardless of their physical location (rack, switch)
- [ ] VMs in the same Subnet are in the same broadcast domain regardless of which infrastructure they run on
- [ ] VMs are reachable at their subnet IP alongside bare-metal servers and cluster nodes
- [ ] The system provisions all necessary networking infrastructure for each subnet automatically
- [ ] Any resource type (ComputeInstance, Cluster, BaremetalInstance) can be
  placed on any subnet permitted by the shared placement contract; invalid
  placement is rejected before persistence
- [ ] VMs, BM servers, and cluster nodes receive uniform networking treatment —
  SecurityGroup, NetworkACL, and ExternalIP operations work identically
  regardless of resource type
- [ ] Workload network attachments contain a typed Subnet reference and optional typed SecurityGroup references, plus resource-specific interface fields where applicable; NetworkACL membership is resolved from the Subnet
- [ ] Each resource type has its own network attachment configuration appropriate to the resource (e.g., BMaaS uses one physical attachment, clusters use one shared subnet and one tenant-facing physical interface per node)
- [ ] ExternalIPAttachment supports all three service types as targets
- [ ] The tenant workflow for creating networking resources is identical regardless of service type
- [ ] NetworkClass manager combinations are resolved by the provider; tenants do not select a NetworkClass per VirtualNetwork
- [ ] If both configured managers are configured, one internal target is
  reconciled per manager for every resource and all targets must become READY;
  if only one is configured, that manager receives the operation
- [ ] Every create path enforces the shared dependency-ready matrix before
  persistence and rejects Pending, Failed, or Deleting dependencies with a
  field-specific `FailedPrecondition`; it never creates a dependent resource
  merely to wait for the dependency
- [ ] The only Pending dependency exception is the atomic OSAC-owned automatic
  ExternalIP plus ExternalIPAttachment flow; its pool is Ready first, and no
  tenant-created resource or default NATGateway uses the exception

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
- [ ] Provider configuration may register one Fabric Manager, one K8s Manager,
  or both. Each resource operation is dispatched to every configured manager;
  a Fabric Manager handles
  physical operations when selected, while a K8s Manager may implement the
  corresponding resource directly in a K8s-only deployment
- [ ] VM networking is integrated into the same networking layer as bare-metal servers
- [ ] Networking backends are registered through configuration deployed with the OSAC installation
- [ ] The system validates that every selected manager has the complete
  networking, resource, and workload contract; unfinished operations use the
  approved internal no-op path rather than exposing a partial API
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
