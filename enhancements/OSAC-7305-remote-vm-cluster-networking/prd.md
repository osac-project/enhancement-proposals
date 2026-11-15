# VMaaS Networking with Per-Tenant VM Clusters

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

- The Cloud Infrastructure Admin registers the clusters that run tenant VMs:
  workload clusters and, if wanted, the management cluster. A cluster can be
  registered at installation or later, and the management cluster has no special
  status among registered clusters.
- Each VM-hosting cluster is prepared for tenant networking once, when it is
  registered, by the Cloud Infrastructure Admin together with the provider's
  network team. No per-tenant or per-VM networking setup is needed, and the
  management cluster needs this preparation only if tenants are assigned to it.
- The Cloud Provider Admin assigns one registered VM cluster to each tenant when
  the tenant is created, so one deployment can host different tenants on
  different clusters. That cluster can be the management cluster or a workload
  cluster. All of a tenant's VMs run on the assigned cluster, and the tenant's
  networks work for them there.
- The assignment is provider-side administration: tenants neither choose nor see
  the cluster that hosts their VMs. Changing a tenant's cluster after creation
  is not supported.
- A cluster that is not prepared for tenant networking cannot be assigned, and a
  removed cluster cannot be assigned. Tenant creation that names either is
  rejected with an error identifying the cluster and the unmet prerequisite. The
  gate is enforced by the API and adds no UI or UX change.
- A cluster can be removed from VM hosting only when no tenant is assigned to
  it; a removed cluster is no longer available for assignment.
- When provider networking is enabled, a VM on its tenant's assigned cluster
  attaches to one tenant Subnet and its SecurityGroups, either selected
  explicitly or resolved from tenant defaults, receives its tenant IPv4 address,
  and reports network readiness before it reports ready.
- External access for those VMs with the same behavior as on the management
  cluster today, including pool-allocated ExternalIPs, attachments, and outbound
  translation.
- Tenant isolation on every VM-hosting cluster, including the same visibility,
  access, and dependency rules that apply on the management cluster.
- A CI-only configuration where provider networking is disabled: VM provisioning
  still succeeds, networking steps are skipped, and VM readiness does not depend
  on a tenant IPv4 address or provider connectivity, matching today's behavior.
- If a cluster becomes unprepared after a tenant is assigned to it, VM
  provisioning fails with a diagnostic that identifies the unmet networking
  prerequisite.
- A fresh installation whose tenants are assigned to the management cluster
  behaves exactly as it does today: the same networking behavior, the same
  preparation on the management cluster, and no new prerequisites. No upgrade or
  migration path is claimed.

## Out of Scope

- General workload-cluster management: provisioning a cluster, its credentials,
  and connecting it to the deployment; this work consumes that foundation.
- The placement mechanism that records which cluster a tenant runs on; this work
  consumes the placement foundation that provides it.
- Choosing a cluster per VM or per project, and placing one tenant's VMs on more
  than one cluster.
- Cross-cluster network mobility, per-cluster duplication of one tenant's
  networking resources, and moving an existing tenant's VMs or networks to a
  different cluster.
- Upgrading an existing installation to change where its tenants' VMs run, and
  migrating tenants between clusters.
- Non-networking VM capabilities on a VM-hosting cluster, including storage
  tiers, volume metering, console access, power state, restart, and GPU: this
  work does not change them and does not claim them as a new capability.
- Any UI or UX change, including cluster-selection and cluster-readiness
  interfaces.
- Networking for hosted control plane clusters and for MaaS gateway clusters.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to assign one registered VM cluster to a
  tenant when it is created, whether that cluster is the management cluster or a
  workload cluster, so that I control where each tenant's VMs run and tenants
  never have to know about the OpenShift clusters behind OSAC.
