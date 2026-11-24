# Test Plan — OSAC-46 VM instance types

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 13

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-VIT-01: A tenant VM request expands an active type into the hub CR

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 640-646](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L640-L646)
- **Dependencies:** Real deployed fulfillment, tenant CLI and hub API; test type and template; guest runtime is outside this assertion.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_happy_path` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L334)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_happy_path` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the active suite type with 2 vCPUs and 4 GiB memory.

1. Create a VM using the type and confirm its ID is listed.
2. Read CPU, memory and type label on the hub CR.

**Expected results.** The CR has 2 vCPUs, 4 GiB and labels the selected type.

#### TC-VIT-02: A deployed request for an unknown InstanceType is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 614-618](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L614-L618)
- **Dependencies:** Real deployed fulfillment, CLI, PostgreSQL and hub API; no provider is needed for rejection.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_nonexistent_instance_type` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L461)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_nonexistent_instance_type` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use a valid fixture template, image and network with a synthetic type name absent from the fixture.

1. Request the VM through the CLI.
2. Inspect exit status and diagnostic.

**Expected results.** The request fails with a not-found diagnostic.

#### TC-VIT-03: A tenant can view shared types and their labels in the UI

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 640-647](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L640-L647)
- **Dependencies:** Real UI, authentication and fulfillment in an isolated deployment; fixture InstanceTypes; no guest runtime.
- **Gap:** Canonical API List and tenant VM tests do not assert this UI journey. No matching UI E2E test identified.

**Preconditions.** Create a shared active fixture type standard-2-4.

1. Open the instance type selector as a tenant user.
2. Check the available type and displayed compute values.

**Expected results.** The user can select standard-2-4 and sees 2 vCPUs and 4 GiB.

