# Testplan — OSAC-4307

## Overview

- **Feature:** OSAC-3664 — Fabric Manager — Agentless VLAN
- **Design task:** OSAC-4307
- **Total test cases:** 31
- **Requirements covered:** 13 of 13
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

- The ConfigMap has name agentless_net, role fabric, and capability ipv4.
- The NetworkClass exposes agentless_net as the selected fabric manager.
- IPv6 and dual-stack capabilities are absent.

#### TC-FR1-02: Select the backend through the existing provider configuration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | manual |

##### Preconditions

- The deployment supports the existing Netris backend selection mechanism.
- Equivalent tenant networking requests are available for both backend profiles.

##### Steps

1. Select agentless_net through the provider configuration.
2. Submit the same VirtualNetwork, Subnet, and SecurityGroup requests used with
   the Netris profile.

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

##### Steps

1. Create a VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP,
   ExternalIPAttachment, and NATGateway through the existing API.
2. Poll the corresponding CRs and fulfillment-service resources.

##### Expected Results

- Each request is accepted without an agentless-specific API field.
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
- Two test interfaces are bound to the same Subnet VLAN.

##### Steps

1. Send ARP and IPv4 traffic between the two interfaces.
2. Inspect the switch VLAN and namespace interface membership.

##### Expected Results

- Both interfaces use the same VLAN and broadcast domain.
- ARP resolves without a routed hop.
- IPv4 traffic reaches the peer while the Subnet remains a single L2 domain.

#### TC-FR3-02: Route cross-Subnet traffic by default and enforce SecurityGroup restrictions

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- One Ready VirtualNetwork contains two Ready Subnets.
- Test interfaces are bound to different Subnets and have no applicable
  SecurityGroup initially.

##### Steps

1. Send traffic between the Subnets with no applicable SecurityGroup.
2. Attach or reconcile a SecurityGroup whose rules exclude the test flow.
3. Repeat the traffic attempt.
4. Add a matching SecurityGroup rule and repeat the traffic attempt.

##### Expected Results

- With no applicable SecurityGroup, the permit-all baseline routes the flow
  between Subnets.
- While the restrictive SecurityGroup is applicable, the excluded flow is
  dropped by its policy.
- After a matching rule is added, the VN namespace routes the flow again.
- SecurityGroup rule changes update only the owned iptables/netfilter rules.

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

- A Ready Subnet has a per-VN DHCP service bound to its VLAN interface.
- A BareMetalInstance has a network attachment referencing that Subnet.

##### Steps

1. Provision the host.
2. Run the generic network-attachment job and hand the port to the Subnet VLAN.
3. Reboot or renew DHCP on the host.
4. Run the generic DHCP lease query job.

##### Expected Results

- The host receives an IPv4 address inside the Subnet CIDR.
- The lease artifact contains the authoritative port MAC from the
  `osac.openshift.io/interface-macs` annotation, the matching SubnetRef, and IP;
  the MAC matches the attachment's annotation mapping.
- BareMetalInstance status contains the same IP in its network attachment status.
- NetworkHandoffComplete and IPDiscoveryComplete become True.

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

### FR-5: Inbound external access

#### TC-FR5-01: Create DNAT after the target address is ready

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- The target has no primary private address at first, then receives one.
- No applicable SecurityGroup is attached to the target, so the baseline permits
  the inbound test flow.

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
- The attachment remains non-ready if ExternalIP allocation succeeds but the
  DNAT operation fails.
- Inbound traffic reaches the target under the permit-all baseline, and the
  attachment becomes Ready only after DNAT success and status feedback
  confirmation.

#### TC-FR5-02: Enforce SecurityGroup restriction and remove DNAT on deletion

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- An ExternalIPAttachment is Ready and its target has a primary IP.
- An applicable SecurityGroup is attached to the target and has no matching
  ingress rule for the test flow.

##### Steps

1. Send traffic to the ExternalIP.
2. Delete the ExternalIPAttachment.
3. Inspect the owned DNAT rule and parent ExternalIP status.

##### Expected Results

- The packet is dropped by the applicable SecurityGroup restriction rather than
  by the permit-all baseline.
