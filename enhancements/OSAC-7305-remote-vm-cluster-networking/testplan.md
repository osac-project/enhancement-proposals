# Testplan — OSAC-7308

## Overview

- **Feature:** OSAC-7305 — VMaaS Networking with Per-Tenant VM Clusters
- **Total test cases:** 34
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 10 of 10

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-R1-01 | Day-2 `Hub` registration engages the cluster and hosts a VM without an operator restart | IC-6 | critical |
| TC-R1-02 | Deleting a `Hub` disengages the cluster and stops its watches | IC-6 | high |
| TC-R1-03 | A second `Hub` registers once the control-object hub is named | IC-10 | high |
| TC-R2-01 | A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation | IC-1 | critical |
| TC-R2-02 | Each unmet prerequisite reports its own reason and names the object (parameterized) | IC-1 | high |
| TC-R2-03 | `prepare-vm-cluster` is idempotent across re-runs | IC-8 | medium |
| TC-R2-04 | The networking instance group mounts one kubeconfig key per registered cluster | IC-7 | high |
| TC-R3-01 | Tenant created with an assignment places its default networking and VM namespace on that cluster only | IC-2 | critical |
| TC-R3-02 | Two tenants assigned to different clusters each land on their own cluster | IC-2 | high |
| TC-R4-01 | No tenant-facing response exposes the cluster identity | IC-3 | critical |
| TC-R4-02 | A tenant cannot set or change the target cluster through the API | IC-3 | high |
| TC-R5-01 | Assigning an unprepared cluster is rejected naming the cluster and prerequisite | IC-2 | critical |
| TC-R5-02 | Assigning a nonexistent cluster is rejected naming it | IC-2 | high |
| TC-R5-03 | Assigning a `Hub` that is being deleted is rejected | IC-2 | medium |
| TC-R5-04 | Selecting from more than one cluster without an assignment is rejected | IC-2 | medium |
| TC-R6-01 | Deleting a `Hub` with an assigned tenant is rejected | IC-2 | critical |
| TC-R6-02 | A `Hub` with no assigned tenant deletes and becomes unassignable | IC-2 | high |
| TC-R7-01 | A VM on its assigned cluster attaches, receives an IPv4, and reports network readiness | IC-4 | critical |
| TC-R7-02 | Tenant defaults resolve on the assigned cluster | IC-5 | high |
| TC-R7-03 | Namespace, CUDN, and SecurityGroup policies are created on the assigned cluster | IC-5 | critical |
| TC-R7-04 | Deleting the VM removes the remote namespace and policies, keeping shared tenant networking | IC-3 | high |
| TC-R8-01 | Pool-allocated external access works for a VM on its assigned cluster | — | high |
| TC-R9-01 | Two tenants on the same cluster cannot reach each other's networks | IC-5 | critical |
| TC-R9-02 | Cross-tenant Subnet and SecurityGroup references are rejected | IC-5 | high |
| TC-R10-01 | With provider networking disabled a VM provisions without an address or network task | — | critical |
| TC-R10-02 | A cluster reports `TenantNetworkingReady=True/ProvisioningDisabled` when networking is disabled | IC-1 | high |
| TC-R11-01 | A prerequisite removed after assignment fails provisioning with a named diagnostic | IC-9 | critical |
| TC-R11-02 | An unreachable cluster retries and never falls back to the main cluster | IC-6 | high |
| TC-R11-03 | Restoring the prerequisite lets the retry succeed with no tenant action | IC-9 | high |
| TC-R12-01 | A single-`Hub` fresh installation with no assignment behaves as today | IC-8 | critical |
| TC-R12-02 | The baseline VMaaS networking suite passes unchanged on a single-cluster installation | IC-8 | critical |

## Test Cases

### R-1: Clusters that run tenant VMs are registered at installation or later, with the management cluster registered like any other

##### Shared Preconditions

