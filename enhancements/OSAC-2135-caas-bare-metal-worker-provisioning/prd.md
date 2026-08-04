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
- Tenant-visible ClusterOrder status reflects provisioning progress and reports clear failure conditions when bare-metal hosts cannot be provisioned.
- Tenant experience remains unchanged — no CaaS-managed bare-metal infrastructure details (hosts, images, or installation agents) are visible to tenants. Tenant-owned BareMetalInstance workflows (BMaaS) are unaffected.
- CaaS-managed worker instances and associated images are hidden from tenant-facing APIs, UIs, and catalogs.
- Manual scale-up and scale-down of bare-metal worker nodes (tenant-initiated worker count changes).
- Release of CaaS-managed BareMetalInstances when a cluster is decommissioned or scaled down.
- No CaaS-related UI changes required — tenant console workflows for cluster management and tenant-owned bare-metal instances are unaffected.

## Out of Scope

- **Day-2 autoscaling:** Automated workload-driven scaling based on resource utilization. CaaS does not currently support autoscaling; this is deferred to a future phase.
- **Virtual machine worker nodes:** Provisioning VM-based worker nodes using this pattern (deferred to future VMaaS integration).
- **Admin tuning APIs:** Administrator-facing APIs for adjusting provisioning heuristics or retry thresholds.
- **Boot-over-network optimization:** Network boot acceleration or advanced bare-metal caching strategies `[Jira: OSAC-2134]`.
- **Custom networking configuration:** Direct management of tenant-specific VLANs or advanced network routing by CaaS.
- **Host sanitization:** Physical host cleanup after deprovisioning (disk wipe, network reset) is BMaaS's responsibility. BMaaS must complete sanitization before returning a host to the provisioning pool; a host that fails sanitization must not be made available for reuse.
- **Billing and quota:** Cluster-level metering and quota tracking are covered by a separate CaaS metering feature.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want bare-metal worker nodes to be provisioned automatically when CaaS clusters need them, so that I no longer need to maintain a static pool of pre-booted agents.

- As a Cloud Infrastructure Admin, I want CaaS to automatically handle provisioning retries and release of failed bare-metal resources, so that transient BMaaS failures do not leave orphaned infrastructure.

### Tenant Admin / Tenant User

- As a Tenant User, I want to create a ClusterOrder specifying bare-metal resource classes for my worker nodes, so that my cluster is backed by physical hardware without me managing infrastructure directly.

- As a Tenant User, I want my cluster creation and management experience to remain unchanged, so that I am never exposed to underlying bare-metal instances, images, or installation internals.

- As a Tenant User, I want to scale my cluster's bare-metal worker count up or down, so that I can adjust capacity to match my workload needs.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want CaaS-provisioned bare-metal instances and associated images hidden from tenant-facing views and catalogs, so that tenants cannot accidentally interact with underlying infrastructure nodes.

- As a Cloud Provider Admin, I want to be able to access CaaS-managed BareMetalInstances for debugging (ssh, console, restart), so that I can troubleshoot worker node issues without disrupting the tenant experience.

## Assumptions

- BMaaS can provision bare-metal hosts that join a cluster as worker nodes without manual admin intervention.
- BMaaS can prepare provisioned hosts with the boot configuration needed for a specific cluster.

## Dependencies

- **BareMetalInstanceType definitions `[Jira: OSAC-2675]`:** Resource class specifications must be finalized so that ClusterOrder can reference them.
- **BMaaS host lifecycle API:** BMaaS must support requesting, observing readiness of, and releasing bare-metal hosts so that CaaS can manage the full provisioning lifecycle.
- **Cluster-specific host preparation:** BMaaS must support provisioning hosts preconfigured for a specific cluster, so that CaaS can request worker nodes without separate configuration steps.
- **BMaaS networking for subnet attachment `[Jira: OSAC-1437]`:** BMaaS must support network attachments on BareMetalInstances so that CaaS-managed worker hosts are moved to the cluster's tenant subnet as part of the BMI lifecycle.

---

## Provenance

Authored: respond @ prd 0.6.3 - c045d41, workspace feat/osac-taxonomy-presentation @ d22bfa1
Phases: revise, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.6.3","ai_workflows":"c045d41","source_repo":"d22bfa1","source_repo_branch":"feat/osac-taxonomy-presentation","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","respond","respond"],"authoring_modes":["skill"],"context_changed":false} -->
