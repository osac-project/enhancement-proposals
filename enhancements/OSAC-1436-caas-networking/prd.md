# CaaS Networking — Unified API with Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-09-24 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support read (List/Get), create, and delete. NetworkACL
rules and Subnet-to-ACL associations are immutable after creation. The Cluster
network attachment remains create-time-only; changing it requires delete and
recreate.

CaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## 1. Problem Statement

Cluster provisioning has no networking configuration. Tenants cannot choose which subnet their cluster nodes use, cannot place two clusters in the same virtual network, and cannot isolate them in separate networks. All clusters are placed on a single deployment-wide networking backend with zero tenant control. Cluster networking is completely divergent from VM and bare-metal server workflows, requiring separate knowledge and tools.

## 2. Goals and Non-Goals

### 2.0 Current network attachment constraint

CaaS supports one `network_attachment` per Cluster. That attachment supplies
the subnet for the entire cluster; node sets do not receive separate tenant
attachments. Multi-NIC cluster-node networking is future scope.

### 2.1 Goals

- A tenant can create a cluster with explicit network configuration, specifying which subnet to use for cluster nodes and using that subnet's optional NetworkACL to refine the deployment default ACL policy
- A cluster uses a single network attachment — one subnet for all node sets. The system automatically determines which physical interface to use for each node set based on its BareMetalInstanceType
- Tenants can request automatic external IP attachment for cluster API server and ingress endpoints with `--external-ip-attachment`, without pre-creating external IP resources
- When network configuration is omitted, the system applies the tenant's default Subnet, which has no ACL association, under the deployment default ACL policy
- Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- The system automatically selects suitable bare-metal hosts and configures network connectivity before cluster provisioning begins
- Auto-provisioned external IPs and external IP attachments are cleaned up when the cluster is deleted
- BareMetalInstanceTypes provide structured network-port information that the system uses to configure network connectivity

### 2.2 Non-Goals

