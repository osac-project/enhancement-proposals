---
title: storage-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-09-27
last-updated: 2026-09-30
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

# Storage Networking (Phase 1)

| Field       | Value                                              |
|-------------|----------------------------------------------------|
| Author(s)   | Dan Manor                                          |
| Jira        | [OSAC-5690](https://redhat.atlassian.net/browse/OSAC-5690) |
| Date        | 2026-09-27                                         |

## Terminology

| Term | Definition |
|------|-----------|
| **VAST VIP** | A Virtual IP address exposed by the VAST storage cluster that workloads connect to for block storage data-plane operations. VIPs are managed by VAST and are located outside the managed network fabric gateway. |
| **Storage CIDR** | A dedicated IP range reserved at OSAC installation time for VAST VIP addresses. This CIDR must not overlap with any tenant VirtualNetwork CIDR and must route outside the fabric gateway. |
| **Per-Tenant VIP Pool** | Each tenant receives a dedicated VAST VIP pool. Storage tenant isolation at the network level is not required for the first phase, but per-tenant VIP pools exist on the VAST side. |

## Problem Statement

VMaaS, CaaS, and BMaaS workloads need a network path to remote VAST storage
for block workloads. The OSAC networking and storage subsystems are currently
independent: the storage design (OSAC-1332, OSAC-1111) assumes "CaaS cluster
nodes have network reachability to the storage backend" without specifying how
that reachability is achieved.

The first phase needs a clear, minimal routing and NAT solution for supported
consumers, subject to the network policy on the path, without waiting for a
full tenant-isolated storage network design. The following problems must be
solved:

1. **No defined network path from workloads to VAST.** Tenant workloads run
   inside isolated VirtualNetworks on the OSAC fabric. The VAST cluster runs
   outside the managed network fabric gateway. There is no mechanism today
   ensuring that traffic
   destined for VAST VIPs routes externally rather than being trapped within
   the fabric.

2. **IP overlap risk.** Tenants choose their own VirtualNetwork CIDRs (or
   receive defaults from NetworkClass). If a VN CIDR overlaps with the VAST
   VIP address range, packets destined for storage will be routed within the
   fabric instead of externally, breaking storage access silently.

3. **NAT capacity for storage traffic.** Block storage workloads generate
   concurrent NVMe-TCP sessions and CSI operations. The NATGateway's ExternalIP
   must support these connections. There is no guidance or validation today for
   NAT capacity relative to storage consumption.

If not addressed, storage will be unreachable from tenant workloads — blocking
the first phase.

## In Scope

- Network connectivity from VMaaS and CaaS environments to VAST block storage
  for use by the VAST CSI Driver, subject to the effective policy on tenant
  Subnets used by the storage data path. VMaaS CSI traffic originating on the
  management network is outside the tenant Subnet policy boundary.
- Network connectivity from BMaaS hosts to VAST block storage (network path
  only; tenant-side storage configuration remains manual), subject to the
  effective policy on the host's tenant Subnet.
- Document the NetworkACL prerequisite for tenant-Subnet storage traffic. The
  deployment `PERMIT` fallback permits unmatched traffic; under `DENY`, the
  selected Subnet must have a NetworkACL that permits storage traffic and its
  replies. A Subnet's ACL association is fixed at creation, so a workload using
  the default Subnet under `DENY` must use another Subnet created with the
  required ACL association.
- A dedicated Storage CIDR configured at OSAC installation time, reserved
  for VAST VIP addresses.
- Validation preventing tenants from creating VirtualNetworks whose CIDRs
  overlap with the Storage CIDR, ensuring storage-bound packets always
  route externally.
- Ensuring tenant VirtualNetworks used by CaaS workers or BMaaS hosts for
  block storage have a NATGateway with adequate NAT capacity for storage
  traffic.
- VAST block storage only.

## Out of Scope

- **File or object storage.** Only block storage is supported in the first phase.
- **Storage backends other than VAST.**
- **Storage tenant isolation at the network level.** Per-tenant VAST VIP pools
  exist but are not network-isolated from each other. Tenant-isolated storage
  networking is deferred to OSAC-5073.
- **Automating tenant storage configuration or CSI setup for BMaaS.** BMaaS
  tenants configure storage manually.
- **Direct-attach / VLAN-based storage networking.** This design assumes VAST
  is external and accessed over SNAT. Dedicated storage VLANs, SR-IOV, or
  RDMA paths are not covered.
- **Per-subnet or per-workload NAT.** NATGateway operates at the
  VirtualNetwork level. Per-subnet NAT granularity is future work.
- **Creating or associating NetworkACLs for storage.** Storage consumes the
  networking policy selected for the existing data path; it does not manage
  ACL resources, Subnet associations, or deployment fallback policy.
- **Storage traffic QoS or bandwidth reservation.**
- **East-west storage paths.** GPU-to-storage over east-west fabric
  (Spectrum-X, InfiniBand) is deferred per OSAC-1382.

## User Stories

### VMaaS and CaaS Users

- As a VMaaS or CaaS user, I want my workloads to reach VAST block storage
  through the VAST CSI Driver so that I can provision and mount
  PersistentVolumes when the applicable management-network or tenant-Subnet
  policy permits the storage traffic.

### BMaaS Tenants

- As a BMaaS tenant, I want the network path to VAST storage to be available
  when the effective policy on my Subnet permits the traffic so that I can
  configure storage manually if I choose to use it.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to configure a Storage CIDR at
  OSAC installation time so that the platform knows which IP range is reserved
  for VAST VIPs and can prevent conflicts with tenant networks.

- As a Cloud Infrastructure Admin, I want the platform to reject
  VirtualNetwork creation requests whose CIDR overlaps with the Storage
  CIDR so that storage-bound traffic always routes externally and never gets
  trapped in the fabric.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want a minimal connectivity path that can be
  delivered within the first phase timeframe so that storage is unblocked
  without requiring the full tenant-isolated storage network design.

- As a Cloud Provider Admin, I want the default VirtualNetwork CIDR configured
  in NetworkClass to be validated against the Storage CIDR so that newly
  onboarded tenants do not receive a default network that conflicts with
  storage.

## Assumptions

- The VAST cluster is deployed outside the managed network fabric gateway and
  is reachable from the fabric's external network. Tenants consume VAST over
  the network — there is no in-fabric VAST deployment for the first phase.

- Each tenant receives a dedicated VAST VIP pool. Storage tenant isolation at
  the network level is not required for the first phase — all tenants share
  the same SNAT path to VAST.

- SNAT via NATGateway is sufficient for tenant-Subnet block storage data-plane
  traffic, including CaaS and BMaaS NVMe-TCP sessions.
  The VMaaS CSI path uses the management network. No inbound (DNAT)
  connectivity from VAST to tenant workloads is required — all storage
  connections are initiated by the client side. Tenant Subnet ACLs are
  stateless, so replies are evaluated independently and must also be permitted
  when the deployment fallback is `DENY`.

- A single NATGateway ExternalIP per VirtualNetwork provides enough NAT
  capacity for the expected storage connection count in the first phase scope.

- The Storage CIDR is a single contiguous range configured once at
  installation and does not change during the deployment's lifetime.

- Tenant VirtualNetworks used by CaaS workers or BMaaS hosts for block storage
  must have a NATGateway configured. The VMaaS CSI path uses the
  management network. The default VirtualNetwork created during tenant
  onboarding already includes a NATGateway, but that does not guarantee
  connectivity when the deployment ACL fallback is `DENY`. Its default Subnet
  has no ACL association; workloads requiring storage in that deployment need
  a different Subnet created with an ACL that permits the traffic.

- BMaaS hosts use their tenant Subnet for network connectivity to VAST;
  storage traffic is available only when the effective Subnet policy permits
  it. BMaaS tenants are responsible for configuring storage on their hosts.

## Dependencies

- **Unified Networking (OSAC-1433):** VirtualNetwork, NATGateway, ExternalIP,
  NetworkACL, and NetworkClass must be implemented and operational. Storage
  networking builds on these primitives — it does not introduce new networking
  resources. Tenant-Subnet data paths require the deployment fallback or the
  Subnet's associated NetworkACL to permit both the client traffic and, under a
  `DENY` fallback, its replies.

- **Storage Backend & Tier (OSAC-1111, OSAC-1110):** StorageBackend
  registration and StorageTier assignment must be functional so that the VAST
  endpoint and Global VIP Pool information is available.

- **CaaS Cluster Storage (OSAC-1332):** The storage controller that installs
  CSI drivers and StorageClasses on tenant clusters must be operational. This
  PRD addresses the network reachability prerequisite that OSAC-1332 assumes.

- **Tenant Onboarding (Default Networking — OSAC-1433):** The default
  networking onboarding flow must validate the Storage CIDR constraint and
  ensure NATGateway provisioning.

- **OSAC-5073 (Shared VAST Global VIP Pool):** This feature implements the
  reduced first phase scope of OSAC-5073. The broader effort covers
  tenant-isolated storage networking beyond the first phase.

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ 2293f9140
Phases: revise, revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
