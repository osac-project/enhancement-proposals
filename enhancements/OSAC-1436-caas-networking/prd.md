# CaaS Networking — Unified API with Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support only Create, List/Get, and Delete, and the
Cluster network attachment field is create-time-only; changes require delete
and recreate.

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

### 2.0 Current network attachment constraint

CaaS supports one `network_attachment` per Cluster. That attachment supplies
the subnet for the entire cluster; node sets do not receive separate tenant
attachments. Multi-NIC cluster-node networking is future scope.

### 2.1 Goals

- A tenant can create a cluster with explicit network configuration, specifying which subnet and security groups to use for cluster nodes
- A cluster uses a single network attachment — one subnet for all node sets. The system automatically determines which physical interface to use for each node set based on its BareMetalInstanceType
- Tenants can request automatic external IP attachment for cluster API server and ingress endpoints with `--external-ip-attachment`, without pre-creating external IP resources
- When network configuration is omitted, the system applies the tenant's default subnet and security group
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

- As a Tenant User, I want to create a cluster with explicit network configuration so that I can place it on a specific subnet with specific security group rules
- As a Tenant User, I want my cluster's node sets to automatically use the correct physical interface based on their BareMetalInstanceType so that network connectivity is configured without manual interface specification
- As a Tenant User, I want to create a cluster with `--external-ip-attachment` so that the system provisions external IPs for both the API server and ingress and the cluster is externally reachable in a single API call
- As a Tenant User, I want to create a cluster without specifying network configuration and have it placed on my default subnet with my default security groups
- As a Tenant User, I want to see my cluster's API server and ingress endpoint addresses in the cluster status so that I can access the cluster
- As a Tenant User, I want auto-provisioned networking resources to be automatically cleaned up when I delete my cluster so that I do not accumulate orphaned resources

### Tenant Admin Stories

- As a Tenant Admin, I want to place multiple clusters in the same virtual network so that they can communicate privately with each other and with my VMs
- As a Tenant Admin, I want to isolate clusters in separate virtual networks so that I can enforce network boundaries between different projects or teams

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define structured network-port metadata for BareMetalInstanceTypes so that the system can automatically configure network connectivity when provisioning clusters

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether cluster hosts were successfully selected and network connectivity configured so I can troubleshoot provisioning failures

## 4. Requirements

### 4.1 Functional Requirements

#### Network Configuration

- **FR-1:** Cluster creation supports the singular `network_attachment` field. The attachment may omit its subnet or omit or explicitly supply an empty security-group list; the complete resolved attachment is immutable after creation. The default SecurityGroup is used only when the resolved Subnet belongs to the tenant's default VirtualNetwork; otherwise the caller must provide SecurityGroups from the resolved Subnet's VirtualNetwork. The attachment applies to the entire cluster — all node sets share the same subnet. The system determines which physical network interface to use for each node set from its BareMetalInstanceType. [User]

#### Optional Network Configuration with Defaults

- **FR-2:** The network configuration on cluster creation is optional. When the attachment is omitted or empty, the system applies the tenant's default subnet and default security group. When a partial attachment is supplied, only missing subnet or security-group fields are defaulted; an explicitly empty security-group list is treated as missing; supplied values are preserved. The default SecurityGroup is used only when the resolved subnet belongs to the tenant's default VirtualNetwork; otherwise the caller must provide SecurityGroups from the resolved subnet's VirtualNetwork. The resolved configuration is stored so the cluster is self-describing after creation. [User]

#### Auto External IP

- **FR-3:** Cluster creation supports `--external-ip-attachment`. The request synchronously selects pools with capacity and persists two Pending, auto-provisioned ExternalIP requests (API and ingress), reserving two logical pool-capacity slots. Provider address allocation is asynchronous and does not block ClusterOrder provisioning. An ExternalIPAttachment is created for each endpoint only after that ExternalIP has a real backend allocation and the Cluster is Ready with the corresponding endpoint. The ExternalIPs and resulting ExternalIPAttachments are labeled as auto-provisioned. [User]

#### Endpoint Discovery

- **FR-4:** Cluster status exposes API server and ingress endpoint addresses. The system discovers these addresses during cluster provisioning and makes them available in the cluster status. [User]

#### External IP Activation

- **FR-5:** The system creates each ExternalIPAttachment only after its ExternalIP has a confirmed backend allocation and the Cluster target is Ready with the corresponding API or ingress endpoint. It then configures inbound routing and activates the attachment. If either prerequisite is unmet, no attachment is created. [User]

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

- **FR-11:** Auto-provisioned networking resources (external IPs, external IP attachments) are labeled as auto-provisioned. When a cluster is deleted, the system cleans up auto-provisioned resources in reverse order: external IP attachments first, then external IPs. Manually created resources are not cleaned up. Default networking resources (virtual networks, subnets, security groups, NATGateways) are not cleaned up as they are tenant-scoped and shared across resources. [User]

#### Provider Networking Disabled

