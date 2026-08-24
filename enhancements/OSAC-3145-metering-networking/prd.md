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

## 1. Problem Statement

OSAC provisions ExternalIPs and NAT Gateways that consume scarce provider infrastructure from allocation until deletion, but has no mechanism to report that consumption to billing. An ExternalIP consumes finite address pool space whether it is attached to a resource or not — the provider's pool is finite and each allocation reduces availability. A NAT Gateway consumes dedicated gateway capacity for as long as it exists. Metering exists to supply billing with usage data for resources that can incur cost — not to enforce quota, and not to inventory every networking object a tenant holds.

VirtualNetworks, Subnets, and SecurityGroups are configuration metadata that will not incur cost — they are free across all surveyed hyperscalers and GPU/AI clouds, none of which meter them on an allocation basis — so metering does not report them.

Without metering for the billable networking resources, Cloud Provider Admins have no usage data to account for the scarce network infrastructure tenants hold, and Tenant Admins have no visibility into their billable networking footprint across projects.

## 2. In Scope

### 2.1 Services

Metered networking resources are service-agnostic — an ExternalIP or NATGateway is metered regardless of which service (VMaaS, CaaS, BMaaS) consumes it.

| Resource | VMaaS | CaaS | BMaaS |
|----------|-------|------|-------|
| NATGateway | Yes | Yes | Yes |
| ExternalIP | Yes | Yes | Yes |

ExternalIP resources support all three services and can be attached to ComputeInstances, Clusters, and BareMetalInstances. Attachment status is tracked as a queryable dimension on the ExternalIP meter, not as a separately metered resource.

VirtualNetwork, Subnet, and SecurityGroup are available on all three services but are not metered — they are configuration metadata that will not incur cost, so metering does not report them.

### 2.2 Capabilities

- Billing-bound reporting — metering reports only networking resources that can incur cost; it is not a quota feed and not a complete inventory of the networking objects a tenant or user holds
- Networking resource allocation metering — metering for ExternalIPs and NATGateways from READY/ALLOCATED state to deletion
- Unattached IP metering — ExternalIPs generate usage data regardless of attachment status, with attachment status as a queryable dimension
- Parent-child attribution — extending [Part 1](/enhancements/metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that ExternalIPs attached to a parent resource can be attributed to it in a unified usage view: ExternalIPs to ComputeInstances, Clusters, and BareMetalInstances

## 3. Out of Scope

- Metering of VirtualNetwork, Subnet, and SecurityGroup — these are configuration metadata that will not incur cost (free across all surveyed hyperscalers and GPU/AI clouds); metering does not report them (per PR #159 review, [comment 5204380439](https://github.com/osac-project/enhancement-proposals/pull/159#issuecomment-5204380439))
- Quota enforcement and a complete inventory of the networking resources a tenant or user holds — these are not purposes of metering
- BMaaS compute metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)); ExternalIPs and NATGateways consumed by BMaaS are in scope here
- Storage metering — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Network bandwidth metering (ingress/egress traffic) — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, rate schedules, invoicing, and budget alerts — deferred to a separate billing PRD; this PRD supplies the usage data that billing consumes
- UI for viewing networking usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside tenant environments

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want networking resource usage data across all tenants to be available broken down by resource type (ExternalIP, NATGateway), so that downstream systems can track the scarce network infrastructure each tenant consumes.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to add meters for new networking resource types that consume scarce infrastructure (e.g., LoadBalancer, VPN Gateway) via configuration without redeployment, extending Part 1 CAP-6 to networking resources.

### Tenant Admin

- As a Tenant Admin, I want my organization's networking resource usage data to be available broken down by project, including the count and duration of ExternalIPs and NATGateways, so that downstream systems can attribute networking consumption to the teams that provisioned them.

### Tenant User

- As a Tenant User, I want networking resource usage data for the projects I belong to — including ExternalIP allocation duration and NATGateway uptime — to be available so that downstream systems can report the networking resource consumption of my deployments.

## 5. Capabilities

### 5.1 Networking Resource Allocation Metering

- **CAP-1:** Billable networking resources (ExternalIP, NATGateway) are metered on an allocation basis. Usage accrues from the point the resource reaches READY or ALLOCATED state until deletion.
- **CAP-2:** Networking usage is queryable by resource type, IP family (IPv4/IPv6 for ExternalIP), region, tenant, and project.

### 5.2 Unattached IP Metering

- **CAP-3:** ExternalIPs are metered regardless of whether they are attached to a resource. An allocated-but-unattached IP consumes address pool space that other tenants cannot use — the provider's pool is finite and each allocation reduces availability. Metering unattached IPs provides visibility into idle address consumption, enabling providers to identify underutilized allocations. The `attached` status is included as a queryable dimension so that downstream systems (e.g., cost management, quota enforcement) can distinguish between active and idle IP usage.

### 5.3 Cross-cutting

- **CAP-4:** Networking meters are additive to the Part 1 metering deployment and require no separate infrastructure. All networking meters use the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Usage Measurement Model

This section defines the metering units and measurement approach for networking resources, extending the usage measurement model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md). Downstream systems (cost management, billing) consume this usage data and apply their own pricing — rate schedules are outside the scope of metering.

Each metered networking resource type has a flat allocation meter. Usage is queryable by resource type, region, tenant, and project; ExternalIPs additionally use IP family and attachment status (see CAP-2 and CAP-3).

| Resource | Meter | Unit | Example (30 days) |
|----------|-------|------|-------------------|
| ExternalIP (IPv4) | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |
| NATGateway | resource-seconds | seconds of allocation | 2,592,000 resource-seconds |

## 7. Acceptance Criteria

- [ ] Each billable networking resource (ExternalIP, NATGateway) generates allocation usage data from READY/ALLOCATED state to deletion
- [ ] An allocated-but-unattached ExternalIP generates usage data
- [ ] VirtualNetwork, Subnet, and SecurityGroup generate no metering usage data
- [ ] Networking usage can be broken down by resource type, region, tenant, and project; ExternalIPs additionally expose IP family and attachment status
- [ ] ExternalIPs attached to a parent resource (ComputeInstances/Clusters/BareMetalInstances) can be attributed to the parent in a unified usage view
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

### 11.1 Should allocation metering start at PENDING or READY?

- **Owner:** OSAC platform team
- **Impact:** CAP-1. The current model starts metering at READY/ALLOCATED because that is when the resource is usable by the tenant. However, a resource may already consume scarce provider capacity while PENDING (e.g., an ExternalIP reserved from the pool before it becomes attachable). Starting at PENDING aligns with the BMaaS allocation model (metering from provisioning start). Starting at READY aligns with what the tenant can observe and use. This applies to all metered networking resources with a PENDING-to-READY transition.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — this document (OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)

---

## Provenance

Authored: respond @ prd 0.6.3 - 6ec8c11, workspace main @ 78853cd
Final: revise @ prd 0.8.0 - 7efcedb, workspace HEAD @ 6e8f396

> Context changed between respond and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"6e8f396","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["respond","respond","respond","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
