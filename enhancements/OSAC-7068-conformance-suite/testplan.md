# Testplan - OSAC-7068

## Overview

- **Feature:** OSAC-7068 - OSAC Conformance Suite
- **Design:** [design.md](design.md)
- **Scope:** the core runner shipped by OSAC-7454
- **Total test cases:** 73 documented TC scenarios, backed by 138 pytest cases (parametrization expands some scenarios into multiple pytest cases)
- **Requirements covered:** see the traceability table; 12 of 12 PRD requirements are mapped, with deferred parts named
- **Interface changes covered:** IC-1 through IC-6, as referenced by each case

FR-N is the Nth In Scope item of the [PRD](prd.md). This plan preserves the PRD numbering and does not redefine an FR to mean a different section of the core.

This test plan covers the suite runner itself. Tests that a domain declares and runs against a provider, target installation reads, test Tenants, resource cleanup, and release publication are follow-up work and are out of scope here.

The 138 pytest cases are the collection count, including parametrizations. The documented TC scenarios below map the behavior those cases cover.

### Requirement traceability

| PRD requirement | Core status | Test section |
|---|---|---|
| FR-1: one image per release, release refusal, replacement | Partial: image build, UID, digest, packaged smoke gap; release refusal and replacement deferred | FR-1 |
| FR-2: component and end-to-end execution layers | Partial: generic pytest layer implemented; provider component layer deferred | FR-2 |
| FR-3: shared test Tenant, cleanup, leftovers | Deferred: the core creates no Tenant and reports empty leftovers | FR-3 |
| FR-4: selection by profiles and selectors, plan | Implemented | FR-4 |
| FR-5: one configuration file, per-domain sections, configuration errors | Partial: common and target keys and errors; per-domain sections deferred and rejected | FR-5 |
| FR-6: verdict per test/profile/component, named checks, report, evidence, diagnostics | Partial: test and profile verdict, three checks, report, JUnit, evidence, diagnostics; per-component results deferred | FR-6 |
| FR-7: domain model, networking first | Partial: marker catalog and Netris settings check; domain declarations deferred | FR-7 |
| FR-8: OSAC CI and E2E lab | Deferred | FR-8 |
| FR-9: self-reported report, one release and component version, rerun | Partial: report records release and image identity and plans rerun; component version is not read | FR-9 |
| FR-10: live output, list, run plan, keep, focused rerun, interrupt | Partial: list, run, plan, keep, focused plan, interrupt; child output is buffered and streaming is deferred | FR-10 |
| FR-11: secret redaction | Implemented | FR-11 |
| FR-12: installation and Fabric Manager documentation | Deferred | FR-12 |

### Fixtures

- **Synthetic pytest tree:** a temporary tree of pytest modules with conformance markers, a pass, a failure, a skip, a teardown failure, and duplicate function names.
- **Fake tree adapter:** an in-process `TestTree` implementation that returns fixed identities and outcomes, so the CLI, plan, verdict, and report can be tested without a pytest child.
- **Configuration fixture:** a temporary `conformance.yaml` and the files it names, including a token, a CA, and a kubeconfig.
- **Catalog fixture:** a temporary `catalog.yaml` with marker selectors and profiles.
- **Target kubeconfig fixture:** a temporary kubeconfig and a fake `kubectl` command for diagnostics and the Netris settings check.
- **Image smoke fixture:** podman, the Containerfile, and network access, enabled only when `OSAC_CONFORMANCE_IMAGE_TEST=1`.

### Test infrastructure

| Module | Covers |
|---|---|
| `tests/unit/test_conformance_config.py` | Configuration parsing, required keys, path traversal, duplicate keys, URL parsing, redactor inputs |
| `tests/unit/test_conformance_selection.py` | Catalog loading, profile expansion, selector union, plan replay |
| `tests/unit/test_conformance_verdict.py` | Profile results, three checks, result, focused exit codes |
| `tests/unit/test_conformance_report.py` | Report keys, redaction, JUnit XML |
| `tests/unit/test_conformance_execution.py` | Pytest collection, outcome mapping, evidence, process errors |
| `tests/unit/test_conformance_pytest_plugin.py` | Manifest, JSONL records, captured logging, log-file suppression |
| `tests/unit/test_conformance_interrupt.py` | First and second signal, forwarding, registration deferral |
| `tests/unit/test_conformance_redact.py` | Text and object redaction, registry auth, serialized annotations |
| `tests/unit/test_conformance_image_digest.py` | Environment and podman/Docker socket digest lookup, image ID fallback |
| `tests/unit/test_conformance_diagnostics.py` | Diagnostics files, namespace, failed command |
| `tests/unit/test_conformance_netris.py` | Netris ConfigMap check pass, fail, unreadable, null namespace, timeout |
| `tests/unit/test_conformance_integration.py` | list, run, run --plan, empty plan, unknown profile, interrupt |
| `tests/unit/test_conformance_image.py` | Containerfile build and --help smoke, gated by OSAC_CONFORMANCE_IMAGE_TEST=1 |

