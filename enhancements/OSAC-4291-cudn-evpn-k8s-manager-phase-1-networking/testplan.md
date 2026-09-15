# Testplan — OSAC-4291

## Overview

- **Feature:** OSAC-4291 — CUDN EVPN K8s Manager Phase 1 Networking:
  Single-Cluster VM-to-Fabric Bridging
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Scope:** Provider registration, sequential fabric-to-CUDN provisioning,
  first-subnet VM support, fabric-only additional Subnets, EVPN connectivity,
  readiness, deletion, and Phase 1 failure recovery.
- **Inherited boundary:** The shared Unified Networking plan owns IPv4-only,
  connected single-hub admission, create/read/delete-only operations, and
  tenant reference/defaulting validation.
- **Manual prerequisites:** OCP with OVN-Kubernetes, FRR, NMState, VTEP,
  RouteAdvertisements, BGP underlay, gateway MAC coordination, and a real
  Netris fabric. These are installation prerequisites, not tenant API
  features.
- **Explicit limits:** IPv4 only; one CUDN/VM-capable Subnet per
  VirtualNetwork; no VM placement after multiple Subnets exist; no automatic
  VTEP or gateway-MAC provisioning; no multi-cluster, secondary-CUDN,
  multi-NIC, same-cluster VM-to-VM inter-Subnet routing, or east-west feature.

## Execution strategy

- **Unit:** fulfillment-service topology validation, manager capability
  resolution, operator phase/state logic, VNI/ConfigMap parsing, CUDN
  readiness, VM placement, and deletion guards.
- **Integration:** real PostgreSQL and validation path, envtest/Kind CRDs and
  controllers, fake Netris/AAP jobs, documented ConfigMap data handoff, fake
  CUDN/namespace/MetalLB readiness, failure injection, and race tests.
- **E2E:** real OCP/OVN-K/FRR/Netris environment verifying CUDN, EVPN routes,
  VM-to-fabric traffic, fabric-only Subnets, VM blocking, and cleanup.

## Test cases

### R1: Provider manager registration and capability contract

#### TC-R1-01: Valid `cudn_evpn` registration is accepted

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-1 | Unit, integration, E2E-preflight | critical | automated |

##### Steps

1. Install the provider ConfigMap declaring `cudn_evpn`.
2. Verify IPv4 support, IPv6 disabled, create/read/delete operations, and the
   separate Phase 1 single-subnet VM-placement validation.
3. Create a NetworkClass with `fabric_manager=netris` and
   `k8s_manager=cudn_evpn`.
4. With the Fabric Manager advertising NATGateway support, create a Ready
   VirtualNetwork and an Allocated, unconsumed ExternalIP, then create a
   NATGateway through the combined NetworkClass.

##### Expected results

- Registration and capability loading succeed.
- NetworkClass is accepted only after required installation prerequisites are
  available.
- `cudn_evpn` is not selected as Default Networking's default manager when
  required manual prerequisites are absent.
- In a combined NetworkClass, NATGateway is accepted through the configured
  Fabric Manager when that manager advertises NAT support; `cudn_evpn` does
  not need to advertise the NATGateway operation itself.

#### TC-R1-02: Incomplete or tenant-controlled registration is rejected

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-1 | Unit, integration | critical | automated |

##### Cases

- unregistered/incomplete manager;
- IPv6/dual-stack capability;
- missing VTEP/FRR/BGP prerequisite;
- tenant tries to select manager, VNI, VTEP, gateway MAC, or skip annotation;
- NATGateway request in K8s-only mode;
- NATGateway request in combined mode when the Fabric Manager does not
  advertise NATGateway support.

##### Expected results

- Provider misconfiguration or unsupported tenant input fails before backend
  provisioning.
- K8s-only NATGateway requests and combined-manager requests without Fabric
  NATGateway support are rejected before persistence or dispatch.

### R2: Sequential fabric-to-CUDN provisioning

#### TC-R2-01: First Subnet creates fabric and CUDN in order

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-3, IC-5 | Unit, integration, E2E | critical | automated |

##### Steps

