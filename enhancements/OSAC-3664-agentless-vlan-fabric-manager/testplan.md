# Testplan — OSAC-4307

## Overview

**Last updated:** 2026-09-24

**Mandatory support boundary:** Every supported profile requires each Subnet's
associated NetworkACL to be actively enforced before the Subnet can be Ready.
The agentless backend does not implement enforcement, so this milestone cannot
serve the shared networking API or be selected as a supported fabric manager.
Reject selection; if a mismatch reaches reconciliation, the Subnet and its
dependents remain not Ready. No API-ready workload/data-plane case is executable
against this backend in this milestone. Any future positive case that asserts a
Subnet or dependent resource is Ready must provision its associated NetworkACL
and verify active enforcement before readiness.

**Current positive data-plane cases:** TC-FR3-01 through TC-FR3-03 and
TC-NFR3-01 through TC-NFR3-02 are raw topology tests only. Their fixtures create
VLAN/namespace/route state directly; they must not create API Subnets, attach API
workloads, assert Ready status, or claim NetworkACL enforcement. Other positive
API/resource cases in this test plan are future acceptance criteria and are
deferred until this backend implements NetworkACL enforcement.


- **Feature:** OSAC-3664 — Fabric Manager — Agentless VLAN
- **Design task:** OSAC-4307
- **Design:** [design.md](design.md)
- **Authority:** This requirement-anchored test plan is part of the design PR;
  the design document's Test Plan section is only a short strategy summary.
- **Total test cases (including future-gated cases):** 35
- **Currently executable cases:** 8 (selection/rejection and raw topology only)
- **Deferred until NetworkACL enforcement:** 27
- **Requirements covered:** 13 of 13
- **Interface changes covered:** 6 of 6

## Test Cases

### FR-1: Backend selection

#### TC-FR1-01: Keep agentless_net ineligible without NetworkACL enforcement

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- The installer values enable the agentless fabric-manager entry.
- No agentless manager ConfigMap exists.

##### Steps

1. Render and apply the operator Helm configuration.
2. Inspect the generated fabric-manager ConfigMap and the NetworkClass
   capability state.

##### Expected Results

- A candidate ConfigMap may identify agentless_net and its IPv4 topology
  capability, but it is not advertised as a supported fabric manager.
- The registration cannot claim NetworkACL enforcement.
- IPv6 and dual-stack capabilities are absent.

#### TC-FR1-02: Reject agentless_net as a supported fabric manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | manual |

##### Preconditions

- Every supported networking profile requires NetworkACL enforcement.
- agentless_net does not implement or advertise that enforcement.

##### Steps

1. Attempt to select agentless_net through provider configuration and through a
   NetworkClass reference.
2. Submit a Subnet request against a fixture containing a stale agentless
   selection to exercise controller-side rejection.

##### Expected Results

- Both selection attempts are rejected because agentless_net cannot satisfy the
  mandatory NetworkACL readiness contract.
- A stale selection does not dispatch a data-plane job; the Subnet and dependent
  resources remain not Ready.
- Tenant API requests do not gain backend-specific fields.

#### TC-FR1-03: Keep mismatched Subnets and dependents not Ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- agentless_net is registered but does not advertise NetworkACL enforcement.
- A Subnet has a required NetworkACL association whose rules are not enforced.

##### Steps

1. In a controller test, inject a stale selection of agentless_net to exercise
   the defensive readiness check.
2. Attempt to attach a workload to the affected Subnet and observe Subnet and
   attachment status and backend dispatch.

##### Expected Results

- The stale selection is rejected before a supported backend dispatch.
- The Subnet and dependent attachment remain not Ready; the workload is not
  permitted to use the Subnet.
- No ACL-unaware permit-all fallback is applied or treated as successful.

### FR-2: Fabric-manager-agnostic networking (future after NetworkACL support)

These scenarios are future acceptance criteria. Their Ready outcomes are valid
only after this backend implements mandatory NetworkACL enforcement and every
Subnet used by a positive case has an associated, actively enforced policy.