The fixtures use pytest `tmp_path`, `monkeypatch`, a fake `kubectl` command, fake runtime sockets serving the podman and Docker inspect APIs, and a synthetic pytest tree with real modules. The core integration test uses a fake `TestTree` adapter so the CLI and report can be exercised without a container.

### Coverage matrix

| Cases | Tier | Owner | Working directory | Boundary proved | Real | Simulated or omitted | Execution status |
|---|---|---|---|---|---|---|---|
| FR-1 to FR-12 core cases | Unit | [DEV] | `osac/` repository root | Core runner contracts | Runner, pytest plugin, fake commands | Signal delivery with a fake child, target installation, podman, container runtime | Implemented: `uv run pytest tests/unit/test_conformance_*.py` |
| FR-4, FR-5, FR-9, FR-10 integration cases | Core integration | [DEV] | `osac/` repository root | CLI to pytest child to report | Runner, pytest, synthetic tree | Interrupt delivery through the `_InterruptingTree` adapter (TC-FR10-09), target installation, container runtime | Implemented: `uv run pytest tests/unit/test_conformance_integration.py`; real-signal delivery is TC-FR10-12 and is not automated |
| FR-1 image and FR-1 packaged smoke | Image smoke | [DEV] | `osac/` repository root | Containerfile, entry point, packaged run | Podman, image build | Target installation | Implemented for `--help`; packaged `list` to `run --plan` is a gap |

All commands run from the `osac` repository root. `[DEV]` owns the core runner and its tests. `[QE]` owns the deferred CI and E2E lab work. `[DOCS]` owns the deferred guide updates.

TC-FR10-09 is simulated: the core integration adapter raises `Interrupted` directly instead of delivering a signal to a live pytest child. TC-FR10-12 is the real-signal case and is not automated yet.

## Test Cases

### FR-1: One suite image per OSAC release

Release refusal and replacement are not implemented in the core; see TC-FR1-05.

#### TC-FR1-01: The image builds and starts

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-1 | [DEV] | IC-1 | critical | automated |

##### Preconditions

- podman is available and can pull the pinned UBI and kubectl images.
- `OSAC_CONFORMANCE_IMAGE_TEST=1`.

##### Steps

1. Build `tests/conformance/Containerfile` from the repository root.
2. Run `podman run --rm <tag> --help`.

##### Expected Results

- The build exits 0 and produces an image tagged `<tag>`.
- `podman run --rm <tag> --help` exits 0 and prints the `osac-conformance` usage.
- The image contains `osac-conformance` and `kubectl`; the final image stage sets `USER 1001`.

#### TC-FR1-02: The image digest comes from the environment first

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-1 | [DEV] | IC-1 | critical | automated |

##### Preconditions

- A fake podman or Docker socket and a set `OSAC_CONFORMANCE_SUITE_IMAGE_DIGEST`.

##### Steps

1. Call `suite_image_digest()` with both the environment variable and the socket available.

##### Expected Results

- The environment variable wins and no socket request is made.

#### TC-FR1-03: The image digest falls back through the runtime

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-1 | [DEV] | IC-1 | high | automated |

##### Preconditions

- A fake libpod or Docker-compatible socket serving container inspect.

##### Steps

1. Call `suite_image_digest()` without the environment variable.
2. Serve `ImageName`, `ImageDigest`, `Config.Image`, `RepoDigests`, and `Image` in separate cases.

##### Expected Results

- The digest is read from the highest-precedence field.
- A Docker-compatible reference resolves its repo digest.
- The runtime image ID is the fallback when no registry digest is available.
- An unreachable socket falls back to the environment or returns an empty string.

#### TC-FR1-04: A packaged list and run smoke is a gap

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-1 | [DEV] | IC-1, IC-5 | high | manual |

##### Preconditions

- The built image, a mounted configuration, and an empty results directory.

##### Steps

1. Run `osac-conformance list` in the image.
2. Run `osac-conformance run --plan /results/conformance-plan.yaml`.

##### Expected Results

- The packaged test tree is collected, the mounted configuration is read, and `conformance-plan.yaml`, `conformance-report.yaml`, and `junit.xml` are written.
- This case is not automated yet; the current image smoke only runs `--help`.

