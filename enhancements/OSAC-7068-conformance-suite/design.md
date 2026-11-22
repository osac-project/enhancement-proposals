---
title: osac-conformance-suite
authors:
  - dmanor@redhat.com
creation-date: 2026-10-22
last-updated: 2026-11-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-7068
prd: "prd.md"
see-also:
  - Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md
  - Per-Service Enablement: /enhancements/OSAC-3046-per-service-enablement/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Conformance Suite

## Summary

OSAC publishes one conformance suite image per release, `ghcr.io/osac-project/osac-conformance:<release>`, that runs a release's conformance tests against a target installation. The first shipped piece is a small runner in `tests/conformance/`. It reads `conformance.yaml`, expands the selected profiles from a shipped catalog into selectors, collects the pytest tests whose markers match those selectors, computes a plan, runs the plan through pytest, applies named checks, and writes `conformance-report.yaml`, `junit.xml`, `conformance.log`, per-test evidence, and a diagnostics bundle to the results directory.

This revision describes the core runner that OSAC-7454 implements. Target installation reads, provider-side test execution, test Tenants, provider resources, cleanup, and release publication are follow-up work. The design keeps one runner, one configuration file, one plan format, and one report format so those follow-up stories add behavior without adding a second tool.

## Motivation

Providers plug their own components into OSAC. The first is the network Fabric Manager, an Ansible role that OSAC runs as AAP jobs. The suite that proves a Fabric Manager works was first defined inside the [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md) as the networking-only image `osac-network-conformance`, which no release published; the merged contract (section 4.11) defines networking as a domain of this suite.

The generic rules are not networking rules. One runner, one configuration file, one plan, one report, and one redaction boundary serve every domain. Keeping those rules in one place means the next domain adds selectors and tests, not a second suite.

The core runner is the first deliverable because every later part depends on it: the catalog and marker vocabulary, the plan format, the result rules, the report and JUnit mapping, the redaction boundary, and the interrupt behavior. [User]

### Goals

- One runner and one report format for every domain.
- Selection is declared with markers and a shipped catalog, not inferred from the target installation.
- The plan is reproducible: `list` writes it, `run` executes the same plan, and `run --plan` reruns a saved plan or a subset.
- One verdict made of named checks, each with a rule, a remedy, and a short message.
- One redaction boundary covers stdout, the timestamped log, evidence, messages, JUnit, the report, and diagnostics.
- The runner works in a container as an unprivileged user with only the configuration and results directories mounted.

### Non-Goals

- Reading the target installation's fulfillment API, Capabilities, registrations, enabled services, or installed release.
- Running provider-side tests, execution environment images, podman jobs, or scratch clusters.
- Creating a test Tenant, provider-scoped resources, or cleanup journals.
- Per-domain results, identities, or domain-specific checks.
- Selectors that discover tests without markers. Every selector shipped here is a marker selector.
- Changing any OSAC API, CRD, or controller.
- Starting the suite or showing its report from the OSAC console, API, or CLI.
- Upgrade and air-gapped modes.
- Publishing the image from the release pipeline. That is follow-up work.
- Parallel test execution. The core runs pytest with `-n 0`.

## Proposal

The runner is a Python package under `tests/conformance/` with an `osac-conformance` entry point. It has no service, database, or controller. It reads the run configuration, expands the selected profiles from the shipped catalog, collects pytest tests and their markers, computes a plan, runs the plan in a pytest child process, and turns the recorded outcomes into a report.

The flow is:

```text
profiles -> selectors -> marked tests -> plan -> pytest outcomes -> checks -> report
```

Terms used in this document:

- **Selector:** a named marker matcher. The shipped catalog contains `generic`, `vmaas`, `bmaas`, `caas`, and `netris`; each maps to a pytest marker such as `conformance_generic`.
- **Profile:** a named bundle of selectors. The shipped catalog contains `generic`, `vm`, `baremetal`, `cluster`, and `netris`. `generic` always applies.
- **Test:** a pytest item that carries one or more conformance markers. Its classification is `blocking` unless it carries `conformance_informing`.
- **Plan:** the tests selected by the union of the selected profiles' selectors, with duplicate selectors and tests removed.
- **Run:** one execution of the runner. A run has an 8-character lowercase alphanumeric run ID.
- **Classification:** `blocking` or `informing`. A failing blocking test fails a check; a failing informing test is reported and does not fail a check.
- **Check:** a named rule in the verdict, with the rule it applies, its remedy, and a short message. The installation passes when every check passes.

The catalog is data. The runner never branches on a selector or profile name. A new profile is a catalog entry; a new selector is a catalog entry plus a marker in `pyproject.toml` and markers on tests.

## Workflow Description

**Actor.** The Cloud Infrastructure Admin, who owns and operates the target installation and runs the suite. The core only reads the target's kubeconfig for diagnostics and the networking Netris settings check. It does not call the fulfillment API.

**Starting state.** The operator has a configuration directory with `conformance.yaml` and the target hub kubeconfig it names, and a new empty results directory.

