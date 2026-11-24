# Testplan — OSAC-7308

## Overview

- **Feature:** OSAC-7305 — VMaaS Networking with Per-Tenant VM Clusters
- **Networking test cases:** 36 (32 case IDs; parameterized rows count individually)
- **Placement dependency checks:** 7, owned by OSAC-977 and counted separately
- **Interface changes covered:** 8 of 8

Tiers follow [`docs/INTEGRATION-TESTING.md`](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md).
Implementation-owned cases are `[DEV]`; deployed cross-component user journeys are
`[QE]`.

## Test Case Index

| ID | Scenario | IC | Priority | Tier | Owner |
|----|----------|----|----------|------|-------|
| TC-R1-01 | Multiple day-2 VM hosts become ready without an operator restart | IC-6 | critical | E2E | [QE] |
| TC-R1-02 | Removing an unused `WorkloadCluster` stops its readiness probes | IC-6 | high | E2E | [QE] |
| TC-R1-03 | Adding a VM-hosting cluster needs no `NetworkClass` change | IC-2 | high | E2E | [QE] |
| TC-R1-04 | Resources that must stay on the management cluster never land on a VM-hosting cluster | IC-6 | high | component-integration | [DEV] |
| TC-R2-01 | A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation | IC-1 | critical | E2E | [QE] |
| TC-R2-02 | Each unmet prerequisite reports its own reason and names the object (parameterized) | IC-1 | high | E2E | [QE] |
| TC-R2-04 | A networking job uses the shared credential for its target only | IC-7 | high | Contract | [DEV] |
| TC-R2-05 | A freshly prepared cluster whose advertisement is `ConfigurationPending` is assignable | IC-1 | critical | E2E | [QE] |
| TC-R2-07 | Concurrent readiness and registration updates preserve both conditions | IC-1 | high | component-integration | [DEV] |
| TC-R3-01 | Tenant created with an assignment places its default networking and VM namespace on that cluster only | IC-2 | critical | E2E | [QE] |
| TC-R3-02 | Two tenants assigned to different clusters each land on their own cluster | IC-2 | high | E2E | [QE] |
| TC-R3-03 | A bare-metal-only tenant retains default networking in a mixed VMaaS and BMaaS deployment | IC-2 | critical | E2E | [QE] |
| TC-R4-01 | No tenant-facing response exposes the cluster identity | IC-3 | critical | E2E | [QE] |
| TC-R4-02 | The networking admission policy prevents target changes after creation | IC-3 | high | component-integration | [DEV] |
| TC-R5-05 | Networking uses the recorded target after another cluster registers | IC-2 | high | component-integration | [DEV] |
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
| TC-R12-01 | A fresh management-only deployment uses the recorded local VM target | IC-2 | critical | E2E | [QE] |
| TC-R12-02 | The baseline VMaaS networking suite passes unchanged on a single-cluster installation | — | critical | E2E | [QE] |
| TC-R12-03 | A day-2 remote VM host does not change management-cluster placement | IC-2 | critical | E2E | [QE] |

## Test Cases

### R-1: Remote VM hosts are registered after OSAC installation

##### Shared Preconditions

- `main` running OSAC, and existing workload clusters `vw1` and `vw2` reachable from `main`. They are not registered as `Hub`s.
- Provider networking enabled (`global.networking.provisioningEnabled=true`).
- The provider has prepared the workload clusters used in each case for networking and can register them through the day-2 API.
- Private API access token for the fulfillment API.

#### TC-R1-01: Multiple day-2 VM hosts become ready without an operator restart

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | critical | E2E | [QE] | automated |

**Steps:** 1. Record the operator pod UID and restart count → 2. Register `vw1` then `vw2` via day-2 VMaaS registration with access to each target; neither requires an ACM `ManagedCluster` → 3. Wait for both to report `TenantNetworkingReady=True` → 4. Assign a tenant to `vw2` and create a VM on its default Subnet → 5. Read the namespace and VM on `vw2` and re-read the operator pod UID