#### TC-FR1-05: Release refusal and replacement are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7457 | AC-1 | [DEV] | IC-1 | high | manual |

##### Preconditions

- A target installation on a different release than `osacRelease`.

##### Steps

1. Run `osac-conformance run` against the target.

##### Expected Results

- The core does not read the target release and does not refuse the run.
- Release comparison and the replacement of `osac-network-conformance` are follow-up work.

### FR-2: Two execution layers

The generic pytest layer is implemented. Provider component execution is deferred; see TC-FR2-05.

#### TC-FR2-01: Pytest outcomes map to conformance results

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A tree with a passing, failing, skipped, and teardown-failing test.

##### Steps

1. Run the plan through pytest.
2. Read the JSONL records.

##### Expected Results

- A passing test has one `call` record with `outcome: passed` and maps to `pass`.
- A failing test has a `call` record with `outcome: failed`, `message` equal to `str(report.longrepr)`, and maps to `fail`.
- A skipped test has a `call` or `setup` record with `outcome: skipped` and maps to `skip`; a teardown skip maps to `skip`.
- A teardown failure adds a `teardown` record with `outcome: failed` and maps to `fail`.
- `durationSeconds` is the sum of the `duration` fields in the test records.

#### TC-FR2-02: Captured output and logging reach the evidence log

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A test that writes stdout, stderr, and captured logging.

##### Steps

1. Run the plan.
2. Read `tests/<hash>/test.log`.

##### Expected Results

- The log holds the captured logging, stdout, and stderr after redaction.

#### TC-FR2-03: Collection failure and pytest process errors are configuration errors

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A tree with a collection error.
- A child process that exits 3, 4, or 5.

##### Steps

1. Run the plan.

##### Expected Results

- Exit 2.
- No report is written.
- The error includes the pytest output.

#### TC-FR2-04: Duplicate function names get distinct IDs

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-6 | low | automated |

##### Preconditions

- Two test functions with the same name in different modules, or parameterized cases.

##### Steps

1. Collect the tree.

##### Expected Results

- Each canonical node ID is unique and each evidence directory is distinct.

#### TC-FR2-05: Provider component execution is deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7456 | N/A | [DEV] | IC-1 | high | manual |

##### Preconditions

- A provider component with an execution environment image.

##### Steps

1. Attempt to run a component test through the core.

##### Expected Results

- The core does not start execution environment images, podman jobs, or scratch clusters.
- The component layer is follow-up work.

### FR-3: Shared test Tenant, cleanup, and leftovers

The core creates no Tenant and no resources, so cleanup and leftovers are deferred; see TC-FR3-01 and TC-FR3-02.

#### TC-FR3-01: The core creates no Tenant and reports empty leftovers

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7455 | N/A | [DEV] | IC-5 | high | manual |

##### Preconditions

- A complete run.

##### Steps

1. Read `leftovers[]` and inspect the target namespace for a Tenant.

##### Expected Results

- `leftovers[]` is empty and no Tenant is created.
- Tenant creation and cleanup are follow-up work.

#### TC-FR3-02: Resource cleanup is deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7455 | N/A | [DEV] | IC-5 | high | manual |

##### Preconditions

- A test that creates an OSAC resource.

##### Steps

1. Run the plan and inspect the target.

##### Expected Results

- The core does not create provider resources, does not clean them up, and has no cleanup journal.
- Cleanup and leftover recovery are follow-up work.

### FR-4: Selection by profiles and selectors, and the plan

#### TC-FR4-01: Generic always applies and selectors are deduplicated

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-4 | critical | automated |

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

#### TC-FR4-02: A test can count toward multiple profiles

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-4, IC-6 | high | automated |

##### Preconditions

- A test carrying `conformance_generic` and `conformance_vmaas`.

##### Steps

1. Assign profiles for `[generic, vm]`.

##### Expected Results

- The test `profiles` list holds `generic` and `vm`.
- The plan holds the test once.

#### TC-FR4-03: An unknown profile is a configuration error

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-2, IC-4 | critical | automated |

##### Preconditions

- A configuration selecting a profile the catalog does not ship.

##### Steps

1. Run `list`.

##### Expected Results

- Exit 2.
- The error names the unknown profile.
- No report is written.

#### TC-FR4-04: Collection records markers and node IDs

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-6 | critical | automated |

##### Preconditions

- A synthetic tree with selector and classification markers.

##### Steps

1. Run the collection pass.
2. Read the manifest.

##### Expected Results

- Each item has `nodeid`, `name`, and sorted marker names.
- The runner derives a canonical ID relative to the tree root.