- The DNAT rule is removed before the attachment finalizer is cleared.
- ExternalIP status.attached becomes false after feedback.

### FR-6: Outbound external connectivity

#### TC-FR6-01: SNAT permitted egress through the NATGateway ExternalIP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- An ExternalIP is Allocated with status.address populated.
- A NATGateway references that ExternalIP and a Ready VirtualNetwork.
- No applicable SecurityGroup is attached, so the permit-all baseline permits
  the test egress flow.

##### Steps

1. Send traffic from a Subnet interface to an external endpoint.
2. Inspect the endpoint's observed source address and the NATGateway status.

##### Expected Results

- The endpoint observes the NATGateway ExternalIP as the source address.
- The SNAT rule is present in the owned state mapping.
- NATGateway status.phase is Ready.

#### TC-FR6-02: Apply SecurityGroup restriction before SNAT

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A NATGateway has an owned SNAT rule.
- An applicable SecurityGroup is attached and has no matching egress rule for
  the test flow.

##### Steps

1. Send the test flow from a Subnet interface.
2. Add the matching SecurityGroup egress rule and repeat the flow.

##### Expected Results

- The first flow is dropped by the applicable SecurityGroup restriction and
  does not reach SNAT.
- The second flow reaches POSTROUTING and the external endpoint observes the
  NATGateway ExternalIP.
- The NATGateway role does not add or modify SecurityGroup rules.

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
3. Wait for the ExternalIP AAP job to succeed and inspect its
   `external_ip_address` artifact.
4. Read pool and ExternalIP status and inspect the agentless state file.

##### Expected Results

- Pool status.total and status.available reflect the configured CIDR capacity.
- ExternalIP status.state is Allocated and status.address contains an address
  from the pool.
- The AAP artifact, `ExternalIP.status.address`, and the state-file
  `external_ips` entry contain the same address keyed by the ExternalIP UID.
- The state-file `external_ip_pools` entry records the provider-side pool CIDR.

#### TC-FR7-02: Reject exhausted capacity and restore it on release

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | medium | automated |

##### Preconditions

- A Ready ExternalIPPool has no available capacity.

##### Steps

1. Attempt to create another ExternalIP from the exhausted pool.
2. Delete an existing ExternalIP.
3. Wait for the state-file allocation to be removed and create another
   ExternalIP from the pool.

##### Expected Results

- The first create request fails with a capacity/precondition error.
- Pool status.available increases after the deletion is persisted.
- The subsequent create request receives a newly allocated address, and the
  state file contains exactly one allocation for the new ExternalIP UID.

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
2. Wait for both operations to complete, then read the pool status and the
   ExternalIP AAP allocation artifact.

##### Expected Results

- The pool retains `allocated=1` and `available=1` from the capacity update.
- The reconciler's phase and conditions are also present; neither writer
  overwrites fields owned by the other.
- The ExternalIP address in status matches the AAP artifact and its state-file
  allocation, with no duplicate allocation after conflict retries.

### FR-8: Networking across all services

#### TC-FR8-01: Perform BMF port bind and unbind through the generic contract

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A Ready Subnet has a recorded VLAN.
- A BareMetalInstance exposes an interface and subnetRef attachment.

##### Steps

1. Run playbook_osac_move_network_attachment for the bind operation.
2. Inspect the Cumulus port, VLAN, and port_bindings state.
3. Run the deprovisioning operation.

##### Expected Results

- The AgentlessNet attachment role receives host, interface, and Subnet inputs.
- The switch port is assigned to the Subnet VLAN and the binding is recorded.
- Unbind removes the port binding without changing another Subnet's VLAN.

#### TC-FR8-02: Accept downstream CaaS and VMaaS attachment inputs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Fixtures represent a CaaS cluster node and a VMaaS ComputeInstance whose
  attachment omits the Subnet and SecurityGroup fields so tenant defaults must
  be resolved.
- A fake AAP provider captures the selected role arguments.

##### Steps

1. Submit each fixture to the generic attachment and DHCP role contract.
2. Inspect the resolved attachment fields, role argument validation, and
   generated lease-query inputs.

