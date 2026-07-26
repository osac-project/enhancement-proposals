# Metering and Usage Tracking — Part 2d: Network Bandwidth

| Field       | Value                |
|-------------|----------------------|
| Author(s)   | masayag@redhat.com   |
| Jira        | [OSAC-3149](https://redhat.atlassian.net/browse/OSAC-3149) |
| Date        | 2026-07-26           |

## Glossary

Terms defined in the [Part 1 PRD](/enhancements/metering-and-usage-tracking/prd.md) apply here. Additional terms:

| Term | Definition |
|------|-----------|
| **Bandwidth metering** | Metering of data transferred (ingress/egress) across tenant network boundaries, measured in GiB. |

## 1. Problem Statement

OSAC provisions networking infrastructure for tenants but has no mechanism to track network traffic volumes. Data transfer (ingress and egress) consumes provider bandwidth capacity and generates real infrastructure costs — transit fees, peering costs, upstream bandwidth. Unlike resource-based metering where usage is tied to the existence of a resource, bandwidth is a consumption-based meter driven by traffic volume rather than time.

Without bandwidth metering, Cloud Provider Admins cannot apply data transfer pricing, and Tenant Admins have no visibility into which projects or applications generate the most network traffic. The data source for traffic counters must come from the networking vendor integration (e.g., Netris, OVN-Kubernetes).

## 2. In Scope

- Per-tenant bandwidth metering — ingress/egress GiB transferred, broken down by direction
- Vendor integration requirements — the networking vendor must provide per-tenant traffic counters to the metering system
- Project-level bandwidth breakdown — available when the networking vendor's data source supports project attribution

## 3. Out of Scope

- BMaaS metering — tracked separately ([OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506))
- Storage metering — tracked separately ([OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141))
- Networking resource metering (VirtualNetworks, Subnets, PublicIPs, etc.) — tracked separately ([OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145))
- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- Per-application bandwidth metering inside tenant environments
- Bandwidth shaping or rate limiting

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view network bandwidth usage across all tenants broken down by direction (ingress/egress) and tenant, so that I can apply data transfer pricing.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to enable bandwidth metering by integrating the networking vendor's traffic data source, so that per-tenant ingress/egress usage appears alongside resource-based meters.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's network bandwidth usage broken down by direction (ingress/egress) and, when the vendor data source supports it, by project, so that I can identify sources of high data transfer costs.

### Tenant User

- As a Tenant User, I want to view bandwidth usage broken down by ingress and egress and, when the vendor data source supports project attribution, by project, so that I can identify applications generating high data transfer volumes.

## 5. Capabilities

### 5.1 Bandwidth Metering

- **CAP-1:** Network bandwidth is metered per tenant as GiB transferred, broken down by direction (ingress/egress). The data source for traffic counters is provided by the networking vendor integration.
- **CAP-2:** Bandwidth usage is queryable by tenant, direction, and time period. Project-level bandwidth breakdown is available only if the networking vendor's data source provides project-level attribution; otherwise bandwidth is queryable at the tenant level only.

### 5.2 Cross-cutting

- **CAP-3:** Bandwidth meters are additive to the Part 1 metering deployment and require no separate infrastructure. Bandwidth meters use the same deduplication and retention requirements as Part 1 (CAP-15, CAP-16).

## 6. Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. This section defines the metering units and formulas for bandwidth, extending the charge calculation model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md).

Bandwidth is a consumption meter. Unlike the resource-based allocation meters in sibling PRDs, it is driven by traffic volume rather than time.

| Meter | Formula | Example (1 TiB egress) |
|-------|---------|----------------------|
| egress GiB | volume × rate/GiB | 1024 × $0.05/GiB = $51.20 |
| ingress GiB | volume × rate/GiB | 1024 × $0.01/GiB = $10.24 |

## 7. Acceptance Criteria

- [ ] Bandwidth usage is recorded per tenant as GiB transferred, broken down by direction (ingress/egress)
- [ ] Bandwidth usage can be broken down by tenant, direction, and time period; project-level breakdown is available when the vendor data source supports project attribution
- [ ] Bandwidth meters are additive to the Part 1 metering deployment and require no separate infrastructure
- [ ] All Part 1 cross-cutting acceptance criteria (deduplication, retention, independent deployment) apply to bandwidth meters

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- Network bandwidth data will be provided by the networking vendor (e.g., Netris, OVN-Kubernetes) via an integration that provides traffic counters to the metering system.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/metering-and-usage-tracking/prd.md) is a prerequisite. Part 2d extends but does not replace it.
- **Networking vendor integration:** Bandwidth metering depends on a data source for per-tenant traffic counters. The specific vendor API and integration mechanism will be determined during design.

## 10. Risks

### 10.1 Bandwidth data source unidentified

- **Owner:** OSAC platform team / Networking team
- **Mitigation:** No networking vendor has been selected to provide per-tenant ingress/egress traffic counters. Without a data source, bandwidth metering cannot be implemented. Engage Netris and OVN-Kubernetes teams during design to evaluate options. Bandwidth metering may ship after other Part 2 meters if the vendor integration is not ready.

### 10.2 Part 1 metering infrastructure not yet built

- **Owner:** OSAC platform team
- **Mitigation:** All Part 2d meters depend on the metering infrastructure (event pipeline, provider adapters) established by Part 1 (OSAC-985). Part 2d implementation cannot begin until Part 1 infrastructure is deployed.

## 11. Open Questions

### 11.1 Network bandwidth data source

- **Owner:** OSAC platform team / Networking team
- **Impact:** CAP-1, CAP-2. Carried forward from Part 1. The networking vendor (Netris, OVN-Kubernetes, or AAP) must provide per-tenant ingress/egress traffic counters. The choice of data source determines how traffic data reaches the metering system. This must be resolved during design.

## Related PRDs

This PRD is part of the Metering Part 2 family:

- **Part 2a: BMaaS** — [OSAC-2506](https://redhat.atlassian.net/browse/OSAC-2506)
- **Part 2b: Storage** — [OSAC-3141](https://redhat.atlassian.net/browse/OSAC-3141)
- **Part 2c: Networking** — [OSAC-3145](https://redhat.atlassian.net/browse/OSAC-3145)
- **Part 2d: Network Bandwidth** — this document (OSAC-3149)
