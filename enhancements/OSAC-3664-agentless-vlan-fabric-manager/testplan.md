# Testplan — OSAC-4307

## Overview

- **Feature:** OSAC-3664 — Fabric Manager — Agentless VLAN
- **Design task:** OSAC-4307
- **Current contract amendment:** OSAC-6693 — NATGateway v1 controller/AAP contract
- **Design:** [design.md](design.md)
- **Authority:** This requirement-anchored test plan is part of the design PR;
  the design document's Test Plan section is only a short strategy summary.
- **Total test cases:** 36
- **Requirements covered:** 13 of 13
- **Interface changes covered:** 6 of 6

## Test Cases

### FR-1: Backend selection

#### TC-FR1-01: Register agentless_net as an IPv4 fabric manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- The installer values enable the agentless fabric-manager entry.
- No agentless manager ConfigMap exists.

##### Steps

1. Render and apply the operator Helm configuration.
2. Inspect the generated fabric-manager ConfigMap and the NetworkClass
   capability state.

##### Expected Results

- The ConfigMap has name agentless_net, role fabric, and capability ipv4.
- The NetworkClass exposes agentless_net as the selected fabric manager.
- IPv6 and dual-stack capabilities are absent.

#### TC-FR1-02: Select the backend through the existing provider configuration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- The deployment supports the existing Netris backend selection mechanism.
- Equivalent tenant networking requests are available for both backend profiles.

##### Steps

1. Select agentless_net through the provider configuration.
2. Submit the same VirtualNetwork and Subnet requests used with the Netris
   profile.

##### Expected Results

- Backend selection is changed only in provider configuration.
- Tenant API request shapes and fields are unchanged.
- The resources are dispatched to agentless_net rather than Netris.

### FR-2: Fabric-manager-agnostic networking

#### TC-FR2-01: Create the existing networking resource set

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- agentless_net is Ready in NetworkClass.
- The test tenant has the required authorization and tenant metadata.
- A Cloud Infrastructure Admin fixture can create the provider-scoped
  ExternalIPPool; the tenant fixture cannot create or update that pool.

##### Steps

1. Create an ExternalIPPool with the provider-admin fixture.
2. Create a VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment, and
   NATGateway with the tenant fixture through the existing API.
3. Attempt to create or update the ExternalIPPool with the tenant fixture.
4. Poll the corresponding CRs and fulfillment-service resources.

##### Expected Results

- Each request is accepted without an agentless-specific API field.
- The tenant cannot create or modify the provider-scoped ExternalIPPool.
- Each corresponding resource reaches its expected Ready or Allocated state.
- Each tenant-scoped CR retains both required tenant-isolation annotations.

#### TC-FR2-02: Preserve the existing API contract for external access

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- An allocated ExternalIP has an address in status.
- A target resource has a primary private address.

##### Steps

1. Create an ExternalIPAttachment with the existing externalIP and target fields.
2. Create a NATGateway with the existing virtualNetwork and externalIP fields.
3. Query the resources through the existing API.

##### Expected Results

- The requests contain no backend-specific fields.
- ExternalIPAttachment reports the assigned external address through the
  existing status path and reaches Ready only after DNAT succeeds.
- NATGateway reports Ready after its SNAT job reaches a terminal success state.

### FR-3: Multiple Subnets per VirtualNetwork

#### TC-FR3-01: Keep same-Subnet traffic in one broadcast domain

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- One Ready VirtualNetwork contains one Ready Subnet.
- Two test interfaces are bound to the same Subnet VLAN.

##### Steps

1. Send ARP and IPv4 traffic between the two interfaces.
2. Inspect the switch VLAN and namespace interface membership.

##### Expected Results

- Both interfaces use the same VLAN and broadcast domain.
- ARP resolves without a routed hop.
- IPv4 traffic reaches the peer while the Subnet remains a single L2 domain.

#### TC-FR3-02: Route cross-Subnet traffic by default

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- One Ready VirtualNetwork contains two Ready Subnets.
- Test interfaces are bound to different Subnets.

##### Steps

1. Send traffic between the Subnets.
2. Repeat the traffic attempt after reconciliation and a controller restart.

##### Expected Results

- The permit-all baseline routes the flow between Subnets.
- Reconciliation and restart do not introduce a policy-dependent readiness gate
  or change the routed result.

