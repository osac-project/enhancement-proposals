# Managed DNS: current answers and open decisions

Updated: 2026-11-09. This companion records the current requirements discussion
for [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) and
[PR 445](https://github.com/osac-project/enhancement-proposals/pull/445).
The PR remains draft until scope and requirements are agreed. Proposed outcomes
below are not stakeholder approval or changes to Jira.

## R16.Q1: Current answers

### DNS prerequisites

#### Decision (D3)

The provider supplies authoritative DNS and writable zones. Production DNS
server and zone provisioning are separate capabilities; test fixtures do not
make them part of this delivery. [User]

### Deployment boundary

#### Decision (D12)

Managed DNS follows OSAC's supported deployment modes. Expanding platform
support to additional deployment modes is separate work. The
[accepted networking boundary](https://github.com/osac-project/enhancement-proposals/blob/99692be29d74b9e30a25a64542ddc07eeca6ed09/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary)
currently supports connected deployments only. This acknowledges the existing
platform limitation without making connected-only a permanent DNS requirement.
Design qualifies candidate DNS integrations within that platform boundary;
selecting a DNS provider does not itself establish support for additional
deployment modes. [User]

The [deployment discussion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4471110654)
remains open. This clarification does not record reviewer consensus or expand
this feature into disconnected platform enablement.

### Naming and ownership

Preserve immutable OSAC resource names and their existing allowed lengths.
Hostnames distinguish tenant, project, and resource-type scopes; users can
discover their assigned FQDN and publication status. Changes preserve other
tenants' records and records unrelated to this workflow. Exact name layout and
complete data/ownership-name validation belong in design.
[OSAC-1061](https://redhat.atlassian.net/browse/OSAC-1061). [User]

The provider can integrate supported existing DNS without changing its ownership
or unrelated configuration. If the Red Hat External DNS Operator is selected,
retain the requested choice of a compatible existing installation or OSAC-managed
installation, following the
[existing operator convention](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands).
Install/reuse mechanics are design work, and this conditional request does not
select the operator or settle D1/D13. [User]

### IPv4 boundary and Feature alignment

The proposed initial VM path resolves hostnames to supported IPv4 addresses.
IPv6 and dual-stack enablement remain separate work. D5 requires the Feature
owner to reconcile its AAAA checklist with that boundary and
[IPv6 parity](https://redhat.atlassian.net/browse/OSAC-5077). Automatic IPv6
publication requires a supported VM IPv6 endpoint and address-feedback path;
generic DNS record capability alone is insufficient. [User]

### CaaS coordination

CaaS/DNS maintainers participate before the VM approach is selected. The existing
backend is configurable, not hardwired to Route 53. Design evaluates reuse and
convergence while preserving CaaS endpoint names and agreed readiness/cleanup
requirements. D8's configuration-experience choice and D1's implementation
timing remain open; no common backend or migration schedule is selected. [User]

### Requested technology constraint

The Feature requests the Red Hat External DNS Operator; whether it is mandatory
or another solution can meet the need remains D13. The request is not waived,
and alternatives remain for design evaluation. Operator and operand versions
are distinct; a version clarification does not establish VM-workflow support.
Source comments:
[19193410](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19193410),
[19201459](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19201459).

## Open decisions

The linked discussions are the places to agree answers. These references retain
their current meanings; D3 and D12 are settled above, and D10 is technical
qualification in the design handoff. Requirements approval still needs the
applicable product decisions below.

| Reference | Remaining decision | Discussion |
|-----------|--------------------|------------|
| D1 | Feature owner confirms VMaaS-first, broader coverage, or a smaller initial delivery and records any agreed phase split in Jira. | [Delivery scope](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189800) |
| D2 | Feature owner and customer liaison confirm whether existing VMs are adopted, including stopped VMs, or only new VMs receive names initially. | [Adoption](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189824) |
| D4 | Feature owner and networking/security owners confirm publication defaults and permitted DNS clients across tenants, VirtualNetworks, and applicable provider VPCs. | [Publication](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189834), [visibility](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189848) |
| D5 | Feature owner reconciles the AAAA checklist with the initial IPv4 boundary and separate IPv6 work. | [IPv4/AAAA alignment](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189814) |
| D6 | Feature owner and provider/tenant representatives confirm provider-assigned subdomains, tenant-controlled delegated subdomains, or both, and who assigns or approves them. | [Tenant namespaces](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189856) |
| D7 | Feature owner and affected personas confirm required API, CLI, and UI surfaces plus setup, use, and troubleshooting documentation. | [User workflows](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189866) |
| D8 | Feature owner, provider representatives, and CaaS/DNS maintainers confirm common versus service-specific DNS configuration for VMaaS/CaaS. | [Provider experience](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460202946) |
| D9 | Feature owner, networking owners, and affected personas agree lifecycle/configuration outcomes, whether deletion waits for DNS cleanup, and supported cache/address-reuse expectations. | [Lifecycle and deletion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189875) |
| D9 | Feature owner and Cloud Infrastructure Admin agree tenant/VM/zone/record volumes, change rates, publication/removal/recovery objectives, and resolver/cache expectations. | [Operating targets](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189887) |
| D11 | Feature owner, customer liaison, and product owners confirm the required maintenance horizon, supported versions, and update or VM-workflow commitments beyond documented policy. | [Support expectations](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189901) |
| D13 | Feature owner and customer liaison confirm whether the named operator is mandatory and which integration or behavior must be preserved. | [Technology constraint](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460199837) |

The [Feature comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19101116)
proposes VMaaS-first; the Feature description still covers VMaaS, BMaaS, CaaS,
MaaS, and CaaS DNS integration. The
[latest scope review](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4465118321)
proposes a smaller path: one provider-supplied zone, predictable names for new
VMs, publication status, and removal on deletion. Neither proposal establishes
an agreed phase split. Internal publication, external tenant resolution, adoption,
and configuration changes are not silently deferred by this editorial revision.

Publication policy, DNS query visibility, and VM reachability are distinct.
No universal cross-tenant lookup denial or per-VirtualNetwork query isolation is
selected. D4 acceptance must cover overlapping addresses and allowed/denied
lookups under the policy actually agreed.

## Candidate outcomes awaiting agreement

### Adoption, namespaces, and surfaces: D2/D6/D7

- Existing VMs in configured tenant namespaces receive names, including stopped
  VMs. Only permitted addresses still assigned to the VM are published; otherwise
  users see the assigned name with publication pending. Conflicts are reported
  without changing records owned by others.
- The provider assigns or approves each tenant's DNS namespace. Login/email
  domains do not establish DNS authority. The permitted namespace arrangements
  remain D6.
- Providers configure zones and policy; tenants discover FQDNs and DNS status
  through existing VM API, CLI, and UI details, with setup/use/troubleshooting
  documentation. When external tenant resolution is included, Tenant Admins see
  the assigned domain and provider setup information.

### VM lifecycle: D9

- A VM keeps its name and resolution across stop, restart, and migration while
  it retains its published address. Reporting and allocation-validation details
  belong in design.
- Records follow address changes. Users see a DNS problem when a suitable
  address is unavailable rather than an answer pointing at an uncertain target.
- External records follow successful ExternalIP attachment, detachment, and
  replacement; unaffected internal records remain.
- DNS outages leave otherwise ready VMs usable by address. Users see publication
  pending or failed, with retry after recovery.
- Owned records are withdrawn on VM deletion. Cleanup remains visible as pending
  or failed until complete. Whether VM deletion waits for cleanup remains open.
  D9 must bound removal, caching, and stale-address safety expectations; record
  removal does not flush client caches or promise instant global disappearance.

### DNS configuration changes: D4/D6/D9

| Change | Proposed user-visible outcome |
|--------|-------------------------------|
| Assign an initial namespace and enable managed DNS | Existing VMs receive names and publication status under D2. |
| Change address publication policy | Answers include newly permitted addresses and withdraw addresses no longer permitted. |
| Disable managed DNS | Owned records are removed; users see cleanup pending or failed until removal is confirmed, then DNS disabled. |
| Replace an assigned tenant domain/subdomain | Reject while that tenant has VMs or its owned DNS cleanup is incomplete, including pending or failed cleanup. Preserve existing configuration, names, and records on rejection. |

These proposals preserve unrelated records and follow the agreed outage and
cache expectations. The replacement restriction does not prohibit initial
namespace assignment and does not decide whether VM deletion waits for cleanup.
The [configuration discussion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4457237603)
and [cleanup correction](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4459676431)
record the review trail; their resolution did not approve the broader proposals.

## Design handoff

- **D10, supported VM publication:**
  [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) qualifies the actual
  platform/product/provider path and observable publication/error feedback.
  [RFE-7197](https://redhat.atlassian.net/browse/RFE-7197) is Closed / Won't Do;
  delivery cannot depend on reopening it. Documented Service/Route support and
  upstream VM adapter experiments do not prove a supported Red Hat VM path.
  [Product documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking_operators/external-dns-operator-1),
  [lifecycle policy](https://access.redhat.com/support/policy/updates/openshift_operators).
- **Existing DNS integration:** evaluate the
  [configurable CaaS backend](https://github.com/osac-project/osac/blob/c8d3165d6a371915bc13a976c66f805d96808472/osac-installer/docs/dns-backend.md)
  and [OSAC-1050](https://redhat.atlassian.net/browse/OSAC-1050), whose abstraction
  anticipates reuse but excludes delivered VMaaS/BMaaS integration. Coordinate
  with [CaaS's accepted DNS contract](https://github.com/osac-project/enhancement-proposals/blob/19a633e230b6691741f785da72d9b1eae6c75be0/enhancements/OSAC-1436-caas-networking/design.md#endpoint-feedback-and-dns)
  and [OSAC-6811](https://redhat.atlassian.net/browse/OSAC-6811),
  [OSAC-6822](https://redhat.atlassian.net/browse/OSAC-6822), and
  [OSAC-6828](https://redhat.atlassian.net/browse/OSAC-6828).
- **Networking boundary:**
  [manager contract section 4.8](https://github.com/osac-project/enhancement-proposals/blob/19a633e230b6691741f785da72d9b1eae6c75be0/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#48-addressing)
  does not require Fabric Managers to supply per-VirtualNetwork DNS. Publishing
  distinct VM names into provider DNS does not inherently add that manager duty.
  The [unified networking non-goals](https://github.com/osac-project/enhancement-proposals/blob/19a633e230b6691741f785da72d9b1eae6c75be0/enhancements/OSAC-1433-unified-networking/design.md#non-goals)
  exclude tenant zones from that networking increment. If D4/D6 require new
  resolver, visibility, or network behavior, name the contract extension and
  obtain networking/DNS-owner agreement. Existing shared DNS paths are not
  evidence of per-network query isolation; distinct names with overlapping
  addresses do not alone require different answers to the same name.
- **Lifecycle and cleanup:** qualify stable allocation evidence for stopped VMs,
  record ownership, and complete generated data/ownership names. Evaluate the
  earlier address-release-hold proposal with networking owners against
  [ordering section 4.7](https://github.com/osac-project/enhancement-proposals/blob/19a633e230b6691741f785da72d9b1eae6c75be0/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership);
  its mechanism is not a selected contract extension. D9 must define the required
  protection and cache boundary. [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308.html#section-5)
  and [RFC 8767](https://www.rfc-editor.org/rfc/rfc8767.html) explain negative
  caching and stale answers. Measure authoritative and recursive visibility
  separately, preserving [configured resolver behavior](https://redhat.atlassian.net/browse/OSAC-6342).
- **Qualification:** demonstrate the agreed lifecycle, visibility, conflict,
  isolation, failure, maximum-name-length, and scale outcomes through supported
  DNS and client paths. A running publisher does not confirm individual records;
  lab timings, defaults, and quotas do not establish service commitments.

Broader [DNSaaS](https://redhat.atlassian.net/browse/OSAC-3202),
[local DNS](https://redhat.atlassian.net/browse/OSAC-2127), and
[BIND integration](https://redhat.atlassian.net/browse/OSAC-2281) remain coordination
references, not prerequisites. Detailed historical research is retained in the
author's working artifacts; this companion states the current review position.
