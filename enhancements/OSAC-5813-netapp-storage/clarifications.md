# Clarification Log — OSAC-5813

## Status

- Existing conversation and research provide the clarification input for draft.
- Draft authorized by the user on 2026-10-05.
- Revised on 2026-10-05: BMaaS is explicitly out of scope by user direction
  (R2.Q1 / D3), superseding the original four-service ticket baseline.
- Detailed review adds three owned open questions: FC contingency, FC QE access,
  and NetApp retained-volume/recovery procedure. BMaaS scope and the 0.4 Tech
  Preview target are resolved; FC acceptance and Enclave validation gate delivery.

## Round 1 — Scope, precedents, and parallel work

### R1.Q1: How much documentation is needed?

#### Answer

The user requests the lightest useful PRD and design, following VAST/Pure
examples and focusing on NetApp differences.

#### Impact

Use OSAC's six-section PRD format and reference shared storage contracts.
Describe user-visible outcomes; reserve architecture and API schemas for design.

#### Decision (D1)

Keep the documents concise and focused on NetApp-specific additions. This
initial decision changed documentation depth, not the ticket's four-service
baseline. Its workload scope is superseded by R2.Q1 / D3 below.

### R1.Q2: Do the four common lifecycle topics need fresh decisions?

#### Answer

The user asks to consult VAST/Pure PRDs before reopening prerequisites,
ownership, workload scope, or teardown. The source comparison is recorded in
research section 14. Existing provider-prepared connectivity, per-tenant
isolation, cluster/backend lifecycle separation, and safe offboarding supply
the baseline. NetApp's ticket already requests automatic per-tenant SVM creation.

#### Impact

Carry shared policies forward with source links and reference shared attachment
requirements for direct consumers. The initial CaaS, VMaaS, BMaaS, and VaaS
baseline is superseded by R2.Q1 / D3. Do not infer that Pure's NFS scope or
pre-created Realm model defines NetApp's FC scope or SVM creation authority.

### R1.Q3: Must host-registration research finish before drafting?

#### Answer

The user explicitly directs PRD work to proceed in parallel with the ongoing
OSAC-5807 investigation.

#### Impact

Record a design/delivery dependency owned by the Storage Working Group, with
FC validation required before declaring the feature operational.

#### Decision (D2)

OSAC-5807 does not block PRD drafting. The draft does not select a registration
mechanism or claim that centralized FC attachment is already proven.

### R1.Q4: Is a NetApp test environment available?

#### Answer

The requested Slack investigation found an access arrangement and EPMB-1595,
an ONTAP Select license request for management-path research. It did not find a
current access-ready or FC-ready confirmation. The E2E lab was explicitly
reported to lack FC, and Select does not support FC. Sources are in research
section 15. After receiving these findings, the user authorizes the PRD draft.

#### Impact

Separate management experiments from FC acceptance evidence. Track instance
access through the Storage Working Group/partner workstream and real FC test
infrastructure through the Storage Working Group/QE workstream.

### R1.Q5: What milestone is supported by the sources?

#### Answer

