# Test Plan — OSAC-1339 BCM backend

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 20

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The checked-in BCM suite separates a caller-owned credentials Secret from per-BMI generated runtime resources. The Envtest cleanup assertion below covers the generated resources only.

## Test Cases

#### TC-BCM-01: Minimum supported BCM version passes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should succeed with the exact minimum version` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L112)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='checkVersion.*should\ succeed\ with\ the\ exact\ minimum\ version'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** The local endpoint serves cm_version 10.25.03.

1. Call checkVersion.
2. Read the client error.

**Expected results.** The version check succeeds.

#### TC-BCM-02: Unsupported BCM version is classified as too old

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return ErrVersionTooOld for an old version` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L102)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='checkVersion.*should\ return\ ErrVersionTooOld\ for\ an\ old\ version'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return cm_version 9.2 from the local fixture.

1. Call checkVersion.
2. Inspect the returned diagnostic.

**Expected results.** The error contains ErrVersionTooOld’s message.

#### TC-BCM-03: An unreachable version endpoint returns a transport failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Gap:** The general JSON connection-failure test does not call checkVersion; version-specific transport failure is unverified.

**Preconditions.** Use a synthetic local client transport that cannot connect to the fixture version endpoint.

1. Call checkVersion.
2. Compare its error with the HTTP error classification.

**Expected results.** The failure is classified as connection failure for the version operation.

#### TC-BCM-04: HTTP GetDevices decodes the device collection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return a list of devices` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L163)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='GetDevices.*should\ return\ a\ list\ of\ devices'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return one LiteNode node001 and one PhysicalNode head01 from the local fixture.

1. Call GetDevices.
2. Read decoded list and raw object.

**Expected results.** Two devices decode; the first has hostname node001, LiteNode and a raw payload.

#### TC-BCM-05: GetDevice returns nil on a missing hostname

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return nil when device is not found` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L214)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='GetDevice.*should\ return\ nil\ when\ device\ is\ not\ found'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return JSON null when the fixture receives the missing-host lookup.

1. Call GetDevice for nonexistent.
2. Inspect device and error.

**Expected results.** Device and error are nil.

#### TC-BCM-06: HTTP GetDevice parses the chosen device

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return a device when found` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L196)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='GetDevice.*should\ return\ a\ device\ when\ found'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return node001 with resource_class=h100.

1. Request node001.
2. Inspect decoded fields and captured request argument.

**Expected results.** The request names node001 and the device has hostname node001 and class h100.

#### TC-BCM-07: HTTP failure produces a server error for the version check

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return ErrServerError on HTTP 500` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L152)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='checkVersion.*should\ return\ ErrServerError\ on\ HTTP\ 500'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return status 500 from the version fixture.

1. Call checkVersion.
2. Inspect the error classification.

**Expected results.** Error contains ErrServerError.

#### TC-BCM-08: UpdateDevice accepts the fixture update

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should succeed on a successful update` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L228)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='UpdateDevice.*should\ succeed\ on\ a\ successful\ update'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return a successful update from local HTTP for the synthetic device node001.

1. Send the device update.
2. Read parsed response.

**Expected results.** The call succeeds and Success is true.

#### TC-BCM-09: UpdateDevice preserves structured validation failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return ValidationError on validation failure` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L241)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='UpdateDevice.*should\ return\ ValidationError\ on\ validation\ failure'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return BCM validation for a missing partition on the fixture object.

1. Submit the partial synthetic device.
2. Inspect the error and response.

**Expected results.** A ValidationError carries one NOT_NULL entry and the response is available.

#### TC-BCM-10: mTLS fixture rotation uses the replacement client certificate

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Local TLS endpoint, synthetic certificate pairs and Secret reader double; no actual credentials.
- **Gap:** BCM client tests checked cover configuration and HTTP errors. The Secret read, TLS retry and rotation sequence is unverified.

**Preconditions.** Generate two disposable fixture certificate pairs and use a local TLS endpoint and Secret reader double.

1. Start with a valid pair, then install the replacement pair and let the endpoint signal a TLS failure for the old pair.
2. Observe the retry result and classifications for invalid fixture credentials.

**Expected results.** The valid client initializes; the retry uses the replacement pair and succeeds. Unrecoverable TLS errors keep their classification.

#### TC-BCM-11: Authentication failure has its own classification

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return ErrAuthFailed on HTTP 401` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L308)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='should\ return\ ErrAuthFailed\ on\ HTTP\ 401'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return HTTP 401 from the local JSON endpoint.

1. Invoke a device service call.
2. Read the error.

**Expected results.** The response is classified ErrAuthFailed.

#### TC-BCM-12: JSON request connection failure is classified separately

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real HTTP client and synthetic local httptest endpoint, no BCM device or deployment.
- **Execution:** `bare-metal-fulfillment-operator/internal/bcmclient/client_test.go`
- **Evidence:** `TestBCMClient / should return ErrConnectionFailed on connection error` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/bcmclient/client_test.go#L331)).
- **Selector:** `go test ./internal/bcmclient -run '^TestBCMClient$' -ginkgo.focus='should\ return\ ErrConnectionFailed\ on\ connection\ error'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Use the client fixture whose local endpoint is closed.

1. Invoke the generic JSON request.
2. Inspect the error.

**Expected results.** The error is ErrConnectionFailed.

#### TC-BCM-13: Malformed device JSON yields a parse error

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Gap:** BCM HTTP and inventory test suites on OSAC main were checked. The full assertion is unverified.

**Preconditions.** Return a non-JSON fixture response with HTTP success.

1. Call GetDevices.
2. Inspect decoded result and error.

