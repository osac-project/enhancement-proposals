---
title: repository-consolidation
authors:
  - ercohen@redhat.com
creation-date: 2026-05-07
last-updated: 2026-05-07
tracking-link:
  - TBD
see-also:
  - N/A
replaces:
  - N/A
superseded-by:
  - N/A
---

# Repository Consolidation: Mono-Repo for OSAC Core Components

## Summary

This enhancement proposes consolidating four tightly coupled OSAC repositories
(`fulfillment-service`, `osac-operator`, `osac-aap`, and `osac-installer`) into
a single mono-repo. The current multi-repo layout creates persistent friction in
cross-component changes, installer drift, protobuf version skew, and CI
coverage gaps. A single repository with per-component directories eliminates
these issues while preserving separation of concerns through directory structure
and CODEOWNERS.

## Motivation

OSAC's core components are tightly coupled: the `fulfillment-service` defines
protobuf types and CRDs consumed by `osac-operator`; the operator produces
Kubernetes resources that `osac-aap` provisions via Ansible; and `osac-installer`
must wire all three together with correct image references, Kustomize overlays,
and infrastructure prerequisites. Despite this coupling, the components live in
separate GitHub repositories, which creates the following pain points:

**Installer drift.** The `osac-installer` repository frequently falls behind the
other components. Updates happen on a bi-weekly ad-hoc basis when someone
manually bumps image SHAs. In the interim, testers reproduce bugs that have
already been fixed, wasting time on stale deployments. A recent incident
required days to land an installer update PR because two weeks of accumulated
changes had broken Envoy configuration, Keycloak setup, and tenancy defaults
simultaneously.

**Protobuf and CRD version skew.** When a data structure changes in
`fulfillment-service`, the developer must: (1) land the proto change, (2) tag a
release, (3) update the Go module reference in `osac-operator`, (4) verify the
operator still compiles, (5) open a separate PR. This multi-step dance delays
delivery and introduces windows where the two components disagree on types.
Developers routinely discover that the operator references a stale
`fulfillment-service` tag and spend time debugging why things "aren't working."

**Cross-repo CI gaps.** Today, merging a PR in `fulfillment-service` does not
run the operator's tests or the installer's integration suite. Breaking changes
land in one repo and are only caught days later when someone attempts an
end-to-end deployment. There is no mechanism in GitHub to express "this PR in
repo A depends on that PR in repo B" and gate merging on both passing together.

**AI tooling friction.** The team uses AI-assisted development extensively.
AI agents work best when the full context (types, controllers, installer
manifests, Ansible roles) is visible in a single repository. The meta-repo
workaround (`osac-workspace`) helps, but agents still struggle with cross-repo
references, tagging ceremonies, and multi-PR coordination.

