# Metering and Usage Tracking — Part 2a: BMaaS

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506) |
| Date        | 2026-07-14           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Allocation metering** | Metering that runs for the duration a resource exists (creation to deletion), regardless of whether the resource is actively in use. Reflects the provider's physical capacity commitment. |
| **Host type** | A provider-defined bare metal hardware configuration used as the primary metering dimension for BMaaS. Analogous to instance type for VMaaS. |

## 1. Problem Statement

OSAC provisions bare metal hosts but has no mechanism to track their consumption over time. The first metering PRD ([Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md)) established metering for VMaaS, CaaS, and MaaS — all consumption-based meters where metering runs only while the resource is actively serving workloads. BMaaS is fundamentally different: bare metal hosts consume provider capacity from the moment they are provisioned until they are deleted, regardless of whether the tenant is actively using them. A bare metal host is physically reserved and cannot be reassigned — the provider commits rack space, a power port, and a network port whether the host is powered on or off.

Without metering for bare metal hosts, Cloud Provider Admins have no usage data to account for the hardware capacity tenants hold, and Tenant Admins have no visibility into the extent of their bare metal footprint across projects and host types.

## 2. In Scope

- BMaaS allocation metering — metering for bare metal hosts from provisioning start to deletion, regardless of power state (RUNNING, STOPPED, STARTING, STOPPING)
- BMaaS consumption metering — optional meter for powered-on time (RUNNING state only), enabling differentiated metering between active and stopped hosts
- Parent-child attribution — extending [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) CAP-11 and CAP-12 so that storage volumes and public IPs attached to a bare metal host can be queried as a unified usage view

## 3. Out of Scope