**Expected results.** The client returns a decode error without a fabricated device list.

#### TC-BCM-14: Inventory chooses the matching free LiteNode

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`
- **Evidence:** `TestBCMInventoryAdapter / should return a matching free LiteNode` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/bcm_test.go#L905)).
- **Selector:** `go test ./internal/inventory -run '^TestBCMInventoryAdapter$' -ginkgo.focus='should\ return\ a\ matching\ free\ LiteNode'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Return one unassigned matching LiteNode from the HTTP fixture.

1. Call FindFreeHost with resource_class=h100.
2. Observe the selected host.

**Expected results.** The selected host is node001 with inventory ID osac-baremetal/node001, HostType=h100 and HostClass=bcm.

#### TC-BCM-15: A lost verify-after-write claim does not create a host

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — BCM client and inventory](design.md#unit-tests)
- **Dependencies:** Real inventory adapter with mocked BCM API, lifecycle and credential writer. No provider.
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`
- **Evidence:** `TestBCMInventoryAdapter / should return nil when verify-after-write detects concurrent writer` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/bcm_test.go#L436)).
- **Selector:** `go test ./internal/inventory -run '^TestBCMInventoryAdapter$' -ginkgo.focus='should return nil when verify-after-write detects concurrent writer'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Supply an unclaimed synthetic BCM device and a fixture reload that reports a different owner after the update.

1. Call AssignHost and observe the reload outcome.
2. Inspect the resulting host and mocked BMH side effects.

**Expected results.** The losing request returns nil host without creating a BMH.

#### TC-BCM-16: Cleanup preserves caller-owned credential references

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — BCM client and inventory](design.md#unit-tests)
- **Gap:** The cleanup envtest asserts removal of generated resources. The scoped inventory and BMH suites do not establish reference preservation for a caller-owned Secret in the same sequence.

**Preconditions.** Model a fixture allocation that references a caller-owned Secret and has a distinct generated per-BMI runtime resource.

1. Unassign the owning fixture and inspect captured deletes.
2. Repeat after the owned runtime objects are absent.

**Expected results.** The original Secret remains, and repeating cleanup does not remove unrelated resources.

#### TC-BCM-17: BMH identity and readiness follow the lifecycle contract

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — unit tests](design.md#unit-tests)
- **Dependencies:** Real Kubernetes API/etcd and BMF lifecycle code. Fake BCM and management clients; no physical host.
- **Gap:** BCM HTTP and inventory test suites on OSAC main were checked. The full assertion is unverified.

**Preconditions.** Use a scripted BCM fixture and real envtest API with synthetic BMH names, statuses and consumer IDs.

1. Create a BMH for an allocated host and retry with the same and different consumers.
2. Observe readiness in registering and available states and delete twice.

**Expected results.** The BMH records expected identity/MAC and consumer state. Same-ID retry is idempotent, another consumer is not replaced, and readiness changes only at the documented available boundary.

#### TC-BCM-18: BCM inventory allocation creates a fixture BMH and resumes when ready

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — BCM adapter and Metal3 lifecycle](design.md#integration-tests)
- **Dependencies:** Real Kubernetes API and etcd through envtest, a local HTTP BCM double and fixture host status. No actual BCM or bare-metal host.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_envtest_test.go`
- **Evidence:** `TestControllers / assigns a free BCM host, creates the BMH, and reaches Progressing once ready` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_envtest_test.go#L271)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='assigns a free BCM host, creates the BMH, and reaches Progressing once ready'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Seed one free BCM LiteNode in the HTTP fixture.

1. Reconcile until the assignment and BMH exist, then advance the BMH’s readiness state.
2. Observe the BMI phase.

**Expected results.** The fixture device is claimed, its BMH exists and the BMI reaches Progressing after BMH readiness.

#### TC-BCM-19: BCM teardown removes only the fixture allocation and generated runtime objects

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Design — BCM adapter and Metal3 lifecycle](design.md#integration-tests)
- **Dependencies:** Real Kubernetes API and etcd through envtest, a local HTTP BCM double and fixture host status. No actual BCM or bare-metal host.
- **Execution:** `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_envtest_test.go`
- **Evidence:** `TestControllers / clears BCM assignment, deletes the BMH and secret, and frees the host` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_envtest_test.go#L356)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='clears BCM assignment, deletes the BMH and secret, and frees the host'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Provision one BMI in the BCM envtest fixture and record its generated BMH and per-BMI credential resource.

1. Request BMI deletion and let reconciliation complete.
2. Inspect BCM assignment, BMH and generated resource state.

**Expected results.** The fixture device remains inventoried with no instance claim, and the owned BMH and generated per-BMI resource are absent.

#### TC-BCM-20: Cleanup avoids resources of a different fixture owner

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — BCM client and inventory](design.md#unit-tests)
- **Dependencies:** Real inventory adapter and controlled BCM API, lifecycle and credential writer; no provider.
- **Execution:** `bare-metal-fulfillment-operator/internal/inventory/bcm_test.go`
- **Evidence:** `TestBCMInventoryAdapter / should not delete runtime resources owned by another instance` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/bare-metal-fulfillment-operator/internal/inventory/bcm_test.go#L262)).
- **Selector:** `go test ./internal/inventory -run '^TestBCMInventoryAdapter$' -ginkgo.focus='should not delete runtime resources owned by another instance'` from `bare-metal-fulfillment-operator` in OSAC.

**Preconditions.** Set the stub device's owner to BMI fixture B and call cleanup for fixture A.

1. Read the adapter result and verify mock side effects.

**Expected results.** Cleanup is a no-op for the mismatched owner. No BCM mutation, BMH delete or credential deletion is called.
