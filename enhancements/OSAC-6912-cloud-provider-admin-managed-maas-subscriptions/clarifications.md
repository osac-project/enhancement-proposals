# Clarification Log — OSAC-6912

## Status

- Rounds completed: 12
- Open gaps: 1
- Exit criteria met: No

## Round 1 — Access model, scope, fields, interfaces, and feedback

### R1.Q1: Subscription beneficiaries and object visibility

The issue says only Cloud Provider Admins can view or manage Subscription
objects, while the candidate model names users and groups. Should a
Subscription grant model access to its named tenant users/groups even though
they cannot see or manage the Subscription object?

#### Answer

Yes. The Cloud Provider Admin manages the object; entitled users/groups may
benefit from its model access.

#### Impact

Separate Subscription administration permissions from the model-access
entitlement granted to its subjects.

#### Decision (D1)

Only Cloud Provider Admins can directly view or manage Subscription objects;
eligible users/groups may receive model access through a Subscription.

---

### R1.Q2: Organization scope

Should a Subscription apply to one tenant organization, be provider-wide, or
cover multiple explicitly selected tenant organizations?

#### Answer

Provider-wide.

#### Impact

The feature is not scoped to one tenant organization. The meaning of
provider-wide for eligible identities and tenant isolation needs clarification.

#### Decision (D2)

Subscription scope is provider-wide.

---

### R1.Q3: First-release entitlement information

Which candidate controls are required in the first release: eligible users and
groups, model selection, token limits/unlimited access, priority, organization
and attribution metadata, inference priority, or guardrails?

#### Answer

Users and groups, and model selection.

#### Impact

These are confirmed initial capabilities. Token-allowance behavior remains
unresolved because the source issue also mentions usage allowances.

#### Decision (D3)

The first release must identify eligible users/groups and selected models.

---

### R1.Q4: Cloud Provider Admin management interfaces

Which interfaces should support Subscription management in the first release?

#### Answer

UI, API, and CLI.

#### Impact

The initial feature must support all three interfaces for Cloud Provider Admins.

#### Decision (D4)

UI, API, and CLI are in scope for Subscription management.

---

### R1.Q5: Lifecycle status

What should Cloud Provider Admins observe after create/update/delete?

#### Answer

Pending, applied, and failed states, with per-model status.

#### Impact

The UI/API/CLI should expose overall lifecycle progress and model-specific
results. The user-facing meaning of “applied” and failure handling still need
clarification.

#### Decision (D5)

Subscription status must support Pending, Applied, and Failed, including
per-model status.

---

## Round 2 — Entitlement controls and lifecycle

### R2.Q1: Token limits

The first-release controls selected include per-model token limits. Should a
model entitlement also support unlimited access as an alternative to a token
budget?

#### Answer

Per-model token limits are required. Unlimited access was not specified.

#### Impact

Token budgets are in scope. Whether unlimited access is a supported alternative
remains open.

---

### R2.Q2: Eligible identity scope

For a provider-wide Subscription, which identities can be assigned: provider
workforce identities only, or identities from tenant organizations as well?

#### Answer

Provider identities only.

#### Impact

Tenant identities are not Subscription beneficiaries. The exact provider
identity categories still need definition.

#### Decision (D6)

Only Cloud Provider identities can be assigned as Subscription beneficiaries;
Tenant Admin and Tenant User identities are not eligible. Superseded by D15.

---

### R2.Q3: Additional first-release controls

Should priority, organization/metering attribution, inference priority, and
guardrails be included in the first release?

#### Answer

Priority and attribution are required. Inference priority and guardrails were
not selected.

#### Impact

Priority and attribution are in scope. Inference priority and guardrails are not
required for this Feature's initial scope.

#### Decision (D7)

Include subscription priority and organization/metering attribution; do not
require inference priority or guardrails in the initial scope.

---

### R2.Q4: Applied status

What should Applied communicate to the Cloud Provider Admin?

#### Answer

The entitlement is active for its selected models and subjects.

#### Impact

Applied should indicate that the model access granted by the Subscription is
effective.

#### Decision (D8)

Applied means the Subscription's entitlement is active.

---

### R2.Q5: Revocation behavior

What should happen to existing access when a subscription is updated/deleted or
a user/model is removed?

#### Answer

Revoke promptly.

#### Impact

Updates/removals must not leave stale access in place beyond the time needed to
apply the change.