1. The operator writes `conformance.yaml` with `osacRelease`, the selected `profiles`, and the `target` block. Paths in the file are container paths.
2. The operator runs the image with the configuration directory mounted read-only at `/config` and the results directory mounted at `/results`:

   ```sh
   podman run --rm --userns=keep-id:uid=1001,gid=1001 \
     -e OSAC_CONFORMANCE_SUITE_IMAGE_DIGEST="$digest" \
     -v "$PWD/config:/config:ro" -v "$PWD/results:/results" \
     ghcr.io/osac-project/osac-conformance:<release> run
   ```

3. The runner loads and validates `conformance.yaml`, loads the catalog, expands the selected profiles into selectors, checks that the results directory is empty or holds only a plan, and reads its own image digest.
4. It collects the pytest tests through a collection pass and records each test's node ID, name, and markers.
5. It computes the plan, or loads the plan named by `--plan`, and validates it.
6. It runs the plan in a pytest child process. The pytest plugin records each test's outcome and captured output as JSONL.
7. It maps outcomes to `pass`, `fail`, or `skip`, derives the selected profiles' results, applies the three named checks, and writes the report and JUnit XML.
8. It writes the diagnostics bundle and prints the overall result and exit code.

`list` stops after step 5: it writes and prints the plan, creates nothing in any target installation, and does not create `conformance.log`, so the same results directory can accept a later `run --plan`.

**Alternative paths.**

- **Configuration error.** The runner prints each failing check to stderr, writes no report, and exits 2.
- **A blocking test fails.** The test is `fail`; `all-blocking-tests-pass` fails; the report says `in progress`; the exit code is 1 for a complete run.
- **An informing test fails.** The test is `fail`; no check fails; the report result is unaffected.
- **A blocking test reports `skip`.** It is not a pass; `all-blocking-tests-pass` fails.
- **The plan is a focused subset.** `complete-plan` fails, the report says `in progress`, and a focused run still exits 0 when at least one selected blocking test ran, every selected blocking test passed, and no leftovers exist.
- **pytest cannot collect or exits with a process error.** The runner reports a configuration error, writes no report, and exits 2.
- **The run is interrupted.** On the first SIGINT or SIGTERM the runner forwards SIGINT to the pytest child, waits for it to stop, reads the outcomes it wrote, writes a report, and exits 130. A second signal kills the child and exits 130 with no report.
- **The runner is killed.** The run ID is in the first line of `conformance.log`; no cleanup is needed because the core creates no target resources.

## API Extensions

No new or changed gRPC service, REST resource, CRD, webhook, or finalizer. The core calls no OSAC API. It reads the target installation's hub kubeconfig only for the diagnostics bundle and the networking Netris settings check.

The suite adds these new surfaces:

| ID | Surface | Change | Requirements |
|---|---|---|---|
| IC-1 | Suite image and its `podman run` invocation | New image `ghcr.io/osac-project/osac-conformance:<release>`, two required mounts (configuration and results), and an optional runtime socket for digest lookup. | FR-1, FR-8 |
| IC-2 | `conformance.yaml` | New configuration file with `osacRelease`, `profiles`, `target`, and `timeouts`. | FR-5 |
| IC-3 | `conformance-report.yaml` and JUnit XML | New report with the selection, per-test outcomes, three named checks, and the result. | FR-4, FR-6, FR-9, FR-11 |
| IC-4 | Conformance catalog | Shipped `catalog.yaml` with marker selectors and profiles. Operators select profiles from it. | FR-4, FR-7 |
| IC-5 | `osac-conformance` commands, the plan, timestamped output, evidence, and diagnostics | `list`, `run`, `run --plan`, `--keep`, the plan file, the timestamped timestamped log, per-test evidence, and the diagnostics bundle. | FR-4, FR-10, FR-11 |
| IC-6 | Conformance pytest markers | Tests in the test tree carry `conformance_<selector>` and `conformance_blocking` or `conformance_informing`. The runner selects by them and never rewrites them. | FR-4, FR-7 |

FR-N refers to the Nth In Scope item of the [PRD](prd.md).

## UX Alignment

Not applicable. The suite adds no API resource, so there is no `osac-ux/libs/ui-components/src/api/v1/<resource>.ts` file to align with.

### Implementation Details/Notes/Constraints

#### Code location

The runner, the catalog, and the networking settings test live in the osac repository under `tests/conformance/`. The pytest plugin that exposes collection and per-test outcomes is `tests/conformance/pytest_plugin.py`. Unit tests are under `tests/unit/test_conformance_*.py`.

The OSAC QE team is proposed to own the runner. No domain declarations exist in this release; the only shipped test is the networking Netris settings check.

#### Suite image and release

