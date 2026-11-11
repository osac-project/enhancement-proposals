# Testplan — OSAC-7068

## Overview

- **Feature:** OSAC-7068 — OSAC Conformance Suite
- **Design:** [design.md](design.md)
- **Total test cases:** 31
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 7 of 7

FR-N is the Nth In Scope item of the [PRD](prd.md) (12 items, FR-1 through FR-12); IC-N is defined in the design's [API Extensions](design.md#api-extensions). These cases test the suite itself. The tests an area declares and runs against a provider component (for networking, the Fabric Manager task tests and profiles) belong to that area's test plan.

### Fixtures

- **Reference components:** each area's no-op and mock components (networking: the no-op and mock managers of the Network Manager Integration Contract test plan). The mock records each invocation. It has a failpoint per task and API ID, either one-shot or persistent until the test clears it. It can wrap a real component's role, so a lab with real components can fail one chosen task.
- **Lab A:** the OSAC E2E lab at release R whose profile catalog is `generic`, `vm`, `baremetal`, `cluster` and `netris`, with real networking components registered and a second Tenant `other` holding one resource.
- **Lab V:** a lab at release R whose selected profiles are `vm`; `generic` always applies.
- **Runner:** podman with a running rootless socket, a Kind scratch cluster created with `networking.apiServerAddress` so a container on a podman network reaches its API server and with a writable namespace, the image `ghcr.io/osac-project/osac-conformance:R`, a valid `conformance.yaml`, and an empty results directory.
- **Labeled test set:** end-to-end tests in `tests/e2e/` carrying `sig/<area>`, one or more `conformance/<selector>` labels, and `conformance/blocking` or `conformance/informing` (pytest markers mapped from the vocabulary, for example `conformance_generic`, in the current pytest-based tree): a generic test, a test labeled for each of `vmaas`, `bmaas` and `netris`, a test carrying two selector labels, and one informing test.

### Coverage matrix

| Cases | Tier | Owner | Boundary proved | Real | Simulated or omitted | Location and command |
|---|---|---|---|---|---|---|
| TC-FR6-02, TC-FR6-03, TC-FR6-04, TC-FR6-05, TC-FR6-01 (report shape part) | Unit | [DEV] | Plan computation, result rules, and report/JUnit writer | Suite runner | Lab, podman, components (fixture data) | Proposed, in the suite source; `tests/conformance/` in the osac repository; the suite's own unit-test command from the osac repository root (for example `go test ./tests/conformance/...` if the suite is written in Go). |
| TC-FR1-02, TC-FR2-01, TC-FR2-03, TC-FR2-04, TC-FR4-04, TC-FR5-02, TC-FR8-01 | Component integration | [DEV] | Suite runner to podman, EE image, scratch cluster, and lab read APIs | Suite image, podman, Kind scratch cluster, reference components, the Capabilities and registrations lab endpoints | Provider backend (mock component), every other lab service | Proposed CI job; needs a lab endpoint for Capabilities and registrations. Working directory: the CI job workspace in the osac repository. Unresolved: no harness yet. |
| TC-FR1-01, TC-FR2-02, TC-FR3-01 to TC-FR3-05, TC-FR4-01 to TC-FR4-03, TC-FR5-01, TC-FR5-03, TC-FR6-01, TC-FR8-02, TC-FR10-01, TC-FR10-02, TC-FR11-01 | E2E | [QE] | Suite to a deployed OSAC lab with real components | Lab A or Lab V (fulfillment, operator, AAP, real components), runner | None, except the mock failpoint where a case names it | OSAC E2E lab per release; command is the design's `podman run`. Working directory: the release E2E lab workspace. Lab scheduling unresolved. |
| TC-FR7-01, TC-FR9-01, TC-FR12-01 | Manual review | [DOCS] | Area design and provider guide content | — | — | Review of the networking design and provider guide. Working directory: not applicable. |

All commands run from the `osac` repository root unless the row states another working directory.

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

- The results directory holds `conformance-report.yaml`, one JUnit XML file, and the plan the run executed.
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
3. Repeat the run with a scratch kubeconfig whose server address is non-loopback, and once with a loopback address the EE container cannot reach.
4. Read the component job's connection settings and the suite output.

##### Expected Results

