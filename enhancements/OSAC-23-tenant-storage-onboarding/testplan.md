# Test Plan — OSAC-23 Tenant storage onboarding

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 21

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

The design describes a shared Default fallback and a NamespaceReady gate. Current controller specs resolve tenant-labelled classes without that fallback and report Tenant phase independently of NamespaceReady. The cases below identify these differences.

## Test Cases

#### TC-TO-01: Stage 1 records a provisioning job when the hub Secret is absent

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 1 without Secret](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L473)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Stage 1: Backend provisioning / should trigger backend provisioning when hub Secret is missing` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L484)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Stage 1: Backend provisioning should trigger backend provisioning when hub Secret is missing$'` from `osac-operator` in OSAC.

**Preconditions.** Use a ready Tenant with a registered backend fixture and no matching hub Secret.

1. Run one storage reconciliation with the provider double.
2. Read the persisted Tenant and reconcile result.

**Expected results.** The controller schedules its poll interval, records one backend Provision job and reports StorageBackendReady=False.

#### TC-TO-02: Stage 2 provisions when Stage 1 is complete and classes are missing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 2 with Stage 1 complete](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L474)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Stage 2: Cluster storage provisioning / should trigger cluster storage provisioning when Stage 1 complete but no SCs` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L647)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Stage 2: Cluster storage provisioning should trigger cluster storage provisioning when Stage 1 complete but no SCs$'` from `osac-operator` in OSAC.

**Preconditions.** Use a ready tenant and valid Stage 1 Secret with no eligible StorageClass.

1. Reconcile storage with outstanding class discovery.
2. Observe cluster-storage job submission.

**Expected results.** The fixture requests Stage 2 provisioning.

#### TC-TO-03: A duplicate class association is ambiguous, not missing

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Duplicate tier classification](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L475)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Tier definition validation / should not flag an ambiguous (duplicate StorageClass) tier as missing` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L1374)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Tier definition validation should not flag an ambiguous \(duplicate StorageClass\) tier as missing$'` from `osac-operator` in OSAC.

**Preconditions.** Seed two eligible StorageClasses for a single fixture tier.

1. Resolve StorageClasses.
2. Read the duplicate tier’s classification.

**Expected results.** The ambiguous tier is not also classified as missing.

#### TC-TO-04: Cluster-storage teardown is requested before backend teardown

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Ordered teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L476)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Deprovisioning ordering / should clean up cluster storage before backend teardown` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3007)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Deprovisioning ordering should clean up cluster storage before backend teardown$'` from `osac-operator` in OSAC.

**Preconditions.** Create a ready Tenant with its hub Secret and scripted successful cluster-storage and backend teardown providers.

1. Reconcile once and confirm the Tenant has the storage finalizer.
2. Delete the Tenant and reconcile until both mock teardown calls are recorded.

**Expected results.** The recorder sees cluster-storage first and backend second.

#### TC-TO-05: Unmanaged tenant skips steady-state storage reconciliation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Unmanaged steady state](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L477)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Management state / should skip reconciliation when Unmanaged` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L2225)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Management state should skip reconciliation when Unmanaged$'` from `osac-operator` in OSAC.

**Preconditions.** Create a ready Tenant whose management state is Unmanaged, with a scripted provider.

1. Run one reconcile without requesting deletion.
2. Read the job arrays and the finalizers.

**Expected results.** No requeue, storage jobs or storage finalizer are present.

#### TC-TO-06: Kind API projects and retains signaled storage conditions

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Condition propagation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L484)
- **Dependencies:** Real Kind Kubernetes API, deployed fulfillment controller and PostgreSQL. The test writes the operator conditions and sends Signal. No provider or automatic feedback assertion.
- **Execution:** `fulfillment-service/it/it_tenant_storage_onboarding_test.go`
- **Evidence:** `TestIntegration / Tenant storage onboarding feedback / projects and retains operator storage conditions through signaling and reads` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_tenant_storage_onboarding_test.go#L33)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Tenant storage onboarding feedback / projects and retains operator storage conditions through signaling and reads` in the service-only phase.

**Preconditions.** Create a synthetic Tenant in Kind and wait for its CR. Use the private fulfillment client and test-driven hub status.

1. Seed False, Unknown and True StorageReady in the CR status in turn and send Signal for each.
2. Read each persisted condition through a fresh private API request.

**Expected results.** The API projects the expected condition status, reason, message and transition time while retaining the Tenant's other conditions.