- The image reference is `ghcr.io/osac-project/osac-conformance:<release>`, one image per OSAC release, tagged with the release.
- `tests/conformance/Containerfile` defines the image. It builds the package with setuptools on a UBI 9 Python 3.12 builder, installs it into a UBI 9 Python 3.12 minimal runtime, copies `kubectl` from a pinned `registry.k8s.io/kubectl` image, and runs as UID 1001.
- The release pipeline does not publish the image yet. Building and publishing it with the other release images is follow-up work.
- The suite reports its own image digest as `suiteImageDigest`. An explicit `OSAC_CONFORMANCE_SUITE_IMAGE_DIGEST` environment variable wins. Without it, the runner inspects its own container through a podman or Docker unix socket, using the libpod API first and the Docker-compatible API second. It tries `CONTAINER_HOST`, `DOCKER_HOST`, `$XDG_RUNTIME_DIR/podman/podman.sock`, `/run/podman/podman.sock`, and `/var/run/docker.sock`, in that order. If no registry digest is available, the runner falls back to the runtime image ID. If neither is available, the report records an empty string.

#### Running the suite

| Mount | In the container | Purpose |
|---|---|---|
| Configuration directory | `/config`, read-only | `conformance.yaml` and the files it names, including the target hub kubeconfig. Paths in `conformance.yaml` are container paths. |
| Results directory | `/results` | The plan, report, JUnit XML, timestamped log, evidence, and diagnostics. It must be empty or hold only a plan `list` wrote. |
| Runtime socket | optional | Used only to read the suite image digest. An explicit `OSAC_CONFORMANCE_SUITE_IMAGE_DIGEST` removes the need for it. |

The image runs as UID 1001, not root. With rootless podman, `--userns=keep-id:uid=1001,gid=1001` maps the invoking user to that UID so the runner can write `/results` and read `/config`. With rootful podman, drop the `--userns` flag and make the results directory writable by UID 1001, for example `chown -R 1001:0 results`. On a host with SELinux enforcing, append `:Z` to both mounts. `--security-opt label=disable` is not required.

The suite runs in this order:

1. Read and validate `/config/conformance.yaml`.
2. Load the catalog and expand the selected profiles into selectors.
3. Check that the results directory is empty or holds only `conformance-plan.yaml`.
4. Collect the pytest tests and their markers.
5. Compute or load the plan and validate it.
6. Run the plan in pytest with `-n 0`.
7. Derive the selected profiles' results and apply the three checks.
8. Write the report and JUnit XML, then collect diagnostics.

#### Configuration

`conformance.yaml` has these keys:

```yaml
osacRelease: "0.0.1"                 # the OSAC release under test
profiles: [netris]                   # generic always applies
target:
  namespace: osac                    # defaults to osac
  kubeconfig: /config/hub.kubeconfig
  apiURL: https://fulfillment-internal-api.example
  tokenFile: /config/admin-token
  caFile: /config/api-ca.pem
  aap:                               # optional
    url: https://aap.example
    tokenFile: /config/aap-token
timeouts: {}                         # optional duration strings
```

| Key | Meaning | Used by the core |
|---|---|---|
| `osacRelease` | The OSAC release under test. Also the configuration schema version. | Recorded in the report. |
| `profiles` | The profiles the run selects. The catalog expands each profile to its selectors; `generic` always applies. | Yes. |
| `target.namespace` | The namespace that holds the OSAC installation. Defaults to `osac`. | Diagnostics and the Netris check. |
| `target.kubeconfig` | The target installation's hub. | Diagnostics and the Netris check. |
| `target.apiURL` | The target installation's internal fulfillment API. | Parsed and redacted. The core does not call it. |
| `target.tokenFile` | An admin token for the fulfillment API. | Read into the redactor. The core does not call the API. |
| `target.caFile` | The CA that signed the API certificate. | Path validated. The core does not read or use it. |
| `target.aap` | Optional AAP controller URL and read-only token file. | Parsed and redacted. Not used. |
| `timeouts` | Optional duration overrides. | Parsed and validated. Not used. |

The loader requires `target.apiURL`, `target.tokenFile`, and `target.caFile` because they are part of the release schema. The core only validates and redacts them; they become active in follow-up stories. An operator running only the core must still provide them.

The core rejects:

- a missing or unreadable configuration file;
- an unknown top-level key, `target` key, or `target.aap` key;
- a missing required target key;
- a `profiles` value that is not a list of non-empty strings;
- a path containing `..`;
- a duplicate YAML mapping key;
- an `apiURL` or `target.aap.url` that is not an absolute URL with a host;
- a `timeouts` value that is not a flat mapping of strings to strings.

It also rejects an unknown profile, a results directory holding anything other than `conformance-plan.yaml`, an empty execution plan, a plan naming a test the image does not contain, and a plan naming a test that no selected profile's selector selects.

Configuration errors are printed to stderr, one line per check, with the run's redactor applied. The runner writes no report and exits 2. A missing configuration file is diagnosed before the results directory is created.

Unknown keys do not name a replacement. This release has one configuration schema; replacing a key is a deliberate release change.

#### Catalog and selection

The shipped catalog is:

```yaml
selectors:
  - id: generic
    type: marker
    markers: [conformance_generic]
  - id: vmaas
    type: marker
    markers: [conformance_vmaas]
  - id: bmaas
    type: marker
    markers: [conformance_bmaas]
  - id: caas
    type: marker
    markers: [conformance_caas]
  - id: netris
    type: marker
    markers: [conformance_netris]

profiles:
  - id: generic
    selectors: [generic]
  - id: vm
    selectors: [vmaas]
  - id: baremetal
    selectors: [bmaas]
  - id: cluster
    selectors: [caas]
  - id: netris
    selectors: [netris]
```

A selector has an `id`, a `type` of `marker`, and a non-empty list of pytest markers. A profile has an `id` and a list of selector IDs. The loader rejects duplicate IDs, an unsupported selector type, and a profile that references an unknown selector.

Selection rules:

- `generic` is always first in the selected profile list, even when the operator omits it.
- Selected profile IDs are deduplicated in the order given.
- The plan's selectors are the union of the selected profiles' selectors, deduplicated in profile order.
- Selectors do not imply one another.
- A test joins the plan when any selected selector's marker is in the test's marker set.
- A test can carry several selector markers and count toward several selected profiles.
- A test that no selected profile's selector selects is not in the plan and does not affect the verdict.
- `conformance_blocking` and `conformance_informing` classify a test. A test with neither marker is blocking.
- An informing test is reported in `tests[]` but never fails a check.

The catalog ships inside the image and is not operator-editable. Operators select profiles; they do not add selectors or profiles.

The `--catalog` and `--tree` command-line options exist for local development and tests. They are not part of the operator contract. A run that passes either option is a development run, and its report is not a conformance verdict. The report does not yet record these overrides.

#### Test collection and execution

The runner treats the test tree as a black box:

1. **Collection.** It runs `python -m pytest -n 0 --collect-only -q -p tests.conformance.pytest_plugin --rootdir <tree> <tree>`. The plugin writes a JSON manifest with each item's `nodeid`, `name`, and sorted marker names. The runner derives each test's ID from the canonical pytest node ID relative to the tree root, rejects duplicate IDs, and assigns the selected profiles whose selectors match.
2. **Execution.** It runs `python -m pytest -n 0 -p tests.conformance.pytest_plugin -q --tb=short --rootdir <tree> <node IDs>`. The plugin writes one JSONL record per setup, call, and teardown phase that fails or skips, plus the call record for passes. Each record holds `nodeid`, `name`, `when`, `outcome`, `duration`, `message`, `stdout`, `stderr`, and `caplog`.
3. **Mapping.** The runner combines a test's records. Any failure means `fail`; otherwise any skip means `skip`; otherwise `pass`. A test with no records is `skip` with the message `did not run`. Durations are summed.
4. **Evidence.** For a test with recorded output, the runner writes `tests/<16-hex>/test.log` with the combined `caplog`, `stdout`, and `stderr`, after redaction. The directory name is a truncated SHA-256 digest of the test ID, so a parameterized ID cannot escape the directory or exceed the filesystem name limit.

The pytest child receives `OSAC_CONFORMANCE_RESULTS` (the JSONL path), `OSAC_CONFORMANCE_RUN_ID`, `OSAC_CONFORMANCE_RESULTS_DIR`, `OSAC_CONFORMANCE_CONFIG`, and `OSAC_CONFORMANCE_TENANT` when a tenant is set. The core does not set a tenant. The plugin disables pytest's own `log_file` during a conformance run so captured output cannot bypass the runner's redaction boundary.

pytest exit codes 0 and 1 are test outcomes. Exit code 2 is a collection error and becomes a configuration error, unless the child was killed by the forwarded interrupt signal. Other return codes are configuration errors.

The core runs pytest with `-n 0`; it does not run tests in parallel.

#### Plan

`list` writes `/results/conformance-plan.yaml` and prints the same document. The document is:

```yaml
profiles: [generic, vm]
selectors:
  - {id: generic, type: marker, markers: [conformance_generic]}
  - {id: vmaas, type: marker, markers: [conformance_vmaas]}
tests:
  - id: generic/test_smoke.py::test_installation_smoke
    key: <sha256 of the test id>
    name: test_installation_smoke
    profiles: [generic, vm]
    markers: [conformance_generic, conformance_vmaas]
complete: true
```

The `id` and `name` fields are redacted. The opaque `key` lets a redacted `id` be replayed. `list` prints with a UTC timestamp but does not create `conformance.log`.

`run` computes the same plan in memory and executes it. It does not write the plan file. `run --plan <file>` reads a plan written by `list` and accepts each `tests[]` entry as a string test ID or a mapping with `key` or `id`. It validates that every named test exists in the image and that a selected profile's selector selects it. It computes `complete` by comparing the named tests with the full plan for the selected profiles.

A plan that holds no tests is a configuration error: `run` stops before executing anything and exits 2. A subset plan has `complete: false`, is reported `in progress`, and is not a conformance verdict. A focused run still exits 0 when every selected blocking test passed and there are no leftovers.