The ticket's structured fixVersion is **0.4 (Tech Preview)**, with a Jira version
release date of 2026-10-30. The initial capture missed these fields; the BMaaS
source recheck corrected this omission. The storage workstream's
[2026-10-01 statement](https://redhat-internal.slack.com/archives/C0B6USDQ85S/p1790861546517999)
explicitly targets NetApp support for Developer Preview. These are source-derived
planning inputs, not new commitments from the user.

#### Impact

Resolved during Round 3: use Jira's **OSAC 0.4 — Tech Preview** target, reverified
on 2026-10-05. Keep the version date distinct from a confirmed feature delivery
commitment.

## Round 2 — PRD review

### R2.Q1: Should this feature include BMaaS storage?

#### Answer

The user reports that OSAC currently has no BMaaS storage support and directs
the NetApp PRD to exclude it, following the vendor onboarding precedents. BMaaS
storage would belong to a separate future feature. This is an explicit product
scope decision; the user's implementation-status statement was not independently
verified during this revision.

#### Impact

Remove BMaaS from the problem statement, in-scope service list, and consumption
table. Add an explicit out-of-scope boundary. Retain CaaS, VMaaS, and VaaS and
the shared attachment requirements for the remaining consumption paths.

#### Decision (D3)

BMaaS storage integration is out of scope for OSAC-5813's PRD. This user
instruction supersedes the ticket's four-service baseline and the initial scope
recorded under D1 and R1.Q2. No new BMaaS feature ticket is created by this
decision.

### R2.Q2: Does the PRD account for Enclave installation impact?

#### Answer

The user asks whether the required Enclave assessment was performed. The
project's feature dimensions and Enclave Wizard pipeline require this assessment
when a feature adds or changes installation settings. The initial draft described
generic prerequisites but omitted an explicit Wizard-facing installation outcome.

The current installer includes CSI deployment configuration, but its vendor
configuration objects do not define typed Trident fields. Trident controller and
node options exist in the owning charts and are disabled by default. This is
configuration scaffolding, not verified Wizard support. The consuming Enclave
plugin version and actual control rendering were not inspected.

#### Impact

Add the user-facing installation outcome, Cloud Infrastructure Admin story,
documentation coverage, and installer/Enclave delivery dependency. These record
the existing project installation contract; they do not assert that the user
approved a new custom Wizard workflow.

Design identifies which NetApp parameters belong to installation. If installer
values change, decomposition follows the documented installer -> Enclave plugin
-> Wizard verification sequence. Runtime backend/tier administration remains
the existing OSAC UI/CLI/API workflow. Actual Wizard readiness must be verified
before delivery.

## Round 3 — Detailed PRD review

### R3.Q1: How should authoring tags, milestone, and open questions appear?

#### Answer and impact

The user requests a finished reader-facing document without unexplained workflow
tags and asks for explicit Open Questions and risk coverage. The old Clarify
markers were source references to this log, not unanswered questions. Remove
them from the PRD and preserve traceability here and in the requirements capture.

Jira's fixVersion, reverified on 2026-10-05, resolves the target to OSAC 0.4 Tech
Preview. D3 already excludes BMaaS. Neither is a remaining open question.

#### Decision (D4)

Follow the user's requested reader-facing format: remove inline authoring tags
and add Open Questions and compact Risks sections. This explicitly overrides
the project's default six-section/inline-marker convention for this document.

### R3.Q2: Which failure outcomes and infrastructure tasks must be explicit?

#### Answer and impact

The user requests actionable failure visibility for infrastructure and provider
administrators and tenant users. Add documented ONTAP privilege/host/HBA/zoning
prerequisites, FC-operation/host diagnostics for infrastructure administrators,
management-registration and SVM-creation failures for provider administrators,
and pending/failed attachment/mount status for tenants. Failed onboarding remains
not ready; corrected retries must not duplicate tenant allocations.

Management API reachability is not evidence of FC fabric readiness. The revision
keeps registration validation and connected-host FC consumption distinct, and
does not introduce switch automation or promise a diagnosis unavailable from
the observed operation. Diagnostics must remain safe for the viewer.

### R3.Q3: What does safe offboarding mean?

#### Answer and impact

The user allows references to established VAST/Pure contracts instead of a new
cleanup design. Link OSAC-23 and OSAC-2117 and retain OSAC-4884 attachment guards.
Cluster cleanup precedes backend cleanup; remaining active/retained volumes or
attachments block owned SVM deletion. Detachment alone does not permit deletion
of retained data. Success requires owned resources and tenant credential entries
removed and previous tenant access invalidated. Failure blocks completion.

NetApp's retained-volume release and partial-cleanup recovery procedure, including
any timing/credential sequencing needed to satisfy those invariants, remains
owned OQ-3. The PRD does not invent a grace period or change retention policy.

### R3.Q4: What verification and VaaS outcomes are required?

#### Answer and impact

Replace vague deployed verification with QE-owned automated E2E on a real
FC-capable ONTAP deployment and connected hosts. Cases cover all three consumption
paths and workload I/O, cross-tenant isolation, representative management/SVM/FC
failures and retry, guarded cleanup, VAST/NetApp tier coexistence, and Enclave
validation/installation. Manual experiments supplement this required evidence.
Implementation-level tests remain DEV-owned under the integration-testing policy.

VaaS has an explicit independent-volume story using shared authorized VM
attachment. The review's illustrative outside-CaaS/VMaaS wording does not expand
supported consumers: BMaaS remains excluded and direct CaaS node attachment is
not introduced.

### R3.Q5: Which questions and risks actually remain open?

#### Answer and impact

OQ-1 asks the Storage Working Group/Feature owner for a supported FC contingency
or milestone adjustment if OSAC-5807 cannot establish the path in time. No
fallback or scope reduction is agreed. OQ-2 asks the Storage Working Group,
partner workstream, and QE for an approved FC array/host access plan. OQ-3 asks
the Storage Working Group/Core-secrets workstream for retained-volume and failed
cleanup recovery details under existing safeguards. Each has status, owner, and
delivery impact in the PRD. Risk notes describe unproven FC delivery and missing
FC acceptance infrastructure rather than reopening resolved scope decisions.

### R3.Q6: How are mixed providers, credentials, and Enclave bounded?

#### Answer and impact

The user asks to address a tenant with VAST and NetApp tiers. The revision makes
existing tier-selection semantics explicit and requires coexistence verification;
it is an intended compatibility outcome, not a claim that NetApp is implemented
or tested today. Each volume uses its selected tier's provider.

The user allows credential lifecycle to be an assumption or exclusion. Keep
existing central credential handling as the baseline and exclude new rotation
or expiry-renewal automation specific to NetApp. Onboarding/offboarding credential
integration and safe expiry/authentication failure visibility remain covered.

The user emphasizes that the installer/Enclave path gates delivery. State that
feature delivery is blocked until required NetApp inputs are configurable and
validated through the Wizard with supported versions. Keep the infrastructure
administrator story user-facing; implementation fields belong in design.
