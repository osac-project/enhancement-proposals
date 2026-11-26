# Test Plan — OSAC-1332 CaaS cluster storage

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 18

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

## Test Cases

#### TC-CS-01: ClusterOrder mapper returns the owning Tenant key

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [ClusterOrder annotation lookup](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L329)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: mapClusterOrderToTenant / should return reconcile request for the owning Tenant` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3097)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: mapClusterOrderToTenant should return reconcile request for the owning Tenant$'` from `osac-operator` in OSAC.

**Preconditions.** Persist a ready Tenant and a ClusterOrder annotated with that tenant's name.

1. Call the ClusterOrder mapper with the fixture order.
2. Inspect the queue requests.

**Expected results.** Exactly one request names the fixture Tenant and its namespace.

#### TC-CS-02: Missing HostedControlPlane kubeconfig Secret yields no kubeconfig

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Kubeconfig Secret lookup](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L330)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: getClusterKubeconfig / should return nil when kubeconfig Secret does not exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3438)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: getClusterKubeconfig should return nil when kubeconfig Secret does not exist$'` from `osac-operator` in OSAC.

**Preconditions.** Use a fixture order and HostedControlPlane referencing an absent Secret.

1. Run the kubeconfig lookup.
2. Inspect the returned payload.

**Expected results.** No kubeconfig is returned when the recorded Secret does not exist.

#### TC-CS-03: Ready ClusterOrder without kubeconfig is protected but stays storage-unready

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CaaS readiness and finalizer](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L331)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: provisioning trigger / should trigger CaaS provisioning for Ready ClusterOrder with backend ready` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3481)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: provisioning trigger should trigger CaaS provisioning for Ready ClusterOrder with backend ready$'` from `osac-operator` in OSAC.

**Preconditions.** Create a ready Tenant with its backend Secret and VMaaS class, plus an associated Ready ClusterOrder without a cluster reference.

1. Reconcile the Tenant's storage.
2. Read the persisted order finalizers and storage condition.

**Expected results.** The order has the storage finalizer and ClusterStorageReady=False.

#### TC-CS-04: ClusterOrder teardown completes before the finalizer is released

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CaaS teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L332)
- **Dependencies:** Real Kubernetes API server and etcd under envtest, with the reconciler called in-process. The provider/AAP client and job outcomes are test doubles.
- **Gap:** Envtest covers deletion with no provider or kubeconfig. The deployed test observes final removal. Neither holds an active remote cleanup job pending to verify finalizer order.

**Preconditions.** Seed a deleting order with its storage finalizer and a previously provisioned entry.

1. Hold fixture teardown pending and inspect protection.
2. Complete the job and repeat with the HostedControlPlane already gone.

**Expected results.** While cleanup is pending the finalizer stays. Successful cleanup removes the entry and releases the order.

#### TC-CS-05: CaaS class discovery reports ambiguous classes for the same tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Duplicate StorageClass reporting](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L333)
- **Dependencies:** Requires real envtest hub and target Kubernetes APIs, etcd and a synthetic ClusterOrder. Provisioning is scripted.
- **Gap:** The storage Envtest checks duplicate classes at the shared Tenant resolver. No CaaS target-cluster reconciliation case verifies the warning and status on this boundary.

**Preconditions.** Use an isolated CaaS storage reconcile fixture with two equally eligible StorageClasses for the same tier on the target cluster.

1. Reconcile cluster storage and inspect the order's storage readiness and warning events.

**Expected results.** The affected tier remains unresolved and a duplicate-class warning identifies it.

#### TC-CS-06: CaaS provisioning and teardown report lifecycle state

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Deployed provisioning and teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L339)
- **Dependencies:** Real deployed hub, CaaS and tenant cluster, storage controller, AAP and configured storage provider. Dedicated test tenant and cluster; no provider double.
- **Execution:** `tests/e2e/storage/test_caas_cluster_storage.py`
- **Evidence:** `test_caas_cluster_storage_lifecycle` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/tests/e2e/storage/test_caas_cluster_storage.py#L46)).
- **Selector:** Select the pytest node `tests/e2e/storage/test_caas_cluster_storage.py::test_caas_cluster_storage_lifecycle` from the isolated OSAC test environment.

