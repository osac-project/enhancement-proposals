# Simplified Resource Creation — Default Networking and Auto ExternalIP

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1433 |
| Date        | 2026-09-24 |

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

Without default networking, creating a reachable resource can require several
sequential API calls: VirtualNetwork, an optional NetworkACL, Subnet, the
resource itself, ExternalIP, and ExternalIPAttachment. Every tenant must
understand the full networking resource model before provisioning their first
VM, cluster, or bare-metal server. This friction slows onboarding, increases
the chance of misconfiguration, and makes OSAC harder to adopt compared to
platforms where a single create command produces a reachable instance.

## 2. Goals and Non-Goals

### 2.1 Goals

All default networking resources use canonical IPv4 CIDRs. IPv6 and
dual-stack networking are not supported.

- A tenant can create a fully connected VM, bare-metal server, or cluster
  (inbound + outbound) with a single API call on a deployment whose required
  default ACL action is `PERMIT`. With `DENY`, the default Subnet has no ACL
  association and denies unmatched ingress and egress; a tenant that needs
  connectivity must first create an ACL and a Subnet associated with it, then
  select that Subnet when creating the workload.
- Tenants who need custom networking retain the full explicit workflow —
  simplified creation is additive, not a replacement
- Auto-provisioned networking resources are visible and follow the unified
  read/create/delete lifecycle; ACL rules and Subnet ACL associations are fixed at creation

### 2.2 Non-Goals

- Custom default configurations per tenant (all tenants in a deployment
  receive the same default CIDRs and deployment-wide NetworkACL default action)
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

- As a Cloud Infrastructure Admin, I want to configure default IPv4 CIDRs
  and the deployment-wide default ACL action (`PERMIT` or `DENY`) on the
  NetworkClass, so tenant networking has a defined fallback policy

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether a tenant's
  default networking resources were successfully provisioned, so I can
  troubleshoot onboarding failures

## 4. Requirements

### 4.1 Functional Requirements

#### Default Networking

- **FR-1:** At tenant onboarding, the system provisions a default
  VirtualNetwork, an IPv4 Subnet, and a NATGateway for the tenant. The default
  Subnet has no NetworkACL association, so the deployment-wide default ACL
  action governs its unmatched traffic. The tenant transitions to READY only
  after the default VirtualNetwork, Subnet, and NATGateway are READY. If
  default networking provisioning fails, the tenant remains non-READY with a
  status condition describing the failure. The Cloud Provider Admin can
  inspect the failure and retry by deleting and recreating the tenant. [User]
- **FR-2:** The Cloud Infrastructure Admin configures deployment-wide default
  networking parameters on the NetworkClass: IPv4 CIDRs and one required
  NetworkACL default action, `PERMIT` or `DENY`. For each direction, an
  associated NetworkACL's first matching rule decides the packet; if no rule
  matches or no ACL is associated, the NetworkClass default action decides it.
  ACL rules add more-specific decisions and do not replace the default action.
  The tenant default Subnet has no NetworkACL association, so `DENY` blocks
  unmatched ingress and egress on that Subnet. NATGateway and ExternalIP
  resources do not bypass this policy. To permit traffic with a `DENY` fallback,
  a tenant creates a NetworkACL with the needed rules, creates a Subnet that
  references it, and attaches workloads to that Subnet; the association cannot
  be added to the already-created default Subnet.
  Rule precedence is based on match specificity, not action or request order.
  Since ACLs are stateless, ingress and egress, including reply traffic, are
  evaluated independently. With a `DENY` default, permitting a reply requires
  a matching reverse-direction `ALLOW` rule to win precedence; with `PERMIT`,
  an unmatched reply passes unless a matching reverse-direction `DENY` applies.
  A NetworkClass
  without the required defaults is rejected. [User]
- **FR-3:** All tenants receive the same default IPv4 CIDR ranges as
  configured on the NetworkClass. Tenants are isolated at the
  network level — the unified networking API provides VirtualNetworks
  with any IP subnet, and the system enforces isolation regardless of
  overlapping CIDRs between tenants. [User]
- **FR-4:** Default VirtualNetwork, Subnet, and NATGateway resources are
  labeled as defaults and visible in list and detail views. They follow the
  unified networking read/create/delete contract. Address configuration is
  immutable after creation; deletion is blocked while any resource depends on
  the resource. [User]
