# Testplan — OSAC-XXXX

## Overview

- **Feature:** OSAC-XXXX — OSAC Conformance Suite
- **Design:** [design.md](design.md)
- **Total test cases:** 22
- **Requirements covered:** 10 of 10
- **Interface changes covered:** 6 of 6

FR-N is the Nth In Scope item of the [PRD](prd.md); IC-N is defined in the design's [API Extensions](design.md#api-extensions). These cases test the suite itself. The tests an area's suite module runs against a provider component (for networking, the Fabric Manager task tests and profiles) belong to that area's test plan.

### Fixtures

- **Reference components:** each area's no-op and mock components (networking: the no-op and mock managers of the Network Manager Integration Contract test plan). The mock records each invocation. It has a failpoint per task and API ID, either one-shot or persistent until the test clears it. It can wrap a real component's role, so a lab with real components can fail one chosen task.
- **Lab A:** the OSAC E2E lab at release R with VMaaS, BMaaS, and CaaS enabled, real networking components registered, and a second Tenant `other` holding one resource.
- **Lab V:** a lab at release R with only VMaaS enabled.
- **Runner:** podman with a running rootless socket, a Kind scratch cluster with a writable namespace, the image `ghcr.io/osac-project/osac-conformance:R`, a valid `conformance.yaml`, and an empty results directory.

### Coverage matrix

| Cases | Tier | Owner | Boundary proved | Real | Simulated or omitted | Location and command |
|---|---|---|---|---|---|---|
| TC-FR6-02, TC-FR6-01 (report shape part), TC-FR10-01 (redaction and naming part) | Unit | [DEV] | Result rules and report/JUnit writer | Suite core | Lab, podman, components (fixture data) | Proposed, in the suite source; `tests/conformance/` in the osac repository; command not defined yet. |
| TC-FR1-02, TC-FR2-01, TC-FR4-02, TC-FR5-02, TC-FR8-01, TC-FR10-01, TC-FR10-02 | Component integration | [DEV] | Suite core to podman, EE image, scratch cluster, and lab read APIs | Suite image, podman, Kind scratch cluster, reference components | Provider backend (mock component), lab services other than Capabilities and registrations | Proposed CI job; needs a lab endpoint for Capabilities and registrations. Unresolved: no harness or Jira owner yet. |
| TC-FR1-01, TC-FR2-02, TC-FR3-01 to TC-FR3-04, TC-FR4-01, TC-FR4-03, TC-FR5-01, TC-FR6-01, TC-FR6-03, TC-FR8-02 | E2E | [QE] | Suite to a deployed OSAC lab with real components | Lab A or Lab V (fulfillment, operator, AAP, real components), runner | None, except the mock failpoint where a case names it | OSAC E2E lab per release; command is the design's `podman run`. Lab scheduling unresolved: no Jira owner yet. |
| TC-FR7-01, TC-FR9-01 | Manual review | [DOCS] | Area design and provider guide content | — | — | Review of the networking design and provider guide. |

## Test Cases

### FR-1: One suite image per OSAC release, run with podman

#### TC-FR1-01: Run the release image and get a report

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Lab A at release R; runner fixture.

##### Steps

1. Run the design's `podman run` command with the configuration, results, and podman socket mounts.
2. List the results directory and read `conformance-report.yaml`.
3. Run `podman image inspect --format '{{.Digest}}' ghcr.io/osac-project/osac-conformance:R`.

##### Expected Results

- The results directory holds `conformance-report.yaml` and one JUnit XML file.
- `osacRelease` is `R`; `suiteImageDigest` equals the digest from step 3.
- No file in the configuration directory changed.

#### TC-FR1-02: A missing podman socket stops the suite with a configuration error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- Runner fixture; a lab where component tests apply.

##### Steps

1. Run the image without the podman socket mount.

##### Expected Results

- The output names the missing podman socket check; no test runs.
- No `conformance-report.yaml` is written and the exit code is 2.

### FR-2: Component tests run the component as OSAC runs it; profiles run through OSAC's APIs

#### TC-FR2-01: Component tests use OSAC's invocation and not the lab

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- The lab registers the mock component with EE image digest D.
- The fulfillment API access log of the lab is readable.