`--keep` is accepted for forward compatibility. The core creates no target resources, so it has nothing to keep and the flag has no effect.

#### Result rules and checks

A profile's result is computed only for the profiles in the plan's selected list:

- `required` is `true` when at least one planned test counts toward the profile.
- If no planned test counts toward the profile, it is `required: false` and `skip`.
- If the profile has planned tests but no blocking test, it is `required: true` and `skip`.
- If every blocking test that counts toward the profile passes, the profile passes.
- If any blocking test that counts toward the profile fails or skips, the profile fails.
- Informing tests never change a profile's result.

The runner defines exactly three checks:

| ID | Name | Rule | Remedy |
|---|---|---|---|
| `all-blocking-tests-pass` | every selected blocking test passed | every blocking test in the plan has result `pass` | see the failed tests and their evidence |
| `no-leftovers` | nothing was left behind | `leftovers[]` is empty | delete each leftover |
| `complete-plan` | the plan was complete | `complete` is `true` | run without `--plan`, or use the full plan that `osac-conformance list` prints |

Each check carries a short `message`:

- `all-blocking-tests-pass` reports the number of blocking tests that passed, or names the failed tests, or says that the plan has no blocking tests.
- `no-leftovers` reports `no leftovers` or names the leftovers.
- `complete-plan` reports that the plan held every selected test, or that it is a focused subset.

`all-blocking-tests-pass` fails when the plan has no blocking tests. A blocking test that reports `skip` is not a pass.

The overall `result` is `conformant` only when all three checks pass. It is `in progress` otherwise.

Exit codes:

- 0 when the overall result is `conformant`;
- 0 for a focused run when at least one selected blocking test ran, every selected blocking test passed, and `leftovers[]` is empty, even though `complete-plan` fails and the report says `in progress`;
- 1 otherwise;
- 2 on a configuration or command-line error, with no report;
- 130 after an interrupt.

#### Report

`/results/conformance-report.yaml` has exactly these keys:

| Key | Value |
|---|---|
| `osacRelease` | The configured OSAC release. |
| `suiteImageDigest` | The suite image digest, the runtime image ID when no digest is available, or an empty string when neither is available. The field name is historical; consumers must not assume a `sha256:` registry digest. |
| `selectors` | The expanded selectors, in order, starting with `generic`: an object with `id`, `type`, and `markers`. |
| `profiles` | The selected profiles only: `id`, `selectors`, `required`, and `result` (`pass`, `fail`, or `skip`). |
| `tests` | One entry per planned test: `id`, `name`, `profiles`, `classification`, `result` (`pass`, `fail`, or `skip`), `durationSeconds`, and `message`. |
| `checks` | The three checks in table order: `id`, `name`, `rule`, `remedy`, `result` (`pass` or `fail`), and `message`. |
| `leftovers` | Empty in the core. Reserved for follow-up stories that create resources. |
| `complete` | `true` when the plan held every test the selected selectors select; `false` for a focused plan. |
| `result` | `conformant` or `in progress`. |

Example:

```yaml
osacRelease: "0.0.1"
suiteImageDigest: sha256:<digest>
selectors:
  - {id: generic, type: marker, markers: [conformance_generic]}
  - {id: netris, type: marker, markers: [conformance_netris]}
profiles:
  - {id: generic, selectors: [generic], required: true, result: pass}
  - {id: netris, selectors: [netris], required: true, result: skip}
tests:
  - id: generic/test_smoke.py::test_installation_smoke
    name: test_installation_smoke
    profiles: [generic]
    classification: blocking
    result: pass
    durationSeconds: 4.1
    message: ""
  - id: networking/test_netris_settings.py::test_netris_settings_are_present
    name: test_netris_settings_are_present
    profiles: [netris]
    classification: informing
    result: pass
    durationSeconds: 1.2
    message: ""
checks:
  - {id: all-blocking-tests-pass, name: "every selected blocking test passed", rule: "every blocking test in the plan has result pass", remedy: "see the failed tests and their evidence", result: pass, message: "1 blocking test passed"}
  - {id: no-leftovers, name: "nothing was left behind", rule: "leftovers is empty", remedy: "delete each leftover", result: pass, message: "no leftovers"}
  - {id: complete-plan, name: "the plan was complete", rule: "complete is true", remedy: "run without --plan, or use the full plan that osac-conformance list prints", result: pass, message: "plan contained all 2 selected tests"}
leftovers: []
complete: true
result: conformant
```

The generic blocking test is illustrative. The shipped tree currently contains only the networking Netris settings check, which is informing.

`/results/junit.xml` has one `testcase` per `tests[]` entry:

- `name` is the redacted test name;
- `classname` is `conformance`;
- `time` is `durationSeconds`;
- a failure has a `failure` element whose `message` is the test's message and whose body is the test's `test.log`, or its message when no log exists;
- a skip has a `skipped` element whose `message` is the test's message.

XML 1.0 illegal characters are stripped before redaction, so a control character cannot split a secret past the redactor.

