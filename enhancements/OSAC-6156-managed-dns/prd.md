# Managed DNS for tenant resource hostnames

| Field | Value |
|-------|-------|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) |
| PRD task | [OSAC-6158](https://redhat.atlassian.net/browse/OSAC-6158) |
| Date | 2026-10-29 |
| Target milestone | 0.5 |
| Status | Draft — delivery scope under review |

This PRD examines managed DNS for tenant resource hostnames through the required
Red Hat External DNS Operator. D1 asks whether delivery starts with VMaaS or
covers the broader Feature. [User]

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

The following requirements describe the VMaaS-first option under review in D1.
[User]

- Integration with the Red Hat External DNS Operator for automatic VM hostname
  record creation during provisioning and removal during deprovisioning. The
  proposed offering is limited to connected deployments and publishes A records
  for supported IPv4 VM addresses. Automatic AAAA publication requires an IPv6
  endpoint supported by the offering (D5). [User]
- Operator availability follows OSAC's normal prerequisite installation workflow:
  the Cloud Infrastructure Admin can select OSAC-managed installation or use a
  compatible administrator-managed installation. Using an existing installation
  preserves its ownership and unrelated DNS configuration
  ([existing prerequisite convention](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands)). [User]
- Provider control over publication of ExternalIP addresses, tenant-internal
  addresses, or both, with the address policy and query visibility agreed in D4.
  ExternalIP means external to a VirtualNetwork and need not be internet-routable
  ([accepted terminology](https://github.com/osac-project/enhancement-proposals/blob/bb9e8f6475e65304f000b49fc4405616b8eb2f6f/enhancements/OSAC-1433-unified-networking/design.md)).
- Predictable VM hostnames within provider-supplied DNS zones. VM resource names
  remain fixed after creation, and managed DNS does not reduce their existing
  allowed lengths. DNS names distinguish resources with the same name
  across tenants, projects, and resource types. Generated names must meet DNS
  and supported-product limits. Users can discover the assigned FQDN; the exact
  layout is established during design. Tenant-domain assignment remains D6.
  [Jira: OSAC-1061] [User]
- Automatic DNS changes for one tenant's VMs preserve other tenants' records and
  records unrelated to this workflow. Query visibility is a separate policy
  decision in D4. [User]
- External tenant DNS resolution through NS delegation of a subdomain or
  conditional forwarding to the DNS service hosting the managed records. For
  example, delegating `osac.example.com` enables resolution beneath that
  subdomain. The provider supplies authoritative DNS and writable zones as
  deployment prerequisites (D3). [User]

## Out of Scope

- If VMaaS-first is selected under D1, BMaaS, CaaS, and MaaS DNS integration,
  including CaaS Route 53 migration, are excluded from that delivery. They remain
  part of the broader Feature. [User]
- Tenant self-service management of arbitrary DNS records beyond automatically
  provisioned resource hostnames.
- VM console access or BMaaS IPMI/Redfish endpoint hostname exposure.
- Provisioning production authoritative DNS servers or DNS zones. The provider
  supplies the DNS service and zones for the proposed delivery. [User]
- IPv6 and dual-stack enablement, which follow the separate
  [IPv6 parity Feature](https://redhat.atlassian.net/browse/OSAC-5077).
  The proposed record-family boundary is described in In Scope and remains
  subject to D5 alignment. [User]
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
  hostnames to resolve through my deployment's existing DNS infrastructure so
  that users can access VMs by name across the deployment. [User]
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

The following scope confirmations and product decisions remain approval gates.
Answering roles are proposed review routing, not Jira assignments. Answers must
be incorporated into the requirements before approval. [User]

- **D1 — Delivery boundary:** to be determined — does delivery start with VMaaS
  or cover the broader Feature, including BMaaS, CaaS, MaaS, and CaaS DNS
  integration? The Feature owner confirms the boundary and records a phase split
  in Jira if one is selected. The
  [first-phase comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19101116)
  proposes VMaaS-first; it does not establish the decision. Completing this PRD
  task does not satisfy the broader Feature checklist. [User]
- **D5 — IPv6 alignment:** the Feature owner must reconcile the AAAA checklist
  with the proposed IPv4/A boundary and separate
  [IPv6 parity work](https://redhat.atlassian.net/browse/OSAC-5077). [User]

| References | Remaining question | Answering roles | Effect |
|------------|--------------------|-----------------|--------|
| D2 | To be determined — must enabling managed DNS assign names to existing VMs, or only VMs provisioned afterward? | Feature owner and customer liaison | Defines VM adoption. |
| D4 | To be determined — which VM addresses are published, and which clients can resolve each name within or across tenants, VirtualNetworks, and applicable provider VPCs? | Feature owner and networking/security owners | Defines address publication and query visibility separately. Acceptance must check overlapping tenant addresses and the lookups allowed or denied by the agreed policy; universal cross-tenant lookup denial is not assumed. |
| D6 | To be determined — do tenants use provider-assigned subdomains, tenant-controlled delegated subdomains, or both? Who assigns or approves each tenant's DNS namespace? | Feature owner, Cloud Provider Admin, and Tenant Admin representative | Defines domain assignment and ownership; hostname layout and limit validation belong in design. |
| D7 | To be determined — which configuration, hostname-discovery, and success/failure workflows are needed in UI, CLI, and API, with what documentation? | Feature owner and affected persona representatives | Defines a usable, observable VM DNS workflow. |
| Behavioral part of D9 | To be determined — what happens to assigned names and records on VM stop/restart, address change, and ExternalIP attachment/detachment? How do DNS outages affect VM readiness and deletion? | Feature owner, networking owners, and affected persona representatives | Establishes observable lifecycle and failure outcomes; a temporary absence of reported addresses must not implicitly select the DNS policy. |
| Quantitative part of D9 | To be determined — what tenant/VM/record volumes, change rates, publication/removal times, and cache lifetimes must be supported? | Feature owner and Cloud Infrastructure Admin | Supplies measurable capacity and timing acceptance; existing defaults and lab timings are not service commitments. |
| D11 | To be determined — what maintenance, supported-version, and upstream-update commitments are required for this offering, and what has the Red Hat product owner confirmed? | Feature owner, customer liaison, and External DNS Operator product owner | Records available commitments and accepted constraints before approval; version-number clarification does not answer the maintenance question. |

External dependencies:

- **D10 — Supported integration:** automatic VM records must use an integration
  supported for the deployment. Delivery must not depend on
  [RFE-7197](https://redhat.atlassian.net/browse/RFE-7197), which is
  **Closed / Won't Do**. Qualification evidence and coordination context for
  [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) are recorded in the
  [clarification log](clarifications.md). [User]
- External tenant resolution requires reachability of the provider's DNS service
  and control of the tenant's external DNS configuration. Verification preserves
  [configured-resolver behavior](https://redhat.atlassian.net/browse/OSAC-6342),
  including cache effects.

---

## Provenance

Authored: respond @ prd 0.11.5 - 7b2b8de, workspace main @ f6b842aa6
Phases: draft, revise, revise, revise, revise, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7b2b8de","source_repo":"f6b842aa6","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":28,"main_ref":"main","phases":["draft","revise","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