##### Steps

1. Run the suite twice.
2. Read the mock's invocation records and the fulfillment API access log for the component-test phase.

##### Expected Results

- Every record shows image digest D, OSAC's generic playbook, `include_role` with `tasks_from` equal to the task, exactly one input variable (networking: `osac_job_vars`), and the settings and secrets the lab keeps (networking: `network-fulfillment-ig`) as environment variables.
- Hub objects exist only in the scratch cluster namespace.
- No API ID appears in both runs.
- During the component-test phase the fulfillment API received no call.

#### TC-FR2-02: A failing component test does not stop the profiles

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Lab A with the mock component wrapping the real one; failpoint set on one task.

##### Steps

1. Run the suite.

##### Expected Results

- The run of that task has `result: fail` and a non-empty `message`.
- Every required profile has `result` `pass` or `fail`, not `skip`.
- The component and the overall `result` are `in progress`.
- The mock's records show the matching delete task run once for each API ID whose create ran and was not deleted; `leftovers` is `[]`.

### FR-3: Profiles in a test Tenant of a shared lab, cleanup, and timeouts

#### TC-FR3-01: Profiles run in parallel in the test Tenant and leave other Tenants untouched

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- Lab A; record the resource version of Tenant `other` and of its resource.

##### Steps

1. Run the suite; list Tenants while profiles run.
2. After the run, list Tenants and read `other` and its resource.

##### Expected Results

- While profiles run, exactly one Tenant named `osac-conformance-<run ID>` exists, with the run ID matching `[a-z0-9]{8}`.
- The suite log shows every required profile starting before any profile finishes.
- After the run the test Tenant is not listed; `other` and its resource have their recorded resource versions; `leftovers` is `[]`.

#### TC-FR3-02: Cleanup runs after a profile fails

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- Lab A; the mock failpoint makes one profile check fail.

##### Steps

1. Run the suite.
2. List the test Tenant, its resources, and the provider-scoped objects the area creates for the run.

##### Expected Results

- That profile has `result: fail`.
- The first line of `conformance.log` gives the run ID, and every OSAC object the run created is named `osac-conformance-<run ID>` or `osac-conformance-<run ID>-<suffix>`.
- The test Tenant, its resources, and the run's provider-scoped objects no longer exist; `leftovers` is `[]`.

