# Simplified Resource Creation — Default Networking and Auto ExternalIP

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-10-11 |

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

Default networking supports IPv4. IPv6 and dual-stack networking are not
available.

- With provider networking enabled, a tenant can create an integrated workload
  with inbound and outbound connectivity in a single API call, without
  pre-creating networking resources
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
  API call when provider networking is enabled, without manually creating
  ExternalIP and ExternalIPAttachment resources
- As a Tenant User, I want auto-provisioned ExternalIPs to be
  automatically cleaned up when I delete the parent resource, so that I do
  not accumulate orphaned resources
- As a Tenant User, I want a workload with multiple externally reachable
  endpoints to receive a distinct address and route for each endpoint after
  those endpoints are ready, without blocking its required provisioning flow

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

- **FR-1:** At tenant onboarding, OSAC provides default network resources so
  tenants can create workloads without first building a network. Tenant
  onboarding reports when these defaults are ready or explains what needs
  attention. When provider networking is disabled, logical defaults remain
  available for workload requests, while provider connectivity and managed
  outbound access are not promised. [User]
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

- **FR-6:** A supported workload can be created without a network selection
  and use the tenant's defaults. If the caller provides an incomplete
  selection, OSAC fills only missing values and preserves supplied choices.
  It applies the default SecurityGroup only when it belongs to the selected
  Subnet's VirtualNetwork; otherwise the caller must select compatible
  SecurityGroups. The resolved network is visible when the workload is
  retrieved. [User]
- **FR-7:** When a resource is created with an explicit complete attachment,
  OSAC preserves every supplied selection and does not replace it with a
  default. [User]

#### Auto ExternalIP

- **FR-8:** With provider networking enabled, a Tenant User can request
  automatic inbound access when creating an integrating workload. OSAC confirms
  that enough address capacity is available before accepting the request. Each
  address and route becomes available only after the provider assigns a real
  address and the associated service endpoint is ready. If enabled-mode capacity
  is unavailable, creation fails without leaving a partial workload. With
  provider networking disabled, the request does not block ordinary workload
  provisioning and does not promise an address or route. [User]
- **FR-9:** When a workload integration requests access to multiple endpoints,
  OSAC provides a distinct external address and route for each endpoint. The
  service extension identifies the endpoints; each route becomes available
  only after its address and endpoint are ready. [User]
- **FR-10:** Optional inbound access does not block a workload integration's
  required provisioning or bootstrap path. Each service extension defines its
  required endpoints and makes the resulting access available through its
  documented status and lifecycle. [User]
- **FR-11:** Tenants and administrators can identify automatically created
  external addresses and routes. Workload deletion removes these children in
  dependency order. If provider cleanup fails, deletion remains pending with
  a diagnostic until cleanup succeeds; shared tenant defaults remain. When
  provider networking is disabled, logical deletion remains available but
  provider-side cleanup is not promised. [User]

#### Default NATGateway

- **FR-12:** With provider networking enabled, default network resources
  provide outbound connectivity for workloads using the tenant's default
  VirtualNetwork. With provider networking disabled, OSAC does not promise
  provider-managed outbound connectivity. Re-enabling restores the default
  outbound access after the shared activation requirements are met. [User]

Re-enabling provider networking is a coordinated maintenance transition.
Workload owners must remove existing workloads and the Cloud Provider Admin
must resolve existing provider-side work before new workload creation resumes.
Users can continue to inspect and delete resources during the transition.
OSAC does not move existing workloads to tenant networks. After activation,
each workload waits for its own required network resources; one tenant's
failure does not block other ready tenants. [User]

## 5. Acceptance Criteria

- [ ] During re-enablement, users can inspect and delete existing workloads,
  but new workload creation is rejected until provider networking is ready.
  Existing workloads are not moved automatically.

- [ ] Workload integrations complete required provisioning without optional
  inbound addresses; delayed external access does not stop their required
  bootstrap paths.
- [ ] Tenants with identical configured default CIDRs remain isolated within
  their separate VirtualNetworks.
- [ ] With networking enabled, a persistent external cleanup failure leaves deletion pending with an actionable diagnostic and preserves ownership until repair
- [ ] Requested stateful traffic rules apply before a workload is reported
  network-ready; failed application is visible and does not report successful
  tenant connectivity. [User]
- [ ] Each integrating workload service can request automatic inbound access
  without pre-creating an ExternalIP or ExternalIPAttachment; its service
  extension defines the endpoints and verifies their lifecycle.
- [ ] With provider networking enabled, the tenant's default network and
  outbound access are ready before a workload relies on them.
- [ ] With provider networking disabled, default VirtualNetwork, IPv4 Subnet,
  and SecurityGroup remain available for tenant defaulting and workload
  creation, while the default ExternalIP and NATGateway are absent and no
  provider egress is promised
- [ ] Re-enabling provider networking restores default outbound access before
  new workloads that use it are admitted.
- [ ] Default resources appear in list views with a label identifying
  them as defaults
- [ ] Default networking resources expose only create/read/delete operations;
  a Tenant Admin can create replacement resources with customized settings once
  dependencies on the defaults have been removed
- [ ] Deleting a workload with auto-provisioned external access causes its
  auto-created ExternalIP and ExternalIPAttachment resources to be cleaned up
  automatically, according to the owning service extension's lifecycle.
- [ ] A workload with a complete explicit network selection retains it, while
  an omitted or incomplete selection resolves to the tenant defaults where
  the shared rules permit.
- [ ] With provider networking enabled, if requested automatic inbound access
  has no available address capacity, workload creation fails without leaving a
  partial workload. With provider networking disabled, the request does not
  block provisioning or present an address or route as available.
- [ ] A resource created without explicit network attachments shows the
  resolved default attachments when retrieved via the API
- [ ] IPv6 and dual-stack default ranges are rejected.

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP,
  ExternalIPAttachment, NATGateway) defined in the
  [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **ExternalIP pool selection** — provider networking must expose ready IPv4
  capacity for requested automatic external access.
- **Tenant onboarding** — default resources must be available as part of
  tenant creation.
- **Installation configuration** — deployments must provide valid default
  NetworkClass settings before tenant onboarding.

## 7. Risks

### 7.1 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs
  tenant to explicit allocation from another pool

### 7.2 Default SecurityGroup too permissive

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Cloud Infrastructure Admin configures default rules on
  NetworkClass; Tenant Admin can tighten rules after creation

### 7.3 External access cleanup blocks deletion

- **Owner:** Platform
- **Mitigation:** Enabled-mode deletion stays pending while any automatic
  inbound attachment or address remains; status identifies the failed cleanup
  operation, and retries resume after provider repair. Disabled-mode logical
  deletion follows its explicit provider-cleanup exception. [User]

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

There are no open product questions. Service-specific endpoint and workload
flows are defined by their extension designs.

---

## Provenance

Authored: revise @ prd 0.11.5 - 6d28c88, workspace docs/OSAC-1433-network-manager-provider-guide @ eabff3b59 (76 behind origin/main, dirty)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace docs/OSAC-1433-network-manager-provider-guide @ 639af2dba

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"639af2dba","source_repo_branch":"docs/OSAC-1433-network-manager-provider-guide","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["revise","revise","revise","revise","manual-edit","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