#### TC-FR3-03: Isolate overlapping VirtualNetworks on the internal fabric

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Two VirtualNetworks use overlapping IPv4 CIDRs.
- Each VirtualNetwork has a Ready Subnet and an attached test interface.

##### Steps

1. Attempt direct traffic from one private Subnet address to the other.
2. Inspect namespace routes and inter-VN interfaces.

##### Expected Results

- No private route connects the two VirtualNetwork namespaces.
- Direct traffic to the other private address receives no successful response.
- Each namespace contains only its own VirtualNetwork routing state.

### FR-4: Automatic IP assignment

#### TC-FR4-01: Assign a DHCP address to a bare-metal attachment

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** Unit / [DEV].
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

- **Tier / owner:** E2E / [QE].
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

### FR-5: Inbound external access

#### TC-FR5-01: Create DNAT after the target address is ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- An ExternalIP is Allocated with status.address populated.
- The target has no primary private address at first, then receives one.
- The supported external path is available, so the default forwarding baseline
  permits the inbound test flow.
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
- Inbound traffic reaches the target under the permit-all baseline, and the
  attachment becomes Ready only after DNAT success and status feedback
  confirmation.

### FR-6: Outbound external connectivity

#### TC-FR6-01: SNAT permitted egress through the NATGateway ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [DEV].
- An ExternalIP is Allocated with status.address populated.
- A NATGateway references that ExternalIP and a Ready VirtualNetwork.
- The VirtualNetwork has two Ready Subnets, and the NATGateway state contains
  both source CIDRs.
- The VLAN lab's direct peer link and test-only `/32` return route are available,
  so the permit-all baseline permits the test egress flow.

##### Test Tier and Owner

- Local deployed lab E2E — OSAC-6202 [DEV]. From the OSAC repository root on
  branch `e2e`, run `bash ./vlan-e2e.sh --nat-gateway`. This is a local lab
  validation owned by the implementation task; it does not create a separate
  QE task. The runner uses a test-only static route over the direct Containerlab
  peer link and does not verify remote BGP advertisement or convergence.

##### Steps

1. Create NATGateways for two VirtualNetworks, each with an allocated
   ExternalIP, and create one Subnet in each network.
2. Attach DHCP clients from both networks and send traffic to the local
   upstream-router endpoint.
3. Add a second Subnet to one VirtualNetwork, move a client into it, and send
   traffic again.
4. Inspect the endpoint's observed source address, NATGateway status, provider
   source set, SNAT rules, and local FRR `/32` route.

##### Expected Results

- The endpoint observes the NATGateway ExternalIP as the source address.
- Each VirtualNetwork's clients observe its own NATGateway ExternalIP, including
  clients on both Subnets; overlapping private CIDRs remain isolated.
- One explicit `SNAT --to-source` rule exists for each active source CIDR; no
  host-side MASQUERADE changes the observed source.
- The consumer-owned `/32` route is installed locally through the saved
  VirtualNetwork next hop. The test-only static peer route returns traffic.
- NATGateway status.phase is Ready.

#### TC-FR6-02: Reconcile NAT rules before Subnet readiness or cleanup

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
- A current schema-v1 SQLite state contains a Ready VirtualNetwork, one Ready
  Subnet, an allocated ExternalIP, and a Ready NATGateway.
- Provider commands are replaced by fixtures that record Subnet data-plane and
  NATGateway reconciliation calls.

##### Test Tier and Owner

- Unit — OSAC-6202 [DEV]. From `osac-aap/`, run
  `uv run --group development pytest tests/unit/test_agentless_network_state.py -k 'subnet_ensure_adds_nat_source or subnet_delete_reconciles_nat_sources or subnet_delete_waits_for_nat_gateway'`.

##### Steps

1. Call `StateStore.ensure_and_reconcile_subnet` for a second reserved Subnet.
2. Record the provider call sequence and inspect the NATGateway source set and
   revision after the Subnet reaches Ready.
3. Call `StateStore.prepare_delete_subnet` for the second Subnet and record the
   provider call sequence before DHCP, interface, or VLAN cleanup.
4. Repeat Subnet deletion while the NATGateway is still deleting and retains
   the Subnet source, then retry after the gateway cleanup succeeds.

##### Expected Results

- The second CIDR is added to the applied SNAT set after Subnet data-plane setup
  and before the Subnet phase changes to Ready.
- Deleting the Subnet removes its source from the applied set before DHCP,
  namespace-interface, or VLAN state is withdrawn; the first Subnet's rule
  remains present.
