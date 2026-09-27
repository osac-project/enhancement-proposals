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
| **VAST VIP** | A Virtual IP address exposed by the VAST storage cluster that tenant workloads connect to for NFS or block storage data-plane operations. VIPs are managed by VAST and are external to the OSAC fabric. |
| **Storage VIP CIDR** | A dedicated IP range reserved at OSAC installation time for VAST tenant VIP addresses. This CIDR must not overlap with any tenant VirtualNetwork CIDR and must route externally (outside the fabric). |
| **NAT pool** | The set of ExternalIPs available for SNAT on a NATGateway. For storage-consuming workloads, the NAT pool must be large enough to handle concurrent storage connections from all resources in the VirtualNetwork. |

## Problem Statement

OSAC tenants need persistent storage on their CaaS clusters and VMaaS VMs. The
storage backend (VAST) provides NFS and block storage via VIP addresses. Today,
the OSAC networking and storage subsystems are independent: the storage design
(OSAC-1332, OSAC-1111) assumes "CaaS cluster nodes have network reachability to
the storage backend" without specifying how that reachability is achieved.

Without an explicit networking design for storage access, the following problems
arise:

1. **No defined network path from tenant workloads to VAST.** Tenant workloads
   run inside isolated VirtualNetworks on the OSAC fabric. The VAST cluster runs
   outside the datacenter. There is no mechanism today ensuring that tenant
   traffic destined for VAST VIPs routes externally rather than being trapped
   within the fabric.

2. **IP overlap risk.** Tenants choose their own VirtualNetwork CIDRs (or
   receive defaults from NetworkClass). If a tenant's VN CIDR overlaps with the
   VAST VIP address range, packets destined for storage will be routed within
   the fabric instead of externally, breaking storage access silently.

3. **NAT pool sizing for storage.** Storage workloads generate many concurrent
   connections (one per NFS mount, iSCSI session, or CSI operation). The
   NATGateway's NAT pool (ExternalIP) must be large enough to support these
   connections. There is no guidance or validation today for NAT pool sizing
   relative to storage consumption.

4. **No storage-aware tenant onboarding.** Default networking onboarding creates
   a VirtualNetwork, Subnet, and NATGateway, but does not account for storage
   requirements — there is no validation that the default VN CIDR avoids the
   storage VIP range or that the NAT pool is adequate.

If not addressed, storage will be unreachable from tenant workloads, or will
fail intermittently due to NAT exhaustion or routing conflicts — blocking the
0.4 dev preview.

## In Scope

- Defining how tenant workloads reach the external VAST cluster over the
  network using SNAT via NATGateway.
- A dedicated Storage VIP CIDR configured at OSAC installation time that is
  reserved for VAST tenant VIP addresses.
- Validation preventing tenants from creating VirtualNetworks whose CIDRs
  overlap with the Storage VIP CIDR, ensuring storage-bound packets always
  route externally.
- Requirements for NATGateway and NAT pool sizing to support storage traffic
  from tenant VirtualNetworks.
- Updates to tenant onboarding to ensure the default VirtualNetwork and
  NATGateway are storage-ready.

## Out of Scope

- **Direct-attach / VLAN-based storage networking.** This design assumes VAST
  is external and accessed over SNAT. Dedicated storage VLANs, SR-IOV, or
  RDMA paths are not covered.
- **Multi-backend routing.** Only VAST is supported as a storage backend in
  0.4. Routing to multiple storage backends with different network paths is
  deferred.
- **Per-subnet or per-workload NAT.** NATGateway operates at the
  VirtualNetwork level. Per-subnet NAT granularity is future work.
- **Storage traffic QoS or bandwidth reservation.** No network-level QoS
  policies for storage traffic are included.
- **East-west storage paths.** GPU-to-storage over east-west fabric
  (Spectrum-X, InfiniBand) is deferred per OSAC-1382.
