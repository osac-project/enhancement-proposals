# Simplified Resource Creation — Default Networking and Auto ExternalIP

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-07-02 |

## 1. Problem Statement

Creating a reachable resource in OSAC requires 6+ sequential API calls:
VirtualNetwork, Subnet, NetworkACL, the resource itself, ExternalIP,
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
- Auto-provisioned networking resources are visible and follow the same
  create/read/delete lifecycle as manually created ones; their network-owned
  fields are immutable after creation

The shared networking resources, IPv4-only scope, connected single-hub
deployment boundary, and operation contract are defined by the [Unified
Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md#network-operation-contract)
and [Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).

### 2.2 Non-Goals

- Custom default configurations per tenant (all tenants in a deployment
  receive the same default CIDR and default ACL policy)
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

- As a Tenant Admin, I want to inspect my default networking resources after
  they are auto-created and know that network-owned fields are fixed at
  creation time

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure the default CIDR
  range on the NetworkClass, so that the system can auto-create default
  networking resources for tenants at onboarding

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether a tenant's
  default networking resources were successfully provisioned, so I can
  troubleshoot onboarding failures

## 4. Requirements

### 4.1 Functional Requirements

#### Default Networking

- **FR-1:** At tenant onboarding, the system provisions a default
  VirtualNetwork, IPv4 Subnet, and a system-created NetworkACL associated with
  the default Subnet for the tenant, and provisions
  a default NATGateway only when the NetworkClass advertises NATGateway
  support. The tenant transitions to READY only after all supported default
  networking resources are also READY. If default networking
  provisioning fails, the tenant remains in a non-READY state with a
  status condition describing the failure. The Cloud Provider Admin can
  inspect the failure and retry by deleting and re-creating the tenant.
  [User]
- **FR-2:** The Cloud Infrastructure Admin supplies required default networking
  parameters (IPv4 VN and Subnet CIDRs) when creating the single deployment
  NetworkClass. A NetworkClass without `defaults` is rejected at creation
  time, and the NetworkClass network configuration is immutable thereafter.
  The default NetworkACL contains the explicit default ACL policy: deny all
  ingress and allow all egress. The provider-owned deployment baseline is
  separate, hard-coded to `permit` all traffic, and is not tenant-configurable.
  [User]
- **FR-3:** All tenants receive the same default IPv4 CIDR ranges as configured
  on the NetworkClass. Tenants are isolated at the
  network level — the unified networking API provides VirtualNetworks
  with any IP subnet, and the system enforces isolation regardless of
  overlapping CIDRs between tenants. [User]
- **FR-4:** Default resources are labeled as defaults and visible in list and
  detail views. Their network-owned fields are immutable after creation;
  update and patch requests are rejected. Default resources cannot be deleted
  while any resource depends on them. [User]
- **FR-5:** Creating custom VirtualNetworks does not affect default
  resources — both coexist. [User]

#### Optional Network Attachments

- **FR-6:** The network attachment configuration on ComputeInstance,
  Cluster, and BaremetalInstance is optional. When omitted or empty, the
  system populates the tenant's default Subnet only. The effective NetworkACL
  is inherited from the Subnet and is not copied into the workload attachment.
  For VMaaS, ComputeInstance retains its list-shaped field but accepts at most
  one attachment. For BMaaS, resolution produces exactly one tenant network
  attachment. [User]
- **FR-7:** When an attachment supplies a Subnet, that Subnet is preserved
  unchanged. NetworkACL associations are managed only through the NetworkACL
  resource, never through a workload attachment. [User]

#### Auto ExternalIP

- **FR-8:** ComputeInstance and BaremetalInstance support
  `--external-ip-attachment`. When enabled, the system selects the
  available IPv4 ExternalIPPool with the most capacity, reserves capacity,
  and creates a Pending ExternalIP and ExternalIPAttachment binding it to the
  resource. Fabric allocation, target IP discovery, DNAT programming, and
  the `Pending -> Allocated` / `Pending -> Ready` transitions are
  asynchronous. When multiple pools have equal capacity, selection is
  deterministic but unspecified. [User]
- **FR-9:** Cluster supports `--external-ip-attachment`. When enabled,
  the system reserves capacity and creates two Pending ExternalIPs and two
  Pending ExternalIPAttachments — one pair for the API server and one for
  ingress. Fabric allocation, endpoint discovery, and DNAT programming are
  asynchronous. [User]
- **FR-10:** For clusters, the Pending ExternalIP and ExternalIPAttachment
  records are created before provisioning begins. ExternalIPs transition to
  `Allocated` when the manager assigns addresses, and attachments transition
  to `Ready` only after the cluster endpoint addresses are available and
  inbound routing succeeds. [User]
- **FR-11:** Auto-created ExternalIP and ExternalIPAttachment resources
  are labeled with `osac.openshift.io/auto-created: "true"`. When the parent resource is deleted,
  the system deletes auto-created ExternalIPAttachments first, then
  ExternalIPs, before the parent resource is removed. If cleanup of
  auto-created resources fails permanently, the parent resource is still
  deleted — orphaned ExternalIPs remain and must be cleaned up manually
  by the Tenant Admin or Cloud Provider Admin. [User]

#### Default NATGateway

- **FR-12:** At tenant onboarding, the system also provisions a
  NATGateway on the default VirtualNetwork with an automatically allocated
  ExternalIP only when the NetworkClass advertises NATGateway support. The
  NATGateway provides outbound connectivity for all resources on the default
  VirtualNetwork. K8s-only OVN deployments reject NATGateway because of the
  current implementation limitation. [User]

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
- [ ] A BaremetalInstance created without explicit network attachments has
  exactly one resolved default network attachment
- [ ] Default VirtualNetwork, IPv4 Subnet, and the default NetworkACL associated
  with that Subnet exist and are READY before the tenant's first resource
  creation; NATGateway is also READY
  when the deployment advertises that capability
- [ ] Default resources appear in list views with a label identifying
  them as defaults
- [ ] Update and patch requests for default network resources and their
  network-owned fields are rejected; changes require delete and recreate
- [ ] Standard resource metadata and Catalog Item definitions and metadata
  remain governed by their existing designs
- [ ] Deleting a resource with auto-provisioned ExternalIP causes the
  auto-created ExternalIP and ExternalIPAttachment to be cleaned up
  automatically
- [ ] Creating a resource with complete explicit network attachments preserves
  all supplied fields; creating one with partial attachments defaults only the
  missing fields
- [ ] When no ExternalIPPool has available capacity, the create API call
  returns an error and the resource is not persisted
- [ ] A resource created without explicit network attachments shows the
  resolved default attachments when retrieved via the API
- [ ] Creating a BaremetalInstance with more than one explicit network
  attachment returns a single-NIC validation error
- [ ] Creating a ComputeInstance with more than one explicit network
  attachment returns a single-interface validation error

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, NetworkACL, ExternalIP,
  ExternalIPAttachment, NATGateway) defined in the
  [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **OSAC-1712 (automatic pool selection)** — the auto ExternalIP pool
  selection reuses the identical algorithm: pick the READY IPv4 pool with the
  most available capacity
- **Tenant onboarding flow** — default resource creation hooks into the
  existing Tenant controller lifecycle
- **osac-installer** — NetworkClass default configuration must be included
  in setup.sh and installation overlays

## 7. Risks

### 7.1 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs
  tenant to explicit allocation from another pool

### 7.2 Default NetworkACL policy is incorrect

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** The default NetworkACL has an explicit, visible policy:
  deny-all ingress and allow-all egress. It is associated with the default
  Subnet, and changing it requires replacing the default NetworkACL after
  dependencies are removed. Overlapping rules use specificity; contradictory
  equal-specificity rules are rejected. If no tenant rule matches, the
  provider-owned deployment baseline applies and currently permits all traffic;
  tenants cannot override that baseline.

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