1. Create a VirtualNetwork; verify no fabric or CUDN provisioning occurs.
2. Create its first Subnet.
3. Observe fabric VPC/VNet job completion.
4. Read the documented VNI ConfigMap output.
5. Observe K8s manager CUDN/namespace/IPAddressPool creation.
6. Wait for CUDN and Subnet readiness.

##### Expected results

- Fabric job runs before the K8s job.
- `l2_vni`, `l3_vni`, and `fabric_reserved_range` are transferred through
  the documented ConfigMap path.
- CUDN uses EVPN Layer2 transport, correct VNI values, generated Phase 1
  route targets, and reserved ranges.
- Namespace, bridge, CUDN, and IPAddressPool are Ready before Subnet Ready.

#### TC-R2-02: Missing or invalid fabric output blocks CUDN

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-3 | Unit, integration | critical | automated |

##### Cases

- missing ConfigMap;
- missing `l2_vni`, `l3_vni`, or `fabric_reserved_range`;
- malformed VNI/range;
- fabric job Pending or Failed.

##### Expected results

- K8s manager job is not started when fabric is not successful.
- Subnet is Pending/Failed with `VNIExtractionFailed` or the documented
  manager condition.
- No false Ready state or partial CUDN is reported.
- Recovery retries the missing phase without duplicating the successful phase.

#### TC-R2-03: CUDN failure and restart recovery

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-3, IC-5 | Integration, E2E-recovery | high | automated |

##### Expected results

- Missing VTEP, invalid route data, non-Ready CUDN, or CUDN job failure leaves
  Subnet non-Ready and requeues according to the design.
- Controller restart after fabric completion, ConfigMap read, K8s job creation,
  and CUDN readiness resumes idempotently.
- No duplicate VNI, VNet, namespace, CUDN, or job is created.

### R3: First and additional Subnet topology

#### TC-R3-01: First Subnet is VM-capable

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-5 | Unit, integration, E2E | critical | automated |

##### Expected results

- First Subnet receives the only CUDN for the VirtualNetwork.
- VM placement is accepted only after CUDN/namespace readiness.
- CUDN persists for the lifetime of the supported topology.

#### TC-R3-02: Additional Subnet is fabric-only while no VMs exist

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-3 | Unit, integration, E2E | critical | automated |

##### Steps

1. Create first Subnet with no VM.
2. Create a second Subnet under the same VirtualNetwork.
3. Inspect dispatch, fabric VNet, first CUDN, and second namespace.

##### Expected results

- API accepts the second Subnet.
- Only the fabric manager is dispatched for the second Subnet.
- Second Subnet has no CUDN or namespace.
- First Subnet's CUDN persists unchanged.
- VMs are blocked in both Subnets once the VN has multiple Subnets.

#### TC-R3-03: Additional Subnet is rejected after VM creation

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2 | Unit, integration, E2E rejection | critical | automated |

##### Expected results

- API returns `FailedPrecondition` before provisioning starts.
- Error identifies the existing VM/first Subnet and explains the Phase 1
  topology restriction.
- No second VNet, CUDN, namespace, or job is created.

#### TC-R3-04: Explicit provider skip produces fabric-only Subnet

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-3 | Unit, integration, E2E | high | automated |

##### Expected results

- Provider-only skip annotation produces fabric-only provisioning even for a
  first/only Subnet.
- Tenant cannot set or use the annotation as a hidden API input. Test both a
  tenant-facing API request and a direct CR containing the annotation.
- A provider-authenticated path with valid provenance may set the annotation;
  a forged or tenant-owned annotation is rejected or ignored.
- Deletion skips CUDN cleanup for the fabric-only Subnet.

#### TC-R3-05: Persisted Subnet identity determines first-Subnet behavior

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-3 | Unit, integration, E2E-stress | critical | automated |

##### Cases

- Two Subnets are created concurrently and reconciliation observes them in
  reverse list order.
- The controller restarts after either Subnet is persisted but before its
  CUDN decision is reconciled.
- A later Subnet is reconciled before the earlier-created Subnet.

##### Expected results

