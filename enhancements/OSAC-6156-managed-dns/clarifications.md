# Clarification and revision log — OSAC-6158

This log records direct user direction and source interpretation. It does not
record stakeholder approval or changes to Jira.

## Current status

Recorded clarification rounds: R1 through R8. R9 is a follow-up backlog, not an
immediate request for answers. R10 records the authorized revision/publication;
R11 records the research; R12 prepares its findings as a local PRD revision;
R13 addresses the subsequent local review findings; R14 adds proposals for
changes to DNS configuration in response to the next review comment.
Clarification continues as reviews arrive.
Clarification exit criteria are not met: the technology constraint, delivery
boundary, and several observable product behaviors remain open.

R8 records the user's latest direction following human review. It reopens the
firmness of the ExternalDNS requirement recorded in R1 and supersedes the
connected-only proposal recorded in earlier rounds. R10 through R13 are
published at PR 445 head `14780fb`; R14 extends that revision.
The original Feature requests
and exclusions remain source requirements; no customer constraint is presumed
waived.

## R1 — ExternalDNS and the proposed first increment

### R1.ExternalDNS — Confirmed user direction

ExternalDNS is a requirement. Treating it as required does not abandon other
options. The initial integration target is the Red Hat External DNS Operator;
alternatives remain in the design evaluation. A record source, adapter, provider,
or exclusive architecture has not been selected.

### R1.Scope — Proposed boundary, confirmation outstanding

The user requested a revision after discussing a VMaaS-first ExternalDNS
increment, then asked whether VMaaS-first was decided in the Feature or comments.

The Feature reporter's [October 25 comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19101116)
explicitly proposes VMaaS ExternalDNS support as the first phase. The Feature
description retains VMaaS, BMaaS, CaaS, and MaaS coverage. No captured later
comment explicitly reconciles that checklist with the first-phase proposal.

The revised PRD presents VMaaS-first as the proposed delivery boundary for
review, with confirmation remaining under D1. It must not claim a completed Jira
scope decision. BMaaS/CaaS/MaaS integration and CaaS DNS migration are outside
that proposed initial increment, subject to D1.

### R1.Baseline — Established OSAC constraints

The codebase and accepted networking designs establish connected IPv4 behavior,
service-specific assigned-address feedback, and tenant isolation. Canonical
resource names are immutable and unique for their resource type within tenant
and project scope. DNS composition must account for those scopes.

The Feature's AAAA checklist needs explicit alignment with the existing IPv4
boundary and the separate OSAC-5077 IPv6 work. This remains D5; no IPv6 delivery
is approved by this revision.

### R1.Authority — Still open

Choosing ExternalDNS does not establish who supplies and operates authoritative
DNS. The user has not selected existing authority, OSAC-operated nameservers, or
both. Keep that question visible; do not silently scope out local DNS hosting.

### R1.Questions — Narrow the remaining decisions

The user requested the revised draft and a report of remaining questions. Group
the practical questions around deployment compatibility/support, address and
query policy, zones/naming, persona workflows/failure behavior, and capacity/
timing. Keep broader DNSaaS/local-DNS/BIND work as coordination references rather
than assuming they are delivery prerequisites.

## Decision reference mapping

| Original reference | Revised handling |
|--------------------|------------------|
| D1 | VMaaS-first boundary proposed; Feature-owner confirmation outstanding. |
| D2 and D10 | Required product is identified; actual deployment integration and support expectations remain open. |
| D3 and D6 | Group authority/zone ownership and hostname policy; preserve existing immutable identity constraints. |
| D4 | Address publication and tenant/VirtualNetwork query visibility remain separate decisions. |
| D5 | Existing IPv4 boundary is established; align the Feature's AAAA checklist explicitly. |
| D7 and behavioral part of D9 | Persona surfaces and VM DNS lifecycle/failure behavior remain open. |
| D8 | CaaS adoption/migration is outside the proposed increment; reconsider only if D1 expands scope. |
| Quantitative part of D9 | Capacity, change rate, propagation/removal, and cache objectives remain open. |

The research and Jira cross-reference remain historical evidence snapshots.
Their earlier open-question lists do not override this revision log.

## R2 — Follow the existing third-party operator installation convention

The user directed attention to OSAC's existing third-party operator installation
workflow as the way to handle External DNS Operator installation and reuse.

Apply that convention: permit OSAC-managed installation or a compatible
administrator-managed installation. Preserve the existing installation's
ownership and unrelated configuration. Installer examples include NMState's
separate operator-install switch and the documented MCE ownership boundary.