**Expected:** Both registrations are active; adding `vw2` does not replace `vw1`. The operator pod UID and restart count are unchanged. The VirtualNetwork namespace `osac-vn-<id>` exists on `vw2` and contains the `VirtualMachineInstance` whose address is reported by `ComputeInstance.status.compute_network_attachment_statuses[0].ip_address`; `NetworkReady=True`.

#### TC-R1-02: Removing an unused `WorkloadCluster` stops its readiness probes

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | E2E | [QE] | automated |

##### Additional Preconditions

- `WorkloadCluster` `vw2` registered, ready, and with no assigned tenant.

**Steps:** 1. Confirm the operator is probing `vw2` → 2. Remove `vw2` through the placement foundation → 3. After removal is visible to the operator, observe probe requests for two five-minute intervals

**Expected:** No new networking readiness probes contact `vw2` after removal. The probe schedule still runs for other registered targets. Placement owns refusal to remove an assigned target (TC-R6-01); this case does not assert changes to VM or storage watches.

#### TC-R1-03: Adding a VM-hosting cluster needs no `NetworkClass` change

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | E2E | [QE] | automated |

##### Additional Preconditions

- A fresh installation with one `Hub` (`hub`) and a `NetworkClass` that names no cluster.
- `vw1` is prepared for tenant networking before registration.

**Steps:** 1. Record the `NetworkClass` `metadata.generation`, `spec`, and `resourceVersion` → 2. Register `WorkloadCluster` `vw1` and wait for its condition → 3. Create a tenant assigned to `vw1` and a VM → 4. Re-read the `NetworkClass`

**Expected:** The `NetworkClass` is unchanged (same `resourceVersion`); `status.hub` still names `hub` and `status.state` stays `READY`; the tenant's `VirtualNetwork` and `Subnet` are created on `main` and the VM runs on `vw1`.

#### TC-R1-04: Resources that must stay on the management cluster never land on a VM-hosting cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | component-integration | [DEV] | automated |

##### Additional Preconditions

- `main` and one VM-hosting cluster `vw1` are registered; `vw1` has no OSAC CRDs.

**Steps:** 1. Use Kubernetes API discovery on `vw1` to check which resource kinds it serves → 2. Create a `ComputeInstance` with no network attachment, a `Volume`, a `ClusterOrder`, and a `BareMetalInstance` → 3. Check their control-object location and inspect the workload cluster's API audit records or recorded client requests

**Expected:** Discovery on `vw1` does not advertise the OSAC CR types. Each successful operation keeps its control CR on `main`; any placement failure reports an error rather than attempting a remote CR write. No OSAC client request for those CR types reaches `vw1`.

### R-2: Each VM-hosting cluster is prepared for tenant networking once, when registered, with no per-tenant or per-VM setup

##### Shared Preconditions

- `main` running OSAC with provider networking enabled.
- A `vw1` cluster prepared for EVPN networking by the provider. Individual cases specify when it is registered.

#### TC-R2-01: A prepared cluster reports `TenantNetworkingReady=True`, and a second tenant needs no new preparation

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- `vw1` has no CUDN and `RouteAdvertisements osac-evpn` reports `ConfigurationPending`.

**Steps:** 1. Register `vw1` and wait for `TenantNetworkingReady` → 2. Create tenant `t1` assigned to `vw1` with a VM → 3. Create tenant `t2` assigned to `vw1` with a VM → 4. Re-read the condition

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

Use these rows and the first-CUDN case in TC-R2-05 as the shared readiness
fixtures for the probe and the applicable task-time checks in TC-R7-06. A
provider-facing unmet-prerequisite message identifies the target and the
failed check.

#### TC-R2-04: A networking job uses the shared credential for its target only

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-7 | high | Contract | [DEV] | automated |

##### Additional Preconditions

- Two VM-host registrations with distinct test credentials and observable target endpoints. The shared AAP credential mechanism is available.

**Steps:** 1. Launch a Kubernetes Manager task with `cluster.id=vw2` → 2. Observe the authenticated request at the target endpoints and check the job input and diagnostics for secret material → 3. Make the test credential for `vw2` temporarily unavailable and repeat