- Two OpenShift clusters with `cluster-admin` access: `main` running OSAC, and `vw2` reachable from `main`.
- Provider networking enabled (`global.networking.provisioningEnabled=true`).
- `vw2` prepared with `make prepare-vm-cluster HUB_NAME=vw2 VM_KUBECONFIG=... EVPN_VALUES=...`.
- Private API access token for the fulfillment API.

#### TC-R1-01: Day-2 `Hub` registration engages the cluster and hosts a VM without an operator restart

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

**Steps:** 1. Record the operator pod UID and restart count → 2. Create `Hub` `vw2` through `Hubs.Create` with the `vw2` kubeconfig and namespace → 3. Wait for `Hub` `vw2` `TenantNetworkingReady=True` → 4. Create a tenant assigned to `vw2` and a VM on its default Subnet → 5. Read the VM from `vw2` and the operator pod UID

**Expected:** The operator pod UID and restart count are unchanged; `kubectl --kubeconfig vw2 get secret,vmi -A` shows the tenant namespace `osac-vn-<id>` and a `VirtualMachineInstance` whose address is reported by `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address`; `ComputeInstance.status.conditions[NetworkReady].status` is `"True"`.

#### TC-R1-02: Deleting a `Hub` disengages the cluster and stops its watches

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Additional Preconditions

- `Hub` `vw2` registered, ready, and with no assigned tenant.

**Steps:** 1. `Hubs.Delete` `vw2` → 2. Read Secrets in the OSAC namespace → 3. Create a `VirtualMachine` directly on `vw2` in a tenant namespace and observe the operator for two reconcile intervals

**Expected:** `Secret osac-cluster-vw2` no longer exists; `kubectl --kubeconfig main get secret -n <osac-ns> -l sigs.k8s.io/multicluster-runtime-kubeconfig=true` does not list `vw2`; the operator logs no reconcile for `vw2` and the hand-created `VirtualMachine` is left untouched.

#### TC-R1-03: A second `Hub` registers once the control-object hub is named

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-10 | high | automated |

##### Additional Preconditions

- The `NetworkClass` was created without `spec.hub` and one `Hub` (`hub`) is active.

**Steps:** 1. Register `Hub` `vw1` and read `NetworkClass.status` → 2. Recreate the `NetworkClass` with `spec.hub: hub` → 3. Register `Hub` `vw2` → 4. Create a tenant on `vw2` and a VM

**Expected:** Step 1 sets `NetworkClass.status.message` to a message containing `expected exactly one active networking hub` and `status.state` is not `READY`; step 2 sets `status.hub` to `hub` and `status.state` to `READY`; steps 3 and 4 succeed with the tenant's `VirtualNetwork` created on `hub` and its `VirtualMachineInstance` running on `vw2`; a second `NetworkClass` create that changes `spec.hub` to `vw2` is rejected with `InvalidArgument`.

### R-2: Each VM-hosting cluster is prepared for tenant networking once, when registered, with no per-tenant or per-VM setup

##### Shared Preconditions

- `main` running OSAC with provider networking enabled.
- A `vw1` cluster with its EVPN prerequisites supplied through `EVPN_VALUES`.

#### TC-R2-01: A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. Register `Hub` `vw1` and wait for its condition → 2. Create tenant `t1` assigned to `vw1` with a VM → 3. Create tenant `t2` assigned to `vw1` with a VM → 4. Re-read `Hub` `vw1`

**Expected:** Step 1 returns condition type `TenantNetworkingReady`, status `"True"`, reason `PrerequisitesMet`; both VMs reach `Ready` with a tenant IPv4 address; `Hub` `vw1` `status.conditions` is unchanged and no task or job ran against `vw1` during tenant creation for `t2` (job list filtered by the cluster shows only per-tenant tasks).

#### TC-R2-02: Each unmet prerequisite reports its own reason and names the object (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Additional Preconditions

- `Hub` `vw1` registered and reachable; exactly one prerequisite is removed per row.