- Every record shows image digest D, OSAC's generic playbook, `include_role` with `tasks_from` equal to the task, exactly one input variable (networking: `osac_job_vars`), and the settings and secrets the lab keeps (networking: `network-fulfillment-ig`) as environment variables.
- Hub objects exist only in the scratch cluster namespace.
- No API ID appears in both runs.
- During the component-test phase the fulfillment API received no call.
- A loopback scratch server address is rewritten to the host gateway with the original host kept as the certificate name; a non-loopback address is left unchanged.
- An unreachable scratch endpoint is a configuration error before the first component test, not a TLS failure inside a test.

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
- Every selected profile has `result` `pass` or `fail`, not `skip`.
- The component and the overall `result` are `in progress`.
- The mock's records show the matching delete task run once for each API ID whose create ran and was not deleted; `leftovers` is `[]`.

#### TC-FR2-03: A component job timeout and a failed delete are reported

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Runner fixture with the mock component and a test-only area module that declares a 1-minute component job timeout; that module's mock task runs longer than the timeout.
- A one-shot failpoint on one delete task, enabled only for step 2; the slow-task failpoint is enabled only for step 1.

##### Steps

1. Run the test-only area with its 1-minute component job timeout and read the result.
2. Enable the delete failpoint only for this step, run the suite, and read `leftovers`.

##### Expected Results

- Step 1: that test has `result: fail` and its `message` is `job timed out after <timeout>`; no other test is affected.
- Step 2: the delete failure is listed in `leftovers` as `<task>/<API ID>`, and the overall `result` is `in progress`.

#### TC-FR2-04: An interrupt stops a running component job before cleanup

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Runner fixture with the mock component; a mock task that sleeps longer than the test waits; access to the runner's container list.

##### Steps

1. Start a run and send SIGINT while that component job runs, then read the report and the mock's records.
2. Start another run, send SIGKILL while the job runs, then inspect the containers and the first line of `conformance.log`.
3. Start a third run while the abandoned container is still present and read its result.

##### Expected Results

- Step 1: the suite stops and awaits the container, runs the delete tasks only after it exits, reports that test as `fail` with the message `interrupted`, and exits 130; the mock records no delete task while the container is alive.
- Step 2: the container is left behind, named `osac-conformance-<run ID>-<n>`, and the first log line gives the run ID.
- Step 3: the third run starts and completes without being blocked by the abandoned container; remove the container by its name afterwards.

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
- The suite log shows every selected profile starting before any profile finishes.
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

#### TC-FR3-05: An interrupt during a profile create still cleans up the new resource

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- Lab A; a mock failpoint that delays one profile create so it is in flight when the interrupt arrives.

##### Steps

1. Run the suite and send SIGINT while that create is in flight.
2. List the test Tenant and the objects named `osac-conformance-<run ID>*`.

##### Expected Results

- The interrupted test has `result: fail`.
- The runner stops the profile test, waits a bounded time for the in-flight create to return, then reconciles by listing the test Tenant and the objects named `osac-conformance-<run ID>*`; the listing is final because no new create can start. Cleanup deletes the new resource and `leftovers` is empty.
- The exit code is 130.

### FR-4: Tests are selected by the selected profiles' selectors into a plan, and run from a plan

#### TC-FR4-01: The plan is the union of the selected profiles' selectors

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | critical | automated |

##### Preconditions

- Lab V (profiles `[vm]`) and Lab A (profiles `[vm, baremetal, cluster, netris]`); the labeled test set.

##### Steps

1. Run `osac-conformance list` in Lab V and read the plan.
2. Run `osac-conformance list` in Lab A and read the plan.
3. Remove `netris` from Lab A's profiles and run `osac-conformance list` again.
4. Configure Lab V to report VMaaS enabled but omit `vm` from its profiles; run `osac-conformance list`, then `osac-conformance run`.

##### Expected Results

- Step 1: the plan holds the `generic` tests and the `vmaas` tests, and no `bmaas`, `caas` or `netris` test; a test carrying both `generic` and `vmaas` labels appears once.
- Step 2: the plan adds the `bmaas`, `caas` and `netris` tests to Lab V's set; it holds the union and nothing else.
- Step 3: the `netris` tests are gone and the rest of the plan is unchanged, so a selector contributes only when the lab names it.
- Step 4: the plan holds no `vmaas` test, the `vm` profile is reported `required: false` and `result: skip`, the run is not rejected, and the report makes no VMaaS conformance claim.

#### TC-FR4-02: list writes and prints the plan without running anything

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | medium | automated |

##### Preconditions

- Lab V; runner fixture; no Tenant, job or results directory content from a previous run.

