# Metering and Usage Tracking — Part 2: BMaaS, Storage, and Networking

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
| **Storage tier** | A provider-defined storage performance and cost category (e.g., fast, standard, archival). The required pricing dimension for all storage resources. |
| **Network class** | A provider-defined network backend configuration that determines VirtualNetwork behavior and pricing. |
| **Bandwidth metering** | Metering of data transferred (ingress/egress) across tenant network boundaries, measured in GiB. |

## 1. Problem Statement

OSAC provisions bare metal hosts, storage volumes, and networking resources (virtual networks, subnets, public IPs, NAT gateways) but has no mechanism to track their consumption over time. The first metering PRD ([Part 1](/enhancements/metering-and-usage-tracking/prd.md)) established metering for VMaaS, CaaS, and MaaS — all consumption-based meters where billing runs only while the resource is actively serving workloads. BMaaS, storage, and networking are fundamentally different: they consume provider capacity from the moment they are provisioned until they are deleted, regardless of whether the tenant is actively using them. A bare metal host is physically reserved and cannot be reassigned. A storage volume occupies backend disk space whether the parent VM is running or not. A public IP consumes address pool space whether it is attached or not.

Without metering for these resources, Cloud Provider Admins cannot bill tenants for the infrastructure capacity they hold, and Tenant Admins have no visibility into the cost of their networking and storage footprint. This gap grows as OSAC expands its service offerings — every new storage type or networking resource added without metering is revenue the provider cannot recover.

## 2. In Scope

- BMaaS metering — allocation-based metering for bare metal hosts from provisioning to deletion, with an optional consumption meter for powered-on time
- Block storage metering — allocation-based metering for standalone volumes by storage tier and capacity
- File storage metering — allocation-based metering for shared file storage by storage tier and capacity
- Object storage bucket metering — allocation-based metering for reserved bucket capacity (GiB-seconds) and consumption-based metering for API request counts (read and write operations)
- Networking resource metering — allocation-based metering for VirtualNetworks, Subnets, SecurityGroups, PublicIPs, ExternalIPs, NATGateways, and their attachments
- Network bandwidth metering — user-facing requirements for ingress/egress traffic metering per tenant (data source is TBD)
- Parent-child attribution for storage and networking resources attached to VMs and clusters, extending [Part 1](/enhancements/metering-and-usage-tracking/prd.md) CAP-11 and CAP-12
- UI visibility for BMaaS, storage, networking, and object storage usage in the osac-ui console, extending Part 1 cross-cutting acceptance criteria

## 3. Out of Scope

- Costing, billing, quota enforcement, and budget alerts — deferred to a separate PRD
- VMaaS, CaaS, and MaaS metering — covered in [Part 1](/enhancements/metering-and-usage-tracking/prd.md)
- Workload-level metering inside tenant clusters, VMs, or bare metal hosts
- Object storage API-level metering by individual operation type (PUT, GET, LIST, DELETE) — this PRD meters read vs. write request counts in aggregate. The ObjectStorageBucket resource depends on OSAC-2388.
- VM boot disk storage tier attribution — requires `storage_tier_id` on ComputeInstanceDisk, tracked separately
- Provider infrastructure cost tracking (hardware, power, cooling)