- A provider-command failure leaves the Subnet deleting and retains the old
  and pending source sets for retry.
- A deleting NATGateway that still owns the Subnet source blocks Subnet cleanup
  until NATGateway route and SNAT cleanup succeeds.

#### TC-FR6-03: Run AgentlessNet NATGateway v1 playbooks and result artifacts

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
- A temporary schema-v1 SQLite state contains the VirtualNetwork, Subnet,
  ExternalIPPool, and ExternalIP provider prerequisites.
- The AgentlessNet provider inventory contains one test network node and
  provider commands are replaced by test-only fixtures.

##### Test Tier and Owner

- Component integration — OSAC-6202 [DEV]. From `osac-aap/tests/integration/`,
  run `uv run --group development ansible-playbook targets/agentless_net_nat_gateway/tasks/baseline.yml -e '@common_vars.yml'`.

##### Steps

1. Run the production NATGateway create playbook with the controller-shaped
   `nat_gateway_context` and verify the job succeeds with no `osac_result`.
2. Retry ensure with the same identity and inspect the persistent provider row.
3. Run delete with a fixture route-withdrawal failure, then inspect retained
   deleting state and retry after provider cleanup succeeds.
4. Retry delete after the provider row has been removed.

##### Expected Results

- Create succeeds, with no `osac_result`, only after provider state succeeds;
  the row contains the ExternalIP, VirtualNetwork CIDR, and route cleanup
  identity.
- A failed cleanup publishes `osac_error` and retains the NATGateway row and
  ExternalIP consumer reservation.
- A successful delete removes the
  provider row; a repeated delete is idempotent.
- The child Ansible process has unusable Kubernetes credentials and performs
  no OSAC API discovery.

#### TC-FR6-04: Retry, reconcile Subnet sources, and clean up NATGateway state

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [DEV].
- The OSAC-6202 implementation is deployed from the source-pinned SNAT branch.
- The local VLAN lab has an available test ExternalIPPool, SNO, AAP, network
  node, Cumulus switches, and upstream-router endpoint.
- The runner can temporarily select `eth2` as the AgentlessNet external
  interface and can restore the previous AAP ConfigMap value afterward.

##### Test Tier and Owner

- Local deployed lab E2E — OSAC-6202 [DEV]. From the OSAC repository root on
  branch `e2e`, run `bash ./vlan-e2e.sh --nat-gateway`. The test uses the
  existing local VLAN lab and a test-only static return route. It does not
  verify remote BGP advertisement/convergence or physical hardware.

##### Steps

1. Create a gateway in a VirtualNetwork with no Subnets; inspect its empty
   source set, saved ExternalIP reservation, and local `/32` route.
2. Verify a second gateway for the same VirtualNetwork and reuse of the
   consumed ExternalIP are rejected without additional provider state.
3. Create a Subnet and gateway client, force a controller retry for the same
   gateway UID, then add another Subnet and move a client into it.
4. Remove the second Subnet and verify only its SNAT source is removed. Remove
   the last Subnet and verify the gateway retains its ExternalIP reservation
   and route with an empty source set.
5. Delete the gateway and validate its matching delete artifact, natural
   finalizer completion, route/rule/conntrack removal, peer preservation, and
   subsequent ExternalIP release.
6. Repeat cleanup with `bash ./vlan-e2e.sh --cleanup --nat-gateway` and verify
   it is idempotent.

##### Expected Results

- A retry launches a new AAP job but preserves resource UID, ExternalIP, and
  provider identity without duplicating owned rules.
- A new Subnet's SNAT rule is active before Subnet readiness; a deleted
  Subnet's rule is removed before its DHCP/interface/VLAN state is withdrawn.
- Deleting the last Subnet leaves the NATGateway reservation and local route
  intact until the gateway itself is deleted.
- A failed or invalid delete result retains the NATGateway finalizer and
  ExternalIP consumer reservation.
- VirtualNetwork cleanup remains blocked while an ExternalIP consumer retains
  route or NAT state for that VirtualNetwork; this check does not require the
  Subnets to remain.
- Successful deletion removes only the gateway-owned SNAT, forwarding, bypass,
  route, and matching conntrack state. The peer gateway and its traffic remain
  unchanged.
- The ExternalIP remains allocated until NATGateway cleanup succeeds and the
  test explicitly releases it; pool capacity returns to its initial value.

### FR-7: External IP pools

#### TC-FR7-01: Allocate an ExternalIP from the agentless state-file pool

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV].
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

