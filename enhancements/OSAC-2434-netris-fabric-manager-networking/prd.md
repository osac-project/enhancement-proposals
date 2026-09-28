# Fabric Manager — Netris

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | [OSAC-2434](https://redhat.atlassian.net/browse/OSAC-2434) |
| Date        | 2026-09-28 |

> This PRD covers the **Netris fabric manager** — the production networking
> backend for OSAC that manages physical network infrastructure through the
> Netris network controller. It builds on the
> [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md),
> which defines the shared networking model, resources, API, and connected-only
> deployment support boundary. This document defines the requirements for
> delivering that model on environments that use Netris-managed switches and
> the Netris controller for fabric automation.

This PRD also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported.

## 1. Problem Statement

OSAC's networking API requires a fabric manager to translate tenant networking
resources (VirtualNetworks, Subnets, ExternalIPs, NATGateways) into physical
network configuration. The Netris fabric manager is the first and currently
only production-ready backend that fulfills this role, yet it has no formal
product requirements document. Its behavior is inferred from scattered code,
Ansible roles, and feature-level docs, making it difficult to reason about
supported operations, enforce boundaries, and prevent tenants or operators
from triggering unsupported or destructive actions. Without a formal PRD, the
team cannot validate completeness, write acceptance tests against a contract,
or onboard new fabric managers (such as the agentless VLAN backend) with a
clear parity baseline.

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cloud Infrastructure Admin can deploy OSAC with API-driven tenant
  networking on Netris-managed infrastructure by selecting the Netris fabric
  manager as the networking backend.
- Tenants can create and manage VirtualNetworks, Subnets, ExternalIPs,
  ExternalIPAttachments, NATGateways, and SecurityGroups through the OSAC
  networking API, with the Netris backend translating each resource into the
  corresponding Netris controller configuration.
- The system prevents unsupported or destructive operations — such as mutating
  immutable fields, deleting resources with active dependents, or requesting
  capabilities the backend does not support — with clear, user-visible error
  messages.
- Backend networking failures are visible on the affected resource's status
  with actionable, sanitized diagnostics traceable to the failed operation
  without exposing raw response bodies or credentials.

### 2.2 Non-Goals

- No changes to the OSAC networking API or its resource model — the API is
  inherited from the unified networking work (OSAC-1433) and consumed as-is.
- Does not define the networking model itself — VirtualNetwork, Subnet,
  SecurityGroup, ExternalIP semantics are defined in the unified networking PRD.
- IPv6 and dual-stack networking are not supported; the backend supports IPv4.
- SecurityGroup policy enforcement semantics (allow/deny rule evaluation, rule
  ordering, stateful tracking) are defined separately and not part of this PRD.
- UI for backend selection or Netris-specific configuration is out of scope;
  backend selection is a provider configuration concern.
- DNS record creation is not part of this backend — DNS is handled by the
  separate DNS API (OSAC-1050).
- Multiple Netris controllers or split-controller topologies are not
  supported. A single Netris controller may manage multiple sites, mapped from
  OSAC regions.

## 3. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register the Netris fabric manager by
  deploying its metadata-only manager ConfigMap, configuring site settings
  through the installer, and supplying Netris credentials through a
  provider-owned Secret, so that OSAC can use Netris without exposing
  credentials in the registration ConfigMap.
- As a Cloud Provider Admin, I want the system to reject a fabric manager
  registration with duplicate names or invalid capability declarations, so
  that misconfiguration is caught at registration time rather than at
  provisioning time.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select the Netris fabric manager
  as the backend for a NetworkClass by referencing its registered name, so that
  all networking resources using that NetworkClass are provisioned through
  Netris.
- As a Cloud Infrastructure Admin, I want to define provider-owned
  NAT ExternalIPPools backed by Netris IPAM space, so that tenants can allocate
  ExternalIPs for inbound DNAT and outbound NATGateway use.
- As a Cloud Infrastructure Admin, I want to see Netris controller errors
  surfaced on the affected networking resource's status, so that I can diagnose
  fabric problems without accessing the Netris controller directly.
- As a Cloud Infrastructure Admin, I want the system to prevent deletion of a
  VirtualNetwork that still has child Subnets, SecurityGroups, or NATGateways,
  so that dependent resources are not orphaned.

### Tenant Admin

- As a Tenant Admin, I want to create a VirtualNetwork that maps to a Netris
  VPC with isolated routing, so that my tenant's network traffic is isolated
  from other tenants.
- As a Tenant Admin, I want to create Subnets within a VirtualNetwork that map
  to Netris VNets with VXLAN VNI assignments, so that I can segment my
  network into broadcast domains.
- As a Tenant Admin, I want to create a NATGateway that configures Netris SNAT
  rules, so that my tenant's workloads can reach external services (including
  storage systems outside the fabric gateway) with a stable source IP.
