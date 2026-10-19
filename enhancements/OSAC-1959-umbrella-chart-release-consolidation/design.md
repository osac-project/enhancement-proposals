---
title: umbrella-chart-release-consolidation
authors:
  - eerez
creation-date: 2026-09-10
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5183
prd:
  - "prd.md"
see-also:
  - "N/A"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Umbrella Chart Release Consolidation

## Summary

Consolidate OSAC's two independent umbrella-chart build/publish implementations
(`nightly-build.yaml` and the effectively-dormant `publish-osac-installer-chart.yaml`) into one,
and adopt a manifest/pointer versioning model — only the umbrella chart receives a release
version; each mono-repo component keeps its own independent version — so that the release
identity described in [the PRD](prd.md) is both meaningful and reproducible. See the PRD for the
full customer-facing problem statement.

## Motivation

Two systems doing the same job independently is a demonstrated correctness risk:
[OSAC-5178](https://redhat.atlassian.net/browse/OSAC-5178) had to fix the same
OCI-dependency-rewrite regression in both workflows separately, because a fix existed in one and
not the other with nothing structurally preventing that drift. Separately, the workflow intended
to be the official release path assumes every mono-repo component shares one literal version
number at release time — an assumption that does not hold today (the six components have
already drifted to different independent version numbers) and, as explored below, has real
correctness problems if enforced naively.

### Goals

- Reuse `nightly-build.yaml`'s existing, already-tested build/publish machinery rather than
  maintaining a second implementation.
- Make the umbrella chart's release version a real, reproducible manifest pointer, not an
  assumption that every bundled component shares that literal string.
- Preserve today's independent per-component versioning and publishing exactly as-is for
  non-release (nightly, PR, dev) use.

### Non-Goals

- Implementing upgrade execution mechanics (Helm hooks, CRD migrations) — see PRD Out of Scope.
- Changing local development or PR/CI validation's use of `file://` mono-repo-local chart
  dependencies (already correctly scoped by OSAC-5178).
- Designing or blocking on OSAC-4224's Konflux/`registry.redhat.io` release path — that work
  depends only on OSAC-5178 (merged) and can proceed independently of this design's outcome or
  timeline.

## Proposal

1. Extend `nightly-build.yaml` with an opt-in release mode (new `workflow_dispatch` inputs): a
   chosen ref/commit to build, and a human-assigned release version for the umbrella chart
   itself (replacing the auto-generated nightly suffix for that run). The assigned version must
   be validated as a real semver, must be strictly greater than the latest existing `osac/v*`
   release tag, and must not already exist — reusing or regressing a release version is rejected
   before any tagging or publishing happens, not caught after the fact. The chosen ref is
   resolved to a full, immutable commit SHA at the start of the dispatch (a moving ref like a
   branch name is not itself immutable) and that SHA is persisted as part of the release
   manifest — a rerun of the same `release_version` must build from the same persisted SHA, not
   re-resolve the ref and potentially pick up a different commit.
2. Adopt a manifest/pointer model for what a release version means (see Alternatives for the
   rejected alternative): only the umbrella chart receives the release version (e.g.
   `osac/v0.1.0`). Every mono-repo component keeps publishing under its own independent version,
   exactly as today and as nightly already does by default. The umbrella's `Chart.lock`/release
   notes (a "component versions" table already partially exists in
   `publish-osac-installer-chart.yaml`'s release-notes step today) is the authoritative,
   customer-facing record of exactly which component version a given named release contains —
   this is the mechanism that answers the PRD's "which versions does release X contain" user
   story. **This is largely a formalization of behavior that already exists, not a new
   invention**: since OSAC-5178, `nightly-build.yaml` already builds the umbrella with its own
   independent version, already resolves each component's real currently-published version via
   `oci://` (not a forced shared number), and already generates a component-versions table in
   release notes — every night. What's missing today is a deliberate, human-controlled way to
   *cut* one of these as an official release (chosen commit, chosen version, validated and
   immutable) rather than an automatically-generated nightly build, and a single implementation
   instead of two. This is a meaningful point in this option's favor relative to full
   synchronization (see Alternatives) — it extends proven, already-running behavior rather than
   requiring a genuine departure from how OSAC versions components today.
3. Once release mode is added and validated with at least one real successful dispatch, retire
   `publish-osac-installer-chart.yaml` as a separate follow-up change — not bundled into the
   same change that adds release mode, since removing production release tooling is a
   hard-to-reverse action worth its own explicit checkpoint.

### Workflow Description

**Release engineer** is the human cutting an OSAC release.

1. Decides on a target release version (e.g. `0.1.0`) and a commit to release from (typically
   `main`'s current tip).
2. Dispatches `nightly-build.yaml` in release mode with that version and ref.
3. The workflow builds and tests exactly as a normal nightly would (unit, integration, E2E
   unless explicitly skipped), but stamps the umbrella chart with the chosen version and tags it
   `osac/v0.1.0` instead of the auto-generated nightly suffix.
4. Each mono-repo component's chart/image reference in the umbrella is resolved once, at the
   start of this dispatch, to whatever that component's own currently-published version is at
   that moment — no component is force-relabeled. That resolved set is persisted as part of the
   release manifest for this specific dispatch, not re-queried on a rerun: if this exact
   `release_version` is re-dispatched later (e.g. retrying a failed run) after some component has
   independently published a newer version in the meantime, the rerun must reuse the
   already-persisted versions, not silently pick up the newer ones. A named release's contents
   must be immutable once first resolved, regardless of how many times producing it is retried.
5. The umbrella's release notes/manifest record the exact component-version combination
   included.

**Cloud Infrastructure Admin**, installing a specific release:

1. Runs `helm install osac oci://ghcr.io/osac-project/charts/osac --version 0.1.0`.
2. To determine exactly what's included, consults the GitHub Release notes for `osac/v0.1.0`
   (or the chart's own `Chart.lock`), which lists every bundled component's exact version — there
   is no expectation that any individual component will itself display "0.1.0."

**Single-component bug-fix flow (unaffected by this design):**

1. A developer fixes a bug in `osac-csi-driver`, merges to `main`.
2. They push `osac-csi-driver/vX.Y.Z` (its own next independent version) to publish it on its
   own, exactly as today.
3. The next nightly automatically picks it up, exactly as today.
4. No coordination with the release mechanism above is required unless someone specifically
   wants that fix included in a newly-cut named OSAC release.

### API Extensions

N/A — no gRPC service, CRD, admission/conversion webhook, or finalizer is added or modified.
This design only changes GitHub Actions workflow and build-script behavior.

## UX Alignment

N/A — no `osac-ux/libs/ui-components/src/api/v1/<resource>.ts` file exists for this change; it
has no UI-consumable API surface.

### Implementation Details/Notes/Constraints

- `nightly-build.yaml` currently has `concurrency: group: nightly-build, cancel-in-progress:
  true`. A release-mode dispatch must use a distinct concurrency group, with
  `cancel-in-progress: false` for that group — so a real release run can never be silently
  cancelled by the next scheduled 03:00 UTC nightly cron. Note this only gets you queueing, not
  rejection: GitHub Actions `concurrency` groups support cancel-in-progress or queue, not an
  outright reject — a second dispatch sharing the same group will queue behind the first, not be
  rejected.
  - **Grouping choice, deliberately called out rather than assumed:** keying the group on the
    chosen release version (so two *different* release versions can publish concurrently, only
    same-version dispatches serialize) is the default proposed here, since two different,
    well-formed releases publishing to different tags are genuinely independent operations. The
    alternative — one single release-mode group covering *every* release version, so at most one
    release-mode dispatch runs at all, regardless of version — trades that parallelism for a
    simpler release-engineering story ("only one release is ever in flight org-wide"). This is a
    process/policy preference as much as a technical one; recommend per-version grouping as the
    default, called out here for reviewers to weigh in on rather than settled unilaterally.
  - A second accidental dispatch of the *same* `release_version` will queue behind the first
    either way, not be rejected outright, unless the version-monotonicity check in Proposal item
    1 also runs early in the queued run and fails it (which it should, since by the time the
    queued run starts, the first run will already have published that version).
- The dependency-rewrite-to-`oci://` mechanism from OSAC-5178
  (`rewrite_umbrella_mono_repo_dependencies` / `check_umbrella_mono_repo_charts_published` in
  `osac-installer/scripts/nightly-charts.sh`) is unaffected by this design — it already
  correctly points the umbrella at whatever each component's actual currently-published version
  is, which is exactly what the manifest model needs, with no changes required there.
- A partial implementation of the rejected force-shared-version alternative already exists as of
  this writing in draft PR [osac-project/osac#898](https://github.com/osac-project/osac/pull/898)
  (held as a draft) — it should be reworked or discarded once this design is accepted.

### Security Considerations

No new secrets or credentials are introduced — release mode uses the same GHCR publish
credentials `nightly-build.yaml` already uses today. However, the *mechanical* permission model
is not the whole story here: release mode lets whoever can already dispatch
`nightly-build.yaml` (today, effectively anyone with repo write access) produce the official,
customer-installable release artifact, not just a nightly test build. Whether that's an
acceptable authorization boundary for an official release, or whether it needs a stricter gate
(e.g. a GitHub Environment with required reviewers restricted to a release-engineers group, or
restricting release mode to protected refs only) is an open question this design does not
resolve on its own — see Open Questions.

### Failure Handling and Recovery

If a release-mode dispatch's pre-flight check finds a mono-repo component not yet published at
the version the umbrella build expects, it fails loudly with the full list of what's missing
(this already exists — `check_umbrella_mono_repo_charts_published`, from OSAC-5178) rather than
proceeding with stale or `file://` dependency metadata. Recovery is to wait for or trigger that
component's own publish, then re-dispatch. No partial or corrupted release artifact should ever
be tagged/published — the workflow must fail before the tag/push step if any pre-flight check
fails.

The harder case is a failure *after* the pre-flight check passes but before the umbrella tag/push
completes — e.g. a network failure between packaging and pushing. Because the ref and component
versions are already persisted immutably at this point (see Proposal item 1 and Workflow
Description step 4), a retry of the same `release_version` naturally resumes from identical
inputs rather than re-resolving anything — this makes retries idempotent at the input level.
What this design does not yet fully specify is compensating cleanup if the umbrella's own
`osac/vX.Y.Z` git tag gets created before a later step fails (e.g. the chart push itself fails
after the tag already exists) — whether the retry logic checks for and reuses an
already-existing tag pointing at the correct persisted SHA, or whether tag creation is deferred
to the last step specifically to minimize this window, is left as an implementation detail to
resolve, not a gap in the versioning model itself.

### RBAC / Tenancy

N/A — this design affects only build/release CI tooling, not any runtime resource, tenant
isolation boundary, or access-control surface.

### Observability and Monitoring

No new metrics or alerts. The existing Slack notification (`build_slack_charts_published_summary`
in `nightly-charts.sh`) should include the release version and component-version manifest when a
release-mode run completes, reusing the existing notification path rather than adding a new one.

### Risks and Mitigations

- **Risk:** a release engineer or customer misreads "OSAC 0.1.0" as meaning every component is
  literally version 0.1.0. **Mitigation:** the release notes/manifest table must be prominent
  and consistently generated (already partially exists); customer-facing documentation must
  explicitly state that component versions are independent and must be looked up via the
  manifest, not assumed from the release number.
- **Risk:** retiring `publish-osac-installer-chart.yaml` before the new release-mode path is
  fully proven leaves no working official-release mechanism. **Mitigation:** explicitly
  sequenced as a separate, later change gated on at least one real successful release-mode
  dispatch (see Proposal, item 3).

### Drawbacks

Individual components never visibly carry the umbrella's release version number. Anyone wanting
to know "what's in OSAC 0.1.0" must consult the manifest rather than reading a single version
string off any one artifact. This is a real usability cost relative to a (naively) simpler
"everything says 0.1.0" story, traded off against avoiding the duplicate-tag and
version-ordering problems that story would otherwise create (see Alternatives).

## Alternatives (Not Implemented)

**Force every mono-repo component to also publish under the shared release version** (e.g., cut
`osac/v0.1.0` and also re-tag `fulfillment-service`, `osac-operator`, etc. at `v0.1.0`
regardless of their own current version). This was the initial direction explored for
OSAC-5183 and was partially implemented in draft PR
[osac-project/osac#898](https://github.com/osac-project/osac/pull/898). Rejected for two
concrete problems found while working through the design, not merely theoretical concerns:

1. **Duplicate artifacts.** Any component not already coincidentally at the exact target
   version would be published twice for identical content — once under its own natural next
   version, and again under the forced release version purely to satisfy the shared-label
   requirement.
2. **Version-ordering regressions.** A component's own independent version can advance past the
   chosen release number between releases (e.g. `fulfillment-service` naturally reaches
   `v0.1.5` through unrelated work, then a release wants to force it to `v0.1.0`) — publishing a
   numerically "older-looking" tag after a "newer" one already exists is confusing to humans and
   can trip up tooling that assumes tags only move forward.

**Do nothing / status quo** (keep both workflows, keep independent versioning, no unifying
release-version concept). Rejected because it doesn't address the demonstrated
duplication-of-implementation bug risk (OSAC-5178), and leaves the PRD's core customer-facing
problem — "what am I installing, what does it contain" — permanently unanswered.

**Always fully synchronize every component to one shared version** (no independent per-component
versioning at all, ever — every publish of any component, triggered by a change to just that one
component or a full release, always bumps and re-tags all six together). This is distinct from
the rejected hybrid above: it doesn't force a number onto a *second, independently-evolving*
timeline, because there is no second timeline — the shared version is the only version any
component ever has. That structurally avoids both rejection reasons above (no independent number
to duplicate against, no independent number to regress past). This is a real, established
pattern (e.g. Lerna's `fixed`/`locked` mode, as opposed to `independent` mode, which is what the
manifest/pointer proposal above amounts to), and arguably fits OSAC well: no customer ever
installs a mono-repo component independently of the umbrella bundle, so the manifest model's
main justification — preserving independently-meaningful component versions — is weaker here
than it would be for genuinely independently-consumed packages.

Not chosen as the primary proposal, for three reasons, the third more practical than the first
two: (1) it couples every component's publish cadence together — a one-line fix to
`osac-csi-driver` would mean all six components get a new tag, even the five that didn't change
(cheap re-tag/promote rather than a rebuild, but still six new tags every time); (2) it destroys
the signal an individual component's own version currently carries (how much *that specific
thing* has changed), which today's independent versioning provides and some engineering
workflows (bisecting, per-component changelogs) may still rely on; and (3) unlike the
manifest/pointer proposal above — which mostly formalizes behavior `nightly-build.yaml` already
exercises every night since OSAC-5178 — full synchronization would be a genuine departure from
how every component is versioned and published today, requiring changes throughout
`publish-charts.yaml` and each component's own tag-triggered release path, not just the umbrella
build. Given OSAC's components are already always built, tested, and shipped together as one
coupled unit, the coupling cost in (1) and (2) may be smaller in practice than it looks — this is
flagged as a live open question for reviewers, not a settled rejection, but reason (3) means it's
a larger, riskier change to actually implement than the primary proposal.

## Open Questions

1. Exact long-term location for the "component versions" manifest — reuse and formalize the
   existing release-notes markdown table, or introduce a machine-readable manifest (e.g. a
   JSON/YAML file attached to the GitHub Release) that tooling (including a future upgrade
   mechanism, out of scope here) could also consume programmatically.
2. Whether `osac-ui` (already independently versioned, already excluded from any
   shared-version discussion throughout this design) needs any change under this model — current
   expectation is no, its existing independent-version handling is already the pattern this
   design generalizes to the other components.
3. Whether release-mode dispatch needs a stricter authorization gate than "anyone who can
   dispatch `nightly-build.yaml` today" — see Security Considerations. This needs input from
   whoever owns release engineering process/policy, not just the technical design.
4. Whether the manifest/pointer model (this proposal) or full synchronization (see Alternatives)
   is the better long-term fit for OSAC specifically. The manifest model is proposed here as the
   lower-risk default, but reviewers with a stake in release engineering or support should weigh
   in before this is considered settled — the coupling cost of full sync may be smaller than it
   looks, given OSAC's components are never independently consumed by a customer.

## Test Plan

### Unit Tests

- `validate_semver` (new shared helper, extracted from `publish-osac-installer-chart.yaml`'s
  existing inline validation) rejects malformed version strings for the `release_version` input.
- The version-monotonicity check rejects a `release_version` that is not strictly greater than
  the latest existing `osac/v*` release tag, and rejects a `release_version` that already exists,
  both before any tagging or publishing step runs.

### Integration Tests

- A release-mode dispatch against a version where not all sub-charts are published yet fails at
  the pre-flight check rather than proceeding.
- A release-mode dispatch against a version where everything is published succeeds, and the
  published umbrella chart's `Chart.lock` shows real `oci://` references (not `file://`) for
  every dependency, at each dependency's own actual version — not a forced shared version.
- Rerun-immutability: dispatch release mode for a given `release_version`; after it completes (or
  mid-way, simulating a retry), have one mono-repo component publish a newer independent version;
  re-dispatch the *same* `release_version` again and assert the resulting manifest/`Chart.lock` is
  identical to the first run's — the newer component version must not be picked up.

### E2E Tests

- Not applicable beyond what `nightly-build.yaml` already exercises (E2E validation of the
  installed umbrella chart) — release mode reuses that same test execution, just with different
  version-stamping inputs.

## Graduation Criteria

N/A — this is an internal CI/release-process change, not a user-facing API or feature with
alpha/beta/GA maturity levels. (The PRD's underlying customer capability — a well-defined,
installable release version — is expected to be exercised starting at OSAC's first Tech Preview
milestone, but that is a product-release timeline decision, not a graduation criterion of this
design itself.)

## Upgrade / Downgrade Strategy

This design does not itself implement upgrade execution (see PRD Out of Scope), but it is the
foundation any future upgrade tooling depends on: a customer upgrading from OSAC `v0.1.0` to
`v0.1.1` needs the manifest described here to determine exactly which component versions changed
between the two releases. No existing cluster is required to make any change as a result of this
design alone — it only affects how future releases are produced and labeled, not the umbrella
chart's runtime behavior.

## Version Skew Strategy

Version skew between mono-repo components is the *normal, expected, permanent* state under this
design's manifest model, not a transitional upgrade concern — each component versions
independently by design, and the umbrella's manifest (not matching version numbers) is what
establishes a supported, tested combination. This differs from typical Kubernetes version-skew
concerns (control plane vs. kubelet lagging during a rolling upgrade); there is no requirement
here for components to ever converge on a shared literal version number.

## Support Procedures

Given a customer-reported issue against a known OSAC release version, support should consult
that release's manifest (GitHub Release notes / `Chart.lock`) to determine the exact component
versions involved before investigating further — this is the primary mechanism this design
provides for mapping a reported symptom to specific, known code. If a release-mode dispatch
fails at the pre-flight check, the workflow run's log clearly lists which component(s) are not
yet published at the target version; no partial/ambiguous release is ever tagged or published as
a result of a failed dispatch.

## Infrastructure Needed

None beyond the GitHub Actions workflow changes described above.