## 4. User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to view aggregated bare metal host usage across all tenants for a billing period, broken down by tenant, host type, and catalog item (per Part 1 CAP-17), so that I can generate bills that reflect the physical hardware each tenant holds.
- As a Cloud Provider Admin, I want to view storage usage across all tenants broken down by storage tier (fast, standard, archival) and capacity, so that I can price storage according to the tier's cost to the provider.
- As a Cloud Provider Admin, I want to view object storage usage across all tenants broken down by reserved capacity and API request counts (read/write), so that I can bill tenants for both the storage space they hold and the API activity they generate.
- As a Cloud Provider Admin, I want to view networking resource usage across all tenants broken down by resource type (VirtualNetwork, PublicIP, NATGateway), so that I can bill tenants for the network infrastructure they consume.
- As a Cloud Provider Admin, I want to view network bandwidth usage across all tenants broken down by direction (ingress/egress) and tenant, so that I can apply data transfer pricing.
- As a Cloud Provider Admin, I want bare metal hosts to be metered from provisioning start through deletion regardless of power state, so that I can recover the cost of physically reserved hardware even when the tenant has powered it off.
- As a Cloud Provider Admin, I want to see both allocation and consumption meters for bare metal hosts, so that I can offer discounted pricing for stopped hosts while still recovering the baseline reservation cost.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register storage tiers as metering dimensions, so that each tier (e.g., NVMe SSD, HDD archival) can be priced independently in the provider's rate schedule.
- As a Cloud Infrastructure Admin, I want to configure network classes as metering dimensions for VirtualNetworks, so that different network backends (e.g., high-performance DPDK, standard OVN) can carry different rates.
- As a Cloud Infrastructure Admin, I want to enable bandwidth metering by integrating the networking vendor's traffic data source, so that per-tenant ingress/egress usage appears alongside resource-based meters.
- As a Cloud Infrastructure Admin, I want to add meters for new networking resource types (e.g., LoadBalancer, VPN Gateway) via configuration without redeployment, extending Part 1 CAP-6 to networking resources.

### Tenant Admin

- As a Tenant Admin, I want to view my organization's bare metal host usage broken down by project and host type, so that I can attribute hardware costs to the teams that reserved the machines.
- As a Tenant Admin, I want to view my organization's storage usage broken down by project, storage tier, and volume, so that I can identify which teams consume the most storage capacity and on which tier.
- As a Tenant Admin, I want to view my organization's object storage bucket usage broken down by project, capacity, and API request counts, so that I can attribute object storage costs to the teams that use them.
- As a Tenant Admin, I want to view my organization's networking resource usage broken down by project, including the count and duration of VirtualNetworks, PublicIPs, and NATGateways, so that I can attribute networking costs to the teams that provisioned them.
- As a Tenant Admin, I want to view my organization's network bandwidth usage broken down by project and direction (ingress/egress), so that I can identify projects with high data transfer costs.
- As a Tenant Admin, I want to see the total cost footprint of a bare metal host including its attached storage volumes and public IPs, so that I can understand the full cost of each machine without querying multiple reports.

### Tenant User

- As a Tenant User, I want to view storage usage for the projects I belong to, broken down by volume and storage tier, so that I can track how much storage capacity my workloads consume and on which tier.
- As a Tenant User, I want to view object storage bucket usage for the projects I belong to, broken down by capacity and API request counts, so that I can understand how my applications use object storage.
- As a Tenant User, I want to view networking resource usage for the projects I belong to, including PublicIP allocation duration and NATGateway uptime, so that I can understand the networking costs of my deployments.
- As a Tenant User, I want to view bandwidth usage for the projects I belong to, broken down by ingress and egress, so that I can identify applications generating high data transfer volumes.

## 5. Capabilities

### 5.1 BMaaS Metering

- **CAP-18:** Bare metal hosts are metered using allocation-based metering from provisioning start to deletion, regardless of power state (RUNNING, STOPPED, STARTING, STOPPING). The allocation meter (`host-type-seconds`) reflects the physical reservation cost to the provider.
- **CAP-19:** Providers can optionally enable a consumption meter (`bare-metal-compute-seconds`) that runs only while the host is in RUNNING state, enabling differentiated pricing between active and stopped hosts.
- **CAP-20:** BMaaS usage is queryable by host type, catalog item (per Part 1 CAP-17), tenant, and project. Host type is the primary pricing dimension, analogous to instance type for VMaaS.

### 5.2 Storage Metering

