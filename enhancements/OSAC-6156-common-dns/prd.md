# Common DNS for OSAC resources, starting with VM hostnames

| Field | Value |
|---|---|
| Author(s) | Tommy Hughes |
| Jira | [OSAC-6156 · DNS for OSAC resources](https://redhat.atlassian.net/browse/OSAC-6156) |
| Feature milestone | 0.5 |
| Date | 2026-11-24 |

## Problem Statement

A tenant can provision a VM and see its IP address today. To use a hostname in
a script or inventory, someone must create a DNS record, update it when the
address changes and remove it when the VM is deleted. OSAC already publishes
cluster API and ingress names through a configurable CaaS backend. The goal
across services is a common way to name resources, publish and remove their
records in provider DNS, and let tenant workloads resolve those names. The
first delivery applies this model to VMs. [Existing CaaS DNS](https://github.com/osac-project/osac/blob/22cb2778cb6776999a011df548b6d2daed8493fe/osac-installer/docs/dns-backend.md)

## In Scope

- **Tenant enablement.** Internal VM naming starts off for each new tenant.
  The provider assigns the tenant a namespace in a writable private DNS zone and chooses
  when to enable naming. OSAC publishes internal VM records only in the
  designated private zone, including on retry. Enablement covers new and
  existing OSAC-managed VMs on supported tenant networks without VM recreation.
  Tenants can share a private zone. [Clarify: R1.Q2](clarifications.md#decision-d2)
- **Name and ownership.** Each enrolled VM gets a stable fully qualified domain
  name (FQDN). OSAC supports valid resource names up to 63 characters. The FQDN
  distinguishes the tenant, resource kind and full project identity, including
  default projects and nested projects with the same short name. If another
  owner already holds the record, OSAC preserves it and reports the conflict
  on the requesting VM. A delayed cleanup for a deleted VM also preserves a
  replacement VM’s record. [Clarify: R2.Q1](clarifications.md#decision-d4)
- **Internal address publication.** The VM’s A record points to its verified primary
  tenant-network IPv4 address. A VM using only the default cluster network
  when provider networking is disabled is ineligible for VM naming. For an
  enrolled VM awaiting address verification, the name is assigned and
  publication is pending, including while the VM is stopped. Once published,
  the record survives a stop or restart while the address remains assigned.
  When the address is no longer assigned to the VM, OSAC withdraws it from
  DNS. A verified replacement is published under the same name. If the VM
  reports an address that conflicts with its network assignment, publication
  status shows the discrepancy. OSAC waits for verification before publishing
  that address. Attaching, replacing or detaching an ExternalIP leaves the
  VM’s internal name and answer intact.
  [Clarify: R1.Q1](clarifications.md#decision-d1) [Clarify: R2.Q2](clarifications.md#decision-d5) [Clarify: R3.Q3](clarifications.md#decision-d11)
- **ExternalIP names.** ExternalIP naming is a separate deliverable with its
  own per-tenant setting. A provider can enable it while internal VM naming
  is off. OSAC publishes a distinct name for the allocated ExternalIP in
  the provider-designated zone. While the address remains allocated, its
  name resolves to that address even when detached. Attaching it to another
  VM keeps the same name and DNS answer. If a VM receives a different
  ExternalIP, that allocation has its own name. Releasing an allocation
  triggers withdrawal of its managed record.
  Privately routed ExternalIPs use private DNS. An internet-routable address
  gets a public name only when the provider explicitly selects a public zone.
  OSAC manages these records. Tenant Users cannot write them through OSAC.
  The provider’s DNS policy controls who can resolve the name. [Clarify: R1.Q1](clarifications.md#decision-d1)
- **Resolver access.** Every VM on a supported tenant network receives a
  working resolver, even when naming is off and the tenant has zero published
  names. Using its normal guest configuration, the VM can resolve a permitted
  OSAC name without public internet access. The Tenant Admin can find the
  assigned domain and setup instructions. Once the organization configures
  access to the provider’s private DNS, its authorized clients get the same
  primary IPv4 answer for a published VM name as permitted tenant workloads.
  Tenant namespaces prevent name collisions. The provider’s DNS policy governs
  lookups, including through shared resolvers. OSAC project permissions govern
  VM management. Where the provider configures tenant separation, a client on
  an excluded network must be unable to obtain the private answer through
  the shared resolver.
  Connecting to the address also requires the correct route and network
  permissions. [Clarify: R1.Q3](clarifications.md#decision-d3) [Clarify: R2.Q4](clarifications.md#decision-d7)
- **Disablement and deletion.** Disabling internal naming withdraws only
  that tenant’s OSAC-owned VM records. Its VMs keep their resolver. Re-enabling naming
  covers every eligible VM then present and restores surviving VMs’ names
  with their current verified addresses. Deleting a VM triggers withdrawal.
  During a DNS outage, an otherwise usable VM can become ready, and VM
  deletion can finish while DNS cleanup is still pending. [Clarify: R2.Q3](clarifications.md#decision-d6)
- **Status and recovery.** Tenants can tell from the VM UI, CLI and API when
  internal VM naming is off for their tenant. When enabled, each enrolled VM shows its
  assigned FQDN and whether publication is pending, published or failed.
  Administrators can see outstanding changes, failures and retries, including
  cleanup after the VM disappears. Status reflects what the integration can
  confirm. When DNS access returns, cleanup resumes automatically. It completes
  when the integration verifies that the deleted VM’s mapping is gone from
  authoritative DNS or that a replacement VM now owns the record. A verified
  replacement keeps its record even when its FQDN and IPv4 address are
  identical to the deleted VM’s. If ownership is unclear, OSAC preserves the
  record and shows cleanup as unconfirmed.
  Clients may still receive cached answers. [Clarify: R2.Q3](clarifications.md#decision-d6)
- **Configuration changes.** OSAC rejects a change to its DNS settings if
  applying it would prevent cleanup of records it already manages, including
  after a VM is deleted. A tenant suffix change must also preserve every
  already-assigned FQDN and keep published names resolving under the same
  access and address rules. If OSAC rejects a change, the current settings
  stay in effect. The administrator can identify the affected names or
  outstanding cleanup. [Clarify: R3.Q2](clarifications.md#decision-d10)
- **CaaS compatibility.** Enabling, disabling or retrying VM DNS preserves
  existing cluster API and ingress records, including in a shared zone. Cluster
  creation and deletion continue to follow their configured CaaS DNS behavior
  during a DNS outage. [Clarify: R3.Q4](clarifications.md#decision-d12)

The proposed spelling is `<resource-name>.<kind>.<project-label>.<tenant-suffix>`.
For example, the provider could publish these three VMs in the same zone.
Design validates the exact spelling and supported suffix lengths for both the
published name and any records the integration uses to track ownership.
[Clarify: R2.Q1](clarifications.md#decision-d4)

| Tenant | Project | VM name | Example FQDN |
|---|---|---|---|
| north | build | web | `web.vm.build.north.cloud.example` |
| north | test | web | `web.vm.test.north.cloud.example` |
| south | build | web | `web.vm.build.south.cloud.example` |

Deleting `web` in `north/build` withdraws only the first record. Project
permissions govern who can manage each VM, including when a client is
permitted to resolve names from multiple projects.

## Out of Scope

- CaaS migration to common publication, resolver delivery to bare metal, and
  names for bare-metal instances, storage and model-serving endpoints are
  separate deliverables.
- Tenant self-service for zones or records through an API or UI, per-zone
  backend selection or manual management, custom domains, automated
  delegation, domain registration and import of existing records.
  [DNSaaS requirements carried forward](https://redhat.atlassian.net/browse/OSAC-3202?focusedCommentId=19735142)
- OSAC operation of authoritative DNS servers or zones, private zones per
  VirtualNetwork, split-horizon answers, hybrid forwarding endpoints, DNS
  firewall, query logging and DNSSEC.
- IPv6 and dual-stack records, reverse DNS, secondary-interface names and DNS
  inside tenant clusters.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to assign each tenant a DNS namespace
  and enable internal VM names, ExternalIP names, or both so that I can offer
  managed names under the domains my organization operates.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to connect OSAC to our installation’s
  authoritative DNS service so that tenant VMs can use predictable names on
  the infrastructure we operate.
- As a Cloud Infrastructure Admin, I want to find unfinished DNS cleanup after
  a VM is deleted so that I can address a stale record even after the VM is
  gone from inventory.

### Tenant Admin

- As a Tenant Admin, I want the assigned domain and resolver setup instructions
  so that people on my organization’s network can look up our VMs.

### Tenant User

- As a Tenant User, I want a stable VM name for my scripts so that a change to
  its internal address does not require editing them.
- As a Tenant User, I want to look up my VM’s attached ExternalIP by name
  from my organization’s network so that I can connect without tracking
  addresses or writing DNS records.
- As a Tenant User, I want to see my VM’s DNS publication status so that I know
  whether to wait for its name or troubleshoot a connection.
- As a Tenant User, I want my VM to receive a working resolver so that my
  workloads can look up permitted names without configuring each guest.

## Dependencies

- **Provider DNS and networking.** The provider selects the integration per
  installation and supplies authoritative writable zones and resolver access.
  VM networking supplies evidence of address assignment and release. DNS
  publication and cleanup belong to the common DNS capability. The networking
  working group reviews any proposed change to which names tenant VMs can
  resolve today. [Clarify: R3.Q1](clarifications.md#decision-d9) [VM networking contract](https://github.com/osac-project/enhancement-proposals/blob/5a264f8f03d2fae2a9a677c6a19eb513f93113b0/enhancements/OSAC-1435-vmaas-networking/design.md#L384-L391)
- **First VM release.** At least one supported provider integration must
  demonstrate VM record publication, resolution and ownership-safe cleanup
  end to end. Provider-operated BIND is the first backend to qualify. This
  includes deleting a VM during a DNS outage and verifying cleanup after
  access returns. Unrelated records and CaaS endpoints must survive. If a
  replacement VM owns the same FQDN and IPv4 address, its record must keep
  resolving when the old VM’s cleanup completes. Once BIND qualifies, VM
  naming can ship.
- **Operator evaluation.** OSAC-6156 requires an evaluation of the requested
  OpenShift External DNS Operator and its ExternalDNS operand with Infoblox
  for VM naming. With only ExternalIP naming enabled, verify whether OSAC
  can publish the allocated address and withdraw only its record on release.
  From a permitted client outside the VirtualNetwork, check that the same
  name resolves to the allocated address while attached to a VM with no DNS
  access, while detached, and after attachment to another VM. Document
  verified workflows, limits and follow-up work for any gaps.
  This meets the Feature’s Operator criterion. CaaS migration remains a
  separate deliverable under the Feature.
  [Clarify: R2.Q5](clarifications.md#decision-d8)
- **Backend qualification.** The supported VM network profiles and the
  integration’s operating limits must be documented.
  Existing CaaS installations can continue using Route 53.
  [Local BIND integration](https://redhat.atlassian.net/browse/OSAC-2281)

---

## Provenance

Authored: draft @ prd 0.11.5 - ceab343, workspace prd/OSAC-6156 @ 7a1999595
Final: revise @ prd 0.11.5 - 760cf64, workspace prd/OSAC-6156 @ 7a1999595

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"760cf64","source_repo":"7a1999595","source_repo_branch":"prd/OSAC-6156","commits_behind_main":0,"commits_ahead_main":112,"main_ref":"main","phases":["draft","draft","revise","revise","revise","respond","respond","respond","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
