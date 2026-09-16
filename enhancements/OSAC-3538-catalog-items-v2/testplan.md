# Test Plan — OSAC-3538 Catalog Networking IPv4 Boundary

## Scope

This plan verifies that Catalog Item materialization preserves the shared
IPv4-only networking contract and delegates final validation to the owning
resource API.

## Test cases

- Accept catalog defaults and tenant-supplied networking fields that use
  canonical IPv4 CIDRs and typed local references.
- Reject IPv6, dual-stack, malformed, noncanonical, and host-bit-set values
  during materialization or final resource validation.
- Verify Catalog-created VM, Cluster, and BM resources receive the same IPv4
  validation and address-family behavior as equivalent direct creates.
- Verify a rejected Catalog request persists neither a partially materialized
  resource nor a backend allocation.
