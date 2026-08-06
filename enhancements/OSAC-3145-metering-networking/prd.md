# Metering and Usage Tracking — Part 2c: Networking

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145) |
| Date        | 2026-07-26           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering that runs from the point a resource is allocated until deletion, regardless of whether the resource is actively in use. Reflects the provider's physical capacity reservation. |
| **Network class** | A provider-defined network backend configuration that determines VirtualNetwork behavior and metering classification. |

## 1. Problem Statement

OSAC provisions networking resources — virtual networks, subnets, security groups, external IPs, NAT gateways — but has no mechanism to track their consumption over time. These resources consume provider capacity from the moment they are provisioned until deletion, regardless of whether they are actively carrying traffic. An external IP consumes address pool space whether it is attached to a resource or not — the provider's pool is finite and each allocation reduces availability. A VirtualNetwork consumes backend network configuration and VLAN allocation from creation.

Without metering for these resources, Cloud Provider Admins have no usage data to account for the networking infrastructure tenants hold, and Tenant Admins have no visibility into their networking footprint across projects.

## 2. In Scope

### 2.1 Services

Networking resources are service-agnostic — a VirtualNetwork or Subnet is metered regardless of which service consumes it. Attachment resources vary by target type.

| Resource | VMaaS | CaaS | BMaaS |
|----------|-------|------|-------|
| VirtualNetwork | Yes | Yes | Yes |
| Subnet | Yes | Yes | Yes |
| SecurityGroup | Yes | Yes | Yes |
| NATGateway | Yes | Yes | Yes |
| ExternalIP | Yes | Yes | Yes |

ExternalIP resources support all three services and can be attached to ComputeInstances, Clusters, and BareMetalInstances. Attachment status is tracked as a queryable dimension on the ExternalIP meter, not as a separately metered resource.

### 2.2 Capabilities

- Networking resource allocation metering — metering for VirtualNetworks, Subnets, SecurityGroups, ExternalIPs, and NATGateways from READY/ALLOCATED state to deletion
- Unattached IP metering — ExternalIPs generate usage data regardless of attachment status, with attachment status as a queryable dimension
- Parent-child attribution — extending [Part 1](/enhancements/metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that networking resources attached to a parent resource can be attributed to it in a unified usage view: ExternalIPs to ComputeInstances, Clusters, and BareMetalInstances, and Subnets to any resource connected via network attachments

## 3. Out of Scope

- BMaaS compute metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)); networking resources consumed by BMaaS (VirtualNetworks, Subnets, ExternalIPs, etc.) are in scope here
- Storage metering — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Network bandwidth metering (ingress/egress traffic) — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- UI for viewing networking usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want networking resource usage data across all tenants to be available broken down by resource type (VirtualNetwork, ExternalIP, NATGateway), so that downstream systems can track the network infrastructure each tenant consumes.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want VirtualNetwork usage to be automatically grouped by the network classes I have configured in OSAC, so that different network backends (e.g., high-performance DPDK, standard OVN) are tracked as distinct metering categories — without requiring a separate registration step in the metering system.
- As a Cloud Infrastructure Admin, I want to add meters for new networking resource types (e.g., LoadBalancer, VPN Gateway) via configuration without redeployment, extending Part 1 CAP-6 to networking resources.

### Tenant Admin

- As a Tenant Admin, I want my organization's networking resource usage data to be available broken down by project, including the count and duration of VirtualNetworks, ExternalIPs, and NATGateways, so that downstream systems can attribute networking consumption to the teams that provisioned them.

### Tenant User

- As a Tenant User, I want networking resource usage data for the projects I belong to — including ExternalIP allocation duration and NATGateway uptime — to be available so that downstream systems can report the networking resource consumption of my deployments.

## 5. Capabilities

### 5.1 Networking Resource Allocation Metering

- **CAP-1:** Tenant-facing networking resources (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, NATGateway) are metered on an allocation basis. Usage accrues from the point the resource reaches READY or ALLOCATED state until deletion.
- **CAP-2:** Networking usage is queryable by resource type, network class (for VirtualNetworks), IP family (IPv4/IPv6 for IP resources), region, tenant, and project.

### 5.2 Unattached IP Metering

- **CAP-3:** ExternalIPs are metered regardless of whether they are attached to a resource. An allocated-but-unattached IP consumes address pool space that other tenants cannot use — the provider's pool is finite and each allocation reduces availability. Metering unattached IPs provides visibility into idle address consumption, enabling providers to identify underutilized allocations. The `attached` status is included as a queryable dimension so that downstream systems (e.g., cost management, quota enforcement) can distinguish between active and idle IP usage.

### 5.3 Cross-cutting

- **CAP-4:** Networking meters are additive to the Part 1 metering deployment and require no separate infrastructure. All networking meters use the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Usage Measurement Model

This section defines the metering units and measurement approach for networking resources, extending the usage measurement model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md). Downstream systems (cost management, billing) consume this usage data and apply their own pricing — rate schedules are outside the scope of metering.

Each networking resource type has a flat allocation meter. Usage is queryable by resource type, region, tenant, and project; VirtualNetworks additionally use network class; ExternalIPs additionally use IP family and attachment status (see CAP-2 and CAP-3).

| Resource | Meter | Unit | Example (30 days) |
|----------|-------|------|-------------------|
| VirtualNetwork | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |
| Subnet | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |
| ExternalIP (IPv4) | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |
| NATGateway | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |
| SecurityGroup | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |

## 7. Acceptance Criteria

- [ ] Each tenant-facing networking resource (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, NATGateway) generates allocation usage data from READY/ALLOCATED state to deletion
- [ ] An allocated-but-unattached ExternalIP generates usage data
- [ ] Networking usage can be broken down by resource type, region, tenant, and project; VirtualNetworks additionally expose network class; IP resources expose IP family; ExternalIPs expose attachment status
- [ ] Networking resources attached to a parent resource (ExternalIPs to ComputeInstances/Clusters/BareMetalInstances, Subnets via network attachments) can be attributed to the parent in a unified usage view
- [ ] Networking usage data is available after deploying the metering update without provisioning additional infrastructure
- [ ] Networking usage data maintains per-second granularity, deduplication, and retention consistent with Part 1 metering

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes — allocation meters use different start/stop state semantics.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/metering-and-usage-tracking/prd.md) is a prerequisite. Part 2c extends but does not replace it.

## 10. Risks

### 10.1 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2c meters depend on the metering infrastructure (event pipeline, provider adapters) established by Part 1 (OSAC-985). Part 2c implementation cannot begin until Part 1 infrastructure is deployed.

## 11. Open Questions

### 11.1 Should VirtualNetwork metering start at PENDING or READY?

- **Owner:** OSAC platform team
- **Impact:** CAP-1. The current model starts metering at READY/ALLOCATED because that is when the resource is usable by the tenant. However, PENDING resources may already consume backend infrastructure (network configuration, VLAN allocation). Starting at PENDING aligns with the BMaaS allocation model (metering from provisioning start). Starting at READY aligns with what the tenant can observe and use. This applies to all networking resources with a PENDING-to-READY transition.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — this document (OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)

---

## Provenance

Committed: commit @ prd 0.7.1 - b8b3f86, workspace prd/OSAC-3145 @ 2c5bc7d (50 behind origin/main, dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.7.1","ai_workflows":"b8b3f86","source_repo":"2c5bc7d (dirty)","source_repo_branch":"prd/OSAC-3145","commits_behind_main":50,"commits_ahead_main":8,"main_ref":"main","phases":["commit","commit","commit","commit","commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