- **FR-5:** Creating custom VirtualNetworks does not affect the tenant's
  default VirtualNetwork, Subnet, or NATGateway. No ACL resource is created
  automatically for any VirtualNetwork. A Subnet in any VirtualNetwork may
  have zero or one explicitly selected NetworkACL; if omitted, it stays
  unassociated and the deployment default ACL policy applies when no rule
  matches. [User]

#### Optional Network Attachments

- **FR-6:** The network attachment configuration on ComputeInstance,
  Cluster, and BaremetalInstance is optional and supports at most one tenant
  attachment. The attachment refers to a Subnet only. A NetworkACL associated
  with that Subnet adds matching traffic decisions; unmatched traffic uses the
  deployment default ACL policy. When omitted or empty, the system
  populates the attachment with the tenant's default Subnet. A supplied
  Subnet is preserved, and a missing Subnet is defaulted. BaremetalInstance
  also defaults a missing physical interface. The resolved attachment is
  stored with the resource. VMaaS and BMaaS retain plural field names for API
  compatibility; CaaS retains its singular field. [User]
- **FR-7:** When a resource is created with an explicit Subnet attachment, the
  system preserves it and does not replace it with a default. A missing
  Subnet receives the tenant default Subnet; a missing BMaaS interface
  receives the default fabric interface. [User]

#### Auto ExternalIP

- **FR-8:** ComputeInstance and BaremetalInstance support
  `--external-ip-attachment`. When enabled, the system selects an available
  IPv4 ExternalIPPool with the most capacity and reserves capacity for one
  ExternalIP with the workload create request. The ExternalIP is allocated
  asynchronously. The ExternalIPAttachment is created only after the ExternalIP
  is Allocated and the target workload is Ready. When pools have equal
  capacity, selection is deterministic but unspecified. [User]
- **FR-9:** Cluster supports `--external-ip-attachment`. When enabled,
  the system reserves capacity for two ExternalIPs with the cluster create
  request: one for the API server and one for ingress. The IPs are allocated
  asynchronously. [User]
- **FR-10:** The two ExternalIPAttachments are created only after both
  ExternalIPs are Allocated and the Cluster is Ready with its API and ingress
  endpoint addresses. Inbound routing becomes available after those
  attachments are provisioned; no attachment targets a cluster before it is
  Ready. [User]
- **FR-11:** Auto-created ExternalIP and ExternalIPAttachment resources
  are labeled as auto-provisioned. When the parent resource is deleted,
  the system deletes auto-created ExternalIPAttachments first, then
  ExternalIPs, before the parent resource is removed. If cleanup of
  auto-created resources fails permanently, the parent resource is still
  deleted — orphaned ExternalIPs remain and must be cleaned up manually
  by the Tenant Admin or Cloud Provider Admin. An active, manually created
  ExternalIPAttachment targeting a workload blocks its deletion until the
  tenant removes the attachment; other manually created ExternalIPs remain
  tenant-managed. [User]

#### Default NATGateway

- **FR-12:** At tenant onboarding, the system also provisions a
  NATGateway on the default VirtualNetwork with an automatically
  allocated ExternalIP. The NATGateway provides a path for outbound traffic,
  subject to the effective Subnet policy; it does not bypass NetworkACL rules
  or the deployment default ACL action. The default Subnet has no ACL
  association, so a `DENY` fallback blocks unmatched egress and replies. A
  workload that needs outbound connectivity under `DENY` must use a Subnet
  associated at creation with an ACL that permits the required egress and
  reverse-direction reply traffic. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a ComputeInstance with
  `--external-ip-attachment` and no explicit network attachments — the VM
  is created on the default subnet with an auto-provisioned ExternalIP;
  inbound reachability follows the effective Subnet policy, so unmatched
  inbound traffic is denied when the deployment default is `DENY`
- [ ] A Tenant User can create a Cluster with `--external-ip-attachment`
  and no explicit network attachments — the cluster is provisioned with
  ExternalIPs for both API and ingress, all resolved automatically; inbound
  reachability follows the effective Subnet policy, so unmatched inbound
  traffic is denied when the deployment default is `DENY`