#### TC-VIT-04: Supported InstanceType resize updates the selected type

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [enhancements/OSAC-4277-vm-resize-instancetype/design.md, lines 188-206](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-4277-vm-resize-instancetype/design.md#L188-L206)
- **Dependencies:** Real deployed fulfillment, hub and running VM fixture with eligible source and target types; tenant CLI and fixture editor.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_resize_via_cli` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L531)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_resize_via_cli` from OSAC root. Source reviewed, test not run.

**Preconditions.** Start the suite's running VM with the active or medium fixture type and its supported resize target.

1. Edit the VM through the tenant CLI to choose the target type.
2. Read the API type, resulting hub configuration and RestartRequired status.

**Expected results.** The API returns the target type, the hub resolves its CPU and memory, and RestartRequired becomes true. OSAC-4277 supersedes the legacy Phase 1 unconditional rejection.

#### TC-VIT-05: An ACTIVE InstanceType can become DEPRECATED with a timestamp

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 620-621](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L620-L621)
- **Dependencies:** In-process private server and real PostgreSQL testcontainer; synthetic attribution and tenancy; no VM provider.
- **Execution:** `fulfillment-service/internal/servers/private_instance_types_server_test.go`
- **Evidence:** `Transitions ACTIVE to DEPRECATED` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_instance_types_server_test.go#L547)).
- **Selector:** `ginkgo run --timeout 10m --focus='Transitions ACTIVE to DEPRECATED' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create the ACTIVE type fixture.

1. Update spec.state to DEPRECATED.
2. Inspect the returned state and deprecation metadata.

**Expected results.** The state is DEPRECATED, the deprecation timestamp is within one second of the transition and the obsolescence timestamp is absent.

#### TC-VIT-06: Lifecycle transitions and dates follow the deprecation rules

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 620-625](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L620-L625)
- **Dependencies:** Real in-process server and PostgreSQL; isolated type rows; provider omitted.
- **Gap:** The private suite names state-transition tests. Full reverse transition, timestamp mutability and rejection of a past explicit date are tracked here as a separate matrix pending exact per-scenario mapping.

**Preconditions.** Prepare fixture types in ACTIVE, DEPRECATED and OBSOLETE states and past/future timestamps.

1. Exercise documented forward and reverse transitions and update the replacement and dates.
2. Repeat the DEPRECATED transition with a past obsolescence date.

**Expected results.** Supported transitions reach their target states and update expected timestamps, allowed fields persist, and the past date is rejected.

#### TC-VIT-07: A deprecated type still permits Create with a warning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 619-619](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L619-L619)
- **Dependencies:** Real deployed fulfillment, tenant CLI and hub API; fixture type and image; guest runtime omitted.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_deprecated_warning` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L417)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_deprecated_warning` from OSAC root. Source reviewed, test not run.

**Preconditions.** Set the suite's type to DEPRECATED.

1. Create a VM with the tenant CLI.
2. Read warning output, the returned VM ID and hub object.

**Expected results.** Create succeeds and output signals deprecation or a warning. The supplied ID resolves to a hub CR.

#### TC-VIT-08: The warning includes the configured obsolescence date

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 619-635](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L619-L635)
- **Dependencies:** Real fulfillment and PostgreSQL, fixture type with future timestamp, no guest provider.
- **Gap:** The deployed warning assertion does not set or compare an obsolescence date. No exact fulfillment selector verified for that requirement.

**Preconditions.** Set a type to DEPRECATED with a future fixture obsolescence timestamp.

1. Create a VM using the type.
2. Inspect warning metadata and the successful response.

**Expected results.** Create succeeds and the warning contains the configured date.

#### TC-VIT-09: An in-use type cannot be deleted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 623-638](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L623-L638)
- **Dependencies:** Real deployed fulfillment, CLI, PostgreSQL and hub API; fixtures only.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_deletion_protection` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L379)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_deletion_protection` from OSAC root. Source reviewed, test not run.

**Preconditions.** Create a fixture VM referencing an active synthetic type.

1. Wait for the VM to appear in the list and hub.
2. Attempt deletion of the type through the private CLI.

**Expected results.** Deletion fails with a conflict or reference-in-use diagnostic.

#### TC-VIT-10: Default public InstanceType List excludes the obsolete fixture

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 626-637](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L626-L637)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind; fixture types only; no provider.
- **Execution:** `fulfillment-service/it/it_public_instance_types_test.go`
- **Evidence:** `Default list excludes OBSOLETE` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_public_instance_types_test.go#L134)).
- **Selector:** Ginkgo focus `Default list excludes OBSOLETE` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Create three fixture types, then transition the third through DEPRECATED to OBSOLETE.

1. List by the names of the three fixture records with no explicit state filter.
2. Count the returned items.

**Expected results.** The name-scoped list returns two items.

#### TC-VIT-12: An explicit state filter returns the obsolete fixture

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 626-637](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L626-L637)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind; fixture types only; no provider.
- **Execution:** `fulfillment-service/it/it_public_instance_types_test.go`
- **Evidence:** `List with explicit state filter includes OBSOLETE` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/it/it_public_instance_types_test.go#L182)).
- **Selector:** Ginkgo focus `List with explicit state filter includes OBSOLETE` in the deployed fulfillment suite from OSAC root. Source reviewed, test not run.

**Preconditions.** Create the fixture type and transition it through DEPRECATED to OBSOLETE.

1. List with the fixture name and explicit obsolete state filter.
2. Read the returned ID.

**Expected results.** The filtered result has one item with the expected fixture ID.

#### TC-VIT-13: Public reads show the deprecated and obsolete types’ configured timeline

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 626-637](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L626-L637)
- **Dependencies:** Real deployed fulfillment and PostgreSQL in Kind; fixture types only; no provider.
- **Gap:** The private transition specs check timestamp transitions, and the public Get spec checks obsolete state. No exact deployed Get assertion was found for both types’ timestamp and replacement fields.

**Preconditions.** Configure two fixture types with distinct deprecation dates and a replacement. Transition one to OBSOLETE.

1. Get the deprecated and obsolete types through the public API.
2. Compare their returned timeline and replacement metadata with the stored fixtures.

**Expected results.** The results expose each type’s applicable deprecation and obsolescence dates and its configured replacement.

#### TC-VIT-11: A deployed request for an obsolete type is rejected

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 617-632](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-46-vm-instance-types/README.md#L617-L632)
- **Dependencies:** Real deployed fulfillment, CLI, PostgreSQL and hub API; fixture type transitioned through DEPRECATED; provider omitted on rejection.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py`
- **Evidence:** `test_compute_instance_obsolete_instance_type` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py#L491)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_instance_type.py::test_compute_instance_obsolete_instance_type` from OSAC root. Source reviewed, test not run.

**Preconditions.** Transition the suite type from DEPRECATED to OBSOLETE.

1. Request a VM with that type, then inspect the CLI failure.
2. Check that the diagnostic identifies the obsolete type state.

**Expected results.** Current CLI returns FailedPrecondition and identifies the type as obsolete.
