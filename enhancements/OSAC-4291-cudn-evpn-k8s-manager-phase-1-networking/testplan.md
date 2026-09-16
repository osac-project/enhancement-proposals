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
  tenant reference/defaulting validation. It also owns strict dependency-ready
  admission: a Subnet requires a Ready VirtualNetwork, while the Subnet may
  remain Pending only for its own ordered fabric-to-CUDN provisioning. The
  only Pending dependency exception is OSAC-owned automatic ExternalIP access.
- **Manual prerequisites:** OCP with OVN-Kubernetes, FRR, NMState, VTEP,
  RouteAdvertisements, BGP underlay, gateway MAC coordination, and a real
  Netris fabric. These are installation prerequisites, not tenant API
  features.
- **Explicit limits:** IPv4 only; one CUDN/VM-capable Subnet per
  VirtualNetwork; no VM placement after multiple Subnets exist; no automatic
  VTEP or gateway-MAC provisioning; no multi-cluster, secondary-CUDN,
  multi-NIC, same-cluster VM-to-VM inter-Subnet routing, or east-west feature.

## Execution strategy

- **Unit:** fulfillment-service topology validation, complete-manager
  registration resolution, operator phase/state logic, VNI/ConfigMap parsing, CUDN
  readiness, VM placement, and deletion guards.
- **Integration:** real PostgreSQL and validation path, envtest/Kind CRDs and
  controllers, fake Netris/AAP jobs, documented ConfigMap data handoff, fake
  CUDN/namespace/MetalLB readiness, failure injection, and race tests.
- **E2E:** real OCP/OVN-K/FRR/Netris environment verifying CUDN, EVPN routes,
  VM-to-fabric traffic, fabric-only Subnets, VM blocking, and cleanup.

## Test cases

### R1: Provider manager registration and complete manager contract

#### TC-R1-01: Valid `cudn_evpn` registration is accepted

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-1 | Unit, integration, E2E-preflight | critical | automated |

##### Steps

1. Install the provider ConfigMap declaring `cudn_evpn`.
2. Verify IPv4 support, IPv6 disabled, create/read/delete operations, the
   complete shared resource and VMaaS/BMaaS/CaaS service contract, and the
   separate Phase 1 single-subnet VM-placement validation.
3. Create a NetworkClass with `fabric_manager=netris` and
   `k8s_manager=cudn_evpn`.
4. Create a NetworkACL for a Ready Subnet and inspect the dispatcher calls.
5. Create a SecurityGroup for a Ready VirtualNetwork and inspect the dispatcher
   calls.
6. Create a Ready VirtualNetwork and an Allocated, unconsumed ExternalIP, then
   create a NATGateway through the combined NetworkClass.
7. Submit one representative VMaaS, BMaaS, and CaaS operation and inspect that
   the manager receives the normal operation. Execute one unfinished operation
   through a successful no-op AAP role.

##### Expected results

- Registration succeeds with the complete shared manager contract; no
  per-resource, policy, scope, or service capability matrix is loaded.
- NetworkACL and SecurityGroup operations are dispatched to every configured
  manager target. Kubernetes NetworkPolicy is not substituted for the shared
  NetworkACL contract.
- VMaaS, BMaaS, and CaaS operations are all dispatched to the manager target;
  an unfinished provider implementation may return a successful no-op AAP
  result.
- NetworkClass is accepted only after required installation prerequisites are
  available.
- `cudn_evpn` is not selected as Default Networking's default manager when
  required manual prerequisites are absent.
- NATGateway is dispatched to every configured manager target. Its provider
  operation may be a successful no-op while EVPN-specific NAT integration is
  unfinished.

#### TC-R1-02: Incomplete or tenant-controlled registration is rejected

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-1 | Unit, integration | critical | automated |

##### Cases

- unregistered/incomplete manager;
- IPv6/dual-stack capability;
- missing VTEP/FRR/BGP prerequisite;
- tenant tries to select manager, VNI, VTEP, gateway MAC, or skip annotation;
- a partial manager registration that omits any required resource, policy, or
  VMaaS/BMaaS/CaaS service from the complete contract;
- a tenant-controlled attempt to select a manager-specific implementation,
  resource target, service target, or dispatch strategy.

##### Expected results

- Provider misconfiguration or unsupported tenant input fails before backend
  provisioning.