- **CAP-21:** Block storage volumes are metered using allocation-based metering from creation to deletion. The metering unit is GiB-seconds per storage tier.
- **CAP-22:** File storage shares are metered using the same allocation model as block storage — GiB-seconds per storage tier from creation to deletion.
- **CAP-23:** Object storage buckets are metered using a dual model — allocation (reserved capacity as GiB-seconds) and consumption (API request counts for read and write operations).
- **CAP-24:** Storage usage is queryable by storage tier, capacity, tenant, and project. Storage tier is a required pricing dimension as specified by [Part 1](/enhancements/metering-and-usage-tracking/prd.md).
- **CAP-25:** Storage volumes attached to a VM or cluster are attributable to the parent resource, extending Part 1 CAP-11 and CAP-12 so that the full cost of a VM or cluster includes its storage.

### 5.3 Networking Metering

- **CAP-26:** Tenant-facing networking resources (VirtualNetwork, Subnet, SecurityGroup, PublicIP, ExternalIP, NATGateway, and their attachments) are metered on an allocation basis. Usage accrues from the point the resource reaches READY or ALLOCATED state until deletion.
- **CAP-27:** Networking usage is queryable by resource type, network class (for VirtualNetworks), IP family (IPv4/IPv6 for IP resources), region, tenant, and project.
- **CAP-28:** PublicIPs and ExternalIPs are metered regardless of whether they are attached to a resource. An allocated-but-unattached IP still consumes address pool space and is billable.

### 5.4 Bandwidth Metering

- **CAP-29:** Network bandwidth is metered per tenant as GiB transferred, broken down by direction (ingress/egress). The data source for traffic counters is provided by the networking vendor integration.
- **CAP-30:** Bandwidth usage is queryable by tenant, project, direction, and time period.

### 5.5 Cross-cutting

- **CAP-31:** All resources introduced in this PRD are metered using the same model established by Part 1 (CAP-6). No separate metering infrastructure is required — BMaaS, storage, and networking meters are additive to the Part 1 deployment.
- **CAP-32:** Allocation-based and consumption-based meters can coexist for the same resource. A bare metal host has both an allocation meter (host reserved) and an optional consumption meter (host powered on). Usage queries can distinguish between these meter types.
- **CAP-33:** All resources introduced in this PRD support the same per-second granularity, deduplication, and retention requirements as Part 1 (CAP-4, CAP-15, CAP-16).

## 6. Charge Calculation Model

OSAC provides usage data. The provider applies their own price schedule to generate charges. This section defines the metering units and formulas for each resource family, extending the charge calculation model from [Part 1](/enhancements/metering-and-usage-tracking/prd.md).

### BMaaS

BMaaS uses two meters because bare metal hosts have a dual cost structure. The **allocation meter** runs continuously because the physical host is reserved for the tenant and cannot be reassigned — the provider incurs rack space, power, and network port costs regardless of power state. The **consumption meter** runs only while the host is powered on, enabling providers who want to incentivize resource release to offer a lower rate for stopped hosts.

| Meter | Scope | Formula | Example (24 hours) |
|-------|-------|---------|-------------------|
| host-type-seconds (allocation) | PROVISIONING to deletion | duration × rate/s | 86400s × $0.005/s = $432.00 |
| bare-metal-compute-seconds (consumption, optional) | RUNNING only | uptime × rate/s | 43200s × $0.001/s = $43.20 |

### Storage

Storage uses allocation meters because storage capacity is reserved from creation and cannot be shared with other tenants. The storage tier determines the rate — NVMe SSD costs more per GiB than HDD archival. Object storage adds a consumption meter for API request counts alongside the allocation meter for reserved capacity.

| Meter | Formula | Example |
|-------|---------|---------|
| GiB-seconds per tier (block/file allocation) | capacity × duration × rate/GiB-s | 100 GiB × 2592000s × $0.000000015 = $3.89 (30 days, fast tier) |
| GiB-seconds per tier (object storage allocation) | capacity × duration × rate/GiB-s | 500 GiB × 2592000s × $0.000000010 = $12.96 (30 days) |
| API read requests (object storage consumption) | count × rate/request | 10,000,000 × $0.0000004 = $4.00 |
| API write requests (object storage consumption) | count × rate/request | 1,000,000 × $0.000005 = $5.00 |

