# CaaS Networking — Unified API with Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1436 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements; this document defines the service-specific requirements and user stories.

## 1. Problem Statement

Cluster provisioning has no networking configuration. Tenants cannot choose which subnet their cluster nodes use, cannot place two clusters in the same virtual network, and cannot isolate them in separate networks. All clusters are placed on a single deployment-wide networking backend with zero tenant control. Cluster networking is completely divergent from VM and bare-metal server workflows, requiring separate knowledge and tools.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a cluster with explicit network configuration, specifying which subnet and security groups to use for cluster nodes
- A cluster uses a single network attachment — one subnet for all node sets. The system automatically determines which physical interface to use for each node set based on the host type configuration
- Tenants can request automatic external IP attachment for cluster API server and ingress endpoints with `--external-ip-attachment`, without pre-creating external IP resources
- When network configuration is omitted, the system applies the tenant's default subnet and security group
- Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- The system automatically selects suitable bare-metal hosts and configures network connectivity before cluster provisioning begins
- Auto-provisioned external IPs and external IP attachments are cleaned up when the cluster is deleted
- Bare-metal host types provide structured interface information that the system uses to configure network connectivity

### 2.2 Non-Goals

- VM-based cluster node sets (deferred — bare-metal only for initial release)
- DNS API for cluster endpoints (DNS record creation remains template-based until DNS API is implemented)
- Per-node-set subnet placement (all node sets share the cluster's single network attachment)
- Multi-NIC cluster nodes (one attachment per cluster; the system automatically determines which physical interface to use for each node set based on its host type)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a cluster with explicit network configuration so that I can place it on a specific subnet with specific security group rules
- As a Tenant User, I want my cluster's node sets to automatically use the correct physical interface based on their host type so that network connectivity is configured without manual interface specification
- As a Tenant User, I want to create a cluster with `--external-ip-attachment` so that the system provisions external IPs for both the API server and ingress and the cluster is externally reachable in a single API call
- As a Tenant User, I want to create a cluster without specifying network configuration and have it placed on my default subnet with my default security groups
- As a Tenant User, I want to see my cluster's API server and ingress endpoint addresses in the cluster status so that I can access the cluster
- As a Tenant User, I want auto-provisioned networking resources to be automatically cleaned up when I delete my cluster so that I do not accumulate orphaned resources

### Tenant Admin Stories

- As a Tenant Admin, I want to place multiple clusters in the same virtual network so that they can communicate privately with each other and with my VMs
- As a Tenant Admin, I want to isolate clusters in separate virtual networks so that I can enforce network boundaries between different projects or teams

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define structured network interface metadata for bare-metal host types so that the system can automatically configure network connectivity when provisioning clusters

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into whether cluster hosts were successfully selected and network connectivity configured so I can troubleshoot provisioning failures

## 4. Requirements

### 4.1 Functional Requirements

#### Network Configuration

- **FR-1:** Cluster creation supports a single network attachment configuration specifying a subnet (required, immutable) and security groups (mutable). The attachment applies to the entire cluster — all node sets share the same subnet. The system determines which physical network interface to use for each node set based on its host type's interface configuration. [User]

#### Optional Network Configuration with Defaults

- **FR-2:** The network configuration on cluster creation is optional. When omitted, the system applies the tenant's default subnet and default security group. The resolved configuration is stored so the cluster is self-describing after creation. [User]

#### Auto External IP

- **FR-3:** Cluster creation supports `--external-ip-attachment`. When enabled, the system allocates external IPs for both the API server and ingress from available IP pools before provisioning begins. External IPs and their attachments are labeled as auto-provisioned. The attachments are activated once the cluster's API server and ingress endpoints are available. [User]

#### Endpoint Discovery

- **FR-4:** Cluster status exposes API server and ingress endpoint addresses. The system discovers these addresses during cluster provisioning and makes them available in the cluster status. [User]

#### External IP Activation

- **FR-5:** When automatic external IP allocation is enabled, the system creates external IP attachments before provisioning begins. After the cluster's API server and/or ingress endpoints are available, the system configures inbound routing from the external IPs to the endpoints and activates the attachments. [User]

#### Host Selection and Network Configuration

- **FR-6:** The system selects and reserves suitable bare-metal hosts for each node set before cluster provisioning begins, based on the node set's host type and availability. Selected hosts are reserved for the cluster to prevent allocation conflicts. [User]

#### Network Connectivity Setup

- **FR-7:** The system configures network connectivity for selected hosts before cluster provisioning begins. For each host, the system configures the appropriate network interface to connect to the specified subnet. Network connectivity must be ready before provisioning proceeds. [User]

#### Cluster Provisioning

- **FR-8:** Cluster provisioning creates the cluster using pre-selected hosts with pre-configured network connectivity. The provisioning process allocates IP addresses for the API server and ingress endpoints, performs DNS record creation, and makes the endpoint addresses available in cluster status. [User]

#### Host Type Network Interfaces

- **FR-9:** Bare-metal host types include structured network interface information (name, role, description). The system automatically determines which physical interface to use for each node set based on the host type's interface configuration. [User]

#### Bare-Metal Only

- **FR-10:** Cluster node sets are bare-metal only for the initial release. VM-based cluster node sets are architecturally supported but deferred. [User]

#### Auto-Provisioned Resource Cleanup

- **FR-11:** Auto-provisioned networking resources (external IPs, external IP attachments) are labeled as auto-provisioned. When a cluster is deleted, the system cleans up auto-provisioned resources in reverse order: external IP attachments first, then external IPs. Manually created resources are not cleaned up. Default networking resources (virtual networks, subnets, security groups, NATGateways) are not cleaned up as they are tenant-scoped and shared across resources. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Automatic external IP allocation and endpoint discovery complete synchronously within the cluster creation flow. Endpoint addresses are available in cluster status during provisioning, not minutes later.

## 5. Acceptance Criteria

- [ ] A Tenant User can create a cluster with network configuration specifying a subnet and security groups, and the cluster nodes are provisioned on the specified subnet
- [ ] A Tenant User can create a cluster with a single network attachment and multiple node sets, and all node sets are provisioned on the same subnet with the appropriate physical interface automatically selected based on each node set's host type
- [ ] A Tenant User can create a cluster with `--external-ip-attachment` and no explicit network configuration — the cluster is created on the default subnet with auto-provisioned external IPs for both API and ingress
- [ ] Cluster status exposes API server and ingress endpoint addresses after provisioning completes
- [ ] Auto-created external IP attachments activate after endpoint addresses are available and inbound routing is configured
- [ ] The system selects hosts and configures network connectivity before cluster provisioning begins
- [ ] Auto-created external IPs and external IP attachments are labeled as auto-provisioned and visible in list views
- [ ] Deleting a cluster with auto-provisioned resources causes the auto-created external IPs and external IP attachments to be cleaned up
- [ ] The system determines which physical network interface to use based on the host type's interface configuration

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created. If defaults are not configured, creating a cluster without explicit network configuration fails with a clear error.
- The target region's network infrastructure is configured to support virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways, and network connectivity management.
- Bare-metal host types have structured network interface configuration. The system uses this to determine which interface to configure for each subnet.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, external IP attachments, NAT gateways) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/default-networking)

