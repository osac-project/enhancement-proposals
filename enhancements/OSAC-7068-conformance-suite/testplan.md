# Testplan - OSAC-7068

## Overview

- **Feature:** OSAC-7068 - OSAC Conformance Suite
- **Design:** [design.md](design.md)
- **Scope:** the core runner shipped by OSAC-7454
- **Total automated cases:** 138 unit cases, including one gated image smoke
- **Requirements covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12 at the core level
- **Interface changes covered:** IC-1 through IC-6

FR-N is the Nth In Scope item of the [PRD](prd.md); IC-N is defined in the design's [API Extensions](design.md#api-extensions).

This test plan covers the suite runner itself. Tests that a domain declares and runs against a provider, target installation reads, test Tenants, resource cleanup, and release publication are follow-up work and are out of scope here.

### Fixtures

- **Synthetic pytest tree:** a temporary tree of pytest modules with conformance markers, a pass, a failure, a skip, a teardown failure, and duplicate function names.
- **Fake tree adapter:** an in-process `TestTree` implementation that returns fixed identities and outcomes, so the CLI, plan, verdict, and report can be tested without a pytest child.
- **Configuration fixture:** a temporary `conformance.yaml` and the files it names, including a token, a CA, and a kubeconfig.
- **Catalog fixture:** a temporary `catalog.yaml` with marker selectors and profiles.
- **Target kubeconfig fixture:** a temporary kubeconfig and a fake `kubectl` command for diagnostics and the Netris settings check.
- **Image smoke fixture:** podman, the Containerfile, and network access, enabled only when `OSAC_CONFORMANCE_IMAGE_TEST=1`.

### Coverage matrix

| Cases | Tier | Boundary proved | Real | Simulated or omitted | Location and command |
|---|---|---|---|---|---|
| Configuration, catalog, selection, verdict, report, redaction, image digest, interrupt, diagnostics, Netris check, CLI | Unit | Core runner contracts | Runner, pytest plugin, fake commands | Target installation, podman, container runtime | `tests/unit/test_conformance_*.py`; `uv run pytest tests/unit/test_conformance_*.py` |
| `list`, `run`, `run --plan`, subset plans, empty plan, unknown profile, interrupted run | Core integration | CLI to pytest child to report | Runner, pytest, synthetic tree | Target installation, container runtime | `tests/unit/test_conformance_integration.py` |
| Container build and entry point | Image smoke | Containerfile and entry point | Podman, image build | Target installation | `OSAC_CONFORMANCE_IMAGE_TEST=1 uv run pytest tests/unit/test_conformance_image.py` |

## Test Cases

### FR-1: One suite image per OSAC release, run as an unprivileged user

#### TC-FR1-01: The image builds and starts

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | gated automated |

##### Preconditions

- podman is available and can pull the pinned UBI and kubectl images.
- `OSAC_CONFORMANCE_IMAGE_TEST=1`.

##### Steps

1. Build `tests/conformance/Containerfile` from the repository root.
2. Start the image with a minimal configuration and an empty results directory.

##### Expected Results

- The build succeeds.
- The entry point starts as UID 1001 and reaches configuration validation.
- The image contains `osac-conformance` and `kubectl`.

#### TC-FR1-02: The image digest comes from the environment first

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Preconditions

- A fake podman or Docker socket and a set `OSAC_CONFORMANCE_SUITE_IMAGE_DIGEST`.

##### Steps

1. Call `suite_image_digest()` with both the environment variable and the socket available.

##### Expected Results

- The environment variable wins.
- No socket request is made.

#### TC-FR1-03: The image digest falls back to the runtime socket

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | major | automated |

##### Preconditions

- A fake libpod or Docker-compatible socket serving container inspect.

##### Steps

1. Call `suite_image_digest()` without the environment variable.
2. Serve `ImageName`, `ImageDigest`, `Config.Image`, `RepoDigests`, and `Image` in separate cases.

##### Expected Results

- The digest is read from the highest-precedence field.
- A Docker-compatible reference resolves its repo digest.
- An unreachable socket falls back to the environment or returns an empty string.

### FR-2: Selection by declared profiles and marker selectors

#### TC-FR2-01: Generic always applies and selectors are deduplicated

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

##### Preconditions

- A catalog with `generic`, `vm`, and overlapping selectors.

