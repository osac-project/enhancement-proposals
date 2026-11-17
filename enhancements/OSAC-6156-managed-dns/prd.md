# Managed DNS for tenant resource hostnames

| Field | Value |
|-------|-------|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) |
| PRD task | [OSAC-6158](https://redhat.atlassian.net/browse/OSAC-6158) |
| Date | 2026-11-16 |
| Target milestone | 0.5 |
| Status | Draft: delivery scope under review |

## Problem Statement

Tenant users must track VM IP addresses or maintain DNS records separately from
VM provisioning. OSAC automatically publishes DNS records for CaaS API and
application endpoints
([existing DNS behavior](https://github.com/osac-project/osac/blob/032e75eadb2524eeafce03ef8c1f97eda70feefa/osac-installer/docs/dns-backend.md)).
It does not yet provide automatic assignment and lifecycle management of DNS
names for individual VMs. [User]
Providers need to integrate VM hostname management with their DNS infrastructure
so tenants can resolve VM names through their own DNS systems. Manual record
maintenance risks stale records and broken access by hostname.

## In Scope

This draft follows the Feature's recorded VMaaS-first, IPv4 boundary.
Agreement on that boundary and broader service coverage remains D1.
The [current answers and open decisions](clarifications.md) distinguish agreed
constraints from proposals awaiting review. [Clarify: R16.Q1]

- Automatic hostname creation during VM provisioning and removal during
  deprovisioning. A VM's hostname resolves to its supported IPv4 address.
- Provider control over publication of tenant-internal addresses, ExternalIP
  addresses, or both. Defaults and who may resolve names remain D4. ExternalIP
  means external to a VirtualNetwork and need not be internet-routable
  ([accepted terminology](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-unified-networking/design.md)).
- Integration with the provider's supported existing DNS infrastructure,
  preserving its ownership and unrelated configuration. [User]
- Predictable VM hostnames within provider-supplied zones. Resource names remain
  fixed after creation, with their existing allowed lengths preserved. DNS names
  distinguish resources with the same name across tenants, projects, and resource
  types, and meet DNS and supported-product limits. Tenant-domain assignment
  remains D6. [Jira: OSAC-1061] [User]
- Users can discover their VM's assigned FQDN and publication status, including
  failures. Required API, CLI, and UI surfaces remain D7.
- DNS changes for one tenant preserve other tenants' records and records
  unrelated to this workflow. Query visibility is a separate D4 policy. [User]
- Tenants can resolve their VM hostnames from their own networks using the
  provider's DNS integration. Tenant Admins can see their assigned domain and
  the information needed to configure that resolution. [Clarify: R16.Q1]

## Out of Scope

- BMaaS, CaaS cluster endpoint, and MaaS hostname integration in this proposed
  delivery. Broader service coverage remains D1; compatibility and reuse
  evaluation with existing CaaS DNS remain required. [User]
- Tenant self-service management of arbitrary DNS records beyond automatically
  provisioned resource hostnames.
- VM console access or BMaaS IPMI/Redfish endpoint hostname exposure.
- Provisioning production authoritative DNS servers or DNS zones. The provider
  supplies them for the proposed delivery. [User]
- IPv6, AAAA publication, and dual-stack enablement in the initial delivery.
  D5 records alignment with separate IPv6 work. [User]
- DNS-based load balancing or failover, DNSSEC, and public domain registration.
  Tenants retain responsibility for their registrars.
- OSAC in-place upgrades, which the platform does not currently support.

## User Stories

### Cloud Provider Admin / Cloud Infrastructure Admin

- As a Cloud Provider Admin or Cloud Infrastructure Admin with permission to
  configure the DNS offering, I want to integrate the VM hostname zones with the
  provider's existing DNS infrastructure so that tenants can use VM names without
  maintaining records separately. [Clarify: R16.Q1]
- As a Cloud Provider Admin with permission to set DNS publication policy, I
  want to select the VM addresses published in managed
  zones so that the offering follows the provider's intended access scope.

### Tenant Admin

- As a Tenant Admin responsible for my organization's DNS, I want to see my
  assigned domain and the provider's DNS setup information so that I can configure
  resolution of OSAC VM names from my organization's network. [Clarify: R16.Q1]

### Tenant User

- As a Tenant User with access to a provisioned VM, I want its automatically
  assigned hostname to resolve to the published address so that I can connect
  without tracking its IP address.
- As a Tenant User, I want to see my VM's hostname and publication status so
  that I can connect without tracking IP addresses and recognize DNS failures.
  [Clarify: R16.Q1]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my tenant's VM hostnames to follow a
  predictable pattern so that access policies, applications, and scripts can
  reference VMs by name.

## Dependencies

- Managed DNS follows OSAC's supported deployment modes. Expanding platform
  support to additional deployment modes is separate work. [User]
- The provider supplies authoritative DNS and zones, and the provider and Tenant
  Admin supply the access needed for resolution from the intended client networks.
- The Feature owner and reviewers confirm delivery scope and remaining choices
  before requirements approval. The remaining product choices and candidate adoption,
  lifecycle, and configuration outcomes are in the
  [decision companion](clarifications.md#open-decisions). Completing this PRD
  does not complete Feature implementation. [User]
- CaaS/DNS maintainers participate before the VMaaS approach is selected.
  Existing CaaS endpoint DNS continues to work, preserving endpoint names and
  agreed resolution, readiness, and cleanup behavior. Design evaluates
  compatibility and reuse with its configurable backend. Any later adoption of
  a new DNS integration for CaaS requires an explicit provider choice. [User]
- Networking/DNS owners review the selected visibility and cleanup requirements.
  Any required change to resolver delivery or network lifecycle must explicitly
  extend the applicable accepted contract; per-VirtualNetwork query isolation is
  not selected or assumed available. [Clarify: R16.Q1]
- [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) qualifies a VM-to-DNS
  integration supported for the deployment's platform version and DNS service,
  including observable publication success and failure. Technology constraints
  remain subject to D13; detailed qualification belongs in the
  [design handoff](clarifications.md#design-handoff). [User]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ f6b842aa6
Final: revise @ prd 0.11.5 - 922de34, workspace main @ 032e75ead

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"922de34","source_repo":"032e75ead","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":53,"main_ref":"main","phases":["draft","revise","revise","revise","revise","respond","respond","revise","revise","revise","revise","revise","respond","respond","respond","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