#### TC-FR2-01: Create the existing networking resource set

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- Run this case only after `agentless_net` implements mandatory NetworkACL
  enforcement and is eligible for selection in NetworkClass.
- The test tenant has the required authorization and tenant metadata.
- A Cloud Infrastructure Admin fixture can create the provider-scoped
  ExternalIPPool; the tenant fixture cannot create or update that pool.
- The test tenant can create tenant-scoped networking resources.
- A test host is available for creating a BareMetalInstance on the Subnet.
- The ExternalIPPool has capacity for at least two distinct allocations.

##### Steps

1. Create an ExternalIPPool with the provider-admin fixture.
2. Create a VirtualNetwork with the tenant fixture.
3. Create a NetworkACL scoped to that VirtualNetwork, with explicit ingress
   and egress rules for the flows under test. Wait until its policy is active
   and it reaches Ready.
4. Create a Subnet whose `spec.network_acl` explicitly references that
   same-VirtualNetwork ACL. Wait until the policy is enforced on the Subnet and
   the Subnet reaches Ready.
5. Create a BareMetalInstance on the Ready Subnet with the test host fixture.
   Wait until its primary private address is available.
6. Create two ExternalIPs from the pool and wait until both are Allocated with
   distinct addresses.
7. Create an ExternalIPAttachment using the first ExternalIP and the
   BareMetalInstance target. Create a NATGateway using the second ExternalIP
   and the VirtualNetwork.
8. Attempt to create or update the ExternalIPPool with the tenant fixture.
9. Poll the corresponding CRs and fulfillment-service resources.

##### Expected Results

- Each request is accepted without an agentless-specific API field.
- The tenant cannot create or modify the provider-scoped ExternalIPPool.
- The Subnet references the READY NetworkACL in its VirtualNetwork, and its
  readiness follows confirmation that the policy is enforced.
- Each ExternalIP reaches Allocated with a distinct address. The
  ExternalIPAttachment reaches Ready after the target address is available and
  DNAT succeeds; the NATGateway reaches Ready after SNAT succeeds.
- Each tenant-scoped CR retains both required tenant-isolation annotations.

#### TC-FR2-02: Preserve the existing API contract for external access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- Two allocated ExternalIPs have distinct addresses in status.
- A target resource has a primary private address.
- The target Subnet and its NetworkACL are Ready, with the policy enforced.

##### Steps

1. Create an ExternalIPAttachment with the first ExternalIP and the existing
   target fields.
2. Create a NATGateway with the existing VirtualNetwork and the second
   ExternalIP.
3. Query the resources through the existing API.

##### Expected Results

- The requests contain no backend-specific fields.
- ExternalIPAttachment reports the assigned external address through the
  existing status path and reaches Ready only after DNAT succeeds.
- NATGateway reports Ready after its SNAT job reaches a terminal success state.

### FR-3: Multiple Subnets per VirtualNetwork (raw topology tests only)

#### TC-FR3-01: Keep same-VLAN traffic in one broadcast domain (topology only)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The raw topology fixture creates one VirtualNetwork namespace and one VLAN.
- Two test interfaces are bound to the VLAN; no OSAC API objects are created.

##### Steps

1. Send ARP and IPv4 traffic between the two interfaces.
2. Inspect the switch VLAN and namespace interface membership.

##### Expected Results

- Both interfaces use the same VLAN and broadcast domain.
- ARP resolves without a routed hop.
- IPv4 traffic reaches the peer in the raw topology fixture. No Subnet API
  readiness or workload support is asserted.

#### TC-FR3-02: Route between raw VLAN segments (topology only)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The raw topology fixture creates two VLAN segments and their VirtualNetwork
  namespace routes; no OSAC API objects or ACL readiness conditions are used.

##### Steps

1. Send a flow between the raw VLAN segments.
2. Repeat the traffic attempt after reconciliation and a controller restart.

##### Expected Results

- The raw flow follows the namespace routing table.
- This case validates topology only; it does not represent an API-ready Subnet,
  a workload attachment, or NetworkACL enforcement.