Operator reuse is no longer an open product choice in D2. The DNS provider and
operator configuration are deployment inputs for support qualification and
integration testing; OSAC uses ExternalDNS's supported provider integration.
Existing VM adoption and the required support/maintenance expectations remain
open. This does not select a VM record source or adapter, change the proposed
VMaaS-first status, or decide who operates authoritative DNS.

Evidence:

- [Installer operator/operand ownership conventions](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/docs/guides/installation/helm-deployment-guide.md#how-toggles-affect-operands)
- [NMState installation switch](https://github.com/osac-project/osac/blob/f6b842aa68c668f655b84de191b1a6084de4fca0/osac-installer/charts/osac-infra/values.yaml#L106)

## R3 — Authority, naming, and IPv6 recommendations accepted

After focused research into DNS authority, naming limits, and IPv6, the user
agreed to the recommendations and requested the remaining questions.

Confirmed for the working PRD:

- Provider-supplied authoritative DNS and writable zones are prerequisites.
  Provisioning production DNS servers or zones is a separate capability; test
  fixtures do not imply delivery of production DNS hosting. This resolves D3.
- Preserve OSAC's existing immutable resource-name contract and provide a
  deterministic, collision-free DNS mapping with discoverable assigned FQDNs.
  Exact hostname layout and validation of complete data/ownership names are
  design work. Evaluate the short-first-label candidate before shortening any
  resource-name allowance; the example pattern itself is not selected.
- The initial supported VM publication path is IPv4/A. Automatic AAAA publication
  requires a supported IPv6 endpoint/address-feedback contract and integration
  evidence. Generic AAAA support does not demonstrate usable VM IPv6. This
  resolves the D5 product boundary; the Feature checklist still needs review
  alignment, and no Jira edit has been made.

Remaining D6 product choice: provider-assigned tenant subdomains, tenant-owned
delegated subdomains, or both, with an assignment/approval policy.

D10 is deployment qualification for the requested supported Red Hat product.
Customer-specific compatibility/support constraints, if required, are collected
with the existing deployment discovery; the PRD does not invent a new support
period. Operator installation continues to follow R2.

VMaaS-first remains the proposed review boundary under D1. The agreement to these
research recommendations does not establish that Jira's broader service
checklist has been reconciled or that the Feature owner approved the split.

## R4 — Review corrections and explicit approval gates

The user accepted the review assessment and requested a separate commit.
This revision records corrections and outstanding decisions; it does not record
stakeholder answers, change Jira, or approve the requirements.

- D1 now requires Feature-owner confirmation and a recorded phase split in Jira.
  Completing the PRD task does not complete the broader Feature checklist.
  D5 still requires alignment of its AAAA item with the initial IPv4/A boundary.
- Correct the RFE characterization: [RFE-7197](https://redhat.atlassian.net/browse/RFE-7197)
  is Closed / Won't Do. Its [September product response](https://redhat.atlassian.net/browse/RFE-7197?focusedCommentId=18640210)
  says development cannot be prioritized in the foreseeable roadmap. A delivery
  plan must establish another supported publication path without relying on the
  RFE reopening. No source or adapter is selected by this revision.
- D10 is a supported-delivery constraint. Detailed qualification belongs to
  [OSAC-6159](https://redhat.atlassian.net/browse/OSAC-6159). A focused feasibility
  check can proceed alongside product clarification; completing the full design
  is not itself a prerequisite for PRD approval.
- D11 explicitly asks what maintenance, supported-version, and update commitments
  the offering requires and what the Red Hat product owner confirms. Clarifying
  operator versus operand versions did not answer that question.
- D4 still requires a visibility policy separate from address publication.
  Overlapping-address and allowed/denied-resolution tests must follow that
  policy. Universal cross-tenant lookup denial is not selected. Tenant ownership
  and preservation of unrelated DNS records remain required.
- D7 and D9 now separate user surfaces, lifecycle behavior, and quantitative
  acceptance. Existing-VM adoption remains D2. None of these answers is inferred
  from current field values, defaults, or exploratory test timings.
- Preserve allowed resource-name lengths; qualification must validate complete
  DNS record and ownership names. The original BMaaS IPMI/Redfish exclusion is
  stated explicitly again. Repeated settled constraints are condensed.

### Lifecycle evidence motivating D9

The [accepted VMaaS networking design](https://github.com/osac-project/enhancement-proposals/blob/bb9e8f6475e65304f000b49fc4405616b8eb2f6f/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery)
clears reported IP fields when no VMI or matching address exists, including for
a halted VM, while requiring the Kubernetes Manager to preserve its address
across restarts. An empty reported address therefore does not establish the
desired DNS lifecycle. Review must specify name/record behavior on stop/restart,
ExternalIP attach/detach, and address changes, plus DNS-outage effects on VM
readiness and deletion. This is accepted-contract evidence, not a new runtime
test result.

### Disposition of the five questions in Feature comment 19168631

The [original comment](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19168631)
remains relevant after ExternalDNS becomes a requirement.

| Question | Current disposition |
|----------|---------------------|
| Red Hat maintenance and upstream update cadence | Open under D11; no product commitment has been obtained. |
| Supported DNSEndpoint source | The inspected Red Hat operator exposes Service/Route publication; a usable DNSEndpoint source is not assumed. D10 requires a supported VM path independent of RFE-7197. |
| Record and Kubernetes object scale | Open under quantitative D9; targets and exact-deployment measurements remain necessary. Functional lab experiments are not capacity evidence. |
| Reduced name lengths | Preserve OSAC's existing allowed resource-name lengths. D6 design work validates complete generated data and ownership names and collisions. |
| Multiple VPCs and tenants from one cluster | D4 must settle visibility; D10 must qualify the applicable provider topology, permissions, and publication scope. Multiple zones alone do not demonstrate the policy. |

### Qualification evidence for the design task

These are requested evidence items, not completed tests or new Jira assignments:

- Identify the supported OpenShift, operator, operand, provider, and publication
  configuration. Establish documented product support, obtaining product-owner
  confirmation where documentation is inconclusive, and demonstrate the VM DNS
  lifecycle in that configuration. Upstream success alone is insufficient.
- Verify lifecycle and outage recovery against the agreed D2/D9 outcomes, tenant
  write ownership and unrelated-record preservation, and the D4 resolution policy
  with overlapping tenant addresses and applicable provider VPCs.
- Validate complete record and ownership names at maximum allowed resource-name
  lengths, nested/default project scopes, and collision cases. Measure object
  counts, churn, provider limits, and reconciliation behavior against D9 targets.

This leaves the required ExternalDNS integration and alternative evaluation in
place, with provider-supplied authoritative DNS and zones. It does not expand the
increment into DNSaaS or production nameserver provisioning.

## R5 — Feature-level title and review response

The user approved the title "Managed DNS for tenant resource hostnames" and
clarified that the delivery boundary is a question for reviewers. VMaaS-first
remains an option supported by the Feature comment, not an agreed first
increment. The document and PR titles now name the Feature topic. D1 explicitly
asks whether to start with VMaaS or cover the broader Feature; exclusions for
BMaaS/CaaS/MaaS and CaaS DNS integration depend on that decision.

The [automated review of the preceding commit](https://github.com/osac-project/enhancement-proposals/pull/445#issuecomment-6503665243)
identified wording repetition and unresolved acceptance. The response applies
the following editorial corrections:

- D10 uses product-level language while retaining the supported-delivery gate
  and accurate Closed / Won't Do status. Technical integration details remain
  with the design task.
- The automatic AAAA prerequisite is stated in In Scope, with a cross-reference
  from Out of Scope. Scope framing points to D1 without presenting a phase split
  as decided.

The suggestion to replace unanswered questions with provisional testable
assertions is not adopted. No stakeholder discussion resolves D2, D4, D6, D7,
D9, or D11; invented stop/restart, visibility, or timing behavior would change
the requirements. These remain approval gates. D7 user workflows and D9
lifecycle/operating targets retain their existing references and separate
questions; grouping them would not resolve either decision.

No external review reply is recorded as posted until its proposed text is
approved. The PR remains a draft for requirements discussion.

## R6 — Observable requirements and concise dependencies

The user invoked another response round. The automated review of 6bbc9712
retains a 7/10 document-quality score and raises wording, dependency length,
and unresolved acceptance. No human review or product-question resolution is
present in the fetched discussion.

- Replace internal contract terminology with observable behavior: connected
  deployments publish supported IPv4 VM addresses; resource names remain fixed
  after creation with their allowed lengths preserved; generated DNS names
  distinguish tenant/project/type scopes; automatic changes for one tenant
  preserve other tenants' and unrelated records.
- Retain the Red Hat External DNS Operator requirement in In Scope and the
  installation story. The DNS integration story now states the outcome of
  resolving VM names through the deployment's existing DNS infrastructure.
- Condense Dependencies to its scope/product questions and short external
  dependencies. Keep D10's supported-integration requirement and explicit
  Closed / Won't Do warning. Detailed qualification evidence remains under R4
  for the design task rather than being repeated in the PRD.
- Do not invent provisional lifecycle, visibility, capacity, or maintenance
  assertions. No discussion supplies those answers. D7 already explicitly asks
  for UI/CLI/API workflows and documentation, so another dimension note adds
  no requirement.
- Retain delegation, predictable hostnames, and provider publication policy:
  these are explicit Feature requirements. A review preference for a smaller
  initial path does not authorize removing them. D1 remains a scope question.

Qualification still follows the accepted networking and naming constraints
recorded under R1/R3/R4, including the supported IPv6 endpoint/address-feedback
contract before automatic AAAA publication. The observable wording does not
change the required evidence or establish DNS policy from stopped-VM status.

The [DNSaaS](https://redhat.atlassian.net/browse/OSAC-3202),
[local authoritative DNS](https://redhat.atlassian.net/browse/OSAC-2127), and
[BIND integration](https://redhat.atlassian.net/browse/OSAC-2281) references move
here as coordination context for OSAC-6159. They remain non-prerequisites for
the proposed delivery. Any later zone or nameserver provisioning must
coordinate with those owners.

The user's earlier no-reply direction is preserved. This round applies
editorial changes without posting a public review reply or treating a
document-quality pass as requirements approval.

## R7 — Highest justified document quality

The user asked whether the goal was 10/10, with the qualification that further
changes should make sense. This revision removes genuine repetition without
inventing decisions or changing the Feature requirements:

- D1 remains the authoritative delivery-boundary question; other sections use
  brief references and retain conditional service exclusions.
- The record-family proposal is stated in In Scope. Out of Scope and D5 refer
  to it rather than repeat the AAAA prerequisite or IPv4/A boundary.
- Scope and product questions are explicitly required before PRD approval.
  Technical integration, hostname layout, limit validation, and deployment
  qualification belong to design. No unanswered product question is reclassified
  as design work to improve a score.
- The generated Provenance footer remains required workflow metadata. The
  remaining testability limit requires stakeholder answers, not provisional
  lifecycle, visibility, capacity, or support commitments invented by the agent.

The ExternalDNS requirement, delegation, naming guarantees, existing provider
prerequisites, and original Feature exclusions remain unchanged. No public
review reply is requested or posted.

## R8 — Human review and subsequent user discussion

The user selected the four draft review replies as the guide for clarification.
This round records that direction without revising the PRD, committing,
publishing, or posting review replies. Answering roles below are routing
suggestions, not Jira assignments or authorization to contact anyone.
The user subsequently confirmed that clarification will continue as reviews
come in; the remaining questions are retained for that discussion.

### R8.Q1: Is ExternalDNS a firm technology requirement?

The Feature discussion records a request for the Red Hat External DNS Operator.
Does that establish a binding constraint, or could another solution satisfy the
customer's need?

#### Answer

The user agreed that technology selection normally belongs in design and asked
that the firmness of the customer requirement be confirmed first. The guiding
reply treats ExternalDNS as a documented customer request with its mandatory
status still needing verification. Alternatives remain under evaluation.

Evidence: Feature comments
[19193410](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19193410)
and
[19201459](https://redhat.atlassian.net/browse/OSAC-6156?focusedCommentId=19201459)
establish the request and identify the operator. They do not answer whether an
alternative would be accepted.

#### Impact

Reopen the firmness of the R1.ExternalDNS constraint. The Feature owner and
customer liaison need to confirm the requirement and the behavior or existing
integration it must preserve. Do not declare the request waived, assert that
generic DNS satisfies it, or select a replacement. A later PRD revision should
describe observable DNS needs and carry any confirmed technology constraint.
Supportability and deployment qualification remain design work under D10.

---

### R8.Q2: Should the PRD restrict delivery to connected deployments?

The draft borrowed a connected-only restriction from accepted networking scope.
Is that an appropriate blanket boundary for this DNS offering?

#### Answer

The user explicitly rejected limiting the offering to connected deployments and
accepted the reviewer's challenge. The user prefers omitting connected versus
disconnected wording rather than introducing another unsupported scope claim.
Design should evaluate deployment requirements across candidate solutions;
Infoblox is not the only possible approach when alternatives are considered.

#### Impact

A later revision removes the blanket restriction. This does not claim that
every installation mode, DNS provider, or underlying networking capability is
already supported. Qualification must identify actual prerequisites and
limitations, and any conflict with a required workflow returns to requirements
review. Existing IPv4 and tenant-isolation commitments remain in force.

#### Decision (D12)

Do not limit managed DNS to connected deployments or impose a blanket exclusion
of disconnected deployments in the PRD. Evaluate deployment requirements and
specific limitations during design.

---

### R8.Q3: What does existing-operator reuse mean?

If External DNS Operator is used, can the provider reuse an existing
installation or have OSAC install it?

#### Answer

Yes. The intended behavior is to reuse a compatible existing installation or
permit OSAC-managed installation, following the established third-party
operator pattern. This clarifies R2; it does not select the operator as the
exclusive architecture or establish compatibility with every installation.

#### Impact

Preserve ownership and unrelated configuration. Simplify the user-facing
wording when the PRD is revised, conditional on the selected integration and
any confirmed technology requirement. No new installation decision is needed.

---

### R8.Q4: How should VMaaS and CaaS DNS converge?

Should the VMaaS approach be selected before considering its relationship to
the existing CaaS DNS integration?

#### Answer

The guiding reply calls for discussion with CaaS/DNS maintainers before choosing
the VMaaS approach. Design should address convergence with existing CaaS DNS
and any transition involved. Starting with VMaaS remains open for review.

#### Impact

Preserve the Feature's requirement to replace or integrate with CaaS DNS and
carry the cross-service coordination into design. The conditional exclusion of
CaaS implementation from a possible VMaaS-first delivery does not exclude
CaaS compatibility and convergence planning. No common implementation,
migration schedule, or delivery phase is selected. The provider's desired
configuration experience remains R9.Q1; delivery scope remains D1.

## R9 — Provider experience, visibility, and VM lifecycle

These are candidate questions for later review-driven clarification. They have
not been presented as a required answer batch. The technology-constraint
confirmation and D1 delivery-boundary discussion remain routed to the relevant
stakeholders; they are not silently answered by this backlog.

### R9.Q1: What should providers experience across VMaaS and CaaS?

Should a Cloud Infrastructure Admin configure a shared DNS integration for VMs
and clusters, or is separate configuration per service acceptable? This asks
about the provider workflow, not whether both services use the same internal
implementation.

#### Answer

Awaiting user clarification or Feature-owner/CaaS review.

#### Impact

Clarifies the user-facing meaning of cross-service integration and provides an
outcome against which design can compare convergence approaches. It does not
select a backend or decide whether CaaS migration ships in the initial delivery.

---

### R9.Q2: Who should resolve tenant-internal VM names?

Should resolution be available only within the VM's VirtualNetwork, across the
tenant's networks, or to a provider-defined set of client networks? Existing
address-publication controls and the ability to reach a VM do not settle DNS
query visibility.

#### Answer

Awaiting user clarification or Feature-owner/networking-security review.

#### Impact

Supplies the D4 query-visibility policy and corresponding acceptance cases,
including overlapping tenant addresses. It does not introduce a universal
cross-tenant lookup denial or change tenant record ownership requirements.

---

### R9.Q3: Should a stopped VM's hostname still resolve?

When a VM stops but retains its assigned address, should its DNS record remain,
or should the record be removed until the VM starts again?

#### Answer

Awaiting user clarification or Feature-owner/persona review. Retaining the
record while the address remains allocated is a recommendation for discussion,
not an agreed requirement.

#### Impact

Resolves the stop/restart portion of behavioral D9 without inferring DNS policy
from temporarily empty reported IP fields. Address changes, ExternalIP
attachment/detachment, and DNS-outage effects remain separate open behaviors.

## Remaining gaps after R8

- Confirm whether ExternalDNS is a binding customer requirement and which
  behavior or existing integration it must preserve.
- Confirm D1 service delivery boundary and D5 Feature-checklist alignment.
- Answer R9's cross-service provider experience, D4 visibility, and stopped-VM
  behavior questions.
- Retain D2 existing-VM adoption; the rest of D4 publication policy; D6 domain
  assignment; D7 user surfaces/documentation; the remaining behavioral and
  quantitative D9 requirements; and D11 support/maintenance expectations.
- Design still needs to demonstrate a supported delivery path, evaluate
  deployment prerequisites and alternatives, and plan CaaS convergence.

At the end of clarification, the PRD and its published clarification copy
remained unchanged. No review replies, Jira writes, commits, or pushes occurred.

## R10 — Local revision for review

The user invoked `/prd-revise` to apply the four clarified review points, then
explicitly requested no commit and asked to see the draft replies first. This
revision prepares local documents and replies only. It does not authorize
publication or posting comments.

- State the automatic VM hostname behavior without selecting ExternalDNS as the
  implementation. New reference D13 tracks confirmation of the customer-requested
  integration's mandatory status and any behavior that must be preserved. D13 is
  an unresolved product question, not a locked decision or a waiver of the request.
- Apply D12 by removing the connected-only restriction. Do not add connected or
  disconnected scope language or name a provider as the only alternative.
  Deployment qualification stays in design; IPv4/AAAA alignment remains D5.
- Make existing-installation reuse and OSAC-managed installation conditional on
  selecting External DNS Operator. Preserve ownership and unrelated configuration.
- Carry CaaS integration, convergence, maintainer coordination, and any transition
  into the D8 design dependency before the VMaaS approach is chosen. D8's earlier
  conditional implementation deferral does not exclude this planning obligation.
  VMaaS-first remains a proposal under D1; no common backend or migration schedule
  is selected.
- Keep product maintenance/support questions under D11, with the Red Hat-specific
  confirmation conditional on evaluating ExternalDNS. The Closed / Won't Do RFE
  warning still applies to any ExternalDNS proposal under D10.

The local PR-description draft is updated for consistency. The Feature-level
title remains accurate. Draft replies are stored separately for user review;
none are posted or logged as responded. R9 remains a backlog for later
clarification, and other product acceptance decisions remain open.

### Publication authorization

After reviewing the local revision and proposed replies, the user authorized
completion with commit, push, and replies. This supersedes the earlier hold on
publication. The overall reply includes the user's approved assurance that the
PR stays in draft until the open questions, scope, and requirements are agreed.
This authorization does not resolve the remaining product decisions or approve
the requirements for merge.

## R11 — Investigate outstanding questions before further PR discussion

The user requested thorough investigation and artifact updates, with a report
back before comments or thoughts are left on the PR. This authorizes local
research material only. No PR/Jira writes, commits, pushes, or new replies are
part of this step.

Detailed research remains in local working artifacts. The following evidence
summary accompanies the PRD so review does not depend on unpublished material.

### Evidence verified on 2026-11-02

- A stopped VM's reported IP can be empty while its address allocation persists.
  The current controller clears reported addresses without a running VMI; the
  accepted VMaaS design requires address stability across restart/migration.
  DNS retention is still a product proposal, and design must identify a stable
  allocation source rather than infer release from an empty reported value.
  [Current VM controller](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/osac-operator/internal/controller/computeinstance_controller.go#L868),
  [accepted VMaaS contract](https://github.com/osac-project/enhancement-proposals/blob/a46dc709b12c9fe175bd71ae9c2a11f62c18b7eb/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery).
- CaaS already has a configurable internal DNS publisher. Its current endpoint
  discovery is cluster-specific; the accepted CaaS target also defines endpoint
  names, DNS readiness, and cleanup before address release. Coordinate the
  managed-DNS design with [OSAC-6811](https://redhat.atlassian.net/browse/OSAC-6811),
  [OSAC-6822](https://redhat.atlassian.net/browse/OSAC-6822), and
  [OSAC-6828](https://redhat.atlassian.net/browse/OSAC-6828). Their New state does
  not establish completion of the target behavior or its installer guards.
  [Current driver use](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/osac-aap/collections/ansible_collections/osac/service/roles/external_access/tasks/caas_dns_create.yaml),
  [accepted CaaS endpoint/DNS contract](https://github.com/osac-project/enhancement-proposals/blob/a46dc709b12c9fe175bd71ae9c2a11f62c18b7eb/enhancements/OSAC-1436-caas-networking/design.md#endpoint-feedback-and-dns).
- [OSAC-6342](https://redhat.atlassian.net/browse/OSAC-6342) is Closed / Done;
  current DNS waits prefer a configured recursive resolver. This remains
  relevant even though other network-manager DNS settings were removed.
  [Resolver selection](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/osac-aap/collections/ansible_collections/osac/service/roles/external_access/tasks/caas_dns_create.yaml#L95).
- The current Red Hat lifecycle table explicitly includes OpenShift 4.17–4.22
  and 5.0 for Operator 1.3. The earlier 4.22 evidence gap is resolved. Full
  support ends 2027-02-28; maintenance ends 2027-06-30; release cadence is
  unspecified. Exact payload/provider/VM-path qualification remains separate
  from that matrix, and no future rebase commitment is inferred.
  [Published lifecycle policy](https://access.redhat.com/support/policy/updates/openshift_operators).
- The inspected operator release branch has a CRD source enum but wires Service
  and OpenShift Route in its source union/deployment mapping. Upstream 0.14.2's
  Service target annotation supplies a concrete VM adapter candidate. Neither
  source inspection nor earlier upstream experiments proves support for that
  VM use in a shipped Red Hat payload. RFE-7197 remains Closed / Won't Do.
  [Operator source API](https://github.com/openshift/external-dns-operator/blob/1a505729c29129db941065ef487bda6cd49685ed/api/v1beta1/externaldns_types.go),
  [deployment mapping](https://github.com/openshift/external-dns-operator/blob/1a505729c29129db941065ef487bda6cd49685ed/pkg/operator/controller/externaldns/deployment.go),
  [upstream Service source](https://github.com/kubernetes-sigs/external-dns/blob/v0.14.2/source/service.go#L462).
- Operator availability is not per-record acknowledgement. Its inspected status
  reports component conditions and configured zones. Design must demonstrate
  publication/error feedback and resolution through the intended DNS path.
  [Operator status](https://github.com/openshift/external-dns-operator/blob/1a505729c29129db941065ef487bda6cd49685ed/api/v1beta1/externaldns_types.go#L577).
- Tenant login/email domains do not establish authority over DNS namespaces.
  Existing resource names remain immutable and scoped by tenant/project/type.
  A short first DNS label is a candidate for preserving 63-character resource
  names despite ownership prefixes; validate the full data and ownership names,
  nested project scopes, and collisions in the selected implementation.
  [Tenant domain meaning](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/proto/private/osac/private/v1/tenant_type.proto#L44),
  [resource names](https://github.com/osac-project/osac/blob/9ddd24e49a34393e090df4abe5226d2a9b6bc494/fulfillment-service/docs/API.md#resource-names),
  [TXT formatter](https://github.com/kubernetes-sigs/external-dns/blob/v0.14.2/registry/txt.go#L447).
- Publication does not establish client visibility. For example, a Route53
  private zone needs an associated VPC resolver or hybrid inbound endpoint;
  public NS delegation alone does not supply that access. Supported resolution
  methods must match the actual DNS service and permitted client networks.
  [Private-zone resolution](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-private.html).
- A writer's ownership identity must distinguish installations sharing a zone.
  The inspected operator derives its TXT identity from its ExternalDNS resource
  name and uses sync policy. Design must qualify source selection, permissions,
  conflict handling, and transition between writers. Ownership TXT data is not
  tenant authorization.
  [Operator arguments](https://github.com/openshift/external-dns-operator/blob/1a505729c29129db941065ef487bda6cd49685ed/pkg/operator/controller/externaldns/pod.go#L164),
  [upstream ownership handling](https://github.com/kubernetes-sigs/external-dns/blob/v0.14.2/registry/txt.go#L246).
- Authoritative deletion does not flush cached answers. Negative caching can
  delay visibility of new records; stale-answer policies can retain old answers
  during failures. Publication/removal objectives and address reuse therefore
  need explicit resolver/cache expectations. Existing TTLs and provider quotas
  are planning inputs, not service acceptance targets.
  [Negative caching](https://www.rfc-editor.org/rfc/rfc2308.html#section-5),
  [stale-answer behavior](https://www.rfc-editor.org/rfc/rfc8767.html),
  [current Route53 quotas](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/DNSLimitations.html),
  [current throttling model](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/throttling-api-requests.html).

The research supplies concrete adoption, retention, status, and cleanup defaults
for review, plus design qualification work. It does not record user acceptance
of those defaults or close D1, D2, D4, D5 alignment, D6, D7, D8's remaining
experience choice, D9, D10, D11's remaining requirements, or D13. D3 and D12
remain settled as previously recorded. At the end of this research step, the
local and published PRD text was unchanged. No new deployed or load validation
or vendor/customer support confirmation was obtained.

## R12 — Prepare research-backed proposals in the review draft

### R12.Q1: How should the findings appear in the PR?

#### User direction

After discussing revision versus comments, the user invoked `/prd-revise` and
said an overall PR comment was unnecessary. Prepare the local revision and its
review material without an overall comment. The current revision remains
uncommitted for review; no PR/Jira write or review reply is part of this step.

#### Revision

- Incorporate verified facts and supporting sources. Narrow D11 to required
  support commitments that the published policy does not answer.
- Put concrete proposals beside D2, D6, and D7: eligible existing-VM adoption
  with conflict preservation, explicit provider namespace approval, and name/
  success/failure discovery through existing VM workflows.
- Present D9 retention, confirmed-address changes, ExternalIP attach/detach,
  outage/readiness, and cleanup/reuse behavior as proposals for review. Whether
  VM deletion itself waits for cleanup remains explicitly open. Authoritative
  removal and recursive cache expiry remain distinct.
- Keep D4 publication defaults and allowed resolver/client scope open. Require
  resolution methods to match the selected backend and permitted client paths.
- Keep D1, D5 checklist alignment, D13, quantitative D9, and required support
  horizons open. State D8's provider-experience choice alongside its existing
  convergence dependency; do not select one backend or migration schedule.
- Preserve the existing CaaS naming/readiness/cleanup contract in convergence
  work. Keep adapters, allocation/ownership mechanics, exact names, and deployed
  qualification in OSAC-6159. No proposal is promoted to an agreed requirement.

#### Status

The local PR description follows the revision. D3 and D12 remain settled.
No overall comment, thread reply, thread resolution, Jira update, commit, or
push is included. Review the proposed answers or revise them again before
publishing this update to the existing draft PR.

## R13 — Address the local PRD review

### R13.Q1: Apply the three review findings

The user agreed with the local review's findings: improve the motivation in two
user stories, define adoption eligibility, and shorten repeated review guidance.
This authorizes the local revision; it does not close the open product decisions
or authorize commit, push, or PR comments.

- Ground the Provider Admin zone story in avoiding tenant record maintenance
  and the Infrastructure Admin lifecycle story in avoiding manual maintenance
  and stale records. These motivations use the existing Problem Statement.
- Define the proposed adoption cohort as existing VMs of tenants covered by
  provider-managed DNS configuration with an assigned DNS namespace, including
  stopped VMs. Publish only verified, permitted addresses allocated to the VM.
  If no address can yet be verified, show the assigned name with publication
  pending. Preserve records owned by others and report conflicts.
- Remove the decision table's Effect column and repeated review narration,
  preserving decision IDs, reviewers, scope/AAAA alignment, customer constraints,
  policy-based lookup verification with overlapping addresses, ownership, cache
  expectations, and all lifecycle proposals.

The clarified adoption behavior remains a proposal for stakeholder review.
All previously open product decisions remain open. At the end of the local
revision, the PRD, clarification, and PR-description copies were synchronized
but uncommitted and unpublished, with no review replies or Jira changes.

### Publication authorization

After reviewing the revisions, the user explicitly requested commit and push,
with no PR comment. Publish the document changes and synchronize the PR
description. The PR remains draft; this authorization does not resolve the open
product decisions or approve requirements for merge.

## R14 — DNS configuration changes for existing VMs

### R14.Q1: Define supported changes and outcomes for review

The [new inline comment](https://github.com/osac-project/enhancement-proposals/pull/445#discussion_r4457237603)
asks whether address-publication policy changes, tenant domain/subdomain changes,
and disabling managed DNS are supported for existing VMs, and what happens to
owned versus unrelated records. It requests observable behavior; implementation
mechanics remain design work. The comment is submitted by Chai Bot and marked
AI-generated; it is not evidence of new stakeholder consensus.

The user agreed to apply the proposed outcomes in the PRD. The existing
authorization to commit and push without comments applies to this revision;
the draft inline reply is not authorized for posting. The proposed VMaaS
delivery boundary remains subject to D1.

#### Proposed outcomes

- Initial tenant namespace assignment and enabling DNS for existing VMs follow
  D2. This is distinct from replacing a namespace already assigned to a tenant.
- Address-publication policy changes update managed answers to include newly
  permitted addresses and withdraw addresses no longer permitted.
- Disabling managed DNS removes its owned records for affected VMs and reports
  cleanup pending/failure until authoritative removal is confirmed, then reports
  DNS disabled. D9's outage, retry, cleanup, and cache expectations still apply.
- Replacing an assigned tenant DNS domain/subdomain is rejected while that
  tenant has VMs. Rejection leaves the current configuration, names, and records
  unchanged. This is a proposed boundary for the VMaaS option under review,
  not a permanent exclusion of DNS migration capabilities.
- Preserve unrelated records throughout. Report publication and the progress
  or failure of disabling DNS through D7's proposed existing user surfaces.

#### Evidence and boundaries

The accepted CaaS contract restricts changes to its configured domain, zone, and
DNS implementation while clusters exist, partly because names must match cluster
certificates. This is a coordination constraint for D8, not automatic approval
of identical VM rules or proof that every installer guard is implemented.
[Accepted CaaS contract](https://github.com/osac-project/enhancement-proposals/blob/a46dc709b12c9fe175bd71ae9c2a11f62c18b7eb/enhancements/OSAC-1436-caas-networking/design.md#endpoint-feedback-and-dns).

The PRD retains its supported integration requirement under D10. Operator-specific
support dates and RFE disposition are moved out of the PRD body; their evidence
remains in R4/R11 above. In particular, RFE-7197 remains Closed / Won't Do and
must not be assumed to reopen. No newer product support commitment is asserted.

The refreshed automated review's count of thirteen unresolved decisions does
not match this log: D3 and D12 are settled, and D10 concerns technical delivery
qualification. Existing product questions and this round's proposals still need
review; no new decision reference is invented solely to increase the count.

#### Status

The PR description follows the revision. A draft inline reply is retained in
local working artifacts for review only. No reply is posted, no thread is
resolved, and Jira is unchanged. Product proposals remain subject to stakeholder
agreement before requirements approval; the PR remains draft.
