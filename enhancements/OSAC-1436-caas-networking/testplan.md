# Test Plan — OSAC-1436 CaaS Networking IPv4 Boundary

## Scope

This plan covers IPv4 validation for Cluster attachments, MetalLB/API/Ingress
endpoint feedback, and automatic ExternalIP allocation.

## Test cases

- Accept exactly one Ready same-VirtualNetwork Subnet with a canonical IPv4
  CIDR and reject IPv6, dual-stack, malformed, or duplicate references before
  Cluster persistence.
- Accept only canonical IPv4 API and ingress endpoint values in the permitted
  Subnet/VIP range; reject IPv6, malformed, duplicate, and out-of-subnet
  feedback.
- Verify automatic external access reserves two distinct IPv4 ExternalIPs
  atomically and that exhaustion or invalid endpoint feedback leaves no
  Cluster, child attachment, or capacity reservation behind.
- Verify the private worker handoff preserves IPv4-only Subnet and endpoint
  validation.