#### TC-TO-07: Deployed tenant storage becomes ready and tenant Secrets clear on deletion

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Deployed onboarding and teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L490)
- **Dependencies:** Deployed hub, storage operator, AAP and configured storage provider with an isolated tenant fixture. No provider double.
- **Execution:** `tests/e2e/storage/test_tenant_storage_lifecycle.py`
- **Evidence:** `test_tenant_storage_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/storage/test_tenant_storage_lifecycle.py#L24)).
- **Selector:** Select the pytest node `tests/e2e/storage/test_tenant_storage_lifecycle.py::test_tenant_storage_lifecycle` from the isolated OSAC test environment.

**Preconditions.** Use a dedicated Tenant under the deployed managed-storage fixture.

1. Wait for backend and cluster-storage readiness and read the fixture classes.
2. Request Tenant deletion and wait for removal.
3. Query only Secrets owned by that fixture Tenant.

**Expected results.** The reported StorageClasses exist before deletion. The Tenant disappears and its storage namespace has zero Secrets labelled for that fixture.

#### TC-TO-08: Stage 1 does not start for a non-Ready Tenant

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 1 readiness](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L473)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Stage 1: Backend provisioning / should skip reconciliation when Tenant is not Ready` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L453)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Stage 1: Backend provisioning should skip reconciliation when Tenant is not Ready$'` from `osac-operator` in OSAC.

**Preconditions.** Create a Tenant without Ready phase and supply a backend provider double.

1. Reconcile storage once.
2. Read the reconcile result and Tenant backend condition.

**Expected results.** There is no timed requeue, provisioning job or StorageBackendReady condition.

#### TC-TO-09: Partial backend Secrets leave StorageBackendReady false

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 1 incomplete provisioning](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L473)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Multi-provider hub secret readiness (OSAC-4855) / should not set StorageBackendReady=True when hub Secrets exist for only some dispatched providers` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L2440)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Multi-provider hub secret readiness \(OSAC-4855\) should not set StorageBackendReady=True when hub Secrets exist for only some dispatched providers$'` from `osac-operator` in OSAC.

**Preconditions.** Seed a ready Tenant with dispatched LVMS and VAST fixture backends and a hub Secret only for LVMS.

1. Reconcile once.
2. Read the aggregate condition and the two backend entries.

**Expected results.** StorageBackendReady is False. Exactly LVMS reports Ready and the message identifies the missing VAST Secret.

#### TC-TO-10: Tenant phase reaches Ready without a NamespaceReady condition

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Tenant controller storage independence](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L478)
- **Dependencies:** Real envtest API and etcd. Runs the Tenant reconciler in-process without storage providers.
- **Execution:** `osac-operator/internal/controller/tenant_controller_test.go`
- **Evidence:** `TestControllers / Tenant Controller / When namespace exists / should set Phase=Ready without setting NamespaceReady` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/tenant_controller_test.go#L67)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Tenant Controller When namespace exists should set Phase=Ready without setting NamespaceReady$'` from `osac-operator` in OSAC.

**Preconditions.** Create a Tenant with its synthetic workload namespace present and no NamespaceReady condition.

1. Run the Tenant reconciler directly.
2. Read the persisted Tenant.

**Expected results.** Phase=Ready, status.namespace is empty and NamespaceReady stays absent. This is the current controller behavior.

#### TC-TO-11: Missing tier appears in ClusterStorageReady and a warning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Missing storage tier](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L475)
- **Dependencies:** Real envtest Kubernetes API and etcd with synthetic StorageClasses. Catalog replies, provisioning clients and the event recorder are test doubles; no external provider.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Tier definition validation / should report a missing tier via Warning Event and the ClusterStorageReady condition` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L1130)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Tier definition validation should report a missing tier via Warning Event and the ClusterStorageReady condition$'` from `osac-operator` in OSAC.

**Preconditions.** Seed default and archive tier responses. Create the default class only.

1. Reconcile with the fixture catalog and event recorder.
2. Read ClusterStorageReady and the Warning.

**Expected results.** Both the condition message and MissingStorageTier warning identify archive.

#### TC-TO-12: Simultaneous controllers preserve finalizers and competing status updates

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Simultaneous controllers and status conflicts](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L482)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Gap:** The storage controller Envtest verifies patch preservation in isolation. The Kind feedback test injects operator state. Simultaneous reconciliation and conflict resolution are unverified.

**Preconditions.** Start both controllers on one fixture Tenant and retain the two finalizers.

1. Make both produce status writes using the same initial object version.
2. Allow a retry and compare status/finalizers after deletion is requested.

**Expected results.** Neither status nor finalizer is lost; each finalizer clears only after its owned work finishes.

#### TC-TO-13: Unmanaged deletion still honors previously installed storage finalizer

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Unmanaged deletion](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L477)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Gap:** The storage controller envtest checks unmanaged steady state and separate managed deletion. It does not verify the transition to unmanaged with existing cleanup work.

**Preconditions.** Use a previously managed synthetic Tenant with a storage finalizer and set it to Unmanaged.

1. Request deletion and report successful scripted teardown.
2. Observe the fixture cleanup calls and deletion.

**Expected results.** Deletion still queues cleanup and the finalizer releases after completion.

#### TC-TO-14: Stage 2 waits while Stage 1 provisioning is pending

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage ordering](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L474)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Gap:** Stage 1 launch and Stage 2 launch have distinct envtest assertions. No pending-Stage-1 test explicitly verifies zero Stage 2 submissions.

**Preconditions.** Use a ready Tenant with no hub Secret and an in-flight fixture Stage 1 job.

1. Reconcile with the backend still pending.
2. Inspect the Stage 2 mock calls.

