# Test Plan — OSAC-41 Cluster as a Service

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 5

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-CAAS-01: A tenant-created cluster reaches readiness

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 118-139](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-41-caas/README.md#L118-L139)
- **Dependencies:** Real deployed fulfillment, AAP, HostedCluster controllers and BMaaS fixture provider; fixture CatalogItem and Secret references.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's published item, worker and management cluster fixtures.

1. Create a Cluster through the tenant CLI.
2. Observe ClusterOrder and HostedCluster availability.

**Expected results.** The cluster is available with its resolved release image and ready worker.

#### TC-CAAS-02: Deleting before readiness reports deletion and removes the API object

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 118-119](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-41-caas/README.md#L118-L119)
- **Dependencies:** Real fulfillment, hub and worker controllers; synthetic fixture and test backend; full provisioning is not awaited.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py`
- **Evidence:** `test_cluster_delete_reports_deleting_state_without_provisioning` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py#L33)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py::test_cluster_delete_reports_deleting_state_without_provisioning` from OSAC root. Source reviewed, test not run.

**Preconditions.** Create the sample cluster and wait for Progressing and an allocated worker.

1. Delete before readiness.
2. Wait for deleting or archived feedback and the removal of the API object and ClusterOrder.

**Expected results.** Deleting feedback is observed and both objects disappear.

#### TC-CAAS-03: Provider-networked Cluster Create requires a ready NATGateway

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [enhancements/OSAC-1436-caas-networking/prd.md, lines 180-180](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1436-caas-networking/prd.md#L180-L180)
- **Dependencies:** Real deployed fulfillment, operator and enabled fixture network provider; no cluster provisioning follows rejected Create.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_nat_gateway_gate.py`
- **Evidence:** `test_cluster_create_requires_ready_nat_gateway` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_nat_gateway_gate.py#L37)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_nat_gateway_gate.py::test_cluster_create_requires_ready_nat_gateway` from OSAC root with provider networking enabled. Source reviewed, test not run.

**Preconditions.** Use the suite's disposable network with a ready Subnet and SecurityGroup and no NATGateway.

1. Submit Cluster Create selecting the fixture attachment.
2. Check status, diagnostic and filtered List for the proposed name.

**Expected results.** Create returns FailedPrecondition with READY NATGateway detail, and List has no persisted Cluster.

#### TC-CAAS-04: A failed provider job leaves readiness false and can reconcile again

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [enhancements/OSAC-1436-caas-networking/design.md, lines 625-627](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1436-caas-networking/design.md#L625-L627)
- **Dependencies:** Real controller/AAP client boundary with a controlled AAP endpoint; no production DNS or real provider target.
- **Gap:** No exact failure-to-recovery action was verified in the CaaS provider workflow tests. This test exercises the later networking design, since the legacy field proposal defines no failure condition.

**Preconditions.** Set up an isolated ClusterOrder and stub the DNS publish job to return failure once, then success.

1. Reconcile the failed job and read endpoint state.
2. Allow the supported retry and inspect the resulting state and recorded jobs.

**Expected results.** EndpointsReady is false with DNSPublishFailed after the fault, and the retry converges without a duplicate endpoint.

#### TC-CAAS-05: Deleting a provisioned cluster removes deployed worker resources

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 118-119](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-41-caas/README.md#L118-L119)
- **Dependencies:** Real deployed fulfillment, AAP, worker and HostedCluster controllers; isolated worker provider fixture and test metering.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Start from the suite's available cluster and recorded worker IDs.

1. Delete the cluster after its ready-state checks.
2. Observe cleanup of worker BMIs, InfraEnv and ClusterOrder, then read the Cluster API.

**Expected results.** Worker BMIs, InfraEnv and ClusterOrder disappear, and the Cluster is removed from gRPC readback.