- [ ] A Tenant User can create a BaremetalInstance with
  `--external-ip-attachment` and no explicit network attachments — the
  server is placed on the default subnet and receives an ExternalIP after it
  is Allocated and the server is Ready; inbound reachability follows the
  effective Subnet policy, so unmatched inbound traffic is denied when the
  deployment default is `DENY`
- [ ] Tenant onboarding creates the default VirtualNetwork and waits for it
  to become READY before creating the unassociated default Subnet; it waits
  for the Subnet to become READY before creating the NAT ExternalIP, waits for
  that IP to become Allocated, and then creates the NATGateway and waits for it
  to become READY. It creates no default NetworkACL resource.
- [ ] A Subnet may have zero or one NetworkACL association. Omitting the ACL
  leaves it unset; an explicit ACL must be READY and scoped to the same
  VirtualNetwork, and multiple ACL references are rejected.
- [ ] The deployment has one required default ACL action, `PERMIT` or `DENY`.
  The first matching ACL rule decides traffic; if no rule matches or no ACL
  is associated, the configured default action decides. Reply traffic is
  evaluated independently in the reverse direction: unmatched replies pass
  under `PERMIT` unless a matching `DENY` rule applies, and are denied under
  `DENY` unless a matching `ALLOW` rule wins precedence.
- [ ] With `DENY` and no ACL association on the tenant default Subnet, unmatched
  ingress and egress remain denied; NATGateway and ExternalIP configuration do
  not bypass the Subnet policy
- [ ] Default VirtualNetwork, Subnet, and NATGateway resources appear in list
  views with a label identifying them as defaults.
- [ ] Default networking resources support read/create/delete. Subnet address
  configuration and any selected NetworkACL association cannot be updated
  after creation; replacement requires deleting and recreating dependents.
- [ ] Deleting a resource with auto-provisioned ExternalIP causes the
  auto-created ExternalIP and ExternalIPAttachment to be cleaned up
  automatically
- [ ] A complete explicit network attachment is preserved and bypasses
  attachment defaults; an omitted or partial attachment receives defaults for
  missing fields as specified in FR-6
- [ ] When no ExternalIPPool has available capacity, the create API call
  returns an error and the workload is not persisted
- [ ] Auto-created ExternalIPAttachments are created only after the
  ExternalIP is Allocated and the target workload is Ready; cluster
  attachments wait for the Cluster to be Ready with both endpoint addresses
- [ ] A resource created without explicit network attachments shows the
  resolved default Subnet attachment when retrieved via the API. If the Subnet
  has a NetworkACL association, the association is visible through the Subnet;
  if no ACL is associated, the tenant-facing UI shows generic deployment-policy
  fallback guidance without displaying the provider-only action value
- [ ] An IPv6 or dual-stack default CIDR is rejected when NetworkClass defaults
  are validated, and no default resource is persisted from the invalid input

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking
  resource model (VirtualNetwork, Subnet, NetworkACL, ExternalIP,
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

### 7.2 Deployment default ACL policy is too permissive

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Configure the required deployment default action as `DENY`
  when traffic should be denied unless explicitly permitted. If `PERMIT` is
  selected, explicitly associated NetworkACLs can add more-specific DENY rules.
  Changing the deployment default action changes the fallback for all
  unmatched traffic in the deployment and must be reviewed as a coordinated
  policy change.

### 7.3 Auto ExternalIP orphans on partial failure

- **Owner:** Platform
- **Mitigation:** Parent resource finalizer handles cleanup; controller
  retries on transient failures. If cleanup permanently fails, the
  finalizer is removed and the parent is deleted — orphaned ExternalIPs
  must be cleaned up manually

### 7.4 Deployment misconfiguration

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** IPv4 networking defaults and the deployment-wide default
  ACL action are required — a NetworkClass without them is rejected at
  creation time. This prevents tenant onboarding and resource creation from
  using an undefined baseline policy.
  osac-installer setup.sh includes NetworkClass default configuration in
  installation overlays

## 8. Open Questions

### ~~8.1 Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

### ~~8.2 E2E test coverage for simplified creation~~ — Resolved

Resolved: E2E tests for simplified creation are defined in each per-service design's test plan (VMaaS, CaaS, BMaaS). No separate test plan needed in the default networking EP.

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ 2293f9140
Phases: respond, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["respond","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
