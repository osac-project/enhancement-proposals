---
title: storage-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-09-27
last-updated: 2026-09-27
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5690
see-also:
  - enhancements/OSAC-1433-unified-networking/prd.md
  - enhancements/OSAC-1111-storage-backend/prd.md
  - enhancements/OSAC-1110-storage-tier/prd.md
  - enhancements/OSAC-1332-caas-cluster-storage/prd.md
  - enhancements/OSAC-1435-vmaas-networking/prd.md
  - enhancements/OSAC-1436-caas-networking/prd.md
---

# Storage Networking for Dev Preview (0.4)

| Field       | Value                                              |
|-------------|----------------------------------------------------|
| Author(s)   | Dan Manor                                          |
| Jira        | [OSAC-5690](https://redhat.atlassian.net/browse/OSAC-5690) |
| Date        | 2026-09-27                                         |

## Terminology

| Term | Definition |
|------|-----------|
| **VAST VIP** | A Virtual IP address exposed by the VAST storage cluster that workloads connect to for block storage data-plane operations. VIPs are managed by VAST and are external to the OSAC fabric. |
| **Storage VIP CIDR** | A dedicated IP range reserved at OSAC installation time for VAST VIP addresses. This CIDR must not overlap with any tenant VirtualNetwork CIDR and must route externally (outside the fabric). |
| **Global VIP Pool** | A shared (not per-tenant) VAST VIP pool used by all OSAC consumers in Dev Preview. Storage tenant isolation is not required. |

## Problem Statement

VMaaS, CaaS, and BMaaS workloads need a network path to remote VAST storage
for block workloads. The OSAC networking and storage subsystems are currently
independent: the storage design (OSAC-1332, OSAC-1111) assumes "CaaS cluster
nodes have network reachability to the storage backend" without specifying how
that reachability is achieved.

Dev Preview 0.4 needs a clear, minimal connectivity solution that allows
supported consumers to reach the VAST backend without waiting for a full
tenant-isolated storage network design. The following problems must be solved:

1. **No defined network path from workloads to VAST.** Tenant workloads run
   inside isolated VirtualNetworks on the OSAC fabric. The VAST cluster runs
   outside the datacenter. There is no mechanism today ensuring that traffic
   destined for VAST VIPs routes externally rather than being trapped within
   the fabric.

2. **IP overlap risk.** Tenants choose their own VirtualNetwork CIDRs (or
   receive defaults from NetworkClass). If a VN CIDR overlaps with the VAST
   VIP address range, packets destined for storage will be routed within the
   fabric instead of externally, breaking storage access silently.

3. **NAT capacity for storage traffic.** Block storage workloads generate
   concurrent iSCSI sessions and CSI operations. The NATGateway's ExternalIP
   must support these connections. There is no guidance or validation today for
   NAT capacity relative to storage consumption.

If not addressed, storage will be unreachable from tenant workloads — blocking
the 0.4 dev preview.

## In Scope

- Network connectivity from VMaaS and CaaS environments to VAST block storage
  for use by the VAST CSI Driver.
- Network connectivity from BMaaS hosts to VAST block storage (network path
  only; tenant-side storage configuration remains manual).
- A dedicated Storage VIP CIDR configured at OSAC installation time, reserved
  for VAST VIP addresses.
- Validation preventing tenants from creating VirtualNetworks whose CIDRs
  overlap with the Storage VIP CIDR, ensuring storage-bound packets always
  route externally.
- Ensuring VirtualNetworks that host storage-consuming workloads have a
  NATGateway with adequate NAT capacity for storage traffic.
- VAST block storage only.

## Out of Scope

- **File or object storage.** Only block storage is supported in 0.4.
- **Storage backends other than VAST.**
- **Storage tenant isolation.** A shared Global VIP Pool is used by all
  consumers. Per-tenant VIP pools and tenant-isolated storage networking are
  deferred to OSAC-5073.
- **Automating tenant storage configuration or CSI setup for BMaaS.** BMaaS
  tenants configure storage manually.
- **Direct-attach / VLAN-based storage networking.** This design assumes VAST
  is external and accessed over SNAT. Dedicated storage VLANs, SR-IOV, or
  RDMA paths are not covered.
- **Per-subnet or per-workload NAT.** NATGateway operates at the
  VirtualNetwork level. Per-subnet NAT granularity is future work.
- **Storage traffic QoS or bandwidth reservation.**
- **East-west storage paths.** GPU-to-storage over east-west fabric
  (Spectrum-X, InfiniBand) is deferred per OSAC-1382.

## User Stories

### VMaaS and CaaS Users

- As a VMaaS or CaaS user, I want my workloads to reach VAST block storage
  through the VAST CSI Driver so that I can provision and mount
  PersistentVolumes without needing to understand the underlying network
  topology.

### BMaaS Tenants

- As a BMaaS tenant, I want the network path to VAST storage to be available
  so that I can configure storage manually if I choose to use it.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure a Storage VIP CIDR at
  OSAC installation time so that the platform knows which IP range is reserved
  for VAST VIPs and can prevent conflicts with tenant networks.

- As a Cloud Infrastructure Admin, I want the platform to reject
  VirtualNetwork creation requests whose CIDR overlaps with the Storage VIP
  CIDR so that storage-bound traffic always routes externally and never gets
  trapped in the fabric.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want a minimal Dev Preview connectivity path
  that can be delivered within the 0.4 timeframe so that storage is unblocked
  without requiring the full tenant-isolated storage network design.

- As a Cloud Provider Admin, I want the default VirtualNetwork CIDR configured
  in NetworkClass to be validated against the Storage VIP CIDR so that newly
  onboarded tenants do not receive a default network that conflicts with
  storage.

## Assumptions

- The VAST cluster is deployed outside the OSAC datacenter and is reachable
  from the OSAC fabric's external network (internet or WAN). Tenants consume
  VAST over the network — there is no in-fabric VAST deployment for 0.4.

- A shared Global VIP Pool is used by all consumers. Storage tenant isolation
  is not required for Dev Preview. Per-tenant VIP pools are deferred to
  OSAC-5073.

- SNAT via NATGateway is sufficient for block storage data-plane traffic
  (iSCSI sessions, CSI operations). No inbound (DNAT) connectivity from VAST
  to tenant workloads is required — all storage connections are initiated by
  the client side.

- A single NATGateway ExternalIP per VirtualNetwork provides enough NAT
  capacity for the expected storage connection count in the 0.4 dev preview
  scope.

- The Storage VIP CIDR is a single contiguous range configured once at
  installation and does not change during the deployment's lifetime.

- All tenant VirtualNetworks that host workloads requiring storage must have a
  NATGateway configured. The default VirtualNetwork created during tenant
  onboarding already includes a NATGateway.

- BMaaS hosts have network connectivity to VAST through their management or
  fabric network interface. BMaaS tenants are responsible for configuring
  storage on their hosts.

## Dependencies

- **Unified Networking (OSAC-1433):** VirtualNetwork, NATGateway, ExternalIP,
  and NetworkClass must be implemented and operational. Storage networking
  builds on these primitives — it does not introduce new networking resources.

- **Storage Backend & Tier (OSAC-1111, OSAC-1110):** StorageBackend
  registration and StorageTier assignment must be functional so that the VAST
  endpoint and Global VIP Pool information is available.

- **CaaS Cluster Storage (OSAC-1332):** The storage controller that installs
  CSI drivers and StorageClasses on tenant clusters must be operational. This
  PRD addresses the network reachability prerequisite that OSAC-1332 assumes.

- **Tenant Onboarding (Default Networking — OSAC-1433):** The default
  networking onboarding flow must validate the Storage VIP CIDR constraint and
  ensure NATGateway provisioning.

- **OSAC-5073 (Shared VAST Global VIP Pool):** This feature implements the
  reduced Dev Preview scope of OSAC-5073. The broader effort covers
  tenant-isolated storage networking beyond 0.4.
