# Testplan — OSAC-7308

## Overview

- **Feature:** OSAC-7305 — VMaaS Networking with Per-Tenant VM Clusters
- **Total test cases:** 39
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 9 of 9

Tiers follow [`docs/INTEGRATION-TESTING.md`](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md).
Implementation-owned cases are `[DEV]`; deployed cross-component user journeys are
`[QE]`.

## Test Case Index

| ID | Scenario | IC | Priority | Tier | Owner |
|----|----------|----|----------|------|-------|
| TC-R1-01 | Day-2 `WorkloadCluster` registration engages the cluster and hosts a VM without an operator restart | IC-6 | critical | E2E | [QE] |
| TC-R1-02 | Removing a `WorkloadCluster` disengages the cluster and stops its watches | IC-6 | high | E2E | [QE] |
| TC-R1-03 | Adding a VM-hosting cluster needs no `NetworkClass` change | IC-2 | high | E2E | [QE] |
| TC-R1-04 | Resources that must stay on the management cluster never land on a VM-hosting cluster | IC-6 | high | component-integration | [DEV] |
| TC-R2-01 | A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation | IC-1 | critical | E2E | [QE] |
| TC-R2-02 | Each unmet prerequisite reports its own reason and names the object (parameterized) | IC-1 | high | E2E | [QE] |
| TC-R2-03 | `prepare-vm-cluster` is idempotent across re-runs | IC-8 | medium | component-integration | [DEV] |
| TC-R2-04 | The networking instance group mounts one kubeconfig key per registered cluster | IC-7 | high | component-integration | [DEV] |
| TC-R2-05 | A freshly prepared cluster whose advertisement is `ConfigurationPending` is assignable | IC-1 | critical | E2E | [QE] |
| TC-R2-06 | Preparation waits for each node's BGP session and fails when one is not established | IC-8 | medium | component-integration | [DEV] |
| TC-R3-01 | Tenant created with an assignment places its default networking and VM namespace on that cluster only | IC-2 | critical | E2E | [QE] |
| TC-R3-02 | Two tenants assigned to different clusters each land on their own cluster | IC-2 | high | E2E | [QE] |
| TC-R4-01 | No tenant-facing response exposes the cluster identity | IC-3 | critical | E2E | [QE] |
| TC-R4-02 | A tenant cannot set or change the target cluster through the API | IC-3 | high | component-integration | [DEV] |
| TC-R5-01 | Assigning an unprepared cluster is rejected naming the cluster and prerequisite | IC-2 | critical | component-integration | [DEV] |
| TC-R5-02 | Assigning a nonexistent cluster is rejected naming it | IC-2 | high | component-integration | [DEV] |
| TC-R5-03 | Assigning a `WorkloadCluster` that is being removed is rejected | IC-2 | medium | component-integration | [DEV] |
| TC-R5-04 | A tenant with no recorded target is rejected | IC-2 | medium | component-integration | [DEV] |
| TC-R5-05 | A recorded target survives registering another cluster | IC-2 | high | component-integration | [DEV] |
| TC-R5-06 | Assigning a cluster without the `vmaas` capability is rejected | IC-2 | medium | component-integration | [DEV] |
| TC-R6-01 | Removing a cluster with an assigned tenant is rejected | IC-2 | critical | component-integration | [DEV] |
| TC-R6-02 | A removed cluster is no longer assignable | IC-2 | high | component-integration | [DEV] |
| TC-R7-01 | A VM on its assigned cluster attaches, receives an IPv4, and reports network readiness | IC-4 | critical | E2E | [QE] |
| TC-R7-02 | Tenant defaults resolve on the assigned cluster | IC-5 | high | E2E | [QE] |
| TC-R7-03 | Namespace, CUDN, and SecurityGroup policies are created on the assigned cluster while the Subnet CR stays on the hub | IC-5 | critical | E2E | [QE] |
| TC-R7-04 | Deleting the VM keeps shared tenant networking; deleting the tenant removes it | IC-3 | high | E2E | [QE] |
| TC-R7-05 | Annotation copy, `cluster.id`, and attachment namespace validation use the CR's target | IC-3 | high | Envtest | [DEV] |
| TC-R7-06 | `cudn_evpn` splits hub reads from target applies and fails when `cluster` is absent | IC-5 | medium | Contract | [DEV] |
| TC-R8-01 | Pool-allocated external access works for a VM on its assigned cluster | — | high | E2E | [QE] |
| TC-R9-01 | Two tenants on the same cluster cannot reach each other's networks | IC-5 | critical | E2E | [QE] |
| TC-R9-02 | Cross-tenant Subnet and SecurityGroup references are rejected | IC-5 | high | E2E | [QE] |
| TC-R10-01 | With provider networking disabled a VM provisions without a tenant address or network task | — | critical | E2E | [QE] |
| TC-R10-02 | A cluster reports `TenantNetworkingReady=True/ProvisioningDisabled` when networking is disabled | IC-1 | high | Envtest | [DEV] |
| TC-R11-01 | A prerequisite removed after assignment fails provisioning with a named diagnostic | IC-9 | critical | E2E | [QE] |
| TC-R11-02 | An unreachable cluster retries and never falls back to the management cluster | IC-6 | high | E2E | [QE] |
| TC-R11-03 | Restoring the prerequisite lets the retry succeed with no tenant action | IC-9 | high | E2E | [QE] |
| TC-R12-01 | A single-cluster fresh installation with no assignment behaves as today | IC-8 | critical | E2E | [QE] |
| TC-R12-02 | The baseline VMaaS networking suite passes unchanged on a single-cluster installation | IC-8 | critical | E2E | [QE] |
| TC-R12-03 | A tenant with no recorded target is rejected in the two-cluster first-increment shape | IC-2 | critical | component-integration | [DEV] |