#### TC-FR3-03: Isolate raw overlapping VirtualNetworks (topology only)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The raw topology fixture uses overlapping IPv4 address ranges in separate
  namespaces and attaches test interfaces directly; no OSAC API objects are
  created.

##### Steps

1. Attempt direct traffic from one private Subnet address to the other.
2. Inspect namespace routes and inter-VN interfaces.

##### Expected Results

- No private route connects the two VirtualNetwork namespaces.
- Direct traffic to the other private address receives no successful response.
- Each namespace contains only its own VirtualNetwork routing state.

### FR-4: Automatic IP assignment (future after NetworkACL support)

#### TC-FR4-01: Assign a DHCP address to a bare-metal attachment

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- A Ready Subnet has the per-VN dnsmasq service bound to its VLAN interface,
  with a rendered range that excludes the gateway address.
- A BareMetalInstance has a network attachment referencing that Subnet.

##### Steps

1. Provision the host.
2. Run the generic network-attachment job and hand the port to the Subnet VLAN.
3. Reboot or renew DHCP on the host.
4. Run the generic DHCP lease query job.
5. Restart the per-VN dnsmasq service and query the same lease again.

##### Expected Results

- The host receives an IPv4 address inside the Subnet CIDR.
- The lease artifact contains the authoritative port MAC from the
  `osac.openshift.io/interface-macs` annotation, the matching SubnetRef, and IP;
  the MAC matches the attachment's annotation mapping.
- BareMetalInstance status contains the same IP in its network attachment status.
- NetworkHandoffComplete and IPDiscoveryComplete become True.
- The lease survives the dnsmasq restart and the daemon reuses the configured
  lease file rather than assigning a second address.

#### TC-FR4-02: Map multiple DHCP leases to the correct attachments

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A BareMetalInstance has two network attachments on different Subnets.
- The BareMetalHost `osac.openshift.io/interface-macs` annotation maps each
  attached interface to its authoritative MAC.
- The lease artifact contains one entry for each interface and SubnetRef, and
  each entry contains the matching MAC and IP.

##### Steps

1. Submit the completed lease artifact to the feedback path.
2. Observe the BareMetalInstance status.
3. Submit a second artifact that keeps one interface name and SubnetRef but
   replaces its MAC with a stale or another attachment's MAC.
4. Observe the BareMetalInstance status and reconciliation condition.

##### Expected Results

- Each valid status entry retains its original interface and SubnetRef and is
  backed by the matching authoritative MAC.
- Each valid IP address is assigned to the attachment matching both MAC and
  SubnetRef.
- No lease is assigned to a different interface, MAC, or Subnet.
- The MAC-mismatched artifact is rejected; status remains unchanged and IP
  discovery retries instead of accepting the stale or reused interface name.

#### TC-FR4-03: Keep VM address assignment outside AgentlessNet

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A ComputeInstance uses a NetworkClass with agentless fabric and the required
  k8sManager/OVN path.

##### Steps

1. Create the ComputeInstance with an existing network attachment.
2. Observe the VM network status and AgentlessNet job inputs.

##### Expected Results

- OVN supplies the VM address.
- AgentlessNet does not create a fabric-side DHCP address for the VM.
- The attachment contract remains available for the downstream VMaaS flow.

#### TC-FR4-04: Reject duplicate SubnetRef and preserve Subnet reuse

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- `subnet-a` is Ready.
- The BareMetalInstance request contains two physical interfaces that both
  reference `subnet-a`.

##### Steps

1. Submit the BareMetalInstance request through the BMaaS API/CR path.
2. Inspect the validation result and any networking or DHCP-discovery jobs.
3. Submit a second valid BareMetalInstance with one attachment referencing
   `subnet-a`.
4. Observe the second request and its networking/DHCP status.

##### Expected Results

- The request is rejected as an invalid duplicate `subnetRef` attachment before
  network handoff or DHCP discovery begins.
- No AAP network-attachment or DHCP-lease job is launched for the invalid
  request.
- The second valid BareMetalInstance is accepted and can reuse `subnet-a`.
- A valid multi-NIC BareMetalInstance uses a distinct SubnetRef for each
  attachment, and a Subnet remains usable by other BareMetalInstances.

