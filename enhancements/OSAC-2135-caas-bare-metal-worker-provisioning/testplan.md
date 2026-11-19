# Test Plan — OSAC-2135 CaaS bare-metal worker provisioning

## Overview

- **Feature:** OSAC-2135 — CaaS bare-metal worker provisioning
- **Design:** [design.md](design.md) (§Proposal, §API Extensions, §Test Plan)
- **Total test cases:** 13

Cases are derived from the design's Test Plan section. Existing operator
suites are named in Execution; cases without a suite are gaps rather than
pointers at an unrelated file.

## Reconciliation behaviour

#### TC-U-01: Capacity planning reserves the right number of slots

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/worker_capacity_test.go`
- **Covers:** failed-worker cleanup, concurrent capacity actions

#### TC-U-02: A lost Create acknowledgement does not duplicate a worker

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/bmi_recovery_test.go`
- **Covers:** foreign identity rejection, deletion recovery preserving phase

#### TC-U-03: Scale-down updates the NodePool target before cleanup

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/cleanup_test.go`
- **Covers:** Agent cleanup before BMI deletion

#### TC-U-04: Correlation requires a unique bidirectional match and ready gates

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/correlation_test.go`
- **Covers:** MAC extraction and installed-phase projection

#### TC-U-05: Worker phases progress Provisioning -> WaitingForAgent -> Binding -> Ready

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/agent_reconcile_test.go`

#### TC-U-06: Tenant safety fails closed on a tenant mismatch

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/scaling_tenant_safety_test.go`
- **Covers:** failed excess tenant safety

#### TC-U-07: Fulfillment calls carry the authoritative identity and markers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/fulfillment_test.go`

#### TC-U-08: Dependency failures keep the previous state and back off

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Execution:** `osac-operator/internal/controller/baremetalworker/fulfillment_error_test.go`, `osac-operator/internal/controller/baremetalworker/retry_test.go`

## Envtest

#### TC-I-01: A ClusterOrder with bare-metal node requests creates an InfraEnv and workers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Gap:** the design names `baremetalworker_convergence_test.go`, which does not exist yet.

#### TC-I-02: Agent arrival, BMI handoff, and API publication gate binding independently

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Gap:** no envtest suite covers the gates today.

#### TC-I-03: ClusterOrder deletion waits for ClusterTeardownReady before cleanup

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Gap:** no envtest suite covers teardown ordering.

## End to end

#### TC-E-01: A cluster with bare-metal node requests provisions workers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Covers:** worker agents, aggregates, installation, and worker metrics

#### TC-E-02: Worker usage is attributed and billed after READY only

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Gap:** owned by the QE follow-up OSAC-4843.

## Gaps this plan exposes

- No envtest suite for convergence, gating, or teardown ordering.
- No E2E case for the metering rules that the design specifies.