**Expected results.** No Stage 2 job is submitted while the Stage 1 job is pending.

#### TC-TO-15: Active teardown job retains the storage finalizer

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Partial teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L476)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CSP-managed storage (pure cspManaged flow) / should not skip cluster or backend deprovisioning when 0 OSAC tiers resolve but a deprovision job is active or failed with BlockDeletionOnFailure` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L4634)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CSP-managed storage \(pure cspManaged flow\) should not skip cluster or backend deprovisioning when 0 OSAC tiers resolve but a deprovision job is active or failed with BlockDeletionOnFailure$'` from `osac-operator` in OSAC.

**Preconditions.** Use two deleting Tenant fixtures with no resolvable OSAC tier. Seed an active cluster-storage deprovision job on one and a backend deprovision job on the other.

1. Reconcile each Tenant with its scripted job still running.
2. Inspect the provider poll count, requeue and finalizer.

**Expected results.** Each provider is polled once in its fixture and reconciliation requeues while the storage finalizer remains.

#### TC-TO-21: Tenant storage finalizer releases after both cleanup legs finish

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Finalizer release after complete teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L476)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Gap:** The storage controller Envtest verifies dispatch order and retention for an individual active cleanup job. No single two-stage spec inspects both sides of the finalizer release.

**Preconditions.** Use a deleting Tenant whose cluster-storage and backend deprovision jobs can be completed independently.

1. Complete only cluster-storage cleanup and observe the finalizer while backend cleanup remains active.
2. Complete backend cleanup and reconcile again.

**Expected results.** The finalizer remains after cluster-storage cleanup and releases once both jobs succeed.

#### TC-TO-16: Tenant-labelled StorageClass wins over a class labelled Default

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [StorageClass discovery](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L475)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Tier resolution / should resolve only tenant-specific SCs (unlabeled Default SCs ignored)` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L874)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Tier resolution should resolve only tenant-specific SCs \(unlabeled Default SCs ignored\)$'` from `osac-operator` in OSAC.

**Preconditions.** Seed one eligible tenant-labelled default tier class and one class labelled Default for the same tier.

1. Reconcile the tenant and read the resolved classes.

**Expected results.** Only the tenant-labelled class resolves.

#### TC-TO-17: A Stage 2 submission error leaves no job entry

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 2 job failure](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L474)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Cluster storage failure / should record failed cluster storage provisioning job` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L2318)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Cluster storage failure should record failed cluster storage provisioning job$'` from `osac-operator` in OSAC.

**Preconditions.** Use a ready Tenant with its hub Secret, no resolved classes and a Stage 2 mock returning a fixture launch error.

1. Run the Storage reconciler.
2. Read its error and persisted ClusterStorageJobs.

**Expected results.** It returns the launch error and does not persist a job entry.

#### TC-TO-18: Deployed tenant StorageClass is consumed by ComputeInstance

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [ComputeInstance storage use](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L494)
- **Dependencies:** Deployed hub, storage operator, AAP and configured storage provider with an isolated tenant fixture. No provider double.
- **Gap:** The tenant storage lifecycle checks the classes without a ComputeInstance. The VMaaS tier-selection suite uses pre-provisioned fixtures and does not connect the disk to this onboarding run.

**Preconditions.** Use a Tenant onboarded through the VAST fixture and a provisionable VM template.

1. Create a ComputeInstance using the Tenant's resolved tier.
2. Read its disk StorageClass and verify the running fixture.

**Expected results.** The boot disk uses the class from Tenant onboarding and the ComputeInstance becomes available.

#### TC-TO-19: Stage 2 sets readiness when the tenant class is found

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Stage 2 class discovery](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L474)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Stage 2: Cluster storage provisioning / should set ClusterStorageReady=True when SCs are discovered` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L675)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Stage 2: Cluster storage provisioning should set ClusterStorageReady=True when SCs are discovered$'` from `osac-operator` in OSAC.

**Preconditions.** Use a ready Tenant, a matching hub Secret and one labelled default-tier StorageClass.

1. Run storage reconciliation.
2. Read ClusterStorageReady and the class list.

**Expected results.** ClusterStorageReady=True and the class list contains the exact matching fixture name and default tier.

#### TC-TO-20: Tenant controller leaves storage status untouched

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Tenant controller excludes storage logic](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-23-tenant-storage-onboarding/design.md#L478)
- **Dependencies:** Real envtest Kubernetes API and etcd. Tenant controller runs directly without providers.
- **Execution:** `osac-operator/internal/controller/tenant_controller_test.go`
- **Evidence:** `TestControllers / Tenant Controller / When namespace exists / should not modify storage fields` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/tenant_controller_test.go#L85)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Tenant Controller When namespace exists should not modify storage fields$'` from `osac-operator` in OSAC.

**Preconditions.** Create a synthetic Tenant with an existing namespace and no storage classes or jobs in its status.

1. Reconcile with the Tenant controller.
2. Read the persisted storage fields.

**Expected results.** StorageClasses and ProvisioningJobs remain unset.
