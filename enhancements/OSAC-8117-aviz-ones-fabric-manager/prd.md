# Fabric Manager — Aviz ONES

| Field       | Value   |
|-------------|---------|
| Author(s)   | Sutharsan <sutharsan@aviznetworks.com> |
| Jira        | https://redhat.atlassian.net/browse/OSAC-8117 |
| Date        | 2026-11-24 |

This PRD inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary)
(connected, IPv4 deployments) and the [networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary)
(one provider-owned hub). The [Network Manager Integration
Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md)
defines what every Fabric Manager provides; this PRD covers the Fabric Manager
for providers whose fabric is managed by an Aviz ONES controller. The manager
is the `aviz.ones` Ansible collection, maintained by Aviz Networks and vendored
by OSAC, with WG Connectivity & Fabric reviewing the OSAC-side integration.

This phase delivers bare-metal servers. VM support follows in a later phase.

## Problem Statement

A cloud provider whose data-center fabric is managed by Aviz ONES needs that
fabric to carry its tenants' bare-metal servers: Subnet addressing, external
addresses, outbound access and isolation through the OSAC networking API. OSAC
ships Netris and agentless VLAN Fabric Managers, but no published document says
what a provider gets from an ONES manager, what the provider prepares, and
where it behaves differently from the shared contract. Without that, a Cloud
Infrastructure Admin cannot judge whether ONES fits a deployment, a tenant
cannot tell which protections apply to bare metal, and reviewers cannot check
the manager against an agreed behavior.

## In Scope

- One Aviz ONES Fabric Manager serves bare-metal servers on an ONES-run
  fabric, through the existing OSAC networking API.
- Subnet addressing: a bare-metal server ordered on a Subnet gets an address
  from that Subnet's fabric share and reports it in the server's details.
- Isolation: each VirtualNetwork is isolated on the fabric from every other
  VirtualNetwork, even one with the same address range.
- External addresses: provider pools, tenant external addresses, inbound
  access to a bare-metal server, and outbound access for a VirtualNetwork.
- Installation from OSAC's own release: the provider selects ONES and supplies
  its ONES controller settings, and applies the manager's registration with the
  documented procedure.
- A published list of the provider's installation prerequisites, the settings,
  and every place where ONES differs from the shared contract.

## Out of Scope

- VMs and their overlay attachment. VMs are the next phase.
- Cluster guest ingress address reservation, unless the manager implements the
  contract task in this phase.
- SecurityGroup enforcement on the ONES fabric. ONES has no per-port
  enforcement, so the manager declares the documented physical no-op
  capability and bare-metal traffic stays unfiltered.
- Per-VirtualNetwork DNS and IPv6.
- Network types other than EVPN.
- Building or upgrading the ONES controller, switches and gateways, and the
  fabric's peering with the hub nodes; these stay provider work.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want ONES-backed fabrics offered as a supported
  networking option so that customers standardized on Aviz can adopt OSAC
  without replacing their fabric.
- As a Cloud Provider Admin, I want to know that this phase covers bare-metal
  servers and that VMs follow so that I can set customer expectations before
  onboarding.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select ONES as the Fabric Manager
  at installation and supply my ONES API endpoint and credentials so that OSAC
  networking runs on the fabric I already run in ONES.
- As a Cloud Infrastructure Admin, I want a documented list of the ONES
  objects and settings I must prepare (a Fabric created in ONES, the ONES
  controller and API reachable from the OSAC job pods, and the ONES internal
  pools excluded from tenant ranges) so that the first tenant network works
  without trial and error.
- As a Cloud Infrastructure Admin, I want every OSAC object in ONES named
  after the OSAC resource it belongs to so that I can find the ONES objects of
  any OSAC resource from the ONES console.
- As a Cloud Infrastructure Admin, I want an external address pool I create in
  OSAC to become usable addresses on the ONES fabric so that tenants can get
  external addresses from it.
- As a Cloud Infrastructure Admin, I want a failed ONES operation to show in
  the resource's status with a plain message that says whether OSAC will retry
  and what to fix so that I can repair settings or fabric objects without
  reading job logs.
- As a Cloud Infrastructure Admin, I want OSAC to refuse to change an ONES
  object outside OSAC's own scope, even one with a matching name, so that
  tenant networks never take over objects of another tenant or of the provider.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want each VirtualNetwork I create to be
  isolated on the fabric from every other VirtualNetwork, even one with the
  same address range, so that my traffic never reaches another network.
- As a Tenant Admin or Tenant User, I want a bare-metal server I order on a
  Subnet to get an address from that Subnet automatically and see it in the
  server's details so that I can connect to it without manual setup.
- As a Tenant Admin or Tenant User, I want to attach an external address to a
  bare-metal server so that clients outside my network can reach it.
- As a Tenant Admin or Tenant User, I want my VirtualNetwork's outbound traffic
  to leave through one external address so that my workloads can reach the
  internet and I know which address remote services see.
- As a Tenant Admin or Tenant User, I want to know that SecurityGroups do not
  filter my bare-metal servers on an ONES deployment so that I protect them
  another way.

## Assumptions

- ONES keeps the network identifiers it assigns for the whole life of a
  network, so tenant networks keep working across controller restarts and
  upgrades.
- The ONES fabric can be configured to exchange routes with the hub nodes the
  way OSAC expects, which inter-Subnet routing between bare-metal servers
  needs.
- ONES internal pools are known to the provider and excluded from every tenant
  range.

## Dependencies

- **Network Manager Integration Contract (OSAC-1433):** defines the tasks,
  inputs, results and conformance tests this manager implements.
- **BMaaS networking (OSAC-1437):** bare-metal servers on ONES depend on BMaaS
  driving the network handoff and address discovery through the contract.
- **Aviz ONES controller:** API v4.5.0, reachable from the OSAC job pods.
- **`aviz.ones` Ansible collection:** version 0.1.0, Apache-2.0, with no
  dependency beyond Ansible; maintained by Aviz Networks, vendored by OSAC,
  and named as the manager registration's `ansible_role`.
- **Physical SecurityGroup no-op capability:** the
  `security_group_physical_noop` registration capability and its derived
  NetworkClass status are in the accepted contract but are not implemented in
  OSAC yet. This manager needs that support before it can declare the
  capability.
- **Provider fabric preparation:** a Fabric created in ONES, the ONES
  controller and API reachable from the OSAC job pods, and the ONES internal
  pools excluded from tenant ranges.
- **Contribution terms:** Aviz works from a fork with no upstream write access;
  every commit carries DCO sign-off; licensing is Apache-2.0 inbound and
  outbound, with any corporate CLA handled by Red Hat Legal outside the
  repository. WG Connectivity & Fabric reviews and merges the OSAC-side
  integration - registration, installer wiring and vendored collection
  updates - with a CODEOWNERS entry for those paths; no secrets, partner-only
  tooling, or unvetted vendored collections.