##### Steps

1. Expand `[vm]`.
2. Expand `[generic, vm]`.
3. Expand a profile list with a duplicate profile.

##### Expected Results

- `generic` is first.
- Profile IDs and selectors are deduplicated in order.
- Selectors do not imply one another.

#### TC-FR2-02: A test can count toward multiple profiles

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4, IC-6 | major | automated |

##### Preconditions

- A test carrying `conformance_generic` and `conformance_vmaas`.

##### Steps

1. Assign profiles for `[generic, vm]`.

##### Expected Results

- The test's `profiles` list holds `generic` and `vm`.
- The plan holds the test once.

#### TC-FR2-03: An unknown profile is a configuration error

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-4 | critical | automated |

##### Preconditions

- A configuration selecting a profile the catalog does not ship.

##### Steps

1. Run `list`.

##### Expected Results

- Exit 2.
- The error names the unknown profile.
- No report is written.

### FR-3: One configuration file

#### TC-FR3-01: Common keys load and defaults apply

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A valid `conformance.yaml` without `profiles`, `target.namespace`, or `timeouts`.

##### Steps

1. Load the configuration.

##### Expected Results

- `profiles` defaults to `[generic]`.
- `target.namespace` defaults to `osac`.
- `timeouts` defaults to an empty mapping.
- Paths are canonicalized.

#### TC-FR3-02: Unknown keys and domain sections are rejected

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A configuration with an unknown top-level key, an unknown `target` key, an unknown `target.aap` key, or a `networking:` section.

##### Steps

1. Load the configuration.

##### Expected Results

- Each unknown key is named.
- Exit 2.
- No report is written.

#### TC-FR3-03: Required target keys and value types are enforced

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A configuration missing `target.kubeconfig`, `target.apiURL`, `target.tokenFile`, or `target.caFile`.
- A configuration with `profiles` not a list of strings.

##### Steps

1. Load each configuration.

##### Expected Results

- Each case is a configuration error naming the key.
- No partial configuration is returned.

#### TC-FR3-04: Unsafe paths and duplicate keys are rejected

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Preconditions

- A target path or AAP token path containing `..`.
- A YAML document with duplicate mapping keys.
- A YAML document with an unhashable mapping key.

##### Steps

1. Load each configuration and catalog.

##### Expected Results

- Parent-directory traversal is rejected.
- Duplicate keys are rejected.
- Unhashable keys are rejected.

#### TC-FR3-05: URLs must parse

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | major | automated |

##### Preconditions

- `target.apiURL` values `https://[`, `not-a-url`, and a valid URL.
- An invalid `target.aap.url`.

##### Steps

1. Load each configuration.

##### Expected Results

- Malformed URLs are configuration errors with a host requirement.
- A malformed URL does not replace an earlier configuration error.

#### TC-FR3-06: The redactor is seeded from the configuration

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

##### Preconditions

- A token file, an AAP token file, a kubeconfig with token, password, and client key data, and hosts in `apiURL` and the kubeconfig server.

##### Steps

1. Build the redactor for the configuration.
2. Redact text containing each value and host.

##### Expected Results

- Every configured secret and host becomes `<redacted>`.

### FR-4: Plan computation, listing, and replay

#### TC-FR4-01: The plan is the union of selected selectors

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4, IC-5 | critical | automated |

##### Preconditions

- A synthetic tree with generic, vmaas, bmaas, caas, netris, multi-selector, and informing tests.

##### Steps

1. Run `list` with `profiles: [vm]`.
2. Read `conformance-plan.yaml`.

##### Expected Results

- The plan holds the union of `generic` and `vmaas` tests.
- Each test has `id`, `key`, `name`, `profiles`, and `markers`.
- `complete` is `true`.

#### TC-FR4-02: list writes and prints the plan without creating the log

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- An empty results directory.

##### Steps

1. Run `list`.
2. Inspect stdout and the results directory.

##### Expected Results

- The plan is written to `/results/conformance-plan.yaml` and printed.
- No `conformance.log` is created.
- The directory can accept a later `run --plan`.

#### TC-FR4-03: A narrower plan is incomplete and still replayable

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A plan with one of several selected tests.

##### Steps

1. Run `run --plan <file>`.

##### Expected Results