- **FR-12:** A Cloud Provider Admin can disable OSAC network-provider operations through the shared Helm setting or Enclave Wizard checkbox available during installation or upgrade while keeping networking APIs, their authorization/validation/defaulting, and ordinary cluster provisioning available. The setting takes effect through rollout and is not an OSAC console live toggle. Cluster and worker-host provisioning/deletion remain available when baseline platform/provisioning connectivity supports control-plane and assisted-service access, DNS/address services, and required installation/image dependencies. Bare-metal workers remain on provisioning connectivity; OSAC supplies neither tenant port movement/routing nor public ExternalIP routing, and does not discover a tenant DHCP address for them. Endpoint addresses are reported only when actually supplied by the working baseline environment. After logical prerequisites pass, non-allocating Networking API resources report `Ready=True` with reason `ProvisioningDisabled`; unmet prerequisites remain waiting. An ExternalIP without confirmed backend allocation reports `Pending`/`Progressing`, an empty address, and `Ready=False`/`ProvisioningDisabled`; its logical pool-capacity reservation remains held until deletion and no ExternalIPAttachment is created. A confirmed real allocation retains its address and `Allocated` state but reports `Progressing` and `Ready=False`/`ProvisioningDisabled` while networking is disabled. The two automatic ExternalIP requests do not block cluster provisioning; their attachments are created only after real allocation and Cluster Ready. Incomplete worker BMI network phases skipped after disablement report `Unknown`/`ProvisioningDisabled`, while confirmed earlier phases retain `True`; progress treats a phase as complete for that skip only when the reason matches exactly. Existing network operations are cancelled and awaited before skipped/deleted completion; logical cleanup preserves dependency order and may leave provider resources for manual/provider-side cleanup. A host moved to a tenant network before disablement is not moved back on delete; manual/provider restoration may be needed for Ironic cleaning. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Pool selection and capacity validation for automatic ExternalIP requests complete synchronously in the cluster creation flow. Backend address allocation and endpoint discovery continue asynchronously; confirmed endpoint addresses are written to cluster status as the provider supplies them. Automatic ExternalIP requests do not block ClusterOrder provisioning.

Connectivity, allocation, provider policy enforcement/cleanup, and related
provider-work timing requirements described here apply when provider networking is
enabled. Disabled mode retains API prerequisites and explicitly identifies
skipped provider work; it does not claim those provider outcomes. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a cluster with network configuration specifying a subnet and security groups, and the cluster nodes are provisioned on the specified subnet
- [ ] A Tenant User can create a cluster with a single network attachment and multiple node sets, and all node sets are provisioned on the same subnet with the appropriate physical interface automatically selected from each node set's BareMetalInstanceType
- [ ] A Tenant User can create a cluster with `--external-ip-attachment` and no explicit network configuration — the cluster is created on the default subnet with auto-provisioned external IPs for both API and ingress
- [ ] Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- [ ] Each auto-created ExternalIPAttachment is created only after the ExternalIP is Allocated and the Cluster target is Ready with its endpoint address; inbound routing is then configured
- [ ] The system selects hosts and configures network connectivity before cluster provisioning begins
- [ ] Auto-created external IPs and external IP attachments are labeled as auto-provisioned and visible in list views
- [ ] Deleting a cluster with auto-provisioned resources causes the auto-created external IPs and external IP attachments to be cleaned up
- [ ] The system determines which physical network interface to use based on each node set's BareMetalInstanceType `network_ports` configuration

- [ ] With the shared setting disabled after rollout, an API-valid ordinary workload request still provisions using the stated platform/provisioning connectivity
- [ ] Core ClusterOrder install/delete jobs remain active while tenant VIP allocation, IPAM, public DNS/routing, and provider cleanup are absent when networking is disabled
- [ ] Disabled CaaS reports endpoint addresses only when supplied by the baseline environment; it does not create tenant-pool-backed LoadBalancer Services or fabricate VIPs
- [ ] Non-allocating Networking API resources report `Ready=True`; incomplete worker BMI network phases skipped after disablement report `Unknown`/`ProvisioningDisabled`, while confirmed earlier phases retain `True`; ClusterOrder Ready does not claim tenant/public routing, ExternalIP allocation, or provider cleanup
- [ ] With networking disabled, automatic ExternalIP requests remain Pending without an address and do not block ClusterOrder provisioning; no ExternalIPAttachment is created until a real allocation and Ready Cluster target exist
- [ ] Default SecurityGroup resolution, invalid-reference/non-ready-dependency rejection, tenant boundaries, and existing interface/cardinality/immutability rules remain active
- [ ] Networking specification and metadata updates, including SecurityGroup rules, remain rejected in both modes
- [ ] Deletion awaits active network-operation cancellation and preserves dependency/cascade order without provider cleanup; ordinary workload deletion stays active and does not synthesize a `NetworkOffboardComplete` condition for a skipped port move
- [ ] Unallocated ExternalIPs expose no fabricated address and do not bypass Allocated + workload Ready gates for automatic attachment creation [User]

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created. If defaults are not configured, creating a cluster without explicit network configuration fails with a clear error.
- The deployment's network infrastructure is configured to support virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways, and network connectivity management.
- BareMetalInstanceTypes have structured `network_ports` configuration. The system uses the first `fabric` port for each node set when no interface is supplied by the CaaS flow.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)

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
Final: revise @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (57 behind origin/main)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"1f3b63b82","source_repo_branch":"main","commits_behind_main":57,"commits_ahead_main":0,"main_ref":"main","phases":["revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