#### TC-FR4-05: Recover the per-VN DHCP service and lease store

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A VirtualNetwork has two Ready Subnets with dnsmasq ranges, gateway
  exclusions, and a valid per-VN lease file.
- A bare-metal interface has a current lease on one Subnet.

##### Steps

1. Stop or corrupt the per-VN dnsmasq configuration or lease file.
2. Reconcile the VirtualNetwork and Subnets and observe the DHCP condition.
3. Restore the valid lease file and restart the supervised dnsmasq service.
4. Run `query_dhcp_lease` for the existing MAC and SubnetRef.

##### Expected Results

- IP discovery remains pending while the daemon or lease file is invalid.
- The role renders the configured ranges and reserved gateway addresses again.
- The daemon restarts with the preserved lease and the same MAC/Subnet receives
  the same valid address without a duplicate lease.

### FR-5: Inbound external access (future after NetworkACL support)

#### TC-FR5-01: Create DNAT after the target address is ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- The target has no primary private address at first, then receives one.
- The target Subnet and its NetworkACL are Ready, with the policy enforced.
- The supported external path is available, and the target Subnet NetworkACL
  explicitly permits the inbound test flow.
- The provider-owned BGP peer is established and can report learned `/32`
  routes.

##### Steps

1. Create the ExternalIPAttachment before the target address is available.
2. Inspect the attachment status and AAP job history.
3. Publish the target's current primary address.
4. Reconcile the attachment and send traffic to the ExternalIP.

##### Expected Results

- No attachment AAP job or DNAT rule is created while the target address is
  absent.
- The attachment remains Pending or Progressing with no unknown DNAT target.
- After the address appears, the controller dispatches the DNAT operation.
- The whole-address DNAT rule and consumer-owned ExternalIP `/32` are present;
  the upstream BGP peer learns the route.
- The attachment remains non-ready if ExternalIP allocation succeeds but the
  DNAT operation fails.
- Inbound data-plane checks require the associated Subnet NetworkACL to be Ready
  and enforced. If the ACL is absent or unready, the attachment remains not Ready.

### FR-6: Outbound external connectivity (future after NetworkACL support)

#### TC-FR6-01: SNAT permitted egress through the NATGateway ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- A NATGateway references that ExternalIP and a Ready VirtualNetwork.
- The VirtualNetwork has two Ready Subnets, and the NATGateway state contains
  both source CIDRs.
- Both source Subnets explicitly reference READY NetworkACLs in the same
  VirtualNetwork, and enforcement is active on both before the NATGateway may
  become Ready.
- Test traffic originates from one of the source Subnets, whose NetworkACL
  permits the egress flow. If enforcement is absent or unready on either source
  Subnet, the NetworkClass is rejected or the dependent NATGateway remains not
  Ready.

##### Steps

1. Send traffic from a Subnet interface to an external endpoint.
2. Inspect the endpoint's observed source address and the NATGateway status.

##### Expected Results

- The endpoint observes the NATGateway ExternalIP as the source address.
- One explicit `SNAT --to-source` rule exists for each source CIDR; no
  host-side MASQUERADE changes the observed source.
- The consumer-owned `/32` route is learned by the provider BGP peer.
- NATGateway status.phase is Ready.

#### TC-FR6-02: Reconcile NAT rules after Subnet churn

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A Ready VirtualNetwork has a Ready NATGateway and one Subnet in
  `nat_gateways.source_cidrs`.
- A fake AAP provider can observe SNAT rule changes and Subnet finalizers.

##### Steps

1. Add a second Subnet to the VirtualNetwork and wait for its VLAN/DHCP state.
2. Inspect NATGateway reconciliation and the source-CIDR revision.
3. Delete the second Subnet and observe NATGateway and Subnet cleanup ordering.

##### Expected Results

- The second CIDR is added to the desired SNAT set before the Subnet is
  reported Ready.
- Deleting the Subnet removes its SNAT rule and updates the revision before
  the Subnet VLAN, gateway, or DHCP state is released.
- The NATGateway remains usable for the first Subnet throughout the churn.