- Partial manager registration and tenant-controlled routing are rejected as
  provider configuration or authorization errors. A tenant resource or
  workload request is never rejected because a manager lacks a resource,
  policy, scope, or service implementation declaration; an unfinished operation is
  represented by its normal successful no-op AAP result.

#### TC-R1-03: Subnet admission requires a Ready VirtualNetwork

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-3 | Unit, integration, E2E rejection | critical | automated |

##### Cases

- Hold the parent VirtualNetwork in `Pending`, `Failed`, and `Deleting` and
  submit the first CUDN-EVPN Subnet through the public API.
- Repeat through the direct hub-CR admission path.
- Advance the VirtualNetwork to `Ready` and retry the same request.

##### Expected results

- Each non-Ready parent returns `FailedPrecondition` identifying the Subnet's
  `spec.virtual_network` field, the VirtualNetwork identity, observed state,
  required `Ready` state, and wait-and-retry remediation.
- No Subnet, hub CR, CUDN, namespace, ConfigMap, manager job, or AAP job is
  created for the rejected request.
- After the VirtualNetwork is Ready, Subnet admission succeeds exactly once;
  the Subnet may then remain Pending while its own fabric-to-CUDN sequence
  runs.

### R2: Sequential fabric-to-CUDN provisioning

#### TC-R2-01: First Subnet creates fabric and CUDN in order

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-3, IC-5 | Unit, integration, E2E | critical | automated |

##### Steps

1. Create a VirtualNetwork; verify no fabric or CUDN provisioning occurs.
2. Wait until the VirtualNetwork is `Ready`.
3. Create its first Subnet.
4. Observe fabric VPC/VNet job completion.
5. Read the documented VNI ConfigMap output.
6. Observe K8s manager CUDN/namespace/IPAddressPool creation.
7. Wait for CUDN and Subnet readiness.

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
- Both configured managers are dispatched for the second Subnet; the
  k8s-manager operation completes through the successful no-op path.
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

#### TC-R3-04: Fabric-only Subnets retain the complete target plan

| Interface | Test type | Priority | Automation |
|---|---|---|---|
| IC-2, IC-3 | Unit, integration, E2E | high | automated |

##### Expected results

- A later Subnet is fabric-only under the Phase 1 topology rule, while the
  normal fabric and k8s manager targets are both present in the dispatch plan.
- The k8s-manager create operation is a successful no-op and creates no CUDN,
  namespace, or other k8s resource for that Subnet.
- No tenant or provider annotation can remove a manager target or select a
  subset of the shared API.
- Deletion records the normal k8s-manager successful no-op before fabric
  cleanup.

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
- Exactly that Subnet receives the CUDN; later Subnets are fabric-only, while
  their normal k8s-manager operations complete through the successful no-op
  path.
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
- Fabric-only Subnet: fabric VNet plus a successful k8s-manager no-op; no CUDN
  object is created or deleted.
- VirtualNetwork/VPC is deleted only after every direct shared-network blocker is
  gone: child Subnets, SecurityGroups, NetworkACLs, and NATGateways where those
  resources are provided by the combined NetworkClass. The CUDN-specific
  controller additionally waits for its provider-owned CUDN/namespace state.
- CUDN deletion failure prevents fabric deletion and leaves a visible failed
  deletion state.
- Attempting to delete a VirtualNetwork while a Subnet remains is rejected;
  the CUDN, namespace, Subnet, and fabric state remain unchanged. CUDN cleanup
  occurs only from the admitted owning Subnet deletion path.

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
- CaaS cluster creation and private-worker provisioning through the shared
  manager contract, including a temporary successful no-op provider path;
- update/patch/replace of network-owned fields;
- a tenant-controlled attempt to select a manager-specific implementation or
  dispatch target.

##### Expected results

- Invalid tenant-controlled routing is rejected before persistence or dispatch.
- The normal manager job is dispatched for every canonical operation; an
  unfinished provider operation may complete as a successful no-op.

## Graduation gate

- All Phase 1 validation bullets map to unit/integration tests.
- First-Subnet CUDN/VM, additional fabric-only Subnet, VM blocking,
  connectivity, deletion, concurrency, and recovery have E2E coverage.
- Every Phase 1 limitation has a negative test or provider preflight check.
