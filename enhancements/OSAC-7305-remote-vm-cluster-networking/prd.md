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
VMs on a dedicated workload cluster is not supported for tenant networking: the
networking path assumes the management cluster, and the partial split-cluster
plumbing that exists does not deliver a usable networking capability. Providers
need the networking path to follow VM hosting because tenant workloads carry the
network load, address consumption, and failure blast radius that they do not
want on the cluster running OSAC's own control plane. Leaving this unaddressed
keeps dedicated workload-cluster deployments outside the VMaaS networking
support boundary.

## In Scope

- A deployment-wide placement choice, made at installation, with exactly two
  supported outcomes: VMs and their tenant networking run on the management
  cluster, or they run on one dedicated workload cluster. Changing the choice on
  an existing installation requires a reinstall, because tenant networking
  objects live on the cluster that was in use.
- When provider networking is enabled, a VM on the workload cluster attaches to
  one tenant Subnet and its SecurityGroups, either selected explicitly or
  resolved from tenant defaults, receives its tenant IPv4 address, and reports
  network readiness before it reports ready.
- External access for VMs on the workload cluster with the same behavior as on
  the management cluster, including pool-allocated ExternalIPs, attachments, and
  outbound translation.
- Tenant isolation on the workload cluster, including the same visibility,
  access, and dependency rules that apply on the management cluster.
- A CI-only configuration where provider networking is disabled: VM provisioning
  still succeeds, networking steps are skipped, and VM readiness does not depend
  on a tenant IPv4 address or provider connectivity, matching today's
  management-cluster behavior.
- The workload cluster's networking prerequisites are configured once for the
  deployment rather than per VM: an EVPN-capable OVN-Kubernetes on that cluster,
  BGP routing and VTEPs on its nodes, fabric AS, VTEP range, and BGP peers agreed
  with the provider, and provider fabric peering with those nodes.
- OSAC's Kubernetes Manager configures tenant networking on the workload
  cluster. The fabric manager keeps its own tasks and stays registered once; it
  is not re-registered or re-pointed per cluster.
- Existing management-cluster deployments continue to behave exactly as before.

## Out of Scope

- General workload-cluster management itself, including provisioning,
  lifecycle, and credential handling of that cluster; this work consumes that
  foundation.
- Choosing a cluster per VM, per tenant, or per project, and deployments that
  mix management-cluster and workload-cluster VMs.
- More than one VM-hosting cluster per deployment, and any form of cross-cluster
  network mobility or per-cluster duplication of tenant networking resources.
- Non-networking VM capabilities on the workload cluster, including storage
  tiers, volume metering, console access, power state, restart, and GPU: this
  work does not change them and does not claim them as a new capability.
- Exposing placement in the API, CLI, or console, and any other UI or UX change.
- Networking for hosted control plane clusters and for MaaS gateway clusters.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to choose once, at installation,
  whether a deployment hosts VMs on the management cluster or on a dedicated
  workload cluster, so that VM hosting can be separated from the management
  cluster without offering tenants a per-VM or per-tenant placement choice.
- As a Cloud Infrastructure Admin, I want the workload cluster's networking
  prerequisites to be configured once for the deployment, so that a dedicated
  VM cluster can be operated and validated without per-VM setup.
- As a Cloud Infrastructure Admin, I want VM provisioning on a workload cluster
  to fail with a diagnostic that identifies the unmet networking prerequisite,
  so that I can tell a cluster or networking problem from a tenant request
  problem.

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
- As a Tenant User, I want to expose my VM through a pool-allocated external
  address, so that clients outside the tenant network can reach it.

## Assumptions

- The workload-cluster foundation provides the cluster, its credentials, and
  the access path that VM provisioning and networking use; this PRD does not
  define that foundation.
- Users run this capability with provider networking enabled. The
  networking-disabled configuration exists for CI and is not a tenant-facing
  deployment mode.
- The provider fabric peers with the workload cluster's nodes as it peers with
  the management cluster's nodes today, so tenant and external addresses on that
  cluster are reachable through the fabric.

## Dependencies

- **VMaaS networking baseline (OSAC-1435):** provides the attachment model,
  address reporting, and external-access behavior this capability extends. It
  blocks this work and must land first.
- **Workload-cluster foundation:** provides cluster provisioning, credentials,
  and remote access. This feature consumes it and does not deliver it.
- **Accepted designs that must be amended for this capability:** the Unified
  Networking hub support boundary, which currently excludes the dedicated-cluster
  option; the network manager contract, where tasks currently reach the hub with
  no cluster identifier and the fabric extends and peers VRFs with hub nodes,
  together with its conformance tests; the CUDN EVPN design, whose hub
  prerequisites this capability changes; and the VMaaS networking design, whose
  non-goals exclude VMs outside the hub.
- **OSAC operator behavior:** the operator currently refuses to run with a
  remote cluster configured while provider networking is enabled. That
  restriction must be lifted as part of this capability.
- **Fabric manager and external address pools:** must reach the workload
  cluster's nodes and provide pool capacity for external access.
- **Design and delivery obligations:** the design EP for this Feature must define
  cluster targeting and resource placement; delivery must include automated
  tests that distinguish management-cluster from workload-cluster placement and
  deployment documentation covering topology, prerequisites, and limitations.
- **CI-only networking-disabled path:** depends on the remote-cluster placement
  defect tracked in OSAC-7297 being resolved before that path can be exercised
  in CI.

---

## Provenance

Committed: commit @ prd 0.11.5 - 70405a6, workspace prd/OSAC-7307 @ 98a2809 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"98a2809 (dirty)","source_repo_branch":"prd/OSAC-7307","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
