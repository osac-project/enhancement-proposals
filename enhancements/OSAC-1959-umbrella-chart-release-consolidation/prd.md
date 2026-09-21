# OSAC Release Versioning and Consolidated Release Mechanism

| Field       | Value   |
|-------------|---------|
| Author(s)   | eerez |
| Jira        | https://redhat.atlassian.net/browse/OSAC-5183 |
| Date        | 2026-09-10 |

## Problem Statement

Today, OSAC has no coherent, product-facing definition of what an "OSAC release version"
means, or a working mechanism to produce one. The umbrella Helm chart's dependencies (six
mono-repo components plus `osac-ui`) each version independently, with no manifest tying them
into a single, discoverable release identity. The mechanism intended to produce an official,
customer-installable release is effectively dormant — no clean, non-nightly `osac/vX.Y.Z` tag
exists since 2026-07 — while the continuously-running nightly build produces artifacts that are
not meant to represent a stable, supportable release.

Concretely, a Cloud Infrastructure Admin trying to install or track a specific OSAC build today
(during development, ahead of any external release) cannot answer:
"what version am I installing," "exactly which component versions does OSAC `v0.1.0` contain,"
or "what changed between one OSAC release and the next." Left unaddressed, this blocks any
customer-facing release, support, or upgrade story once OSAC reaches its first Tech Preview
milestone, and leaves the team without a real release mechanism to produce one when that time
comes.

## In Scope

- A defined, unambiguous meaning for an "OSAC release version" (e.g. `v0.1.0`), and a way for a
  Cloud Infrastructure Admin to determine exactly which version of every constituent component
  a given release contains.
- A single release version must be consistently identifiable across every place it appears: the
  umbrella chart's own `Chart.yaml` version, its OCI registry tag, the corresponding Git tag
  (`osac/vX.Y.Z`), the GitHub Release, and the component-version manifest. A Cloud Infrastructure
  Admin should never encounter a mismatch between what any one of these says the release is.
- A single, working, tested mechanism to cut such a release from a chosen commit, replacing
  today's two duplicate, divergent tools for producing one.
- Installing a specific, named OSAC release version via the umbrella chart.

## Out of Scope

- Automated in-place upgrade execution (Helm upgrade hooks, CRD migration logic, data
  migrations between OSAC versions). This PRD defines what a release version *is* and how it is
  produced and discovered; the mechanics of safely moving an existing installation from one
  version to the next is separate, follow-on work.
- Changes to per-component independent versioning/publishing (`osac-operator`,
  `fulfillment-service`, etc. each publishing on their own cadence) — unaffected.
- OSAC-4224's Konflux/`registry.redhat.io` distribution work — independent and explicitly
  non-blocking; it depends only on OSAC-5178 (already merged), not on this PRD's outcome.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to install a specific, well-defined OSAC release
  version, so that I know exactly what I am deploying.
- As a Cloud Infrastructure Admin, I want to determine exactly which component versions are
  included in a given named OSAC release, so that I can diagnose issues or plan an upgrade with
  confidence rather than guessing.
- As a Cloud Infrastructure Admin, I want OSAC release version numbers to only ever move
  forward in one unambiguous sequence, so that I can safely reason about upgrade order without
  encountering a release that looks numerically older than one I already have installed.

### Tenant Admin

- As a Tenant Admin, I want the OSAC installation my Cloud Infrastructure Admin manages to have
  a clear, reportable version identity, so that when I raise a support issue, it can be reliably
  mapped to a known, specific release rather than an ambiguous or undocumented build.

## Assumptions

- **OSAC has no external clients or installations today — it is still in active development.**
  Nothing in this PRD addresses a live customer pain point; it's proactive groundwork. This is a
  deliberate reason to do it *now* rather than a reason to defer: establishing a coherent
  versioning/release identity is far cheaper before any real installation depends on a specific
  version number than retrofitting one afterward.
- Customer-facing upgrade flows will primarily be exercised once OSAC reaches its first Tech
  Preview release; this PRD establishes the versioning foundation ahead of that milestone, not
  because upgrade is being actively exercised by real customers today. This affects urgency and
  sequencing, not whether the problem needs solving now — the release mechanism needs to exist
  and be trustworthy before there is a customer relying on it.

## Dependencies

- **OSAC-5178 (merged):** the umbrella chart's dependency metadata already correctly resolves to
  real, published component versions rather than local build-only paths before packaging — a
  prerequisite for any release manifest described here to be meaningful.
- **OSAC-4224 (Konflux / `registry.redhat.io` release):** independent and non-blocking in both
  directions — that work can proceed against whichever release mechanism is current, and does
  not need to wait on this PRD or its design being finalized.