**Preconditions.** Use the CaaS storage suite with a dedicated Tenant, cluster template and fixture storage provider.

1. Provision the cluster, read its storage condition/finalizer and Tenant entry.
2. Delete the cluster and verify entry cleanup.

**Expected results.** The order gains the storage finalizer and ClusterStorageReady=True. A ready Tenant clusterStorage entry is present, then disappears on teardown if the Tenant still exists.

#### TC-CS-07: StorageClasses are isolated to the owning cluster

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Cluster storage isolation](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L341)
- **Dependencies:** Real deployed hub, CaaS and tenant cluster, storage controller, AAP and configured storage provider. Dedicated test tenant and cluster; no provider double.
- **Gap:** The deployed CaaS storage suite provisions one tenant and one cluster. It does not compare a second cluster's tier classes.

**Preconditions.** Use two disposable clusters from different fixture tenants and unique storage-tier classes.

1. Read classes on each cluster through its authorized test context.
2. Compare visible fixture class identities.

**Expected results.** Each cluster sees its designated class without exposing classes assigned to the other fixture tenant.

#### TC-CS-08: Missing cluster reference yields no kubeconfig

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Kubeconfig inputs](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L330)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: getClusterKubeconfig / should return nil when ClusterReference is nil` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3403)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: getClusterKubeconfig should return nil when ClusterReference is nil$'` from `osac-operator` in OSAC.

**Preconditions.** Persist a synthetic ClusterOrder with an unset cluster reference.

1. Call the kubeconfig retrieval helper for that order.

**Expected results.** The helper returns nil bytes with no error.

#### TC-CS-09: VMaaS class resolution preserves an existing CaaS status entry

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [VMaaS regression](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L334)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: VMaaS regression / should not affect VMaaS provisioning when CaaS ClusterOrders exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3552)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: VMaaS regression should not affect VMaaS provisioning when CaaS ClusterOrders exist$'` from `osac-operator` in OSAC.

**Preconditions.** Seed a ready Tenant with a backend Secret, one local VMaaS class and a Ready ClusterOrder with a ready CaaS status entry.

1. Reconcile the Tenant in the local VMaaS configuration.
2. Read its storage classes and clusterStorage entries.

**Expected results.** The local class resolves, ClusterStorageReady is true, and clusterStorage contains both the local entry and the previously recorded CaaS entry.

#### TC-CS-10: A PVC can use a provisioned CaaS StorageClass

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Deployed PVC use](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L339)
- **Dependencies:** Real deployed hub, CaaS and tenant cluster, storage controller, AAP and configured storage provider. Dedicated test tenant and cluster; no provider double.
- **Gap:** CaaS lifecycle checks observed storage state and trust setup. PVC binding and I/O remain unverified.

**Preconditions.** Provision a disposable cluster with a configured test StorageClass and a fixture workload.

1. Request a small PVC using that class.
2. Wait for it to bind and read back a fixture value, then clean up.

**Expected results.** The bound volume uses the selected class and returns the fixture bytes.

#### TC-CS-11: Missing HostedControlPlane yields no kubeconfig

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Kubeconfig inputs](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L330)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: getClusterKubeconfig / should return nil when HostedControlPlane does not exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3418)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: getClusterKubeconfig should return nil when HostedControlPlane does not exist$'` from `osac-operator` in OSAC.

**Preconditions.** Create a synthetic order whose cluster reference points to an absent HostedControlPlane.

1. Call the kubeconfig retrieval helper.

**Expected results.** The helper returns nil bytes with no error.

#### TC-CS-12: Secret without the requested data key yields no kubeconfig

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Kubeconfig inputs](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L330)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Gap:** The storage controller envtest checks missing order reference, absent control plane, missing Secret and a valid Secret. It does not verify a present Secret with the requested key absent.

**Preconditions.** Seed a HostedControlPlane and its referenced synthetic Secret with only an unrelated data key.

1. Call the kubeconfig retrieval helper for the referencing ClusterOrder.

