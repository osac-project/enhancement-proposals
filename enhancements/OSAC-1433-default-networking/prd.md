# Simplified Resource Creation — Default Networking and Auto ExternalIP

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-07-02 |

This PRD inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
default networking supports connected deployments only; air-gapped and
disconnected networking deployments are not supported.

It also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

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

All default networking resources use canonical IPv4 CIDRs. IPv6 and
dual-stack networking are not supported.

- A tenant can create a fully connected VM, bare-metal server, or cluster
  (inbound + outbound) with a single API call, without pre-creating any
  networking resources
- Tenants who need custom networking retain the full explicit workflow —
  simplified creation is additive, not a replacement
- Auto-provisioned networking resources are visible and follow the unified
  networking create/read/delete lifecycle; changes require replacement

### 2.2 Non-Goals

- Custom default configurations per tenant (all tenants in a deployment
  receive the same default CIDR and SecurityGroup rules)
- Auto-provisioning of VirtualNetworks or Subnets beyond the initial
  default (tenants create additional VNs manually)
- UI support for simplified creation (deferred — API and CLI only for now)
- Automatic migration of existing tenants to receive default networking
  resources (only new tenants get defaults at onboarding)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a resource (VM, cluster, or
  bare-metal server) without pre-creating networking resources, so that
  the system provides sensible defaults and I can get started quickly
- As a Tenant User, I want to create a resource with
  `--external-ip-attachment` and have it externally reachable in a single
  API call, without manually creating ExternalIP and ExternalIPAttachment
  resources
- As a Tenant User, I want auto-provisioned ExternalIPs to be
  automatically cleaned up when I delete the parent resource, so that I do
  not accumulate orphaned resources
- As a Tenant User, I want to create a Cluster with
  `--external-ip-attachment` and have the system automatically provision
  ExternalIPs for both the API server and ingress endpoints before cluster
  provisioning begins

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect my default networking resources and
  create replacement networking resources when I need different settings

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
  VirtualNetwork, IPv4 Subnet, SecurityGroup, and NATGateway for the tenant. The tenant
  transitions to READY only after all
  default networking resources are also READY. If default networking
  provisioning fails, the tenant remains in a non-READY state with a
  status condition describing the failure. The Cloud Provider Admin can
  inspect the failure and retry by deleting and re-creating the tenant.
  [User]
- **FR-2:** The Cloud Infrastructure Admin configures default networking
  parameters (IPv4 CIDRs and SecurityGroup rules) on the
  NetworkClass. Defaults are required — a NetworkClass without defaults
  is rejected at creation time. [User]
- **FR-3:** All tenants receive the same default IPv4 CIDR ranges as
  configured on the NetworkClass. Tenants are isolated at the
  network level — the unified networking API provides VirtualNetworks
  with any IP subnet, and the system enforces isolation regardless of
  overlapping CIDRs between tenants. [User]
- **FR-4:** Default resources are labeled as defaults and visible in list
  and detail views. They follow the unified networking create/read/delete
  contract; changes require delete and recreate, and deletion is blocked while
  any resource depends on them. [User]
- **FR-5:** Creating custom VirtualNetworks does not affect default
  resources — both coexist. [User]

#### Optional Network Attachments

- **FR-6:** The network attachment configuration on ComputeInstance,
  Cluster, and BaremetalInstance is optional and supports at most one tenant
  attachment. When omitted or empty, the system populates it with the tenant's
  default Subnet and default SecurityGroup. When a partial attachment is
  supplied, only missing fields are defaulted and supplied values are
  preserved. A missing or explicitly empty `security_groups` list is treated
  as missing; the default SecurityGroup applies only when the resolved Subnet
  belongs to the tenant's default VirtualNetwork, otherwise the caller must
  provide SecurityGroups from the resolved Subnet's VirtualNetwork. The resolved attachment is stored with the resource so the
  resource is self-describing after creation. VMaaS and BMaaS retain plural
  field names for API compatibility; CaaS retains its singular field. [User]
- **FR-7:** When a resource is created with an explicit complete attachment,
  no values are replaced by defaults. Missing fields in a single explicit
  attachment receive only their corresponding defaults. [User]

#### Auto ExternalIP

- **FR-8:** ComputeInstance and BaremetalInstance support
  `--external-ip-attachment`. When enabled, the system selects the
  available ExternalIPPool with the most capacity, allocates an
  ExternalIP, and creates an ExternalIPAttachment binding it to the
  resource. The system selects the pool with the most available capacity
  using IPv4. When multiple
  pools have equal capacity, selection is deterministic but unspecified.
  [User]
- **FR-9:** Cluster supports `--external-ip-attachment`. When enabled,
  the system allocates two ExternalIPs and creates two
  ExternalIPAttachments — one for the API server and one for ingress.
  [User]
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

#### Default NATGateway

- **FR-12:** At tenant onboarding, the system also provisions a
  NATGateway on the default VirtualNetwork with an automatically
  allocated ExternalIP. The NATGateway provides outbound connectivity
  for all resources on the default VirtualNetwork. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a ComputeInstance with
  `--external-ip-attachment` and no explicit network attachments — the VM
  is created on the default subnet with an auto-provisioned ExternalIP
  for inbound access
- [ ] A Tenant User can create a Cluster with `--external-ip-attachment`
  and no explicit network attachments — the cluster is provisioned with
  ExternalIPs for both API and ingress, all resolved automatically
- [ ] A Tenant User can create a BaremetalInstance with
  `--external-ip-attachment` and no explicit network attachments — the
  server is placed on the default subnet with an auto-provisioned
  ExternalIP
- [ ] Default VirtualNetwork, IPv4 Subnet, SecurityGroup, and NATGateway
  exist and are READY before the tenant's first resource creation
- [ ] Default resources appear in list views with a label identifying
  them as defaults
- [ ] Default networking resources expose only create/read/delete operations;
  a Tenant Admin can create replacement resources with customized settings once
  dependencies on the defaults have been removed
- [ ] Deleting a resource with auto-provisioned ExternalIP causes the
  auto-created ExternalIP and ExternalIPAttachment to be cleaned up
  automatically
- [ ] Creating a resource with explicit network attachments bypasses
  defaults entirely — no default resources are referenced
- [ ] When no ExternalIPPool has available capacity, the create API call
  returns an error and the resource is not persisted
- [ ] A resource created without explicit network attachments shows the
  resolved default attachments when retrieved via the API
- [ ] An IPv6 or dual-stack default CIDR is rejected when NetworkClass defaults
  are validated, and no default resource is persisted from the invalid input

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP,
  ExternalIPAttachment, NATGateway) defined in the
  [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **OSAC-1712 (automatic pool selection)** — the auto ExternalIP pool
  selection reuses the identical algorithm: pick the READY pool with the
  most available capacity from the IPv4 pool
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
- **Mitigation:** Defaults are required — a NetworkClass without defaults
  is rejected at creation time. This eliminates the scenario where tenant
  onboarding succeeds but resource creation fails due to missing defaults.
  osac-installer setup.sh includes NetworkClass default configuration in
  installation overlays

## 8. Open Questions

### ~~8.1 Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

### ~~8.2 E2E test coverage for simplified creation~~ — Resolved

Resolved: E2E tests for simplified creation are defined in each per-service design's test plan (VMaaS, CaaS, BMaaS). No separate test plan needed in the default networking EP.
