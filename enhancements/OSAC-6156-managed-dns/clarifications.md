# Managed DNS: current answers and open decisions

Updated: 2026-11-18. This companion records the current requirements discussion
for [OSAC-6156](https://redhat.atlassian.net/browse/OSAC-6156) and
[PR 445](https://github.com/osac-project/enhancement-proposals/pull/445).
The PR is open for review; scope and requirements still need reviewer agreement.
Recorded author decisions and remaining proposals do not establish reviewer
consensus or changes to Jira.

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
Install/reuse mechanics are design work; this conditional request does not select
an exclusive implementation. [User]

### Tenant namespaces: D6

The provider assigns tenant namespaces within supported provider-supplied
writable zones. A shared provider zone can contain distinct tenant namespaces;
separate zones per tenant are not required. Exact name layout belongs in design.
Tenant self-service custom-domain onboarding, authority verification, and
delegation automation are outside this delivery. An already delegated,
provider-operable zone can be evaluated as supplied DNS infrastructure; this
does not establish support for every provider or zone arrangement. [User]

### Delivery scope and IPv4 boundary

The current Feature records VMaaS-first and excludes initial BMaaS, CaaS endpoint,
and MaaS hostname integration. D1 and D5 retain that service and IPv4 boundary.
On 2026-11-18, the author explicitly revised D2 to include existing VMs under
the enablement rule below. This supersedes the earlier author adoption
exclusion and proposes an extension to the recorded Feature boundary. Feature
owner and reviewer agreement is still required; Jira has not been changed.
[User]

The current Feature description and proposed initial VM path both specify
supported IPv4 addresses and exclude initial IPv6, AAAA, and dual-stack support.
D5 retains the review reference for alignment with
[IPv6 parity](https://redhat.atlassian.net/browse/OSAC-5077). Automatic IPv6
publication requires a supported VM IPv6 endpoint and address-feedback path;
generic DNS record capability alone is insufficient. [User]

### Existing VM coverage: D2

Enabling or re-enabling managed DNS for a tenant covers all supported
OSAC-managed VMs belonging to that tenant, including existing VMs and VMs
created while DNS was disabled. Previously assigned names stay the same; other
VMs receive managed names. Only verified assigned addresses permitted by the
selected publication policy are published. A missing verified address leaves
publication pending, including for stopped VMs, rather than publishing an
uncertain target. [User]

This assigns OSAC-managed names to VMs; it does not migrate manually managed
names or take ownership of records managed outside this workflow. Conflicts
remain visible without overwriting records owned by others. VM creation history
alone does not exclude a supported VM in the enabled tenant. [User]

The [earlier adoption discussion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189824)
was closed against the recorded Feature exclusion. Its historical closure does
not approve this scope extension or establish reviewer consensus.

### VM lifecycle and operational visibility: D7/D9

The current Feature requires records to follow supported VM address changes
and be removed on VM deletion. Cloud Infrastructure Admins with permission to
monitor DNS can observe publication success, pending work, failures, and retry
state without inspecting implementation internals.

VM FQDNs and publication status are available through the API, CLI, and existing
VM details UI. Documentation covers provider setup, tenant resolution setup,
use, and troubleshooting. Fields, commands, and screen design belong in design.
[User]

DNS outages do not block otherwise usable VMs. VM deletion does not wait for DNS
cleanup. Administrators can inspect pending or failed DNS cleanup and its retry
status through supported operational interfaces until cleanup completes,
including after the VM has been deleted. The post-deletion operational interface
and durable tracking mechanism belong in design; the VM details page is not
required to remain available after deletion. [User]

While managed DNS is enabled, a VM keeps its name and records across stop,
restart, and migration while its published addresses remain assigned. Records
follow supported address changes under the selected publication policy,
including ExternalIP attachment,
detachment, and replacement; unaffected records remain. An unavailable suitable
address is shown as pending or a DNS problem rather than publishing an uncertain
target. Design qualifies retained-address evidence separately from runtime IP
reporting. [User]

Replacement of an assigned tenant domain/subdomain is rejected while that tenant
has VMs or its owned DNS cleanup is incomplete, including pending or failed
cleanup. Rejection preserves existing configuration, names, and records. Initial
namespace assignment is permitted. This guard does not delay VM deletion. [User]

OSAC coordinates withdrawal through the configured integration and preserves
cleanup capability until the managed records are removed. Publication and
cleanup status report what supported feedback or verification can establish;
accepted requests and a healthy publisher do not alone establish completion.
Pending, failed, or unknown outcomes remain visible, including after VM deletion.
Record mutations can be delegated without giving up cleanup tracking or
preservation of unrelated records. Exact confirmation and retry mechanisms
belong in design. [User]

Provider propagation and resolver/client caches limit when earlier answers stop
being used. Record removal does not guarantee immediate cache eviction or prevent
an old answer from reaching a reassigned address. This PRD does not require IP
quarantine or a universal stale-answer prevention guarantee. Design documents the
risk and evaluates mitigations within the accepted networking contract; stronger
protections need explicit agreement. This boundary is recorded, rather than left
as a mandatory product decision. [User]

Changes to DNS provider, zone, or namespace settings are rejected if they would
leave managed records or unfinished cleanup without a supported cleanup path.
Rejection preserves existing configuration and records. Safe credential repair
or rotation remains possible; this guard does not select an in-place provider
migration feature. [User]

### Live configuration: D4/D9

Authorized provider administrators configure managed DNS enablement and
address-publication policy per tenant. Each setting applies to all supported
OSAC-managed VMs belonging to that tenant. Changes preserve other tenants'
configuration and records, including when tenants share provider-supplied DNS
infrastructure. This administrative scope was clarified by the user on
2026-11-18. It does not add tenant self-service DNS controls. [User]

Providers can change a tenant's address-publication policy for its existing
managed VMs between tenant-internal addresses, ExternalIP addresses, or both.
Assigned hostnames stay stable while records converge to newly permitted
addresses and withdraw addresses no longer permitted. Pending changes and
failures remain visible. The DNS change does not require VM stop, restart, or
recreation. [User]

Managed DNS has one enable/disable behavior per tenant for this delivery.
Disabling stops new hostname publication for that tenant and withdraws its
affected OSAC-owned records through the configured integration. Unfinished
withdrawal remains visible until cleanup completes, including for VMs deleted
in the meantime. Tenants lose the managed lookups as withdrawal propagates,
subject to documented cache limits. The provider's DNS service and unrelated
records are preserved. [User]

Re-enabling resumes normal management for all supported OSAC-managed VMs in
that tenant using current eligible addresses. Previously assigned names are
preserved; other VMs receive managed names under D2. VM operation and deletion
do not wait for these DNS operations. Ownership and conflict protections still
apply. Separate controls to pause new hostname assignment or retain managed
records on disablement are outside this delivery. [User]

These are recorded author answers, approved on 2026-11-18, and remain subject
to reviewer confirmation. They answer the two scope questions in the
[lifecycle discussion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4603176590).
Design qualifies the supported transitions, recovery, and observable outcomes;
no particular control layout or implementation is selected here.

### Operating qualification: D9

Design qualifies and documents supported tenant/VM/zone/record volumes, change
rates, and measured publication, removal, recovery, and resolver/cache behavior.
The reviewed requirements establish no numeric deployment minimum or deadline.
Any such requirement identified later is recorded in the PRD and validated.
Provider quotas, publisher defaults, and lab measurements do not themselves
establish OSAC service commitments. Qualification remains a delivery gate. [User]

### Publication and resolution: D4

Enabling managed DNS for a tenant requires explicit provider selection of
tenant-internal addresses, ExternalIP addresses, or both for that tenant. No
implicit OSAC-wide publication default is selected. This determines which
addresses are published, separately from who can resolve their names. [User]

OSAC publishes the records and supplies the setup information needed for
resolution from the intended tenant networks. The provider supplies necessary
DNS access and configuration; its existing DNS access policy governs queries.
Per-VirtualNetwork query isolation is excluded. This does not promise control
over client hosts files or independently managed DNS mappings, or replace
network access controls. The resolution boundary and initial publication-policy
selection are recorded. Live policy changes and enable/disable behavior are
recorded above under D4/D9. [User]

### Support baseline: D11

Selected integrations follow documented product lifecycle and supported-version
policies. No additional maintenance or future rebase commitment is assumed.
The original support-expectation question is answered on that basis; D10 still
qualifies the actual VM workflow, versions, and provider path. [User]

### CaaS coordination

CaaS DNS publishes records for cluster API and application endpoints. It does
not provide automatic assignment and lifecycle management of DNS names for
individual VMs. [User]

CaaS/DNS maintainers participate before the VM approach is selected. Its existing
backend is configurable. Preserve CaaS endpoint names and agreed resolution,
readiness, and cleanup behavior. Design evaluates compatibility and reuse;
any later adoption of a new integration for CaaS requires an explicit provider
choice. A shared configuration model is not required by this PRD. If paths differ,
design explains why and how ownership and cleanup coexist safely. Reusing a
backend does not require adopting CaaS's readiness or cleanup lifecycle for VMs.
The D8 reviewer thread remains open for confirmation of this handoff. [User]

[OSAC-2281](https://redhat.atlassian.net/browse/OSAC-2281) covers local BIND support
for CaaS endpoint DNS, including tenant resolution. The
[coordination comment](https://redhat.atlassian.net/browse/OSAC-2281?focusedCommentId=19587688)
proposes independent delivery and asks for confirmation of its abstraction and
configuration scope. It is related work, not a dependency selected for this VM
delivery. Its scope confirmation remains with the networking working group.

### Requested technology constraint

The current Feature calls for a supported OpenShift External DNS Operator and
operand integration where their supported capabilities meet deployment needs.
It does not select an exclusive implementation. D13 records this constraint;
resolution of the original requirement question is proposed in the reviewer
thread. Actual support, compatibility, and evaluation of alternative or coexisting
paths remain D10 design work. The requested path is not waived. Operator and
operand versions are distinct, and a version clarification does not establish
VM-workflow support. [User]
Source comments:
[19193410](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19193410),
[19201459](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19201459).

## Open decisions

Stable references and links retain answered questions alongside the remaining
decisions. Closed own questions are distinguished from open reviewer threads;
recorded answers do not establish reviewer consensus. D3 and D12 are settled
above, and D10 is technical qualification in the design handoff. Requirements
approval still needs human review of the proposed scope and recorded answers.

| Reference | Status | Decision or recorded boundary | Discussion |
|-----------|--------|-------------------------------|------------|
| D1 | Recorded scope; question closed | The current Feature records VMaaS-first and excludes other service delivery. The original checklist mismatch is answered; separate reviewer proposals for a smaller initial slice remain open. | [Delivery scope](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189800) |
| D2 | Revised author scope; reviewer agreement pending | Enabling managed DNS for a tenant covers all its supported OSAC-managed VMs, including existing VMs and VMs created while DNS was disabled. Preserve assigned names; assign others without taking over unrelated DNS records. This supersedes the earlier author exclusion and proposes a Feature scope extension. The earlier thread remains historically closed. | [Adoption](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189824) |
| D4 | Recorded answer; question closed | Provider administrators configure enablement and address-publication policy per tenant. Enabling requires explicit selection of internal addresses, ExternalIP addresses, or both for that tenant. Other tenants' configuration and records are preserved. Requirements remain subject to review. | [Publication](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4601833305) |
| D4 | Resolution clarified; question closed | Names resolve from intended tenant networks through provider DNS under its existing access policy. The provider supplies DNS access/configuration; OSAC does not add per-VirtualNetwork query isolation. | [Visibility](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189848) |
| D5 | Recorded constraint; question closed | Initial IPv6/AAAA/dual-stack support is excluded. Separate IPv6 work remains a coordination reference. | [IPv4/AAAA alignment](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189814) |
| D6 | Recorded answer; question closed | The provider assigns tenant namespaces within supported supplied zones. Separate tenant zones are not required; tenant self-service domain onboarding/delegation is outside this delivery. Exact layout is design work. | [Tenant namespaces](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4601833328) |
| D7 | Recorded answer; question closed | VM FQDN/status appear in API, CLI, and existing VM details, with setup/use/troubleshooting documentation. Administrators can inspect cleanup and retry status after VM deletion through supported operational interfaces. Interface implementation is design work. | [User workflows](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4601833336) |
| D8 | Design handoff; reviewer thread open | Evaluate backend/configuration reuse with CaaS maintainers and safe coexistence if paths differ. A common configuration model is not required; preserve CaaS behavior and explicit provider choice for later adoption. | [Provider experience](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460202946) |
| D9 | Recorded lifecycle answers; discussion open for review | Live policy changes apply per tenant, preserving names and updating eligible targets without VM restart or recreation. Disabling stops that tenant's new publication and withdraws its owned records; re-enabling covers all its supported OSAC-managed VMs under revised D2. Other tenants' configuration and records are preserved. Unfinished work stays visible. VM operation and deletion remain independent. Recorded domain/cleanup guards and cache limitations still apply; design qualifies transitions and operating limits. | [Lifecycle and deletion](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4601833353) |
| D9 | Design handoff; question answered | Design qualifies and documents supported volumes, change rates, and measured publication/removal/recovery and resolver behavior. Any identified deployment minimum or deadline is recorded in the PRD and validated; no numeric commitment is invented. | [Operating targets](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4601833363) |
| D11 | Support baseline recorded; question closed | Follow documented product support/lifecycle policies without an assumed extra maintenance or rebase promise. Actual VM integration qualification remains D10. | [Support expectations](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460189901) |
| D13 | Constraint recorded; reviewer thread open | Retain the requested supported OpenShift ExternalDNS path where capabilities meet requirements, without an exclusive engine. Compatibility and actual VM-path proof remain in design; reviewer resolution is requested. | [Technology constraint](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4460199837) |

The recorded [Feature description](https://redhat.atlassian.net/browse/OSAC-6156)
specifies VMaaS-first and IPv4; it excludes BMaaS, CaaS endpoint, and MaaS hostname
integration from this delivery. It also excludes automatic existing-VM adoption
until explicitly agreed, and per-VirtualNetwork DNS query isolation. Revised D2
now proposes existing-VM coverage as an explicit extension; it does not imply a
Jira change or Feature-owner acceptance. D1 and D5 retain the answered source
questions. Earlier source updates and own-thread closures are not evidence of
reviewer consensus.

The [scope review](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4465118321)
also proposes a smaller path using one provider-supplied zone and new VMs.
Provider-assigned namespaces are recorded under D6; exact name layout belongs
in design. Explicit publication-policy selection, live policy changes, and
enable/disable behavior are recorded author answers under D4/D9. Resolution
follows the provider boundary recorded above. The author decisions do not
resolve the separate scope review.

Publication policy, DNS query visibility, and VM reachability are distinct.
No universal cross-tenant lookup denial is selected, and per-VirtualNetwork
query isolation is outside the recorded Feature boundary. Qualification covers
overlapping addresses and resolution from intended networks under the provider's
existing DNS access policy. No OSAC-specific query enforcement is added.

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
  [configurable CaaS backend](https://github.com/osac-project/osac/blob/d786d49247cb21a4e522a174288436c4a139570b/osac-installer/docs/dns-backend.md)
  and [OSAC-1050](https://redhat.atlassian.net/browse/OSAC-1050), whose abstraction
  anticipates reuse but excludes delivered VMaaS/BMaaS integration. Coordinate
  with [CaaS's accepted DNS contract](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1436-caas-networking/design.md#endpoint-feedback-and-dns)
  and [OSAC-6811](https://redhat.atlassian.net/browse/OSAC-6811),
  [OSAC-6822](https://redhat.atlassian.net/browse/OSAC-6822), and
  [OSAC-6828](https://redhat.atlassian.net/browse/OSAC-6828). Current CaaS
  [bootstrap/publication ordering](https://github.com/osac-project/osac/blob/d786d49247cb21a4e522a174288436c4a139570b/osac-aap/collections/ansible_collections/osac/service/roles/external_access/tasks/caas_dns_publish.yaml)
  is service-specific; backend reuse does not imply identical VM readiness or
  cleanup sequencing.
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
  record ownership, and complete generated data/ownership names. Qualify live
  policy changes, disablement, and enablement for existing and new VMs under D2.
  Cover first-time naming, ownership conflicts, stopped VMs, publication across
  existing VM populations, provider limits, and concurrent VM creation/deletion.
  Verify that changing one tenant's policy or enablement preserves other tenants'
  configuration and records, including with shared DNS infrastructure.
  Include re-enablement before an earlier withdrawal completes; a delayed
  withdrawal must not undo the current enabled state. Qualify delivery
  of withdrawal requests, recovery after publisher/provider outages, and the
  evidence used to report per-VM publication/removal. A submitted request or
  healthy Operator must not be reported as confirmed record removal without
  sufficient evidence. Evaluate any proposed address-reuse mitigation with
  networking owners against
  [ordering section 4.7](https://github.com/osac-project/enhancement-proposals/blob/eb7f6ab9a8683036333f238cd8da3d71a85b814d/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership);
  its mechanism is not a selected contract extension. DNS cleanup must remain
  trackable and finish after VM deletion without introducing a DNS-dependent
  deletion gate through child resources. Design must qualify durable cleanup
  tracking, retries, and administrator visibility after removal of the active VM
  record. The existing
  [database archive](https://github.com/osac-project/osac/blob/d786d49247cb21a4e522a174288436c4a139570b/fulfillment-service/internal/database/dao/generic_dao_request.go#L110)
  preserves a deleted-object snapshot; the
  [VM details page](https://github.com/osac-project/osac/blob/d786d49247cb21a4e522a174288436c4a139570b/osac-ui/libs/ui-components/src/components/vm/VmDetailsPage.tsx#L10)
  reads the active VM. Neither demonstrates ongoing post-deletion DNS cleanup
  visibility. Document propagation and resolver/cache limits and residual
  stale-answer/address-reuse risks. IP quarantine and a guarantee against every
  stale answer are not selected requirements; additional protections require
  explicit agreement and must preserve nonblocking VM deletion.
  [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308.html#section-5)
  and [RFC 8767](https://www.rfc-editor.org/rfc/rfc8767.html) explain negative
  caching and stale answers. Measure authoritative and recursive visibility
  separately, preserving [configured resolver behavior](https://redhat.atlassian.net/browse/OSAC-6342).
- **Qualification:** demonstrate the agreed lifecycle, visibility, conflict,
  isolation, failure, maximum-name-length, and scale outcomes through supported
  DNS and client paths. Qualify and document the supported deployment envelope,
  change rates, and measured publication/removal/recovery and resolver behavior.
  A required deployment minimum or deadline, when identified, is recorded in the
  PRD and validated. A running publisher does not confirm individual records;
  lab timings, defaults, and quotas do not establish service commitments.

Broader [DNSaaS](https://redhat.atlassian.net/browse/OSAC-3202),
[local DNS](https://redhat.atlassian.net/browse/OSAC-2127), and
[BIND integration](https://redhat.atlassian.net/browse/OSAC-2281) remain coordination
references, not prerequisites. Detailed historical research is retained in the
author's working artifacts; this companion states the current review position.