- VM-based cluster node sets (deferred — bare-metal only for initial release)
- DNS API for cluster endpoints (DNS record creation remains template-based until DNS API is implemented)
- Per-node-set subnet placement (all node sets share the cluster's single network attachment)
- Multi-NIC cluster nodes (the current contract has one attachment per cluster; the system automatically determines which physical interface to use for each node set based on its BareMetalInstanceType)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a cluster with explicit network configuration so that I can place it on a specific subnet and use an optional NetworkACL associated with that subnet to refine the deployment default traffic policy
- As a Tenant User, I want my cluster's node sets to automatically use the correct physical interface based on their BareMetalInstanceType so that network connectivity is configured without manual interface specification
- As a Tenant User, I want to create a cluster with `--external-ip-attachment` so that the system provisions external IPs for both the API server and ingress; inbound reachability follows the effective Subnet policy
- As a Tenant User, I want to create a cluster without specifying network configuration and have it placed on my default Subnet under the deployment default ACL policy; with a `DENY` fallback, cluster installation requires a selected Subnet with a READY NetworkACL that permits required egress and reply flows, or a deployment configured with `PERMIT`
- As a Tenant User, I want to see my cluster's API server and ingress endpoint addresses in the cluster status so that I can access the cluster
- As a Tenant User, I want auto-provisioned networking resources to be automatically cleaned up when I delete my cluster so that I do not accumulate orphaned resources

### Tenant Admin Stories

- As a Tenant Admin, I want to place multiple clusters in the same virtual network so that they can communicate privately with each other and with my VMs
- As a Tenant Admin, I want to isolate clusters in separate virtual networks so that I can enforce network boundaries between different projects or teams
- As a Tenant Admin, I want to manage the optional NetworkACL associated with a cluster subnet so that its matching rules refine traffic policy consistently to every node set on that subnet

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define structured network-port metadata for BareMetalInstanceTypes so that the system can automatically configure network connectivity when provisioning clusters

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether cluster hosts were successfully selected and network connectivity configured so I can troubleshoot provisioning failures

## 4. Requirements

### 4.1 Functional Requirements

#### Network Configuration

- **FR-1:** Cluster creation supports one network attachment that identifies the subnet for the entire cluster; all node sets share that subnet. The subnet may be omitted, and the resolved attachment is immutable after creation. Any NetworkACL associated with the selected subnet refines the deployment default ACL policy for all cluster nodes; when absent, the deployment default action applies. The system determines which physical network interface to use for each node set from its BareMetalInstanceType. [User]

#### Optional Network Configuration with Defaults

- **FR-2:** Network configuration is optional when creating a cluster. When the attachment is omitted or empty, the system applies the tenant's default Subnet, which has no ACL association. When an attachment is supplied without a Subnet, only the Subnet is defaulted; supplied values are preserved. The resolved Subnet is stored with the cluster so the cluster is self-describing after creation. For an explicitly selected Subnet, any associated NetworkACL refines the deployment default policy. The default Subnet's unmatched traffic follows the deployment action: `DENY` blocks unmatched ingress and egress. Because connected cluster installation requires outbound access to assisted-service and image sources, a deployment using `DENY` must use an explicitly selected Subnet created with a READY NetworkACL that allows those flows and required replies, with the egress path configured; otherwise the deployment must use `PERMIT` for the default Subnet. [User; PR review: CodeRabbit]

#### Auto External IP

- **FR-3:** Cluster creation supports `--external-ip-attachment`. When enabled, the system reserves capacity for two external IPs, one for the API server and one for ingress, before provisioning begins. The IPs are allocated asynchronously. Their attachments are created only after both IPs are Allocated and the Cluster is Ready with both endpoints available; inbound routing begins after the attachments are provisioned. External IPs and attachments are labeled as auto-provisioned. [User]

#### Endpoint Discovery

- **FR-4:** Cluster status exposes API server and ingress endpoint addresses. The system discovers these addresses during cluster provisioning and makes them available in the cluster status. [User]

#### External IP Activation

- **FR-5:** When automatic external IP allocation is enabled, inbound routing to the API server and ingress becomes available after the Cluster is Ready, the endpoint addresses are available, and the corresponding ExternalIPs are Allocated, subject to the effective Subnet policy. ExternalIP routing does not bypass that policy; unmatched inbound traffic to the unassociated default Subnet is denied when the deployment action is `DENY`. To permit it, use the `PERMIT` default or an explicitly selected Subnet created with a NetworkACL that allows the required inbound and return flows. [User; PR review: CodeRabbit]

#### Host Selection and Network Configuration

- **FR-6:** The system selects and reserves suitable bare-metal hosts for each node set before cluster provisioning begins, based on the node set's BareMetalInstanceType and availability. Selected hosts are reserved for the cluster to prevent allocation conflicts. [User]

#### Network Connectivity Setup

- **FR-7:** BMaaS provisions each selected host on the provisioning network, then moves the host's stored `fabric_interface` to the tenant network, reboots the host, and discovers its tenant-network DHCP address before the host joins the cluster installation flow. The interface is resolved once from the node set's BareMetalInstanceType during cluster creation and stored on the ClusterOrder; CaaS does not re-resolve it at worker creation time. [User]

#### Cluster Provisioning

- **FR-8:** Cluster provisioning creates the cluster using pre-selected hosts with pre-configured network connectivity. The provisioning process allocates IP addresses for the API server and ingress endpoints, performs DNS record creation, and makes the endpoint addresses available in cluster status. [User]

#### BareMetalInstanceType Network Ports

- **FR-9:** BareMetalInstanceTypes include structured network-port information (name, role, type, speed). The system automatically selects the first `fabric` port for each node set when resolving the cluster's single tenant attachment. [User]

#### Bare-Metal Only

- **FR-10:** Cluster node sets are bare-metal only for the initial release. VM-based cluster node sets are architecturally supported but deferred. [User]

#### Auto-Provisioned Resource Cleanup

- **FR-11:** Auto-provisioned networking resources (external IPs, external IP attachments) are labeled as auto-provisioned. When a cluster is deleted, the system cleans up auto-provisioned resources in dependency order: external IP attachments first, then external IPs. A manually created ExternalIPAttachment in `Ready` status targeting the cluster blocks its deletion until the tenant removes it; Pending or Failed attachments do not block deletion and remain tenant-managed. Other manually created ExternalIPs remain tenant-managed. Default networking resources (virtual networks, subnets, NATGateways) are not cleaned up as they are tenant-scoped and shared across resources. Tenant-created NetworkACLs are not auto-deleted because they may be shared by multiple Subnets. [User]

#### NetworkACL Policy

- **FR-12:** Cluster traffic uses the deployment default ACL policy, refined by any NetworkACL associated with its Subnet, uniformly across all node sets. Each Subnet has zero or one active association, and an ACL may be reused by Subnets in the same VirtualNetwork. Ingress and egress rules are evaluated independently using the shared match-specificity order; action and request order do not determine precedence. The first matching rule allows or denies traffic, and traffic with no matching rule uses the required deployment default ACL action, which also applies when no ACL is associated. The policy is stateless, so return traffic is evaluated independently in the reverse direction. With a `DENY` fallback, permitting a reply requires a matching reverse-direction `ALLOW` rule to win precedence; with `PERMIT`, an unmatched reply passes unless a matching reverse-direction `DENY` rule applies. Traffic between workloads on the same Subnet is not filtered by the Subnet NetworkACL; traffic between Subnets must satisfy the source Subnet's egress policy and the destination Subnet's ingress policy. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** ExternalIPPool selection and capacity reservation complete synchronously with the cluster create request. ExternalIP allocation and attachment provisioning follow their readiness prerequisites; API and ingress endpoint addresses are available in Cluster status when the Cluster becomes Ready, without an additional delayed discovery step.

## 5. Acceptance Criteria

- [ ] A Tenant User can create a cluster with network configuration specifying a subnet, and the cluster nodes are provisioned on that subnet under its optional NetworkACL association and the deployment default ACL policy
- [ ] A Tenant User can create a cluster with a single network attachment and multiple node sets, and all node sets are provisioned on the same subnet with the appropriate physical interface automatically selected from each node set's BareMetalInstanceType
- [ ] A Tenant User can create a cluster with `--external-ip-attachment` and no explicit network configuration — the cluster is created on the default subnet with auto-provisioned external IPs for both API and ingress; inbound reachability follows the effective Subnet policy, and unmatched inbound traffic is denied when the deployment action is `DENY`
- [ ] Cluster installation can reach assisted-service and image sources only when its effective Subnet policy permits the required outbound and reply flows; under a `DENY` fallback, the tenant uses an explicitly selected Subnet created with a permitting NetworkACL and a configured egress path, or the deployment uses `PERMIT` for the default Subnet
- [ ] Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- [ ] Auto-created external IP attachments are created only after both ExternalIPs are Allocated and the Cluster is Ready with API and ingress endpoint addresses; DNAT is configured afterward
- [ ] The system selects hosts and configures network connectivity before cluster provisioning begins
- [ ] Auto-created external IPs and external IP attachments are labeled as auto-provisioned and visible in list views
- [ ] Deleting a cluster with auto-provisioned resources causes the auto-created external IPs and external IP attachments to be cleaned up
- [ ] Deleting a cluster with a Ready, manually created ExternalIPAttachment targeting it is rejected until the tenant removes that attachment; Pending or Failed attachments do not block deletion
- [ ] The system determines which physical network interface to use based on each node set's BareMetalInstanceType `network_ports` configuration
- [ ] Cluster traffic uses the first matching NetworkACL rule under the shared match-specificity order and unmatched traffic uses the deployment default ACL action; under `DENY`, permitting return traffic requires a matching reverse-direction `ALLOW` rule to win precedence, while under `PERMIT`, unmatched replies pass unless a reverse-direction `DENY` rule applies

## 6. Assumptions

- The tenant has a default VirtualNetwork and Subnet pre-created, with no ACL association on the default Subnet; unmatched traffic uses the required deployment-wide default ACL action. If defaults are not configured, creating a cluster without explicit network configuration fails with a clear error.
- The deployment's network infrastructure is configured to support virtual networks, subnets, NetworkACLs, external IPs, external IP attachments, NAT gateways, and network connectivity management.
- BareMetalInstanceTypes have structured `network_ports` configuration. The system uses the first `fabric` port for each node set when no interface is supplied by the CaaS flow.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, NetworkACLs, external IPs, external IP attachments, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default Subnet selection, optional ACL association, and deployment fallback action defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)