##### Expected Results

- Both fixtures expand omitted Subnet and SecurityGroup fields to the tenant's
  defaults.
- The single CaaS `BareMetalNetworkAttachment` has `primary: true`.
- The single VMaaS attachment is implicitly primary; generic
  `query_dhcp_lease` arguments do not require a `primary` field.
- The AgentlessNet role accepts the contract without a service-specific API
  change.
- Full service provisioning remains assigned to OSAC-1611 and OSAC-3665.

### FR-10: Failure visibility

#### TC-FR10-01: Surface a switch-port or VLAN failure

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

#### TC-FR10-02: Surface missing or stale DHCP feedback

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

### FR-11: Lifecycle cleanup

#### TC-FR11-01: Remove DNAT before releasing an ExternalIP

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

- DNAT is absent before the ExternalIP is released.
- The attachment finalizer is removed only after DNAT cleanup feedback.
- Pool capacity increases only after ExternalIP deletion.

#### TC-FR11-02: Clean one Subnet/VirtualNetwork without affecting peers

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- The first VirtualNetwork has two Ready Subnets, each with VLAN and namespace
  state, and a SecurityGroup policy that applies to both Subnets.
- The second VirtualNetwork has an independent Subnet, VLAN, namespace, and
  test attachment.

##### Steps

1. Delete one Subnet from the first VirtualNetwork and wait for its finalizer
   cleanup to complete.
2. Inspect state-file entries, DHCP state, switch VLANs, namespace interfaces,
   gateway state, and the SecurityGroup policy for the remaining Subnet.
3. Verify permitted traffic for the remaining Subnet, then delete the first
   VirtualNetwork and inspect the second VirtualNetwork.

##### Expected Results

- The deleted Subnet's DHCP state, VLAN, interfaces, gateway, and
  Subnet-owned state are removed in dependency order, and its VLAN is not
  released before cleanup is confirmed.
- The SecurityGroup-owned chain remains after Subnet deletion; its rules for
  the remaining Subnet continue to permit the configured traffic, while
  SecurityGroup reconciliation removes only obsolete rules for the deleted
  Subnet.
- After the first VirtualNetwork is deleted, its remaining child state and
  SecurityGroup rules are removed in dependency order.
- The second VirtualNetwork's namespace, VLAN, and connectivity remain present.
- The deleted resources' finalizers are removed only after cleanup feedback.

#### TC-FR11-03: Delay parent-first ExternalIP release until attachment cleanup

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

### NFR-2: Netris-equivalent tenant behavior

#### TC-NFR2-01: Compare core API behavior with the Netris backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- Equivalent Netris and agentless test environments expose the same API.
- The same tenant scenario is runnable against both backends.

##### Steps

1. Create the same VirtualNetwork, multiple Subnets, SecurityGroup, and
   attachment scenario against each backend.
2. Compare API responses, phases, conditions, and allowed/denied traffic.

##### Expected Results

- Resource shapes and tenant-visible status fields match the existing API
  contract.
- Same-Subnet, permitted cross-Subnet, and denied traffic outcomes match.
- Backend selection does not add tenant-visible API fields.

#### TC-NFR2-02: Compare external access behavior with the Netris backend

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- Equivalent ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway
  scenarios are available in both backend environments.

##### Steps

1. Exercise permitted and denied inbound traffic through ExternalIPAttachment.
2. Exercise permitted and denied outbound traffic through NATGateway.
3. Compare status and cleanup results.

##### Expected Results

- Both backends expose the same allowed/denied traffic outcomes.
- Inbound traffic reaches the target only through its ExternalIP and permitted
  policy.
- Outbound traffic observes the configured NATGateway ExternalIP.
- Deletion removes only the resources' owned mappings.

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
  addresses.
- SecurityGroup rules permit the intended external flow.

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

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 31 |
| Critical | 11 |
| High | 19 |
| Medium | 1 |
| Low | 0 |
| Automated | 30 |
| Manual | 1 |
| Requirements with test cases | 13 / 13 |
| Interface changes with test cases | 6 / 6 |