## Test Cases

### R-1: Clusters that run tenant VMs are registered at installation or later, with the management cluster registered like any other

##### Shared Preconditions

- Two OpenShift clusters with `cluster-admin` access: `main` running OSAC, and `vw2` reachable from `main`.
- Provider networking enabled (`global.networking.provisioningEnabled=true`).
- `vw2` prepared with `make prepare-vm-cluster HUB_NAME=vw2 VM_KUBECONFIG=... EVPN_VALUES=...`.
- Private API access token for the fulfillment API.

#### TC-R1-01: Day-2 `WorkloadCluster` registration engages the cluster and hosts a VM without an operator restart

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | critical | E2E | [QE] | automated |

**Steps:** 1. Record the operator pod UID and restart count → 2. Create `WorkloadCluster` `vw2` with the `vmaas` capability and its kubeconfig → 3. Wait for `TenantNetworkingReady=True` → 4. Create a tenant assigned to `vw2` and a VM on its default Subnet → 5. Read the VM from `vw2` and the operator pod UID

**Expected:** The operator pod UID and restart count are unchanged; `kubectl --kubeconfig vw2 get secret,vmi -A` shows the tenant namespace `osac-vn-<id>` and a `VirtualMachineInstance` whose address is reported by `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address`; `ComputeInstance.status.conditions[NetworkReady].status` is `"True"`.

#### TC-R1-02: Removing a `WorkloadCluster` disengages the cluster and stops its watches

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | E2E | [QE] | automated |

##### Additional Preconditions

- `WorkloadCluster` `vw2` registered, ready, and with no assigned tenant.

**Steps:** 1. Remove `vw2` through the placement foundation → 2. Read the operator's engaged clusters and caches → 3. Create a `VirtualMachine` directly on `vw2` in a tenant namespace and observe the operator for two reconcile intervals

**Expected:** The operator no longer has a client or cache for `vw2`; the operator logs no reconcile for `vw2` and the hand-created `VirtualMachine` is left untouched; a tenant still assigned to `vw2` would have blocked the removal (TC-R6-01).

#### TC-R1-03: Adding a VM-hosting cluster needs no `NetworkClass` change

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | E2E | [QE] | automated |

##### Additional Preconditions

- A fresh installation with one `Hub` (`hub`) and a `NetworkClass` that names no cluster.

**Steps:** 1. Record the `NetworkClass` `metadata.generation`, `spec`, and `resourceVersion` → 2. Register `WorkloadCluster` `vw1` and wait for its condition → 3. Create a tenant assigned to `vw1` and a VM → 4. Re-read the `NetworkClass`

**Expected:** The `NetworkClass` is unchanged (same `resourceVersion`); `status.hub` still names `hub` and `status.state` stays `READY`; the tenant's `VirtualNetwork` and `Subnet` are created on `main` and the VM runs on `vw1`.

#### TC-R1-04: Resources that must stay on the management cluster never land on a VM-hosting cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | component-integration | [DEV] | automated |

##### Additional Preconditions

- `main` and one VM-hosting cluster `vw1` are registered; `vw1` has no OSAC CRDs.

**Steps:** 1. Create a `ComputeInstance` with no network attachment, a `Volume`, a `ClusterOrder`, and a `BareMetalInstance` → 2. Resolve each one's target cluster through the placement path → 3. List OSAC CRs on `vw1`

**Expected:** Every one of those resources targets the management cluster or fails with a named placement error; `kubectl --kubeconfig vw1 get computeinstances,volumes,clusterorders,baremetalinstances -A` returns no resources; no request reaches `vw1`'s API server for an OSAC CRD.