### Networking

Each networking resource type has a flat allocation meter. Resource type and network class (for VirtualNetworks) are the pricing dimensions.

| Resource | Meter | Formula | Example (30 days) |
|----------|-------|---------|-------------------|
| VirtualNetwork | resource-seconds | duration × rate/s | 2592000 × $0.000005 = $12.96 |
| Subnet | resource-seconds | duration × rate/s | 2592000 × $0.000001 = $2.59 |
| PublicIP (IPv4) | resource-seconds | duration × rate/s | 2592000 × $0.000001 = $2.59 |
| NATGateway | resource-seconds | duration × rate/s | 2592000 × $0.00001 = $25.92 |
| SecurityGroup | resource-seconds | duration × rate/s | 2592000 × $0.0000001 = $0.26 |

### Bandwidth

Bandwidth is a consumption meter. Unlike the resource meters above, it is driven by traffic volume rather than time.

| Meter | Formula | Example (1 TiB egress) |
|-------|---------|----------------------|
| egress GiB | volume × rate/GiB | 1024 × $0.05/GiB = $51.20 |
| ingress GiB | volume × rate/GiB | 1024 × $0.01/GiB = $10.24 |

## 7. Acceptance Criteria

### BMaaS

- [ ] A bare metal host generates allocation usage data (host-type-seconds) from provisioning start to deletion, queryable per tenant and host type
- [ ] A bare metal host in STOPPED state continues generating allocation usage data
- [ ] A bare metal host in RUNNING state generates consumption usage data (bare-metal-compute-seconds) when the consumption meter is enabled
- [ ] BMaaS usage can be broken down by host type, catalog item (per Part 1 CAP-17), tenant, and project
- [ ] A bare metal host with attached storage volumes and public IPs can be queried as a unified cost view

### Storage

- [ ] A block storage volume generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] A file storage share generates usage data (GiB-seconds) from creation to deletion, queryable per tenant, storage tier, and capacity
- [ ] An object storage bucket generates capacity usage data (GiB-seconds) from creation to deletion, queryable per tenant and storage tier
- [ ] An object storage bucket generates API request count usage data, broken down by read and write operations
- [ ] Storage usage can be broken down by storage tier, tenant, project, and individual volume
- [ ] A storage volume attached to a stopped VM continues generating usage data (extending Part 1 CAP-11)
- [ ] A storage volume attached to a VM or cluster can be attributed to the parent resource in a unified cost view

### Networking

- [ ] Each tenant-facing networking resource (VirtualNetwork, Subnet, SecurityGroup, PublicIP, ExternalIP, NATGateway) generates allocation usage data from READY/ALLOCATED state to deletion
- [ ] An allocated-but-unattached PublicIP generates usage data
- [ ] Networking usage can be broken down by resource type, network class, IP family, region, tenant, and project
- [ ] PublicIPs and Subnets attached to a VM can be attributed to the parent resource in a unified cost view

### Bandwidth

- [ ] Bandwidth usage is recorded per tenant as GiB transferred, broken down by direction (ingress/egress)
- [ ] Bandwidth usage can be broken down by tenant, project, direction, and time period

### Cross-cutting

- [ ] BMaaS, storage, and networking meters are additive to the Part 1 metering deployment and require no separate infrastructure
- [ ] A Tenant Admin can view BMaaS, storage, networking, and object storage usage for their organization in the osac-ui console, broken down by project
- [ ] A Tenant User can view storage, object storage, and networking usage for the projects they belong to in the osac-ui console
- [ ] A Cloud Provider Admin can view BMaaS, storage, networking, and object storage usage across all tenants in the osac-ui console
- [ ] All Part 1 cross-cutting acceptance criteria (per-second granularity, deduplication, retention, independent deployment) apply to Part 2 meters

