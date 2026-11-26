# Test Plan — OSAC-2135 CaaS bare-metal worker provisioning

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 21

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-U-01: Capacity reserves two slots before calling Create

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 941-943](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L941-L943)
- **Dependencies:** Controller package, fake Kubernetes client and recording fulfillment double.
- **Execution:** `osac-operator/internal/controller/baremetalworker/worker_capacity_test.go`
- **Evidence:** `returns after persisting reservations before issuing Create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker/worker_capacity_test.go#L80)).
- **Selector:** Ginkgo focus `returns after persisting reservations before issuing Create` in `osac-operator/internal/controller/baremetalworker`. Source reviewed, test not run.

**Preconditions.** Use the suite's standard NodeSet requesting two workers with none allocated.

1. Run one capacity stage.
2. Inspect the worker journal and recorded Create calls.

**Expected results.** Exactly two named reservations have empty BMI IDs and no Create call has run.

#### TC-U-02: A lost Create acknowledgment preserves the attempt origin

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 943-948](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L943-L948)
- **Dependencies:** Fake Kubernetes client and fulfillment Create error double.
- **Execution:** `osac-operator/internal/controller/baremetalworker/worker_capacity_test.go`
- **Evidence:** `preserves the attempt clock after a lost Create acknowledgement` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker/worker_capacity_test.go#L57)).
- **Selector:** Ginkgo focus `preserves the attempt clock after a lost Create acknowledgement` in `osac-operator/internal/controller/baremetalworker`. Source reviewed, test not run.

**Preconditions.** Use one standard worker reservation and an interrupted Create response.

1. Read the persisted attempt start.
2. Reconcile twice while the Create result remains interrupted.

**Expected results.** The reservation remains singular and its original attempt time is unchanged.

#### TC-U-03: Scale-down lowers desired count while retaining the retiring reference

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 944-958](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L944-L958)
- **Dependencies:** Real envtest API and etcd; in-process controller and recording fulfillment/Agent state fixtures; no CAPI controllers or provider.
- **Execution:** `osac-operator/internal/controller/baremetalworker_convergence_test.go`
- **Evidence:** `drops desired immediately on scale-down and keeps retiring references until cleanup` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker_convergence_test.go#L1922)).
- **Selector:** Ginkgo focus `drops desired immediately on scale-down and keeps retiring references until cleanup` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the suite order with two current workers.

1. Reduce the request to one and reconcile.
2. Read desired/current/ready counters and the worker journal.

**Expected results.** Desired and current are 1, Ready is 0, and the retiring worker remains Unbinding with its BMI ID.

#### TC-U-04: Correlation requires one in-scope match and ready inputs

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 945-945](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L945-L945)
- **Dependencies:** Fake Kubernetes, BMI and networking readbacks with synthetic MAC and address fixtures.
- **Gap:** Correlation and binding specs cover individual guards. A verified single selected-port, API readiness and ambiguity matrix was not identified.

**Preconditions.** Use two fixture Agents and one worker with a selected port, accepted lease and authoritative readbacks.

1. Vary selected port, scope, ownership and candidate count independently.
2. Compare binding intent and mutation counts.

**Expected results.** Only the unique reciprocal in-scope match with all ready inputs binds. Unrelated, claimed or ambiguous candidates remain unchanged.

#### TC-U-05: An installed Agent advances a Binding worker to Ready

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 947-947](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L947-L947)
- **Dependencies:** Fake Kubernetes client and recorded controller events; no CAPI or fulfillment process.
- **Execution:** `osac-operator/internal/controller/baremetalworker/agent_reconcile_test.go`
- **Evidence:** `binding to ready` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker/agent_reconcile_test.go#L84)).
- **Selector:** Ginkgo focus `Agent convergence binding to ready$` in `osac-operator/internal/controller/baremetalworker`. Source reviewed, test not run.

**Preconditions.** Use the table's identified Binding worker and installed Agent.

1. Run the Agent reconciliation stage.
2. Inspect the phase and durable worker identity/history.

**Expected results.** The phase becomes Ready without changing worker identity or attempt history.

#### TC-U-06: Scale-down retains a worker reference with inconsistent tenant ownership

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 949-950](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L949-L950)
- **Dependencies:** In-process worker reconciler and fake fulfillment; no real provider or tenants.
- **Execution:** `osac-operator/internal/controller/baremetalworker/scaling_tenant_safety_test.go`
- **Evidence:** `retains a foreign BMI status ID instead of deleting it during failed scale-down` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker/scaling_tenant_safety_test.go#L48)).
- **Selector:** Ginkgo focus `retains a foreign BMI status ID` in `osac-operator/internal/controller/baremetalworker`. Source reviewed, test not run.

**Preconditions.** Use a synthetic failed worker readback and ClusterOrder with different tenant identities.

1. Run the scale-down reconciliation for the fixture.
2. Inspect Delete calls and the worker journal.

**Expected results.** No Delete is requested and the journal retains the uncertain reference in Unbinding.

#### TC-U-07: Worker creation propagates authoritative placement and provenance

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 949-950](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L949-L950)
- **Dependencies:** Synthetic authorized Cluster and recorded fulfillment request; mocked networking lookups.
- **Gap:** The fulfillment wrapper cases assert deadlines. No one server-owned identity, NodeSet placement and marker assertion was confirmed across the worker request tests.

**Preconditions.** Set up a fixture Cluster with a tenant, Subnet, node-set instance type and selected fabric interface.

1. Reconcile one owned worker Create.
2. Compare the recorded request with authoritative fixture placement, owner and cluster provenance.

**Expected results.** The request carries the trusted tenant, Subnet, both SecurityGroups, selected interface, type and Cluster API ID.

#### TC-U-08: A blocked dependency preserves the allocation and schedules backoff

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 949-951](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L949-L951)
- **Dependencies:** Fake fulfillment and provider clients with captured metrics and a fixed clock.
- **Gap:** Retry and failure-classification tests exercise parts of the result. No single combined checkpoint/no-attempt/no-metric assertion was verified.

**Preconditions.** Reserve a fixture worker and return FailedPrecondition for a not-yet-ready dependency.

1. Reconcile once and inspect status, error metrics and retry duration.
2. Mark the dependency ready and reconcile again.

**Expected results.** The slot remains reserved without a new Failed phase, failed attempt or failure metric. Retry uses backoff and later proceeds with the same slot.

#### TC-I-01: Envtest creates InfraEnv and starts two bare-metal workers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 954-956](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L954-L956)
- **Dependencies:** Real envtest Kubernetes API and etcd, in-process reconciler and local ignition HTTP fixture; fake private fulfillment, Agent status fixture and no network provider or BMaaS hosts.
- **Execution:** `osac-operator/internal/controller/baremetalworker_lifecycle_test.go`
- **Evidence:** `starts worker provisioning and stalls at Binding without networking` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker_lifecycle_test.go#L84)).
- **Selector:** Ginkgo focus `starts worker provisioning and stalls at Binding without networking` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the suite ClusterOrder requesting two bm-standard workers and the fixture ignition endpoint.

1. Reconcile until the InfraEnv exists, supply fixture ignition and observe its Ready condition.
2. Drive worker creation and compare fake Create calls with the worker journal.

**Expected results.** InfraEnvReady becomes true. Two tenant-owned BMI Create calls, with the fixture Subnet name, produce two identified WaitingForAgent workers. No worker reaches Ready without the networking dependency.

#### TC-I-02: An installed Agent cannot cause Ready until a fresh post-bind observation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 954-957](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L954-L957)
- **Dependencies:** Real envtest API/etcd and in-process worker controller; Agent/host readbacks and fulfillment are fixtures; no CAPI or provider.
- **Execution:** `osac-operator/internal/controller/baremetalworker_convergence_test.go`
- **Evidence:** `makes no Ready decision from the pre-bind snapshot` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker_convergence_test.go#L1596)).
- **Selector:** Ginkgo focus `makes no Ready decision from the pre-bind snapshot` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the suite's worker and an unbound Agent with matching MAC and installed state.

1. Reconcile binding, then read worker status.
2. Reconcile again and check Agent version and Create calls.

**Expected results.** First observation is Binding; the second becomes Ready without repatching the Agent or allocating again.

#### TC-I-03: ClusterOrder deletion waits for ClusterTeardownReady

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 958-960](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L958-L960)
- **Dependencies:** Real envtest API and worker controller; synthetic pending endpoint/job, Agent and fake BMI API; no real networking provider.
- **Gap:** Worker lifecycle and convergence suites were checked. No exact full gate-to-finalizer ordering assertion was verified.

**Preconditions.** Mark a fixture order deleting with an Agent, BMI and pending automatic endpoint cleanup.

1. Reconcile with teardown not ready, then after setting it ready.
2. Record Agent removal, BMI Delete and finalizer order.

**Expected results.** No worker cleanup starts before readiness. The Agent is removed before BMI deletion, and both are cleared before the worker finalizer.

#### TC-I-04: A lost Create response recovers the original worker after restart

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 943-948](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L943-L948)
- **Dependencies:** Real envtest API/etcd and in-process reconciler; fake fulfillment commits one Create and controls List visibility; no real host.
- **Execution:** `osac-operator/internal/controller/baremetalworker_convergence_test.go`
- **Evidence:** `recovers a lost Create acknowledgement after restart and delayed List visibility` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker_convergence_test.go#L905)).
- **Selector:** Ginkgo focus `recovers a lost Create acknowledgement after restart and delayed List visibility` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the suite order requesting two workers and a fixture that drops the first successful Create response and delays List visibility.

1. Restart reconciliation and observe the first reservation while the committed worker is hidden.
2. Restore visibility, inspect the recovered ID and then reconcile the independent second reservation.

**Expected results.** The first reservation recovers its original worker ID without a second allocation. The second starts independently after recovery and the fixture ends with two distinct worker records.

#### TC-I-05: Each Agent, BMI and management publication gate blocks premature binding

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 954-957](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L954-L957)
- **Dependencies:** Real envtest API; fixture Agent, BMI readiness/lease and publication inputs; fake fulfillment, no live provider.
- **Gap:** The convergence suite proves post-bind observation and real binding conflict in individual specs. No exact three-input matrix was verified.

**Preconditions.** Set up a worker with otherwise valid fixture evidence.

1. Hold Agent, BMI handoff and management publication absent in separate runs.
2. Supply all evidence and observe binding.

**Expected results.** Each missing gate prevents approval and labels. Binding begins only when all required inputs are present.

#### TC-I-06: InfraEnv uses late binding and controller-owned credentials

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 943-946](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L943-L946)
- **Dependencies:** Real envtest API and in-process worker controller; fake fulfillment image lookup and synthetic Secret; no assisted-service or host.
- **Gap:** No verified test was found for the combined owner reference, absent clusterRef, selected image and owned pull-secret fields in worker Envtest sources.

**Preconditions.** Prepare a fixture ClusterOrder UID, selected image and synthetic pull-secret reference.

1. Reconcile InfraEnv creation.
2. Read owner references, spec and Secret ownership.

**Expected results.** The order owns InfraEnv, clusterRef is absent, the selected image is retained and the referenced Secret is controller-owned.

#### TC-I-07: A concurrent Agent binding wins without controller takeover

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 945-949](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L945-L949)
- **Dependencies:** Real envtest API and etcd, fixture Agent and recording fulfillment; a test hook supplies a competing binding update.
- **Execution:** `osac-operator/internal/controller/baremetalworker_convergence_test.go`
- **Evidence:** `propagates a real Agent binding conflict without takeover` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/baremetalworker_convergence_test.go#L1275)).
- **Selector:** Ginkgo focus `propagates a real Agent binding conflict without takeover` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the suite's worker and initially unbound Agent fixture.

1. Introduce a concurrent supported Agent update in the fixture when reconciliation begins.
2. Observe the reconciliation result and read the persisted binding.

**Expected results.** The optimistic update reports a conflict and the competing binding remains intact.

#### TC-E-01: A deployed cluster provisions its requested bare-metal worker

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 962-964](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L962-L964)
- **Dependencies:** Real deployed fulfillment, operator, AAP, assisted-service and BMaaS test provider; test cluster template, host and metering collector.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite catalog item with one ci-worker-bm worker.

1. Create a Cluster through the tenant CLI.
2. Wait for cluster availability and inspect guest workers and hub correlations.

**Expected results.** The guest has the expected ready worker, and hub status correlates the worker to the requested NodeSet.

#### TC-E-02: Deleting a cluster before Ready emits no worker or control-plane usage

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 954-964](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L954-L964)
- **Dependencies:** Real deployed fulfillment, cluster/worker controllers and metering; isolated compatible BMaaS test backend and Echo readback.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py`
- **Evidence:** `test_cluster_delete_reports_deleting_state_without_provisioning` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py#L33)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_delete_feedback_light.py::test_cluster_delete_reports_deleting_state_without_provisioning` from OSAC root. Source reviewed, test not run.