### R-2: Each VM-hosting cluster is prepared for tenant networking once, when registered, with no per-tenant or per-VM setup

##### Shared Preconditions

- `main` running OSAC with provider networking enabled.
- A `vw1` cluster prepared with `make prepare-vm-cluster HUB_NAME=vw1 VM_KUBECONFIG=... EVPN_VALUES=...`.

#### TC-R2-01: A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | critical | E2E | [QE] | automated |

**Steps:** 1. Read `WorkloadCluster` `vw1`'s condition → 2. Create tenant `t1` assigned to `vw1` with a VM → 3. Create tenant `t2` assigned to `vw1` with a VM → 4. Re-read the condition

**Expected:** Step 1 reports the condition type `TenantNetworkingReady`, status `"True"`, reason `AwaitingFirstNetwork` while no CUDN exists yet; once the first tenant's default networking is ready the reason becomes `PrerequisitesMet` and stays there; both VMs reach `Ready` with a tenant IPv4 address; no preparation command or job ran against `vw1` during tenant creation for `t2` (job list filtered by the cluster shows only per-tenant tasks).

#### TC-R2-02: Each unmet prerequisite reports its own reason and names the object (parameterized)

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | high | E2E | [QE] | automated |

##### Additional Preconditions

- `WorkloadCluster` `vw1` registered and reachable; exactly one prerequisite is removed per row.

##### Steps

1. Remove or degrade `{prerequisite}` on `vw1`.
2. Wait for the probe interval (five minutes) and read `WorkloadCluster` `vw1` `status.conditions`.
3. Compare `{reason}` and the message.

##### Expected Results

| Prerequisite | Expected Result |
|--------------|-----------------|
| `VTEP tenant-vtep` set to `Accepted=False` | `TenantNetworkingReady=False`, reason `VTEPNotAccepted`, message contains `vw1` and `tenant-vtep` |
| `RouteAdvertisements osac-evpn` set to `Accepted=False` **with a CUDN present** | `TenantNetworkingReady=False`, reason `RouteAdvertisementsNotAccepted`, message contains `osac-evpn` |
| `clusteruserdefinednetworks.k8s.ovn.org` CRD absent | `TenantNetworkingReady=False`, reason `CUDNNotAvailable`, message contains `clusteruserdefinednetwork` |
| `HyperConverged Available=False` | `TenantNetworkingReady=False`, reason `VirtualizationNotAvailable`, message contains `HyperConverged` |
| Credential revoked | `TenantNetworkingReady=False`, reason `KubeconfigRejected` or `ClusterUnreachable`, message names `vw1` and contains no token |

#### TC-R2-03: `prepare-vm-cluster` is idempotent across re-runs

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-8 | medium | component-integration | [DEV] | automated |

**Steps:** 1. Run `make prepare-vm-cluster HUB_NAME=vw1 VM_KUBECONFIG=... EVPN_VALUES=...` → 2. Capture object `resourceVersion`s for the VTEP, `RouteAdvertisements`, `FRRConfiguration`, and the `osac-remote-access` service account → 3. Run the same command again

**Expected:** Both runs exit 0; the second run changes no object (`resourceVersion` values are identical) and prints no error; `WorkloadCluster` `vw1` `TenantNetworkingReady` stays `"True"`.

#### TC-R2-04: The networking instance group mounts one kubeconfig key per registered cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-7 | high | component-integration | [DEV] | automated |

##### Additional Preconditions

- Two `WorkloadCluster` records with the `vmaas` capability: `vw1`, `vw2`.

**Steps:** 1. Read the networking instance group's mounted Secret keys → 2. Launch any Kubernetes Manager task on `vw2` and inspect the job pod environment → 3. Compare the mounted key names with the `cluster.id` value

**Expected:** The Secret has exactly one key per registered VM-hosting cluster, named after the cluster; the job pod mounts the Secret read-only and its environment contains no kubeconfig content (`printenv` shows no cluster token); the task's `osac_job_vars.cluster.id` equals `vw2` and matches a mounted key.

#### TC-R2-05: A freshly prepared cluster whose advertisement is `ConfigurationPending` is assignable

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- `vw1` freshly prepared; no CUDN exists on it; `RouteAdvertisements osac-evpn` reports `ConfigurationPending`.

**Steps:** 1. Register `WorkloadCluster` `vw1` → 2. Read its condition → 3. Create tenant `t1` assigned to `vw1` → 4. Create a VM on its default Subnet → 5. Re-read the condition and the advertisement

**Expected:** Step 2 reports `TenantNetworkingReady=True` with reason `AwaitingFirstNetwork`; step 3 succeeds; after the CUDN exists the advertisement becomes `Accepted=True` and the condition reason becomes `PrerequisitesMet`; the VM reaches `Ready` with a tenant IPv4 address.