#### TC-FR4-05: Classification defaults to blocking

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-6 | critical | automated |

##### Preconditions

- Tests with `conformance_blocking`, `conformance_informing`, and neither marker.

##### Steps

1. Build the test identities.

##### Expected Results

- `conformance_informing` is informing.
- `conformance_blocking` is blocking.
- A test with neither marker is blocking.

#### TC-FR4-06: Duplicate test IDs are a configuration error

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-6 | high | manual |

##### Preconditions

- Two tests with the same canonical ID.

##### Steps

1. Run collection.

##### Expected Results

- Exit 2 with a duplicate-ID error.
- This case is implemented in the collection path but has no direct unit case yet.

#### TC-FR4-07: The plan is the union of selected selectors

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-4, IC-5 | critical | automated |

##### Preconditions

- A synthetic tree with generic, vmaas, bmaas, caas, netris, multi-selector, and informing tests.

##### Steps

1. Run `list` with `profiles: [vm]`.
2. Read `conformance-plan.yaml`.

##### Expected Results

- The plan holds the union of `generic` and `vmaas` tests.
- Each test has `id`, `key`, `name`, `profiles`, and `markers`.
- `complete` is `true`.

#### TC-FR4-08: list writes and prints the plan without creating the log

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- An empty results directory.

##### Steps

1. Run `list`.
2. Inspect stdout and the results directory.

##### Expected Results

- The plan is written to `/results/conformance-plan.yaml` and printed.
- No `conformance.log` is created.
- The directory can accept a later `run --plan`.

#### TC-FR4-09: A narrower plan is incomplete and still replayable

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A plan with one of several selected tests.

##### Steps

1. Run `run --plan <file>`.

##### Expected Results

- The subset tests run; tests omitted from the plan do not run.
- `report.complete is False`.
- The `complete-plan` check has `result: fail`; `report.result == "in progress"`.
- `exit_code(report, focused=True) == 0` when at least one selected blocking test ran, every selected blocking test passed, and `report.leftovers == []`.

#### TC-FR4-10: The opaque plan key replays a redacted test ID

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A plan whose test `id` was redacted and whose `key` is the SHA-256 of the original ID.

##### Steps

1. Run `run --plan <file>`.

##### Expected Results

- The test is resolved by `key` and runs.

#### TC-FR4-11: An empty plan, unknown test, or unselected test is an error

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-5 | critical | automated |

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

#### TC-FR4-12: list and run work against a synthetic tree

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-3, IC-5 | critical | automated |

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

#### TC-FR4-13: Development catalog and tree overrides are not a conformance verdict

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-3 | [DEV] | IC-4, IC-5 | high | manual |

##### Preconditions

- A run with `--catalog` or `--tree` pointing at a development catalog or tree.

##### Steps

1. Run `list` and `run` with the override.
2. Inspect the report provenance.

##### Expected Results

- The override is used and a report is written.
- The report does not record the override.
- The run is a development run, not a conformance verdict; follow-up should mark or remove the overrides in release images.

### FR-5: One configuration file

Per-domain configuration sections are deferred and rejected by the loader; see TC-FR5-09.

#### TC-FR5-01: Common keys load and defaults apply

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2 | critical | automated |

##### Preconditions

- A valid `conformance.yaml` without `profiles`, `target.namespace`, or `timeouts`.

##### Steps

1. Load the configuration.

##### Expected Results

- `profiles` defaults to `[generic]`.
- `target.namespace` defaults to `osac`.
- `timeouts` defaults to an empty mapping.
- Paths are canonicalized.

#### TC-FR5-02: Unknown keys and domain sections are rejected

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2 | critical | automated |

##### Preconditions

- A configuration with an unknown top-level key, an unknown `target` key, an unknown `target.aap` key, or a `networking:` section.

##### Steps

1. Load the configuration.

##### Expected Results

- `stderr` contains `osac-conformance: <key> is not defined by this release` for each unknown key, including `networking is not defined by this release` for the domain section.
- `main()` returns 2 and the results directory contains no report.

#### TC-FR5-03: Required target keys and value types are enforced

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2 | critical | automated |

##### Preconditions

- A configuration missing `target.kubeconfig`, `target.apiURL`, `target.tokenFile`, or `target.caFile`.
- A configuration with `profiles` not a list of strings.

##### Steps

1. Load each configuration.

##### Expected Results

- `ConfigError.checks` contains `target.kubeconfig must be a non-empty string` (and the matching message for each other missing key), or `profiles must be a list of non-empty strings`.
- `load_config` returns no `Config`.

