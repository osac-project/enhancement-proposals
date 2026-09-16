# Test Plan — OSAC-1433 Unified Networking IPv4 Boundary

## Scope

This plan verifies the shared IPv4-only networking contract across the public
API, manager capability resolution, persistence, backend dispatch, and status
feedback. It covers documentation-level requirements for VMaaS, CaaS, and
BMaaS consumers; service-specific behavior remains in their respective plans.

## Test cases

### Canonical address validation

- Accept canonical dotted-decimal IPv4 CIDRs with zero host bits and canonical
  dotted-decimal IPv4 addresses without a CIDR suffix.
- Reject IPv6, dual-stack, malformed, noncanonical, and host-bit-set values
  before persistence or backend dispatch.
- Require Subnet CIDRs to be contained by their parent VirtualNetwork and
  reject overlapping sibling Subnets.

### Provider and manager boundaries

- Accept only `addressFamily: ipv4` in manager capabilities and NetworkClass
  status; reject IPv6, dual-stack, or mismatched manager registrations.
- Accept only `IPV4` ExternalIPPools with canonical IPv4 CIDRs; reject
  unspecified families and IPv6/dual-stack pools.
- Treat invalid manager-reported addresses or status feedback as provisioning
  failures and never mark the resource Ready.

### Cross-service smoke coverage

- Create valid IPv4 VirtualNetwork, Subnet, ExternalIPPool, ExternalIP, and
  workload attachments through VMaaS, CaaS, and BMaaS paths.
- Verify every persisted and reported address remains IPv4 and that rejected
  requests leave no resource, allocation, or backend side effect.