#### TC-R2-06: Preparation waits for each node's BGP session and fails when one is not established

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-8 | medium | component-integration | [DEV] | automated |

##### Additional Preconditions

- `evpn.bgp.waitForEstablished=true` (the default); the fabric side of the peering is not configured for one node.

**Steps:** 1. Run `make prepare-vm-cluster` against `vw1` → 2. Observe the hook's exit status and stderr → 3. Configure the fabric peer and re-run

**Expected:** Step 1 exits non-zero with a message naming the node and peer address, after listing the BGP session states; no `Accepted=True` advertisement is reported for that node; step 3 exits 0 and every session is `Established`.

### R-3: The Cloud Provider Admin assigns one registered cluster per tenant at creation, and all of that tenant's VMs run there

##### Shared Preconditions

- `main` running OSAC with provider networking enabled.
- Two prepared `WorkloadCluster` records: `vw1` and `vw2`.

#### TC-R3-01: Tenant created with an assignment places its default networking and VM namespace on that cluster only

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | E2E | [QE] | automated |

**Steps:** 1. Create tenant `t1` assigned to `vw2` → 2. Wait for `Tenant.status.conditions[DefaultNetworkingReady].status == "True"` → 3. Read `t1`'s default `VirtualNetwork` ID and check for that specific `osac-vn-<id>` namespace on `vw1`, `vw2`, and `main` → 4. Create a VM on `t1`'s default Subnet

**Expected:** `osac-vn-<id>` for `t1`'s default VirtualNetwork exists on `vw2` only; that same namespace is absent from `vw1` and `main` (other tenants' namespaces there are ignored); the `VirtualMachineInstance` is `Running` on `vw2` and absent from `vw1`; `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address` is non-empty.

#### TC-R3-02: Two tenants assigned to different clusters each land on their own cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | E2E | [QE] | automated |

**Steps:** 1. Create tenant `t1` assigned to `vw1` and tenant `t2` assigned to `vw2` → 2. Create one VM for each → 3. Read the `osac.openshift.io/vm-cluster` annotation from each `ComputeInstance`, `VirtualNetwork`, `Subnet`, `SecurityGroup`, and `NetworkAttachment`

**Expected:** Every `t1` CR carries `osac.openshift.io/vm-cluster: vw1` and every `t2` CR carries `vw2`; `t1`'s `osac-vn-<id>` namespace exists only on `vw1` and `t2`'s only on `vw2`; both VMs are `Ready` with distinct addresses.

### R-4: Assignment is provider-side administration; tenants neither choose nor see the hosting cluster, and it cannot change

##### Shared Preconditions

- Two prepared `WorkloadCluster` records, `vw1` and `vw2`.
- Tenant `t1` assigned to `vw1` with one VM.
- Tenant-scoped API credentials for `t1`.

#### TC-R4-01: No tenant-facing response exposes the cluster identity

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | critical | E2E | [QE] | automated |

**Steps:** 1. As `t1`, call `Tenants.Get`, `ComputeInstances.List`, `Subnets.List`, `VirtualNetworks.List`, `SecurityGroups.List`, and `NetworkAttachments.List` → 2. Serialize each response to JSON → 3. Search for `vw1`, `vw2`, `hub`, `kubeconfig`, `vm-cluster`, and `workloadcluster`

**Expected:** No response contains any of the searched strings; no response schema exposes a cluster, hub, or placement field; error messages reference only tenant-owned identifiers.

#### TC-R4-02: A tenant cannot set or change the target cluster through the API

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | high | component-integration | [DEV] | automated |

**Steps:** 1. As `t1`, attempt `ComputeInstances.Create` with metadata annotation `osac.openshift.io/vm-cluster: vw2` → 2. As a provider admin, `Patch` the annotation on the existing `ComputeInstance` to `vw2` → 3. Read the stored annotation and the `VirtualMachineInstance` location

**Expected:** Step 1 either rejects the request or stores `vw1`; the stored annotation after step 3 is `vw1`; the `VirtualMachineInstance` remains on `vw1`; no new object appears on `vw2`.

### R-5: An unprepared or removed cluster cannot be assigned, and the rejection names the cluster and the unmet prerequisite

##### Shared Preconditions

- `WorkloadCluster` `vw1` prepared and ready; `vw3` registered with `VTEP tenant-vtep` `Accepted=False`.

#### TC-R5-01: Assigning an unprepared cluster is rejected naming the cluster and prerequisite

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | component-integration | [DEV] | automated |

**Steps:** 1. `Tenants.Create` with the assignment set to `vw3` → 2. Read the error code and message → 3. `Tenants.List`

