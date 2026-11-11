# Fabric Manager — Netris

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2434 |
| Date        | 2026-11-08 |

This PRD inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary)
(connected, IPv4 deployments) and the [networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary)
(one provider-owned hub). The [Network Manager Integration
Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md)
defines what every Fabric Manager provides; this PRD covers the Fabric Manager
for providers whose fabric is run by a Netris controller.

## Problem Statement

A cloud provider whose data-center fabric is managed by Netris needs that
fabric to carry its tenants' networks, external addresses and outbound access
for VMs, bare-metal servers and clusters. OSAC ships a Netris Fabric Manager
and runs its VM networking lab on it, but no published document says what a
provider gets from it, what the provider prepares, and where it behaves
differently from the shared contract. Without that, a Cloud Infrastructure
Admin cannot judge whether Netris fits a deployment, a tenant cannot tell
which protections apply to bare metal, and reviewers cannot check the
manager against an agreed behavior.

## In Scope

- One Netris Fabric Manager serves every workload service: VMs, bare-metal
  servers, clusters, and Ethernet east-west domains for bare-metal servers.
- It works with OSAC's EVPN Kubernetes manager, so VMs and bare-metal servers
  can share a Subnet.
- Routing between Subnets of one VirtualNetwork. Bare-metal servers can use
  every Subnet; VMs can use only the VirtualNetwork's first Subnet until
  OSAC's EVPN Kubernetes manager supports more.
- External addresses: provider pools, tenant external addresses, inbound
  access to a workload, outbound access for a VirtualNetwork, and a
  cluster's ingress address.
- Installation from OSAC's own release: the provider selects Netris and
  supplies its Netris controller settings, and needs no separate image or
  registration step.
- A published list of the provider's installation prerequisites, the
  settings, and every place where Netris differs from the shared contract.

## Out of Scope

- SecurityGroup filtering on the Netris fabric. VMs are filtered on the hub
  by OSAC's Kubernetes manager; bare-metal servers and cluster workers on a
  Netris deployment are not filtered by SecurityGroups.
- Per-VirtualNetwork DNS. Bare-metal servers get the resolver the provider
  configured in Netris for the installation; VMs get the cluster DNS.
- Network types other than EVPN, and IPv6.
- Building or upgrading the Netris controller, switches and gateways, and
  the fabric's peering with the hub nodes; these stay provider work.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select Netris as the Fabric
  Manager at installation and supply my Netris controller address,
  credentials, site, tenant and the provider networks OSAC uses so that OSAC networking runs on my existing
  fabric without a provider-built image.
- As a Cloud Infrastructure Admin, I want a documented list of the Netris
  objects and fabric settings I must prepare (the bare-metal provisioning
  network, the management network for provider endpoints, the private range
  Netris reserves, the installation DNS resolver) so that the first tenant
  network works without trial and error.
- As a Cloud Infrastructure Admin, I want every OSAC object in Netris named
  after the OSAC resource it belongs to so that I can find the Netris
  objects of any OSAC resource from the Netris console.
- As a Cloud Infrastructure Admin, I want an external address pool I create
  in OSAC to become usable addresses on the Netris fabric so that tenants can
  get external addresses from it.
- As a Cloud Infrastructure Admin, I want a failed Netris operation to show
  in the resource's status with a plain message that says whether OSAC will
  retry and what to fix so that I can repair settings or fabric objects
  without reading job logs.
- As a Cloud Infrastructure Admin, I want OSAC to refuse to change a Netris
  object outside OSAC's Netris tenant or network, even one with a matching
  name, so that tenant networks never take over objects of another tenant or
  of the provider.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want each VirtualNetwork I create to be
  isolated on the fabric from every other VirtualNetwork, even one with the
  same address range, so that my traffic never reaches another network.
- As a Tenant Admin or Tenant User, I want a VM and a bare-metal server on the
  same Subnet to reach each other directly so that one application can span
  both.
- As a Tenant Admin or Tenant User, I want workloads on different Subnets of
  one VirtualNetwork to reach each other through the Subnet gateway so that I
  can split an application across Subnets.
- As a Tenant Admin or Tenant User, I want a bare-metal server I order on a
  Subnet to get an address from that Subnet automatically and see it in the
  server's details so that I can connect to it without manual setup.
- As a Tenant Admin or Tenant User, I want to attach an external address to a
  VM or bare-metal server so that clients outside my network can reach it.
- As a Tenant Admin or Tenant User, I want my VirtualNetwork's outbound
  traffic to leave through one external address so that my workloads can
  reach the internet and I know which address remote services see.
- As a Tenant Admin or Tenant User, I want a cluster I create on a Netris
  deployment to get a reachable ingress address so that its applications
  answer from outside.
- As a Tenant Admin or Tenant User, I want to know that SecurityGroups filter
  my VMs but not my bare-metal servers on a Netris deployment so that I
  protect bare-metal servers another way.

## Assumptions

- The Netris controller keeps the network identifiers it assigns for the
  whole life of a network, so tenant networks keep working across controller
  restarts and upgrades.
- The Netris fabric can be configured to exchange routes with the hub nodes
  the way OSAC's EVPN Kubernetes manager expects, which inter-Subnet routing
  between VMs and bare metal needs.

## Dependencies

- **Network Manager Integration Contract (OSAC-1433):** defines the tasks,
  inputs, results and conformance tests this manager implements.
- **CUDN EVPN Kubernetes manager (OSAC-4291):** connects VMs to the Subnets
  the Netris manager builds; VMs on Netris need it.
- **BMaaS networking (OSAC-1437):** bare-metal servers on Netris depend on
  BMaaS driving the network handoff and address discovery through the
  contract.
- **CaaS networking (OSAC-1436):** clusters on Netris depend on CaaS
  choosing each cluster's ingress address and attaching workers through
  BMaaS. Netris only carries the address's traffic.
- **Multi-Fabric East-West Networking (OSAC-1382):** defines the Ethernet
  east-west domains Netris builds.
- **Netris controller and its Ansible collection:** a supported controller
  version reachable from the OSAC job pods, and the collection OSAC vendors.
- **Provider fabric preparation:** EVPN peering between the fabric and the
  hub nodes, the bare-metal provisioning network, and the management network
  must exist before the first tenant network.