## 8. Assumptions

- Part 1 metering infrastructure is deployed and operational.
- The BareMetalInstance proto will be extended with `host_type` before BMaaS metering is implemented. The BareMetalInstanceType EP (OSAC-1201) is the expected vehicle for this.
- Tenant-facing storage APIs (Volume, FileShare) will be implemented before storage metering. Object storage metering depends on OSAC-2388 (Object Storage API).
- Allocation-based metering is supported by the Part 1 metering infrastructure without architectural changes — allocation meters use different start/stop state semantics.
- Network bandwidth data will be provided by the networking vendor (e.g., Netris, OVN-Kubernetes) via an integration that provides traffic counters to the metering system.

## 9. Dependencies

- **Part 1 metering infrastructure:** The metering infrastructure established by [Part 1](/enhancements/metering-and-usage-tracking/prd.md) is a prerequisite. Part 2 extends but does not replace it.
- **OSAC-984 (Storage Volume API):** Tenant-facing block storage Volume resource must exist in the fulfillment-service proto before storage metering can be implemented.
- **OSAC-2387 (File Storage API):** FileShare resource must exist in the fulfillment-service proto before file storage metering can be implemented.
- **OSAC-2388 (Object Storage API):** ObjectStorageBucket resource must exist in the fulfillment-service proto before object storage metering can be implemented.
- **OSAC-1201 (BareMetalInstanceType EP):** Must add `host_type` to the BareMetalInstance proto. Without this, BMaaS metering has no primary pricing dimension.
- **Networking vendor integration:** Bandwidth metering depends on a data source for per-tenant traffic counters. The specific vendor API and integration mechanism will be determined during design.

## 10. Open Questions

### 10.1 Network bandwidth data source

- **Owner:** OSAC platform team / Networking team
- **Impact:** CAP-29, CAP-30. Carried forward from Part 1. The networking vendor (Netris, OVN-Kubernetes, or AAP) must provide per-tenant ingress/egress traffic counters. The choice of data source determines how traffic data reaches the metering system. This must be resolved during design.

### 10.2 Object storage API metering granularity

- **Owner:** OSAC platform team
- **Impact:** CAP-23. Should object storage metering distinguish between different API operation types (PUT/GET/LIST/DELETE) with separate meters, or aggregate all operations into read vs. write categories? This PRD aggregates into read vs. write. Fine-grained per-operation metering would increase dimensionality but give providers more pricing flexibility.

### 10.3 Should unattached PublicIPs be billed at a different rate than attached ones?

- **Owner:** OSAC platform team / Providers
- **Impact:** CAP-28. This PRD requires that unattached IPs are metered. Whether the provider charges a premium for unattached IPs (to incentivize release, as AWS does with Elastic IPs) is a pricing policy decision. Usage data must include `attached` as a queryable dimension so that providers can apply differentiated rates if desired.

### 10.4 Should BMaaS allocation metering include FAILED state?

- **Owner:** OSAC platform team / Providers
- **Impact:** CAP-18. A bare metal host in FAILED state may still be physically reserved — the hardware exists in the rack and cannot be assigned to another tenant until the failed instance is deleted. This argues for continuing allocation metering during FAILED state. However, if the failure is caused by provider infrastructure (e.g., IPMI unreachable, firmware issue), charging the tenant for a host they cannot use raises the same SLA concern as Part 1 open question 9.6 for VMs. The design must determine whether FAILED state continues or pauses the allocation meter.

### 10.5 Should VirtualNetwork metering start at PENDING or READY?

- **Owner:** OSAC platform team
- **Impact:** CAP-26. The current model starts metering at READY/ALLOCATED because that is when the resource is usable by the tenant. However, PENDING resources may already consume backend infrastructure (network configuration, VLAN allocation). Starting at PENDING aligns with the BMaaS allocation model (metering from provisioning start). Starting at READY aligns with what the tenant can observe and use. This applies to all networking resources with a PENDING-to-READY transition.