##### Steps

1. Remove or degrade `{prerequisite}` on `vw1`.
2. Wait for the probe interval (five minutes) and read `Hub` `vw1` `status.conditions`.
3. Compare `{reason}` and the message.

##### Expected Results

| Prerequisite | Expected Result |
|--------------|-----------------|
| `VTEP tenant-vtep` set to `Accepted=False` | `TenantNetworkingReady=False`, reason `VTEPNotAccepted`, message contains `vw1` and `tenant-vtep` |
| `RouteAdvertisements osac-evpn` set to `Accepted=False` | `TenantNetworkingReady=False`, reason `RouteAdvertisementsNotAccepted`, message contains `osac-evpn` |
| `clusteruserdefinednetworks.k8s.ovn.org` CRD absent | `TenantNetworkingReady=False`, reason `CUDNNotAvailable`, message contains `clusteruserdefinednetwork` |
| `HyperConverged Available=False` | `TenantNetworkingReady=False`, reason `VirtualizationNotAvailable`, message contains `HyperConverged` |

#### TC-R2-03: `prepare-vm-cluster` is idempotent across re-runs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | medium | automated |

**Steps:** 1. Run `make prepare-vm-cluster HUB_NAME=vw1 VM_KUBECONFIG=... EVPN_VALUES=...` → 2. Capture object `resourceVersion`s for the VTEP, `RouteAdvertisements`, `FRRConfiguration`, and the `osac-remote-access` service account → 3. Run the same command again

**Expected:** Both runs exit 0; the second run changes no object (`resourceVersion` values are identical) and prints no error; `Hub` `vw1` `TenantNetworkingReady` stays `"True"`.

#### TC-R2-04: The networking instance group mounts one kubeconfig key per registered cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-7 | high | automated |

##### Additional Preconditions

- Three `Hub` records: `hub`, `vw1`, `vw2`.

**Steps:** 1. `kubectl get secret -n <osac-ns> osac-cluster-kubeconfigs -o jsonpath='{.data}'` → 2. Launch any Kubernetes Manager task on `vw2` and inspect the job pod environment

**Expected:** The Secret has exactly the keys `hub`, `vw1`, and `vw2`; the job pod mounts the Secret read-only and its environment contains no kubeconfig content (`printenv` shows no cluster token); the task's `osac_job_vars.cluster.id` equals `vw2`.

### R-3: The Cloud Provider Admin assigns one registered cluster per tenant at creation, and all of that tenant's VMs run there

##### Shared Preconditions

- `main` running OSAC with provider networking enabled.
- Two prepared `Hub` records: `vw1` and `vw2`.

#### TC-R3-01: Tenant created with an assignment places its default networking and VM namespace on that cluster only

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create tenant `t1` assigned to `vw2` → 2. Wait for `Tenant.status.conditions[DefaultNetworkingReady].status == "True"` → 3. List namespaces matching `osac-vn-*` on `vw1`, `vw2`, and `main` → 4. Create a VM on `t1`'s default Subnet

**Expected:** `osac-vn-<id>` for `t1`'s default VirtualNetwork exists on `vw2` only; on `vw1` and `main` the same list is empty; the `VirtualMachineInstance` is `Running` on `vw2` and absent from `vw1`; `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address` is non-empty.

#### TC-R3-02: Two tenants assigned to different clusters each land on their own cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

**Steps:** 1. Create tenant `t1` assigned to `vw1` and tenant `t2` assigned to `vw2` → 2. Create one VM for each → 3. Read the `osac.openshift.io/vm-cluster` annotation from each `ComputeInstance`, `VirtualNetwork`, `Subnet`, `SecurityGroup`, and `NetworkAttachment`

**Expected:** Every `t1` CR carries `osac.openshift.io/vm-cluster: vw1` and every `t2` CR carries `vw2`; `t1`'s `osac-vn-<id>` namespace exists only on `vw1` and `t2`'s only on `vw2`; both VMs are `Ready` with distinct addresses.

