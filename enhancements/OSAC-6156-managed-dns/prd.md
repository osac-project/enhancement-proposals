# Managed DNS for tenant resource hostnames

| Field | Value |
|-------|-------|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) |
| PRD task | [OSAC-6158](https://redhat.atlassian.net/browse/OSAC-6158) |
| Date | 2026-11-02 |
| Target milestone | 0.5 |
| Status | Draft — delivery scope under review |

## Problem Statement

Tenant users must track VM IP addresses or maintain DNS records separately from
VM provisioning. OSAC already manages CaaS endpoint DNS through a configurable
backend, while VMaaS lacks an automatic resource-hostname workflow
([existing DNS behavior](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/osac-installer/docs/dns-backend.md)).
Providers need to integrate VM hostname management with their DNS infrastructure
so tenants can resolve VM names through their own DNS systems. Without this
capability, tenants maintain records manually, risking stale records and broken
access by hostname.

## In Scope

The VMaaS option below is subject to D1. [User]

- Automatic VM hostname record creation during provisioning and removal during
  deprovisioning, publishing A records for supported IPv4 VM addresses. Automatic
  AAAA publication requires an IPv6 endpoint supported by the offering (D5).
  [User] [Clarify: R8.Q1]
- If the External DNS Operator is selected, the Cloud Infrastructure Admin can
  reuse a compatible existing installation or have OSAC install it. Reuse
  preserves its ownership and unrelated DNS configuration
  ([existing prerequisite convention](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands)). [User]
- Provider control over publication of ExternalIP addresses, tenant-internal
  addresses, or both, with the address policy and query visibility agreed in D4.
  ExternalIP means external to a VirtualNetwork and need not be internet-routable
  ([accepted terminology](https://github.com/osac-project/enhancement-proposals/blob/a46dc709b12c9fe175bd71ae9c2a11f62c18b7eb/enhancements/OSAC-1433-unified-networking/design.md)).
- Predictable VM hostnames within provider-supplied DNS zones. VM resource names
  remain fixed after creation, and managed DNS does not reduce their existing
  allowed lengths. DNS names distinguish resources with the same name
  across tenants, projects, and resource types. Generated names must meet DNS
  and supported-product limits. Users can discover the assigned FQDN.
  Tenant-domain assignment remains D6.
  [Jira: OSAC-1061] [User]
- Automatic DNS changes for one tenant's VMs preserve other tenants' records and
  records unrelated to this workflow. Query visibility is a separate policy
  decision in D4. [User]
- External tenant DNS resolution through NS delegation of a subdomain or
  conditional forwarding to the DNS service hosting the managed records. For
  example, delegating `osac.example.com` enables resolution beneath that
  subdomain. The provider supplies authoritative DNS and writable zones as
  deployment prerequisites (D3). The applicable resolution method depends on
  the DNS service and permitted client networks; private-zone access requires
  a reachable resolution path. [User] [Clarify: R12.Q1]

## Out of Scope

- Implementation of BMaaS, CaaS, and MaaS DNS integration, including CaaS Route 53
  migration, if the VMaaS option in D1 is selected. CaaS convergence planning
  remains required under D8. [Clarify: R8.Q4]
- Tenant self-service management of arbitrary DNS records beyond automatically
  provisioned resource hostnames.
- VM console access or BMaaS IPMI/Redfish endpoint hostname exposure.
- Provisioning production authoritative DNS servers or DNS zones. The provider
  supplies the DNS service and zones for the proposed delivery. [User]
- IPv6 and dual-stack enablement; see the record-family proposal in In Scope
  and its D5 alignment decision. [User]
- DNS-based load balancing or failover.
- DNSSEC.
- Public domain registration; tenants retain responsibility for their registrars.
- OSAC in-place upgrades, which the platform does not currently support.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin with permission to configure the provider's DNS
  offering, I want to configure the DNS zones used for VM hostnames so that
  tenants can use VM hostnames without maintaining DNS records separately.
  [Clarify: R13.Q1]
- As a Cloud Provider Admin with permission to set DNS publication policy, I want
  to select the VM address ranges published in managed zones so that the DNS
  offering follows the provider's intended internal and external access scope.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin responsible for VM provisioning, I want VM
  hostname records to be created and removed automatically with their resources
  so that I avoid maintaining DNS records separately and leaving stale records
  after VM deletion. [Clarify: R13.Q1]
- As a Cloud Infrastructure Admin responsible for DNS integration, I want OSAC VM
  hostnames to resolve through my deployment's existing DNS infrastructure so
  that users can access VMs by name across the deployment. [User]
- As a Cloud Infrastructure Admin responsible for installation, I want to select
  a compatible existing or OSAC-managed External DNS Operator installation when
  that operator is selected so that VM DNS follows the deployment's operator
  ownership policy. [Clarify: R8.Q3]

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

The decisions and proposals below require agreement before PRD approval.
Supporting evidence is in the [clarification log](clarifications.md).
Design owns integration, hostname layout, limit validation, and deployment
qualification under D10, subject to D13's confirmed technology constraints.
[Clarify: R8.Q1] [Clarify: R12.Q1]

- **D1 — Delivery boundary:** confirm VMaaS-first or broader Feature coverage.
  The [Feature comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19101116)
  proposes VMaaS-first. The Feature owner records any agreed phase split in
  Jira; completing this PRD does not satisfy the whole Feature checklist. [User]
- **D5 — IPv6 alignment:** the Feature owner must reconcile the AAAA checklist
  with the proposal in In Scope and separate
  [IPv6 parity work](https://redhat.atlassian.net/browse/OSAC-5077). [User]

| Reference | Proposal or remaining decision | Reviewers |
|-----------|--------------------------------|-----------|
| D13 | Confirm whether the requested Red Hat External DNS Operator is mandatory or another solution can meet the need, and which existing integration or behavior must be preserved. [Clarify: R8.Q1] | Feature owner and customer liaison |
| D2 | Review the adoption proposal below, including stopped VMs, unverified addresses, conflicts, and rollout expectations. [Clarify: R13.Q1] | Feature owner and customer liaison |
| D4 | Confirm publication defaults and permitted clients across tenants, VirtualNetworks, and applicable provider VPCs. Verify overlapping addresses and allowed/denied lookups under that policy; universal cross-tenant lookup denial is not assumed. | Feature owner and networking/security owners |
| D6 | Proposed: the provider assigns or approves each tenant's DNS namespace. Confirm provider-assigned subdomains, tenant-controlled delegated subdomains, or both. Login/email domains do not establish DNS authority. [Clarify: R12.Q1] | Feature owner, Cloud Provider Admin, and Tenant Admin representative |
| D7 | Proposed: providers configure zones/policy; tenants discover FQDNs and pending/success/failure through existing VM API, CLI, and UI details. Document setup, use, and troubleshooting. Confirm the required surfaces. [Clarify: R12.Q1] | Feature owner and affected persona representatives |
| D8 | Confirm common versus service-specific DNS configuration experience for VMaaS/CaaS. [Clarify: R9.Q1] | Feature owner, provider representatives, and CaaS/DNS maintainers |
| Behavioral part of D9 | Review the lifecycle proposals below; confirm whether VM deletion waits for DNS cleanup. [Clarify: R12.Q1] | Feature owner, networking owners, and affected persona representatives |
| Quantitative part of D9 | Confirm tenant/VM/record volumes, churn, publication/removal and recovery objectives, and resolver/cache expectations. Measure authoritative and recursive visibility separately; defaults, quotas, and lab timings are not service commitments. | Feature owner and Cloud Infrastructure Admin |
| D11 | Confirm the required maintenance horizon and version/update commitments beyond documented policy. Seek product confirmation for deployment or VM-workflow support that published documentation does not answer. [Clarify: R12.Q1] | Feature owner, customer liaison, and relevant product owners |

Adoption proposal for review (D2):

Existing VMs of tenants covered by the provider's managed DNS configuration and
assigned a DNS namespace receive names, including stopped VMs. Records publish
only verified addresses allocated to that VM and permitted by publication policy.
A stopped VM with a verified retained allocation can therefore receive a record.
Until an address can be verified, the assigned name is visible with publication
pending. Existing record conflicts are reported without changing records owned
by others. [Clarify: R13.Q1]

Lifecycle proposals for review (D9):

- A VM keeps its assigned name across stop, restart, and migration. Its record
  remains while the published address is still valid and allocated to it;
  temporarily missing reported addresses do not by themselves remove the record.
- Records follow confirmed address changes. An uncertain address is reported
  as a DNS problem rather than silently published as a new target.
- An external record is published after ExternalIP attachment succeeds and is
  withdrawn on detachment or replacement. Unaffected internal records remain.
- DNS outages do not make an otherwise ready VM unready or prevent its use by
  address. Users see publication pending or failed, and changes retry after
  recovery.
- DNS cleanup remains pending until removal of the owned record is confirmed
  by the authoritative service. Affected addresses are held from reuse until
  that confirmation; whether VM deletion itself waits remains open. Cached
  answers may persist afterward, so the agreed address-reuse policy must also
  account for supported resolver/cache behavior. [Clarify: R12.Q1]

For the ExternalDNS evaluation, Red Hat currently lists Operator 1.3 full
support through 2027-02-28 and maintenance through 2027-06-30; its release
cadence is unspecified. The offering's required support horizon remains D11.
[Published lifecycle policy](https://access.redhat.com/support/policy/updates/openshift_operators).

External dependencies:

- **D8 — CaaS alignment:** design evaluates integration with existing CaaS DNS in
  consultation with CaaS/DNS maintainers before choosing the VMaaS approach. It
  addresses convergence and any transition involved, preserving CaaS endpoint
  names and agreed readiness/cleanup requirements. Implementation timing remains
  subject to D1. [Clarify: R8.Q4] [Clarify: R12.Q1]
- **D10 — Supported integration:** automatic VM records must use an integration
  supported for the deployment. An ExternalDNS approach must not depend on
  [RFE-7197](https://redhat.atlassian.net/browse/RFE-7197), which is
  **Closed / Won't Do**. Qualification evidence and coordination context for
  [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) are recorded in the
  [clarification log](clarifications.md). Qualification demonstrates actual VM
  record publication and observable failures; availability of the publishing
  component alone does not establish successful publication. [User]
  [Clarify: R12.Q1]
- External tenant resolution requires reachability of the provider's DNS service
  and control of the tenant's external DNS configuration. Verification preserves
  [configured-resolver behavior](https://redhat.atlassian.net/browse/OSAC-6342),
  including cache effects.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ f6b842aa6
Final: revise @ prd 0.11.5 - b369da0, workspace main @ 9ddd24e49

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"b369da0","source_repo":"9ddd24e49","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":76,"main_ref":"main","phases":["draft","revise","revise","revise","revise","respond","respond","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
