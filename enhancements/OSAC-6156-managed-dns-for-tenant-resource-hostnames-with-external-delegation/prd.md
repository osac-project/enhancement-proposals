# Managed VM hostnames through ExternalDNS

| Field | Value |
|-------|-------|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) |
| PRD task | [OSAC-6158](https://redhat.atlassian.net/browse/OSAC-6158) |
| Date | 2026-10-29 |
| Target milestone | 0.5 |
| Status | Draft — VMaaS-first scope proposed for review |

The proposed deliverable is automatic VM hostnames through the Red Hat External
DNS Operator. The Feature owner must confirm this initial delivery boundary (D1).
[User]

## Problem Statement

Tenant users must track VM IP addresses or maintain DNS records separately from
VM provisioning. OSAC already manages CaaS endpoint DNS through a configurable
backend, while VMaaS lacks an automatic resource-hostname workflow
([existing DNS behavior](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/osac-installer/docs/dns-backend.md)).
Providers need to integrate VM hostname management with their DNS infrastructure
so tenants can resolve VM names through their own DNS systems. Without this
capability, tenants maintain records manually, risking stale records and broken
access by hostname.

## In Scope

The following boundaries describe the proposed VMaaS-first increment. [User]

- Integration with the Red Hat External DNS Operator for automatic VM hostname
  record creation during provisioning and removal during deprovisioning. The
  address source follows OSAC's existing connected, IPv4 networking contract;
  the initial records are A records. Automatic AAAA publication requires a
  supported IPv6 endpoint and address-feedback contract (D5). [User]
- Operator availability follows OSAC's normal prerequisite installation workflow:
  the Cloud Infrastructure Admin can select OSAC-managed installation or use a
  compatible administrator-managed installation. Using an existing installation
  preserves its ownership and unrelated DNS configuration. [User]
- Provider control over publication of ExternalIP addresses, tenant-internal
  addresses, or both, with the address policy and query visibility agreed in D4.
  ExternalIP means external to a VirtualNetwork and need not be internet-routable
  ([accepted terminology](https://github.com/osac-project/enhancement-proposals/blob/bb9e8f6475e65304f000b49fc4405616b8eb2f6f/enhancements/OSAC-1433-unified-networking/design.md)).
- Predictable VM hostnames within provider-supplied DNS zones. DNS mapping
  preserves OSAC's existing resource-name contract and distinguishes resources
  across tenant, project, and resource-type scopes. Generated names must meet DNS
  and supported-product limits. Users can discover the
  assigned FQDN; the exact layout is established during design. Tenant-domain
  assignment remains D6. [Jira: OSAC-1061] [User]
- External tenant DNS resolution through NS delegation of a subdomain or
  conditional forwarding to the DNS service hosting the managed records. For
  example, delegating `osac.example.com` enables resolution beneath that
  subdomain. The provider supplies authoritative DNS and writable zones as
  deployment prerequisites. [User]

## Out of Scope

- BMaaS, CaaS, and MaaS DNS integration, including CaaS Route 53 migration,
  under the proposed initial delivery boundary. [User]
- Tenant self-service management of arbitrary DNS records beyond automatically
  provisioned VM hostnames.
- VM console hostname exposure.
- Provisioning production authoritative DNS servers or DNS zones. The provider
  supplies the DNS service and zones for this increment. [User]
- IPv6 and dual-stack enablement, which follow the separate
  [IPv6 parity Feature](https://redhat.atlassian.net/browse/OSAC-5077).
  Automatic AAAA publication follows a supported IPv6 endpoint and feedback
  contract. [User]
- DNS-based load balancing or failover.
- DNSSEC.
- Public domain registration; tenants retain responsibility for their registrars.
- OSAC in-place upgrades, which the platform does not currently support.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin with permission to configure the provider's DNS
  offering, I want to configure the DNS zones used for VM hostnames so that
  tenant VMs receive resolvable names automatically.
- As a Cloud Provider Admin with permission to set DNS publication policy, I want
  to select the VM address ranges published in managed zones so that the DNS
  offering follows the provider's intended internal and external access scope.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin responsible for VM provisioning, I want VM
  hostname records to be created and removed automatically with their resources
  so that DNS follows the infrastructure lifecycle.
- As a Cloud Infrastructure Admin responsible for DNS integration, I want OSAC VM
  hostname management to integrate with the Red Hat External DNS Operator so that
  I can operate it within the deployment's DNS infrastructure. [User]
- As a Cloud Infrastructure Admin responsible for installation, I want to select
  OSAC-managed or administrator-managed External DNS Operator installation so
  that VM DNS follows the deployment's operator ownership policy. [User]

### Tenant Admin

- As a Tenant Admin responsible for my organization's external DNS, I want to
  configure subdomain delegation or conditional forwarding to the provider's DNS
  service so that my users can resolve OSAC VM names from outside OSAC.

### Tenant User

- As a Tenant User with access to a provisioned VM, I want its automatically
  assigned hostname to resolve to the published address so that I can access the
  VM by name.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want my tenant's VM hostnames to follow a
  predictable pattern so that access policies, applications, and scripts can
  reference VMs by name.

## Dependencies

Scope confirmation remains necessary before PRD approval:

- **D1 — Delivery boundary:** the Feature owner must confirm the proposed
  VMaaS-first increment. The [first-phase comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19101116)
  proposes that boundary; the Feature description still lists all four services.
  This draft does not represent a completed Jira scope decision.
- **D5 — IPv6 dependency:** the initial publication path uses supported IPv4 VM
  addresses. Automatic AAAA publication requires an approved IPv6 endpoint and
  feedback contract, with integration coverage. Generic AAAA record support does
  not establish usable VM IPv6 networking. The broader Feature checklist must
  reflect this delivery boundary during review. [User]

Five practical question groups remain. Answering roles are proposed review
routing, not assignments made in Jira. Original decision references are retained
for traceability.

| References | Remaining question | Answering roles | Effect |
|------------|--------------------|-----------------|--------|
| D2 | To be determined — must enabling managed DNS assign names to existing VMs, or only VMs provisioned afterward? | Feature owner and customer liaison | Defines VM adoption. Required customer-specific compatibility or support constraints are collected with the deployment inputs for D10. |
| D4 | To be determined — which VM addresses are published, and which clients can resolve them within or across tenants and VirtualNetworks? | Feature owner and networking/security owners | Establishes address publication and query visibility as separate acceptance requirements. |
| D6 | To be determined — do tenants use provider-assigned subdomains, tenant-controlled delegated subdomains, or both? Who assigns or approves each tenant's DNS namespace? | Feature owner, Cloud Provider Admin, and Tenant Admin representative | Defines domain assignment and ownership. The provider supplies authoritative DNS and writable zones under D3; hostname layout and numeric limit validation are design work. |
| D7, behavioral part of D9 | To be determined — which configuration, hostname-discovery, and success/failure workflows are needed in UI, CLI, and API, with what documentation? What happens to names on stop/restart or an address change, and how do DNS failures affect VM availability and deletion? | Feature owner and affected persona representatives | Defines a usable VM workflow and observable lifecycle/failure behavior without inventing new resource states. |
| Quantitative part of D9 | To be determined — what tenant/VM/record volumes, change rates, publication/removal times, and cache lifetimes must be supported? | Feature owner and Cloud Infrastructure Admin | Supplies measurable capacity and timing acceptance; existing defaults and lab timings are not service commitments. |

Design and validation follow the agreed product boundary:

- **D3 — DNS prerequisites:** the provider supplies the authoritative DNS service
  and writable zones. Production server deployment and zone provisioning are
  separate capabilities. Disposable DNS backends for development/testing do not
  expand the production offering. [User]
- **D6 — Naming constraints:** preserve immutable OSAC resource identity and its
  existing allowed name lengths. Establish an unambiguous DNS mapping for tenant
  and project scopes, including nested/default projects, and validate complete
  generated names. The exact hostname format is established during design. [User]
- VM address discovery, tenant ownership, and attachment lifecycle follow the
  [accepted VMaaS networking contract](https://github.com/osac-project/enhancement-proposals/blob/bb9e8f6475e65304f000b49fc4405616b8eb2f6f/enhancements/OSAC-1435-vmaas-networking/design.md).
  The current connected IPv4 boundary and tenant permissions are preserved unless
  explicitly extended. DNS query visibility requires its own policy in D4.
- The authoritative DNS service must be reachable through the agreed resolver
  path. Delegation or forwarding depends on control of the tenant's external DNS
  configuration. DNS verification preserves the
  [configured-resolver behavior](https://redhat.atlassian.net/browse/OSAC-6342),
  including cache effects.
- **D10 — Deployment qualification:** the design must qualify the supported
  External DNS Operator deployment,
  configured DNS provider, and VM record-publication mechanism. Operator setup
  follows the existing
  [prerequisite lifecycle convention](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands):
  OSAC-managed installation or compatible administrator-managed installation,
  with configuration and resource ownership respected in either mode. ExternalDNS
  handles its supported DNS-provider integrations. The
  [CRD-source request](https://redhat.atlassian.net/browse/RFE-7197) has no committed
  delivery date; DNSEndpoint support is not assumed. Alternatives remain in the
  design evaluation. [User]
- [DNSaaS](https://redhat.atlassian.net/browse/OSAC-3202),
  [local authoritative DNS](https://redhat.atlassian.net/browse/OSAC-2127), and
  [BIND integration](https://redhat.atlassian.net/browse/OSAC-2281) are coordination
  references. This increment does not require those broader Features to ship
  first. Any later extension to zone or authoritative-server provisioning must
  coordinate with those owners.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7b2b8de, workspace main @ f6b842aa6
Phases: draft, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f6b842aa6","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":28,"main_ref":"main","phases":["draft","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