## 8. Risks

### 8.1 Host selection logic complexity

- **Owner:** Platform team
- **Mitigation:** Host selection logic must account for host type matching, availability, and labels. If not implemented correctly, cluster provisioning cannot proceed. Thorough testing required.

### 8.2 Endpoint discovery delay or failure

- **Owner:** Platform team
- **Mitigation:** If endpoint addresses are not discovered correctly, they will not appear in cluster status, and external IP attachments will not activate. Monitor endpoint discovery reliability and address discovery mechanisms.

### 8.3 Host type network interface configuration not populated

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** If host type resources do not have structured network interface configuration, interface determination will fail. Ensure host type resources are populated with interface metadata before cluster networking goes live.

### 8.4 IP address pool configuration for API and ingress endpoints

- **Owner:** Platform team / Cloud Infrastructure Admin
- **Mitigation:** The cluster provisioning system needs IP address pools configured for the subnet so it can allocate addresses for API server and ingress endpoints. Clarify whether this is created when the subnet is created or during cluster provisioning.

## 9. Open Questions

### ~~9.1 How does the system select hosts?~~ — Resolved

Resolved: The operator queries Agent CRs directly via K8s API, selecting by host type and availability. This is the current approach but may evolve as the agent management model changes.

### ~~9.2 How is host network state configuration managed?~~ — Resolved

Resolved: DHCP handles all host-side networking. The host receives IP, gateway, prefix, and DNS from the fabric's DHCP server. No static configuration or NMState needed.

### ~~9.3 How are IP address pools for cluster endpoints configured?~~ — Resolved

Resolved: The k8s_manager creates MetalLB IPAddressPool at subnet creation time with a reserved sub-range of the subnet CIDR. The DHCP server excludes this range to prevent overlap.
