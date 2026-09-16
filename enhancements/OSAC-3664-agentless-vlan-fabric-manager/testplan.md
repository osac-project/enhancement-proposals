# Testplan — OSAC-3664 Agentless VLAN Fabric Manager

## Scope

This plan covers the agentless VLAN backend's shared Unified Networking
contract and its backend-specific switch/VLAN behavior. The Unified Networking,
VMaaS, CaaS, and BMaaS plans remain authoritative for shared API validation and
service lifecycle cases; this plan verifies that agentless dispatch preserves
those rules.

The [Unified Networking deployment support boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary)
is also authoritative here: agentless VLAN supports connected deployments only,
and air-gapped or disconnected deployments are rejection cases.

## Unit tests

- Validate IPv4-only CIDRs, canonical formats, one-subnet and one-interface
  workload constraints, typed references, NetworkACL inheritance, and the
  provider-owned permit-all baseline.
- Reject IPv6, dual-stack, invalid manager/resource operations, unknown
  VLAN or switch identifiers, lifecycle-only interfaces, and invalid
  direction/protocol/port/CIDR NetworkACL rules.
- Verify agentless manager registration selects the complete networking
  contract: create/read/delete operations, SecurityGroup, NetworkACL,
  NATGateway, and VMaaS/BMaaS/CaaS service targets. A provider operation that
  is still under development may complete as a successful no-op, but no
  resource, policy, scope, or service subset declaration is registered.
- Verify controller state transitions remain Pending until switch/VLAN and IP
  prerequisites are complete, and invalid manager responses become Failed
  rather than Ready.
- Verify deletion admission checks direct reverse references and returns every
  blocker without detaching or deleting a child.

## Integration tests

- Create a VirtualNetwork, Subnet, and NetworkACL through the shared API and
  verify the agentless manager receives the expected VLAN/switch operations.
- Verify bare-metal attachment provisioning moves the selected port to the
  requested VLAN, discovers the IPv4 address, and writes status only after the
  switch and DHCP operations succeed.
- Verify ExternalIP allocation and ExternalIPAttachment dispatch use the
  discovered IPv4 endpoint, remove DNAT before releasing the address, and
  preserve the shared readiness and ownership rules.
- Verify stateless NetworkACL evaluation: matching tenant denies override the
  deployment permit baseline, while unmatched traffic uses the baseline.
- Verify stateful SecurityGroup evaluation: allow-only rules, implicit default
  deny, established return traffic, and conjunction with the effective Subnet
  NetworkACL. Verify that a provider no-op still preserves the normal API
  resource, status, and dispatch contract.
- Inject switch, VLAN, DHCP, DNAT, and cleanup failures. Verify diagnostic
  status, retry behavior, finalizer retention, and no partial release.
- Attempt Subnet and VirtualNetwork deletion with workloads, SecurityGroups,
  ACL associations, child Subnets, NATGateways, and ExternalIP references. Verify
  `FAILED_PRECONDITION`, complete blocker details, and unchanged backend state.
- Delete admitted leaf resources and verify only their own fabric state is
  removed; no tenant-managed child is cascaded.

## End-to-end tests

- In a connected single-hub deployment, create the supported IPv4 networking
  graph through API and CLI, provision a bare-metal workload, and verify VLAN
  reachability and status IP discovery.
- Create a NATGateway and verify permitted outbound traffic uses its ExternalIP;
  if the provider implementation is temporarily a no-op, verify the normal
  successful job/status result instead of a capability-gated API rejection.
- Verify allowed and denied ingress/egress traffic through explicit
  NetworkACL rules and the hard-coded deployment baseline.
- Verify ExternalIP inbound traffic and cleanup ordering.
- Verify invalid IPv6, multi-hub, air-gapped, and multi-interface requests fail
  before persistence or backend dispatch. Verify that a NATGateway request is
  not rejected merely because its provider operation is a no-op during
  development.
- Verify parent deletion with active dependents is rejected and reports every
  blocker; then delete resources leaf-first and verify successful cleanup.

## Graduation criteria

Every shared validation branch has a unit or integration assertion, every
supported agentless provisioning flow has an E2E case, and every rejected
operation leaves no partial resource, allocation, VLAN configuration, or
finalizer state.
