# Testplan — OSAC-4307

## Overview

- **Feature:** OSAC-3664 — Fabric Manager — Agentless VLAN
- **Design task:** OSAC-4307
- **Design:** [design.md](design.md)
- **Authority:** This requirement-anchored test plan is part of the design PR;
  the design document's Test Plan section is only a short strategy summary.
- **Total test cases:** 37
- **Requirements covered:** 16 of 16
- **Interface changes covered:** 6 of 6

## Test Cases

### FR-1: Backend selection

#### TC-FR1-01: Register agentless_net as an IPv4 fabric manager

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

- The ConfigMap has the Fabric Manager role label, name agentless_net, implementationRef osac.templates.agentless_net, contractVersion v1, and ipv4 capability only.
- The NetworkClass selects agentless_net without a K8s Manager, which is the Fabric-only IPv4 profile.
- The registration does not claim evpn-vxlan, ipv6, or dualStack.

#### TC-FR1-02: Select the backend through the existing provider configuration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | manual |

##### Preconditions

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

- One Ready VirtualNetwork contains one Ready Subnet.
- Two test interfaces are bound to the same Subnet VLAN and have a SecurityGroup rule that permits the test traffic.

##### Steps

1. Send ARP and IPv4 traffic between the two interfaces.
2. Inspect the switch VLAN and namespace interface membership.

##### Expected Results

- Both interfaces use the same VLAN and broadcast domain.
- ARP resolves without a routed hop.
- IPv4 traffic reaches the peer while the Subnet remains a single L2 domain.

#### TC-FR3-02: Route cross-Subnet traffic when SecurityGroup permits

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- One Ready VirtualNetwork contains two Ready Subnets.
- Test interfaces are bound to different Subnets and their SecurityGroup explicitly permits the test flow.

##### Steps

1. Send traffic between the Subnets.
2. Repeat the traffic attempt after reconciliation and a controller restart.

##### Expected Results

- The explicit SecurityGroup rule permits the flow and the routed packet reaches the peer.
- Reconciliation and restart preserve the selected route and effective policy.

#### TC-FR3-03: Isolate overlapping VirtualNetworks on the internal fabric

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

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
- osac_result.data.leases contains the authoritative port MAC from the
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

#### TC-FR4-03: Reject ComputeInstance networking in the Fabric-only profile

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- agentless_net is registered with ipv4 only and selected without a K8s Manager.
- The NetworkClass therefore selects the Fabric-only IPv4 profile.
- A ComputeInstance requests a Subnet from that NetworkClass.

##### Steps

1. Submit the ComputeInstance networking request.
2. Inspect profile validation, AAP job history, and AgentlessNet inputs.

##### Expected Results

- OSAC rejects the ComputeInstance target before AAP dispatch because the
  Fabric-only profile has no K8s network integration.
- No AgentlessNet DHCP query or attachment job starts for the ComputeInstance.
- VM address assignment remains available through a compatible
  Fabric-backed EVPN profile and its K8s Manager.

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

### FR-5: Inbound external access

#### TC-FR5-01: Create DNAT after the target address is ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- The target has no primary private address at first, then receives one.
- The target attachment has a SecurityGroup rule that permits the inbound test flow, and the supported external path is available.
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
- Inbound traffic reaches the target only when the attached SecurityGroup permits the flow, and the
  attachment becomes Ready only after DNAT success and status feedback
  confirmation.

### FR-6: Outbound external connectivity

#### TC-FR6-01: SNAT permitted egress through the NATGateway ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- A NATGateway references that ExternalIP and a Ready VirtualNetwork.
- The attached SecurityGroup explicitly permits egress to the test endpoint.
- The VirtualNetwork has two Ready Subnets, and the NATGateway state contains
  both source CIDRs.

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

### FR-7: External IP pools

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
3. Wait for the ExternalIP AAP job to complete and inspect its validated
   osac_result.data.externalIP.address.
4. Read pool and ExternalIP status, reservation state, and agentless state file.

##### Expected Results

- Pool status.total and status.available reflect the configured CIDR capacity.
- ExternalIP status.state is Allocated and status.address contains an address
  from the pool.
