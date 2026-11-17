# Managed DNS for tenant resource hostnames

| Field | Value |
|-------|-------|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) |
| PRD task | [OSAC-6158](https://redhat.atlassian.net/browse/OSAC-6158) |
| Date | 2026-11-17 |
| Target milestone | 0.5 |
| Status | Draft: delivery scope under review |

## Problem Statement

Tenant users must track VM IP addresses or maintain DNS records separately from
VM provisioning. OSAC automatically publishes DNS records for CaaS API and
application endpoints
([existing DNS behavior](https://github.com/osac-project/osac/blob/d786d49247cb21a4e522a174288436c4a139570b/osac-installer/docs/dns-backend.md)).
It does not yet provide automatic assignment and lifecycle management of DNS
names for individual VMs. [User]
Providers need to integrate VM hostname management with their DNS infrastructure
so tenants can resolve VM names through their own DNS systems. Manual record
maintenance risks stale records and broken access by hostname.

## In Scope

This draft follows the Feature's recorded VMaaS-first, IPv4 boundary.
The [current answers and open decisions](clarifications.md) distinguish agreed
constraints from proposals awaiting review. [Clarify: R16.Q1]

- Automatic hostname creation during VM provisioning and removal during
  deprovisioning. A VM's hostname resolves to its supported IPv4 address.
  DNS records follow supported VM address changes. Names and records persist
  across stop, restart, and migration while their published addresses remain
  assigned to the VM. [User]
- Provider control over publication of tenant-internal addresses, ExternalIP
  addresses, or both. Enabling managed DNS requires explicit provider selection
  of the address publication policy (D4). ExternalIP
  means external to a VirtualNetwork and need not be internet-routable
  ([accepted terminology](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-unified-networking/design.md)). [User]
- Provider-configurable integration with supported existing DNS infrastructure
  without requiring Route 53, preserving the provider's ownership and unrelated
  configuration. [User]
- Predictable VM hostnames within provider-supplied zones. Resource names remain
  fixed after creation, with their existing allowed lengths preserved. DNS names
  distinguish resources with the same name across tenants, projects, and resource
  types, and meet DNS and supported-product limits. The provider assigns tenant
  namespaces within supported provider-supplied writable zones; separate zones
  per tenant are not required (D6). [Jira: OSAC-1061] [User]
- Users can discover their VM's assigned FQDN and publication status, including
  failures, through the API, CLI, and existing VM details UI. Documentation
  covers provider setup, tenant resolution setup, use, and troubleshooting
  (D7). [User]
- VM deletion triggers removal of its managed DNS records through the configured
  integration. DNS outages do not block otherwise usable VMs, and VM deletion
  does not wait for DNS cleanup. Administrators can inspect pending or failed
  cleanup and its retry status through supported operational interfaces until
  cleanup completes, including after the VM has been deleted. [User]
- Publication and cleanup status report what the supported integration can
  establish, distinguishing confirmed completion from pending, failed, or unknown
  outcomes. Documentation explains provider propagation and resolver-cache limits;
  record removal does not guarantee that clients stop using earlier answers or
  that those answers cannot reach a reassigned address. [User]
- Replacement of an assigned tenant domain is rejected while that tenant has
  VMs or its owned DNS cleanup is incomplete. Existing configuration, names,
  and records are preserved on rejection. [User]
- Changes to DNS provider, zone, or namespace settings are rejected when they
  would leave managed records or unfinished cleanup without a supported cleanup
  path. Rejection preserves the existing configuration and records. [User]
- DNS changes for one tenant preserve other tenants' records and records
  unrelated to this workflow. [User]
- Tenants can resolve their VM hostnames from their own networks using the
  provider's DNS integration and existing DNS access policy. The provider supplies
  the necessary DNS access and configuration. Tenant Admins can see their assigned
  domain and the information needed to configure resolution. [User]

## Out of Scope

- BMaaS, CaaS cluster endpoint, and MaaS hostname integration in this proposed
  delivery. Compatibility and reuse evaluation with existing CaaS DNS remain
  required. [User]
- Automatic DNS adoption of pre-existing VMs. D2 records this initial exclusion.
- Tenant self-service management of arbitrary DNS records beyond automatically
  provisioned resource hostnames.
- Tenant self-service onboarding or delegation of custom DNS domains.
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
- As a Cloud Infrastructure Admin with permission to monitor DNS, I want to see
  publication and cleanup success, pending work, failures, and retry state,
  including cleanup for deleted VMs, so I can diagnose DNS problems without
  inspecting implementation internals. [User]

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
  before requirements approval. The remaining product choices and candidate
  lifecycle and configuration outcomes are in the
  [decision companion](clarifications.md#open-decisions). Completing this PRD
  does not complete Feature implementation. [User]
- CaaS/DNS maintainers participate before the VMaaS approach is selected.
  Existing CaaS endpoint DNS continues to work, preserving endpoint names and
  agreed resolution, readiness, and cleanup behavior. Design evaluates
  compatibility and reuse with its configurable backend and provider configuration.
  A shared configuration model is not required. Any later adoption of a new DNS
  integration for CaaS requires an explicit provider choice. [User]
- Networking/DNS owners review intended resolution paths, cleanup confirmation,
  and documented propagation, cache, and address-reuse limitations.
  Any required change to resolver delivery or network lifecycle must explicitly
  extend the applicable accepted contract; per-VirtualNetwork query isolation is
  not selected or assumed available. [Clarify: R16.Q1]
- The Feature calls for a supported OpenShift External DNS Operator and operand
  integration where supported capabilities meet deployment needs. It does not
  require an exclusive implementation. D13 records this constraint. [User]
- [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) qualifies a VM-to-DNS
  integration supported for the deployment's platform version and DNS service,
  including observable publication success and failure. Design qualifies and
  documents supported deployment volumes and change rates, and measured
  publication/removal/recovery and resolver behavior. Any required deployment
  minimum or deadline is recorded in the PRD when identified. Integrations follow
  documented product lifecycle and supported-version policies; no additional
  maintenance or rebase commitment is assumed (D11). Qualification belongs in the
  [design handoff](clarifications.md#design-handoff). [User]

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ f6b842aa6
Final: respond @ prd 0.11.5 - 922de34, workspace main @ 032e75ead

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"922de34","source_repo":"032e75ead","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":53,"main_ref":"main","phases":["draft","revise","revise","revise","revise","respond","respond","revise","revise","revise","revise","revise","respond","respond","respond","revise","revise","revise","revise","respond","respond","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