## 8. Risks

### 8.1 Host selection logic complexity

- **Owner:** Platform team
- **Mitigation:** Host selection logic must account for BareMetalInstanceType matching, availability, and labels. If not implemented correctly, cluster provisioning cannot proceed. Thorough testing required.

### 8.2 Endpoint discovery delay or failure

- **Owner:** Platform team
- **Mitigation:** If endpoint addresses are not discovered correctly, they will not appear in cluster status, and external IP attachments will not activate. Monitor endpoint discovery reliability and address discovery mechanisms.

### 8.3 BareMetalInstanceType network-port configuration not populated

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** If BareMetalInstanceType resources do not have structured `network_ports` configuration with a `fabric` port, interface determination will fail. Ensure the catalog resources are populated before cluster networking goes live.

### 8.4 IP address pool configuration for API and ingress endpoints

- **Owner:** Platform team / Cloud Infrastructure Admin
- **Mitigation:** The cluster provisioning system needs IP address pools configured for the subnet so it can allocate addresses for API server and ingress endpoints. Clarify whether this is created when the subnet is created or during cluster provisioning.

## 9. Open Questions

### ~~9.1 How does the system select hosts?~~ — Resolved

Resolved: The operator queries Agent CRs directly via K8s API, selecting by BareMetalInstanceType-derived inventory requirements and availability. This is the current approach but may evolve as the agent management model changes.

### ~~9.2 How is host network state configuration managed?~~ — Resolved

Resolved: DHCP handles all host-side networking. The host receives IP, gateway, prefix, and DNS from the fabric's DHCP server. No static configuration or NMState needed.

### ~~9.3 How are IP address pools for cluster endpoints configured?~~ — Resolved

Resolved: The system creates IP address pools for cluster endpoint allocation at subnet creation time, reserving a sub-range of the subnet CIDR. The DHCP assignment range excludes this sub-range to prevent overlap.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: respond @ prd 0.11.3 - 2bd6607, workspace main @ 2293f9140

> Context changed between revise and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","manual-edit","revise","respond"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