**Expected:** Only the `vw2` credential is used for target operations. Job input and diagnostics contain the identifier but no credential material. With the `vw2` credential unavailable, the job reports a retryable failure and does not use `vw1` or the hub as a substitute.

#### TC-R2-05: A freshly prepared cluster whose advertisement is `ConfigurationPending` is assignable

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- `vw1` freshly prepared; no CUDN exists on it; `RouteAdvertisements osac-evpn` reports `ConfigurationPending`.

**Steps:** 1. Register `WorkloadCluster` `vw1` → 2. Read its condition → 3. Create tenant `t1` assigned to `vw1` → 4. Create a VM on its default Subnet → 5. Re-read the condition and the advertisement

**Expected:** Step 2 reports `TenantNetworkingReady=True` with reason `AwaitingFirstNetwork`; step 3 succeeds; after the CUDN exists the advertisement becomes `Accepted=True` and the condition reason becomes `PrerequisitesMet`; the VM reaches `Ready` with a tenant IPv4 address.

#### TC-R2-07: Concurrent readiness and registration updates preserve both conditions

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-1 | high | component-integration | [DEV] | automated |

##### Additional Preconditions

- Fulfillment API and PostgreSQL running. Seed a `WorkloadCluster` record with a registration condition and a networking condition.

**Steps:** 1. Drive overlapping condition writes as the registration and networking writers → 2. Read back the cluster after both writes complete → 3. Invoke the networking write as an authenticated non-operator identity → 4. Send an invalid readiness observation as the operator

**Expected:** Both new condition values persist, along with all other status fields and spec. Step 3 returns `PermissionDenied`; step 4 returns `InvalidArgument`. Neither changes the record, and the networking write cannot update `Available`.

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

#### TC-R3-03: A bare-metal-only tenant retains default networking in a mixed VMaaS and BMaaS deployment

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- VMaaS, BMaaS, and provider networking are enabled, with both a Fabric
  Manager and a Kubernetes Manager. A bare-metal host is available.
- Under the placement assumption in design §4.1.2, OSAC-977 supplies `vw1`
  for `t1` and `vw2` for `t2`. Only `t1` will run a VM.

**Steps:** 1. Let default networking provision for both tenants → 2. Create a
VM for `t1` and attach a bare-metal instance to `t2`'s default Subnet without
creating a VM for `t2` → 3. Read both tenants' networking status, job targets,
and CUDNs.

**Expected:** Both default networks reach `Ready`. `t1`'s VM and CUDN are on
`vw1`; `t2`'s default network gets its CUDN on `vw2` before any VM exists for
that tenant. `t2`'s bare-metal attachment succeeds via the fabric. No
Kubernetes job selects a cluster other than its recorded target. If OSAC-977
allows ordinary tenants to have no target in this configuration, confirm
their network behavior separately before adding that test.

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

#### TC-R4-02: The networking admission policy prevents target changes after creation

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | high | component-integration | [DEV] | automated |

**Steps:**

1. With the existing networking policy enabled on management, create annotated
   and unannotated fixtures for `VirtualNetwork`, `Subnet`, `SecurityGroup`,
   and `NetworkAttachment` using an allowed OSAC controller identity.
2. As the allowed identity, try to change or remove the annotation from the
   annotated fixtures and add it to the unannotated ones.
3. Repeat the target change as a Kubernetes `cluster-admin`. Then patch an
   unrelated annotation using the allowed controller identity and read back
   the fixtures.

**Expected:** Admission denies all target changes, including changes attempted
by the allowed controller identity. Its unrelated update succeeds. Target
presence and values remain exactly as created. VMaaS owns the corresponding
`ComputeInstance` test.

### R-5: An unprepared or removed cluster cannot be assigned, and the rejection names the cluster and the unmet prerequisite

