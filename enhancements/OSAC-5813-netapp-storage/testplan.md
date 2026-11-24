# Test Plan — OSAC-5813 CSP-managed NetApp storage for VMaaS

## Overview

- **Design:** [Public PRD](prd.md)
- **Total test cases:** 11

Execution entries identify assertions inspected on OSAC main. The listed product suites were not run during this documentation update.

## Test Cases

#### TC-NA-01: A credential-free CSP-managed NetApp backend persists

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [CSP-managed backend registration](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L21)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. Backend records are fixtures; no external array or AAP workflow.
- **Execution:** `fulfillment-service/it/it_storage_backend_ownership_test.go`
- **Evidence:** `TestIntegration / Storage backend ownership API / persists a credential-free CSP-managed backend and enforces immutable ownership` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/fulfillment-service/it/it_storage_backend_ownership_test.go#L107)).
- **Selector:** Use the installer fulfillment suite with `FULFILLMENT_GINKGO_ARGS` set to an exact focus for Ginkgo spec `Storage backend ownership API / persists a credential-free CSP-managed backend and enforces immutable ownership` in the service-only phase.

**Preconditions.** Use the authenticated private API in isolated Kind and a synthetic NetApp backend with CSP ownership.

1. Register the backend with no endpoint or credentials.
2. Update its description and Get it again.

**Expected results.** Get returns CSP-managed ownership, the changed description, and no endpoint or credentials.

#### TC-NA-02: Shared CSP readiness records one class per configured tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CSP class readiness](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L22)
- **Dependencies:** Real envtest Kubernetes API and etcd with synthetic StorageClasses. Catalog replies, provisioning clients and the event recorder are test doubles; no external provider.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CSP-managed storage (pure cspManaged flow) / should set StorageReady=True, clear stale OSAC status/conditions, and trigger zero AAP jobs when all csp-managed StorageClasses exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3765)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CSP-managed storage \(pure cspManaged flow\) should set StorageReady=True, clear stale OSAC status/conditions, and trigger zero AAP jobs when all csp-managed StorageClasses exist$'` from `osac-operator` in OSAC.

**Preconditions.** Seed two CSP-managed catalog tiers and exactly one eligible StorageClass for each. Use the shared CSP resolver with the test's generic CSP backend fixture.

1. Reconcile initial storage for the synthetic Tenant.
2. Read StorageReady, the tier-to-class map and the provider recorder.

**Expected results.** StorageReady=True with both exact class mappings. No OSAC provider job is submitted.

#### TC-NA-03: Shared CSP readiness identifies every missing tier

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Missing-tier diagnostics](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L23)
- **Dependencies:** Real envtest Kubernetes API and etcd with synthetic StorageClasses. Catalog replies, provisioning clients and the event recorder are test doubles; no external provider.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CSP-managed storage (pure cspManaged flow) / should set StorageReady=False with NotFound and emit MissingStorageTier events when 1-of-2 or 0-of-2 csp-managed StorageClasses are missing` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L3899)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CSP-managed storage \(pure cspManaged flow\) should set StorageReady=False with NotFound and emit MissingStorageTier events when 1-of-2 or 0-of-2 csp-managed StorageClasses are missing$'` from `osac-operator` in OSAC.

**Preconditions.** Seed two CSP-managed tiers for the shared CSP resolver. Use one fixture with no eligible classes and one with only the gold class.

1. Reconcile each initial Tenant.
2. Compare StorageReady and the recorded missing-tier warnings.

**Expected results.** Both are StorageReady=False/NotFound. The first warns for both tiers and the second only for silver.

#### TC-NA-04: VM boots and uses its selected NetApp FC tiers

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Boot and additional disks on qualified FC storage](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L26)
- **Dependencies:** Real deployed VMaaS, AAP, Kubernetes, Trident and a dedicated qualified NetApp FC fixture. No customer storage or provider doubles.
- **Gap:** Tenant storage E2E verifies class readiness; no corresponding NetApp FC boot and data I/O assertion was verified.

**Preconditions.** Use a dedicated qualified FC target with precreated separate boot and data tier classes.

1. Create a VM using the two selected tiers.
2. Verify the selected volume classes and read/write benign fixture data.

**Expected results.** The VM boots from the selected boot tier and the data disk binds to its tier and returns the fixture data.

#### TC-NA-05: NetApp preview fixture offers only the qualified FC tiers

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Excluded preview transports](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L43)
- **Dependencies:** Deployed VMaaS catalog, qualified NetApp FC fixture and synthetic user account. No backend double.
- **Gap:** The NetApp role capability test checks block and VMaaS metadata. Canonical deployed storage tests do not verify the preview's exact FC offer catalog.

**Preconditions.** Prepare a deployed preview catalog with an isolated qualified FC offer and an unqualified non-FC candidate.

1. Inspect the NetApp VMaaS offerings presented by the configured catalog.
2. Compare them with the operator's supported fixture offer set.

**Expected results.** The advertised NetApp offers contain only the qualified FC tiers.

#### TC-NA-06: StorageClass access failure leaves initial shared CSP onboarding incomplete

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Target access failures and retry](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L24)
- **Dependencies:** Real envtest hub API and etcd. The remote client, authorization result and CSP catalog are test doubles. No external appliance.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / Remote cluster StorageClass target selection / should fail closed without falling back to local StorageClasses when remote StorageClass List returns Forbidden, and preserve latched readiness on later Forbidden errors` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L5947)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller Remote cluster StorageClass target selection should fail closed without falling back to local StorageClasses when remote StorageClass List returns Forbidden, and preserve latched readiness on later Forbidden errors$'` from `osac-operator` in OSAC.

