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
VMs on one or more workload clusters is not supported for tenant networking: the
networking path assumes the management cluster, and the partial split-cluster
plumbing that exists does not deliver a usable networking capability. Providers
need the networking path to follow VM hosting because tenant workloads carry the
network load, address consumption, and failure blast radius that they do not
want on the cluster running OSAC's own control plane. Leaving this unaddressed
keeps workload-cluster deployments outside the VMaaS networking support
boundary.

## In Scope

- Placement is chosen in two steps. At installation, the deployment is set to
  run VMs either on the single management cluster or on dedicated workload
  clusters, and any number of workload clusters can be registered at runtime.
  In the workload-cluster mode, the Cloud Provider Admin assigns one registered
  workload cluster when the tenant is created, and all of that tenant's VMs and
  tenant networking run on it. Both choices are provider-side administration:
  tenants neither choose nor see the cluster that hosts their VMs. Neither
  choice can be changed afterwards: switching the deployment mode requires a
  reinstall, and moving a tenant to another cluster is not supported.
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
- Each workload cluster's networking prerequisites are configured once, when the
  cluster is registered, rather than per VM or per tenant: an EVPN-capable
  OVN-Kubernetes on that cluster, BGP routing and VTEPs on its nodes, the
  cluster's AS, VTEP range, and the fabric's BGP peers and AS agreed with the
  provider, and provider fabric peering with those nodes.
- Because the workload cluster carries the VM networking, the management cluster
  no longer needs the EVPN host setup for tenant VM traffic, which is part of why
  a provider chooses this shape.
- OSAC's Kubernetes Manager configures tenant networking on the tenant's
  workload cluster. The fabric manager keeps its own tasks and stays registered
  once; it is not re-registered or re-pointed per cluster.
- Existing management-cluster deployments continue to behave exactly as before.

## Out of Scope

- General workload-cluster management itself, including provisioning,
  lifecycle, and credential handling of that cluster; this work consumes that
  foundation.
- Choosing a cluster per VM or per project, and placing one tenant's VMs on more
  than one cluster.
- Cross-cluster network mobility, per-cluster duplication of one tenant's
  networking resources, and moving an existing tenant's VMs or networks to a
  different workload cluster.
- Non-networking VM capabilities on the workload cluster, including storage
  tiers, volume metering, console access, power state, restart, and GPU: this
  work does not change them and does not claim them as a new capability.
- Placement choices other than the cluster selected at tenant creation,
  including per-VM placement, placement changes, and any other UI or UX change.
- Networking for hosted control plane clusters and for MaaS gateway clusters.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to assign one registered workload cluster
  when a tenant is created, so that all of that tenant's VMs run on a cluster I
  chose and tenants never have to know about the OpenShift clusters behind
  OSAC.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to choose at installation whether a
  deployment hosts VMs on the management cluster or on dedicated workload
  clusters, so that VM hosting can be separated from the management cluster
  without offering tenants a per-VM placement choice.
- As a Cloud Infrastructure Admin, I want to register and prepare each workload
  cluster's networking prerequisites once, so that any registered cluster can
  host tenants without per-VM or per-tenant setup.
- As a Cloud Infrastructure Admin, I want VM provisioning on a workload cluster
  with provider networking enabled to fail with a diagnostic that identifies the
  unmet networking prerequisite, so that I can tell a cluster or networking
  problem from a tenant request problem.

### Tenant Admin

- As a Tenant Admin, I want my tenant's VirtualNetworks, Subnets,
  SecurityGroups, and default networking to keep working with the same
  isolation on a workload cluster, so that my users' VMs stay on their own
  networks without depending on management-cluster placement.

### Tenant User

- As a Tenant User, I want to create a VM on my tenant's workload cluster with
  my requested Subnet and SecurityGroups, or with my tenant defaults, and see
  its address and network readiness, so that I can run workloads the same way I
  do today.
- As a Tenant User, I want to expose my VM through a pool-allocated external
  address, so that clients outside the tenant network can reach it.

## Assumptions

- The workload-cluster foundation provides the cluster, its credentials, and
  the access path that VM provisioning and networking use; this PRD does not
  define that foundation.
- Workload clusters can be registered with OSAC at runtime, and the placement
  foundation records which cluster a tenant runs on. This PRD consumes that
  placement foundation and does not define it. The foundation is not implemented
  yet, so the placement model in this document is the target state.
- Users run this capability with provider networking enabled. The
  networking-disabled configuration exists for CI and is not a tenant-facing
  deployment mode.

## Delivery Sequencing

- The first increment delivers this capability on the configuration that exists
  today: a deployment installed with a separate workload cluster, using the
  documented multicluster installation and a workload-cluster kubeconfig. That
  path already runs VMs on the separate cluster with provider networking
  disabled; this capability adds provider networking to it and does not wait for
  runtime cluster registration or per-tenant cluster assignment. Until those
  land, placement stays deployment-wide, the one configured workload cluster
  hosts every tenant's VMs, and tenants see no placement choice.
- The placement model in this document becomes available when the placement
  foundation lands. The ordering of the two increments, and what providers
  should expect in between, must be agreed with that work before implementation
  starts.

## Dependencies

- **VMaaS networking baseline (OSAC-1435):** provides the attachment model,
  address reporting, and external-access behavior this capability extends. It
  blocks this work and must land first.
- **Workload-cluster and placement foundation:** provides runtime cluster
  registration, cluster credentials and remote access, and the per-tenant
  cluster assignment that the Cloud Provider Admin makes at tenant creation.
  This feature consumes it and does not deliver it; see Delivery Sequencing for
  the order of the two increments.
- **Accepted designs that must be amended for this capability:** the Unified
  Networking hub support boundary, which currently excludes the workload-cluster
  option; the network manager contract, where tasks currently reach the hub with
  no cluster identifier and the fabric extends and peers VRFs with hub nodes,
  together with its conformance tests; the CUDN EVPN design, whose hub
  prerequisites this capability changes; and the VMaaS networking design, whose
  non-goals exclude VMs outside the hub.
- **OSAC operator behavior:** the operator currently refuses to run with a
  remote cluster configured while provider networking is enabled. That
  restriction must be lifted as part of this capability.
- **Fabric manager, provider fabric, and external address pools:** the fabric
  manager must reach the fabric controller and needs no cluster access; the
  provider fabric must peer with the workload cluster's nodes; and address pools
  must have capacity for external access.
- **Design and delivery obligations:** the design EP for this Feature must
  define how tenant networking follows the tenant's assigned cluster; delivery
  must include automated tests that distinguish management-cluster from
  workload-cluster placement and deployment documentation covering topology,
  prerequisites, and limitations.
- **CI-only networking-disabled path:** depends on the remote-cluster placement
  defect tracked in OSAC-7297 being resolved before that path can be exercised
  in CI.

---

## Provenance

Committed: commit @ prd 0.11.5 - 70405a6, workspace prd/OSAC-7307 @ 21202a8 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"21202a8 (dirty)","source_repo_branch":"prd/OSAC-7307","commits_behind_main":0,"commits_ahead_main":4,"main_ref":"main","phases":["commit","commit","commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