#### TC-FR5-04: Unsafe paths and duplicate keys are rejected

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2 | critical | automated |

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

#### TC-FR5-05: URLs must parse

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2 | high | automated |

##### Preconditions

- `target.apiURL` values `https://[`, `not-a-url`, and a valid URL.
- An invalid `target.aap.url`.

##### Steps

1. Load each configuration.

##### Expected Results

- `ConfigError.checks` contains `target.apiURL must be an absolute URL with a host` for `https://[` and `not-a-url`.
- It contains `target.aap.url must be an absolute URL with a host` for the invalid AAP URL.
- A malformed URL does not replace an earlier configuration error; both messages are present.

#### TC-FR5-06: The redactor is seeded from the configuration

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2, IC-5 | critical | automated |

##### Preconditions

- A token file, an AAP token file, a kubeconfig with token, password, and client key data, and hosts in `apiURL` and the kubeconfig server.

##### Steps

1. Build the redactor for the configuration.
2. Redact text containing each value and host.

##### Expected Results

- Every configured secret and host becomes `<redacted>`.

#### TC-FR5-07: A configuration error writes no report

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-2, IC-5 | critical | automated |

##### Preconditions

- A missing configuration file.
- An unknown key.

##### Steps

1. Run `list` or `run`.

##### Expected Results

- `main()` returns 2.
- `stderr` contains `osac-conformance: <message>` for each failing check.
- The results directory contains no `conformance-report.yaml` or `junit.xml`.
- A token value and API host from the configuration are absent from `stderr` and replaced by `<redacted>`.

#### TC-FR5-08: A non-empty results directory stops the run

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-2 | [DEV] | IC-5 | critical | manual |

##### Preconditions

- A results directory containing a file other than `conformance-plan.yaml`.

##### Steps

1. Run `list`.

##### Expected Results

- Exit 2.
- The unexpected entries are named.
- No report is written.
- This case is implemented in `_check_results` but has no direct unit case yet.

#### TC-FR5-09: Per-domain configuration sections are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7456 | AC-2 | [DEV] | IC-2 | high | manual |

##### Preconditions

- A `conformance.yaml` with a `networking:` section.

##### Steps

1. Load the configuration.

##### Expected Results

- The core rejects the section as an unknown key.
- Per-domain configuration sections and the selected tests reading them are follow-up work.

### FR-6: Verdict, report, evidence, and diagnostics

Per-component results are deferred; see TC-FR6-13.

#### TC-FR6-01: All passing checks produce a conformant verdict

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | critical | automated |

##### Preconditions

- A complete plan with passing blocking tests and no leftovers.

##### Steps

1. Evaluate the report.

##### Expected Results

- `[check.id for check in report.checks] == ["all-blocking-tests-pass", "no-leftovers", "complete-plan"]`.
- Every `check.result == "pass"`.
- `report.result == "conformant"` and `exit_code(report) == 0`.

#### TC-FR6-02: A blocking failure or skip fails the blocking check

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | critical | automated |

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

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | high | automated |

##### Preconditions

- A plan containing only informing tests.

##### Steps

1. Evaluate the report.

##### Expected Results

- `all-blocking-tests-pass` fails with `no blocking tests in the plan`.
- An informing-only plan is not a conformance verdict.

#### TC-FR6-04: An informing failure does not fail a check

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | critical | manual |

##### Preconditions

- A complete plan with passing blocking tests and one failing informing test.

##### Steps

1. Evaluate the report.

##### Expected Results

- The informing test is `fail` in `tests[]`.
- No check fails.
- `result` is `conformant`.
- Exit code is 0.
- This combination has no direct unit case yet; the individual behaviors are covered.

#### TC-FR6-05: Leftovers and incomplete plans fail their checks

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | high | automated |

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

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3, IC-4 | high | automated |

##### Preconditions

- A selected profile whose planned tests are all informing.

##### Steps

1. Derive the profile result.

##### Expected Results

- `required` is `true`.
- `result` is `skip`.

#### TC-FR6-07: The report has exactly the defined keys

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | critical | automated |

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

#### TC-FR6-08: Report messages and check messages are redacted

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3, IC-5 | critical | automated |

##### Preconditions

- A test message, a check message, and a leftover containing a known secret.

##### Steps

1. Write the report.

##### Expected Results

- Every known secret is `<redacted>`.

#### TC-FR6-09: JUnit has one testcase per test

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | critical | automated |

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

#### TC-FR6-10: XML-invalid characters cannot split a secret

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | high | automated |

##### Preconditions

- A message containing a secret split by a C0 control character.

