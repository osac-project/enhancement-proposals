# Test Plan — OSAC-1433 Default Networking IPv4 Boundary

## Scope

This plan verifies that tenant defaults use the shared canonical IPv4
contract, and that invalid address-family input cannot create partial default
resources.

## Test cases

- Accept required canonical IPv4 VirtualNetwork and Subnet CIDRs when the
  Subnet is contained by the VirtualNetwork.
- Reject IPv6, dual-stack, malformed, noncanonical, and host-bit-set default
  CIDRs before NetworkClass or tenant default resources are persisted.
- Verify onboarding creates only the IPv4 default VirtualNetwork and Subnet
  and that readiness does not depend on an IPv6 resource.
- Verify automatic ExternalIP selection considers only Ready IPv4 pools and
  returns the documented exhaustion error without persisting the tenant
  workload or allocation.
- Verify omitted workload networking resolves to the IPv4 default Subnet and
  that all resolved addresses are canonical IPv4 values.
