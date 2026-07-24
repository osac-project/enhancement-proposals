---
title: neat-enhancement-idea
authors:
  - TBD
creation-date: yyyy-mm-dd
last-updated: yyyy-mm-dd
tracking-link: # link to the tracking ticket (for example: Jira issue) that corresponds to this enhancement
  - TBD
prd: # relative path to the PRD document for this enhancement
  - "prd.md"
see-also:
  - "/enhancements/this-other-neat-thing"
replaces:
  - "/enhancements/that-less-than-great-idea"
superseded-by:
  - "/enhancements/our-past-effort"
---

To get started with this template:
1. **Create a directory.** Create a directory inside `enhancements/` using
   the naming convention `OSAC-NNNN-feature-slug` (see
   [CONTRIBUTING.md](../CONTRIBUTING.md)) — the same directory your `prd.md`
   already lives in, or will live in.
1. **Make a copy of this template.** Copy this file into that directory
   as `design.md`.
1. **Fill out the metadata at the top.** The embedded YAML document is
   checked by the linter. The `prd` field should point to the PRD file
   in the same directory (typically `prd.md`).
1. **Fill out the "overview" sections.** The Summary and Motivation
   sections should be brief — detailed requirements live in the PRD.
   Focus on the technical approach and design rationale.
1. **Consult the author guide.** See
   [design_guide.md](design_guide.md) for per-section authoring guidance,
   the PRD vs design EP boundary, OSAC personas, and examples.
1. **Create a PR.** Assign it to folks with expertise in that domain to help
   sponsor the process.
1. **Merge after reaching consensus.** Merge when there is consensus
   that the design is complete and all reviewer questions have been
   answered so that work can begin. Come back and update the document
   if important details (API field names, workflow, etc.) change
   during code review.
1. **Keep all required headers.** If a section does not apply to an
   enhancement, explain why but do not remove the section — reviewers
   and the automated EP review check for this.

**Using the `/design` skill (recommended):** If you are using an AI-assisted
development tool (Claude Code, Cursor, or similar), use the `/design`
workflow instead of copying this template manually. Run `/design:ingest`
with your Jira ticket (after the PRD is merged) to start the guided flow:
ingest, draft, publish. The skill produces a design document that follows
this template.

See [README.md](../README.md) for background behind these instructions.

# Neat Enhancement Idea

This is the title of the enhancement. Keep it simple and descriptive. A good
title can help communicate what the enhancement is and should be considered as
part of any review.

The YAML `title` should be lowercased and spaces/punctuation should be
replaced with `-`.

## Summary

One to two sentences describing the technical approach proposed by this
enhancement. Reference the PRD for full requirements context:
"See [PRD](prd.md) for detailed requirements."

## Motivation

Restate the problem in implementation terms for technical reviewers. Describe
the current system's limitations and why this approach is proposed. Keep brief
— the PRD contains the full problem statement, user stories, and acceptance
criteria. This section bridges from the PRD for readers who need implementation
context.

### Goals

Design-scoped goals that constrain the implementation approach. These are
not product outcomes (those are in the PRD) but implementation constraints:
e.g., "Reuse the existing controller reconciliation pattern" or "Support
both IPv4 and dual-stack from the initial implementation."

### Non-Goals

What is out of scope for this design. Listing non-goals helps to
focus discussion and make progress. Highlight anything that is being
deferred to a later phase of implementation that may call for its own
enhancement.

## Proposal

This section should explain what the proposal actually is. Enumerate
*all* of the proposed changes at a *high level*, including all of the
components that need to be modified and how they will be
different. Include the reason for each choice in the design and
implementation that is proposed here.

To keep this section succinct, document the details like API field
changes, new images, and other implementation details in the
**Implementation Details** section and record the reasons for not
choosing alternatives in the **Alternatives** section at the end of
the document.

### Workflow Description