##### Steps

1. Write the JUnit XML.

##### Expected Results

- The control character is removed and the secret is redacted.

#### TC-FR6-11: Evidence is confined and bounded

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A test ID with `..`, `/`, `:`, and a long parameter.

##### Steps

1. Write evidence.

##### Expected Results

- The path stays under `tests/<hash>/`.
- The directory name is 16 hex characters.
- The test ID is not repeated in the path.

#### TC-FR6-12: Diagnostics are redacted and use the configured namespace

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A fake `kubectl` returning control-plane state and pod logs.
- A configured namespace.

##### Steps

1. Collect diagnostics.

##### Expected Results

- `diagnostics/osac-state.yaml` holds the redacted YAML from `kubectl get pods,deployments,events -n <namespace> -o yaml`.
- `diagnostics/pod-logs.txt` holds the redacted output of `kubectl logs -n <namespace> -l app.kubernetes.io/part-of=osac --tail=2000`.
- Both commands use `target.namespace`.
- A failed command writes `diagnostics command failed: <error>` with the error redacted.

#### TC-FR6-13: Per-component results are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7456 | N/A | [DEV] | IC-3 | high | manual |

##### Preconditions

- A registered provider component.

##### Steps

1. Run the suite and inspect the report.

##### Expected Results

- The report has no `components[]` key and no per-component result.
- Component identity and per-component conformance are follow-up work.

### FR-7: Domain model, networking first

Domain declarations are deferred; the core ships a marker catalog and the Netris settings check; see TC-FR7-06.

#### TC-FR7-01: The Netris setting present passes

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-4 | [DEV] | IC-4 | critical | automated |

##### Preconditions

- A `network-fulfillment-ig` ConfigMap with `NETRIS_CONTROLLER_URL` set.

##### Steps

1. Run the Netris settings check.

##### Expected Results

- The check passes.

#### TC-FR7-02: The Netris setting missing fails

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-4 | [DEV] | IC-4 | critical | automated |

##### Preconditions

- A `network-fulfillment-ig` ConfigMap without `NETRIS_CONTROLLER_URL`.

##### Steps

1. Run the Netris settings check.

##### Expected Results

- The check fails with `NETRIS_CONTROLLER_URL is not set in network-fulfillment-ig`.
- The test is informing and does not fail `all-blocking-tests-pass`.

#### TC-FR7-03: An unreadable Netris ConfigMap fails

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-4 | [DEV] | IC-4 | high | automated |

##### Preconditions

- A `kubectl` command that exits non-zero.

##### Steps

1. Run the Netris settings check.

##### Expected Results

- The check fails with the kubectl stderr in the message.

#### TC-FR7-04: An explicit null namespace falls back to osac

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-4 | [DEV] | IC-4 | high | automated |

##### Preconditions

- A configuration with `target.namespace: null`.

##### Steps

1. Run the Netris settings check.

##### Expected Results

- The check reads the `network-fulfillment-ig` ConfigMap in `osac`.

#### TC-FR7-05: A kubectl timeout fails the check

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-4 | [DEV] | IC-4 | high | automated |

##### Preconditions

- A `kubectl` command that exceeds 60 seconds.

##### Steps

1. Run the Netris settings check.

##### Expected Results

- The check fails with `kubectl get configmap network-fulfillment-ig timed out after 60 seconds`.

#### TC-FR7-06: Domain declarations are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7456 | N/A | [DEV] | IC-4 | high | manual |

##### Preconditions

- A domain that declares tests, configuration, identity, checks, timeouts, or reference components.

##### Steps

1. Inspect the shipped catalog and tests.

##### Expected Results

- The core ships a marker catalog and the Netris settings test only.
- Domain declarations and domain-specific checks are follow-up work.

### FR-8: OSAC CI and E2E lab

No CI job or E2E lab run exists yet; see TC-FR8-01.

#### TC-FR8-01: OSAC CI and E2E lab runs are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7457 | N/A | [QE] | IC-1 | high | manual |

##### Preconditions

- An OSAC CI job and an E2E lab target with real provider-side tests.

##### Steps

1. Run the suite in CI and in the E2E lab.

##### Expected Results

- The core has no CI job or E2E lab run yet.
- Reference components, E2E lab scheduling, and promotion from informing to blocking are follow-up work.

### FR-9: Self-reported report and rerun

Component version and one-report-per-component are deferred; see TC-FR9-03.

#### TC-FR9-01: The report records the release and image identity

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-3 | high | automated |

##### Preconditions

- A report from a run.

##### Steps

1. Read `osacRelease` and `suiteImageDigest`.