- As a Tenant Admin, I want to allocate ExternalIPs from a provider-defined
  pool and attach them to workloads, so that my services are reachable from
  outside the VirtualNetwork through Netris DNAT rules.
- As a Tenant Admin, I want the system to reject attempts to mutate immutable
  fields (NetworkClass, region, CIDRs) on existing resources, so that I
  receive a clear error instead of entering an inconsistent state.
- As a Tenant Admin, I want to create SecurityGroups that map to Netris ACL
  rules, so that I can define access policies for my network resources.

### Tenant User

- As a Tenant User, I want a bare-metal server, cluster node, or VM attached
  to a Subnet to automatically receive an IP address from the Netris IPAM,
  so that I do not configure addressing manually.
- As a Tenant User, I want my workloads on different Subnets within the same
  VirtualNetwork to be able to communicate through the VirtualNetwork routing
  path, so that I can segment my network without losing internal connectivity.

## 4. Requirements

### 4.1 Functional Requirements

#### Backend Registration and Selection

- **FR-1:** The Netris fabric manager must be registered as a ConfigMap with
  the label `osac.openshift.io/network-fabric-manager: "true"`, containing
  its name, description, and declared capabilities (ipv4, ipv6, dualStack,
  dpuSupport).
- **FR-2:** The system must reject registration of a fabric manager with a
  name that duplicates an existing registered manager.
- **FR-3:** A Cloud Infrastructure Admin can select the Netris fabric manager
  as the backend for a NetworkClass. Backend selection is not visible to
  tenants and requires no networking-API changes.

#### Resource Provisioning

- **FR-4:** When a tenant creates a VirtualNetwork referencing a
  Netris-backed NetworkClass, the backend must create a corresponding Netris
  VPC (VRF) with isolated routing.
- **FR-5:** When a tenant creates a Subnet within a VirtualNetwork, the
  backend must create a corresponding Netris VNet with a VXLAN VNI and the
  specified CIDR range.
- **FR-6:** When a tenant creates a NATGateway, the backend must configure
  Netris SNAT rules so that outbound traffic from the associated VirtualNetwork
  egresses with the NATGateway's external IP as its source address.
- **FR-7:** When a tenant allocates an ExternalIP and creates an
  ExternalIPAttachment, the backend must configure a Netris DNAT rule to route
  inbound traffic to the target resource. A tenant workload target must resolve
  to its tenant VPC; the management VPC may be used only for an explicitly
  supported cluster-endpoint attachment, never as a fallback for a failed
  tenant-VPC lookup.
- **FR-8:** A Cloud Infrastructure Admin creates each ExternalIPPool and
  defines its CIDR. The current API supports exactly one CIDR per pool. The
  backend must create or resolve the corresponding provider-owned Netris IPAM
  allocation; each allocated ExternalIP is reserved as a /32 subnet with
  `purpose=nat`. Tenants may allocate ExternalIPs from the pool but may not
  create or change it.
- **FR-9:** When a tenant creates a SecurityGroup, the backend must translate
  the rules into Netris ACL configurations on the corresponding VPC. The
  parent VPC and applicable Subnet CIDRs must resolve before ACL creation;
  missing values must fail closed and must not become a default VPC or a
  wildcard CIDR.

#### Automatic IP Assignment

- **FR-10:** A bare-metal server, cluster node, or VM attached to a
  Netris-backed Subnet must automatically receive an IP address from the
  Subnet's CIDR range, allocated through Netris IPAM. The assigned address
  must be visible on the resource's status.

#### Immutability and Boundary Enforcement

- **FR-11:** The system must reject mutations to immutable fields on
  networking resources: NetworkClass on VirtualNetwork, region on
  VirtualNetwork, and CIDRs on Subnet and ExternalIPPool. Rejection must
  occur at admission time with a clear error message.
- **FR-12:** The system must prevent deletion of a VirtualNetwork that has
  active child Subnets, SecurityGroups, or NATGateways. The status must
  indicate which dependents block deletion.
- **FR-13:** The system must prevent deletion of a Subnet that has active
  child ComputeInstances or BareMetalInstances attached to it.
- **FR-14:** The system must prevent deletion of an ExternalIPPool that has
  active child ExternalIPs allocated from it.

#### Lifecycle Cleanup

- **FR-15:** When a networking resource is deleted (and deletion is not
  blocked by FR-12, FR-13, or FR-14), the backend must remove the
  corresponding Netris configuration (VPC, VNet, SNAT rule, DNAT rule, ACL) and
  release any IPAM allocations, without affecting other resources.
- **FR-16:** Teardown must respect dependency order: an ExternalIPAttachment's
  DNAT rule is removed before its ExternalIP is released back to the
  pool.

#### Failure Visibility