### FR-7: External IP pools (future after NetworkACL support)

#### TC-FR7-01: Allocate an ExternalIP from the agentless state-file pool

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A Cloud Infrastructure Admin creates an IPv4 ExternalIPPool with known
  capacity.

##### Steps

1. Wait for the pool to reach Ready.
2. Create an ExternalIP through the existing API.
3. Wait for the ExternalIP AAP job to commit provider state and inspect the
   allocated-address and provider-result annotations.
4. Read pool and ExternalIP status, reservation state, and agentless state file.

##### Expected Results

- Pool status.total and status.available reflect the configured CIDR capacity.
- ExternalIP status.state is Allocated and status.address contains an address
  from the pool.
- The committed provider-result annotation, `ExternalIP.status.address`, and
  the state-file `external_ips` entry contain the same address keyed by the
  ExternalIP UUID and state digest.
- The fulfillment-service reservation is `COMMITTED` and pool capacity is held
  exactly once.
- The state-file `external_ip_pools` entry records the provider-side pool CIDR.

#### TC-FR7-02: Reject exhausted capacity and restore it on release

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A Ready ExternalIPPool has no available capacity.

##### Steps

1. Attempt to create another ExternalIP from the exhausted pool.
2. Delete an existing ExternalIP and wait for provider `CLEANUP_COMPLETE` or
   `NOT_COMMITTED` to be acknowledged by fulfillment-service.
3. Create another ExternalIP from the pool.

##### Expected Results

- The first create request fails with a capacity/precondition error.
- Pool status.available increases only after the reservation reaches `RELEASED`.
- The subsequent create request receives a newly allocated address, and the
  state file contains exactly one allocation for the new ExternalIP UUID.

#### TC-FR7-03: Preserve pool status during concurrent allocation and reconciliation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- An ExternalIPPool has `status.total=2`, `status.allocated=0`,
  `status.available=2`, and `status.phase=Ready`.
- The fulfillment-service capacity update and ExternalIPPoolReconciler phase
  update can run concurrently.

##### Steps

1. Start an ExternalIP creation and an ExternalIPPool reconciliation that
   updates the phase/conditions at the same time.
2. Wait for both operations to complete, then read the pool status, provider
   annotations, reservation row, and ExternalIP state.

##### Expected Results

- The pool retains `allocated=1` and `available=1` from the capacity update.
- The reconciler's phase and conditions are also present; neither writer
  overwrites fields owned by the other.
- The ExternalIP address in status matches the provider annotation and its
  state-file allocation, with no duplicate allocation after conflict retries.
- The reservation row and pool capacity update are idempotent.

#### TC-FR7-04: Recover an interrupted provider state-file write

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- The AgentlessNet state file has a valid committed generation and `.bak`.
- The test can interrupt a write before, during, and after atomic rename.

##### Steps

1. Inject a process or host failure at each write phase.
2. Restart the provider role and inspect the state file, sidecar lock, and
   backup.
3. Retry allocation and cleanup after selecting the validated generation.

##### Expected Results

- The reader sees either the previous complete JSON or the next complete JSON,
  never truncated content.
- A malformed current file blocks mutation and requires explicit `.bak` restore.
- Concurrent writers serialize on the stable sidecar lock and do not duplicate
  an ExternalIP or release capacity twice.

### FR-8: Networking across all services (future after NetworkACL support)

#### TC-FR8-01: Perform BMF port bind and unbind through the generic contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A Ready Subnet has a recorded VLAN.
- A BareMetalInstance exposes an interface, authoritative MAC, host UID, and
  SubnetRef attachment; the provider provisioning-network ID is configured.

##### Steps

1. Run `playbook_osac_move_network_attachment` with `attach` and the stable
   binding/host/MAC/Subnet/provisioning-network inputs.
2. Verify the port is on the tenant VLAN, reboot the host, and wait for
   `NetworkHandoffComplete` and DHCP discovery.
3. Power off the host and run the same playbook with `detach`.
4. Inspect the Cumulus port, VLAN, and `port_bindings` state.

##### Expected Results

