# VMaaS Networking — Multi-Interface VMs and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements; this document defines the service-specific requirements and user stories.

## 1. Problem Statement

Tenants cannot create VMs with multiple network interfaces or designate which interface provides the default gateway. Creating a VM with external access requires manual IP allocation and NAT configuration, forcing tenants to understand inbound and outbound routing before provisioning their first reachable VM. The default networking experience varies across resource types — some resources have simplified creation flows while VMs require explicit networking details on every create.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with multiple network interfaces on different subnets, designating one as primary
- A tenant can create a VM with `--external-ip-attachment` and have the system allocate an external IP and attach it automatically for inbound access
- A tenant can create a VM without specifying networking details — the system uses the tenant's default subnet and security group
- The platform prevents VM creation in regions that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (this PRD covers VMs only; clusters and bare-metal servers are addressed in separate enhancements)
- Multiple network interfaces for bare-metal servers (bare-metal multi-interface support is out of scope)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with multiple network interfaces, so that the VM can communicate on multiple subnets
- As a Tenant User, I want to designate one network interface as primary, so that it provides the VM's default gateway and DNS configuration
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that the VM is externally reachable without manually allocating an IP
- As a Tenant User, I want to create a VM without specifying network details, so that the system uses my default subnet and security group and I can get started quickly
- As a Tenant User, I want clear error messages when I try to create a VM in a region that only supports bare-metal servers, so that I understand the limitation and can choose a different region

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect and modify the default networking resources (subnet, security group) used when VMs are created without explicit network configuration
- As a Tenant Admin, I want to see which subnet and security groups each VM is attached to, and the IP address allocated to each interface, so I can audit my organization's network topology

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure which regions support VM provisioning, so that VM creation is rejected with a clear error in BM-only regions

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into auto-provisioned networking resources (external IPs), so I can monitor capacity and troubleshoot connectivity issues

## 4. Requirements

### 4.1 Functional Requirements

#### Multi-Interface VMs

- **FR-1:** A tenant can create a VM with multiple network interfaces on different subnets, designating one as primary. The primary interface provides the default gateway, DNS, and is the target for inbound external access and outbound NAT. Non-primary interfaces receive IP addresses but do not provide a default gateway. [User]
- **FR-2:** When a VM has multiple network interfaces, exactly one must be designated as primary. When a VM has only one network interface, it is implicitly primary. [User]

#### Optional Network Configuration with Defaults

- **FR-3:** Network configuration is optional when creating a VM. When omitted, the system uses the tenant's default subnet and default security group (see Default Networking PRD). The resolved configuration is stored with the VM so the VM is self-describing after creation. [User]

#### Auto External IP

- **FR-4:** VMs support `--external-ip-attachment`. When specified, the system auto-selects the external IP pool with the most available capacity, allocates an IP, and attaches it to the VM's primary interface for inbound access. The IP and attachment are automatically cleaned up when the VM is deleted. Default networking resources (virtual networks, subnets, security groups, NATGateway) are not cleaned up as they are tenant-scoped and shared across resources. [User]

#### IP Address Discovery

- **FR-5:** The allocated IP address for each network attachment is visible in the VM status after provisioning completes. When an external IP is attached to a VM, inbound traffic to the external IP is routed to the VM's primary attachment IP. [User]

#### Region Validation

- **FR-6:** When a VM is created, the platform validates that the target region supports virtualization. If the region only supports bare-metal servers, the create request fails with a clear error message explaining the limitation. [User]

#### Backward Compatibility

- **FR-7:** Existing VMs continue to work without changes. The platform accepts both old and new network configuration formats during a transition period. If both formats are provided, the create request fails with an error. If the old format is provided alone, it is converted to the new format automatically. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Auto external IP allocation completes synchronously within the create request. If no pool has available capacity, the create request fails with a clear error. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with multiple `--network-attachment` flags and designate one as `--primary`
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no explicit network configuration — the VM is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] Creating a VM in a bare-metal-only region returns an error with a clear message
- [ ] A multi-interface VM is provisioned with all interfaces operational, with the primary interface providing the default gateway
- [ ] VM status shows the allocated IP address for each network attachment after provisioning completes
- [ ] External IP attachment with a VM target routes inbound traffic to the VM's primary attachment IP
- [ ] Auto-created external IPs and attachments are visible in list views with a label indicating they were auto-provisioned
- [ ] Deleting a VM with auto-provisioned external IP causes the auto-created IP and attachment to be cleaned up automatically
- [ ] Creating a VM using the old network configuration format succeeds and is internally converted to the new format
- [ ] Creating a VM with both old and new configuration formats returns an error

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created by the platform (see Default Networking PRD). If defaults are not configured, creating a VM without explicit network configuration fails with a clear error.
- The target region supports virtualization. Bare-metal-only regions do not support VMs.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, NAT gateways) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/default-networking)
- **OSAC-1712 (automatic pool selection)** — the auto external IP pool selection reuses the identical algorithm: pick the pool with the most available capacity matching the IP family
- **OSAC-1511 or OSAC-1717** — a virtualization platform integration must exist for the platform to provision overlay networks on hosting clusters
- **OSAC-1457, OSAC-1458, OSAC-1460** — core provisioning infrastructure (in progress)
- **OSAC-1459** — multi-job tracking (new, required for subnet provisioning to trigger multiple backend jobs)

## 8. Risks

### 8.1 Virtualization platform integration blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** OSAC-1511 and OSAC-1717 are both in spike/blocked state. If neither lands, VM networking cannot function. Prioritize unblocking one of these dependencies or accept that VMs remain unavailable until a virtualization platform integration exists.

### 8.2 Multi-job tracking not implemented

- **Owner:** Platform team
- **Mitigation:** OSAC-1459 is a prerequisite for subnet provisioning to trigger multiple backend jobs. If not implemented, subnet provisioning can only call one backend system — defer multi-backend support or accept single-backend-only subnet provisioning.

### 8.3 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### ~~9.1 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.
