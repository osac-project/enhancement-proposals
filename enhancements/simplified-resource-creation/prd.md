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

## 3. User Stories

### Tenant Stories

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
- As a tenant, I want to create a Cluster with `--external-ip=auto` and
  have the system automatically provision ExternalIPs for both the API
  server and ingress endpoints before cluster provisioning begins
- As a tenant, I want to create a Cluster with `--nat-gateway=auto` and
  have the system automatically provision a NATGateway on the VirtualNetwork
  so that cluster nodes have outbound connectivity without manual setup

### Provider Stories

- As a provider, I want to configure a default CIDR range and default
  SecurityGroup rules, so that the system can auto-create default
  networking resources for tenants on first use

## 4. Requirements

### 4.1 Functional Requirements

#### Default Networking

- **FR-1:** At tenant onboarding, the system provisions a default
  VirtualNetwork, Subnet, and SecurityGroup for the tenant. The tenant
  transitions to READY only after all default networking resources are
  also READY. [User]
- **FR-2:** The provider configures default networking parameters (CIDR,
  SecurityGroup rules, CIDR mode) on the NetworkClass. When defaults are
  not configured, creating a resource without explicit `network_attachments`
  fails with a clear error. [User]
- **FR-3:** Two CIDR modes are supported: `shared_cidr` (default — all
  tenants receive the same CIDR, isolated at the fabric level) and
  `isolated_cidr` (each tenant gets a unique CIDR slice from the
  provider's supernet). [User]
- **FR-4:** Default resources are labeled `osac.openshift.io/default:
  "true"`, visible in list and detail views, and editable by the tenant
  (e.g., adding SecurityGroup rules). Default resources cannot be deleted
  while any resource depends on them. [User]
- **FR-5:** Creating custom VirtualNetworks does not affect default
  resources — both coexist. [User]

#### Optional Network Attachments

- **FR-6:** The `network_attachments` field on ComputeInstance, Cluster,
  and BaremetalInstance is optional. When omitted, the system populates it
  with the tenant's default Subnet and default SecurityGroup. The resolved
  attachments are stored in the resource spec so the resource is
  self-describing after creation. [User]
- **FR-7:** When a resource is created with explicit `network_attachments`,
  no defaults are applied. [User]

#### Auto ExternalIP

- **FR-8:** ComputeInstance and BaremetalInstance support an
  `external_ip_mode` field with values `NONE` (default) and `AUTO`. When
  `AUTO`, the system auto-selects the READY ExternalIPPool with the most
  available capacity, creates an ExternalIP, and creates an
  ExternalIPAttachment binding it to the resource. [User]
- **FR-9:** Cluster supports a `external_ip_mode` field with values
  `NONE` (default), `AUTO_API` (API server only), `AUTO_INGRESS` (ingress
  only), and `AUTO_ALL` (both). For `AUTO_ALL`, two ExternalIPs and two
  ExternalIPAttachments are created. [User]
- **FR-10:** For clusters, ExternalIPs are allocated before provisioning
  is dispatched and passed as template parameters, resolving the CaaS
  prerequisite ordering requirement. ExternalIPAttachments are created in
  Pending state and activate once VIPs are discovered. [User]
- **FR-11:** Auto-created ExternalIP and ExternalIPAttachment resources
  are labeled `osac.openshift.io/auto-provisioned: "true"` and have an
  owner-reference annotation pointing to the parent resource. When the
  parent is deleted, auto-created resources are garbage-collected. [User]

#### Auto NATGateway

- **FR-12:** All resource types (ComputeInstance, BaremetalInstance,
  Cluster) support a `nat_gateway_mode` field with values `NONE` (default)
  and `AUTO`. When `AUTO`, the system auto-selects an ExternalIP from the
  best available pool and creates a NATGateway on the resource's
  VirtualNetwork using that ExternalIP as the SNAT source. If a NATGateway
  already exists on the VN, it is reused. [User]

## 5. Acceptance Criteria

- [ ] A tenant can create a ComputeInstance with `--external-ip=auto` and
  no `network_attachments` — the VM is created on the default subnet with
  an auto-provisioned ExternalIP for inbound access
- [ ] A tenant can create a Cluster with `--external-ip=auto-all
  --nat-gateway=auto` and no `network_attachments` — the cluster is
  provisioned with ExternalIPs for API and ingress plus a NATGateway for
  outbound, all resolved automatically
- [ ] A tenant can create a BaremetalInstance with `--external-ip=auto`
  and no `network_attachments` — the server is placed on the default
  subnet with an auto-provisioned ExternalIP
- [ ] Default VN, Subnet, and SG exist and are READY before the tenant's
  first resource creation
- [ ] Default resources appear in list views with the
  `osac.openshift.io/default: "true"` label
- [ ] A tenant can modify default SecurityGroup rules (e.g., add ingress
  rules) and the changes take effect
- [ ] Deleting a resource with auto-provisioned ExternalIP causes the
  auto-created ExternalIP and ExternalIPAttachment to be
  garbage-collected
- [ ] Creating a resource with explicit `network_attachments` bypasses
  defaults entirely — no default resources are referenced
- [ ] When no ExternalIPPool has available capacity, resource creation
  with `external_ip_mode=AUTO` fails with a clear error
- [ ] A resource created without `network_attachments` shows the resolved
  default attachments in its spec when retrieved via Get

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP,
  ExternalIPAttachment, NATGateway) defined in the
  [Unified Networking EP](/enhancements/unified-networking)
- **OSAC-1712 (automatic pool selection)** — the auto ExternalIP pool
  selection reuses the same strategy: pick the READY pool with the most
  available capacity matching the IP family
- **Tenant onboarding flow** — default resource creation hooks into the
  existing Tenant controller lifecycle

## 7. Risks

### 7.1 Default CIDR supernet exhaustion (isolated_cidr mode)

- **Owner:** Provider
- **Mitigation:** Provider monitors allocation count; clear error on
  exhaustion; provider can widen supernet

### 7.2 ExternalIPPool exhaustion

- **Owner:** Provider
- **Mitigation:** Pool capacity visible in status; clear error directs
  tenant to explicit allocation from another pool

### 7.3 Default SecurityGroup too permissive

- **Owner:** Provider
- **Mitigation:** Provider configures default rules on NetworkClass;
  tenant can tighten rules after creation

### 7.4 Auto ExternalIP orphans on partial failure

- **Owner:** Platform
- **Mitigation:** Standard finalizer pattern; controller retries; if
  permanently failed, ExternalIP is GC'd with parent resource