### R-4: Assignment is provider-side administration; tenants neither choose nor see the hosting cluster, and it cannot change

##### Shared Preconditions

- Two prepared `Hub` records, `vw1` and `vw2`.
- Tenant `t1` assigned to `vw1` with one VM.
- Tenant-scoped API credentials for `t1`.

#### TC-R4-01: No tenant-facing response exposes the cluster identity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

**Steps:** 1. As `t1`, call `Tenants.Get`, `ComputeInstances.List`, `Subnets.List`, `VirtualNetworks.List`, `SecurityGroups.List`, and `NetworkAttachments.List` → 2. Serialize each response to JSON → 3. Search for `vw1`, `vw2`, `hub`, `kubeconfig`, and `vm-cluster`

**Expected:** No response contains any of the searched strings; no response schema exposes a cluster, hub, or placement field; error messages from step 1 reference only tenant-owned identifiers.

#### TC-R4-02: A tenant cannot set or change the target cluster through the API

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Steps:** 1. As `t1`, attempt `ComputeInstances.Create` with metadata annotation `osac.openshift.io/vm-cluster: vw2` → 2. As a provider admin, `Patch` the annotation on the existing `ComputeInstance` to `vw2` → 3. Read the stored annotation and the `VirtualMachineInstance` location

**Expected:** Step 1 either rejects the request or stores `vw1`; the stored annotation after step 3 is `vw1`; the `VirtualMachineInstance` remains on `vw1`; no new object appears on `vw2`.

### R-5: An unprepared or removed cluster cannot be assigned, and the rejection names the cluster and the unmet prerequisite

##### Shared Preconditions

- `Hub` `vw1` prepared and ready; `Hub` `vw3` registered with `VTEP tenant-vtep` `Accepted=False`.

#### TC-R5-01: Assigning an unprepared cluster is rejected naming the cluster and prerequisite

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. `Tenants.Create` with the assignment set to `vw3` → 2. Read the error code and message → 3. `Tenants.List`

**Expected:** The call returns `InvalidArgument`; the message contains `vw3` and `tenant-vtep`; no tenant record is created (`Tenants.List` total is unchanged and the new tenant name returns `NotFound`).

#### TC-R5-02: Assigning a nonexistent cluster is rejected naming it

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

**Steps:** 1. `Tenants.Create` with the assignment set to `vw-missing` → 2. Read the error

**Expected:** The call returns `InvalidArgument` and the message contains `vw-missing` and the word `not found`.

#### TC-R5-03: Assigning a `Hub` that is being deleted is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Additional Preconditions

- `Hub` `vw4` registered, ready, and with no assigned tenant.

**Steps:** 1. `Hubs.Delete` `vw4` → 2. Before the delete completes, `Tenants.Create` with the assignment set to `vw4`

**Expected:** The create returns `InvalidArgument` with a message containing `vw4` and stating the cluster is being deleted; after the delete completes, a repeated create also returns `InvalidArgument`.

#### TC-R5-04: Selecting from more than one cluster without an assignment is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Additional Preconditions

- `vw1` and `vw2` both active and ready, and no placement assignment for the new tenant.

**Steps:** 1. `Tenants.Create` without an assignment → 2. Read the error

**Expected:** The call returns `InvalidArgument` with a message stating that no VM cluster is assigned to the tenant; no CR for the tenant is created on either cluster.

### R-6: A cluster is removed from VM hosting only when no tenant is assigned, and a removed cluster cannot be assigned

##### Shared Preconditions

- `Hub` `vw1` prepared and ready; `Hub` `vw5` prepared and ready.

#### TC-R6-01: Deleting a `Hub` with an assigned tenant is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Additional Preconditions

- Tenant `t1` assigned to `vw5`.

**Steps:** 1. `Hubs.Delete` `vw5` → 2. Read the error code and message → 3. `Hubs.Get` `vw5`