##### Steps

1. Run `osac-conformance list` in a new results directory.
2. Read `/results/conformance-plan.yaml` and standard output.
3. List Tenants, the mock component's invocations, and the results directory.

##### Expected Results

- The plan is written to the results directory and printed, test by test, with the selector that selected each test and, for every test no selector selected, the reason (for example "no selector names the `bmaas` label").
- The plan records the selected profiles and the expanded selectors it was computed from, starting with `generic`.
- No Tenant exists, the mock records no invocation, and the results directory holds only the plan; the exit code is 0.
- The labels in `tests/e2e/` are unchanged after `list` and after a run.

#### TC-FR4-03: run executes a plan, and a narrower plan is never conformant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Lab V, all tests passing; the plan written by TC-FR4-02.

##### Steps

1. Run `osac-conformance run --plan <plan>` in a new results directory.
2. Edit the plan to keep one passing test; run `osac-conformance run --plan <edited plan>` in another results directory.
3. Run the unedited plan again in a third results directory.
4. Run a plan naming only a profile test that needs setup another test also performs, such as a networking SecurityGroup test that needs the VMs of the VM test.

##### Expected Results

- Step 1: the run executes exactly the plan's tests; `complete` is `true` and the result is `conformant`; the report records `selectors: [generic, vmaas]`.
- Step 2: only that test runs; `complete` is `false`, CHECK-4 fails, the result is `in progress`, and the exit code is 0 because every selected blocking test passed.
- Step 3: the same tests run with the same results as step 1, so a plan is repeatable.
- Step 4: the named test performs its own setup, passes, and no other test runs; the plan does not expand to the whole profile.

#### TC-FR4-04: An unknown selector, an unknown test, or an empty plan is an error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Runner fixture; a valid configuration; a plan written by `list`.

##### Steps

1. Add `frobnicate` to the selected `profiles` and run `osac-conformance list`.
2. Add the name of a test the image does not contain to the plan and run `osac-conformance run --plan <that plan>`.
3. Run `osac-conformance run --plan <an empty plan>`, and run `osac-conformance run` in a lab whose selected profiles select no test.

##### Expected Results

- Steps 1 and 2 stop before any test with exit code 2 and write no report.
- The output names the selector the image does not ship, and the test name the plan names but the image does not contain.
- Step 3: each empty plan stops before any test with exit code 2, writes no report, and names the empty plan as the error.

### FR-5: One configuration file, including the selected tests' settings; configuration errors only for selected runs

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
- The plan's profiles are the ones `conformance.yaml` names, and its selectors are their expansion; the suite reads no profile from the lab.

#### TC-FR5-02: Configuration errors stop the suite only for selected runs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Runner fixture with the mock component.

##### Steps

1. Run with an invalid `lab.tokenFile` token.
2. Run with `networking.externalIPPoolCIDR` removed; the selected `vm` profile needs it.
3. Run in Lab V (profiles `[vm]`) with `networking.taskTests.hosts` removed; no selected run needs it.
4. Run with `osacRelease` set to a release other than the one the lab runs.
5. Run with a results directory that already holds a file.
6. Run with a key this release does not define (`networking.taskTests.settings`).
7. Run with an unknown command (`osac-conformance frobnicate`).
8. Run with an unknown flag (`osac-conformance run --frobnicate`).
9. Run with a profile the image does not ship (`profiles: [frobnicate]`).

##### Expected Results

- Runs 1, 2, 4, 5, 6, 7, 8 and 9: no test runs; the output names the failing check (token rejected; the missing `networking.externalIPPoolCIDR`; the release mismatch with both releases; the results directory not empty; the undefined key; the unknown command; the unknown flag; the unknown selector); exit code 2, nothing written to the results directory.
- Run 3: no configuration error; the report is written, the plan holds no host run, and the result is unaffected.

#### TC-FR5-03: A selected end-to-end test reads its settings from the configuration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Lab A with the labeled test set; the settings each selected test needs are in `conformance.yaml` and its area section.
- The runner environment has no `OSAC_*` variables and no CI-only credentials, and the lab-only paths the tests used to assume do not exist.

##### Steps

1. Run the suite from that environment.
2. Read the results and evidence of the selected profile tests.
3. Repeat the run with the `OSAC_*` variables the tests read today set to different values.

##### Expected Results