- The address in osac_result, ExternalIP.status.address, and the state-file
  external_ips entry is the same and is keyed by the ExternalIP UID.
- OSAC accepts the result and updates its reservation and pool capacity exactly once.
- The state-file `external_ip_pools` entry records the provider-side pool CIDR.

#### TC-FR7-02: Reject exhausted capacity and restore it on release

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A Ready ExternalIPPool has no available capacity.

##### Steps

1. Attempt to create another ExternalIP from the exhausted pool.
2. Delete an existing ExternalIP and wait for the release task to return
   osac_result.data.externalIP.releaseState = RELEASED.
3. Create another ExternalIP from the pool.

##### Expected Results

- The first create request fails with a capacity/precondition error.
- Pool status.available increases only after OSAC validates the common RELEASED result.
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

### FR-8: Fabric workload attachment targets

#### TC-FR8-01: Perform BMF port bind and unbind through the generic contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A Ready Subnet has a recorded VLAN.
- A BareMetalInstance exposes an interface, authoritative MAC, host UID, and
  SubnetRef attachment; the provider provisioning-network ID is configured.

##### Steps

1. Run `playbook_osac_move_network_attachment` with
   `osac_job_vars.context.attachment.action: ATTACH` and the stable
   binding/host/MAC/Subnet/provisioning-network inputs.
2. Verify the port is on the tenant VLAN, reboot the host, and wait for
   `NetworkHandoffComplete` and DHCP discovery.
3. Power off the host and run the same playbook with
   `osac_job_vars.context.attachment.action: DETACH`.
4. Inspect the Cumulus port, VLAN, and `port_bindings` state.

##### Expected Results

- The AgentlessNet role receives the contract-defined binding under
  `osac_job_vars.context.attachment`, including stable binding UID, workload
  kind/UID, host UID, interface, authoritative MAC, Subnet and VirtualNetwork
  UIDs/references, tenant ID, action, and provisioning-network ID.
- The successful task returns the matching binding UID, observed state, and
  backend port identity in osac_result.data.attachment.
- Attach returns state ATTACHED; detach returns state RESTORED. Both results
  identify the same stable binding UID and the observed backend port.
- The switch port is assigned to the Subnet VLAN and the binding is recorded;
  DHCP and handoff readiness follow reboot.
- Detach restores the exact provisioning VLAN, reports
  `NetworkOffboardComplete`, and removes the binding without changing another
  Subnet's VLAN.

#### TC-FR8-02: Enforce the Fabric-only target boundary

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- agentless_net is registered with ipv4 only and selected without a K8s Manager.
- The NetworkClass therefore selects the Fabric-only IPv4 profile.
- A fake AAP provider captures dispatch attempts.
- Valid Cluster target, SecurityGroup, and ExternalIPAttachment fixtures are available.

##### Steps

1. Submit a BaremetalInstance attachment using normalized context and verify it
   is routed to the Fabric Manager workload_attachment.move entry point; query
   its lease through `osac_job_vars.context.attachments` using binding UID,
   Subnet UID/reference, interface, and authoritative MAC.
2. Request a Cluster-targeted SecurityGroup update and ExternalIPAttachment.
3. Request a Cluster workload_attachment.move and dhcp_lease.query operation,
   then request a ComputeInstance attachment through this profile.
4. Configure `cudn_evpn` with evpn-vxlan but compatibleFabricManagers=netris,
   then attempt to combine it with `agentless_net`, which lacks evpn-vxlan and
   compatibleK8sManagers.

##### Expected Results

- BaremetalInstance receives workload_attachment.move and dhcp_lease.query;
  both operations require the exact contract inputs and result.
- The query returns exactly one matching entry in `osac_result.data.leases`
  with `subnetRef`, `interface`, `ipAddress`, and `macAddress`; missing, stale,
  or ambiguous matches fail with a diagnostic.
- Cluster-level SecurityGroup and ExternalIPAttachment requests are routed to
  the Fabric Manager, while Cluster move and lease-query requests are rejected
  before AAP dispatch.