- The subset runs.
- `complete` is `false`.
- The report says `in progress`.
- The focused run exits 0 when at least one selected blocking test ran, every selected blocking test passed, and there are no leftovers.

#### TC-FR4-04: The opaque plan key replays a redacted test ID

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A plan whose test `id` was redacted and whose `key` is the SHA-256 of the original ID.

##### Steps

1. Run `run --plan <file>`.

##### Expected Results

- The test is resolved by `key`.
- The test runs.

#### TC-FR4-05: An empty plan, unknown test, or unselected test is an error

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A plan with no tests.
- A plan naming a test the image does not contain.
- A plan naming a test no selected profile selects.
- A plan with duplicate keys.

##### Steps

1. Run `run --plan <file>` for each case.

##### Expected Results

- Each case exits 2 with a configuration error.
- No test runs.
- No report is written.

### FR-5: Configuration errors stop before any test

#### TC-FR5-01: A configuration error writes no report

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

##### Preconditions

- A missing configuration file.
- An unknown key.

##### Steps

1. Run `list` or `run`.

##### Expected Results

- Exit 2.
- The error is printed to stderr.
- The results directory does not gain a report.
- Secrets and hosts in the error are redacted.

#### TC-FR5-02: A non-empty results directory stops the run

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | planned |

##### Preconditions

- A results directory containing a file other than `conformance-plan.yaml`.

##### Steps

1. Run `list`.

##### Expected Results

- Exit 2.
- The unexpected entries are named.
- No report is written.

### FR-6: Verdict and named checks

#### TC-FR6-01: All passing checks produce a conformant verdict

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A complete plan with passing blocking tests and no leftovers.

##### Steps

1. Evaluate the report.

##### Expected Results

- `all-blocking-tests-pass`, `no-leftovers`, and `complete-plan` pass.
- `result` is `conformant`.
- Exit code is 0.

#### TC-FR6-02: A blocking failure or skip fails the blocking check

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A plan with a failing blocking test.
- A plan with a skipped blocking test.

##### Steps

1. Evaluate the report for each case.

##### Expected Results

- `all-blocking-tests-pass` fails.
- The check message names the failed tests, or says the skip is not a pass.
- `result` is `in progress`.

#### TC-FR6-03: A plan with no blocking tests fails the blocking check

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | major | automated |

##### Preconditions

- A plan containing only informing tests.

##### Steps

1. Evaluate the report.

##### Expected Results

- `all-blocking-tests-pass` fails with `no blocking tests in the plan`.
- An informing-only plan is not a conformance verdict.

#### TC-FR6-04: An informing failure does not fail a check

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | planned |

##### Preconditions

- A complete plan with passing blocking tests and one failing informing test.

##### Steps

1. Evaluate the report.

##### Expected Results

- The informing test is `fail` in `tests[]`.
- No check fails.
- `result` is `conformant`.
- Exit code is 0.

#### TC-FR6-05: Leftovers and incomplete plans fail their checks

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | major | automated |

##### Preconditions

- A report with one leftover.
- A focused plan.

##### Steps

1. Evaluate each report.

##### Expected Results

- `no-leftovers` fails and names the leftover.
- `complete-plan` fails and says the plan is a focused subset.
- `result` is `in progress`.

#### TC-FR6-06: A selected profile with no blocking test is not a pass

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4 | major | automated |

##### Preconditions

- A selected profile whose planned tests are all informing.

##### Steps

1. Derive the profile result.

##### Expected Results

- `required` is `true`.
- `result` is `skip`.

### FR-7: Conformance markers

#### TC-FR7-01: Collection records markers and node IDs

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- A synthetic tree with selector and classification markers.

##### Steps

1. Run the collection pass.
2. Read the manifest.

##### Expected Results

- Each item has `nodeid`, `name`, and sorted marker names.
- The runner derives a canonical ID relative to the tree root.

#### TC-FR7-02: Classification defaults to blocking

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- Tests with `conformance_blocking`, `conformance_informing`, and neither marker.

##### Steps

1. Build the test identities.

##### Expected Results

- `conformance_informing` is informing.
- `conformance_blocking` is blocking.
- A test with neither marker is blocking.

#### TC-FR7-03: Duplicate test IDs are a configuration error

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | major | planned |

##### Preconditions

- Two tests with the same canonical ID.