- The AgentlessNet attachment role receives stable host, interface, MAC, Subnet,
  direction, and provisioning-network inputs.
- The switch port is assigned to the Subnet VLAN and the binding is recorded;
  DHCP and handoff readiness follow reboot.
- Detach restores the exact provisioning VLAN, reports
  `NetworkOffboardComplete`, and removes the binding without changing another
  Subnet's VLAN.

#### TC-FR8-02: Accept downstream CaaS and VMaaS attachment inputs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Fixtures represent a CaaS cluster node and a VMaaS ComputeInstance whose
  attachment omits the Subnet field so the existing tenant default must be
  resolved.
- A fake AAP provider captures the selected role arguments.

##### Steps

1. Submit each fixture to the generic attachment and DHCP role contract.
2. Inspect the resolved attachment fields, role argument validation, and
   generated lease-query inputs.

##### Expected Results

- Both fixtures expand the omitted Subnet field to the tenant's default.
- The single CaaS `BareMetalNetworkAttachment` has `primary: true`.
- The single VMaaS attachment is implicitly primary; generic
  `query_dhcp_lease` arguments do not require a `primary` field.
- The AgentlessNet role accepts the contract without a service-specific API
  change.
- Full service provisioning remains assigned to OSAC-1611 and OSAC-3665.

### FR-9: Failure visibility (future after NetworkACL support)

#### TC-FR9-01: Surface a switch-port or VLAN failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- The Cumulus test provider returns a deterministic failure for the requested
  VLAN or access-port operation.

##### Steps

1. Create or attach a resource that requires the failed operation.
2. Poll the resource status and provisioning job history.

##### Expected Results

- The resource does not reach Ready.
- Status.conditions contains a failure reason identifying the fabric operation.
- The job history contains the failed target and provider error.

#### TC-FR9-02: Surface missing or stale DHCP feedback

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- A BMF attachment has completed port handoff.
- The DHCP query returns no matching lease or an artifact from an older
  generation.

##### Steps

1. Run the DHCP lease query and feedback reconciliation.
2. Inspect the attachment/BareMetalInstance status.

##### Expected Results

- The stale or unmatched artifact is ignored.
- Status identifies DHCPLeaseUnavailable or the equivalent diagnostic reason.
- No ExternalIPAttachment DNAT job is dispatched without a current target IP.

#### TC-FR9-03: Block operations during a net-node outage and restore safely

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- A VirtualNetwork, Subnet, NATGateway, and ExternalIPAttachment are Ready.
- The net node has a valid state generation, `.bak`, dnsmasq lease files, and
  provider BGP session.

##### Steps

1. Stop or isolate the net node and attempt a new Subnet, attachment, delete,
   and ExternalIP capacity-release operation.
2. Observe existing resource conditions, finalizers, reservations, and traffic.
3. Restore the net node and allow state, namespaces, dnsmasq, NAT, and BGP to
   rehydrate.

##### Expected Results

- New mutations, cleanup releases, and finalizer removal are blocked with
  `NetNodeUnavailable`; no capacity is released early.
- Existing resources become degraded; active flows may continue only while the
  kernel state remains alive, and conntrack continuity is not promised after
  restart.
- New routes are advertised only after the restored data path is verified, and
  resources return to Ready after reconciliation.

### FR-10: Lifecycle cleanup (future after NetworkACL support)

#### TC-FR10-01: Remove DNAT before releasing an ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- An ExternalIPAttachment is Ready and owns a DNAT mapping.
- The parent ExternalIP is Allocated.

##### Steps

1. Delete the ExternalIPAttachment.
2. Observe the DNAT rule, attachment finalizer, and ExternalIP status.
3. Delete the ExternalIP after the attachment is gone.

##### Expected Results

- The ExternalIP `/32` is withdrawn before DNAT and conntrack cleanup.
- DNAT and owner-specific conntrack state are absent before the ExternalIP is
  released.
- The attachment finalizer is removed only after DNAT cleanup feedback.
- `status.attached` remains true until consumer cleanup is acknowledged.
- Pool capacity increases only after the reservation reaches `RELEASED`.