##### Expected Results

- `osacRelease` equals the configured release.
- `suiteImageDigest` is the environment value, a registry digest, a runtime image ID, or an empty string.

#### TC-FR9-02: A saved plan reruns the same tests or a subset

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-5 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A plan written by `list`.

##### Steps

1. Run `run --plan <file>`.
2. Run a narrower plan.

##### Expected Results

- The same plan runs the same tests.
- A narrower plan runs a subset and is reported `in progress`.

#### TC-FR9-03: One component version per report is deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7456 | N/A | [DEV] | IC-3 | high | manual |

##### Preconditions

- Two versions of a provider component.

##### Steps

1. Run the suite against each version.

##### Expected Results

- The core does not read component identity or version.
- One passing report per component version is follow-up work.

### FR-10: Live output, commands, and interrupt handling

Child output is buffered and the signal gate covers the pytest child only; see TC-FR10-05, TC-FR10-10, and TC-FR10-11.

#### TC-FR10-01: The run ID is eight lowercase alphanumeric characters

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A new run.

##### Steps

1. Generate a run ID.

##### Expected Results

- The ID matches `[a-z0-9]{8}`.

#### TC-FR10-02: Output goes to stdout and the log with a timestamp and redaction

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- An `OutputSink` with a known secret.

##### Steps

1. Write a line.

##### Expected Results

- stdout and `conformance.log` both hold the timestamped line.
- The secret is `<redacted>`.

#### TC-FR10-03: list does not create the run log

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- An empty results directory.

##### Steps

1. Run `list`.

##### Expected Results

- The plan is written and printed.
- `conformance.log` is not created.

#### TC-FR10-04: --keep is accepted and has no effect

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A run with `--keep`.

##### Steps

1. Run a plan with `--keep`.

##### Expected Results

- The flag is accepted.
- No resources are retained because the core creates none.
- `leftovers[]` is empty.

#### TC-FR10-05: Child output is buffered until pytest exits

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | manual |

##### Preconditions

- A long-running test that writes output before it finishes.

##### Steps

1. Run the plan and observe the runner output timing.

##### Expected Results

- The child stdout and stderr appear after `process.communicate()` returns, not while the test is running.
- Streaming through the redactor is follow-up work.

#### TC-FR10-06: The first signal forwards SIGINT and keeps completed outcomes

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A running pytest child and one completed test.

##### Steps

1. Send SIGINT.
2. Read the report.

##### Expected Results

- The child receives SIGINT.
- The completed test keeps its outcome.
- The report is written.
- The process returns 130.

#### TC-FR10-07: The second signal kills the child and writes no report

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- A running pytest child.

##### Steps

1. Send SIGINT twice.

##### Expected Results

- The child is killed.
- No report is written.
- The process returns 130.

#### TC-FR10-08: A signal during registration is replayed after attachment

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A signal arrives between `Popen` returning and the child handle being attached.

##### Steps

1. Trigger the signal during registration.

##### Expected Results

- The signal is deferred.
- The child is attached.
- The signal reaches the child.
- Two signals escalate after attachment.

#### TC-FR10-09: Interrupt outcomes supplied by the adapter are reported

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | automated |

##### Preconditions

- The core integration adapter `_InterruptingTree` raises `Interrupted` with one completed outcome.

##### Steps

1. Run `run` with the fake adapter.

##### Expected Results

- The CLI preserves the supplied completed outcome, writes the report, and returns 130.
- This case is simulated: it does not deliver a signal to a live pytest child.

#### TC-FR10-10: The interrupt result line and return code are a known mismatch

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | manual |

##### Preconditions

- An interrupted run.

##### Steps

1. Read the `result:` line and the process return code.

##### Expected Results

- The `result:` line shows the verdict-derived exit code (0 or 1).
- The process returns 130.
- Computing the final exit code once is follow-up work.

#### TC-FR10-11: The signal gate covers only the pytest child

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | manual |

##### Preconditions

- An interrupt during collection or report writing.

##### Steps

1. Send SIGINT before or after the pytest child runs.

##### Expected Results

- Collection and report/diagnostics writing are not signal-protected.
- Extending the signal guarantee to those phases is follow-up work.

#### TC-FR10-12: A real SIGINT reaches a live pytest child

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-7 | [DEV] | IC-5 | high | manual |

##### Preconditions

- A live pytest child with one completed test and one running test.

##### Steps

1. Run `run`.
2. Send SIGINT to the runner process.

##### Expected Results

- The signal reaches the live pytest child.
- The child stops gracefully and writes the completed outcomes.
- The runner reads the outcomes, writes the report, and returns 130.
- This real-signal path is not automated yet; the integration case uses a fake adapter.