**Expected:** The call returns `InvalidArgument`; the message contains `vw3` and `tenant-vtep`; no tenant record is created (`Tenants.List` total is unchanged and the new tenant name returns `NotFound`).

#### TC-R5-02: Assigning a nonexistent cluster is rejected naming it

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | component-integration | [DEV] | automated |

**Steps:** 1. `Tenants.Create` with the assignment set to `vw-missing` → 2. Read the error

**Expected:** The call returns `InvalidArgument` and the message contains `vw-missing` and the word `not found`.

#### TC-R5-03: Assigning a `WorkloadCluster` that is being removed is rejected

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | medium | component-integration | [DEV] | automated |

##### Additional Preconditions

- `WorkloadCluster` `vw4` registered, ready, and with no assigned tenant.

**Steps:** 1. Start removing `vw4` through the placement foundation → 2. Before the removal completes, `Tenants.Create` with the assignment set to `vw4`

**Expected:** The create returns `InvalidArgument` with a message containing `vw4` and stating the cluster is being removed; after the removal completes, a repeated create also returns `InvalidArgument`.

#### TC-R5-04: A tenant with no recorded target is rejected

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | medium | component-integration | [DEV] | automated |

##### Additional Preconditions

- `vw1` and `vw2` both registered and ready, and the placement foundation records no target for the new tenant.

**Steps:** 1. `Tenants.Create` without a target → 2. Read the error → 3. Repeat with one cluster registered and still no recorded target

**Expected:** Both calls return `InvalidArgument` with a message stating that no VM cluster is assigned to the tenant; no CR for the tenant is created on either cluster and no cluster is chosen by counting registrations.

#### TC-R5-05: A recorded target survives registering another cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | component-integration | [DEV] | automated |

##### Steps

1. With one registered cluster `vw1`, create tenant `t1` with no explicit target; the foundation records `vw1`.
2. Register `WorkloadCluster` `vw2`.
3. Create a VM for `t1`.
4. Read `t1`'s stored target and the new CRs' annotation.

##### Expected Results

- Step 1 succeeds and `t1` stores `vw1` as its target.
- Step 3 succeeds; every new CR carries `osac.openshift.io/vm-cluster: vw1`; no CR or task targets `vw2`.
- Step 4 shows the stored target unchanged; creating another tenant still requires an explicit target from the foundation.

#### TC-R5-06: Assigning a cluster without the `vmaas` capability is rejected

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | medium | component-integration | [DEV] | automated |

##### Additional Preconditions

- `WorkloadCluster` `vw6` registered and prepared, with `spec.supported_workloads` set to `["maas"]` only.

**Steps:** 1. `Tenants.Create` with the assignment set to `vw6` → 2. Read the error code and message → 3. Add `vmaas` to `vw6`'s capabilities and repeat the create

**Expected:** Step 1 returns `InvalidArgument` with a message naming `vw6` and the missing `vmaas` capability, and no tenant record is created; step 3 succeeds and the tenant's CRs carry `vw6`.

### R-6: A cluster is removed from VM hosting only when no tenant is assigned, and a removed cluster cannot be assigned

##### Shared Preconditions

- `WorkloadCluster` `vw1` prepared and ready; `WorkloadCluster` `vw5` prepared and ready.

#### TC-R6-01: Removing a cluster with an assigned tenant is rejected

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | component-integration | [DEV] | automated |

##### Additional Preconditions

- Tenant `t1` assigned to `vw5`.

**Steps:** 1. Remove `vw5` through the placement foundation → 2. Read the error code and message → 3. Read `vw5`

**Expected:** The call returns `FailedPrecondition`; the message states that tenants are assigned and includes the count `1`; `vw5` still exists with no deletion timestamp, and `t1`'s networking is unaffected (`DefaultNetworkingReady` stays `"True"`).

#### TC-R6-02: A removed cluster is no longer assignable

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | component-integration | [DEV] | automated |

##### Steps

1. Remove `vw5` (no tenant assigned, no cleanup outstanding).
2. Read `vw5` and `Tenants.Create` with the target set to `vw5`.

##### Expected Results

- Step 1 returns success and `vw5` then returns `NotFound`.
- Step 2's create returns `InvalidArgument` naming `vw5`, and no CR is created for the tenant.

### R-7: With provider networking enabled, a VM on its assigned cluster attaches to one Subnet and its SecurityGroups, receives its tenant IPv4, and reports network readiness before ready

##### Shared Preconditions

- Tenant `t1` assigned to `vw1`, whose default networking is `Ready`.
- The provider's Netris fabric is reachable and `RouteAdvertisements osac-evpn` is `Accepted=True` (or `AwaitingFirstNetwork` before the first CUDN).

