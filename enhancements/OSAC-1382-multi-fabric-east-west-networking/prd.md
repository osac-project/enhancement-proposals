# Multi-Fabric East-West Networking for AI Workloads

| Field       | Value   |
|-------------|---------|
| Author(s)   | Vladik Romanovsky |
| Jira        | [OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382) |
| Date        | 2026-07-14 |

## Problem Statement

AI workloads running in shared, multi-tenant sovereign AI clouds require high-bandwidth, low-latency east-west connectivity for inter-GPU communication during distributed training (collective operations via RDMA over InfiniBand/RoCE) and cross-node coordination for multi-tier AI applications. At the same time, hard tenant isolation must be enforced across all fabric types to prevent data leakage.

Today, provisioning east-west connectivity across heterogeneous fabrics (Ethernet/Spectrum-X, InfiniBand, NVLink) requires manual, error-prone coordination. This results in slow AI tenant onboarding, high operational overhead, risk of misaligned isolation boundaries across fabrics, and inability to offer predictable high-performance east-west out of the box.

OSAC's unified networking model (EP #50) provides north-south connectivity and general workload support. Per-service networking extensions (CaaS in EP #107, with VMaaS and BMaaS planned) build on this foundation. However, none of these address automated east-west provisioning or unified multi-fabric tenant isolation for AI workloads.

## In Scope (Phase 1)