##### Steps

1. Run collection.

##### Expected Results

- Exit 2 with a duplicate-ID error.

### FR-8: Test execution

#### TC-FR8-01: Pytest outcomes map to conformance results

| Interface Change | Priority | Automation |
|---|---|---|
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A tree with a passing, failing, skipped, and teardown-failing test.

##### Steps

1. Run the plan through pytest.
2. Read the JSONL records.

##### Expected Results

- Pass maps to `pass`.
- Failure maps to `fail`.
- Skip and teardown skip map to `skip`.
- A teardown failure maps to `fail`.
- Duration is the sum of the recorded phases.

#### TC-FR8-02: Captured output and logging reach the evidence log

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A test that writes stdout, stderr, and captured logging.

##### Steps

1. Run the plan.
2. Read `tests/<hash>/test.log`.

##### Expected Results

- The log holds the captured logging, stdout, and stderr.
- The content is redacted.

#### TC-FR8-03: Collection failure and pytest process errors are configuration errors

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A tree with a collection error.
- A child process that exits 3, 4, or 5.

##### Steps

1. Run the plan.

##### Expected Results

- Exit 2.
- No report is written.
- The error includes the pytest output.

#### TC-FR8-04: Duplicate function names get distinct IDs

| Interface Change | Priority | Automation |
|---|---|---|
|---|---|---|
| IC-6 | minor | automated |

##### Preconditions

- Two test functions with the same name in different modules, or parameterized cases.

##### Steps

1. Collect the tree.

##### Expected Results

- Each canonical node ID is unique.
- The evidence directories are distinct.

### FR-9: Report and JUnit XML

#### TC-FR9-01: The report has exactly the defined keys

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A report built from a plan with one pass, one fail, and one skip.

##### Steps

1. Write the report.
2. Load the YAML.

##### Expected Results

- Keys are exactly `osacRelease`, `suiteImageDigest`, `selectors`, `profiles`, `tests`, `checks`, `leftovers`, `complete`, and `result`.
- `selectors` entries have `id`, `type`, and `markers`.
- `profiles` entries have `id`, `selectors`, `required`, and `result`.
- `tests` entries have `id`, `name`, `profiles`, `classification`, `result`, `durationSeconds`, and `message`.
- `checks` entries have `id`, `name`, `rule`, `remedy`, `result`, and `message`.

#### TC-FR9-02: Report messages and check messages are redacted

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

##### Preconditions

- A test message, a check message, and a leftover containing a known secret.

##### Steps

1. Write the report.

##### Expected Results

- Every known secret is `<redacted>`.

#### TC-FR9-03: JUnit has one testcase per test

| Interface Change | Priority | Automation |
|---|---|---|
|---|---|---|
| IC-3 | critical | automated |

##### Preconditions

- A report with one pass, one fail, and one skip.

##### Steps

1. Write `junit.xml`.
2. Parse it.

##### Expected Results

- Three `testcase` elements.
- `classname` is `conformance`.
- A failure has a `failure` element whose body is `test.log`.
- A skip has a `skipped` element.

#### TC-FR9-04: XML-invalid characters cannot split a secret

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | major | automated |

##### Preconditions

- A message containing a secret split by a C0 control character.

##### Steps

1. Write the JUnit XML.

##### Expected Results

- The control character is removed.
- The secret is redacted.

### FR-10: Live output, evidence, and diagnostics

#### TC-FR10-01: The run ID is eight lowercase alphanumeric characters

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A new run.

##### Steps

1. Generate a run ID.

##### Expected Results

- The ID matches `[a-z0-9]{8}`.

#### TC-FR10-02: Output goes to stdout and the log with a timestamp and redaction

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- An `OutputSink` with a known secret.

##### Steps

1. Write a line.

##### Expected Results

- stdout and `conformance.log` both hold the timestamped line.
- The secret is `<redacted>`.

#### TC-FR10-03: Evidence is confined and bounded

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A test ID with `..`, `/`, `:`, and a long parameter.

##### Steps

1. Write evidence.

##### Expected Results

- The path stays under `tests/<hash>/`.
- The directory name is 16 hex characters.
- The test ID is not repeated in the path.

#### TC-FR10-04: Diagnostics are redacted and use the configured namespace

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A fake `kubectl` returning control-plane state and pod logs.
- A configured namespace.

