# Testplan — K8s-only Networking Manager

## Overview

- **Feature:** K8s-only Networking Manager (OSAC-1433 manager split)
- **Source PRD:** [prd.md](prd.md)
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking design](../OSAC-1433-unified-networking/design.md),
  including the [connected-only deployment support boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary)
- **Shared tests:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Requirements covered:** FR-1 through FR-9 and NFR-1 through NFR-4
- **Total test cases:** 13
- **Scope:** Provider registration, complete manager profile, direct K8s dispatch,
  default behavior, VMaaS/BMaaS/CaaS integration, strict readiness,
  create/read/delete-only behavior, and failure recovery.

The Unified Networking test plan remains authoritative for common resource
fields, IPv4 formats, typed references, default precedence, attachment
cardinality, policy semantics, deletion guards, and strict dependency-ready
creation. This plan tests the K8s-only profile's concrete implementation and
its interaction with those shared rules.

The following shared cases are executed for this profile and are not replaced
by the profile-specific cases: `TC-R1-05` (provider-owned ExternalIPPool
ownership), `TC-R2-01`, `TC-R2-02`, `TC-R2-04`, and `TC-R2-05` (common field and
format validation), `TC-R3-00`, `TC-R3-01`, and `TC-R3-02` (defaults and typed
references), `TC-R4-01` through `TC-R4-04` (strict readiness), `TC-R5-01`
through `TC-R5-03` (policy behavior), `TC-R6-01` and `TC-R6-02` (operation and
immutability rejection), `TC-R7-01` (deletion guards), `TC-R8-01` (automatic
ExternalIP lifecycle), `TC-R9-01` (CLI parity), and `TC-R10-01` through
`TC-R10-03` (retry and recovery). They run against K8s-only resources with the
provider/tenant actors and backend adapters defined here.

## Execution strategy

- **Unit:** Parse the manager registration, validate the complete profile and
  topology, build the single-target dispatch plan, select AAP templates/roles,
  and validate all resource/workload requests.
- **Integration:** Use real persistence and API admission with envtest/Kind
  CRDs, a fake K8s manager/AAP controller, controllable CUDN/NetworkPolicy/
  MetalLB status, direct CR admission, default-networking reconciliation, and
  injected manager failures.
- **E2E:** Use a connected single-hub OpenShift deployment with the shipped
  K8s-only profile to verify all resource and workload flows. Use real CUDN,
  complete policy adapters, MetalLB, OSAC controllers, and CLI/API clients;
  an unfinished backend may be verified through its successful no-op AAP role.

## Test cases

### FR-1: Provider topology and manager registration

#### TC-FR1-01: Connected single-hub IPv4 K8s-only registration

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-1 | AC-1, AC-2 | IC-1 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- Provider inventory reports exactly one active hub and connected deployment
  mode.
- The `k8s_only` manager ConfigMap exists, has the K8s-manager label, and
  advertises `addressFamily: ipv4`.

##### Steps

1. Create a NetworkClass with `k8s_manager: k8s_only` and no
   `fabric_manager`.
2. Read NetworkClass status and the resolved manager plan.
3. Repeat with zero hubs, two hubs, air-gapped mode, IPv6 capability, and a
   missing/disabled/wrong-type manager registration.

##### Expected results

- The connected single-hub IPv4 NetworkClass is accepted and reports
  `addressFamily: ipv4`.
- Zero hubs, multiple hubs, air-gapped mode, IPv6, a missing manager, a
  disabled manager, and a wrong-type ConfigMap return the documented provider
  configuration precondition error before any tenant resource is provisioned.
- The NetworkClass contains one K8s manager target and no Fabric target.

### FR-2: Complete manager declaration

#### TC-FR2-01: No partial resource or workload declarations

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-2 | AC-3 | IC-1 | Unit, integration | critical | automated |

##### Preconditions

- A provider can submit manager registrations and read the resolved
  NetworkClass status.

##### Steps

1. Register the shipped K8s-only profile with IPv4 and no resource, policy,
   scope, or service subset declaration.
2. Resolve every canonical networking resource and all three workload service
   flows from that single complete profile.