**Preconditions.** Use the shared CSP reconciler with a synthetic remote StorageClass and a remote client double that can return Forbidden. A local class for the same tier is also present.

1. Reconcile with the scripted access failure.
2. Restore the scripted List access and reconcile again.

**Expected results.** The first result returns Forbidden with no resolved class or readiness condition. The second resolves the remote class and stores StorageReady=True.

#### TC-NA-07: NetApp offboarding preserves CSP-owned shared resources

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [CSP storage ownership on offboarding](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L27)
- **Dependencies:** Requires dedicated deployed VMaaS and preconfigured NetApp FC fixture with read access to shared-resource identities.
- **Gap:** Pure-CSP controller Envtest checks zero deprovision submissions and finalizer release using a generic fixture. No deployed NetApp shared-resource preservation assertion was verified in storage or VMaaS E2E.

**Preconditions.** Use a deployed NetApp FC fixture with shared SVM, TridentBackendConfig and StorageClass. Record the fixture resource identities before offboarding.

1. Offboard one synthetic tenant and wait for its resources to clear.
2. Compare the shared resource identities before and after.

**Expected results.** The tenant's resources are removed and shared SVM, TridentBackendConfig and StorageClass identities are unchanged.

#### TC-NA-08: CSP-owned FC block tier registers with its backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [FC block tier registration](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L21)
- **Dependencies:** Real Kind Kubernetes, deployed fulfillment services and PostgreSQL. The suite seeds backend prerequisites; provider reconciliation is outside the assertion.
- **Gap:** Kind verifies NetApp backend registration separately. No FC tier association assertion was verified.

**Preconditions.** Register the credential-free CSP-managed NetApp backend in the private fixture.

1. Create an eligible FC block tier referencing the backend.
2. Get it using its ID and inspect association.

**Expected results.** The tier is stored as a block offering with the exact backend association. This procedure checks catalog registration.

#### TC-NA-09: ComputeInstance hands only the requested NetApp class to provisioning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Requested VM disk tier selection](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L26)
- **Dependencies:** Real envtest Kubernetes API and etcd. AAP and catalog are test doubles. No Trident or FC I/O.
- **Execution:** `osac-operator/internal/controller/computeinstance_controller_test.go`
- **Evidence:** `TestControllers / ComputeInstance Controller / CSP-managed and mixed CSP/OSAC storage provisioning (OSAC-6596) / should provision a pure-CSP NetApp ComputeInstance with filtered tenant_storage_classes and no JIT tier definitions or backend connections` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/computeinstance_controller_test.go#L1484)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^ComputeInstance Controller CSP-managed and mixed CSP/OSAC storage provisioning \(OSAC-6596\) should provision a pure-CSP NetApp ComputeInstance with filtered tenant_storage_classes and no JIT tier definitions or backend connections$'` from `osac-operator` in OSAC.

**Preconditions.** Seed a ready Tenant with resolved gold and silver NetApp classes. Use a ComputeInstance requesting only gold for boot.

1. Reconcile with the NetApp catalog fixtures and record the job inputs.

**Expected results.** One provisioning request includes only the gold class, with no JIT tier definitions or backend connections.

#### TC-NA-10: Duplicate shared CSP classes produce one ambiguity warning

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [Duplicate class diagnostics](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L23)
- **Dependencies:** Real envtest Kubernetes API and etcd with synthetic StorageClasses. Catalog replies, provisioning clients and the event recorder are test doubles; no external provider.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CSP-managed storage (pure cspManaged flow) / should set StorageReady=False with MultipleFound and emit DuplicateStorageClass event without MissingStorageTier when duplicate csp-managed SCs exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L4007)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CSP-managed storage \(pure cspManaged flow\) should set StorageReady=False with MultipleFound and emit DuplicateStorageClass event without MissingStorageTier when duplicate csp-managed SCs exist$'` from `osac-operator` in OSAC.

**Preconditions.** Use the shared CSP fixture with two matching StorageClasses for gold.

1. Reconcile initial Tenant storage and read its readiness and warning events.

**Expected results.** StorageReady=False/MultipleFound with one DuplicateStorageClass event and no MissingStorageTier event.

#### TC-NA-11: CSP-only offboarding releases the finalizer without scheduling provider cleanup

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [CSP storage ownership on offboarding](https://github.com/osac-project/enhancement-proposals/blob/8065d527d9a113c00eb10dea3af95f3d5524ee72/enhancements/OSAC-5813-netapp-storage/prd.md#L27)
- **Dependencies:** Real envtest Kubernetes API and etcd with synthetic StorageClasses. Catalog replies, provisioning clients and the event recorder are test doubles; no external provider.
- **Execution:** `osac-operator/internal/controller/storage_controller_test.go`
- **Evidence:** `TestControllers / Storage Controller / CSP-managed storage (pure cspManaged flow) / should remove storage finalizer immediately on handleDelete without triggering deprovision jobs for pure-CSP and deleted-CSP-tier tenants` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-operator/internal/controller/storage_controller_test.go#L4243)).
- **Selector:** `go test ./internal/controller -run '^TestControllers$' -ginkgo.focus='^Storage Controller CSP-managed storage \(pure cspManaged flow\) should remove storage finalizer immediately on handleDelete without triggering deprovision jobs for pure-CSP and deleted-CSP-tier tenants$'` from `osac-operator` in OSAC.

**Preconditions.** Use the shared CSP reconciler with a synthetic tenant and its CSP-owned class. Configure provider doubles with a deprovision recorder.

1. Delete the tenant and reconcile.
2. Check the recorded deprovision calls and Tenant finalizer if the resource still exists.

**Expected results.** No provider deprovision job is submitted; the storage finalizer is released or the Tenant is already absent.