##### Steps

1. Collect diagnostics.

##### Expected Results

- `osac-state.yaml` and `pod-logs.txt` are written.
- The commands use the configured namespace.
- A failed command is recorded and redacted.

#### TC-FR10-05: list does not create the run log

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- An empty results directory.

##### Steps

1. Run `list`.

##### Expected Results

- The plan is written and printed.
- `conformance.log` is not created.

### FR-11: Redaction

#### TC-FR11-01: Known secrets and hosts are redacted

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

##### Preconditions

- A redactor seeded with a secret and a host.

##### Steps

1. Redact text containing both.

##### Expected Results

- Both become `<redacted>`.

#### TC-FR11-02: Existing sanitizer rules are composed

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- Text with a bearer token, a Basic credential, an assignment, and a JSON secret.

##### Steps

1. Redact the text.

##### Expected Results

- The existing `sanitize_text` rules apply unchanged.

#### TC-FR11-03: Structured objects are redacted recursively

| Interface Change | Priority | Automation |
|---|---|---|
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A nested object with credential-named keys, a container environment name/value pair, a registry auth config entry, and a serialized annotation.

##### Steps

1. Redact the object.

##### Expected Results

- Every credential value is `<redacted>`.
- Non-credential values are unchanged.
- A serialized JSON annotation is redacted by structure.

### FR-12: Interrupt handling

#### TC-FR12-01: The first signal forwards SIGINT and keeps completed outcomes

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A running pytest child and one completed test.

##### Steps

1. Send SIGINT.
2. Read the report.

##### Expected Results

- The child receives SIGINT.
- The completed test keeps its outcome.
- The report is written.
- Exit code is 130.

#### TC-FR12-02: The second signal kills the child and writes no report

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | critical | automated |

##### Preconditions

- A running pytest child.

##### Steps

1. Send SIGINT twice.

##### Expected Results

- The child is killed.
- No report is written.
- Exit code is 130.

#### TC-FR12-03: A signal during registration is replayed after attachment

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A signal arrives between `Popen` returning and the child handle being attached.

##### Steps

1. Trigger the signal during registration.

##### Expected Results

- The signal is deferred.
- The child is attached.
- The signal reaches the child.
- Two signals escalate after attachment.

### Core integration

#### TC-CORE-01: list and run against a synthetic tree

| Interface Change | Priority | Automation |
|---|---|---|
|---|---|---|
| IC-3, IC-5 | critical | automated |

##### Preconditions

- A synthetic tree, a catalog, a configuration, and an empty results directory.

##### Steps

1. Run `list`.
2. Run `run --plan`.
3. Read the report and JUnit XML.

##### Expected Results

- The plan is written.
- The tests run.
- The report and JUnit XML match the outcomes.

#### TC-CORE-02: An interrupt reports completed tests

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | major | automated |

##### Preconditions

- A synthetic tree with one completed test and one running test.

##### Steps

1. Run `run`.
2. Send SIGINT.

##### Expected Results

- The completed test keeps its outcome.
- The report is written.
- Exit code is 130.

## Known coverage gaps

- `TC-FR5-02` (a non-empty results directory stops the run) is implemented in `_check_results` but has no direct unit case yet.
- `TC-FR6-04` (an informing failure alongside a passing blocking test) follows from the check logic and is covered in part by `test_a_plan_without_blocking_tests_fails_the_blocking_check`, but has no direct case with a passing blocking test.
- `TC-FR7-03` (duplicate canonical test IDs) is implemented in the collection path but has no direct unit case. `test_duplicate_function_names_get_distinct_ids` covers the non-duplicate case.

## Out of Scope

The following are follow-up stories and are not tested here:

- target installation API, Capabilities, registrations, enabled services, and release checks;
- provider-side test execution, execution environment images, podman jobs, and scratch clusters;
- test Tenants, provider resources, cleanup, leftovers, and cleanup journals;
- per-domain results and identities;
- release pipeline publication;
- E2E lab runs with real provider-side tests.

## Execution

```sh
# Unit and core integration tests
uv run pytest tests/unit/test_conformance_*.py

# Image smoke, when podman and network access are available
OSAC_CONFORMANCE_IMAGE_TEST=1 uv run pytest tests/unit/test_conformance_image.py
```