- Every selected profile test runs and reports its real result; none fails or skips with a missing-setting message, and no test needs a CI-only input or a lab-only path.
- Step 3 changes no result, so the configuration and not the environment decides the tests' settings.
- The live log names the configuration source of the settings each selected test used.

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

- The top-level keys are exactly `osacRelease`, `suiteImageDigest`, `selectors`, `components`, `enabledServices`, `profiles`, `tests`, `checks`, `leftovers`, `complete`, `result`.
- Each `tests[]` entry has `id` (unique), `name` (`[<area>][<layer>][<profiles>] <case ID>: <title>` for a profile test, `[<area>][<layer>] <case ID>: <title>` for a component test), `layer` (`component` or `profile`), `profiles` (the selected profiles it counts toward), `classification` (`blocking` or `informing`), `result` (`pass`, `fail`, or `skip`), `durationSeconds` (integer), `message`; each `profiles[]` entry has `name`, `selectors`, `required`, `result`; each `checks[]` entry has `id`, `name`, `rule`, `remedy`, `result`.
- `/results/junit.xml` has one `testcase` per `tests[]` entry: `name` is the test name, `classname` is `<area>.<layer>`, `time` is `durationSeconds`; a failed test has a `failure` element with its `message`, a skipped one a `skipped` element.

#### TC-FR6-02: Conformant only when every blocking test in the plan and selected profile passes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- Result fixtures for one component: (a) all pass; (b) one blocking component test in the plan fails; (c) one selected profile fails; (d) a profile the plan does not select is skipped; (e) a test that no selector selected, and so is not in the plan; (f) all pass, with one entry in `leftovers`; (g) a selected profile whose tests are all informing.

##### Steps

1. Compute the component and overall results and the exit code for each fixture.

##### Expected Results

- (a) `conformant`, exit 0; (b) `in progress`, exit 1; (c) `in progress`, exit 1; (d) `conformant`, exit 0; (e) `conformant`, exit 0; (f) `in progress`, exit 1; (g) `in progress`, exit 1.

#### TC-FR6-03: A blocking test in the plan that is skipped is not a pass

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- Result fixtures for one component, otherwise passing: (a) a blocking test in the plan has `result: skip`; (b) the same test has `result: pass`.

##### Steps

1. Compute `checks[]`, the component result, the overall `result`, and the exit code for each fixture.

##### Expected Results

- (a) CHECK-1 fails; the component and the overall `result` are `in progress`; the exit code is 1.
- (b) CHECK-1 passes; the component and the overall `result` are `conformant`; the exit code is 0.

#### TC-FR6-04: The installation verdict is a list of named checks

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- Report fixtures for Lab V: (a) all selected tests pass; (b) one blocking test in the plan fails; (c) one leftover remains; (d) a plan that holds fewer tests than the selected profiles' selectors select; (e) no component registered.

##### Steps

1. Read `checks[]`, each check's `rule` and `remedy`, and the overall `result` for each fixture.

##### Expected Results

- `checks[]` contains CHECK-1 to CHECK-4, then any area checks, each with `id`, `name`, a non-empty `rule`, a non-empty `remedy`, and `result`.
- (a) every check passes and `result` is `conformant`; (b) CHECK-1 and CHECK-2 fail and `result` is `in progress`; (c) CHECK-3 fails; (d) CHECK-4 fails, `complete` is `false`, and `result` is `in progress`; (e) CHECK-2 fails and `result` is `in progress`.

#### TC-FR6-05: An informing failure is reported and never fails the run

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Result fixtures for one component, otherwise passing: (a) one informing test fails; (b) the same test marked blocking; (c) one informing test reports `skip`.

##### Steps

1. Compute `checks[]`, the component result, the overall `result`, and the exit code for each fixture.

##### Expected Results

- (a) the test has `result: fail` and `classification: informing`; CHECK-1 passes; the component and the overall `result` are `conformant`; the exit code is 0.
- (b) CHECK-1 fails; the component and the overall `result` are `in progress`; the exit code is 1.
- (c) the test is reported with `result: skip` and `classification: informing`; CHECK-1 passes; the result is `conformant`; the exit code is 0.

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

- Every row that is specific to networking has a definition in the networking design: its component tests and pass conditions, its selectors and which tests each selects, its configuration section and errors, its component identity, its support condition, how the suite finds its registered components, a title for each test, its selectors and which tests each selects, its timeout keys and defaults, its component job timeout, any named check it adds, where it reads settings and secrets, what it reads on the lab hub and its extra evidence, and its reference components.
- The networking design links here and does not redefine the image, the common configuration keys, the report keys, the named-check format, the conformance label vocabulary (`sig/<area>`, `conformance/<selector>`, `conformance/blocking` or `conformance/informing`), or the result rules.

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
- The job runs the same selector-selected component tests as a field run.