- Declarative east-west connectivity for AI workloads on Ethernet-based fabrics.
- East-west capabilities and defaults expressed through the existing NetworkClass and VirtualNetwork model — no new top-level resource types.
- Automated enforcement of multi-tenant isolation on east-west paths, enforced at the fabric level by the fabric manager.
- Tenant onboarding provisions both north-south and east-west isolation domains as a single operation.
- Integration with the unified networking primitives (EP #50) and compatible with per-service extensions (EP #107).
- Operator documentation for configuring east-west capable NetworkClasses.

**Phase 1 approach:** Phase 1 uses Netris as the fabric manager, with AAP roles for east-west provisioning (VRF lifecycle, port assignment via L3VPN over VXLAN). The fabric manager capability contract — what any fabric manager must support for east-west isolation — will be defined in the design document; Phase 1 implementation is Netris-scoped but the OSAC API will not hard-code Netris-specific concepts.

## Out of Scope

- Full InfiniBand east-west support (PKey management, SHARP, UFM integration) — planned for Phase 2+.
- NVLink Multi-Node partition management and alignment with other fabrics — planned for Phase 2+.
- High-performance east-west storage access (GPU-to-storage over east-west paths).
- Cross-tenant east-west connectivity (explicitly forbidden).
- North-south connectivity enhancements (covered by base unified networking in EP #50).
- DPU/HBN Virtual Function assignment and software-based host segmentation.
- Layer-4 load balancing for tenant services.

## Future Phases / Roadmap (for awareness)

Phase 2+ will expand support to InfiniBand (PKey + UFM) and NVLink Multi-Node partitions, along with tighter alignment across all three fabrics and high-performance east-west storage access patterns.

## End-to-End Tenant Onboarding Flow

1. Cloud Infrastructure Admin configures a NetworkClass with east-west capabilities and defaults (node groups, port-to-fabric mappings, east-west connectivity profiles).
2. Cloud Infrastructure Admin creates a tenant with storage and networking requirements.
3. System automatically provisions north-south and east-west isolation domains via the fabric manager, wiring the configured ports into the tenant's east-west domain.
4. Tenant User deploys a distributed workload; compute instances communicate over the east-west fabric without additional network configuration.
5. Cross-tenant traffic is blocked at the fabric level.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to integrate OSAC with the Netris Controller so that tenant network isolation is automatically enforced across Ethernet fabrics without manual switch configuration.

- As a Cloud Infrastructure Admin, I want to configure NetworkClasses with east-west capabilities and defaults (node groups, port-to-fabric mappings, connectivity profiles) so that tenant onboarding is fully automated and consistent.

- As a Cloud Infrastructure Admin, I want tenant onboarding to automatically provision both north-south and east-west isolation domains so that new AI tenants get full connectivity without manual fabric configuration.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want visibility into tenant fabric allocation (isolation domains, network segments, port assignments) so that I can audit isolation boundaries and troubleshoot connectivity issues.

### Tenant Admin

- As a Tenant Admin, I want confidence that my tenant's east-west network isolation is enforced at the fabric level so that other tenants cannot access my data or GPU traffic.

- As a Tenant Admin, I want to define SecurityGroup rules that control which resources can communicate east-west within my tenant's VirtualNetworks, and have those rules enforced as fabric-level ACLs.

### Tenant User

- As a Tenant User, I want my provisioned compute instances to automatically connect to the correct VNets for east-west communication so that distributed workloads can communicate via RDMA without additional network configuration.

- As a Tenant User, I want my Kubernetes clusters to have east-west connectivity within my VPC boundary. (Note: namespace-level network isolation within clusters is provided by the k8s networking layer — see EP #107.)

## Acceptance Criteria

**Tenant Onboarding**
- [ ] Creating a tenant on an east-west capable NetworkClass provisions both NS and EW isolation domains automatically
- [ ] Tenant creation with east-west connectivity completes end-to-end through the fabric manager
- [ ] East-west capable NetworkClass defines which Server Cluster Template and fabric defaults to use for tenant onboarding
- [ ] Server-to-tenant assignments are activated on the fabric when the tenant is created

**Tenant Isolation**
- [ ] Hosts in different tenants cannot exchange traffic on the east-west fabric
- [ ] Hosts in the same tenant and same subnet have L2 connectivity on the EW fabric
- [ ] Hosts in the same tenant but different subnets route at L3 within the tenant's isolation domain
- [ ] SecurityGroup rules translate to fabric-level ACLs, and traffic denied by those rules is dropped on the east-west fabric

**NetworkClass East-West Configuration**
- [ ] Platform admin can configure a NetworkClass with east-west capabilities, node groups, and fabric bindings
- [ ] Configuration changes (add/remove nodes) are reflected in the fabric manager

**East-West Connectivity**
- [ ] Compute instances in the same tenant can communicate over the east-west fabric without additional network configuration
- [ ] RDMA over RoCE workloads function correctly over the Ethernet east-west path

## Assumptions

- Target deployments use Netris (or equivalent) as the Ethernet fabric manager.
- The unified networking model from EP #50 is the base layer.
- Per-service networking extensions (EP #107 for CaaS, others planned) will be merged before or in parallel with this work.
- The existing NetworkClass and VirtualNetwork model can be extended to express east-west capabilities and defaults.

## Dependencies

- **Unified Networking (EP #50):** NetworkClass, VirtualNetwork, Subnet, SecurityGroup primitives must be in place as the foundation layer.
- **Fabric Manager (Netris for Phase 1):** API availability for east-west isolation and multi-tenancy capabilities. The fabric manager capability contract will be defined in the design document.
- **osac-aap Netris collection:** The existing `netris.controller` collection provides the low-level API wrappers that east-west AAP roles build on.

## Risks

### Multi-fabric coordination complexity

Multi-fabric coordination (Ethernet + InfiniBand + NVLink) introduces significant integration complexity. Mitigated by the phased approach: Phase 1 delivers Ethernet-only east-west, deferring InfiniBand and NVLink to Phase 2+ after patterns are established.

**Owner:** Vladik Romanovsky

### Netris Controller dependency

The solution depends on Netris for Ethernet fabric management. API changes, availability issues, or missing multi-tenancy features in Netris could block progress. Mitigated by clear abstraction boundaries between OSAC and the fabric manager, and by designing the integration to be replaceable.

**Owner:** Vladik Romanovsky

### Testing without physical hardware

East-west validation requires multi-switch fabric topology. Mitigated by using the netris-lab simulated environment (Cumulus Linux VMs) which responds to the Netris API identically to physical switches. The simulation validates control-plane behavior: API provisioning workflows, VPC/VNet creation, tenant isolation at the switch level, and Server Cluster lifecycle. Data-plane validation (RDMA over RoCE performance, lossless transport, latency) requires real hardware and is deferred to production qualification.

**Owner:** Vladik Romanovsky
