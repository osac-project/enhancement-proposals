# Simplified Resource Creation — Default Networking and Auto ExternalIP

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1029 |
| Date        | 2026-07-02 |

## 1. Problem Statement

Creating a reachable resource in OSAC requires 6+ sequential API calls:
VirtualNetwork, Subnet, SecurityGroup, the resource itself, ExternalIP,
and ExternalIPAttachment. Every tenant must understand the full networking
resource model before provisioning their first VM, cluster, or bare-metal
server. This friction slows onboarding, increases the chance of
misconfiguration, and makes OSAC harder to adopt compared to platforms
where a single create command produces a reachable instance.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a fully connected VM, bare-metal server, or cluster
  (inbound + outbound) with a single API call, without pre-creating any
  networking resources
- Tenants who need custom networking retain the full explicit workflow —
  simplified creation is additive, not a replacement
- Auto-provisioned networking resources are visible, editable, and follow
  the same lifecycle as manually created ones

### 2.2 Non-Goals

- Custom default configurations per tenant (all tenants in a deployment
  receive the same default CIDR and SecurityGroup rules)
- Auto-provisioning of VirtualNetworks or Subnets beyond the initial
  default (tenants create additional VNs manually)
- UI support for simplified creation (deferred — API and CLI only for now)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a resource (VM, cluster, or
  bare-metal server) without pre-creating networking resources, so that
  the system provides sensible defaults and I can get started quickly
- As a Tenant User, I want to create a resource with `--external-ip=auto`
  and have it externally reachable in a single API call, without manually
  creating ExternalIP and ExternalIPAttachment resources
- As a Tenant User, I want auto-provisioned ExternalIPs to be
  automatically cleaned up when I delete the parent resource, so that I do
  not accumulate orphaned resources
- As a Tenant User, I want to create a Cluster with
  `--external-ip=auto-all` and have the system automatically provision
  ExternalIPs for both the API server and ingress endpoints before cluster
  provisioning begins
- As a Tenant User, I want to create a Cluster with `--nat-gateway=auto`
  and have the system automatically provision a NATGateway on the
  VirtualNetwork so that cluster nodes have outbound connectivity without
  manual setup

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect and customize my default networking
  resources (e.g., modify SecurityGroup rules) after they are auto-created

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure a default CIDR
  range and default SecurityGroup rules on the NetworkClass, so that the
  system can auto-create default networking resources for tenants at
  onboarding

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether a tenant's
  default networking resources were successfully provisioned, so I can
  troubleshoot onboarding failures

## 4. Requirements

### 4.1 Functional Requirements

#### Default Networking

- **FR-1:** At tenant onboarding, the system provisions a default
  VirtualNetwork, Subnet, and SecurityGroup for the tenant. The tenant
  transitions to READY only after all default networking resources are
  also READY. If default networking provisioning fails, the tenant
  remains in a non-READY state with a status condition describing the
  failure. The Cloud Provider Admin can inspect the failure and retry
  by deleting and re-creating the tenant. [User]
- **FR-2:** The Cloud Infrastructure Admin configures default networking
  parameters (CIDR, SecurityGroup rules) on the NetworkClass. When
  defaults are not configured, creating a resource without explicit
  network attachments fails with a clear error. [User]
- **FR-3:** All tenants receive the same default CIDR range as configured
  on the NetworkClass. Tenants are isolated at the network level — the
  unified networking API provides VirtualNetworks with any IP subnet, and
  the system enforces isolation regardless of overlapping CIDRs between
  tenants. [User]
- **FR-4:** Default resources are labeled as defaults, visible in list
  and detail views, and editable by the Tenant Admin (e.g., adding
  SecurityGroup rules). Default resources cannot be deleted while any
  resource depends on them. [User]
- **FR-5:** Creating custom VirtualNetworks does not affect default
  resources — both coexist. [User]

#### Optional Network Attachments

- **FR-6:** The network attachment configuration on ComputeInstance,
  Cluster, and BaremetalInstance is optional. When omitted, the system
  populates it with the tenant's default Subnet and default SecurityGroup.
  The resolved attachments are stored with the resource so the resource is
  self-describing after creation. [User]
- **FR-7:** When a resource is created with explicit network attachments,
  no defaults are applied. [User]

#### Auto ExternalIP

- **FR-8:** ComputeInstance and BaremetalInstance support an automatic
  external IP mode. When enabled, the system selects the available
  ExternalIPPool with the most capacity, allocates an ExternalIP, and
  creates an ExternalIPAttachment binding it to the resource. The system
  selects the pool with the most available capacity matching the requested
  IP family (defaulting to IPv4). When multiple pools have equal capacity,
  selection is deterministic but unspecified. [User]