3. Attempt to register resource, policy, scope, or service subset declarations,
   malformed values, unknown keys, or unsupported address families.
4. Route one unfinished operation through a successful no-op AAP role.

##### Expected results

- The shipped profile resolves to the complete resource and workload contract;
  no per-resource or workload status matrix is produced.
- Every operation receives one K8s target, including NetworkACL, NATGateway,
  BMaaS, and CaaS operations.
- A partial manager declaration rejects provider registration; it never creates a
  partial tenant API.
- A successful no-op still creates the normal job/target result.

### FR-3: Canonical resource implementation

#### TC-FR3-01: All resources use the documented K8s entrypoint

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-3 | AC-4, AC-8 | IC-2 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- The shipped K8s-only profile is admitted as a complete manager profile.
- Test fixtures can provide Ready VirtualNetwork, Subnet, policy, and pool
  dependencies as required by each resource.

##### Matrix

| Resource | Expected K8s entrypoint | Ready condition |
|---|---|---|
| VirtualNetwork | `cudn_net` | Logical VN is Ready; K8s network objects are materialized by a Ready child Subnet. |
| Subnet | `cudn_net` | Parent VN is Ready, and its labeled Namespace plus Layer2 `ClusterUserDefinedNetwork` are accepted and observable. |
| SecurityGroup | complete `network_policy` adapter | All OSAC SecurityGroup rules are installed in the applicable Subnet namespaces and reported Ready. |
| NetworkACL | `network_policy` ACL adapter | Stateless ACL rules are installed at the Subnet boundary and reported Ready. |
| ExternalIPPool | `metallb_l2` | MetalLB `IPAddressPool` and `L2Advertisement` are accepted and ready. |
| ExternalIP | `metallb_l2` | A parking `LoadBalancer` Service reports one allocated IPv4 address. |
| ExternalIPAttachment | `metallb_l2` plus service-specific adapter | A target workload binding reports Ready. |
| NATGateway | `nat_gateway` | SNAT state is reported Ready, or the development no-op returns success. |

##### Steps

1. Create each resource with Ready dependencies.
2. Capture the dispatch plan, persisted routing metadata, AAP template,
   selected role, and job variables.
3. Complete the fake manager operation and read status.
4. Repeat the create/delete operation after a controller restart.
5. In E2E, inspect the backend objects: the Subnet Namespace labels and
   Layer2 `ClusterUserDefinedNetwork`; the SecurityGroup adapter's policy
   objects; the MetalLB `IPAddressPool` and `L2Advertisement`; the ExternalIP
   parking `LoadBalancer` Service and allocated IPv4; and the attached
   workload-namespace `LoadBalancer` Service.
6. In E2E, create a VM with the supported single attachment and verify it has
   exactly one KubeVirt `l2bridge` interface and an IPv4 address in the
   selected Subnet. Verify same-VirtualNetwork connectivity, cross-VN
   isolation, an allowed SecurityGroup flow, denial of an unmatched flow, and
   stateful return traffic. Verify the allocated ExternalIP reaches the VM
   through the attached Service.

##### Expected results

- Each canonical resource creates exactly one K8s target and one operation-
  specific AAP job.
- The persisted generic
  `osac.openshift.io/implementation-strategy` annotation contains the K8s
  manager name; `osac.openshift.io/k8s-implementation-strategy` is absent.
- The operation-specific template is selected independently from the manager
  role, and the AAP resource payload is the complete OSAC resource.
- The resource becomes Ready only after the K8s target succeeds; retries do
  not create a second backend object or duplicate allocation.
- Delete invokes the persisted K8s target and no nonexistent Fabric target.
- E2E confirms the concrete CUDN, policy, and MetalLB objects and their
  readiness, not only the persisted OSAC status.
- E2E confirms the VM dataplane and external access behavior. A status-only
  success without the expected interface, IPv4 address, policy enforcement, or
  Service path fails the test.

### FR-4: Policy and NAT resource dispatch

#### TC-FR4-01: NetworkACL and NATGateway use the normal dispatch contract

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-4 | AC-5 | IC-4 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- The shipped profile is admitted as a complete manager profile.
- Valid Ready dependencies are available so dispatch, not readiness, is being
  tested.