**Expected:** The call returns `FailedPrecondition`; the message states that tenants are assigned and includes the count `1`; `Hubs.Get` still returns `vw5` with no deletion timestamp, and `t1`'s networking is unaffected (`DefaultNetworkingReady` stays `"True"`).

#### TC-R6-02: A `Hub` with no assigned tenant deletes and becomes unassignable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Steps

1. `Hubs.Delete` `vw5` (no tenant assigned).
2. `Hubs.Get` `vw5` and `Tenants.Create` with the assignment set to `vw5`.

##### Expected Results

- Step 1 returns success and `Hubs.Get` then returns `NotFound`.
- Step 2's create returns `InvalidArgument` naming `vw5`, and no CR is created for the tenant.

### R-7: With provider networking enabled, a VM on its assigned cluster attaches to one Subnet and its SecurityGroups, receives its tenant IPv4, and reports network readiness before ready

##### Shared Preconditions

- Tenant `t1` assigned to `vw1`, whose default networking is `Ready`.
- The provider's Netris fabric is reachable and `RouteAdvertisements osac-evpn` is `Accepted=True`.

#### TC-R7-01: A VM on its assigned cluster attaches, receives an IPv4, and reports network readiness

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

**Steps:** 1. Create a VM with an explicit Subnet and SecurityGroup → 2. Stream `ComputeInstance` status → 3. Read the `VirtualMachineInstance` from `vw1` → 4. Check the order of the conditions

**Expected:** `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address` is a non-empty IPv4 address inside the Subnet CIDR; `status.conditions[NetworkReady].status == "True"`; `status.phase` becomes `Ready` only after `NetworkReady` is `True`; the `VMI` has interface address equal to the reported IPv4; the AAP job `osac-apply-network-attachment` recorded `osac_job_vars.cluster.id == "vw1"`.

#### TC-R7-02: Tenant defaults resolve on the assigned cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Steps:** 1. Create a VM with no Subnet and no SecurityGroups → 2. Read the resulting `NetworkAttachment` spec and the VM status

**Expected:** The `NetworkAttachment` references the tenant's default Subnet ID and default SecurityGroup ID; the VM receives an IPv4 address from the default Subnet CIDR; `NetworkReady` is `"True"`; no `InvalidArgument` is returned.

#### TC-R7-03: Namespace, CUDN, and SecurityGroup policies are created on the assigned cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

**Steps:** 1. Create a tenant VirtualNetwork, Subnet, and SecurityGroup with one ingress rule → 2. Run `kubectl --kubeconfig vw1 get namespace osac-vn-<id> -o yaml`, `get cudn osac-vn-<id> -o yaml`, and `get networkpolicy -n osac-vn-<id> -o yaml` → 3. Repeat the three reads with `--kubeconfig main` and `--kubeconfig vw2`

**Expected:** On `vw1` the namespace carries `k8s.ovn.org/primary-user-defined-network: ""`, annotations `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference`, the CUDN has `transport: EVPN`, `vni` route targets `0:<l2_vni>` and `0:<l3_vni>`, and the `osac-sg-<id>` policy exists; on `main` and `vw2` all three reads return `NotFound`.

#### TC-R7-04: Deleting the VM removes the remote namespace and policies, keeping shared tenant networking

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Steps:** 1. Delete the VM → 2. Wait for the `ComputeInstance` to disappear → 3. Read the tenant namespace, CUDN, and policies on `vw1` → 4. Read the tenant's default VirtualNetwork and Subnet

**Expected:** After step 2, no `VirtualMachine`, `VirtualMachineInstance`, `pod`, or `DataVolume` labelled with the instance ID remains on `vw1`; the tenant's default VirtualNetwork namespace, CUDN, and SecurityGroup policies still exist on `vw1`; `Subnets.Get` for the default Subnet still returns `Ready`.

### R-8: External access for those VMs behaves as on the management cluster today