Networking verifies the readiness status, reason, and message that placement
consumes (TC-R2-02 and TC-R11-01). Tenant admission itself is a
[placement dependency check](#placement-dependency-acceptance).

#### TC-R5-05: Networking uses the recorded target after another cluster registers

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | high | component-integration | [DEV] | automated |

##### Steps

1. Start with `t1` already assigned to `vw1` by placement.
2. Register `WorkloadCluster` `vw2`.
3. Reconcile new VM-targeted networking CRs for `t1`.
4. Compare their annotations and task targets to the stored target.

##### Expected Results

- Each new networking CR carries `osac.openshift.io/vm-cluster: vw1`.
- Networking sends its Kubernetes Manager tasks to `vw1`; it does not choose
  `vw2` or modify the placement record.

### R-6: A cluster is removed from VM hosting only when no tenant is assigned, and a removed cluster cannot be assigned

Removal safeguards and subsequent admission are
[placement dependency checks](#placement-dependency-acceptance).
Networking verifies that probing stops after removal (TC-R1-02).

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
2. Read the per-VirtualNetwork namespace, CUDN, and policies on `vw1`, and the tenant's default VirtualNetwork and Subnet.
3. Delete tenant `t1` and wait for its networking resources to be removed.
4. Re-read the namespace, CUDN, and policies on `vw1`.

##### Expected Results

- After step 2, no `VirtualMachine`, `VirtualMachineInstance`, `pod`, or `DataVolume` labelled with the instance ID remains on `vw1`; the tenant's default VirtualNetwork namespace, CUDN, and SecurityGroup policies still exist; `Subnets.Get` for the default Subnet still returns `Ready`.
- After step 4, the per-VirtualNetwork namespace, CUDN, and SecurityGroup policies are gone from `vw1`; `Subnets.Get` returns `NotFound`.

#### TC-R7-05: Annotation copy, `cluster.id`, and attachment namespace validation use the CR's target

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-3 | high | Envtest | [DEV] | automated |

**Steps:** 1. With a `ComputeInstance` annotated for `vw1`, reconcile it and read the created `NetworkAttachment` → 2. Run `ParseVMAttachment` with an accepted result naming a namespace that exists only on `vw1`'s (fake) target client → 3. Run the same result after the registry confirms the target was removed → 4. Reconcile a `NetworkAttachment` that requires a target but lacks the annotation

**Expected:** Step 1's `NetworkAttachment` carries `osac.openshift.io/vm-cluster: vw1` copied from the `ComputeInstance`, and the operator writes no other value; step 2 validates the namespace and its tenant label through the target cluster's reader and accepts the result; step 3 fails as final with a provider message naming the confirmed removed cluster, and never falls back to the local reader.
Step 4 launches no job, selects no fallback, and records `VmClusterNotAssigned`
in provider-only diagnostics.

#### TC-R7-06: `cudn_evpn` splits hub reads from target applies and fails when `cluster` is absent

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-5 | medium | Contract | [DEV] | automated |

**Steps:** 1. Run `create_subnet` with `cluster: {id: vw1}` and a sibling Subnet
whose owner CR exists only on the hub fixture → 2. Run it with the applicable
shared prerequisite fixtures from TC-R2-02 and TC-R2-05, including a pending
advertisement before and after the first CUDN → 3. Run with no `cluster` key.

**Expected:** Step 1 reads the owner Subnet CR from the hub and creates the
CUDN on the target. In step 2, the job allows the first-CUDN exception and
otherwise reports the same unmet-prerequisite reason as the probe for the
same check. It performs no writes when a prerequisite fails. Step 3 fails
before applying objects and never falls back to the job pod's cluster.

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

**Steps:** 1. Add a second `t1` VM on the same network and allow TCP on the test port between those VMs → 2. Confirm the first `t1` VM reaches that listener → 3. From `t1`, ping `t2`'s VM and attempt to reach its listener on the same test port, with no policy allowing traffic from `t1` → 4. Inspect both namespaces' policies and selectors

**Expected:** The same-tenant connection succeeds before the cross-tenant checks. All cross-tenant ICMP probes are dropped and the cross-tenant TCP connection times out. Each baseline policy is scoped to its own VirtualNetwork namespace and each SecurityGroup selects only the matching instances in that namespace.

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

**Steps:** 1. Provide registered and reachable `vw1` to the operator with networking disabled and EVPN prerequisites absent → 2. Run the probe and capture its condition update at the Fulfillment boundary

**Expected:** The operator reports `TenantNetworkingReady=True` with reason `ProvisioningDisabled`, does not require EVPN prerequisites, and submits no changes to registration conditions. This test does not exercise placement admission.

### R-11: If a cluster becomes unprepared after assignment, provisioning fails only when a networking prerequisite is unmet, with a named diagnostic

##### Shared Preconditions

- Tenant `t1` assigned to `vw1`, whose default networking is `Ready`, with one existing VM.
- Provider networking enabled.

#### TC-R11-01: A prerequisite removed after assignment fails provisioning with a named diagnostic

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-9 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- After a successful probe, degrade `RouteAdvertisements osac-evpn` on `vw1`
  while a CUDN exists. Hold the next probe until the new job has checked its
  prerequisites.

**Steps:** 1. Create a second VM on `t1` → 2. Observe the `apply-network-attachment` job fail before the next probe → 3. Read `NetworkReady` and the job diagnostic, and check for target writes → 4. Allow the next probe and read the cluster condition → 5. Check `main` and `vw2` for objects of this VM

**Expected:** Despite the last readiness observation being `True`, the job reports `vw1` and `osac-evpn` without applying changes. Tenant-visible `NetworkReady=False` has a generic reason and message without the cluster identity. The next probe reports the unmet prerequisite. The VM does not become ready and no network or VM objects for it are placed on `main` or `vw2`.

#### TC-R11-02: An unreachable cluster retries and never falls back to the management cluster

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-6 | high | E2E | [QE] | automated |

##### Additional Preconditions

- Network transport to the `vw1` API is blocked from both the operator and
  the AAP job; their credentials stay valid. Verify the interruption from
  both client locations. Keep the hub API reachable.

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

- A fresh management-only VM deployment with provider networking enabled.
  Registration and placement make an explicit management VM target available.
  Only TC-R12-03 registers a remote VM host.

#### TC-R12-01: A fresh management-only deployment uses the recorded local VM target

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | E2E | [QE] | automated |

**Steps:** 1. Check that the management target's `WorkloadCluster` reports
`TenantNetworkingReady=True` and create `t1` using the existing
management-only workflow → 2. Create a VM on its default Subnet; compare
the tenant's recorded target, the networking annotations, and the target IDs
in the VM and Kubernetes Manager jobs → 3. Delete only the VM and check its
default networking → 4. Delete the tenant and check the same resources again.

**Expected:** No explicit per-tenant target choice is needed. The tenant's
recorded target, the resource annotations, and both jobs use the same explicit
management target ID, and shared credential delivery supplies the
corresponding access without a fallback. The VM reaches `Ready` with a tenant
IPv4 address on management. After step 3 the VM is gone but the default
VirtualNetwork, its namespace, CUDN, Subnet, and SecurityGroup policies still
exist. After step 4 those default-network resources are removed.

#### TC-R12-02: The baseline VMaaS networking suite passes unchanged on a single-cluster installation

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| — | critical | E2E | [QE] | automated |

**Steps:** 1. Run the OSAC-1435 VMaaS networking acceptance suite against the single-cluster installation → 2. Compare results with the baseline recorded before this feature

**Expected:** Every case in the baseline suite passes with no modified expectation, including attachment, address reporting, network readiness ordering, external access, SecurityGroup rules, and dependency-safe cleanup; the case count equals the baseline count.

#### TC-R12-03: A day-2 remote VM host does not change management-cluster placement

| Interface Change | Priority | Tier | Owner | Automation |
|-----------------|----------|------|-------|------------|
| IC-2 | critical | E2E | [QE] | automated |

##### Additional Preconditions

- `t1` already has a recorded management target. The provider has a prepared
  remote VM cluster that is not yet registered.

**Steps:** 1. Register the remote VM cluster after OSAC is installed and wait for its readiness condition → 2. Create `t2` assigned to the remote target → 3. Create one VM for each tenant and read the CRs, namespace, and VM locations

**Expected:** Both VMs provision successfully on their recorded targets. `t1`'s networking remains on management and `t2`'s networking uses the remote target. Neither tenant's per-VirtualNetwork namespace is copied to the other cluster.

## Placement dependency acceptance

**Owner: [OSAC-977](https://redhat.atlassian.net/browse/OSAC-977).** These
acceptance checks retain their case IDs for traceability. They are not
networking implementation cases and are excluded from this plan's totals.

| ID | Placement acceptance check |
|---|---|
| TC-R5-01 | An unprepared target is rejected without creating the tenant. The error surfaces the networking diagnostic, naming the target and failed prerequisite. |
| TC-R5-02 | A nonexistent target is rejected with a provider diagnostic naming it. |
| TC-R5-03 | A target in the process of removal cannot be assigned. |
| TC-R5-04 | Reserved `system` and `shared` tenants and ordinary tenants in a VMaaS-disabled deployment can onboard without a VM target. |
| TC-R5-06 | A cluster without the `vmaas` capability cannot be assigned. A request using a supported, ready target can proceed. |
| TC-R6-01 | Removal is refused while a tenant is assigned. Existing tenant networking remains ready. |
| TC-R6-02 | An unused cluster can be removed, and a subsequent assignment to that target is rejected. |

## Gaps

### Requirement Coverage Gaps

The plan traces all 12 PRD requirements. [OSAC-977](https://redhat.atlassian.net/browse/OSAC-977)
owns the placement admission and removal checks in R-5 and R-6; their results
cannot be inferred from networking-only tests. The mixed-deployment case
(TC-R3-03) assumes a recorded target for each ordinary tenant. Behavior for
an intentionally unassigned tenant in that configuration depends on the
placement decision in design §9.1.

### Interface Change Coverage Gaps

All eight interfaces are mapped to planned cases, not executed coverage.
The shared AAP credential contract (TC-R2-04) needs the supported delivery path
and a harness that observes real AAP launches to two test targets. A fake
credential resolver does not prove that boundary. A deployed multi-cluster
environment with prepared hosts, per-tenant placement, and a way to isolate API
transport failures is also needed for the QE cases; the execution path is not
yet established. Volume placement, console routing, and legacy credential
migration are covered by their owning designs.

## Implementation verification

| Behavior and cases | Tier, suite, and command | Boundary |
|---|---|---|
| Fulfillment condition upsert (IC-1, TC-R2-07) | Component integration. Proposed spec under `fulfillment-service/it/`; from the OSAC root, `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. | Real Fulfillment API, PostgreSQL, and authorized test writers; registration and networking observations supplied by the test. No AAP or physical provider. |
| Target annotation policy (IC-3, TC-R4-02) | Component integration. Proposed live-admission spec under `osac-operator/test/integration/`; from `osac-operator/`, `make integration-tests` against a deployed cluster with the installer policy and test identities. | Real Kubernetes admission; no VM or fabric. A Helm render alone does not exercise denied patches. |
| Attachment and probe behavior (IC-3/IC-1, TC-R7-05/TC-R10-02) | Envtest. Extend the networking cases in `osac-operator/internal/controller/`; run `make test` from `osac-operator/`. | Real Kubernetes API and etcd for management CRs; target client and Fulfillment status boundary controlled by fixtures. |
| Manager reads, applies, and live precheck (IC-5, TC-R7-06) | Contract. Extend the `cudn_evpn` suite; from `osac-aap/tests/integration/`, run `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e '@common_vars.yml'` after setting up its Kind fixture. Share applicable prerequisite cases with TC-R2-02 and TC-R2-05. Separate hub and target endpoints are proposed. | Real playbook and Kubernetes API; prerequisite objects/off-host failures are fixture-controlled. No live OVN, fabric, or AAP credential mediation. |

## Summary

| Metric | Count |
|--------|-------|
| Networking test cases | 36 |
| Critical | 14 |
| High | 21 |
| Medium | 1 |
| Low | 0 |
| Automated | 36 |
| Manual | 0 |
| Placement dependency checks (not included above) | 7 |
| Requirements mapped | 12 / 12 |
| Interface changes with test cases | 8 / 8 |
