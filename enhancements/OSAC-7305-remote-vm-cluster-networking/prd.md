# VMaaS Networking on a Dedicated VM Workload Cluster

| Field       | Value   |
|-------------|---------|
| Author(s)   | Yoni Bettan (yonibettan@gmail.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-7305 |
| Date        | 2026-11-09 |

This PRD is tracked by OSAC-7307 and extends the
[VMaaS Networking PRD](/enhancements/OSAC-1435-vmaas-networking/prd.md), which
defines how a VM is attached to one tenant Subnet and SecurityGroup set, reports
its address, and reaches the outside world. That PRD inherits the
[Unified Networking deployment and hub support
boundaries](/enhancements/OSAC-1433-unified-networking/prd.md); the hub boundary
excludes VMs outside the hub, and this document is the increment that lifts that
exclusion for VM hosting.

## Problem Statement

OSAC today runs virtual machines and their tenant networking only on the
management cluster. A deployment that keeps management on one cluster and hosts
VMs on a dedicated workload cluster is not a supported or documented capability,
and the partial split-cluster plumbing that exists is not a usable VMaaS
networking story. Providers who need to separate VM hosting from the management
cluster therefore cannot offer VMaaS on that topology, and tenants remain
dependent on hub-local placement. Leaving this unaddressed keeps dedicated
workload-cluster deployments out of the VMaaS support boundary.

## In Scope

- A deployment-wide placement choice with exactly two supported outcomes: all
  VMs run on the management cluster, or all VMs run on one dedicated workload
  cluster. [Clarify: R1.Q2]
- Full VM lifecycle on the workload cluster at parity with the management
  cluster: creation from a catalog item or template, instance type, disk image,
  boot and additional disks with storage tiers, SSH key, user data, power state,
  restart, console access, deletion, and volume metering. [Clarify: R2.Q1]
- Tenant networking on the workload cluster: a VM attaches to one tenant Subnet
  and its SecurityGroups, either selected explicitly or resolved from tenant
  defaults, and receives its tenant IPv4 address with a network-ready state
  before it is reported ready. [Clarify: R1.Q3]
- External access for VMs on the workload cluster with the same behavior as on
  the management cluster, including pool-allocated ExternalIPs, attachments, and
  outbound translation. [Clarify: R2.Q3]
- Tenant isolation on the workload cluster, including the same visibility,
  access, and dependency rules that apply on the management cluster.
- A CI-only configuration where provider networking is disabled: VM
  provisioning still succeeds while networking steps are skipped, matching
  today's management-cluster behavior. [Clarify: R1.Q4]
- Provider-side networking setup for a workload cluster is performed once at
  deployment time: fabric and address-pool configuration is deployment-scoped
  and driven from the management cluster, not repeated per VM or per tenant.
  [Clarify: R2.Q2]
- Existing management-cluster deployments continue to behave exactly as before.

## Out of Scope

- General workload-cluster management itself, including provisioning,
  lifecycle, and credential handling of that cluster; this work consumes that
  foundation. [Jira: OSAC-7305]
- Choosing a cluster per VM, per tenant, or per project, and deployments that
  mix hub-hosted and workload-cluster VMs. [Clarify: R1.Q2]
- More than one VM-hosting cluster per deployment, and any form of cross-cluster
  network mobility or per-cluster duplication of tenant networking resources.
  [Clarify: R1.Q3]
- Exposing placement in the API, CLI, or console, and any other UI or UX change.
  [Clarify: R2.Q4]
- Networking for hosted control plane clusters and for MaaS gateway clusters.
  [Jira: OSAC-7305]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to choose once whether a deployment hosts
  VMs on the management cluster or on a dedicated workload cluster, so that I
  can separate VM hosting from the management cluster without offering tenants
  a placement choice.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want the workload cluster's networking
  prerequisites to be configured once for the deployment, so that a dedicated
  VM cluster can be operated and validated without per-VM setup.
- As a Cloud Infrastructure Admin, I want VM provisioning on a workload cluster
  to fail with a diagnostic that identifies the unmet prerequisite, so that I
  can tell a cluster or networking problem from a tenant request problem.

### Tenant Admin

- As a Tenant Admin, I want my tenant's VirtualNetworks, Subnets,
  SecurityGroups, and default networking to keep working with the same
  isolation on a workload cluster, so that my users' VMs stay on their own
  networks without depending on management-cluster placement.

### Tenant User

- As a Tenant User, I want to create a VM on the deployment's VM cluster with my
  requested Subnet and SecurityGroups, or with my tenant defaults, and see its
  address and network readiness, so that I can run workloads the same way I do
  today.
- As a Tenant User, I want console access, power state changes, restart, and
  deletion to work for my VM on the workload cluster, so that I can operate it
  through its lifecycle.
- As a Tenant User, I want to expose my VM through a pool-allocated external
  address, so that clients outside the tenant network can reach it.

## Assumptions

- The workload-cluster foundation provides the cluster, its credentials, and
  the access path that VM provisioning and networking use; this PRD does not
  define that foundation.
- Users run this capability with provider networking enabled. The
  networking-disabled configuration exists for CI and is not a tenant-facing
  deployment mode.
- The current management-cluster capability set is the parity target and does
  not change while this capability is delivered.
- A workload cluster can reach the external address pools used for external
  access, because that configuration is driven from the management cluster.

## Dependencies

- **VMaaS networking baseline (OSAC-1435):** provides the attachment model,
  address reporting, and external-access behavior this capability extends. It
  blocks this work and must land first.
- **Workload-cluster foundation:** provides cluster provisioning, credentials,
  and remote access. This feature consumes it and does not deliver it.
- **Fabric manager and external address pools:** must be usable from the
  management cluster against the workload cluster, including pool capacity for
  external access.
- **Design and delivery obligations:** the design EP for this Feature must define
  cluster targeting and resource placement; delivery must include automated
  tests that distinguish management-cluster from workload-cluster placement and
  deployment documentation covering topology, prerequisites, and limitations.
  These are ordering constraints for the work, not acceptance criteria for this
  document. [Clarify: R2.Q5]
- **CI-only networking-disabled path:** depends on the remote-cluster placement
  defect tracked in OSAC-7297 being resolved before that path can be exercised
  in CI.

---

## Provenance

Committed: commit @ prd 0.11.5 - 70405a6, workspace prd/OSAC-7307 @ ffd5b2d

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"ffd5b2d","source_repo_branch":"prd/OSAC-7307","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