##### Shared Preconditions

- Tenant `t1` assigned to `vw1` with a running VM that has a tenant IPv4 address.
- An `ExternalIPPool` with spare capacity.

#### TC-R8-01: Pool-allocated external access works for a VM on its assigned cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | automated |

**Steps:** 1. Create an `ExternalIP` without an explicit address → 2. Create an `ExternalIPAttachment` targeting the VM → 3. Reach the VM's SSH port from outside the tenant network → 4. Delete the attachment and then the `ExternalIP`

**Expected:** The `ExternalIP` is `ALLOCATED` with an address from the pool; the attachment reaches `READY`; the SSH connection succeeds and `whoami` on the VM returns the configured user; after step 4 both objects are gone and the fabric no longer answers on the released address; the AAP fabric tasks recorded no `osac_job_vars.cluster` key.

### R-9: Tenant isolation parity on every VM-hosting cluster

##### Shared Preconditions

- Tenants `t1` and `t2` both assigned to `vw1`, each with one VM.

#### TC-R9-01: Two tenants on the same cluster cannot reach each other's networks

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

**Steps:** 1. From `t1`'s VM, `ping -c 3` and `nc -z -w 3 <port>` `t2`'s VM address → 2. Read the `osac-sg-<id>` policies in both namespaces → 3. Read each namespace's pod selector

**Expected:** All packets to `t2`'s address are dropped (100% packet loss, connection times out); each namespace's baseline policy selects only pods of its own VirtualNetwork; `t1`'s SecurityGroup policy `podSelector` matches only `osac.openshift.io/compute-instance-id` of `t1`'s VM.

#### TC-R9-02: Cross-tenant Subnet and SecurityGroup references are rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Steps:** 1. As `t1`, create a VM referencing `t2`'s default Subnet ID → 2. As `t1`, create a VM referencing `t2`'s default SecurityGroup ID

**Expected:** Step 1 returns `InvalidArgument` or `NotFound` and no `ComputeInstance` is created; step 2 returns `InvalidArgument` or `NotFound` and no `ComputeInstance` is created; no CR is created on `vw1` for either attempt.

### R-10: The CI-only networking-disabled configuration keeps working

##### Shared Preconditions

- `main` with `global.networking.provisioningEnabled=false`.
- Tenant `t1` assigned to `vw1`.

#### TC-R10-01: With provider networking disabled a VM provisions without an address or network task

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

**Steps:** 1. Create a VM → 2. Read `ComputeInstance.status` → 3. Read the `VirtualMachineInstance` from `vw1` → 4. List AAP jobs for the instance

**Expected:** `status.phase` becomes `Ready`; `status.conditions[NetworkReady]` is `"True"` with reason `ProvisioningDisabled`; `compute_network_attachment_statuses` is empty and no IPv4 is reported; no `NetworkAttachment` CR exists; no `apply-network-attachment` or `create-subnet` job is listed for the instance; the `VirtualMachineInstance` runs in the tenant namespace on `vw1`.

#### TC-R10-02: A cluster reports `TenantNetworkingReady=True/ProvisioningDisabled` when networking is disabled

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Steps:** 1. Register `Hub` `vw1` while networking is disabled and the EVPN prerequisites are absent → 2. Read `Hub.status.conditions` → 3. `Tenants.Create` with the assignment set to `vw1`

**Expected:** The condition is `"True"` with reason `ProvisioningDisabled`; the message states that provider networking is disabled; step 3 succeeds and the tenant's `DefaultNetworkingReady` reaches `"True"` with reason `ProvisioningDisabled`.

### R-11: If a cluster becomes unprepared after assignment, provisioning fails only when a networking prerequisite is unmet, with a named diagnostic

##### Shared Preconditions

- Tenant `t1` assigned to `vw1`, whose default networking is `Ready`, with one existing VM.
- Provider networking enabled.