#### TC-FR8-02: The E2E lab release run is conformant with real components

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- Lab A at release R with real components.

##### Steps

1. Run the suite with every profile selected.

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

- The guide says the report is self-reported and attached to the component's design, lists what the Cloud Infrastructure Admin checks before onboarding or support (result, OSAC release, suite image digest, component identity and EE image digest), and gives the rerun model: component tests for every new component or EE image version, a report covering one OSAC release and one component version.
- The guide states that blocking or informing is declared metadata, that a human owner promotes a test after it has been stable in OSAC CI for a component test or in the E2E lab for a profile test, and that an area may declare its tests blocking from the start as networking does.
- The networking design states its support condition and that OSAC does not enforce it.

### FR-10: Verbose output, listing, and focused reruns

#### TC-FR10-01: The live log and evidence show every step and every failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

##### Preconditions

- Runner fixture with the mock component and its failpoint set to fail one component task with a wrong typed output; a component secret in the lab with a known value, which the mock component's failing task prints in its Ansible output and in its `osac_error` message; `lab.aap` set, and the failpoint also fails one profile check so a profile fails with job entries.

##### Steps

1. Run the suite.
2. Read standard output, `/results/conformance.log`, and `/results/tests/`.

##### Expected Results

- Standard output and `conformance.log` hold the same timestamped lines: the header (run ID, test Tenant, suite digest, release, selectors, enabled services, components), the plan with the selector that selected each test and a reason for each test no selector selected, `STARTED (<n>/<total>)` and `PASSED`/`FAILED`/`SKIPPED` lines for every test, each running test's own log lines, and the closing summary with counts per layer and profile split by classification, the named checks, the failed test with its first failure line, the path of the plan, leftovers, result, and exit code.
- The failing test's lines say what was expected and what was observed, and give its evidence paths; its evidence holds its log and, for each job, the job input, its environment with secrets redacted, its output, its result, the playbook, a command that reruns it, and the hub objects on a failure. The names in the design are the current example, not a contract.
- Running the rerun command the evidence provides by hand, after filling in the secrets, reproduces the same failure.
- Every test name in the log, the report, and the JUnit XML has the form `[<area>][<layer>][<profiles>] <case ID>: <title>` for a profile test and `[<area>][<layer>] <case ID>: <title>` for a component test.
- The secret value appears nowhere on standard output or under `/results` (live log, evidence, test messages, JUnit XML, report); `<redacted>` appears in its place where the output contained it. A profile's API log holds only the allowlisted fields.
- `/results/diagnostics/` holds the runner's own bundle: the installed release name and version, the OSAC namespace's control-plane state and pod logs, and the test Tenant's resources, with the secret absent and no Helm values. It is not tenant-scoped and may name resources of the other Tenant.
- The failed profile's evidence holds the lab's AAP job output for each job entry of its resources.

#### TC-FR10-02: A plan reruns its tests, and a narrowed plan is never conformant

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Lab V with the mock component; the plan written by TC-FR4-02.
- Lab V has capacity for the Tenant and resources the first `--keep` run retains plus the second run, and a second configuration whose `externalIPPoolCIDR` does not overlap the first run's.
- Step 5a uses the first configuration and retains its pool; step 5b and steps 6 to 9 use the second configuration, whose `externalIPPoolCIDR` does not overlap the retained pool.

##### Steps

1. Run `osac-conformance run --plan <plan>` in a new results directory.
2. Edit the plan to keep one test and run `osac-conformance run --plan <edited plan>` in a new results directory.
3. Add the name of a test the image does not contain to a plan and run `osac-conformance run --plan <that plan>`.
4. Run `osac-conformance run --frobnicate`.
5. Step 5a: with the mock component's failpoint set to fail TC-VM-01, run `osac-conformance run --keep` with the first configuration in a new results directory. Step 5b: with no failpoint, run `osac-conformance run --plan <a plan naming only TC-VM-01> --keep` with the second configuration in another results directory.
6. Start a full run in a new results directory and send SIGINT while the profiles run.
7. With the mock failpoint set to fail only an informing test, run `osac-conformance run --keep` in a new results directory.
8. Repeat step 6, sending SIGINT twice.
9. Delete the resources step 8 left by run ID, then with the failpoint set to fail an informing test, run `osac-conformance run --plan <a plan naming only that informing test>` in a new results directory.