**Preconditions.** Start the fixture cluster and wait while Progressing for one allocated worker.

1. Delete before the cluster reaches Ready.
2. After removal, check usage since test start for the cluster and allocated worker IDs using the suite's bounded observation.

**Expected results.** No cluster or worker heartbeats are observed during the 120-second checks.

#### TC-E-03: Scaling adds and removes the selected worker without replacement

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 965-967](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L965-L967)
- **Dependencies:** Real deployed OSAC, BMaaS, CAPI, assisted-service and real tenant API; dedicated worker fixtures.
- **Gap:** Canonical lifecycle issues scale requests. Exact target, selected Machine drain and no-replacement assertions remain unresolved for the combined deployed scenario.

**Preconditions.** Use one ready worker and capacity for a second in a disposable test pool.

1. Scale to two and observe the new worker joining.
2. Scale back to one and track the NodePool target, Machine, Agent and BMI.

**Expected results.** The new worker joins, the target decreases before cleanup, and the selected Machine, Agent and BMI disappear without another allocation.

#### TC-E-04: Eligible active workers begin billing after cluster readiness

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 954-964](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L954-L964)
- **Dependencies:** Real deployed fulfillment, Kafka and metering with Echo readback and a BMaaS/assisted-service fixture.
- **Gap:** Canonical cluster-create metering helpers establish typed worker usage once available. Exact retroactive eligibility and no duplicate Cluster worker-count charge need a separate verified mapping.