#### TC-FR10-02: Clean one Subnet/VirtualNetwork without affecting peers

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The first VirtualNetwork has two Ready Subnets, each with VLAN and namespace
  state.
- The second VirtualNetwork has an independent Subnet, VLAN, namespace, and
  test attachment.

##### Steps

1. Delete one Subnet from the first VirtualNetwork and wait for its finalizer
   cleanup to complete.
2. Inspect state-file entries, DHCP state, switch VLANs, namespace interfaces,
   gateway state, and the forwarding baseline for the remaining Subnet.
3. Verify permitted traffic for the remaining Subnet, then delete the first
   VirtualNetwork and inspect the second VirtualNetwork.

##### Expected Results

- The deleted Subnet's DHCP state, VLAN, interfaces, gateway, and
  Subnet-owned state are removed in dependency order, and its VLAN is not
  released before cleanup is confirmed.
- The forwarding baseline for the remaining Subnet continues to permit
  supported traffic after the sibling Subnet is deleted.
- After the first VirtualNetwork is deleted, its remaining child state and
  forwarding state are removed in dependency order.
- The second VirtualNetwork's namespace, VLAN, and connectivity remain present.
- The deleted resources' finalizers are removed only after cleanup feedback.

#### TC-FR10-03: Delay parent-first ExternalIP release until attachment cleanup

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- An ExternalIP is Allocated and its ExternalIPAttachment is Ready with an
  owned DNAT mapping and attachment finalizer.
- The test can request parent-first deletion or issue ExternalIP and
  ExternalIPAttachment deletion concurrently.

##### Steps

1. Request ExternalIP deletion while the attachment still owns DNAT, or issue
   both deletion requests concurrently.
2. Observe ExternalIP status, pool capacity, attachment finalizer, DNAT state,
   and cleanup job feedback.
3. Allow DNAT cleanup feedback to complete and the attachment finalizer to be
   removed.
4. Reconcile the ExternalIP deletion and inspect pool capacity again.

##### Expected Results

- ExternalIP release is rejected or delayed while the attachment owns DNAT or
  retains its finalizer.
- The ExternalIP remains allocated and its pool capacity is not reusable while
  attachment cleanup is incomplete.
- After confirmed DNAT cleanup and finalizer removal, ExternalIP deletion
  releases the address and only then increases pool capacity.

#### TC-FR10-04: Remove NAT before releasing an ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A Ready NATGateway owns explicit SNAT rules and an advertised ExternalIP
  `/32`.
- The parent ExternalIP is Allocated and has no competing consumer.

##### Steps

1. Request NATGateway deletion and ExternalIP deletion concurrently.
2. Observe the BGP route, SNAT rules, conntrack state, NATGateway finalizer,
   reservation state, and pool capacity.
3. Allow route withdrawal and SNAT/conntrack cleanup to complete, then retry
   ExternalIP deletion.

##### Expected Results

- ExternalIP capacity remains held while the NATGateway route or SNAT state
  exists.
- The route is withdrawn before SNAT and conntrack cleanup, and the NATGateway
  consumer reservation remains held until the service acknowledges cleanup.
- Pool capacity increases only after the reservation reaches `RELEASED`.

### NFR-1: IPv4-only capability (future after NetworkACL support)

#### TC-NFR1-01: Reject unsupported IPv6 and dual-stack requests

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- NetworkClass advertises only the agentless_net ipv4 capability.

##### Steps

1. Submit an IPv6 or dual-stack VirtualNetwork or Subnet request.
2. Inspect the API response, resource condition, and AAP job history.

##### Expected Results

- The request is rejected or marked Failed with an address-family diagnostic.
- No fabric AAP job starts for the unsupported request.
- No IPv6 or dual-stack state entry is created.

#### TC-NFR1-02: Reject IPv4 /31 and /32 Subnet prefixes

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- `agentless_net` is Ready with IPv4 capability in a future supported
  implementation, after mandatory NetworkACL enforcement.
- A Ready VirtualNetwork has a supernet containing the candidate Subnet CIDRs.

##### Steps

