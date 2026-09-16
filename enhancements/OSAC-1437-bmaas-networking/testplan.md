# Test Plan — OSAC-1437 BMaaS Networking IPv4 Boundary

## Scope

This plan covers IPv4 validation for BaremetalInstance attachments, DHCP
discovery feedback, and automatic ExternalIP allocation.

## Test cases

- Accept a Ready same-VirtualNetwork Subnet with a canonical IPv4 CIDR and
  reject IPv6, dual-stack, malformed, or non-Ready attachment input before
  BaremetalInstance persistence.
- Publish only one canonical IPv4 address for the resolved interface; reject
  IPv6, malformed, duplicate, wrong-subnet, and multiple-lease feedback.
- Verify automatic external access selects a Ready IPv4 ExternalIPPool and
  creates an IPv4 ExternalIP; exhaustion leaves no BaremetalInstance, child
  resource, port move, or capacity reservation behind.
- Verify invalid IPv4 input is rejected before provisioning-network changes or
  backend dispatch.
