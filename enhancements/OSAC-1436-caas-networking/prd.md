# CaaS Networking — Unified API with Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support only Create, List/Get, and Delete. A Cluster's
network selection is fixed at creation; changing it requires replacing the
Cluster.

CaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

Provider-dependent connectivity, allocation, and cleanup in this document
describe the enabled mode. FR-12 defines the shared installation/upgrade
setting and disabled experience. Networking APIs retain the published default
SecurityGroup selection, immutability, validation, and dependency rules in
both modes. [User]

## 1. Problem Statement

Cluster provisioning has no networking configuration. Tenants cannot choose which subnet their cluster nodes use, cannot place two clusters in the same virtual network, and cannot isolate them in separate networks. All clusters are placed on a single deployment-wide networking backend with zero tenant control. Cluster networking is completely divergent from VM and bare-metal server workflows, requiring separate knowledge and tools.

## 2. Goals and Non-Goals

### 2.1 Current network attachment constraint

CaaS supports one tenant network attachment per Cluster. It supplies the
Subnet for the whole Cluster; node sets do not receive separate tenant
attachments. Multi-NIC cluster-node networking is future scope.

### 2.2 Goals

- A tenant can create a cluster with explicit network configuration, specifying which subnet and security groups to use for cluster nodes
- A cluster uses one tenant Subnet for all node sets, and the service chooses suitable interfaces for those nodes
- Tenants can request automatic external IP attachment for cluster API server and ingress endpoints with `--external-ip-attachment`, without pre-creating external IP resources
- When network configuration is omitted, the system applies the tenant's default subnet and security group
- Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- The platform provisions suitable bare-metal hosts and provides required network connectivity as part of cluster creation
- Auto-provisioned external IPs and external IP attachments are cleaned up when the cluster is deleted
- Administrators can make suitable tenant-facing interfaces discoverable for each server type

### 2.3 Non-Goals