- Storage metering (block, file, object storage) — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Networking resource metering (VirtualNetworks, Subnets, PublicIPs, etc.) — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Network bandwidth metering (ingress/egress traffic) — tracked separately ([OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- VMaaS, CaaS, and MaaS metering — covered in [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md)
- UI for viewing BMaaS usage — metering data is consumed by the billing system, which provides the user-facing usage views
- Workload-level metering inside bare metal hosts

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view aggregated bare metal host usage across all tenants for a given time period, broken down by tenant, host type, and catalog item (per Part 1 CAP-17), so that I can account for the physical hardware each tenant holds.
- As a Cloud Provider Admin, I want bare metal hosts to be metered from provisioning start through deletion regardless of power state, so that I can track the capacity commitment of physically reserved hardware even when the tenant has powered it off.
- As a Cloud Provider Admin, I want to see both allocation and consumption meters for bare metal hosts, so that I can distinguish between reserved capacity and active usage. A bare metal host occupies physical capacity (rack space, power port, network cable) whether powered on or off — the allocation meter captures this. When powered on, it additionally consumes electricity, cooling, and CPU cycles — the consumption meter captures this. The dual-meter model gives providers two independent usage signals per host, enabling downstream systems to distinguish reserved from active capacity.

### Cloud Infrastructure Admin

- Not directly affected by this feature. BMaaS metering uses host types already configured via OSAC-1201 (BareMetalInstanceType EP) — no separate registration step in the metering system is required.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's bare metal host usage broken down by project and host type, so that I can attribute hardware usage to the teams that reserved the machines.
- As a Tenant Admin, I want to see the total usage footprint of a bare metal host including its attached storage volumes and public IPs, so that I can understand the full resource consumption of each machine without querying multiple reports.

### Tenant User

- Not directly affected by this feature. Bare metal hosts are typically provisioned and managed by Tenant Admins; Tenant Users interact with the workloads running on them.

## 5. Capabilities

### 5.1 BMaaS Allocation Metering

- **CAP-1:** Bare metal hosts are metered using allocation-based metering from provisioning start to deletion, regardless of power state (RUNNING, STOPPED, STARTING, STOPPING). The allocation meter (`host-type-seconds`) reflects the physical capacity reservation by the tenant.
- **CAP-2:** Providers can optionally enable a consumption meter (`bare-metal-compute-seconds`) that runs only while the host is in RUNNING state, enabling differentiated metering between active and stopped hosts.
- **CAP-3:** BMaaS usage is queryable by host type, catalog item (per Part 1 CAP-17), tenant, and project. Host type is the primary metering dimension, analogous to instance type for VMaaS.

### 5.2 Dual Metering Model

- **CAP-4:** Allocation-based and consumption-based meters can coexist for the same resource. A bare metal host has both an allocation meter (host reserved) and an optional consumption meter (host powered on). Usage queries can distinguish between these meter types.

### 5.3 Cross-cutting

- **CAP-5:** BMaaS meters are additive to the Part 1 metering deployment and require no separate infrastructure. All BMaaS meters use the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Usage Calculation Model

OSAC captures usage data. Downstream systems (billing, quota, analytics) consume this data and apply their own logic. This section defines the metering units and accumulation rules for BMaaS, extending the usage calculation model from [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md).

BMaaS uses two meters because bare metal hosts have a dual capacity profile. The **allocation meter** runs continuously because the physical host is reserved for the tenant and cannot be reassigned — it occupies rack space, a power port, and a network port regardless of power state. The **consumption meter** runs only while the host is powered on, capturing active compute usage separately from the baseline reservation.

| Meter | Scope | Unit | Accumulation | Example (24 hours) |
|-------|-------|------|-------------|-------------------|
| host-type-seconds (allocation) | PROVISIONING to deletion | seconds | wall-clock duration the host exists | 86,400s |
| bare-metal-compute-seconds (consumption, optional) | RUNNING only | seconds | wall-clock duration the host is powered on | 43,200s (if running 12 of 24 hours) |

## 7. Acceptance Criteria

- [ ] A bare metal host generates allocation usage data (host-type-seconds) from provisioning start to deletion, queryable per tenant and host type
- [ ] A bare metal host in STOPPED state continues generating allocation usage data
- [ ] A bare metal host in RUNNING state generates consumption usage data (bare-metal-compute-seconds) when the consumption meter is enabled
- [ ] BMaaS usage can be broken down by host type, catalog item (per Part 1 CAP-17), tenant, and project
- [ ] A bare metal host with attached storage volumes and public IPs can be queried as a unified usage view
- [ ] Allocation-based and consumption-based meters can coexist for the same resource; usage queries can distinguish between meter types
- [ ] BMaaS meters are additive to the Part 1 metering deployment and require no separate infrastructure
- [ ] BMaaS meters record usage at per-second granularity — a host existing for 30 seconds appears in usage data
- [ ] Duplicate BMaaS metering events do not cause double-counting
- [ ] BMaaS raw events are retained for at least 7 days; aggregated data is retained for at least 13 months
- [ ] BMaaS metering deployment is independent of existing provisioning workflows

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- The BareMetalInstance proto will be extended with `host_type` before BMaaS metering is implemented. The BareMetalInstanceType EP (OSAC-1201) is the expected vehicle for this.
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes — allocation meters use different start/stop state semantics.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/OSAC-985-metering-and-usage-tracking/prd.md) is a prerequisite. Part 2a extends but does not replace it.
- **OSAC-1201 (BareMetalInstanceType EP):** Must add `host_type` to the BareMetalInstance proto. Without this, BMaaS metering has no primary metering dimension.

## 10. Risks

### 10.1 BMaaS metering dimension not yet in proto

- **Owner:** OSAC platform team
- **Mitigation:** OSAC-1201 (BareMetalInstanceType EP) is the expected vehicle to add `host_type` to the BareMetalInstance proto. Until this lands, BMaaS metering has no primary metering dimension and cannot be implemented. Track OSAC-1201 as a blocking dependency.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2a meters depend on the metering infrastructure (event pipeline, usage store) established by Part 1 (OSAC-985). Part 2a implementation cannot begin until Part 1 infrastructure is deployed. The Part 1 design is complete; implementation has not started.

## 11. Open Questions

### 11.1 Should BMaaS allocation metering include FAILED state?

- **Owner:** OSAC platform team / Providers
- **Impact:** CAP-1. A bare metal host in FAILED state may still be physically reserved — the hardware exists in the rack and cannot be assigned to another tenant until the failed instance is deleted. This argues for continuing allocation metering during FAILED state. However, if the failure is caused by provider infrastructure (e.g., IPMI unreachable, firmware issue), metering a tenant for a host they cannot use raises the same concern as Part 1 D-5 (failed-state metering) for VMs. The design must determine whether FAILED state continues or pauses the allocation meter. Note: the metering decision is independent of any downstream billing policy — metering captures what happened; billing systems decide what to charge for.

## Related PRDs

This PRD is part of the Metering Part 2 family, which was split from a combined PRD into focused features:

- **Part 2a: BMaaS** — this document (OSAC-2506)
- **Part 2b: Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149)