### FR-11: Secret redaction

#### TC-FR11-01: Known secrets and hosts are redacted

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-6 | [DEV] | IC-2, IC-5 | critical | automated |

##### Preconditions

- A redactor seeded with a secret and a host.

##### Steps

1. Redact text containing both.

##### Expected Results

- Both become `<redacted>`.

#### TC-FR11-02: Existing sanitizer rules are composed

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-6 | [DEV] | IC-5 | critical | automated |

##### Preconditions

- Text with a bearer token, a Basic credential, an assignment, and a JSON secret.

##### Steps

1. Redact the text.

##### Expected Results

- The existing `sanitize_text` rules apply unchanged.

#### TC-FR11-03: Structured objects are redacted recursively

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7454 | AC-6 | [DEV] | IC-5 | high | automated |

##### Preconditions

- A nested object with credential-named keys, a container environment name/value pair, a registry auth config entry, and a serialized annotation.

##### Steps

1. Redact the object.

##### Expected Results

- Every credential value is `<redacted>`.
- Non-credential values are unchanged.
- A serialized JSON annotation is redacted by structure.

### FR-12: Documentation

The installation and Fabric Manager guides are not updated; see TC-FR12-01.

#### TC-FR12-01: Documentation pointers are deferred

| Story | AC | Owner | Interface Change | Priority | Automation |
|---|---|---|---|---|---|
| OSAC-7458 | N/A | [DOCS] | IC-1 | low | manual |

##### Preconditions

- The installation guide and the Fabric Manager guide.

##### Steps

1. Inspect the guides for the suite run section and the go-live checklist.

##### Expected Results

- The core change does not update the guides.
- The installation guide ending with the suite run and the Fabric Manager guide pointing to it are follow-up work.

## Gaps

The PRD items moved to follow-up stories are listed under [Out of Scope](#out-of-scope) and are not counted as covered by this core test plan.

- `TC-FR1-04` (A packaged list and run smoke is a gap): manual or deferred.
- `TC-FR1-05` (Release refusal and replacement are deferred): manual or deferred.
- `TC-FR2-05` (Provider component execution is deferred): manual or deferred.
- `TC-FR3-01` (The core creates no Tenant and reports empty leftovers): manual or deferred.
- `TC-FR3-02` (Resource cleanup is deferred): manual or deferred.
- `TC-FR4-06` (Duplicate test IDs are a configuration error): manual or deferred.
- `TC-FR4-13` (Development catalog and tree overrides are not a conformance verdict): manual or deferred.
- `TC-FR5-08` (A non-empty results directory stops the run): manual or deferred.
- `TC-FR5-09` (Per-domain configuration sections are deferred): manual or deferred.
- `TC-FR6-04` (An informing failure does not fail a check): manual or deferred.
- `TC-FR6-13` (Per-component results are deferred): manual or deferred.
- `TC-FR7-06` (Domain declarations are deferred): manual or deferred.
- `TC-FR8-01` (OSAC CI and E2E lab runs are deferred): manual or deferred.
- `TC-FR9-03` (One component version per report is deferred): manual or deferred.
- `TC-FR10-05` (Child output is buffered until pytest exits): manual or deferred.
- `TC-FR10-10` (The interrupt result line and return code are a known mismatch): manual or deferred.
- `TC-FR10-11` (The signal gate covers only the pytest child): manual or deferred.
- `TC-FR10-12` (A real SIGINT reaches a live pytest child): manual or deferred.
- `TC-FR12-01` (Documentation pointers are deferred): manual or deferred.

## Out of Scope

The following are follow-up stories and are not tested here:

- target installation API, Capabilities, registrations, enabled services, and release checks;
- provider-side test execution, execution environment images, podman jobs, and scratch clusters;
- test Tenants, provider resources, cleanup, leftovers, and cleanup journals;
- per-domain results and identities;
- release pipeline publication;
- E2E lab runs with real provider-side tests;
- installation and Fabric Manager guide updates.

## Summary

| Metric | Count |
|---|---|
| Documented TC scenarios | 73 |
| Pytest cases represented | 138 |
| Critical | 36 |
| High | 35 |
| Medium | 0 |
| Low | 2 |
| Automated | 54 |
| Manual | 19 |

## Execution

```sh
# Unit and core integration tests
uv run pytest tests/unit/test_conformance_*.py

# Image smoke, when podman and network access are available
OSAC_CONFORMANCE_IMAGE_TEST=1 uv run pytest tests/unit/test_conformance_image.py
```