#### Decision (D9)

Removing an entitled subject or model, or deleting a Subscription, should
promptly revoke the affected access.

---

## Round 3 — Allowances, identity scope, organization scope, and failure detail

### R3.Q1: Unlimited access

Per-model token limits are in scope. Should a model entitlement also allow
unlimited access as an alternative to a token budget?

#### Answer

Token budgets only.

#### Impact

Each model entitlement requires a token budget; unlimited access is not part of
the initial scope.

#### Decision (D10)

The initial scope supports token budgets only, not unlimited model access.

---

### R3.Q2: Eligible provider identities

Which identities count as eligible provider identities? Subscription management
is Cloud Provider Admin-only, but could other provider personas be beneficiaries?

#### Answer

Cloud Provider Admins only.

#### Impact

Only Cloud Provider Admin identities/groups are eligible beneficiaries.
Cloud Infrastructure Admins and tenant identities are not.

#### Decision (D11)

Only Cloud Provider Admin identities/groups may receive access through a
Subscription.

---

### R3.Q3: Organization association

Given the subscription was previously described as provider-wide, what is the
purpose of its organization association?

#### Answer

It scopes the entitlement.

#### Impact

The organization association limits entitlement scope, which conflicts with the
earlier provider-wide scope decision. Resolve this before drafting.

---

### R3.Q4: Failure details

What should a Failed or per-model failure show to a Cloud Provider Admin?

#### Answer

An actionable reason.

#### Impact

Failed status should identify the affected model and provide a user-actionable
reason or next step.

#### Decision (D12)

Failures must expose an actionable reason to the Cloud Provider Admin.

---

## Round 4 — Management scope versus entitlement scope

### R4.Q1: Meaning of provider-wide

Which scope should the PRD use: provider-wide management with each subscription
scoped to an associated organization, or a provider-wide entitlement?

#### Answer

Cloud Provider Admins manage subscriptions at provider scope; each subscription's
entitlement is organization-scoped.

#### Impact

This distinguishes who manages Subscription objects from which organization the
subscription's access applies to. The kind of organization and eligible
beneficiary identities remain open.

#### Decision (D13)

Management is provider-wide; each subscription entitlement is scoped to its
associated organization. This supersedes the earlier interpretation of D2.

---

## Round 5 — Organization-scoped entitlement

### R5.Q1: Associated organization

For an organization-scoped entitlement, what does the Subscription’s associated
organization represent?

#### Answer

An OSAC Tenant.

#### Impact

Each Subscription is scoped to a customer Tenant, while Subscription
administration remains provider-wide.

#### Decision (D14)

Each Subscription is associated with one OSAC Tenant.

---

### R5.Q2: Eligible identities

Who may receive model access from an organization-scoped Subscription?

#### Answer

Users/groups belonging to the associated Tenant.

#### Impact

Tenant users/groups may be entitled to model access, but Tenant Admins and
Tenant Users still cannot view or manage the Subscription object.

#### Decision (D15)

Eligible beneficiaries are users/groups belonging to the associated OSAC
Tenant. This supersedes D11; only Cloud Provider Admins may manage the object.

---

## Round 6 — Milestone, revocation, and group selection

### R6.Q1: Target milestone

What target milestone should the PRD state? The Jira currently has no fix
version.

#### Answer

Backlog.

#### Impact

The PRD has no target release committed yet.

#### Decision (D16)

Target milestone is Backlog.

---

### R6.Q2: Revocation timing

What user-visible timing should “revoke promptly” specify?

#### Answer

Within one minute.

#### Impact

Access removed by a Subscription change should stop being effective within one
minute.

#### Decision (D17)

Subscription access revocation must take effect within one minute.

---

### R6.Q3: Attribution metadata and group selection

Besides the associated OSAC Tenant, what attribution data is required? The same
question asked how the Cloud Provider Admin selects eligible identities.

#### Answer

“Groups. Type each group name and choose the Add Group button. Members of these
groups can use the models.”

#### Impact

This specifies a group-selection interaction and confirms group members receive
model access. It does not specify whether individuals can be assigned directly
or whether cost-center/label attribution is required.

#### Decision (D18)

The Cloud Provider Admin must be able to add group names; members of selected
groups can use the models allowed by the Subscription.

---

## Round 7 — Subject and attribution details

### R7.Q1: Direct user assignment

Should Cloud Provider Admins assign individual users directly, or are groups
the only eligible subjects?