- **Air-gapped or disconnected deployments.** Only connected deployments are
  supported.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure a Storage VIP CIDR at
  OSAC installation time so that the platform knows which IP range is reserved
  for VAST tenant VIPs and can prevent conflicts with tenant networks.

- As a Cloud Infrastructure Admin, I want the platform to reject
  VirtualNetwork creation requests whose CIDR overlaps with the Storage VIP
  CIDR so that tenant traffic destined for storage always routes externally
  and never gets trapped in the fabric.

- As a Cloud Infrastructure Admin, I want visibility into whether a tenant's
  NATGateway is correctly configured for storage access so that I can
  troubleshoot connectivity issues between tenant workloads and the VAST
  cluster.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want the default VirtualNetwork CIDR configured
  in NetworkClass to be validated against the Storage VIP CIDR so that newly
  onboarded tenants do not receive a default network that conflicts with
  storage.

- As a Cloud Provider Admin, I want guidance on NAT pool sizing relative to
  the number of tenants and their expected storage consumption so that I can
  provision enough ExternalIPs to avoid NAT exhaustion under storage load.

### Tenant Admin

- As a Tenant Admin, I want my CaaS clusters and VMaaS VMs to have network
  connectivity to the storage backend without additional manual configuration
  so that persistent storage works out of the box when a StorageClass is
  assigned to my tenant.

- As a Tenant Admin, I want a clear error when I attempt to create a
  VirtualNetwork with a CIDR that conflicts with the storage VIP range so
  that I understand why the request was rejected and can choose a
  non-conflicting CIDR.

### Tenant User

- As a Tenant User, I want to provision PersistentVolumeClaims on my CaaS
  cluster using the assigned StorageClass and have them successfully mount
  without needing to understand the underlying network topology so that I can
  focus on my workloads.

## Assumptions

- The VAST cluster is deployed outside the OSAC datacenter and is reachable
  from the OSAC fabric's external network (internet or WAN). Tenants consume
  VAST over the network — there is no in-fabric VAST deployment for 0.4.

- Each tenant receives a dedicated VAST VIP pool. VIPs within that pool are
  drawn from the platform-wide Storage VIP CIDR. The VAST administrator
  configures VIP pools from this CIDR during tenant onboarding.

- SNAT via NATGateway is sufficient for storage data-plane traffic (NFS
  mounts, iSCSI sessions). No inbound (DNAT) connectivity from VAST to
  tenant workloads is required — all storage connections are initiated by the
  tenant side.

- A single NATGateway ExternalIP per VirtualNetwork provides enough NAT
  capacity for the expected storage connection count in the 0.4 dev preview
  scope. NAT pool expansion (multiple ExternalIPs per NATGateway) is future
  work if connection limits are hit.

- The Storage VIP CIDR is a single contiguous range configured once at
  installation and does not change during the deployment's lifetime.

- All tenant VirtualNetworks that host workloads requiring storage must have
  a NATGateway configured. The default VirtualNetwork created during tenant
  onboarding already includes a NATGateway.

## Dependencies

- **Unified Networking (OSAC-1433):** VirtualNetwork, NATGateway, ExternalIP,
  and NetworkClass must be implemented and operational. Storage networking
  builds on these primitives — it does not introduce new networking resources.

- **Storage Backend & Tier (OSAC-1111, OSAC-1110):** StorageBackend
  registration and StorageTier assignment must be functional so that tenants
  have VAST VIP pool information available.

- **CaaS Cluster Storage (OSAC-1332):** The storage controller that installs
  CSI drivers and StorageClasses on tenant clusters must be operational. This
  PRD addresses the network reachability prerequisite that OSAC-1332 assumes.

- **Tenant Onboarding (Default Networking — OSAC-1433):** The default
  networking onboarding flow must be extended to validate the Storage VIP CIDR
  constraint and ensure NATGateway provisioning.

- **VAST Administration:** The VAST cluster administrator must allocate
  per-tenant VIP pools from the Storage VIP CIDR. This is an operational
  dependency outside the OSAC platform.
