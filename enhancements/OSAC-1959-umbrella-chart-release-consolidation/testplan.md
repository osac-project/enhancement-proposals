# Test Plan — OSAC-1959 Umbrella chart release consolidation

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 6

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-UR-01: Release-version validation rejects malformed input

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 311-315](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L311-L315)
- **Dependencies:** Local version helper and fixture strings; no CI runner, registry or cluster.
- **Gap:** Current release preparation uses the shared release-line and version helpers, but no focused release-input test was found in the canonical release test inventory.

**Preconditions.** Use synthetic release line 1.2 and versions 1.2.3, 1.2.3-rc.1 and 1.2.

1. Evaluate these versions at the shared validation boundary.
2. Record the decision before any publication handler is called.

**Expected results.** Both complete versions pass syntax validation and 1.2 fails with an invalid-version decision.

#### TC-UR-02: A version that is not strictly greater is rejected before tagging

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 315-317](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L315-L317)
- **Dependencies:** Local version comparison and a temporary Git tag fixture; build and publishing are omitted.
- **Gap:** Canonical release workflow preparation has a monotonicity guard, but no matching test of the decision and no-publication result was found.

**Preconditions.** Use latest osac/v1.2.4 and a requested 1.2.3 in one synthetic release line.

1. Evaluate the release preparation decision against the fixture tags.
2. Inspect the tag set and record whether publication preparation was selected.

**Expected results.** The lower version fails, the tag set is unchanged and publication preparation is skipped.

#### TC-UR-03: An existing release tag blocks publishing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 315-317](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L315-L317)
- **Dependencies:** Local Git tag fixture and release preparation code; registry and runner are omitted.
- **Gap:** The canonical release workflow checks tag existence during preparation. No independent guard assertion with a synthetic existing tag was found.

**Preconditions.** Create osac/v1.2.4 in a disposable repository.

1. Submit 1.2.4 to the release preparation boundary.
2. Check original tag identity and publish decision.

**Expected results.** Preparation rejects the existing version, and there is no tag or publication change.

#### TC-UR-04: The umbrella chart pins each dependency to its published version

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 324-325](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L324-L325)
- **Dependencies:** Real Helm, release preparation and disposable OCI registry; fixture component artifacts; no OSAC workloads.
- **Gap:** The canonical release workflow resolves and pins versions; no registry-backed test found asserting every lock entry's OCI endpoint and independent version.

**Preconditions.** Seed every declared dependency in a disposable registry, including operator 1.2.2 and fulfillment 1.2.3.

1. Prepare and package the umbrella chart.
2. Read its packaged lock and resolve each dependency from the test registry.

**Expected results.** Every declared dependency has an OCI reference and its own resolved version, including the distinct operator and fulfillment versions.

#### TC-UR-05: Missing subchart publication fails preflight

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 321-322](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L321-L322)
- **Dependencies:** Real release preflight and disposable OCI registry; fixture charts; deployed stack omitted.
- **Gap:** No matching missing-subchart release dispatch test was found in the release workflow and installer test inventory.

**Preconditions.** Seed the expected set of fixture chart versions except the selected operator chart.

1. Request assembly against that registry.
2. Inspect the preflight result and test registry's umbrella artifacts.

**Expected results.** Preflight identifies the missing subchart and creates no umbrella publication.

#### TC-UR-06: A release retry preserves the original dependency selection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 326-329](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1959-umbrella-chart-release-consolidation/design.md#L326-L329)
- **Dependencies:** Real Helm, isolated release workflow and disposable OCI registry; fixture chart versions; no workload deployment.
- **Gap:** The design asks for an identical lock on a retry. Current release preparation rejects a published umbrella tag. The interrupted retry before umbrella publication has no verified immutability assertion; the post-publication rejection is TC-UR-03.

**Preconditions.** Stage an unpublished umbrella release with a saved lock and published component fixtures.

1. Add a newer operator version to the disposable registry.
2. Retry the same unpublished release and compare its lock and rendered dependency manifests with the saved artifacts.

**Expected results.** The selected versions and manifests match the original set and retain the initially selected operator version.
