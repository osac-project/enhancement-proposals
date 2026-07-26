# Metering and Usage Tracking — Part 2a: BMaaS

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506) |
| Date        | 2026-07-14           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering that runs for the duration a resource exists (creation to deletion), regardless of whether the resource is actively in use. Reflects the provider's physical capacity cost. |
| **Host type** | A provider-defined bare metal hardware configuration used as the primary pricing dimension for BMaaS. Analogous to instance type for VMaaS. |

## 1. Problem Statement

OSAC provisions bare metal hosts but has no mechanism to track their consumption over time. The first metering PRD ([Part 1](/enhancements/metering-and-usage-tracking/prd.md)) established metering for VMaaS, CaaS, and MaaS — all consumption-based meters where metering runs only while the resource is actively serving workloads. BMaaS is fundamentally different: bare metal hosts consume provider capacity from the moment they are provisioned until they are deleted, regardless of whether the tenant is actively using them. A bare metal host is physically reserved and cannot be reassigned — the provider incurs rack space, power, and network port costs whether the host is powered on or off.

Without metering for bare metal hosts, Cloud Provider Admins have no usage data to account for the hardware capacity tenants hold, and Tenant Admins have no visibility into the cost of their bare metal footprint across projects and host types.

## 2. In Scope

- BMaaS allocation metering — metering for bare metal hosts from provisioning start to deletion, regardless of power state (RUNNING, STOPPED, STARTING, STOPPING)
- BMaaS consumption metering — optional meter for powered-on time (RUNNING state only), enabling differentiated pricing between active and stopped hosts
- Parent-child attribution — extending [Part 1](/enhancements/metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that storage volumes and public IPs attached to a bare metal host can be queried as a unified usage view

## 3. Out of Scope

- Storage metering (block, file, object storage) — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Networking resource metering (VirtualNetworks, Subnets, PublicIPs, etc.) — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering (ingress/egress traffic) — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- VMaaS, CaaS, and MaaS metering — covered in [Part 1](/enhancements/metering-and-usage-tracking/prd.md)
- Workload-level metering inside bare metal hosts

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view aggregated bare metal host usage across all tenants for a given time period, broken down by tenant, host type, and catalog item (per Part 1 CAP-17), so that I can account for the physical hardware each tenant holds.
- As a Cloud Provider Admin, I want bare metal hosts to be metered from provisioning start through deletion regardless of power state, so that I can recover the cost of physically reserved hardware even when the tenant has powered it off.
- As a Cloud Provider Admin, I want to see both allocation and consumption meters for bare metal hosts, so that I can offer discounted pricing for stopped hosts while still recovering the baseline reservation cost. A bare metal host has a fixed cost to the provider (rack space, power port, network cable) whether powered on or off — the allocation meter covers this. When powered on, it additionally consumes electricity, cooling, and CPU cycles — the consumption meter covers this. For example, a provider could charge $0.005/s for allocation (always) and $0.001/s for consumption (RUNNING only): a stopped host costs $0.005/s, a running host costs $0.006/s. Without the dual model, the provider either charges full price for stopped hosts or absorbs the reservation cost of idle hardware.

### Cloud Infrastructure Admin

- Not directly affected by this feature. BMaaS metering uses host types already configured via OSAC-1201 (BareMetalInstanceType EP) — no separate registration step in the metering system is required.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's bare metal host usage broken down by project and host type, so that I can attribute hardware costs to the teams that reserved the machines.
- As a Tenant Admin, I want to see the total usage footprint of a bare metal host including its attached storage volumes and public IPs, so that I can understand the full resource consumption of each machine without querying multiple reports.

### Tenant User

- Not directly affected by this feature. Bare metal hosts are typically provisioned and managed by Tenant Admins; Tenant Users interact with the workloads running on them.

## 5. Capabilities

### 5.1 BMaaS Allocation Metering

- **CAP-1:** Bare metal hosts are metered using allocation-based metering from provisioning start to deletion, regardless of power state (RUNNING, STOPPED, STARTING, STOPPING). The allocation meter (`host-type-seconds`) reflects the physical reservation cost to the provider.
- **CAP-2:** Providers can optionally enable a consumption meter (`bare-metal-compute-seconds`) that runs only while the host is in RUNNING state, enabling differentiated pricing between active and stopped hosts.
- **CAP-3:** BMaaS usage is queryable by host type, catalog item (per Part 1 CAP-17), tenant, and project. Host type is the primary pricing dimension, analogous to instance type for VMaaS.

### 5.2 Dual Metering Model

- **CAP-4:** Allocation-based and consumption-based meters can coexist for the same resource. A bare metal host has both an allocation meter (host reserved) and an optional consumption meter (host powered on). Usage queries can distinguish between these meter types.

### 5.3 Cross-cutting

- **CAP-5:** BMaaS meters are additive to the Part 1 metering deployment and require no separate infrastructure. All BMaaS meters use the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. This section defines the metering units and formulas for BMaaS, extending the charge calculation model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md).

