# Multi-Fabric East-West Networking

| Field       | Value   |
|-------------|---------|
| Author(s)   | Vladik Romanovsky |
| Jira        | [OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382) |
| Date        | 2026-07-14 |

## Problem Statement

High-performance workloads — AI training and inference, storage clusters, HPC — running in shared, multi-tenant sovereign clouds require high-bandwidth, low-latency east-west connectivity between servers. Distributed AI workloads (training and inference) drive massive east-west traffic through collective operations (RDMA over InfiniBand/RoCE), and storage replication and other scale-out workloads have similar requirements. At the same time, hard tenant isolation must be enforced across all fabric types to prevent data leakage.

Today, provisioning east-west connectivity across heterogeneous fabrics (Ethernet/Spectrum-X, InfiniBand, NVLink) requires manual, error-prone coordination. This results in slow tenant onboarding, high operational overhead, risk of misaligned isolation boundaries across fabrics, and inability to offer predictable high-performance east-west out of the box.

OSAC's unified networking model (EP #50) provides north-south connectivity and general workload support. Per-service networking extensions (CaaS in EP #107, with VMaaS and BMaaS planned) build on this foundation. However, none of these address automated east-west provisioning or unified multi-fabric tenant isolation.

## In Scope (Phase 1)

- Declarative east-west connectivity on Ethernet-based fabrics.
- Automated multi-tenant isolation on east-west paths, enforced at the fabric level.
- Ability to create east-west isolation domains for a group of servers — as part of tenant onboarding, as an explicit admin operation, or when resizing an existing deployment.
- Visibility into tenant isolation boundaries for auditing and troubleshooting.
- Integration with the unified networking primitives (EP #50) and compatible with per-service extensions (EP #107).

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

## End-to-End Flow

East-west isolation domains can be provisioned in multiple ways:

1. **During tenant onboarding** — when a new tenant requests high-performance connectivity, the system creates an east-west isolation domain alongside the north-south network as a single operation.
2. **As an explicit admin operation** — a Cloud Infrastructure Admin creates an isolation domain for a specific set of servers or node groups, independent of tenant creation.
3. **When resizing** — servers are added to or removed from an existing isolation domain without recreating the tenant or the domain.

Regardless of how the domain is created:
- The fabric manager provisions per-tenant isolation (separate routing domains, no cross-tenant traffic).
- Compute instances within the domain communicate over the east-west fabric without additional network configuration.
- Cross-tenant traffic is blocked at the fabric level.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to integrate OSAC with a fabric manager so that tenant network isolation is automatically enforced across Ethernet fabrics without manual fabric configuration.

- As a Cloud Infrastructure Admin, I want to create east-west isolation domains for a group of servers so that tenants get high-performance, isolated connectivity for their workloads.

- As a Cloud Infrastructure Admin, I want to add or remove servers from an existing east-west isolation domain so that I can resize tenant deployments without recreating the isolation domain.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want visibility into tenant fabric allocation (isolation domains, network segments, port assignments) so that I can audit isolation boundaries and troubleshoot connectivity issues.

### Tenant Admin

- As a Tenant Admin, I want confidence that my tenant's east-west network isolation is enforced at the fabric level so that other tenants cannot access my data or traffic.

- As a Tenant Admin, I want to define SecurityGroup rules that control which resources can communicate east-west within my tenant's networks, and have those rules enforced as fabric-level ACLs.

### Tenant User

- As a Tenant User, I want my provisioned compute instances to connect to the correct east-west network so that distributed workloads can communicate without additional network configuration.

- As a Tenant User, I want my Kubernetes clusters to have east-west connectivity within my isolation boundary. (Note: namespace-level network isolation within clusters is provided by the k8s networking layer — see EP #107.)

## Acceptance Criteria

**East-West Isolation Domain Lifecycle**
- [ ] An east-west isolation domain can be created for a specified set of servers
- [ ] Each isolation domain belongs to exactly one tenant; cross-tenant membership is rejected
- [ ] An isolation domain can be created as part of tenant onboarding or as a separate operation
- [ ] Servers can be added to or removed from an existing isolation domain
- [ ] An isolation domain can be deleted, releasing the server assignments

**Visibility**
- [ ] Cloud Provider Admin can inspect isolation domain ownership, server membership, and network segment assignments for auditing and troubleshooting

**Tenant Isolation**
- [ ] Hosts in different isolation domains cannot exchange traffic on the east-west fabric
- [ ] Hosts in the same isolation domain and same subnet have L2 connectivity on the east-west fabric
- [ ] Hosts in the same isolation domain but different subnets route at L3 within the domain
- [ ] SecurityGroup rules translate to fabric-level ACLs, and traffic denied by those rules is dropped on the east-west fabric

**East-West Connectivity**
- [ ] Bare metal instances and VMs in the same isolation domain can communicate over the east-west fabric without additional network configuration

## Assumptions

- Target deployments use a fabric manager capable of east-west tenant isolation on Ethernet fabrics.
- Servers participating in the east-west fabric have dedicated NICs for east-west traffic, separate from their north-south and management interfaces.
- The unified networking model from EP #50 is the base layer.
- Per-service networking extensions (EP #107 for CaaS, others planned) will be merged before or in parallel with this work.

## Dependencies

- **Unified Networking (EP #50):** Networking primitives must be in place as the foundation layer.
- **Fabric Manager:** API availability for east-west isolation and multi-tenancy capabilities. The fabric manager capability contract will be defined in the design document.

## Risks

### Multi-fabric coordination complexity

Multi-fabric coordination (Ethernet + InfiniBand + NVLink) introduces significant integration complexity. Mitigated by the phased approach: Phase 1 delivers Ethernet-only east-west, deferring InfiniBand and NVLink to Phase 2+ after patterns are established.

**Owner:** Vladik Romanovsky

### Fabric manager dependency

The solution depends on a fabric manager for east-west isolation. API changes, availability issues, or missing multi-tenancy features could block progress. Mitigated by clear abstraction boundaries between OSAC and the fabric manager, and by designing the integration to be replaceable.

**Owner:** Vladik Romanovsky

### Testing without physical hardware

East-west validation requires multi-switch fabric topology. Mitigated by using a simulated environment that responds to the fabric manager API identically to physical switches. The simulation validates control-plane behavior: provisioning workflows, isolation domain creation, and tenant isolation at the switch level. Data-plane validation (RDMA over RoCE performance, lossless transport, latency) requires real hardware and is deferred to production qualification.

**Owner:** Vladik Romanovsky