**PR coordination overhead.** Features that span components require two or three
synchronized PRs across repos, each needing its own review cycle, CI run, and
merge ordering. Developers must manually communicate dependency order ("merge
fulfillment-service#123 first, then osac-operator#45"). Misordering causes
broken `main` branches.

### User Stories

- As an OSAC developer, I want to change a protobuf message and its
  corresponding controller logic in a single PR so that I do not have to
  coordinate releases across repositories.
- As an OSAC developer, I want every PR to run the full installation suite so
  that I catch integration regressions before merge, not days later.
- As a QA engineer, I want the installer to always reflect the latest code so
  that I do not waste time reproducing already-fixed bugs on stale deployments.
- As a new contributor, I want to clone one repository and have the complete
  OSAC codebase available so that I can understand how the components interact
  without navigating multiple repos and module dependencies.
- As a release engineer, I want a single repository to tag and release so that
  I do not have to orchestrate multi-repo release trains with precise ordering.

### Goals

- Eliminate protobuf/CRD version skew between `fulfillment-service` and
  `osac-operator` by making them part of the same Go module (or sibling modules
  in the same repo).
- Ensure every PR runs integration tests that cover the full stack (API, operator,
  installer).
- Remove the manual installer-update ceremony: changes to any component's
  manifests are immediately reflected in the installer overlays within the same
  commit.
- Preserve clear separation of concerns through directory structure, CODEOWNERS
  files, and per-component CI jobs.
- Maintain the ability to build and release independent container images for
  each component.

### Non-Goals

- Merging `osac-test-infra` into the mono-repo. Test infrastructure has a
  different lifecycle and set of maintainers.
- Merging `enhancement-proposals` or `docs` repos. These are documentation-only
  and benefit from independent review processes.
- Changing the project's CI system.

## Proposal

Consolidate `fulfillment-service`, `osac-operator`, `osac-aap`, and
`osac-installer` into a single repository with the following top-level layout:

```
osac/
├── fulfillment-service/     # gRPC server, REST gateway, proto definitions, DB
├── osac-operator/           # Kubernetes operator, CRDs, controllers
├── osac-aap/                # Ansible roles and playbooks
├── osac-installer/          # Kustomize base/overlays, prerequisites, scripts
├── proto/                   # Shared proto definitions (moved from fulfillment-service/proto)
├── go.work                  # Go workspace file linking Go modules
├── OWNERS                   # Top-level ownership
├── CODEOWNERS               # Per-directory GitHub review assignments
├── Makefile                 # Top-level build/test/lint targets
└── .github/
    └── workflows/           # CI: per-component + integration
```

### Workflow Description

**Developer making a cross-component change:**

1. The developer creates a single feature branch in the mono-repo.
2. They modify protobuf definitions under `proto/`, update the
   `fulfillment-service` handler, adjust the `osac-operator` controller, and
   fix the installer overlay if needed.
3. They open a single PR. CI runs unit tests for each affected component and
   the full integration suite.
4. Reviewers from the relevant CODEOWNERS groups are auto-assigned.
5. The PR merges atomically. There is no version skew window.

**Developer making a single-component change:**

1. The developer modifies files only under `fulfillment-service/`.
2. CI detects which components are affected (via path filters) and runs only
   the relevant unit tests plus the integration suite.
3. Only the `fulfillment-service` CODEOWNERS group is assigned for review.
4. The experience is equivalent to working in a single-component repo.

**Release process:**

1. A release tag (e.g., `v1.2.0`) is created on the mono-repo.
2. CI builds container images for each component:
   `osac-fulfillment-service:v1.2.0`, `osac-operator:v1.2.0`,
   `osac-aap-ee:v1.2.0`.
3. The installer overlays reference images from the same tag, guaranteeing
   consistency.

### API Extensions

No API changes. This is a repository and build infrastructure change only.

### Implementation Details/Notes/Constraints

**Phase 1: Repository setup and history migration**

- Create the new `osac` repository under `osac-project`.
- Import each component's full git history using `git subtree add` or a
  history-rewriting tool so that `git log --follow` and `git blame` continue to
  work for migrated files.
- Set up `go.work` to link the `fulfillment-service` and `osac-operator` Go
  modules, allowing them to reference each other's packages at source (no
  published tags needed).

**Phase 2: CI setup**

- Create GitHub Actions workflows with path-based triggers:
  - `fulfillment-service/**` triggers fulfillment unit tests.
  - `osac-operator/**` triggers operator unit tests.
  - `osac-aap/**` triggers Ansible lint and molecule tests.
  - `osac-installer/**` triggers installation dry-run.
  - Any change triggers the integration test suite.
- Retain per-component Containerfile builds; add a top-level Makefile for
  convenience (`make build-all`, `make test-all`, `make images`).

**Phase 3: Proto consolidation**

- Move `fulfillment-service/proto/` to top-level `proto/` so both
  `fulfillment-service` and `osac-operator` can import generated types
  directly without go module version pinning.
- Update `buf.yaml` and `buf.gen.yaml` for the new layout.
- Remove the tagged-release dependency between the two Go modules.

**Phase 4: Installer alignment**

- Update `osac-installer` overlays to use relative references to component
  manifests within the same repo (e.g., `../../fulfillment-service/manifests`).
- CI for any component change automatically validates that the installer
  overlay still applies cleanly.

**Phase 5: Archive old repositories**

- Archive `fulfillment-service`, `osac-operator`, `osac-aap`, and
  `osac-installer` on GitHub (read-only). Add a prominent notice pointing to
  the new mono-repo.
- Update all documentation, wiki links, and bookmarks.

**Conflux / Build System Compatibility**