#### Output, evidence, and diagnostics

**Output.** The runner writes its own lines to stdout and appends them to `/results/conformance.log` with a UTC ISO timestamp. The pytest child's stdout and stderr are captured and replayed through the redactor after the child exits; they are not streamed while a test is running. The `run` output is:

- `run <run ID>: <N> tests`;
- each line the pytest child wrote, redacted and timestamped;
- `result: <result>, exit <code>`.

`list` prints the plan with the same timestamp and redaction, but uses a path that does not create `conformance.log`.

The run ID is the first line of `conformance.log` for a `run`.

**Evidence.** The core writes one file per test with captured output: `tests/<16-hex>/test.log`, containing the test's captured logging, stdout, and stderr after redaction. No job directories, API logs, resource snapshots, AAP job logs, or domain evidence directories exist in the core.

**Diagnostics.** Every `run` that reaches test execution writes `/results/diagnostics/` through `kubectl` and the configured kubeconfig:

| File | Content |
|---|---|
| `osac-state.yaml` | `kubectl get pods,deployments,events -n <namespace> -o yaml` |
| `pod-logs.txt` | `kubectl logs -n <namespace> -l app.kubernetes.io/part-of=osac --tail=2000` |
| `tenant-resources.yaml` | Written only when a tenant is set. The core does not set one. |

Each command has a 300 second timeout. The 300-second diagnostics timeout is a fixed internal bound. The `timeouts` mapping is reserved for domain wait keys and does not configure diagnostics. A failed command is recorded as `diagnostics command failed: <error>` and redacted. The diagnostics bundle is not tenant-scoped; it holds the configured OSAC namespace's control-plane state and logs. It is operator data and is not automatically shareable.

**Redaction.** `tests/conformance/redact.py` is the one boundary. It composes the existing `tests/e2e/core/sanitize.py` rules with:

- the values of `target.tokenFile` and `target.aap.tokenFile`;
- kubeconfig `token`, `password`, and `client-key-data` values;
- the target API host, the AAP host, and each kubeconfig server host.

It redacts text and structured objects, including credential-named keys, container environment name/value pairs, registry auth config entries, and JSON embedded in Kubernetes annotations. Every writer uses it: stdout, `conformance.log`, evidence, test messages, JUnit, the report, diagnostics, and configuration errors.

The core makes no API calls, so there is no `api.log` and no API-client allowlist. The redaction claim is limited to the secret values the suite reads; it does not detect secrets it never reads in arbitrary control-plane logs.

#### Interrupt handling

`InterruptGate` installs handlers for SIGINT and SIGTERM:

- The first signal forwards SIGINT to the pytest child. pytest stops gracefully and writes the outcomes of completed tests. The runner reads those outcomes, raises `Interrupted` with them, writes the report, JUnit, and diagnostics, and returns 130.
- A second signal kills the child and raises `KeyboardInterrupt`. The runner returns 130 with no report.
- A signal that arrives between `Popen` returning and the child handle being attached is deferred and replayed after attachment, so a live child is never abandoned.
- Tests that did not run are reported `skip` with `did not run`. Tests that completed keep their recorded outcomes.
- On an interrupted run the process returns 130. The `result:` line is printed before the interrupt override and currently shows the verdict-derived exit code (0 or 1), not 130. This is a display mismatch; the process exit code is authoritative.
- The signal gate covers the pytest child execution only. Collection, report writing, and diagnostics collection are not signal-protected.

The suite is not resumable. A new run starts from the beginning.

### Security Considerations

- **Credentials.** The configuration directory holds the admin token, the API CA, and the kubeconfig. It is mounted read-only. The runner never copies a file from `/config` into the results directory. The admin token and AAP token are read only to seed the redactor. The core does not send them to any service.
- **One redaction boundary.** Every byte the runner prints or writes passes through `Redactor.text` or `Redactor.obj`. This covers stdout, the timestamped log, evidence, test messages, JUnit, the report, diagnostics, and configuration errors. The claim is limited to the values the suite reads.
- **Unprivileged container.** The image runs as UID 1001. `--userns=keep-id:uid=1001,gid=1001` maps the invoking user to that UID under rootless podman. The runtime socket is optional and is used only to inspect the suite's own container for its image digest. The core starts no other container.
- **Report.** The report is self-reported and can be edited. `suiteImageDigest` lets a reader verify which image ran when it is a registry digest; it can also hold a runtime image ID or be empty when no digest is available. The report may be shared.
- **Diagnostics.** The diagnostics bundle is operator data and is not automatically shareable. It is not tenant-scoped; it holds the configured OSAC namespace's control-plane state and logs. The secret values the suite reads are redacted from it, and Helm values are never collected.
- **No tenant writes.** The core creates no Tenant and no OSAC resource. It uses the kubeconfig for read-only diagnostics and the Netris ConfigMap read.

### Failure Handling and Recovery