- ComputeInstance targets fail profile validation before AAP dispatch.
- A K8s Manager cannot be paired with agentless_net for the Fabric-backed EVPN
  profile because AgentlessNet lacks evpn-vxlan and mutual peer declarations;
  the same rejection applies to `cudn_evpn` before AAP dispatch.
- No service-specific fields are added to the manager context.

### FR-9: Failure visibility

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

### FR-10: Lifecycle cleanup

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

### NFR-1: IPv4-only capability

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
- SecurityGroup behavior is included in parity and must match the shared default-deny, input-order-preserving allow-rule, and stateful-return semantics.

#### TC-NFR2-02: Compare external access behavior with the Netris backend

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

- Both backends expose the same in-scope resource and status behavior.
- Inbound traffic reaches the target only through its ExternalIP after the
  attachment is Ready.
- Outbound traffic observes the configured NATGateway ExternalIP.
- Deletion removes only the resources' owned mappings.
- SecurityGroup behavior is included in parity and must match the shared contract; the current packet path is a known blocker to passing these cases.

### NFR-3: Internal VirtualNetwork isolation

#### TC-NFR3-01: Enforce private isolation for overlapping VirtualNetworks

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

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

- Two overlapping VirtualNetworks have an ExternalIPAttachment and a
  NATGateway configured through allocated ExternalIPs with populated status
  addresses. The attached SecurityGroups explicitly allow the tested inbound
  and outbound flows.

##### Steps

1. Attempt direct traffic to the peer's private address.
2. Send traffic through the peer's ExternalIP over the external path.

##### Expected Results

- Direct private traffic remains unreachable.
- The explicit ExternalIP/NATGateway path carries the permitted flow.
- No internal cross-VN route is created.

### FR-11: SecurityGroup conformance

#### TC-FR11-01: Enforce default-deny, order-preserving, stateful policy on every path

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

Create a SecurityGroup with explicit ingress and egress rules and attach it to
endpoints on the same Subnet and on different Subnets. Verify unmatched traffic
is denied, matching traffic is allowed, established return traffic is allowed,
and the same behavior applies to L2-switched, routed, inbound DNAT, and outbound
SNAT traffic. Put different SecurityGroups on two endpoints sharing one Subnet,
and attach multiple groups to one endpoint; verify each binding receives only
the union of its own groups' allow rules. Verify apply receives the complete
binding snapshot on group create, rule update, and binding add/remove. On attach,
policy succeeds before Ready; on detach, the workload leaves the network before
its binding disappears from the next policy snapshot. Repeat after a rule update
and verify obsolete rules stop matching.

**Current result:** blocked by the documented Cumulus packet-path limitation
and the lack of proven per-binding policy isolation. This test is a release
blocker; AgentlessNet must not be called contract conformant until it passes.

#### TC-FR11-02: Remove only the SecurityGroup-owned policy on deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

Delete a SecurityGroup after its workload bindings are detached. Verify its
policy is removed, unrelated SecurityGroup rules remain, and the delete task
returns a valid osac_result only after cleanup is observed.

### FR-12: Common manager result contract

#### TC-FR12-01: Validate common results and OSAC-owned status

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-6 | critical | automated |

For every manager task, verify success returns osac_result with schemaVersion,
operation, resourceUID, and observedGeneration. For ExternalIP allocation verify
the required allocated address is durably stored before result return; for
release verify the UID-owned allocation is absent before RELEASED is returned.
Verify OSAC validates the result and owns API status, annotations, and pool
capacity. Missing or stale results fail reconciliation; no private callback,
provider-specific result annotation, or manager-specific ConfigMap is used as a second
result channel.

## Gaps

The existing test cases for SecurityGroup conformance cannot pass with the
current architecture. AgentlessNet is not a contract-conformant Fabric Manager
until TC-FR11-01 passes on every assigned packet path. The common result tests
are acceptance criteria for the planned implementation.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 37 |
| Critical | 13 |
| High | 23 |
| Medium | 1 |
| Low | 0 |
| Automated | 36 |
| Manual | 1 |
| Requirements with test cases | 16 / 16 |
| Interface changes with test cases | 6 / 6 |