Multiple container images from a single repository is a well-supported pattern.
Each component retains its own `Containerfile` and build context. GitHub Actions
matrix builds can produce all images in parallel.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Larger PR review surface | CODEOWNERS enforces per-directory review; path-filtered CI prevents unnecessary test runs |
| Git history noise from unrelated components | `git log -- <directory>` scopes history; CODEOWNERS ensures only relevant reviewers are notified |
| Longer CI times if all tests run on every PR | Path-based CI triggers run only affected component tests; full integration runs as a separate required check |
| Migration disrupts in-flight work | Coordinate migration during a low-activity window; freeze PRs on old repos for 1-2 days |
| Go module complexity with multiple modules in one repo | `go.work` handles this natively; Kubernetes and other large projects use this pattern |
| Permissions and access control changes | GitHub CODEOWNERS and branch protection rules provide equivalent granularity to separate repos |

### Drawbacks

**Larger repository size.** The combined repo will be larger to clone, though
the individual components are relatively small (Go code, YAML manifests, Ansible
roles). Shallow clones (`--depth 1`) mitigate this for CI.

**Blast radius of broken `main`.** A bad merge in any component breaks `main`
for everyone. However, this is already the case in practice: a broken
`fulfillment-service` deploy blocks all other work today, just with a delayed
feedback loop. The mono-repo makes the breakage visible immediately rather than
hiding it behind stale installer references.

**Cognitive load for contributors focused on one component.** A developer
working only on Ansible roles sees Go code they do not care about. Directory
structure and CODEOWNERS mitigate this: `cd osac-aap` is functionally
equivalent to working in a separate repo. IDE project filtering and sparse
checkouts are available for those who want a narrower view.

**Loss of per-component GitHub issue/PR numbers.** Existing issue references
(e.g., `fulfillment-service#42`) will point to archived repos. New issues use
the mono-repo's tracker. Jira remains the authoritative issue tracker, so GitHub
issue numbers are less critical.

## Alternatives (Not Implemented)

### Alternative 1: Cross-Repo GitHub Actions Triggers

Set up GitHub Actions in `fulfillment-service` and `osac-operator` to
automatically trigger a PR in `osac-installer` whenever a change merges to
`main`. The triggered workflow would bump image SHAs, run the installer tests,
and auto-merge if green.

**Why this is not optimal:**

- The auto-generated installer PR can fail for reasons unrelated to the
  triggering change (e.g., accumulated drift from other repos). Debugging
  requires context across repositories.
- This doubles the number of PRs: every component merge creates a follow-up
  installer PR, flooding the review queue. The team already struggles with PR
  review throughput.
- It doubles CI compute: the component's CI runs first, then the installer's CI
  runs separately. In a mono-repo, a single CI run covers both.
- It does not solve the protobuf version-skew problem: the operator still needs
  a tagged release from `fulfillment-service` to update its Go module
  dependency. The cross-repo trigger only helps the installer.
- Race conditions arise when two component PRs merge in quick succession: the
  second installer-update PR may conflict with or overwrite the first.
- There is no atomic merge: the component change is on `main` before the
  installer is verified, creating a window where `main` across repos is
  inconsistent.

### Alternative 2: Git Submodules in the Installer Repo

Make `osac-installer` a "super-repo" that includes the other three as git
submodules. CI in the installer repo would pull the latest submodule references
and run the full test suite.

**Why this is not optimal:**

- Git submodules are notoriously difficult to work with. Developers must
  remember to run `git submodule update --init --recursive`, submodule pointers
  drift, and PRs that update submodules are confusing to review.
- It does not solve the protobuf version-skew issue. The operator still depends
  on a tagged release of `fulfillment-service`'s Go module.
- Cross-component PRs still require coordinating merges: change the submodule
  repo first, then update the submodule pointer in the installer, which is
  two-step just like today.
- The `osac-workspace` meta-repo is already a lighter version of this approach
  (using `bootstrap.sh` instead of submodules), and the team still experiences
  all the drift problems.

### Alternative 3: Shared Go Module Published via Tags

Publish protobuf-generated types and shared packages as a standalone Go module
(e.g., `github.com/osac-project/osac-common`) with semantic versioning. Both
`fulfillment-service` and `osac-operator` depend on this shared module.

**Why this is not optimal:**

- Adds a third repository to coordinate: proto changes now require a three-step
  dance (land in common, tag, update both consumers).