#### TC-R7-01: A VM on its assigned cluster attaches, receives an IPv4, and reports network readiness

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-4 | critical | E2E | [QE] | automated |

**Steps:** 1. Create a VM with an explicit Subnet and SecurityGroup → 2. Stream `ComputeInstance` status → 3. Read the `VirtualMachineInstance` from `vw1` → 4. Check the order of the conditions

**Expected:** `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address` is a non-empty IPv4 address inside the Subnet CIDR; `status.conditions[NetworkReady].status == "True"`; `status.phase` becomes `Ready` only after `NetworkReady` is `True`; the `VMI` has interface address equal to the reported IPv4; the provision job recorded `osac_job_vars.cluster.id == "vw1"` and the networking job recorded the same value.

#### TC-R7-02: Tenant defaults resolve on the assigned cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | high | E2E | [QE] | automated |

**Steps:** 1. Create a VM with no Subnet and no SecurityGroups → 2. Read the resulting `NetworkAttachment` spec and the VM status

**Expected:** The `NetworkAttachment` references the tenant's default Subnet ID and default SecurityGroup ID, and carries the `osac.openshift.io/vm-cluster` annotation of the `ComputeInstance`; the VM receives an IPv4 address from the default Subnet CIDR; `NetworkReady` is `"True"`; no `InvalidArgument` is returned.

#### TC-R7-03: Namespace, CUDN, and SecurityGroup policies are created on the assigned cluster while the Subnet CR stays on the hub

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | critical | E2E | [QE] | automated |

**Steps:** 1. Create a tenant VirtualNetwork with two Subnets and a SecurityGroup with one ingress rule → 2. Run on `vw1`: `get namespace osac-vn-<id>`, `get cudn osac-vn-<id>`, and `get networkpolicy -n osac-vn-<id>` → 3. Repeat the three reads with `--kubeconfig main` and `--kubeconfig vw2` → 4. Read the owner Subnet CR from `main`

**Expected:** On `vw1` the namespace carries `k8s.ovn.org/primary-user-defined-network: ""`, annotations `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference`, the CUDN has `transport: EVPN`, `vni` route targets `0:<l2_vni>` and `0:<l3_vni>`, and the `osac-sg-<id>` policy exists; on `main` and `vw2` all three reads return `NotFound`; the owner Subnet CR exists on `main` and the second Subnet completes without an orphaned-network failure.

#### TC-R7-04: Deleting the VM keeps shared tenant networking; deleting the tenant removes it

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | high | E2E | [QE] | automated |

##### Steps

1. Delete the VM and wait for the `ComputeInstance` to disappear.
2. Read the tenant namespace, CUDN, and policies on `vw1`, and the tenant's default VirtualNetwork and Subnet.
3. Delete tenant `t1` and wait for its networking resources to be removed.
4. Re-read the namespace, CUDN, and policies on `vw1`.

##### Expected Results

- After step 2, no `VirtualMachine`, `VirtualMachineInstance`, `pod`, or `DataVolume` labelled with the instance ID remains on `vw1`; the tenant's default VirtualNetwork namespace, CUDN, and SecurityGroup policies still exist; `Subnets.Get` for the default Subnet still returns `Ready`.
- After step 4, the tenant's namespace, CUDN, and SecurityGroup policies are gone from `vw1`; `Subnets.Get` returns `NotFound`.

#### TC-R7-05: Annotation copy, `cluster.id`, and attachment namespace validation use the CR's target

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | high | Envtest | [DEV] | automated |

**Steps:** 1. With a `ComputeInstance` annotated for `vw1`, reconcile it and read the created `NetworkAttachment` → 2. Run `ParseVMAttachment` with an accepted result naming a namespace that exists only on `vw1`'s (fake) target client → 3. Run the same result with no target client

**Expected:** Step 1's `NetworkAttachment` carries `osac.openshift.io/vm-cluster: vw1` copied from the `ComputeInstance`, and the operator writes no other value; step 2 validates the namespace and its tenant label through the target cluster's reader and accepts the result; step 3 rejects the result as final with a message naming the cluster, and never falls back to the local reader.

#### TC-R7-06: `cudn_evpn` splits hub reads from target applies and fails when `cluster` is absent

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | medium | Contract | [DEV] | automated |

**Steps:** 1. Run `create_subnet` with `cluster: {id: vw1}` and a sibling Subnet whose owner CR exists only on the hub fixture → 2. Run `create_subnet` with the target fixture rejecting writes → 3. Run `create_subnet` with no `cluster` key

**Expected:** Step 1 reads the owner Subnet CR from the hub and creates the CUDN on the target; step 2 fails `retryable: true` without writing to the hub; step 3 fails with a message naming the missing cluster and never applies to the job pod's cluster.

