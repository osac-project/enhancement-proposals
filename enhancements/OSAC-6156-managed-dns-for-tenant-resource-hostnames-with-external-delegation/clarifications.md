# Clarification and revision log — OSAC-6158

This log records direct user direction and source interpretation. It does not
record stakeholder approval or changes to Jira.

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