Explain how the user will use the feature. Be detailed and explicit.
Describe all of the actors, their roles, and the APIs or interfaces
involved. Define a starting state and then list the steps that the
user would need to go through to trigger the feature described in the
enhancement. Optionally add a
[mermaid](https://github.com/mermaid-js/mermaid#readme) sequence
diagram.

Use sub-sections to explain variations, such as for error handling,
failure recovery, or alternative outcomes.

### API Extensions

API Extensions are CRDs, admission and conversion webhooks, aggregated API servers,
and finalizers, i.e. those mechanisms that change the API surface and behaviour.

- Name the API extensions this enhancement adds or modifies.
- Does this enhancement modify the behaviour of existing resources, especially those owned
  by other parties than the authoring team (including upstream resources), and, if yes, how?
  Please add those other parties as reviewers to the enhancement.

## UX Alignment

*Skip this section if `osac-ux/libs/ui-components/src/api/v1/<resource>.ts` does not exist.*

If a matching `@temp-api` file exists — whether this EP covers a new resource or
adds/changes fields on an existing one — complete the table below. This section is
reviewed alongside the proto design to ensure the backend ships fields the UI can
consume without a migration pass.

| UI field (`@temp-api` TypeScript) | Proto field (this EP) | Notes / deviation |
|---|---|---|
| `spec.fieldName` | `spec.field_name` | Direct mapping |
| `spec.storageClass` | `spec.storage_tier_id` | Deviation: UI uses string enum; proto references StorageTier resource |

List any deviations from the known anti-patterns (sub-resource actions,
string-union storage classes, K8s-internal fields, one-time secrets, RHOAI
operator fields). Each deviation requires a justification.

After the backend ships and `pnpm gen-types` is run in osac-ux, the UI
migration diff should be limited to the deviations documented here.

### Implementation Details/Notes/Constraints

What are some important details that didn't come across above in the
**Proposal**? Go in to as much detail as necessary here. This might be
a good place to talk about core concepts and how they relate. While it is useful
to go into the details of the code changes required, it is not necessary to show
how the code will be rewritten in the enhancement.

### Security Considerations

Cover authentication and authorization changes, data exposure risks, and
input validation requirements. If the feature inherits the existing security
model without changes, state that and explain why it is sufficient.

For multi-tenant features, describe how tenant isolation is enforced
(e.g., OPA policies, namespace scoping, annotation-based filtering).

### Failure Handling and Recovery

Enumerate concrete failure modes for the proposed design. For each:
what happens, how the system recovers, and what the user observes.

Cover controller reconciliation failures, API-side errors, and
integration failures (e.g., AAP job failures, network provisioning
timeouts). Note retry behavior and idempotency guarantees.

### RBAC / Tenancy

Describe role-based access rules, tenant isolation boundaries, and
visibility constraints introduced or modified by this enhancement.

For new resources, specify the required tenant isolation metadata:
`osac.openshift.io/tenant` and `osac.openshift.io/owner-reference`
annotations, and how they are enforced.

If no RBAC or tenancy changes are required, state so with brief
justification.

### Observability and Monitoring

List new metrics, Kubernetes events, alerts, or structured log events
introduced by this enhancement. Describe what each metric measures and
what threshold would indicate a problem.

If no new observability changes are needed, state: "No new observability
changes. Existing monitoring mechanisms apply."

### Risks and Mitigations

What are the risks of this proposal and how do we mitigate. Think broadly. For
example, consider both security and how this will impact the larger
ecosystem.

How will security be reviewed and by whom?

Consider including folks that also work outside your immediate sub-project.

### Drawbacks

The idea is to find the best form of an argument why this enhancement should
_not_ be implemented.

What trade-offs (technical/efficiency cost, user experience, flexibility,
supportability, etc) must be made in order to implement this? What are the reasons
we might not want to undertake this proposal, and how do we overcome them?

Does this proposal implement a behavior that's new/unique/novel? Is it poorly
aligned with existing user expectations?  Will it be a significant maintenance
burden?  Is it likely to be superseded by something else in the near future?

## Alternatives (Not Implemented)

Similar to the `Drawbacks` section the `Alternatives` section is used
to highlight and record other possible approaches to delivering the
value proposed by an enhancement, including especially information
about why the alternative was not selected.

## Open Questions [optional]

This is where to call out areas of the design that require closure before deciding
to implement the design.  For instance,
 > 1. This requires exposing previously private resources which contain sensitive
  information.  Can we do this?

## Test Plan

**Note:** *Section not required until targeted at a release.*

List concrete test scenarios for each test type, with enough detail that an
implementer knows what to build.

### Unit Tests

List specific behaviors to unit-test (e.g., "validation rejects overlapping
CIDRs", "status condition transitions from Pending to Provisioned").

### Integration Tests

List scenarios that exercise the component with its real dependencies in a
kind cluster (e.g., "creating a VirtualNetwork reconciles the namespace and
network resources", "deleting a parent resource cascades to children").
Integration tests are the primary test layer for controller and server logic.

### E2E Tests

List user-facing workflows that span multiple components (e.g., "tenant
creates a ComputeInstance attached to a Subnet and reaches it via PublicIP").
Reference osac-test-infra pytest patterns.

Call out anything tricky to test: CIDR parsing, dual-stack, concurrent
reconciliation, AAP job coordination, etc.

## Graduation Criteria

**Note:** *Section not required until targeted at a release.*

Define graduation milestones.

These may be defined in terms of API maturity, or as something else. Initial proposal
should keep this high-level with a focus on what signals will be looked at to
determine graduation.

Consider the following in developing the graduation criteria for this
enhancement:

- Maturity levels
  - [`alpha`, `beta`, `stable` in upstream Kubernetes][maturity-levels]
  - `Dev Preview`, `Tech Preview`, `GA` in OpenShift
- [Deprecation policy][deprecation-policy]

Clearly define what graduation means by either linking to the [API doc definition](https://kubernetes.io/docs/concepts/overview/kubernetes-api/#api-versioning),
or by redefining what graduation means.

In general, we try to use the same stages (alpha, beta, GA), regardless how the functionality is accessed.

[maturity-levels]: https://git.k8s.io/community/contributors/devel/sig-architecture/api_changes.md#alpha-beta-and-stable-versions
[deprecation-policy]: https://kubernetes.io/docs/reference/using-api/deprecation-policy/

**If this is a user facing change requiring new or updated documentation in [openshift-docs](https://github.com/openshift/openshift-docs/),
please be sure to include in the graduation criteria.**

**Examples**: These are generalized examples to consider, in addition
to the aforementioned [maturity levels][maturity-levels].

### Removing a deprecated feature

- Announce deprecation and support policy of the existing feature
- Deprecate the feature

## Upgrade / Downgrade Strategy

If applicable, how will the component be upgraded and downgraded? Make sure this
is in the test plan.

Consider the following in developing an upgrade/downgrade strategy for this
enhancement:
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to keep previous behavior?
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to make use of the enhancement?

Upgrade expectations:
- Each component should remain available for user requests and
  workloads during upgrades. Ensure the components leverage best practices in handling [voluntary
  disruption](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/). Any exception to
  this should be identified and discussed here.
- Micro version upgrades - users should be able to skip forward versions within a
  minor release stream without being required to pass through intermediate
  versions - i.e. `x.y.N->x.y.N+2` should work without requiring `x.y.N->x.y.N+1`
  as an intermediate step.
- Minor version upgrades - you only need to support `x.N->x.N+1` upgrade
  steps. So, for example, it is acceptable to require a user running 4.3 to
  upgrade to 4.5 with a `4.3->4.4` step followed by a `4.4->4.5` step.
- While an upgrade is in progress, new component versions should
  continue to operate correctly in concert with older component
  versions (aka "version skew"). For example, if a node is down, and
  an operator is rolling out a daemonset, the old and new daemonset
  pods must continue to work correctly even while the cluster remains
  in this partially upgraded state for some time.

Downgrade expectations:
- If an `N->N+1` upgrade fails mid-way through, or if the `N+1` cluster is
  misbehaving, it should be possible for the user to rollback to `N`. It is
  acceptable to require some documented manual steps in order to fully restore
  the downgraded cluster to its previous state. Examples of acceptable steps
  include:
  - Deleting any CVO-managed resources added by the new version. The
    CVO does not currently delete resources that no longer exist in
    the target version.

## Version Skew Strategy

How will the component handle version skew with other components?
What are the guarantees? Make sure this is in the test plan.

Consider the following in developing a version skew strategy for this
enhancement:
- During an upgrade, we will always have skew among components, how will this impact your work?
- Does this enhancement involve coordinating behavior in the control plane and
  in the kubelet? How does an n-2 kubelet without this feature available behave
  when this feature is used?
- Will any other components on the node change? For example, changes to CSI, CRI
  or CNI may require updating that component before the kubelet.

## Support Procedures

Describe how to
- detect the failure modes in a support situation, describe possible symptoms (events, metrics,
  alerts, which log output in which component)

- disable the API extension (e.g. remove MutatingWebhookConfiguration `xyz`, remove APIService `foo`)

  - What consequences does it have on the cluster health?
  - What consequences does it have on existing, running workloads?
  - What consequences does it have for newly created workloads?

- Does functionality fail gracefully and will work resume when re-enabled without risking
  consistency?

## Infrastructure Needed [optional]

Use this section if you need things from the project. Examples include a new
subproject, repos requested, github details, and/or testing infrastructure.
