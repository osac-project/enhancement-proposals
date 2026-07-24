# Design EP Author Guide

This guide explains how to write a design enhancement proposal (EP) for
OSAC. It covers what a design EP is, how it differs from a PRD, per-section
authoring guidance, and common mistakes to avoid.

## What is a Design EP?

A design EP describes **how** a feature will be implemented — architecture,
API design, controller logic, provisioning workflows. It builds on a merged
PRD (which describes **what** and **why**) and provides enough detail for
engineering to estimate, plan, and implement.

A design EP answers:
- What components change, and how?
- What are the new or modified APIs, CRDs, and data models?
- How does the system behave on failure, and how does it recover?
- What is the test strategy?

## PRD vs Design EP

OSAC uses a two-stage enhancement process. The PRD comes first and defines
the requirements. The design EP follows and specifies the implementation.

| | **PRD** (`prd.md`) | **Design EP** (`design.md`) |
|---|---|---|
| **Audience** | Product managers, reviewers, stakeholders | Engineers, architects |
| **Focus** | User-facing capabilities and outcomes | Architecture, API fields, reconciliation logic |
| **Content** | User stories, in/out of scope, success criteria | CRD schemas, controller design, playbook parameters |
| **Lifecycle** | Merged before design work begins | Merged before implementation begins |

**Litmus test:** Could this statement change if we swapped the
implementation and kept the same user-facing behavior? If yes, it's design
detail — it belongs here, not in the PRD.

See [prd_guide.md](prd_guide.md) for the full "what belongs where" table,
the platform-vocabulary allowlist, and the PRD's own litmus test. Don't
duplicate PRD content here: a design EP's Summary and Motivation sections
should bridge from the PRD, not restate its problem statement or user
stories.

## OSAC Personas