#### TC-FR3-03: A delete timeout fails the test and lists the leftover

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Lab A; `timeouts.delete: 2m` (or the area's delete key); a persistent mock failpoint fails one profile resource's delete task until the test clears it after the run.

##### Steps

1. Run the suite.

##### Expected Results

- The test waiting for that delete has `result: fail` and a `message` naming the delete timeout.
- `leftovers` contains `<kind>/<API ID>` of that resource and nothing else; the overall `result` is `in progress`.

#### TC-FR3-04: A timeout override replaces the area default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- Lab A; an area readiness timeout set to `1s` in `timeouts` (networking: `vmReady: 1s`).

##### Steps

1. Run the suite.

##### Expected Results

- The profile test that waits for that readiness has `result: fail` and a `message` naming that timeout key.
- Cleanup runs: `leftovers` is `[]`.

### FR-4: Runs selected from enabled services and registered components

#### TC-FR4-01: A VMaaS-only lab requires only what VMaaS needs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- Lab V; runner fixture.

##### Steps

1. Run the suite.

##### Expected Results

- `enabledServices` is `[vmaas]`.
- Every profile whose area requires it only for BMaaS or CaaS has `required: false` and `result: skip`.
- Every run that needs BMaaS or CaaS has `result: skip`.
- The overall `result` is `conformant` when every other test passes.

#### TC-FR4-02: An area with no registered component contributes nothing required

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A lab with no networking component registered.

##### Steps

1. Run the suite.

##### Expected Results

- `components` has no `networking` entry; every networking test has `result: skip`; every networking profile has `required: false`.
- With no component found, the overall `result` is `in progress`.

#### TC-FR4-03: A required run that skips is never a pass

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Lab A; the networking optional input `taskTests.hosts` omitted.

##### Steps

1. Run the suite.

##### Expected Results

- The networking host runs have `result: skip`.
- The `baremetal` profile `result` is not `pass`; the component is `in progress`.

### FR-5: One configuration file; configuration errors only for required runs

#### TC-FR5-01: The suite reads lab facts instead of configuration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Lab A; `conformance.yaml` with only the common keys and the area's documented keys.

##### Steps

1. Run the suite.
2. Read the lab hub registration and the Capabilities response.

##### Expected Results

- Each `components[]` identity field equals the value in the lab hub registration.
- `enabledServices` lists the same services as the Capabilities `enabled_services`.

#### TC-FR5-02: Configuration errors stop the suite only for required runs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Runner fixture with the mock component.

##### Steps

1. Run with an invalid `lab.tokenFile` token.
2. Run with an area key that a required run needs removed.
3. Run with an area key that only a run that does not apply needs removed.
4. Run with `osacRelease` set to a release other than the one the lab runs.
5. Run with a results directory that already holds a file.
6. Run with a key this release does not define (`networking.taskTests.settings`).

##### Expected Results

- Runs 1, 2, 4, 5, and 6: no test runs; the output names the failing check (token rejected; the missing key; the release mismatch with both releases; the results directory not empty; the undefined key); exit code 2, nothing written to the results directory.
- Run 3: no configuration error; the report is written and that run has `result: skip`.

### FR-6: Report and result rules

#### TC-FR6-01: The report has exactly the defined keys and matches the JUnit XML

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- The report and JUnit XML of TC-FR1-01.

##### Steps

1. Compare the report's top-level keys with the design's list.
2. Check each `tests[]` entry and the JUnit XML test cases.

##### Expected Results

- The top-level keys are exactly `osacRelease`, `suiteImageDigest`, `components`, `enabledServices`, `profiles`, `tests`, `leftovers`, `focus`, `result`.
- Each `tests[]` entry has `id` (unique), `name` (`[<area>][<layer>][<profile>] <case ID>: <title>`), `layer` (`component` or `profile`), `profile`, `result` (`pass`, `fail`, or `skip`), `durationSeconds` (integer), `message`; each `profiles[]` entry has `name`, `area`, `required`, `result`.
- `/results/junit.xml` has one `testcase` per `tests[]` entry: `name` is the test name, `classname` is `<area>.<layer>`, `time` is `durationSeconds`; a failed test has a `failure` element with its `message`, a skipped one a `skipped` element.

#### TC-FR6-02: Conformant only when every applying test and required profile passes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- Result fixtures for one component: (a) all pass; (b) one applying component test fails; (c) one required profile fails; (d) a non-required profile skipped; (e) a run that does not apply skipped; (f) all pass, with one entry in `leftovers`.

##### Steps

1. Compute the component and overall results and the exit code for each fixture.

##### Expected Results

- (a) `conformant`, exit 0; (b) `in progress`, exit 1; (c) `in progress`, exit 1; (d) `conformant`, exit 0; (e) `conformant`, exit 0; (f) `in progress`, exit 1.

#### TC-FR6-03: No secret appears in the outputs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Lab A; the token file and each secret value of the component in the lab contain unique marker strings.

##### Steps

1. Run the suite, capturing standard output.
2. Search the results directory and the captured output for each marker.

##### Expected Results

- Zero matches for every marker.

### FR-7: Areas plug in; networking first

#### TC-FR7-01: The networking design defines every plug-in item

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | manual |

##### Preconditions

- The Network Manager Integration Contract design at release R.

##### Steps

1. For each row of the design's area plug-in table, find the networking definition.
2. Check that the networking design links to this proposal for the generic rules.

##### Expected Results

- Every row has a definition in the networking design.
- The networking design links here and does not redefine the image, the common configuration keys, the report keys, or the result rules.

### FR-8: OSAC CI with reference components; profiles in the E2E lab

#### TC-FR8-01: Release CI runs the component tests against reference components

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- The release CI job, the reference no-op and mock components.

##### Steps

1. Run the CI job for release R.

##### Expected Results

- With the no-op component, every component test it supports has `result: pass`.
- The job stores the report and JUnit XML as CI artifacts.

#### TC-FR8-02: The E2E lab release run is conformant with real components

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Lab A at release R with real components.

##### Steps

1. Run the suite with every profile required.

##### Expected Results

- Every component and the overall `result` are `conformant`; `leftovers` is `[]`.

### FR-9: Self-reported report, per-area support condition, rerun policy

#### TC-FR9-01: The policy is documented for providers

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | low | manual |

##### Preconditions

- The provider guide and the networking design at release R.

##### Steps

1. Read the conformance part of the provider guide and the networking support condition.

##### Expected Results

- The guide says the report is self-reported and attached to the component's design, and that the suite runs for every OSAC release and every new component version.
- The networking design states its support condition and that OSAC does not enforce it.

### FR-10: Verbose output, listing, and focused reruns

#### TC-FR10-01: The live log and evidence show every step and every failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- Runner fixture with the mock component and its failpoint set to fail one component task with a wrong typed output; a component secret in the lab with a known value.

##### Steps

1. Run the suite.
2. Read standard output, `/results/conformance.log`, and `/results/tests/`.

##### Expected Results

- Standard output and `conformance.log` hold the same timestamped lines: the header (run ID, test Tenant, suite digest, release, lab, enabled services, components), the selection with a reason for each run that does not apply, `STARTED (<n>/<total>)`, `STEP:`, and `PASSED`/`FAILED`/`SKIPPED` lines for every test, and the closing summary with counts per layer and profile, the failed test with its first failure line, a `--run` expression that selects exactly the failed tests, leftovers, result, and exit code.
- The failing test's lines say what was expected and what was observed, and give its evidence paths; its directory, `/results/tests/<id>/`, holds `test.log` and, for each job, `job_vars.yaml`, `env.yaml`, `ansible.log`, `result.yaml`, `playbook.yml`, `rerun.sh`, and `hub-objects.yaml`.
- Running that job's `rerun.sh` by hand, after filling in the secrets, reproduces the same failure.
- Every test name in the log, the report, and the JUnit XML has the form `[<area>][<layer>][<profile>] <case ID>: <title>`.
- The secret value appears nowhere under `/results`; `<redacted>` appears in its place where the output contained it.

#### TC-FR10-02: list selects without running, and a focused run is never conformant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- A VMaaS-only lab fixture with the mock component.

##### Steps

1. Run `osac-conformance list`, then `osac-conformance list --run 'TC-RETRY-01'`.
2. Run `osac-conformance run --run 'TC-RETRY-01'` in a new results directory.
3. Run `osac-conformance run --run 'TC-VM-01' --keep` in a new results directory.
4. Run `osac-conformance run --keep` and `osac-conformance run --run '('`.
5. Start a full run in a new results directory and send SIGINT while the profiles run.

##### Expected Results

- Step 1: the first command prints every selected test by name, layer, and profile, and the BMaaS and CaaS runs with the reason "not enabled"; the second prints only the TC-RETRY-01 runs. Both create no Tenant, start no job, write nothing to `/results`, and exit 0.
- Step 2 runs only the matching tests and creates no Tenant; the other tests are `skip` with `not selected by --run`; the report has `focus: TC-RETRY-01` and `result: in progress`, and the exit code is 0 because every selected test passed.
- Step 3 leaves Tenant `osac-conformance-<run ID>` and its resources in place, lists them in `leftovers[]`, and reports `in progress`.
- Step 4: both exit 2 before reading the lab, with no report.
- Step 5: no new test starts; cleanup runs; the report is written with the tests that did not run as `skip`; the exit code is 130.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

### Execution gaps

- The suite source (`tests/conformance/` in the osac repository), its unit test command, and its CI job do not exist yet; no Jira owner exists yet.
- The component-integration CI job needs a lab endpoint for Capabilities and registrations; no harness is identified.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 22 |
| Critical | 10 |
| High | 9 |
| Medium | 2 |
| Low | 1 |
| Automated | 20 |
| Manual | 2 |
| Requirements with test cases | 10 / 10 |
| Interface changes with test cases | 6 / 6 |