- **FR-9:** Cluster supports automatic external IP allocation with
  options for API server only, ingress only, both, or neither. When both
  are enabled, two ExternalIPs and two ExternalIPAttachments are created.
  The CLI supports `--external-ip=auto-all` (both),
  `--external-ip=auto-api` (API server only), and
  `--external-ip=auto-ingress` (ingress only). [User]
- **FR-10:** For clusters, ExternalIPs are allocated before provisioning
  begins, resolving the ordering requirement that cluster nodes need
  external access during setup. ExternalIPAttachments are created in an
  inactive state and activate once the cluster's endpoint addresses are
  available. [User]
- **FR-11:** Auto-created ExternalIP and ExternalIPAttachment resources
  are labeled as auto-provisioned. When the parent resource is deleted,
  the system deletes auto-created ExternalIPAttachments first, then
  ExternalIPs, before the parent resource is removed. If cleanup of
  auto-created resources fails permanently, the parent resource is still
  deleted — orphaned ExternalIPs remain and must be cleaned up manually
  by the Tenant Admin or Cloud Provider Admin. [User]

#### Auto NATGateway

- **FR-12:** All resource types (ComputeInstance, BaremetalInstance,
  Cluster) support an automatic NAT gateway mode. When enabled, the
  system selects an ExternalIP from the best available pool and creates a
  NATGateway on the resource's VirtualNetwork using that ExternalIP as
  the outbound source address. If a NATGateway already exists on the
  VirtualNetwork, it is reused regardless of which ExternalIP it uses,
  its current state, or whether it was manually or auto-created. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a ComputeInstance with `--external-ip=auto`
  and no explicit network attachments — the VM is created on the default
  subnet with an auto-provisioned ExternalIP for inbound access
- [ ] A Tenant User can create a Cluster with `--external-ip=auto-all
  --nat-gateway=auto` and no explicit network attachments — the cluster
  is provisioned with ExternalIPs for API and ingress plus a NATGateway
  for outbound, all resolved automatically
- [ ] A Tenant User can create a BaremetalInstance with
  `--external-ip=auto` and no explicit network attachments — the server
  is placed on the default subnet with an auto-provisioned ExternalIP
- [ ] Default VirtualNetwork, Subnet, and SecurityGroup exist and are
  READY before the tenant's first resource creation
- [ ] Default resources appear in list views with a label identifying
  them as defaults
- [ ] A Tenant Admin can modify default SecurityGroup rules (e.g., add
  ingress rules) and the changes take effect
- [ ] Deleting a resource with auto-provisioned ExternalIP causes the
  auto-created ExternalIP and ExternalIPAttachment to be cleaned up
  automatically
- [ ] Creating a resource with explicit network attachments bypasses
  defaults entirely — no default resources are referenced
- [ ] When no ExternalIPPool has available capacity, the create API call
  returns an error and the resource is not persisted
- [ ] A resource created without explicit network attachments shows the
  resolved default attachments when retrieved via the API

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP,
  ExternalIPAttachment, NATGateway) defined in the
  [Unified Networking EP](/enhancements/unified-networking)
- **OSAC-1712 (automatic pool selection)** — the auto ExternalIP pool
  selection reuses the identical algorithm: pick the READY pool with the
  most available capacity matching the IP family
- **Tenant onboarding flow** — default resource creation hooks into the
  existing Tenant controller lifecycle
- **osac-installer** — NetworkClass default configuration must be included
  in setup.sh and installation overlays

## 7. Risks

### 7.1 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs
  tenant to explicit allocation from another pool

### 7.2 Default SecurityGroup too permissive

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Cloud Infrastructure Admin configures default rules on
  NetworkClass; Tenant Admin can tighten rules after creation

### 7.3 Auto ExternalIP orphans on partial failure

- **Owner:** Platform
- **Mitigation:** Parent resource finalizer handles cleanup; controller
  retries on transient failures. If cleanup permanently fails, the
  finalizer is removed and the parent is deleted — orphaned ExternalIPs
  must be cleaned up manually

### 7.4 Deployment misconfiguration

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** If NetworkClass defaults are not configured, tenant
  onboarding still succeeds but resource creation without explicit
  `network_attachments` fails with a clear error directing the tenant to
  use explicit networking or contact the admin. This is a deployment
  issue, not a runtime failure

## 8. Open Questions

### 8.1 Should capacity exhaustion return an API error or create a Failed resource?

- **Owner:** API design team
- **Impact:** Affects FR-8 and acceptance criteria. Returning an error
  (resource not persisted) is simpler but gives no audit trail. Creating
  a Failed resource provides visibility but adds cleanup burden.

### 8.2 E2E test coverage for simplified creation

- **Owner:** QE / osac-test-infra
- **Impact:** Which user journeys (1-call VM, 1-call cluster, explicit
  bypass) must be covered by E2E tests at milestone boundary? Deferred
  to design phase.