- **Tier / owner:** Component integration / [DEV].
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

- **Tier / owner:** Component integration / [DEV].
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

- **Tier / owner:** Unit / [DEV].
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

### FR-8: Networking across all services

#### TC-FR8-01: Perform BMF port bind and unbind through the generic contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** Unit / [DEV].
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

### FR-9: Failure visibility

#### TC-FR9-01: Surface a switch-port or VLAN failure

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

### FR-10: Lifecycle cleanup

#### TC-FR10-01: Remove DNAT before releasing an ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

- **Tier / owner:** E2E / [QE].
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

### NFR-1: IPv4-only capability

#### TC-NFR1-01: Reject unsupported IPv6 and dual-stack requests

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- **Tier / owner:** Unit / [DEV].
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

- **Tier / owner:** Unit / [DEV].
- `agentless_net` is Ready with IPv4 capability.
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

### NFR-2: Netris parity for in-scope tenant behavior

#### TC-NFR2-01: Compare core API behavior with the Netris backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Equivalent Netris and agentless test environments expose the same API.
- The same tenant scenario is runnable against both backends.

##### Steps

1. Create the same VirtualNetwork, multiple Subnets, and attachment scenario
   against each backend.
2. Compare API responses, phases, conditions, and in-scope attachment results.

##### Expected Results

- Resource shapes and tenant-visible status fields match the existing API
  contract.
- Same-Subnet, permitted cross-Subnet, and topology-isolation outcomes match
  for the in-scope backend behavior.
- Backend selection does not add tenant-visible API fields.
- SecurityGroup provisioning and policy enforcement are excluded from this
  parity comparison.

#### TC-NFR2-02: Compare external access behavior with the Netris backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Equivalent ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway
  scenarios are available in both backend environments.

##### Steps

1. Exercise inbound traffic through ExternalIPAttachment after DNAT succeeds.
2. Exercise outbound traffic through NATGateway and observe the translated
   source address.
3. Compare readiness, status, address translation, and cleanup results.

##### Expected Results

- Both backends expose the same in-scope resource and status behavior.
- Inbound traffic reaches the target only through its ExternalIP after the
  attachment is Ready.
- Outbound traffic observes the configured NATGateway ExternalIP.
- Deletion removes only the resources' owned mappings.
- SecurityGroup provisioning and policy enforcement are excluded from this
  comparison because they remain outside the agentless milestone.

### NFR-3: Internal VirtualNetwork isolation

#### TC-NFR3-01: Enforce private isolation for overlapping VirtualNetworks

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Two VirtualNetworks use overlapping private CIDRs.
- Each has a Ready Subnet and a test endpoint.

##### Steps

1. Inspect the Linux namespaces, route tables, and uplink boundaries.
2. Attempt direct traffic between the private endpoint addresses.

##### Expected Results

- The namespaces contain no direct private route between the two VNs.
- Direct private traffic does not reach the peer.
- The two VLAN and namespace state entries remain separate.

#### TC-NFR3-02: Permit only the explicit external path between VNs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Two overlapping VirtualNetworks have an ExternalIPAttachment and a
  NATGateway configured through allocated ExternalIPs with populated status
  addresses.

##### Steps

1. Attempt direct traffic to the peer's private address.
2. Send traffic through the peer's ExternalIP over the external path.

##### Expected Results

- Direct private traffic remains unreachable.
- The explicit ExternalIP/NATGateway path carries the permitted flow.
- No internal cross-VN route is created.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

### Environment and Boundary Gaps

- The local `vlan-e2e.sh --nat-gateway` run verifies source translation and
  return traffic through a test-only static route. It does not verify remote
  BGP advertisement/convergence or physical hardware behavior.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 36 |
| Critical | 11 |
| High | 24 |
| Medium | 1 |
| Low | 0 |
| Automated | 35 |
| Manual | 1 |
| Requirements with test cases | 13 / 13 |
| Interface changes with test cases | 6 / 6 |

---

## Provenance

Authored: revise @ design 0.11.5 - e2b0d87, workspace osac-6202-natgateway-snat @ 9eac9f81a
Final: revise [manual] @ design 0.11.5 - e2b0d87, workspace osac-6202-natgateway-snat @ b6007aac2

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"b6007aac2","source_repo_branch":"osac-6202-natgateway-snat","commits_behind_main":0,"commits_ahead_main":17,"main_ref":"main","phases":["revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