| Failure | What happens | What the user sees |
|---|---|---|
| The configuration is missing or invalid | The runner writes no report and exits 2. | One line per failing check on stderr, redacted. |
| The results directory holds anything other than a plan | The runner stops before running a test and exits 2. | The unexpected entry names. |
| pytest cannot collect the tree | The runner stops and exits 2. | `pytest collection failed: <detail>`. |
| A blocking test fails | The test is `fail`; `all-blocking-tests-pass` fails. | `fail` with the test message; the report says `in progress`; exit 1 for a complete run. |
| A blocking test skips | The test is `skip`; `all-blocking-tests-pass` fails. | `skip` with the reason; `in progress`. |
| An informing test fails | The test is `fail`; no check fails. | `fail` with the test message; the overall result is unaffected. |
| The plan has no blocking tests | `all-blocking-tests-pass` fails. | `no blocking tests in the plan`. |
| The plan is a focused subset | `complete-plan` fails. | `in progress`; a focused run can still exit 0 when its blocking tests passed and there are no leftovers. |
| The run is interrupted | The first signal stops pytest gracefully, keeps completed outcomes, writes a report, and exits 130. | The interrupted test's result; tests that did not run are `skip`. |
| The suite is killed or receives a second interrupt | No further cleanup and no report. | The run ID is in the first line of `conformance.log`; rerun the same plan. |
| A diagnostics command fails | The failure is recorded in the diagnostics file and redacted. | `diagnostics command failed: <error>`. |

The core creates no target resources, so it has nothing to clean up and `leftovers[]` is empty. Follow-up stories that create resources must add their own cleanup and journal rules.

### RBAC / Tenancy

No RBAC or tenancy changes. The core reads the target installation's hub kubeconfig to collect the diagnostics bundle and to read the `network-fulfillment-ig` ConfigMap for the Netris settings check. It does not use an admin token, does not call the fulfillment API, and does not create a Tenant or any OSAC resource. It needs read access to the configured namespace's pods, deployments, events, pod logs, and the `network-fulfillment-ig` ConfigMap.

### Observability and Monitoring

No monitoring changes for the target installation. The suite's output is its observability: the timestamped timestamped log, per-test evidence, the report and JUnit XML, and the diagnostics bundle.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| The core does not verify the target release, enabled services, or domain results. | The design states this limitation. Follow-up stories add target reads and domain results. The report records `osacRelease` and the operator runs the image whose tag matches the release. |
| The image is not published by the release pipeline yet. | The design records publication as follow-up work. Operators can build the image locally for development. |
| A marker is not registered in `pyproject.toml`. | pytest emits `PytestUnknownMarkWarning`. The shipped catalog and markers are registered in `pyproject.toml`. |
| A test ID contains environment data and leaks through a path. | Evidence directories use a truncated SHA-256 digest, not the test ID. Plan and report IDs pass through the redactor. |
| A control character splits a secret in JUnit XML. | XML-illegal characters are stripped before redaction. |
| `--keep` is accepted but has no effect. | The core creates no resources to keep. The design states the flag is forward compatibility only. |
| A focused plan is mistaken for a conformance verdict. | `complete-plan` fails and the report says `in progress`. |
| The pytest child output is buffered until the child exits. | The design states the limitation. Streaming through the redactor is follow-up work. |
| `--catalog` or `--tree` can produce a report that does not use the shipped inputs. | The design marks both as development-only. The report does not yet record the override; follow-up should mark or remove them in release images. |
| An interrupted run logs the verdict-derived exit code before returning 130. | The design states the mismatch. Follow-up should compute the final exit code once. |
| The signal gate covers only the pytest child. | The design states the phase boundary. Collection and report writing are not signal-protected. |
| `suiteImageDigest` can be a runtime image ID. | The design documents the fallback. Consumers must not assume a registry digest. |

### Drawbacks

- The core reports test and profile results only. It does not report a target release check, enabled services, or domain results.
- The runner is Python and pytest-specific. Another test framework needs a new adapter.
- The runner does not execute tests in parallel.
- The catalog is shipped with the image, so adding a selector or profile requires a new image.

The cost is accepted because the core is small, testable, and gives the follow-up stories a stable plan, report, and redaction contract.

## Alternatives (Not Implemented)

- **Keep the domain, Tenant, and target-read abstractions in the core.** Rejected: they had no implementation in this release and made the configuration, report, and checks describe behavior the image did not have.
- **Read the target installation from the core.** Rejected for this release: it needs API and hub credentials, a release check, and domain identity. Follow-up work adds it.
- **Run provider-side tests from the core.** Rejected for this release: it needs the podman socket, EE images, a scratch cluster, and backend cleanup.
- **Create a test Tenant and run profiles in it.** Rejected for this release: the shipped tests do not create OSAC resources yet.
- **Read JUnit XML from pytest instead of JSONL.** Rejected: the plugin's JSONL records captured output and per-phase outcomes without losing failures that JUnit flattens.
- **Make `run` the default command.** Rejected: an explicit `list` or `run` is clearer, and the image entry point is used in scripts.
- **Derive the plan from enabled services or registrations.** Rejected for this release: every shipped selector is a marker selector.

