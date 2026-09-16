# Test Plan — OSAC-1435 VMaaS Networking IPv4 Boundary

## Scope

This plan covers IPv4 validation for VM network attachments, discovered VM
addresses, and automatic ExternalIP allocation. Multi-interface behavior is
outside this boundary split.

## Test cases

- Accept a Ready same-VirtualNetwork Subnet with a canonical IPv4 CIDR and
  reject IPv6, dual-stack, malformed, or non-Ready network inputs before VM
  persistence.
- Accept only canonical IPv4 VMI/status addresses in the resolved Subnet;
  reject IPv6, malformed, duplicate, or out-of-subnet addresses.
- Verify automatic external access selects a Ready IPv4 ExternalIPPool and
  creates an IPv4 ExternalIP; exhaustion leaves no VM, child resource, or
  capacity reservation behind.
- Verify invalid IPv4 input is rejected consistently by direct API, private
  handoff, and CLI documentation paths.