- The first Subnet is selected by stable persisted creation sequence, never by
  unordered list position or reconciliation order.
- Exactly that Subnet receives the CUDN; later Subnets are fabric-only unless
  the explicit provider skip rule applies.
- Restart and retry preserve the same identity without duplicate CUDNs, VNIs,
  namespaces, or backend jobs.

### R4: VM placement and connectivity

#### TC-R4-01: Single-subnet VM placement succeeds

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-5, IC-6 | Unit, integration, E2E | critical | automated |

##### Expected results

- VM has exactly one attachment/interface.
- Template receives the selected Subnet's CUDN NAD and namespace.
- OVN DHCP supplies an IPv4 address.
- VM becomes Ready only after CUDN and namespace readiness.

#### TC-R4-02: VM placement is rejected for unsupported topology

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-5 | Unit, integration, E2E rejection | critical | automated |

##### Cases

- VN has multiple Subnets, including the first CUDN Subnet;
- selected Subnet is fabric-only;
- CUDN/namespace is missing or non-Ready;
- VM has more than one attachment;
- tenant attempts to select another Subnet as a fallback.

##### Expected results

- VM create is rejected before persistence or template dispatch.
- Deleting a VM does not automatically make an already multi-Subnet VN
  VM-capable again.
- No arbitrary first Subnet or alternate namespace is selected.

#### TC-R4-03: EVPN data-plane connectivity works

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-5, IC-6 | E2E | critical | automated/manual network validation |

##### Expected results

- Same-subnet VM-to-BM L2 ping succeeds.
- VM MAC/IP is visible through EVPN Type-2 routes.
- Cross-subnet VM-to-BM L3 ping succeeds through the configured fabric ipVRF
  where that connectivity is part of the installation.
- VM-to-VM inter-Subnet routing on the same cluster remains unsupported.

### R5: Deletion and dependency guards

#### TC-R5-01: CUDN Subnet deletion waits for VMs

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Expected results

- Delete is blocked while VMs/VMIs exist.
- `DeletionBlocked` event/condition is emitted and controller requeues.
- CUDN and fabric VNet remain intact.

#### TC-R5-02: First and later Subnet deletion ordering

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

##### Expected results

- First Subnet: VMs → CUDN → namespace → fabric VNet.
- Fabric-only Subnet: fabric VNet only; no CUDN call.
- VirtualNetwork/VPC is deleted only after every child VNet/Subnet is gone.
- CUDN deletion failure prevents fabric deletion and leaves a visible failed
  deletion state.

### R6: Concurrency, isolation, and unsupported Phase 1 features

#### TC-R6-01: Concurrent topology operations are race-safe

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E-stress | critical | automated |

##### Cases

- two second-Subnet creates concurrently;
- VM create concurrent with second-Subnet create;
- delete/recreate around CUDN deletion and VNI reuse.

##### Expected results

- Database/API locking allows only a supported topology.
- No duplicate CUDN/VNI or unsupported VM placement occurs.
- Deletion ordering prevents VNI reuse before CUDN is gone.

#### TC-R6-02: Phase 1 non-goals are not exposed

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection/preflight | high | automated where user-visible |

##### Cases

- IPv6/dual-stack;
- multi-cluster VM placement;
- multi-NIC/secondary CUDN;
- automatic VTEP provisioning;
- automatic gateway-MAC coordination;
- tenant setting provider-only topology controls;
- CaaS private-worker EVPN port-move integration while transport support is
  TBD;
- update/patch/replace of network-owned fields;
- NATGateway in a K8s-only NetworkClass whose only manager is `cudn_evpn`, or
  an attempt to dispatch NATGateway directly to `cudn_evpn` instead of through
  a capable Fabric Manager.

##### Expected results

- Capability is not advertised or request is rejected.
- No unsupported manager/job/backend operation is dispatched.

## Graduation gate

- All Phase 1 validation bullets map to unit/integration tests.
- First-Subnet CUDN/VM, additional fabric-only Subnet, VM blocking,
  connectivity, deletion, concurrency, and recovery have E2E coverage.
- Every Phase 1 limitation has a negative test or provider preflight check.