Design EPs don't repeat persona definitions — see
[prd_guide.md](prd_guide.md#osac-personas) for the canonical table
(Cloud Provider Admin, Cloud Infrastructure Admin, Tenant Admin, Tenant
User). In a design EP, personas show up as the actors in the **Workflow
Description** section — name them explicitly when describing who triggers
each step.

## Per-Section Authoring Guidance

These apply across all sections:

- **Favor conciseness.** Long design documents don't get read. Every
  sentence should earn its place.
- **Be specific.** No vague language: name the data structure, the cache
  strategy, the error taxonomy — not "an efficient data structure" or
  "appropriate caching."
- **Bridge from the PRD, don't repeat it.** Assume the reader may not have
  read the PRD and needs enough context to understand the design
  decisions, but direct them to `prd.md` for the full requirements.
- **Keep all required headers.** If a section doesn't apply, explain why
  but don't remove it.

### YAML Frontmatter

- `title`: lowercase slug with hyphens (e.g., `networking-api`)
- `authors`: email addresses
- `creation-date` / `last-updated`: ISO date format (`yyyy-mm-dd`)
- `tracking-link`: full Jira URL
- `prd`: relative path to the PRD document (typically `prd.md`)
- `see-also` / `replaces` / `superseded-by`: usually `N/A` for new proposals

### Summary

1-2 sentences: what this design achieves and the technical approach. End
with a PRD reference — "See [PRD](prd.md) for detailed requirements."

### Motivation (Goals, Non-Goals)

2-4 paragraphs restating the problem in implementation terms for technical
reviewers. No user stories here — those are in the PRD. Goals are
design-scoped constraints on the implementation approach ("reuse the
existing controller reconciliation pattern"), not product outcomes
("tenants can create VirtualNetworks" — that's a PRD goal). Non-goals
prevent scope creep at the implementation level.

### Proposal (Workflow Description, API Extensions)

1-2 paragraphs introducing the key resources/APIs at a high level —
typically the new CRDs, gRPC services, and controller changes. Workflow
Description defines actors using OSAC personas, enumerates the steps a
user takes starting from a defined state, and is explicit about which APIs
are involved (gRPC, REST, kubectl). Use a
[Mermaid](https://github.com/mermaid-js/mermaid#readme) sequence diagram
for multi-step interactions. API Extensions names new gRPC services
(fulfillment-service), new CRDs (osac-operator), webhooks, and finalizers,
and calls out operational impact if the controller is down.

### UX Alignment

Required only when a matching `osac-ux/libs/ui-components/src/api/v1/<resource>.ts`
file exists. Complete the field-mapping table and justify any deviation
from the known anti-patterns (sub-resource actions, string-union storage
classes, K8s-internal fields, one-time secrets, RHOAI operator fields).

### Implementation Details/Notes/Constraints

This is where technical depth lives. Include proto schema snippets
following the standard object shape (`id`, `Metadata`, `<Type>Spec`,
`<Type>Status`) and the conventions in
[fulfillment-service's API.md](https://github.com/osac-project/fulfillment-service/blob/main/docs/API.md) —
spec for desired state, status for observed state, conditions for
lifecycle, declarative design with no imperative methods. Cover database
schema considerations and controller reconciliation logic (state machine,
finalizer flow), and describe integration with existing OSAC components.

### Security Considerations

Cover input validation, authentication/authorization changes, and data
exposure risks. For multi-tenant features, describe how tenant isolation
is enforced — OPA policies, namespace scoping, `osac.openshift.io/tenant`
annotation filtering. If the feature inherits the existing security model
unchanged, state that and explain why it's sufficient. Don't invent
security concerns that don't apply.

### Failure Handling and Recovery

Enumerate concrete failure modes — not generic categories. For each: what
happens, how the system recovers, what the user sees. Cover controller-side
failures (reconciliation errors, stale caches), API-side failures
(validation, database errors), and integration failures (AAP job timeouts,
network provisioning failures). Note retry behavior, idempotency
guarantees, and behavior when a controller restarts mid-reconciliation.

### RBAC / Tenancy

All new resources **must** include tenant isolation metadata:
`osac.openshift.io/tenant` for tenant scoping, `osac.openshift.io/owner-reference`
for resource hierarchy. Describe how OPA policies enforce isolation at
runtime, and note visibility constraints (can a tenant see resources from
other tenants? platform-defined resources like NetworkClass?). If no RBAC
or tenancy changes are needed: "No RBAC or tenancy changes required." with
brief justification.

### Observability and Monitoring

List new Prometheus metrics (name, type, labels, and what threshold
indicates a problem), Kubernetes events (type, reason, when it fires), and
structured log events. If none: "No new observability changes. Existing
monitoring mechanisms apply."

### Risks and Mitigations

Technical risks only — product risks belong in the PRD. Each risk needs a
concrete mitigation or an explicit "To be determined." Consider version
skew, performance bottlenecks, security exposure, backwards compatibility,
and cross-component coordination.

### Drawbacks

Steel-man the argument against the proposal. What trade-offs (maintenance
burden, API complexity, user experience) must be made, and how do we
justify them?

### Alternatives (Not Implemented)

At least one real alternative per non-trivial design decision, including
"Do nothing" where applicable. For each: brief description, pros, cons,
and the rejection reason. Be honest about trade-offs.

### Open Questions

Optional — omit entirely if none remain after drafting. Each question gets
its own numbered subsection, framed as a clear, answerable question
directed at reviewers. Design scope only — no process-level actions. This
section is transient: when a question is resolved during review, fold the
answer into the relevant section and remove the entry.

### Test Plan

*Not required until targeted at a release.* List concrete test scenarios
under Unit, Integration, and E2E sub-sections — not general strategy. Each
scenario should be specific enough that an implementer knows what to build
(e.g., "validation rejects overlapping CIDRs," not "test validation").
Reference OSAC test patterns: Ginkgo for unit/integration tests, pytest for
e2e (via osac-test-infra). Call out tricky areas explicitly (CIDR parsing,
dual-stack, concurrent reconciliation).

### Graduation Criteria

*Not required until targeted at a release.* If not yet targeting a
release: "Graduation criteria will be defined when targeting a release.
Expected stages: Dev Preview -> Tech Preview -> GA based on production
deployment feedback." If targeting a release, define maturity levels and
success signals.

### Upgrade / Downgrade Strategy, Version Skew Strategy, Support Procedures

For a new API with no upgrade impact: "This is a new API with no upgrade
impact. Downgrade requires deleting all instances of the new resources
before reverting." For changes to existing APIs, describe migration steps
and version-skew handling between fulfillment-service and osac-operator.
Support Procedures should describe failure-detection symptoms (events,
metrics, alerts), how to disable the feature and the consequences, and
recovery behavior.

### Infrastructure Needed

Usually "None." If needed, specify new test infrastructure, repos, or CI
changes.

## Common Mistakes

### Vague implementation

The design-EP equivalent of PRD design leakage. Symptoms: no proto
schemas, hand-waving on hard parts ("handle edge cases appropriately," "the
controller will handle provisioning"), and generic risks ("things might
break"). **Fix:** name the data structures, error codes, and validation
rules; state specific risks with concrete mitigations ("concurrent subnet
allocation may cause CIDR overlap" with "use optimistic locking with
resource version").

### Missing PRD reference

Every design EP needs a `prd:` frontmatter field or an explicit link to
`prd.md`. A design EP with no PRD reference reads as ungrounded — reviewers
can't tell whether the implementation matches agreed requirements.

### Reintroducing user stories

User stories belong in the PRD, not the design EP. If a design EP
restates them, it's duplicating content that will drift out of sync with
the PRD as requirements evolve.

### Unbounded scope, no alternatives

A design EP with no non-goals and "Alternatives: none considered" signals
the author hasn't scoped the boundaries of the change. Every non-trivial
design decision should have at least one real alternative and a stated
rejection reason.

### Thin test plans

"Unit and integration tests will be added" gives an implementer nothing to
build from. Specify what's tested (validation logic, state transitions,
error paths) and how (kind cluster, mocked backends).

## Workflow

### Using the `/design` skill (recommended)

If you are using an AI-assisted development tool (Claude Code, Cursor, or
similar), the `/design` workflow automates design EP creation:

1. **`/design:ingest`** with your Jira ticket (after the PRD is merged) to
   gather design context
2. **`/design:draft`** to generate the design document from the template
3. **`/design:publish`** to create a PR on enhancement-proposals

The skill produces a design EP that follows
[design_template.md](design_template.md) and can be reviewed with the
`design-review` skill.

### Manual workflow

1. Confirm the PRD is merged in the same `enhancements/OSAC-NNNN-feature-slug/`
   directory (see [CONTRIBUTING.md](../CONTRIBUTING.md) for the naming
   convention)
2. Copy the template: `cp guidelines/design_template.md enhancements/OSAC-NNNN-feature-slug/design.md`
3. Fill out all sections, referencing the per-section guidance above
4. Self-review against the common mistakes above
5. Create a pull request against `main`

## Review

Design EPs are reviewed against four criteria: architecture (OSAC pattern
compliance, tenant isolation, dependency clarity), feasibility
(implementation depth, proto schemas, risk quality), scope (boundary
clarity, PRD reference, dimension coverage), and testability (test
strategy specificity, graduation criteria). Use the `design-review` skill
for a detailed automated assessment before submitting your PR.

## External References

- [OpenShift Enhancements](https://github.com/openshift/enhancements) —
  this template's structure and section conventions descend from OpenShift's
  own enhancement-proposal process