### R-8: External access for those VMs behaves as on the management cluster today

##### Shared Preconditions

- Tenant `t1` assigned to `vw1` with a running VM that has a tenant IPv4 address.
- An `ExternalIPPool` with spare capacity.

#### TC-R8-01: Pool-allocated external access works for a VM on its assigned cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| — | high | E2E | [QE] | automated |

**Steps:** 1. Create an `ExternalIP` without an explicit address → 2. Create an `ExternalIPAttachment` targeting the VM → 3. Reach the VM's SSH port from outside the tenant network → 4. Delete the attachment and then the `ExternalIP`

**Expected:** The `ExternalIP` is `ALLOCATED` with an address from the pool; the attachment reaches `READY`; the SSH connection succeeds and `whoami` on the VM returns the configured user; after step 4 both objects are gone and the fabric no longer answers on the released address; the AAP fabric tasks recorded no `osac_job_vars.cluster` key.

### R-9: Tenant isolation parity on every VM-hosting cluster

##### Shared Preconditions

- Tenants `t1` and `t2` both assigned to `vw1`, each with one VM.

#### TC-R9-01: Two tenants on the same cluster cannot reach each other's networks

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | critical | E2E | [QE] | automated |

**Steps:** 1. From `t1`'s VM, `ping -c 3` and `nc -z -w 3 <port>` `t2`'s VM address → 2. Read the `osac-sg-<id>` policies in both namespaces → 3. Read each namespace's pod selector

**Expected:** All packets to `t2`'s address are dropped (100% packet loss, connection times out); each namespace's baseline policy selects only pods of its own VirtualNetwork; `t1`'s SecurityGroup policy `podSelector` matches only `osac.openshift.io/compute-instance-id` of `t1`'s VM.

#### TC-R9-02: Cross-tenant Subnet and SecurityGroup references are rejected

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | high | E2E | [QE] | automated |

**Steps:** 1. As `t1`, create a VM referencing `t2`'s default Subnet ID → 2. As `t1`, create a VM referencing `t2`'s default SecurityGroup ID

**Expected:** Step 1 returns `InvalidArgument` or `NotFound` and no `ComputeInstance` is created; step 2 returns `InvalidArgument` or `NotFound` and no `ComputeInstance` is created; no CR is created on `vw1` for either attempt.

### R-10: The CI-only networking-disabled configuration keeps working

##### Shared Preconditions

- `main` with `global.networking.provisioningEnabled=false`.
- Tenant `t1` assigned to `vw1`.

#### TC-R10-01: With provider networking disabled a VM provisions without a tenant address or network task

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| — | critical | E2E | [QE] | automated |

**Steps:** 1. Create a VM → 2. Read `ComputeInstance.status` → 3. Read the `VirtualMachineInstance` from `vw1` → 4. List AAP jobs for the instance

**Expected:** `status.phase` becomes `Ready`; `status.conditions[NetworkReady]` is `"True"` with reason `ProvisioningDisabled`; `compute_network_attachment_statuses` is empty and no tenant IPv4 is reported; no `NetworkAttachment` CR exists; no `apply-network-attachment` or `create-subnet` job is listed for the instance; the `VirtualMachineInstance` runs in the tenant namespace on `vw1`.

#### TC-R10-02: A cluster reports `TenantNetworkingReady=True/ProvisioningDisabled` when networking is disabled

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | high | Envtest | [DEV] | automated |

**Steps:** 1. Register `WorkloadCluster` `vw1` while networking is disabled and the EVPN prerequisites are absent → 2. Read its `status.conditions` → 3. `Tenants.Create` with the target set to `vw1`

**Expected:** The condition is `"True"` with reason `ProvisioningDisabled`; the message states that provider networking is disabled; step 3 succeeds and the tenant's `DefaultNetworkingReady` reaches `"True"` with reason `ProvisioningDisabled`.

### R-11: If a cluster becomes unprepared after assignment, provisioning fails only when a networking prerequisite is unmet, with a named diagnostic

##### Shared Preconditions

- Tenant `t1` assigned to `vw1`, whose default networking is `Ready`, with one existing VM.
- Provider networking enabled.

#### TC-R11-01: A prerequisite removed after assignment fails provisioning with a named diagnostic

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-9 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- Set `RouteAdvertisements osac-evpn` to `Accepted=False` on `vw1` after the tenant is ready.

**Steps:** 1. Create a second VM on `t1` → 2. Wait for the `create-subnet` or `apply-network-attachment` job to fail → 3. Read `ComputeInstance.status.conditions[NetworkReady]`, the job entry message, and `WorkloadCluster` `status.conditions` → 4. Check `main` and `vw2` for any object of this VM