## Test Plan

The requirement-anchored [testplan](testplan.md) lists every case. It preserves the PRD FR-1 through FR-12 numbering and records each requirement as implemented, partial, or deferred; it does not redefine an FR to mean a different section of the core. Summary:

### Unit Tests

- Configuration: common keys, defaults, deduplicated profiles, optional AAP, unknown keys, rejected domain sections, missing target keys, profiles type, missing file, path canonicalization, parent traversal, duplicate keys, URL parsing, redactor inputs.
- Catalog and selection: generic first, selector union, deduplication, no implied selectors, unknown profile, subset completeness, replay by key, unknown and unselected test rejection, multi-profile tests, duplicate catalog keys.
- Plan and output: plan shape, redaction, run ID, evidence confinement and bounded names, `echo` does not create the log.
- Execution: marker collection, pass/fail/skip mapping, teardown failure and skip, duplicate function names, collection failure, pytest process errors, captured output and logging, interrupt paths.
- Verdict: conformant, blocking failure and skip, no blocking tests, informing-only plan, leftovers, incomplete plan, focused exit codes, selected profile with no blocking test.
- Report: exact keys, redaction, JUnit mapping, failure body, XML illegal characters.
- Redaction: known secrets and hosts, existing sanitizer rules, unknown assignments, objects, quoted values, YAML decoding, container environment pairs, registry auth, serialized annotations.
- Image digest: environment override, podman and Docker APIs, repo digest, image ID fallback, socket discovery, runtime command selection.
- Interrupt: first signal, second signal, forwarding, child kill, registration deferral.
- Diagnostics: redacted control-plane state, failed command, configured namespace.
- Netris check: setting present, missing, unreadable ConfigMap, null namespace, kubectl timeout.
- Core integration: synthetic tree `list` and `run`, empty plan, unknown profile, list artifact, interrupt with completed outcomes.
- Image smoke: build and start the Containerfile when `OSAC_CONFORMANCE_IMAGE_TEST=1`.

### Integration Tests

- The core integration suite runs `list` and `run` against a synthetic pytest tree and fake tree adapter, with no target installation.
- The image smoke builds the Containerfile and runs `--help` when podman and network access are available. A packaged `list` to `run --plan` smoke that checks the shipped tree, mounted config/results, and generated artifacts is a known gap.

### E2E Tests

- The core has no E2E lab run. A real target installation, provider-side tests, and a test Tenant belong to follow-up stories.

## Graduation Criteria

- **Dev Preview:** the core source, catalog, pytest plugin, report, and unit tests exist; the image builds locally; `list` and `run` work against the shipped test tree.
- **Tech Preview:** the image is published with each release; target reads, domain tests, and a test Tenant are added; the E2E lab runs the full suite with a real provider-side test set.
- **GA:** the suite gates every release in CI and the E2E lab, and supported domain reports are `conformant`.

## Upgrade / Downgrade Strategy

The suite is not installed in OSAC and has no upgrade impact on a target installation. Each release has its own image, and a report covers one `osacRelease`. Running a release's suite after that release is installed is ordinary operation and needs no upgrade mode.

## Version Skew Strategy

The configuration schema is versioned by `osacRelease`; one release defines one schema and unknown keys are errors. The core does not check the target installation's release. The operator must run the image whose tag matches the target release. Follow-up work adds the target release check.

## Support Procedures

- **Detect:** read the report's `result`, each failed `checks[]` message, the failed `tests[]` messages, the JUnit XML, the timestamped log, and the failed tests' evidence directories.
- **Rerun:** run `osac-conformance list` to write a plan, then `osac-conformance run --plan <file>` to rerun it. A narrower plan is a focused run and is reported `in progress`.
- **Interrupt or kill:** the run ID is in the first line of `conformance.log`. The core creates no target resources, so no cleanup is needed. Rerun the same plan.
- **Clean up:** `leftovers[]` is empty in the core. Follow-up stories that create resources must document their own cleanup.
- **Disable:** stop the container. No target state is changed.

## Infrastructure Needed

- An image repository, `ghcr.io/osac-project/osac-conformance`, published with each release. Publication is follow-up work.
- A CI job that builds the image and runs the unit and core integration tests.
- The conformance markers registered in `pyproject.toml`.
- Documentation: the installation guide ends with running the suite; the Fabric Manager guide points to it.
- Follow-up work for target reads, provider-side tests, a test Tenant, resource cleanup, and release publication.

---

## Provenance

Authored: draft @ design 0.11.5 - e2b0d87, workspace provider-networking-docs @ d3d48c727
Final: revise [manual] @ design 0.11.5 - e2b0d87, workspace provider-networking-docs @ 28ffb6868

Revised 2026-11-22 to describe the core runner shipped by OSAC-7454 and remove the domain, layer, Tenant, target-read, cleanup, and journal scope that the core does not implement.

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"28ffb6868","source_repo_branch":"provider-networking-docs","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