#### Answer

Groups only.

#### Impact

Cloud Provider Admins select groups; individual users are eligible only through
membership in a selected group.

#### Decision (D19)

Groups are the only assignable Subscription subjects.

---

### R7.Q2: Attribution data

Does the associated OSAC Tenant provide all required attribution, or should the
first release also capture cost-center values and/or labels?

#### Answer

Tenant association only.

#### Impact

No separate cost-center or label attribution is required in the initial scope.

#### Decision (D20)

The associated OSAC Tenant is the only required attribution field; cost-center
and label metadata are not required in the initial scope.

---

## Round 8 — Model dependency and audit history

### R8.Q1: Model selection dependency

Should a Subscription select only models already registered and available in
OSAC's MaaS catalog?

#### Answer

Registered models only.

#### Impact

Subscription creation depends on selected models already being registered;
model deployment and placement remain out of scope.

#### Decision (D21)

Subscriptions may reference only already-registered MaaS models.

---

### R8.Q2: Audit history

Do Cloud Provider Admins need a separate audit history of who created,
changed, or deleted a Subscription?

#### Answer

Standard metadata only.

#### Impact

No separate Subscription audit-history view is required; current creator and
timestamps are sufficient.

#### Decision (D22)

Standard resource metadata is sufficient for the initial scope; no separate
change-history capability is required.

---

## Round 9 — Group and individual-user subjects

### R9.Q1: Supporting RHOAI subscription subjects

A reviewer noted that the MaaS subscription contract supports both group-based
and user-based subjects. Should OSAC allow direct Tenant-user assignment as an
exception to the standard group-based path, and may a Subscription include both
groups and individual users?

#### Answer

Keep group-based assignment and allow direct assignment to individual Tenant
users for exceptions. A Subscription may include both groups and users.

#### Impact

The PRD must cover group and direct user assignment, and OSAC must resolve both
group membership and individually selected Tenant users.

#### Decision (D23)

Subscription subjects may include groups and individual users belonging to the
associated Tenant, including both types on one Subscription. Groups are the
standard assignment path; direct user assignment is available for exceptions.
This supersedes D19's group-only restriction and aligns with D15's eligible
Tenant-user and group scope.

---

## Round 10 — Token rate-limit windows

### R10.Q1: Multiple windows per model

Should a Subscription allow only one token-rate-limit window per model, or may
Cloud Provider Admins configure multiple windows for the same model at once?

#### Answer

Admins should be able to configure multiple windows for the same model at once.

#### Impact

The PRD should describe multiple token-rate limits per model, each applying over
its own configured time window, rather than restricting subscriptions to an
hourly limit.

#### Decision (D24)

Cloud Provider Admins may configure multiple token-rate limits for the same
model simultaneously, with each limit applying over a specified time window.
The detailed supported window formats and validation belong in the design.

---

## Round 11 — External Tenant identities

### R11.Q1: Identity lookup and Tenant qualification

Should OSAC require Tenant users or groups to be registered or validated in
OSAC, and should Cloud Provider Admins provide the Tenant ID with each identity?

#### Answer

No. Cloud Provider Admins provide group names and user identifiers from the
Tenant's external IdP. OSAC does not look up or validate their existence or
membership. The Subscription's Tenant association supplies the scope, and OSAC
applies any Tenant qualification required by MaaS.

#### Impact

The PRD must not imply an OSAC identity directory or picker. MaaS authorization
must match the supplied identifiers against the Tenant's identity claims.

#### Decision (D25)

Tenant group names and user identifiers may be supplied without OSAC-side
existence or membership checks. Cloud Provider Admins do not provide a Tenant ID
with each identity; the Subscription's Tenant association scopes the
identifiers. The detailed MaaS representation belongs in the design.

---

## Round 12 — MaaS inference attribution

### R12.Q1: Tenant-only attribution for the default Project

Can v1 MaaS inference usage be attributed to the Tenant's default OSAC Project
using the Tenant identifier alone?

#### Answer

Pending confirmation from the Metering team.

#### Impact

The current v1 scope keeps the Tenant association as the only required
attribution. If the Tenant identifier cannot identify the default Project, the
v1 attribution requirements need to be revisited.

---

## Remaining Gaps

- Metering team to confirm whether the Tenant identifier alone can attribute
  MaaS inference usage to the Tenant's default OSAC Project for v1.
