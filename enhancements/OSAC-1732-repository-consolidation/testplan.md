# Test Plan — OSAC-1732 Repository consolidation

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 4

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-RC-01: Consolidated CI runs each component's existing unit suite

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 373-376](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1732-repository-consolidation/README.md#L373-L376)
- **Dependencies:** Each component runs its existing unit fixtures from the consolidated tree; providers and the deployed stack are omitted.
- **Gap:** The canonical unit workflow defines component jobs, but the proposal-wide build and suite-retention assertion has no single qualifying test. Image assembly is supplemental build validation.

**Preconditions.** Use disposable checkouts at a public synthetic component-only change and its parent.

1. Compare the path-filter decisions and named test jobs for the two revisions.
2. Check unit results for the changed component and separately record image build results.

**Expected results.** The changed component's existing suite runs from its monorepo path and the path filter selects its job. Image builds are reported separately.

#### TC-RC-02: Deployed CI uses images from the pull request revision

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 377-378](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1732-repository-consolidation/README.md#L377-L378)
- **Dependencies:** Real deployed OSAC stack, CI-built images and selected provider fixture; no production registry or deployment.
- **Gap:** The canonical deployed suites consume CI images, but no test reviewed in the PR workflow or E2E harness independently asserts deployed image provenance for the full set.

**Preconditions.** Use an isolated deployment and an immutable digest map from one synthetic PR SHA.

1. Capture the component digests produced by the PR build.
2. Compare deployed workload image IDs against the map, then run the existing lifecycle smoke.

**Expected results.** Every workload under test resolves to the digest for that PR SHA and the lifecycle smoke completes.

#### TC-RC-03: Imported files retain source history

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 380-382](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1732-repository-consolidation/README.md#L380-L382)
- **Dependencies:** Local Git object databases only.
- **Gap:** No history-preservation assertion found in the canonical workflow or installer test inventory.

**Preconditions.** Record one pre-import revision, former path and commit subject per migrated repository in disposable fixture clones.

1. Follow each file across the monorepo import boundary.
2. Compare the recovered revision, subject and file contents with the source clone.

**Expected results.** Each selected file reaches its pre-import history and the recovered contents match.

#### TC-RC-04: The consolidated installation preserves baseline lifecycle results

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 380-383](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-1732-repository-consolidation/README.md#L380-L383)
- **Dependencies:** Real isolated instances of both stack layouts with equivalent charts, prerequisites and provider fixtures; no shared production services.
- **Gap:** The current monorepo deployed suites do not compare results with a legacy multi-repository deployment.

**Preconditions.** Prepare equivalent fixture tenants and catalog entries in isolated baseline and consolidated deployments.

1. Run the same create, read and delete lifecycle in both deployments.
2. Compare API status and resulting hub resources after each transition.

**Expected results.** Both layouts reach the same terminal states and remove the corresponding resources.