##### Expected Results

- Step 1: the run executes exactly the plan's tests; `complete` is `true`, the report records `selectors: [generic, vmaas]`, and the exit code is 0.
- Step 2: only that test runs; `complete` is `false`, CHECK-4 fails, the result is `in progress`, and the exit code is 0 because every selected blocking test passed.
- Step 3: exits 2 before reading the lab, names the test the image does not contain, and writes no report.
- Step 4: exits 2 before reading the lab, with no report.
- Step 5: the failing run leaves Tenant `osac-conformance-<run ID>` and its resources in place, lists them in `leftovers[]`, and reports `in progress`; the passing focused run uses its own pool, cleans up as usual, leaves `leftovers` empty, and leaves the first run's Tenant and pool untouched.
- Step 6: no new test starts; cleanup runs; the report is written with the tests that did not run as `skip`; the exit code is 130.
- Step 7: cleanup runs as usual, `leftovers` is empty, and the informing failure leaves the result unchanged.
- Step 8: the second signal terminates the suite immediately, with no further cleanup and no report written after it.
- Step 9: the informing test has `result: fail`, `complete` is `false`, the result is `in progress`, and the exit code is 0 because every selected blocking test passed and `leftovers` is empty.

### FR-11: Secret values the suite reads never appear in output, logs, evidence, report, or JUnit

#### TC-FR11-01: No secret appears in the outputs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- Lab A with `lab.aap` set; the token file, each secret value of the component in the lab, the AAP token, each credential in the lab and scratch kubeconfigs, a secret Helm release value (for example the osac chart's `token`), the lab API host, and each kubeconfig server address contain unique marker strings.

##### Steps

1. Use the test-only area module to make each credential marker appear in a captured source: the component echoes its secret markers on standard output, the suite's API client sends the admin token in a profile request, the AAP client sends the AAP token in a job-log request, and the scratch connection presents the kubeconfig credential.
2. Run the suite, capturing standard output and evidence.
3. Search standard output, `conformance.log`, every evidence file, the report, the JUnit XML, and the diagnostics bundle for each marker.

##### Expected Results

- Zero matches for every credential marker and for the internal-hostname markers in any of those outputs; where the output contained a value, `<redacted>` appears instead.
- The Helm-value marker is an exclusion test: the suite never collects the Helm values, so the marker never enters an output path at all.

### FR-12: The guides end with the suite

#### TC-FR12-01: The installation and Fabric Manager guides point to the suite

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| N/A | low | manual |

##### Preconditions

- The installation guide and the Fabric Manager guide at release R.

##### Steps

1. Read the final verification step of the installation guide.
2. Read part 6 of the Fabric Manager guide and its go-live checklist.
3. Read section 9.1 of the installation guide's support condition.

##### Expected Results

- Section 7 of the installation guide ends with running the release's suite and reading its report and named checks.
- Part 6 of the Fabric Manager guide and its go-live checklist point to the suite and no longer give separate manual verification steps.
- Section 9.1 no longer says "Until that suite is available"; it points to the suite's `vm` profile and the Fabric Manager guide.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

### Execution gaps

These gaps block the Dev Preview graduation criterion:

- The suite source (`tests/conformance/` in the osac repository), its unit test command, and its CI job do not exist yet.
- The component-integration CI job needs a lab endpoint for Capabilities and registrations; no harness is identified.
- The selected end-to-end tests still read CI-only inputs (about 44 `OSAC_*` environment variables, a fixed test user, and lab-only SSH paths); adapting them to read their settings from the conformance configuration is outstanding.
- The test tree needs the collection step `list` uses to report each test's labels, and the profile tests need to use the tree's shared client so their API requests reach the evidence; neither exists yet.
- The tree's own settings conflict with the suite's model and must be changed: `-n 4 --dist loadfile` gives the tree its own parallelism, its clients are gRPC rather than the profile API log's shape, `ensure_tenants` creates the fixed Tenants `tenant1` and `tenant2`, and the token comes from `oc create token ... --as system:admin`.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 31 |
| Critical | 12 |
| High | 15 |
| Medium | 2 |
| Low | 2 |
| Automated | 28 |
| Manual | 3 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 7 / 7 |