- **FR-17:** When a Netris controller API call fails during provisioning or
  teardown, the failure must be reflected on the affected networking
  resource's status condition with an actionable, sanitized diagnostic, such
  as the failed operation and Netris error code or request ID. Credentials,
  authorization data, tenant or network identifiers, and unfiltered response
  bodies must not be exposed.
- **FR-18:** When the Netris controller is unreachable, the affected resources
  must show a Failed or Degraded condition while retries use bounded
  exponential backoff; they must not remain indefinitely indistinguishable
  from successful or in-progress resources.

#### Capability Declaration

- **FR-19:** The Netris fabric manager must declare its supported capabilities
  in its registration ConfigMap. The NetworkClass Capabilities Controller
  must compute the effective capabilities of each NetworkClass as the
  intersection of its fabric manager and K8s manager capabilities, and
  surface them to the fulfillment service.
- **FR-20:** A VirtualNetwork with an explicitly configured region that has no
  Netris site mapping must fail visibly before any Netris resources are
  created. The default site may be used only when the region is omitted. A
  Subnet must use the site resolved for its parent VirtualNetwork.
- **FR-21:** A NATGateway must apply only to its referenced VirtualNetwork. If
  that VirtualNetwork or its Netris VPC cannot be resolved, the NATGateway
  must fail visibly without creating a rule in the management VPC.

#### Workload Networking Operations

- **FR-22:** When OSAC attaches or detaches a workload network port, the
  selected fabric manager must implement the mandatory `move_network_attachment`
  operation to move the port between its configured provisioning segment and
  tenant Subnet. The K8s manager does not perform this physical-port operation.
  Both attach and detach must be safe to retry.
- **FR-23:** When OSAC requests DHCP lease discovery, the selected manager must
  implement the manager-neutral `query_dhcp_lease` operation and return the
  lease address for resource status. Netris resolves the lease from IPAM host
  entries by port MAC address; server-name lookup is used only where the
  service contract permits it.

### 4.2 Non-Functional Requirements

- **NFR-1:** The Netris backend supports IPv4 networking. IPv6 and dual-stack
  are not supported.
- **NFR-2:** Netris controller credentials (URL, username, password) must be
  stored in Kubernetes Secrets and never logged or exposed in resource status.
- **NFR-3:** Different VirtualNetworks must have no direct connectivity on the
  internal fabric — a workload in one VirtualNetwork cannot reach another
  VirtualNetwork's private subnet addresses, even when their address ranges
  overlap. Cross-VN reachability is only possible via ExternalIPs over the
  external path.
- **NFR-4:** Provisioning must reconcile Netris to the desired state
  idempotently. Repeating the same request must not create duplicate VPCs,
  VNets, NAT rules, or ACLs; an update request must update existing mutable
  resources to match the new spec without leaving stale configuration. A
  successful hash for an unchanged spec must not suppress recovery from
  incomplete provisioning or detected missing Netris resources. Deleting a
  backend resource that is already absent must succeed as an idempotent no-op.
- **NFR-5:** Concurrent ExternalIP allocations from the same provider pool
  must receive distinct addresses. Retrying allocation for the same ExternalIP
  must return its existing reservation rather than allocate a second address.

## 5. Acceptance Criteria

- [ ] The Netris fabric manager is registered via a labeled ConfigMap with
  name, description, and capabilities; duplicate names are rejected.
- [ ] A Cloud Infrastructure Admin selects the Netris backend for a
  NetworkClass; tenants creating VirtualNetworks on that NetworkClass get
  Netris-backed networking without seeing the backend choice.
- [ ] A tenant creates a VirtualNetwork and the backend creates a Netris VPC
  with isolated routing; the resource reaches a ready state.
- [ ] A tenant creates a Subnet and the backend creates a Netris VNet with a
  VXLAN VNI; the resource reaches a ready state.
- [ ] A VirtualNetwork with an explicitly unmapped region fails with a clear
  status and creates no Netris resources at a default site; when region is
  omitted, the configured default site is used. Its Subnets use the same site.
- [ ] A bare-metal server attached to a Netris-backed Subnet receives an IP
  from the Subnet's CIDR via Netris IPAM, visible in its status.
- [ ] Attaching a workload port moves it from the provisioning segment to the
  tenant Subnet; detaching moves it back, and retrying either operation does
  not move it to an incorrect segment.
- [ ] Querying a workload's DHCP lease by port MAC returns the matching Netris
  IPAM host-entry address for resource status.
- [ ] A tenant creates a NATGateway; outbound traffic from the associated
  VirtualNetwork egresses with the NATGateway's external IP as the source
  address.
- [ ] A NATGateway whose tenant VirtualNetwork cannot be resolved fails
  visibly and creates no NAT rule in the management VPC.
- [ ] A provider defines a NAT ExternalIPPool with its single supported CIDR;
  a tenant can allocate an ExternalIP whose Netris /32 reservation has
  `purpose=nat`.