**Expected:** `NetworkReady` is `"False"` with a generic tenant-facing reason (`VmClusterNotReady`) whose message names no cluster; the job entry message contains `vw1` and `osac-evpn`; the `WorkloadCluster` condition names the cluster and the unmet prerequisite; the `ComputeInstance` does not reach `Ready`; no namespace, CUDN, policy, or `VirtualMachine` for this VM exists on `main` or `vw2`.

#### TC-R11-02: An unreachable cluster retries and never falls back to the management cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | E2E | [QE] | automated |

##### Additional Preconditions

- API access to `vw1` blocked for both the operator and the AAP job (for example by a `NetworkPolicy` on the job's egress and by revoking the operator's credential), not only for a background `curl`.

**Steps:** 1. Create a VM on `t1` → 2. Observe the `status.jobs` entry across two retry intervals → 3. Read `WorkloadCluster` `status.conditions` → 4. Confirm no job or object was created on `main` → 5. Restore access

**Expected:** The entry state is `Retrying` with a message containing a next-retry timestamp and an HTTP transport error; the retry cadence follows the existing backoff (two minutes, then four); the `WorkloadCluster` reports `TenantNetworkingReady=False` with reason `ClusterUnreachable`; `kubectl --kubeconfig main get vmi -A` shows no VM for the instance and no job targets `main`; after step 5 the retry succeeds.

#### TC-R11-03: Restoring the prerequisite lets the retry succeed with no tenant action

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-9 | high | E2E | [QE] | automated |

##### Preconditions

- State from TC-R11-01.

**Steps:** 1. Restore `RouteAdvertisements osac-evpn` to `Accepted=True` → 2. Wait for the retry → 3. Read the VM status and the cluster condition

**Expected:** Without any tenant action the entry reaches `Succeeded`; `NetworkReady` becomes `"True"`; the VM receives an IPv4 address and reaches `Ready`; the `WorkloadCluster` returns to `TenantNetworkingReady=True/PrerequisitesMet`; the public `NetworkReady` message stays generic.

### R-12: A fresh installation whose tenants are assigned to the management cluster behaves exactly as today

##### Shared Preconditions

- A fresh single-cluster installation where the management cluster is the only registered `WorkloadCluster` and the only `Hub`.
- No placement assignment for the tenants created during the test.

#### TC-R12-01: A single-cluster fresh installation with no assignment behaves as today

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-8 | critical | E2E | [QE] | automated |

**Steps:** 1. Create tenant `t1` with no explicit assignment → 2. Create a VM on its default Subnet → 3. Read the `WorkloadCluster` conditions and the CR annotations → 4. Delete the VM and the tenant

**Expected:** Step 1 succeeds because the foundation resolves the deployment's single target; the `WorkloadCluster` reports `TenantNetworkingReady=True`; `t1`'s `VirtualNetwork`, `Subnet`, `SecurityGroup`, `NetworkAttachment`, and `ComputeInstance` carry `osac.openshift.io/vm-cluster` naming that cluster; the VM receives an IPv4 address, reaches `Ready`, and appears on the management cluster; delete removes the VM namespace and keeps the tenant's default networking.

#### TC-R12-02: The baseline VMaaS networking suite passes unchanged on a single-cluster installation

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-8 | critical | E2E | [QE] | automated |

**Steps:** 1. Run the OSAC-1435 VMaaS networking acceptance suite against the single-cluster installation → 2. Compare results with the baseline recorded before this feature

**Expected:** Every case in the baseline suite passes with no modified expectation, including attachment, address reporting, network readiness ordering, external access, SecurityGroup rules, and dependency-safe cleanup; the case count equals the baseline count.

#### TC-R12-03: A tenant with no recorded target is rejected in the two-cluster first-increment shape

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | component-integration | [DEV] | automated |

##### Additional Preconditions

- The `install-multicluster` shape: management `Hub` plus one registered `WorkloadCluster`, with no placement foundation target for new tenants.

**Steps:** 1. `Tenants.Create` with no target → 2. Read the error → 3. Repeat after the foundation records the workload cluster as the tenant's target

**Expected:** Step 1 returns `InvalidArgument` stating that no VM cluster is assigned; the error does not select the management cluster and does not count registered clusters; step 3 succeeds and the tenant's CRs carry the workload cluster's name.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases. Volume placement, the console
proxy, storage status keys, and the compute/storage instance-group credentials are
out of scope for this design and are not covered here; their owning designs
(VMaaS, storage) carry that coverage.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 39 |
| Critical | 15 |
| High | 18 |
| Medium | 6 |
| Low | 0 |
| Automated | 38 |
| Manual | 0 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 9 / 9 |