- VM-based cluster node sets (deferred — bare-metal only for initial release)
- DNS API for cluster endpoints (automated DNS management is outside this enhancement)
- Per-node-set subnet placement (all node sets share the cluster's single network attachment)
- Multi-NIC cluster nodes (one tenant Subnet is supported for the initial release)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a cluster with explicit network configuration so that I can place it on a specific subnet with specific security group rules
- As a Tenant User, I want cluster node sets to use a suitable tenant-facing interface automatically so that I do not need to know the host's physical port layout
- As a Tenant User, I want to create a cluster with `--external-ip-attachment` so that the system provisions external IPs for both the API server and ingress and the cluster is externally reachable in a single API call
- As a Tenant User, I want to create a cluster without specifying network configuration and have it placed on my default subnet with my default security groups
- As a Tenant User, I want to see my cluster's API server and ingress endpoint addresses in the cluster status so that I can access the cluster
- As a Tenant User, I want auto-provisioned networking resources to be automatically cleaned up when I delete my cluster so that I do not accumulate orphaned resources

### Tenant Admin Stories

- As a Tenant Admin, I want to place multiple clusters in the same virtual network so that they can communicate privately with each other and with my VMs
- As a Tenant Admin, I want to isolate clusters in separate virtual networks so that I can enforce network boundaries between different projects or teams

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to make suitable tenant-facing interfaces discoverable for cluster node types so that the service can connect them to the selected Subnet

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see whether Cluster networking is ready and what failed so I can troubleshoot provisioning issues

## 4. Requirements

### 4.1 Functional Requirements

#### Network Configuration

- **FR-1:** A tenant can attach a Cluster to one Subnet, shared by all of its node sets. The selection is fixed at Cluster creation. OSAC uses the default SecurityGroup only when it belongs to the selected Subnet's VirtualNetwork; otherwise the tenant selects SecurityGroups from that VirtualNetwork. The service chooses a suitable tenant-facing interface for each node set. [User]

#### Optional Network Configuration with Defaults

- **FR-2:** Network selection is optional. If the tenant omits it, OSAC uses the tenant's defaults. If the tenant supplies a partial selection, OSAC fills only missing choices and preserves supplied values. The resolved network remains visible with the Cluster after creation. [User]

#### Auto External IP

- **FR-3:** A tenant can request `--external-ip-attachment` for a Cluster's management API and guest ingress endpoints. OSAC accepts the request only when enough address capacity is available. Address assignment may finish asynchronously and does not block Cluster installation. Each inbound route becomes available only after its address and matching Cluster endpoint are ready. Automatically created addresses and routes are identifiable and visible to their owner. [User]

#### Endpoint Discovery

- **FR-4:** Cluster status makes the API and guest ingress addresses available when they are known. Workers can reach the API for installation through the platform's management connectivity; optional tenant inbound addresses are reported separately and are not required for bootstrap. [User]

#### External IP Activation

- **FR-5:** OSAC activates inbound access only after the requested external address is real and the corresponding API or ingress endpoint is ready. If either is unavailable, the route remains unavailable and the Cluster does not report external access as ready. [User]

#### Host Selection and Network Configuration

- **FR-6:** Cluster creation uses available hosts that meet each node set's selected type. Worker installation can proceed once required management connectivity is available; optional tenant external addresses do not block that bootstrap path. [User]

#### Network Connectivity Setup

- **FR-7:** When provider networking is enabled, each worker joins its selected tenant network with the requested SecurityGroup policy and receives a tenant address before joining the Cluster. A network or address-discovery failure is visible and prevents the affected worker from being reported as connected. [User]

#### Cluster Provisioning

- **FR-8:** Cluster installation and worker bootstrap do not depend on optional tenant ExternalIPs. The API and guest ingress endpoints are available through their respective platform and tenant network paths, with the addresses and publication needed by users and workers provided when the endpoints are ready. Cluster readiness does not claim that an optional ExternalIP has been assigned. [User]

#### Worker Interface Availability

- **FR-9:** Tenants and administrators can discover the available network interfaces and their relevant characteristics for each bare-metal instance type. The service selects a suitable tenant-facing interface for each node set when the tenant does not choose one. [User]

#### Bare-Metal Only

- **FR-10:** The initial release supports bare-metal Cluster node sets. VM-based node sets are outside this release's scope. [User]

#### Auto-Provisioned Resource Cleanup

- **FR-11:** Automatically created external addresses and routes remain visible and identifiable. Cluster deletion removes them and the Cluster's dependent network state in a safe order. If provider cleanup fails, deletion remains pending with a diagnostic until cleanup can continue. The owner removes manually created inbound routes first; shared tenant defaults remain available. [User]

#### Provider Networking Disabled

- **FR-12:** A Cloud Provider Admin can disable provider networking during installation or upgrade while keeping ordinary Cluster provisioning and the networking APIs available. The setting takes effect after rollout. When disabled, Cluster and worker provisioning or deletion can continue if the platform's baseline connectivity and installation prerequisites are available. OSAC does not configure tenant networking or public ExternalIP routes; endpoint addresses are reported only when supplied by the baseline environment. Networking requests retain their normal validation and dependency rules, and their status makes clear when provider work was skipped rather than completed. Automatic ExternalIP requests do not block Cluster installation and do not provide inbound routes without real addresses and ready endpoints. Logical deletion remains available, while skipped provider cleanup may require administrator action. [User]

#### Shared Network and Policy Behavior

- **FR-13:** CaaS can operate in a deployment that serves bare-metal clusters without VM networking. Clusters remain isolated when tenants use identical private CIDRs, and distinct guest endpoints sharing a Subnet receive distinct addresses without colliding with workload addresses. [User]
- **FR-14:** Each worker interface uses its selected groups' complete stateful ingress/egress policy before tenant traffic; allow rules combine, established replies are allowed, and unmatched new traffic is denied. Failure is visible and keeps the dependent network lifecycle step non-ready. [User]

Re-enabling provider networking requires the Cloud Provider Admin to drain/delete all existing deployment workloads, including managed cluster workers, finish or account for outstanding network operations, and arrange cleanup of leftover provider state. Workloads remain readable/deletable during the transition, but new workload creation is blocked. After deployment activation, each new workload requires its own provider-backed network dependencies to be ready; a failure in one tenant's defaults does not block other ready tenants. OSAC does not automatically move existing baseline workloads into tenant networks. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** OSAC checks capacity before accepting an automatic external-access request. Address assignment and endpoint discovery may continue asynchronously, and optional address assignment does not block Cluster installation.

Connectivity, allocation, provider policy enforcement/cleanup, and related
provider-work timing requirements described here apply when provider networking is
enabled. Disabled mode retains API prerequisites and explicitly identifies
skipped provider work; it does not claim those provider outcomes. [User]

## 5. Acceptance Criteria

- [ ] Re-enabling networking with existing workloads is blocked; users can inspect and delete them. After all workloads and outstanding network work are drained and backend leftovers repaired, activation reconciles real network readiness before accepting new workloads. No baseline workload is migrated in place. [User]

- [ ] A cluster installs without optional tenant external addresses; workers continue reaching its management API when optional external allocation fails or is delayed
- [ ] Two tenants with identical private subnet CIDRs each provision a cluster with isolated ingress; concurrent guest clusters on one subnet receive distinct ingress addresses
- [ ] A cluster-only deployment without VM networking provisions API and guest ingress correctly
- [ ] Optional API and ingress inbound addresses reach their respective management-hosted API and tenant-hosted router endpoints
- [ ] Persistent enabled-mode cleanup failure leaves deletion pending with a diagnostic and preserves address ownership until repair [User]
- [ ] A Tenant User can create a cluster with network configuration specifying a subnet and security groups, and the cluster nodes are provisioned on the specified subnet
- [ ] A Tenant User can create a Cluster with multiple node sets that share one tenant Subnet, and the service selects a suitable interface for each node set
- [ ] A Tenant User can create a cluster with `--external-ip-attachment` and no explicit network configuration — the cluster is created on the default subnet with auto-provisioned external IPs for both API and ingress
- [ ] Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- [ ] Each inbound route becomes available only after its external address and matching Cluster endpoint are ready
- [ ] Workers can reach the Cluster's management API for installation without relying on optional tenant inbound addresses
- [ ] Auto-created external IPs and external IP attachments are labeled as auto-provisioned and visible in list views
- [ ] Deleting a cluster with auto-provisioned resources causes the auto-created external IPs and external IP attachments to be cleaned up
- [ ] The service selects an appropriate tenant-facing interface for each node set when the tenant does not specify one

- [ ] Cluster installation and deletion remain available with provider networking disabled when baseline platform connectivity is sufficient; OSAC does not promise tenant-managed addresses or routes
- [ ] Disabled CaaS reports endpoint addresses only when supplied by the baseline environment and does not present an unassigned tenant address as reachable
- [ ] With provider networking disabled, automatic external-access requests do not block Cluster installation and do not expose a fabricated address or route; inbound access becomes available only after a real address and matching ready endpoint exist
- [ ] Default SecurityGroup resolution, invalid-reference/non-ready-dependency rejection, tenant boundaries, and existing interface/cardinality/immutability rules remain active
- [ ] Networking specification and metadata updates, including SecurityGroup rules, remain rejected in both modes
- [ ] Cluster deletion remains available when provider networking is disabled, reports skipped provider cleanup clearly, and does not claim that a tenant network interface was restored when no such operation occurred

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created. If defaults are not configured, creating a cluster without explicit network configuration fails with a clear error.
- The deployment's network infrastructure is configured to support virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways, and network connectivity management.
- Each available bare-metal server type exposes a suitable tenant-facing interface that the service can select for a node set when no interface is supplied.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **Network Manager Integration Contract** — defines the provider manager requirements and shared dispatch behavior; this PRD defines how CaaS cluster lifecycle uses that contract ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))