- [ ] Concurrent ExternalIP allocations from one pool receive distinct
  addresses, and retrying the same ExternalIP returns its original address.
- [ ] A tenant attaches an ExternalIP and the backend creates a Netris DNAT
  rule; inbound traffic reaches the target workload.
- [ ] A tenant-targeted DNAT attachment whose VPC cannot be resolved fails
  without creating the rule in the management VPC; an explicitly supported
  cluster-endpoint attachment may use the management VPC.
- [ ] A tenant creates a SecurityGroup and the backend translates its rules
  into Netris ACLs.
- [ ] Mutating immutable fields (NetworkClass, region, CIDRs) is rejected at
  admission time with a clear error message.
- [ ] Deleting a VirtualNetwork with active children is blocked; the status
  indicates which dependents prevent deletion.
- [ ] Deleting a Subnet with attached workloads is blocked.
- [ ] Deleting an ExternalIPPool with active ExternalIPs is blocked.
- [ ] When deletion is allowed, the backend removes the Netris configuration
  and releases IPAM allocations without affecting other resources.
- [ ] A Netris controller API failure surfaces on the affected resource's
  status with an actionable diagnostic that does not expose credentials or
  tenant or network identifiers, or unfiltered response bodies.
- [ ] Netris controller unreachability transitions affected resources to
  `Failed` or `Degraded` status and retries with bounded exponential backoff.
- [ ] Re-reconciling an already-provisioned resource does not create duplicate
  Netris objects.
- [ ] Updating mutable SecurityGroup rules reconciles the Netris ACL set to the
  new desired rules, removes obsolete rules, and creates no duplicates on retry.
- [ ] A SecurityGroup with an unresolved parent VPC or Subnet CIDR fails
  without creating a default-VPC or wildcard-CIDR permit ACL.
- [ ] Deleting a Netris backend resource that is already absent succeeds as a
  no-op.
- [ ] NetworkClass capabilities are computed as the intersection of fabric and
  K8s manager capabilities and surfaced to the fulfillment service.

## 6. Assumptions

- The OSAC networking API and resource model are complete and stable, inherited
  from the unified networking work (OSAC-1433); this PRD documents the
  backend, not the API.
- A single Netris controller manages the deployment and may expose multiple
  sites. Each configured OSAC region maps to one of those sites; multiple
  controllers and split-controller topologies are unsupported.
- The Netris controller API is the sole source of truth for fabric state. The
  backend does not maintain a separate state store for Netris objects.
- The Netris controller is preconfigured with the required site, tenant, and
  parent IPAM capacity. Cloud Infrastructure Admins define NAT ExternalIPPools
  in OSAC; the Netris backend creates the corresponding allocation and
  per-ExternalIP /32 reservations.
- VAST and other storage systems outside the fabric gateway are reachable via
  NATGateway SNAT — the backend does not provide a separate storage networking
  path.

## 7. Dependencies

- **Unified Networking EP (OSAC-1433)** — defines the networking model and API
  this backend implements
  ([Unified Networking EP](/enhancements/OSAC-1433-unified-networking)).
- **Netris Controller** — external dependency; must be deployed and configured
  with appropriate IPAM pools, site/tenant configuration, and API access
  before the backend can provision resources.
- **AAP (Ansible Automation Platform)** — the backend dispatches provisioning
  jobs to AAP, which executes Ansible roles that call the Netris controller
  API. AAP must be deployed and operational.
- **DNS API (OSAC-1050)** — DNS records for clusters are created outside this
  backend, in the service flow and the DNS API.
- **Agentless VLAN Fabric Manager (OSAC-3664)** — the second fabric manager
  backend; this PRD establishes the parity baseline that the agentless VLAN
  backend targets.

## 8. Risks

### 8.1 Netris controller availability

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** The backend must surface controller unreachability as a
  `Failed` or `Degraded` status on affected resources and retry with bounded
  exponential backoff. Recovery is automatic when the controller becomes
  reachable again through normal reconciliation.

### 8.2 Netris IPAM exhaustion

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** When Netris IPAM cannot allocate an IP (pool exhausted), the
  failure must be surfaced on the resource's status. The Cloud Infrastructure
  Admin must provision additional IPAM capacity in the Netris controller.

### 8.3 Drift between OSAC state and Netris state

- **Owner:** Connectivity & Fabric team
- **Mitigation:** The backend must be idempotent and converge on the desired
  state through reconciliation. Manual changes in the Netris controller that
  conflict with OSAC-managed resources may cause reconciliation failures,
  which are surfaced on the resource's status.

### 8.4 Netris API breaking changes

- **Owner:** Connectivity & Fabric team
- **Mitigation:** Pin the supported Netris controller version range. Validate
  backend compatibility when upgrading the Netris controller.