**Preconditions.** Create a fixture Cluster with an allocated worker that becomes active before Cluster readiness.

1. Observe usage until READY, then read typed worker heartbeats for its allocation span.
2. Compare worker and Cluster charges for the same time interval.

**Expected results.** Before READY no worker usage is emitted. After READY the eligible active span appears once under the worker ID without duplicate Cluster worker-count usage.

#### TC-E-05: A tenant sees its cluster workers and their provenance

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 968-968](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L968-L968)
- **Dependencies:** Real deployed fulfillment, hub and BMaaS test provider; tenant and host fixtures.
- **Execution:** `tests/e2e/caas/sanity/test_cluster_create.py`
- **Evidence:** `test_cluster_create` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/caas/sanity/test_cluster_create.py#L677)).
- **Selector:** `uv run pytest -n 0 tests/e2e/caas/sanity/test_cluster_create.py::test_cluster_create` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the suite's available Cluster fixture and its requested worker NodeSet.

1. Read the worker IDs and their correlated ClusterOrder.
2. Compare the worker API records with the cluster tenant and order labels.

**Expected results.** The worker records retain tenant ownership and ClusterOrder provenance. Worker update and direct Delete behavior remain separate.

#### TC-E-06: Cluster workers provision without creating a BareMetalPool

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 969-971](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#L969-L971)
- **Dependencies:** Real deployed OSAC, AAP and isolated BMaaS test provider; fixture Cluster and dedicated hub namespace.
- **Gap:** Canonical worker lifecycle verifies BMI and Agent objects. No matching assertion found for the absence of BareMetalPool objects and task references.

**Preconditions.** Record the empty BareMetalPool inventory in an isolated hub namespace.

1. Provision the fixture Cluster with one bare-metal worker.
2. Check the hub inventory and cluster_infra execution record.

**Expected results.** A ready worker appears with no BareMetalPool created and no pool task invoked.