1. Submit Subnet requests for `10.20.2.0/31` and `10.20.2.2/32`.
2. Inspect each API response, resource condition, AAP job history, and
   AgentlessNet state.
3. Submit a valid `10.20.2.4/30` Subnet request and inspect its realized
   gateway and DHCP state.

##### Expected Results

- The `/31` and `/32` requests are rejected or marked Failed with an
  unsupported-prefix diagnostic before AAP dispatch.
- The rejected requests create no VLAN, gateway, DHCP scope, state-file entry,
  or other fabric side effect.
- The `/30` request is accepted with `10.20.2.5` as the gateway and the
  remaining usable address available to DHCP.

### NFR-2: physical fabric manager parity (future after NetworkACL support)

#### TC-NFR2-01: Compare core API behavior with the physical fabric manager backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Equivalent physical fabric manager and agentless test environments expose the same API.
- The same tenant scenario is runnable against both backends.

##### Steps

1. Create the same VirtualNetwork, multiple Subnets, and attachment scenario
   against each backend.
2. Compare API responses, phases, conditions, and in-scope attachment results.

##### Expected Results

- After mandatory NetworkACL enforcement is implemented, resource shapes and
  tenant-visible status fields match the existing API contract.
- Same-Subnet, permitted cross-Subnet, and topology-isolation outcomes match
  for the in-scope backend behavior.
- Backend selection does not add tenant-visible API fields.
- Until that implementation exists, supported NetworkClass selection is rejected;
  a mismatched configuration leaves the Subnet and dependent attachments not
  Ready. The backend does not apply a permit-all fallback or claim ACL readiness.

#### TC-NFR2-02: Compare external access behavior with the physical fabric manager backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Equivalent ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway
  scenarios are available in both backend environments.

##### Steps

1. Exercise inbound traffic through ExternalIPAttachment after DNAT succeeds.
2. Exercise outbound traffic through NATGateway and observe the translated
   source address.
3. Compare readiness, status, address translation, and cleanup results.

##### Expected Results

- After mandatory NetworkACL enforcement is implemented, both backends expose
  the same in-scope resource and status behavior.
- Inbound traffic reaches the target only through its ExternalIP after the
  attachment is Ready.
- Outbound traffic observes the configured NATGateway ExternalIP.
- Deletion removes only the resources' owned mappings.
- Until that implementation exists, supported NetworkClass selection is rejected;
  a mismatched configuration leaves the Subnet and dependent attachments not
  Ready. The backend does not apply a permit-all fallback or claim ACL readiness.

### NFR-3: Internal VirtualNetwork isolation (raw topology tests only)

#### TC-NFR3-01: Enforce private isolation for overlapping VirtualNetworks

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The raw topology fixture creates separate namespaces with overlapping IPv4
  address ranges and attaches test interfaces directly; no OSAC API objects are
  created and no Subnet readiness is asserted.

##### Steps

1. Inspect the raw Linux namespaces, route tables, and uplink boundaries.
2. Attempt direct traffic between the test endpoint addresses.

##### Expected Results

- The namespaces contain no direct private route between the two raw topology
  segments.
- Direct private traffic does not reach the peer.
- The two VLAN and namespace state entries remain separate. No API Subnet or
  workload readiness is claimed.

#### TC-NFR3-02: Permit only the explicit external path between VNs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- The raw topology fixture configures an external test path between separate
  namespaces using test addresses; no OSAC API objects, ExternalIPs, or API
  readiness conditions are used.

##### Steps

1. Attempt direct traffic to the peer's private test address.
2. Send a flow through the peer's test external address over the raw path.

##### Expected Results

- Direct private traffic remains unreachable.
- The explicit raw external path carries the test flow.
- No internal cross-VN route is created. No API Subnet, attachment, or workload
  readiness is claimed.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 35 |
| Critical | 12 |
| High | 22 |
| Medium | 1 |
| Low | 0 |
| Automated | 34 |
| Manual | 1 |
| Requirements with test cases | 13 / 13 |
| Interface changes with test cases | 6 / 6 |

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ 06d340f90 (72 behind origin/main)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":72,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","respond","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