- The release tagging ceremony remains, just shifted to a different repo.
- Does not address installer drift at all.
- Does not enable atomic cross-component changes.
- The team previously had `fulfillment-api` and `fulfillment-common` as
  separate repos and already consolidated them into `fulfillment-service`
  because the overhead was not worth it. This alternative repeats the same
  pattern.

### Alternative 4: Periodic Nightly Sync Job

Run a nightly CI job that builds all components from their respective `main`
branches, deploys via the installer, and runs the integration test suite. If
the job fails, create a Jira ticket for investigation.

**Why this is not optimal:**

- Feedback is delayed by up to 24 hours. Developers have moved on to other work
  by the time the nightly job reports failures.
- It does not prevent broken code from merging; it only detects it after the
  fact.
- Debugging a nightly failure requires correlating changes across multiple repos
  to identify which commit broke the integration, a time-consuming process.
- Does not solve the protobuf version-skew or the multi-PR coordination
  problems.
- The team's experience shows that periodic sync attempts (bi-weekly manual
  bumps) already fail to keep pace with the rate of change.

### Alternative 5: Status Quo with Process Improvements

Keep the multi-repo layout but add stricter process requirements: mandatory
installer-update PRs for every component change, required cross-repo CI checks,
and documented dependency ordering in PR templates.

**Why this is not optimal:**

- Process-based solutions degrade over time. Developers forget, skip steps under
  deadline pressure, or leave the team and take the knowledge with them.
- Cross-repo CI checks in GitHub require complex webhook configurations and
  still cannot express "these two PRs must merge together."
- The overhead of maintaining cross-repo automation (triggers, webhooks, status
  checks, bot accounts) approaches the overhead of the migration itself, but
  without the long-term simplification benefits.
- The team has informally attempted process-based solutions (asking developers
  to "follow through with the installer") and the installer still drifts.

## Open Questions

1. Should the Go modules be fully merged into a single `go.mod` or kept as
   separate modules linked by `go.work`? A single module is simpler but creates
   a larger dependency tree for consumers who only need one component. Separate
   modules with `go.work` provide isolation while eliminating the tag-based
   release ceremony.

2. What is the right granularity for CODEOWNERS? Per top-level directory
   (e.g., `fulfillment-service/`) or per sub-directory (e.g.,
   `fulfillment-service/internal/networking/`)?

3. Should the migration preserve full git history via `git subtree` (slower
   migration, full blame/log) or start fresh with a squashed import (faster
   migration, cleaner history, but loses per-file blame)? A middle ground is
   importing history and tagging the merge point for easy reference.

4. How does this interact with the planned Helm migration for the installer?
   If the installer is moving from Kustomize to Helm, the migration should be
   sequenced to avoid doing the repo consolidation on a moving target.

## Test Plan

- **Unit tests**: Each component retains its existing test suite, run via
  path-filtered CI triggers.
- **Integration tests**: The existing `osac-test-infra` E2E suite runs on every
  PR, using images built from the PR's branch. This is the key improvement over
  the current setup.
- **Migration validation**: After history import, verify that `git log --follow`
  works for migrated files, that all CI jobs pass, and that a full deployment
  from the mono-repo produces the same result as the current multi-repo
  deployment.

## Graduation Criteria

This is a one-time infrastructure change, not a feature with maturity stages.
Success criteria:

- All four component repositories are archived on GitHub.
- All active development happens in the mono-repo.
- CI runs the full integration suite on every PR.
- No manual installer-update PRs are needed.
- Time from "proto change" to "operator using new types" drops from days to
  minutes (same PR).

## Upgrade / Downgrade Strategy

Not applicable. This is a repository structure change, not a runtime feature.
Existing deployments are unaffected. The container images produced by the
mono-repo are identical to those produced by the individual repos.

## Version Skew Strategy

The entire point of this proposal is to eliminate version skew between
components. With a mono-repo, all components are built from the same commit,
ensuring consistency by construction.

## Support Procedures

Not applicable. This change affects the development workflow, not the runtime
behavior of any OSAC component. No new failure modes, metrics, or alerts are
introduced.

## Infrastructure Needed

- A new GitHub repository: `osac-project/osac` (or reuse an existing name).
- GitHub Actions runners with capacity for the combined CI workload (expected
  to be comparable to the sum of current per-repo CI, with optimization via
  path-filtered triggers).
- Updated Conflux/OSBS configurations if applicable for multi-image builds.
