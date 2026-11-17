# Managed DNS: current answers and open decisions

Updated: 2026-11-16. This companion records the current requirements discussion
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

The provider can configure integration with supported existing DNS without a
Route 53 dependency or changes to its ownership or unrelated configuration.
If the Red Hat External DNS Operator is selected,
retain the requested choice of a compatible existing installation or OSAC-managed
installation, following the
[existing operator convention](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands).
Install/reuse mechanics are design work, and this conditional request does not
select the operator or settle D1/D13. [User]

### IPv4 boundary and Feature alignment

The current Feature description and proposed initial VM path both specify
supported IPv4 addresses and exclude initial IPv6, AAAA, and dual-stack support.
D5 retains the review reference for alignment with
[IPv6 parity](https://redhat.atlassian.net/browse/OSAC-5077). Automatic IPv6
publication requires a supported VM IPv6 endpoint and address-feedback path;
generic DNS record capability alone is insufficient. [User]

### VM lifecycle and operational visibility

The current Feature requires records to follow supported VM address changes
and be removed on VM deletion. Cloud Infrastructure Admins with permission to
monitor DNS can observe publication success, pending work, failures, and retry
state without inspecting implementation internals. D7 retains the choice of
surfaces; D4/D9 retain the remaining publication policy, lifecycle, outage,
cleanup, and operating-target decisions.

### CaaS coordination

CaaS DNS publishes records for cluster API and application endpoints. It does
not provide automatic assignment and lifecycle management of DNS names for
individual VMs. [User]

CaaS/DNS maintainers participate before the VM approach is selected. Its existing
backend is configurable. Preserve CaaS endpoint names and agreed resolution,
readiness, and cleanup behavior. Design evaluates compatibility and reuse;
any later adoption of a new integration for CaaS requires an explicit provider
choice. D8's configuration experience remains open; a common backend or CaaS
migration is not selected. [User]

[OSAC-2281](https://redhat.atlassian.net/browse/OSAC-2281) covers local BIND support
for CaaS endpoint DNS, including tenant resolution. The
[coordination comment](https://redhat.atlassian.net/browse/OSAC-2281?focusedCommentId=19587688)
proposes independent delivery and asks for confirmation of its abstraction and
configuration scope. It is related work, not a dependency selected for this VM
delivery. Its scope confirmation remains with the networking working group.

### Requested technology constraint

The current Feature calls for a supported OpenShift External DNS Operator and
operand integration where their supported capabilities meet deployment needs.
It does not select an exclusive implementation. D13 retains the question of
which integration behavior must be preserved and whether alternative or
coexisting paths are acceptable. The requested path is not waived; its actual
support remains D10. Operator and operand versions are distinct, and a version
clarification does not establish VM-workflow support.
Source comments:
[19193410](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19193410),
[19201459](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19201459).

## Open decisions

The linked discussions remain the places to agree answers. Stable decision
references and discussion links are preserved; factual source corrections do
not resolve review threads or establish stakeholder consensus. D3 and D12 are
settled above, and D10 is technical qualification in the design handoff.
Requirements approval still needs the applicable product decisions below.

| Reference | Status | Decision or recorded boundary | Discussion |
|-----------|--------|-------------------------------|------------|
| D1 | Decision pending | Feature owner and reviewers confirm the recorded VMaaS-first delivery boundary, any further split, and how broader service coverage is tracked. | [Delivery scope](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189800) |
| D2 | Exclusion recorded; extension pending | The recorded Feature excludes automatic adoption of existing VMs. Feature owner and customer liaison confirm any proposed addition, including ownership, stopped-VM lifecycle, and cleanup. | [Adoption](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189824) |
| D4 | Decision pending | Feature owner and networking/security owners confirm publication defaults, intended DNS clients, and resolution paths across tenants and applicable networks. Per-VirtualNetwork query isolation is outside the recorded Feature boundary; an extension needs explicit agreement. | [Publication](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189834), [visibility](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189848) |
| D5 | Constraint recorded; review reference | The current Feature explicitly excludes initial IPv6/AAAA support. This reference retains the IPv4 review discussion and alignment with separate IPv6 work. | [IPv4/AAAA alignment](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189814) |
| D6 | Decision pending | Feature owner and provider/tenant representatives confirm initial namespace assignment and who assigns or approves it. Separate zones per tenant and tenant-controlled delegation are not assumed initial requirements. | [Tenant namespaces](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189856) |
| D7 | Decision pending | Feature owner and affected personas confirm required API, CLI, and UI surfaces plus setup, use, and troubleshooting documentation. | [User workflows](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189866) |
| D8 | Decision pending | Feature owner, provider representatives, and CaaS/DNS maintainers confirm the initial provider configuration experience. Common versus service-specific configuration remains open; preserve CaaS behavior and explicit provider choice for any later adoption. | [Provider experience](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460202946) |
| D9 | Decision pending | Feature owner, networking owners, and affected personas agree lifecycle/configuration outcomes, whether deletion waits for DNS cleanup, and supported cache/address-reuse expectations. | [Lifecycle and deletion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189875) |
| D9 | Decision pending | Feature owner and Cloud Infrastructure Admin agree tenant/VM/zone/record volumes, change rates, publication/removal/recovery objectives, and resolver/cache expectations. | [Operating targets](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189887) |
| D11 | Decision pending | Feature owner, customer liaison, and product owners confirm the required maintenance horizon, supported versions, and update or VM-workflow commitments beyond documented policy. | [Support expectations](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189901) |
| D13 | Decision pending | Feature owner and customer liaison confirm the requested supported ExternalDNS integration behavior and acceptable alternative or coexisting paths. The current Feature does not require an exclusive engine. | [Technology constraint](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460199837) |

The current [Feature description](https://redhat.atlassian.net/browse/OSAC-6156)
records VMaaS-first and IPv4; it excludes BMaaS, CaaS endpoint, and MaaS hostname
integration from this delivery. It also excludes automatic existing-VM adoption
until explicitly agreed, and per-VirtualNetwork DNS query isolation. D1 tracks
agreement on the delivery boundary and its relationship to broader OSAC DNS
coverage. The source update is not evidence of reviewer consensus.

The [scope review](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4465118321)
also proposes a smaller path using one provider-supplied zone and new VMs.
The exact initial zone/namespace arrangement remains D6. Publication policy,
resolution from tenant networks, and configuration outcomes remain under review.

Publication policy, DNS query visibility, and VM reachability are distinct.
No universal cross-tenant lookup denial is selected, and per-VirtualNetwork
query isolation is outside the recorded Feature boundary. D4 acceptance must
cover overlapping addresses and resolution from intended networks, including
allowed/denied lookups under any access policy actually agreed.

## Candidate outcomes awaiting agreement

### Adoption, namespaces, and surfaces: D2/D6/D7

- If D2 explicitly adds existing-VM adoption, VMs in configured tenant namespaces
  receive names, including stopped VMs. Only permitted addresses still assigned
  to the VM are published; otherwise users see the assigned name with publication
  pending. Conflicts are reported without changing records owned by others.
  This candidate is not part of the current recorded Feature boundary.
- The provider assigns or approves each tenant's DNS namespace. Login/email
  domains do not establish DNS authority. The permitted namespace arrangements
  remain D6. A shared provider zone with distinct tenant namespaces is an initial
  option; a separate zone per tenant is not required by this draft. [User]
- Providers configure zones and policy; tenants discover FQDNs and DNS status
  through existing VM API, CLI, and UI details, with setup/use/troubleshooting
  documentation. Tenant Admins see the assigned domain and provider setup
  information needed for resolution from the intended networks. [Clarify: R16.Q1]

### VM lifecycle: D9

- A VM keeps its name and resolution across stop, restart, and migration while
  it retains its published address. Reporting and allocation-validation details
  belong in design.
- Users see a DNS problem when a suitable address is unavailable rather than an
  answer pointing at an uncertain target.
- External records follow successful ExternalIP attachment, detachment, and
  replacement; unaffected internal records remain.
- DNS outages leave otherwise ready VMs usable by address. Users see publication
  pending or failed, with retry after recovery.
- On VM deletion, cleanup remains visible as pending or failed until complete.
  Whether VM deletion waits for cleanup remains open.
  D9 must bound removal, caching, and stale-address safety expectations; record
  removal does not flush client caches or promise instant global disappearance.

### DNS configuration changes: D4/D6/D9

| Change | Proposed user-visible outcome |
|--------|-------------------------------|
| Assign an initial namespace and enable managed DNS | Eligible VMs receive names and publication status; existing-VM adoption requires explicit agreement under D2. |
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

- **Publication and resolution:** qualify the record source/publisher,
  authoritative DNS service, and resolution from intended client networks
  separately. BIND can serve VM or bare-metal address records; a Kubernetes-based
  publisher still needs a supported resource adapter. Neither workload location
  nor DNS server choice alone selects an OSAC integration. A successful record
  write does not establish tenant resolution or workload reachability.
- **Future multi-VPC compatibility:** consider whether one hub can publish into
  multiple tenant/provider VPC DNS scopes, including private-zone associations.
  [Earlier Feature comments](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19168631)
  [raise this as possible follow-on work](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19168710)
  to consider during design. This is future design
  context, not an initial delivery requirement. It does not reopen the current
  exclusion of per-VirtualNetwork query isolation or require separate tenant
  zones.
- **D10, supported VM publication:**
  [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159) qualifies the actual
  platform/product/provider path and observable publication/error feedback.
  [RFE-7197](https://redhat.atlassian.net/browse/RFE-7197) is Closed / Won't Do;
  delivery cannot depend on reopening it. Documented Service/Route support and
  upstream VM adapter experiments do not prove a supported Red Hat VM path.
  [Product documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking_operators/external-dns-operator-1),
  [lifecycle policy](https://access.redhat.com/support/policy/updates/openshift_operators).
- **Existing DNS integration:** evaluate the
  [configurable CaaS backend](https://github.com/osac-project/osac/blob/032e75eadb2524eeafce03ef8c1f97eda70feefa/osac-installer/docs/dns-backend.md)
  and [OSAC-1050](https://redhat.atlassian.net/browse/OSAC-1050), whose abstraction
  anticipates reuse but excludes delivered VMaaS/BMaaS integration. Coordinate
  with [CaaS's accepted DNS contract](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1436-caas-networking/design.md#endpoint-feedback-and-dns)
  and [OSAC-6811](https://redhat.atlassian.net/browse/OSAC-6811),
  [OSAC-6822](https://redhat.atlassian.net/browse/OSAC-6822), and
  [OSAC-6828](https://redhat.atlassian.net/browse/OSAC-6828).
- **Local BIND candidate:** the
  [draft RFC2136 backend](https://github.com/mlorenzofr/osac/commit/1f81bd02ac01de46bc118f0810341dc02fa5d325)
  extends the existing CaaS record-writing interface. Its local fake-server
  checks and reported staging results do not qualify a supported VM workflow;
  real BIND and deployed lifecycle/resolution evidence still need verification.
  Evaluate ownership, conflicts, and safe cleanup before sharing records or
  handing them between publishers. Upstream
  [ExternalDNS RFC2136 support](https://kubernetes-sigs.github.io/external-dns/v0.14.2/tutorials/rfc2136/)
  is separate evidence from support through Red Hat's Operator. Local DNS does
  not itself expand OSAC's deployment support boundary (D12).
- **Networking boundary:**
  [manager contract section 4.8](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#48-addressing)
  does not require Fabric Managers to supply per-VirtualNetwork DNS. Publishing
  distinct VM names into provider DNS does not inherently add that manager duty.
  The [unified networking non-goals](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-unified-networking/design.md#non-goals)
  exclude tenant zones from that networking increment. If D4/D6 require new
  resolver, visibility, or network behavior, name the contract extension and
  obtain networking/DNS-owner agreement. Existing shared DNS paths are not
  evidence of per-network query isolation; distinct names with overlapping
  addresses do not alone require different answers to the same name.
- **Lifecycle and cleanup:** reassess
  [current VM external-address feedback](https://github.com/osac-project/osac/pull/2377)
  and qualify stable allocation evidence for stopped VMs,
  record ownership, and complete generated data/ownership names. Evaluate the
  earlier address-release-hold proposal with networking owners against
  [ordering section 4.7](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership);
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