BMaaS uses two meters because bare metal hosts have a dual cost structure. The **allocation meter** runs continuously because the physical host is reserved for the tenant and cannot be reassigned — the provider incurs rack space, power, and network port costs regardless of power state. The **consumption meter** runs only while the host is powered on, enabling providers who want to incentivize resource release to offer a lower rate for stopped hosts.

| Meter | Scope | Formula | Example (24 hours) |
|-------|-------|---------|-------------------|
| host-type-seconds (allocation) | PROVISIONING to deletion | duration × rate/s | 86400s × $0.005/s = $432.00 |
| bare-metal-compute-seconds (consumption, optional) | RUNNING only | uptime × rate/s | 43200s × $0.001/s = $43.20 |

## 7. Acceptance Criteria

- [ ] A bare metal host generates allocation usage data (host-type-seconds) from provisioning start to deletion, queryable per tenant and host type
- [ ] A bare metal host in STOPPED state continues generating allocation usage data
- [ ] A bare metal host in RUNNING state generates consumption usage data (bare-metal-compute-seconds) when the consumption meter is enabled
- [ ] BMaaS usage can be broken down by host type, catalog item (per Part 1 CAP-17), tenant, and project
- [ ] A bare metal host with attached storage volumes and public IPs can be queried as a unified usage view
- [ ] Allocation-based and consumption-based meters can coexist for the same resource; usage queries can distinguish between meter types
- [ ] BMaaS meters are additive to the Part 1 metering deployment and require no separate infrastructure
- [ ] All Part 1 cross-cutting acceptance criteria (per-second granularity, deduplication, retention, independent deployment) apply to BMaaS meters

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- The BareMetalInstance proto will be extended with `host_type` before BMaaS metering is implemented. The BareMetalInstanceType EP (OSAC-1201) is the expected vehicle for this.
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes — allocation meters use different start/stop state semantics.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/metering-and-usage-tracking/prd.md) is a prerequisite. Part 2a extends but does not replace it.
- **OSAC-1201 (BareMetalInstanceType EP):** Must add `host_type` to the BareMetalInstance proto. Without this, BMaaS metering has no primary pricing dimension.

## 10. Risks

### 10.1 BMaaS pricing dimension not yet in proto

- **Owner:** OSAC platform team
- **Mitigation:** OSAC-1201 (BareMetalInstanceType EP) is the expected vehicle to add `host_type` to the BareMetalInstance proto. Until this lands, BMaaS metering has no primary pricing dimension and cannot be implemented. Track OSAC-1201 as a blocking dependency.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2a meters depend on the metering infrastructure (event pipeline, provider adapters) established by Part 1 (OSAC-985). Part 2a implementation cannot begin until Part 1 infrastructure is deployed. The Part 1 design is complete; implementation has not started.

## 11. Open Questions

### 11.1 Should BMaaS allocation metering include FAILED state?

- **Owner:** OSAC platform team / Providers
- **Impact:** CAP-1. A bare metal host in FAILED state may still be physically reserved — the hardware exists in the rack and cannot be assigned to another tenant until the failed instance is deleted. This argues for continuing allocation metering during FAILED state. However, if the failure is caused by provider infrastructure (e.g., IPMI unreachable, firmware issue), charging the tenant for a host they cannot use raises the same SLA concern as Part 1 D-5 (failed-state metering) for VMs. The design must determine whether FAILED state continues or pauses the allocation meter.

## Related PRDs

This PRD is part of the Metering Part 2 family, which was split from a combined PRD into focused features:

- **Part 2a: BMaaS** — this document (OSAC-2506)
- **Part 2b: Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