##### Steps

1. With the shipped profile, create a NetworkACL for a Ready Subnet.
2. Create a NATGateway with a Ready VirtualNetwork and Allocated ExternalIP.
3. Repeat through direct API, CLI, provider-created default flow, Catalog or
   Template materialization, and direct hub CR submission.
4. Route either backend operation through a temporary successful no-op AAP
   role and repeat.

##### Expected results

- Each request is admitted, creates one K8s target and one AAP job, and becomes
  Ready after the real adapter or approved no-op succeeds.
- No Fabric fallback is called and MetalLB is not treated as SNAT.
- A partial manager registration is rejected as provider configuration before
  NetworkClass readiness, not as a tenant resource error.

### FR-5: Direct dispatch without fallback

#### TC-FR5-01: Tenant cannot override K8s-only dispatch

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-5 | AC-4, AC-8 | IC-2, IC-4 | Unit, integration, E2E | high | automated |

##### Preconditions

- A tenant can submit public requests and a provider can submit direct hub CRs.
- At least one canonical K8s-only resource exists or can be created with Ready
  dependencies.

##### Steps

1. Supply a tenant manager name, Fabric manager name, generic implementation
   annotation, K8s-specific annotation, or combined strategy value on create,
   update, patch, and direct CR requests.
2. Attempt to submit a manager subset declaration or set provider-owned status
   to Ready.

##### Expected results

- All caller-supplied routing, subset, and status values are rejected or
  ignored according to the shared API contract; they never alter the target.
- K8s-only resources retain exactly one K8s target and no Fabric target.
- Network-owned update, patch, and replace operations are rejected; only
  create, read, and delete are available to callers.

### FR-9: Admission and failure behavior

#### TC-FR9-01: Strict Ready dependency admission applies to K8s-only creates

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-9 | AC-4, AC-8 | IC-4 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- Fixtures can place each referenced VN, Subnet, SecurityGroup, ExternalIPPool,
  ExternalIP, target workload, and manager job in Pending, Failed, Deleting,
  Ready, or Allocated states.

##### Steps

1. Attempt Subnet creation while the VirtualNetwork is Pending, Failed, or
   Deleting.
2. Attempt SecurityGroup creation while the VirtualNetwork is not Ready.
3. Attempt ExternalIP allocation while its pool is not Ready.
4. Attempt ExternalIPAttachment while its ExternalIP or target is not Ready.
5. Attempt a workload with a non-Ready resolved Subnet or SecurityGroup.
6. Repeat the allowlisted OSAC-owned automatic ExternalIP flow.

##### Expected results

- Each tenant-created request returns `FailedPrecondition` with field,
  blocker identity, observed state, required state, and remediation.
- Rejected requests persist no dependent object, reserve no capacity, create
  no CR, and dispatch no K8s job.
- Only the allowlisted OSAC-owned automatic ExternalIP/attachment flow may
  enter Pending after its Ready pool and capacity checks; no tenant-created
  resource or default NATGateway uses that exception.

### NFR-1: Deterministic one-target dispatch

#### TC-NFR1-01: One target and one job are used for each canonical resource

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| NFR-1 | AC-4, AC-8 | IC-2 | Unit, integration, E2E | critical | automated |

##### Preconditions

- The shipped K8s-only profile is admitted and a canonical resource has Ready
  dependencies.
- Both provider and tenant clients are available. The provider owns
  ExternalIPPool create/delete; the tenant can read and reference the pool but
  cannot create, replace, update, patch, or delete it.

##### Steps

1. As provider, create and delete an ExternalIPPool while observing the
   dispatch plan, MetalLB objects, and AAP events.
2. As tenant, read/list and reference the provider-created pool from a valid
   ExternalIP or workload request.
3. As tenant, attempt ExternalIPPool create, update, patch, replace, and
   delete; repeat through the CLI and direct API.
4. Create and delete each remaining canonical tenant resource while observing
   the dispatch plan and AAP events.
5. Repeat after a controller restart and while a manager lookup is delayed.

##### Expected results