#### TC-R11-01: A prerequisite removed after assignment fails provisioning with a named diagnostic

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | critical | automated |

##### Additional Preconditions

- Set `RouteAdvertisements osac-evpn` to `Accepted=False` on `vw1` after the tenant is ready.

**Steps:** 1. Create a second VM on `t1` → 2. Wait for the `create-subnet` or `apply-network-attachment` job to fail → 3. Read `ComputeInstance.status.conditions[NetworkReady]` and the job entry message → 4. Check `main` and `vw2` for any object of this VM

**Expected:** `NetworkReady` is `"False"` with a reason identifying the cluster `vw1` and the unmet prerequisite `RouteAdvertisements osac-evpn`; the entry message contains `vw1` and `osac-evpn`; the `ComputeInstance` does not reach `Ready`; no namespace, CUDN, policy, or `VirtualMachine` for this VM exists on `main` or `vw2`.

#### TC-R11-02: An unreachable cluster retries and never falls back to the main cluster

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Additional Preconditions

- Background `curl` against `vw1`'s API server blocked by network policy.

**Steps:** 1. Create a VM on `t1` → 2. Observe the `status.jobs` entry across two retry intervals → 3. Read `Hub.status.conditions` → 4. Confirm no job or object was created on `main`

**Expected:** The entry state is `Retrying` with a message containing a next-retry timestamp and an HTTP transport error; the retry cadence follows the existing backoff (two minutes, then four); `Hub` `vw1` reports `TenantNetworkingReady=False` with reason `ClusterUnreachable`; `kubectl --kubeconfig main get vmi -A` shows no VM for the instance and no job targets `main`.

#### TC-R11-03: Restoring the prerequisite lets the retry succeed with no tenant action

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-9 | high | automated |

##### Preconditions

- State from TC-R11-01.

**Steps:** 1. Restore `RouteAdvertisements osac-evpn` to `Accepted=True` → 2. Wait for the retry → 3. Read the VM status

**Expected:** Without any tenant action the entry reaches `Succeeded`; `NetworkReady` becomes `"True"`; the VM receives an IPv4 address and reaches `Ready`; `Hub` `vw1` returns to `TenantNetworkingReady=True/PrerequisitesMet`.

### R-12: A fresh installation whose tenants are assigned to the management cluster behaves exactly as today

##### Shared Preconditions

- A fresh single-`Hub` installation where the only `Hub` record is `hub`, pointing at the management cluster.
- No placement assignment for the tenants created during the test.

#### TC-R12-01: A single-`Hub` fresh installation with no assignment behaves as today

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

**Steps:** 1. Create tenant `t1` with no assignment → 2. Create a VM on its default Subnet → 3. Read `Hub` `hub` conditions and the CR annotations → 4. Delete the VM and the tenant

**Expected:** Step 1 succeeds without any assignment because exactly one `Hub` is active; `Hub` `hub` reports `TenantNetworkingReady=True/PrerequisitesMet`; `t1`'s `VirtualNetwork`, `Subnet`, `SecurityGroup`, `NetworkAttachment`, and `ComputeInstance` carry `osac.openshift.io/vm-cluster: hub`; the VM receives an IPv4 address, reaches `Ready`, and appears on the management cluster; delete removes the VM namespace and keeps the tenant's default networking.

#### TC-R12-02: The baseline VMaaS networking suite passes unchanged on a single-cluster installation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-8 | critical | automated |

**Steps:** 1. Run the OSAC-1435 VMaaS networking acceptance suite against the single-`Hub` installation → 2. Compare results with the baseline recorded before this feature

**Expected:** Every case in the baseline suite passes with no modified expectation, including attachment, address reporting, network readiness ordering, external access, SecurityGroup rules, and dependency-safe cleanup; the case count equals the baseline count.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 34 |
| Critical | 13 |
| High | 18 |
| Medium | 3 |
| Low | 0 |
| Automated | 34 |
| Manual | 0 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 10 / 10 |
