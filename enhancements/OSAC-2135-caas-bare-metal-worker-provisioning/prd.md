# CaaS Bare-Metal Worker Node Provisioning

| Field       | Value |
|-------------|-------|
| Author(s)   | Avishay Traeger |
| Jira        | [OSAC-2135](https://redhat.atlassian.net/browse/OSAC-2135) |
| Date        | 2026-08-04 |

## Problem Statement

CaaS requires bare-metal compute to back OpenShift cluster worker nodes. Today, a cron job maintains a static pool of pre-booted hosts running the Assisted Installer ISO. This approach wastes resources on idle hosts, is difficult to size correctly, and requires Cloud Infrastructure Admins to manage cluster-specific agent infrastructure alongside BMaaS. Without on-demand provisioning, OSAC incurs high operational costs from underutilized hardware and risks slow or failing cluster scale-up when the pool is exhausted.

## In Scope

- On-demand provisioning of bare-metal worker nodes when a tenant orders a cluster specifying bare-metal resource classes.
- Tenant experience remains unchanged — no bare-metal infrastructure details (hosts, images, or installation agents) are visible to tenants.
- CaaS-managed infrastructure resources are hidden from tenant-facing APIs, UIs, and catalogs.
- Cleanup of CaaS-managed BareMetalInstances when a cluster is decommissioned or manually scaled down.

## Out of Scope

- **Day-2 autoscaling:** Automated workload-driven scaling based on resource utilization. Scaling down requires complex orchestration around cluster node draining and is deferred to a future phase.
- **Virtual machine worker nodes:** Provisioning VM-based worker nodes using this pattern (deferred to future VMaaS integration).
- **Admin tuning APIs:** Administrator-facing APIs for adjusting provisioning heuristics or retry thresholds.
- **Boot-over-network optimization:** Network boot acceleration or advanced bare-metal caching strategies `[Jira: OSAC-2134]`.
- **Custom networking configuration:** Direct management of tenant-specific VLANs or advanced network routing by CaaS.
- **Host sanitization:** Physical host cleanup after deprovisioning (disk wipe, network reset) is BMaaS's responsibility.
- **Billing and quota:** Cluster-level metering and quota tracking are covered by a separate CaaS metering feature.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want bare-metal worker nodes to be provisioned automatically when CaaS clusters need them, so that I no longer need to maintain a static pool of pre-booted agents.

### Tenant User

- As a Tenant User, I want to create a ClusterOrder specifying bare-metal resource classes for my worker nodes, so that my cluster is backed by physical hardware without me managing infrastructure directly.

- As a Tenant User, I want my cluster creation and management experience to remain unchanged, so that I am never exposed to underlying bare-metal instances, images, or installation internals.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want CaaS-provisioned bare-metal instances and associated images hidden from tenant-facing views and catalogs, so that tenants cannot accidentally interact with underlying infrastructure nodes.

## Assumptions

- BMaaS can provision bare-metal hosts with the required boot configuration without manual intervention.
- A standard boot image exists that can initialize a host as a cluster worker node when given the appropriate configuration payload.

## Dependencies

- **BareMetalInstanceType definitions `[Jira: OSAC-2675]`:** Resource class specifications must be finalized so that ClusterOrder can reference them.
- **Boot configuration pass-through:** BMaaS must support passing cluster-specific boot configuration to provisioned hosts.