- Each operation contains exactly one K8s target and one AAP job.
- No Fabric target, second job, or combined strategy value is created.
- Read/list does not launch a job or require a new manager lookup.
- Provider pool create/delete succeeds; tenant pool create/delete and every
  tenant pool mutation fails authorization/provider-ownership validation before
  persistence, and the existing pool backend objects remain unchanged.

### NFR-2: Idempotent retry and recovery

#### TC-NFR2-01: K8s manager failure and retry are idempotent

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| NFR-2 | AC-8 | IC-2 | Unit, integration, E2E | high | automated where environment permits |

##### Preconditions

- A canonical K8s-only resource has been admitted with one persisted K8s target
  and a controllable AAP/K8s manager response.

##### Steps

1. Make a K8s job Pending, then Failed, then successful.
2. Restart the controller between each state transition.
3. Retry the original API request and reconciliation.
4. Delete after NetworkClass lookup is unavailable.

##### Expected results

- Pending and Failed status retains the documented condition and retries the
  same K8s target.
- A successful retry adopts only an object with the same immutable identity,
  owner, and network spec; it does not duplicate it.
- Delete uses persisted target metadata and does not invent a Fabric target.
- A transient manager lookup failure does not make read/list launch a job.

### FR-6: VMaaS workload eligibility

#### TC-FR6-01: VMaaS uses the complete K8s-only VM surface

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-6 | AC-6 | IC-3 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- VMaaS is enabled and the K8s-only manager is admitted as a complete
  networking/workload profile.
- A Ready VN, Subnet, and SecurityGroup are available.

##### Steps

1. Create a Ready VN, Subnet, and SecurityGroup in K8s-only mode.
2. Create a VM with omitted, empty, partial, and complete typed attachment
   input according to the VMaaS contract.
3. Attempt a second attachment, `primary: false`, IPv6, an ACL attachment,
   and a non-Ready reference.
4. Route one VM operation through the approved successful no-op AAP role.
5. In E2E, inspect the resulting KubeVirt VM/VMI, its single `l2bridge`
   interface, the selected CUDN namespace, and the discovered IPv4 status.

##### Expected results

- VM creation succeeds through the complete K8s manager profile and only with
  the VMaaS-supported zero-or-one list-shaped
  `network_attachments` contract and the shared defaulting rules.
- `primary` remains in the wire contract for compatibility but no explicit
  `primary: false` is accepted; the single entry is implicitly primary.
- Invalid cardinality, fields, formats, policy references, and readiness fail
  before VM or network side effects.
- An unfinished VM operation uses its normal target/job path and no Fabric
  fallback is attempted.

### FR-7: BMaaS and CaaS workload integration

#### TC-FR7-01: BMaaS and CaaS flows use the complete K8s-only profile

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-7 | AC-6 | IC-3 | Unit, integration, E2E | critical | automated where environment permits |

##### Preconditions

- BMaaS and CaaS APIs are enabled, and shared K8s-only resources can be made
  Ready.

##### Steps

1. In K8s-only mode, create BMaaS and CaaS workloads with valid shared network
   resources.
2. Repeat one BMaaS and one CaaS operation through the development no-op AAP
   role.
3. Attempt direct private CR creation for each workload.

##### Expected results

- BMaaS and CaaS are admitted through their service-specific shared flows and
  dispatch to the K8s target.
- The development no-op still creates the normal job and status transition.
- Invalid fields or non-Ready dependencies fail before workload or dependent
  resource persistence; no workload is partially persisted.

### FR-8: Defaults and client parity

#### TC-FR8-01: Default networking follows the complete K8s-only manager contract

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| FR-8 | AC-7 | IC-4 | Unit, integration, E2E | high | automated where environment permits |

##### Preconditions

- A valid provider NetworkClass with required default IPv4 CIDRs exists.
- Tenant onboarding/default-networking reconciliation is enabled.

##### Steps

1. Onboard a tenant with the shipped profile and valid NetworkClass defaults.
2. Observe the default VN, Subnet, and SecurityGroup decisions and verify their
   K8s backend objects and readiness.