## 8. Risks

### 8.1 Suitable host availability

- **Owner:** Platform team
- **Mitigation:** The deployment must provide enough available bare-metal hosts of the required types for cluster creation. Report an actionable error when no suitable hosts are available.

### 8.2 Endpoint discovery delay or failure

- **Owner:** Platform team
- **Mitigation:** If endpoint addresses are not discovered correctly, they will not appear in cluster status, and external IP attachments will not activate. Monitor endpoint discovery reliability and address discovery mechanisms.

### 8.3 Suitable tenant interfaces are unavailable

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Ensure each server type offered for cluster nodes has at least one tenant-facing interface. Without one, cluster creation cannot provide tenant connectivity on that node set.

### 8.4 IP address pool configuration for API and ingress endpoints

- **Owner:** Platform team / Cloud Infrastructure Admin
- **Mitigation:** The management API path must be available for worker installation, and guest ingress addresses must remain unique for clusters that share a Subnet. Address ownership is retained until cleanup completes. [User]

## 9. Open Questions

There are no open product questions. Resolved host lifecycle, address
allocation, and network configuration decisions are documented in the
[CaaS networking design](/enhancements/OSAC-1436-caas-networking/design.md).

---

## Provenance

Authored: revise @ prd 0.11.5 - 6d28c88, workspace docs/OSAC-1433-network-manager-provider-guide @ eabff3b59 (76 behind origin/main, dirty)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace docs/OSAC-1433-network-manager-provider-guide @ 639af2dba

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"639af2dba","source_repo_branch":"docs/OSAC-1433-network-manager-provider-guide","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
