# Clarification and revision log — OSAC-6158

This log records direct user direction and source interpretation. It does not
record stakeholder approval or changes to Jira.

## Current status

Recorded rounds: R1 through R8. R9 is a follow-up backlog, not an immediate
request for answers. The user will continue clarification as reviews arrive.
Clarification exit criteria are not met: the technology constraint, delivery
boundary, and several observable product behaviors remain open.

R8 records the user's latest direction following human review. It reopens the
firmness of the ExternalDNS requirement recorded in R1 and supersedes the
connected-only proposal recorded in earlier rounds. The published PRD has not
yet been revised to reflect this clarification. The original Feature requests
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