3. Verify that the shipped profile creates the default NetworkACL and the
   provider-defined default networking resources through the K8s target; no
   default ExternalIP is created unless the shared onboarding flow requests
   one.
4. Create a VM with `auto_external_ip_attachment=true` and verify that its
   OSAC-owned ExternalIP and ExternalIPAttachment are created as children only
   after the VM and pool prerequisites are satisfied.
5. Repeat with NetworkACL or NATGateway routed through the development no-op
   AAP role, including the shared ExternalIP/NAT ownership flow.

##### Expected results

- Default VN and Subnet use `cudn_net` and become Ready through the K8s target.
- Default SecurityGroup and NetworkACL are created through their complete
  adapters. NATGateway follows the shared default-networking flow.
- The VM's automatic ExternalIP and ExternalIPAttachment are marked and owned
  as OSAC-created workload children, and are cleaned up by the shared automatic
  child flow rather than treated as tenant defaults.
- The complete profile follows the normal shared dependency checks rather than
  a K8s-only special case.

### NFR-3: Tenant cannot override provider routing

#### TC-NFR3-01: CLI and direct API resolve the same profile

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| NFR-3 | AC-1, AC-3 | IC-1, IC-4 | Unit, integration, E2E | high | automated where environment permits |

##### Preconditions

- Provider CLI and direct provider API clients are available, together with a
  tenant client that cannot access provider-only configuration.

##### Steps

1. Use the provider CLI to create/read/list the K8s-only NetworkClass.
2. Use the direct provider API with the same configuration.
3. Use tenant CLI/API requests for every canonical resource and workload
   service.

##### Expected results

- CLI and API produce the same manager, target, status, and error values.
- Tenant CLI does not expose manager selection or dispatch-strategy flags.
- Every resource and workload request follows the complete manager contract;
  invalid fields and non-Ready dependencies fail before persistence in both
  clients.

### NFR-4: Shared operation and readiness contract

#### TC-NFR4-01: Only create, read, and delete are exposed for network-owned data

| Story | AC | Interface Change | Test type | Priority | Automation |
|---|---|---|---|---|---|
| NFR-4 | AC-8 | IC-4 | Unit, integration, E2E | critical | automated |

##### Preconditions

- A canonical K8s-only resource and VM exist with Ready dependencies.

##### Steps

1. Invoke update, patch, replace, and network-field mutation for the resource
   and workload attachment.
2. Invoke create, read/list, and delete in valid leaf-first order.
3. Attempt parent deletion while a K8s-only child or workload reference
   remains.

##### Expected results

- Every network-owned update, patch, replace, and attachment mutation returns
  the shared unsupported-operation error, and persisted spec and backend state
  remain unchanged.
- Valid create, read/list, and leaf-first delete operations remain available.
- A parent with a reverse reference returns `FailedPrecondition` naming the
  blocking resource and does not start deletion or cascade to the child.

## Graduation gate

- Every PRD functional and non-functional requirement has at least one test
  case above.
- Every canonical resource has unit, integration, and E2E coverage for create,
  read, delete, readiness, and retry behavior.
- Every invalid resource and workload path has a negative test proving no
  partial persistence, capacity reservation, CR, or AAP job.
- Shared validation suites are linked and run for K8s-only resources, including
  IPv4 formats, typed references, defaults, attachment cardinality, policy
  rules, update rejection, and leaf-first deletion.
- The test suite proves that no Fabric fallback or invented second target is
  used in K8s-only mode.

## Gaps

None. The common resource contract is inherited from Unified Networking and
the shared test cases are named explicitly above. The profile-specific plan
covers the manager registration and workload operation paths, concrete CUDN,
  policy, and MetalLB objects, VM dataplane behavior, provider/tenant pool
  ownership, defaults, complete resource/workload dispatch, strict readiness, retries, and
  deletion/immutability behavior. Any incomplete profile or backend readiness
  assertion is a profile failure, not an accepted gap.

## Summary

There are 13 test cases: 9 critical and 4 high priority. Four cases are fully
automated unit/integration checks; nine are automated where the required
OpenShift, CUDN, SecurityGroup adapter, MetalLB, or dataplane environment is
available.