**Expected results.** No kubeconfig bytes are returned.

#### TC-CS-13: ClusterOrder mapper ignores an order without the tenant annotation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [ClusterOrder annotation lookup](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L329)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: mapClusterOrderToTenant / should return nil when tenant annotation is missing` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3118)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: mapClusterOrderToTenant should return nil when tenant annotation is missing$'` from `osac-operator` in OSAC.

**Preconditions.** Persist an order without the tenant annotation in the isolated envtest namespace.

1. Call the mapper for the persisted order.

**Expected results.** No Tenant reconcile request is returned.

#### TC-CS-14: ClusterOrder mapper ignores an order with an empty tenant annotation

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [ClusterOrder annotation lookup](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L329)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: mapClusterOrderToTenant / should return nil when tenant annotation is empty` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3132)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: mapClusterOrderToTenant should return nil when tenant annotation is empty$'` from `osac-operator` in OSAC.

**Preconditions.** Persist an order with an empty tenant annotation in the isolated envtest namespace.

1. Call the mapper for the persisted order.

**Expected results.** No Tenant reconcile request is returned.

#### TC-CS-15: ClusterOrder mapper ignores an order naming an absent Tenant

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [ClusterOrder annotation lookup](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L329)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: mapClusterOrderToTenant / should return nil when referenced Tenant does not exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3148)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: mapClusterOrderToTenant should return nil when referenced Tenant does not exist$'` from `osac-operator` in OSAC.

**Preconditions.** Persist an order naming an absent Tenant in the isolated envtest namespace.

1. Call the mapper for the persisted order.

**Expected results.** No Tenant reconcile request is returned.

#### TC-CS-16: Progressing ClusterOrder does not gain the storage finalizer

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CaaS readiness and finalizer](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L331)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: provisioning trigger / should skip CaaS provisioning for non-Ready ClusterOrders` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3521)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: provisioning trigger should skip CaaS provisioning for non-Ready ClusterOrders$'` from `osac-operator` in OSAC.

**Preconditions.** Create a ready Tenant, its hub Secret and a Progressing ClusterOrder belonging to the tenant.

1. Run a tenant storage reconcile with the provider double.
2. Re-read the order.

**Expected results.** The order does not acquire the cluster-storage finalizer in this fixture.

#### TC-CS-17: Deleting ClusterOrder can exit when no storage provider or kubeconfig exists

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CaaS teardown](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L332)
- **Dependencies:** Real envtest Kubernetes API and etcd with the mapper or lookup helper called directly. No AAP, provider or remote-cluster client.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CaaS: cluster deletion without storage provider (OSAC-4340) / should remove the cluster-storage finalizer from a deleting ClusterOrder when no ClusterStorageProvider is configured` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3625)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CaaS: cluster deletion without storage provider \(OSAC-4340\) should remove the cluster-storage finalizer from a deleting ClusterOrder when no ClusterStorageProvider is configured$'` from `osac-operator` in OSAC.

**Preconditions.** Persist an order with the storage finalizer and no cluster reference. Configure no storage provider.

1. Request deletion and reconcile its Tenant.
2. Re-read the order if it still exists.

**Expected results.** The order is gone or its storage finalizer has been removed.

#### TC-CS-18: Both readiness gates are required before the remote job is submitted

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CaaS readiness and finalizer](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-1332-caas-cluster-storage/design.md#L331)
- **Dependencies:** Real envtest Kubernetes API and etcd. Calls the reconciler or helper in-process; fulfillment and provisioning clients are absent or fixture doubles.
- **Gap:** The envtest readiness specs inspect finalizers and conditions without a usable remote kubeconfig. The deployed suite observes eventual readiness but does not vary the two gates.

**Preconditions.** Use a Tenant with a fixture backend, local class and a ClusterOrder with a valid synthetic kubeconfig. Configure the provider double to record remote submission.

1. Reconcile while only the Tenant is ready, then while only the order is ready.
2. Make both ready and reconcile again.

**Expected results.** The provider records no remote job until both are ready, and records one remote submission afterward.