- As a Cloud Provider Admin, I want an error that names the cluster and the
  unmet prerequisite when I assign a cluster that is not prepared for tenant
  networking, so that I know which cluster to fix instead of guessing why
  onboarding failed.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register the clusters that run
  tenant VMs at installation or later, and prepare each one for tenant
  networking once when it is registered, so that any registered cluster can host
  tenants without per-VM or per-tenant setup.
- As a Cloud Infrastructure Admin, I want to remove a cluster from VM hosting
  only when no tenant is assigned to it, so that I never strand a tenant's
  networking on a cluster that is leaving service.
- As a Cloud Infrastructure Admin, I want VM provisioning on a tenant's assigned
  cluster with provider networking enabled to fail only when a networking
  prerequisite is unmet, with a diagnostic that identifies it, so that I can
  tell a cluster or networking problem from a tenant request problem.

### Tenant Admin

- As a Tenant Admin, I want my tenant's VirtualNetworks, Subnets,
  SecurityGroups, and default networking to keep working with the same
  isolation, so that my users' VMs stay on their own networks.

### Tenant User

- As a Tenant User, I want to create a VM with my requested Subnet and
  SecurityGroups, or with my tenant defaults, and see its address and network
  readiness, so that I can run workloads the same way I do today.
- As a Tenant User, I want to expose my VM through a pool-allocated external
  address, so that clients outside the tenant network can reach it.

## Assumptions

- Workload clusters are created in advance or connected as a day-2 operation,
  using the capability that the placement foundation provides. That foundation
  provides the cluster, its credentials, and the access path that VM
  provisioning and networking use; this PRD does not define it.
- The placement foundation records which cluster a tenant runs on and exposes
  whether a registered cluster is prepared. This PRD consumes it and does not
  define it.
- Users run this capability with provider networking enabled. The
  networking-disabled configuration exists for CI and is not a tenant-facing
  deployment mode.

## Delivery Sequencing

- First increment: provider networking for VMs on the workload-cluster shape
  that today's multicluster installation provides, serving all tenants.
- Second increment: per-tenant assignment across the management cluster and
  several workload clusters, including registering and removing VM-hosting
  clusters, once the placement foundation lands.
- The networking path resolves the target cluster per tenant from the first
  increment, so a single cluster is only the degenerate case. The second
  increment changes placement only, not the networking path.

## Dependencies

- **VMaaS networking baseline (OSAC-1435):** provides the attachment model,
  address reporting, and external-access behavior this capability extends. It
  blocks this work and must land first.
- **Workload-cluster and placement foundation
  ([OSAC-XXXX](https://redhat.atlassian.net/browse/OSAC-XXXX)):** provides
  cluster credentials and remote access, cluster registration at installation or
  later, and the per-tenant cluster assignment that the Cloud Provider Admin
  makes at tenant creation. This feature consumes it and does not deliver it;
  see Delivery Sequencing.
- **Accepted designs that must be amended for this capability:** the Unified
  Networking hub support boundary, which currently excludes VM hosting outside
  the management cluster; the network manager contract, whose task targeting,
  VRF peering, and conformance tests assume the management cluster; the CUDN
  EVPN design, whose management-cluster prerequisites this capability changes;
  and the VMaaS networking design, whose non-goals exclude VMs outside the hub.
  The design for this Feature (OSAC-7308) defines the changes, including how
  tenant networking follows the assigned cluster.
- **Design and delivery obligations:** delivery must include automated tests
  that distinguish management-cluster from workload-cluster placement, and
  deployment documentation covering topology, prerequisites, and limitations.
- **CI-only networking-disabled path:** depends on the remote-cluster placement
  defect tracked in OSAC-7297 being resolved before that path can be exercised
  in CI.

---

## Provenance

Committed: commit @ prd 0.11.5 - 70405a6, workspace prd/OSAC-7307 @ 21202a8 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"21202a8 (dirty)","source_repo_branch":"prd/OSAC-7307","commits_behind_main":0,"commits_ahead_main":4,"main_ref":"main","phases":["commit","commit","commit","commit"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
