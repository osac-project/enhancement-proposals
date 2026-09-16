# VMaaS Networking — Single-Interface VMs and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-09-10 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared networking resources and operation contract; the [Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology) defines the IPv4 topology, and its [deployment support boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary) requires connected deployments and excludes air-gapped deployments. This document defines the VMaaS-specific requirements and user stories.

VMaaS follows the shared [strict dependency-ready creation
contract](/enhancements/OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation): resolved networking references and VM placement prerequisites must be Ready before the VM is persisted. Only OSAC-owned automatic ExternalIP children may be created Pending after a Ready pool and capacity validation.

## 1. Problem Statement

VMaaS retains a list-shaped attachment API while the currently supported VM
contract is one interface or none at request time.
Creating a VM with external access requires manual IP allocation and NAT
configuration, forcing tenants to understand inbound and outbound routing
before provisioning their first reachable VM. The default networking
experience varies across resource types — some resources have simplified
creation flows while VMs require explicit networking details on every create.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with zero or one list-shaped network attachment; a single attachment is implicitly primary
- A tenant can create a VM with `--external-ip-attachment` and have the system allocate an external IP and attach it automatically for inbound access
- A tenant can create a VM without specifying networking details — the system uses the tenant's default Subnet and default SecurityGroup, and inherits the effective NetworkACL from the Subnet; an unfinished provider adapter may complete its normal operation as a successful no-op

### 2.2 Non-Goals

- Cluster or bare-metal server networking (this PRD covers VMs only; clusters and bare-metal servers are addressed in separate enhancements)
- Multi-interface VMs and multiple network interfaces for bare-metal servers are unsupported in the current contracts

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment using a list-shaped field, so that the API can retain a stable list shape while supporting only one interface today
- As a Tenant User, I want the single network interface to be implicitly primary, so that it provides the VM's default gateway and DNS configuration
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that the VM is externally reachable without manually allocating an IP
- As a Tenant User, I want to create a VM without specifying network details, so that the system uses my default Subnet, default SecurityGroup, and effective default ACL policy and I can get started quickly
- As a Tenant User, I want clear error messages when I try to create a VM in a deployment that only supports bare-metal servers, so that I understand the limitation and can choose a different deployment

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect the default Subnet, default SecurityGroup, and effective NetworkACL when VMs are created without explicit network configuration
- As a Tenant Admin, I want to see which Subnet and SecurityGroups each VM uses and the effective NetworkACL inherited from that Subnet, so I can audit my organization's network topology

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure which deployments support VM provisioning, so that VM creation is rejected with a clear error in BM-only deployments

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into auto-provisioned networking resources (external IPs), so I can monitor capacity and troubleshoot connectivity issues

## 4. Requirements

### 4.1 Functional Requirements

#### Single-Interface VMs

- **FR-1:** The `network_attachments` list of `ComputeNetworkAttachment` values accepts zero or one entry. A request with more than one entry is rejected. [User]
- **FR-2:** When the list contains one attachment, omission or `primary: true` makes it primary; explicit `primary: false` is rejected. Multi-interface primary selection is unsupported. [User]

#### Optional Network Configuration with Defaults

- **FR-3:** Network configuration is optional when creating a VM. When the
  attachment list is omitted or empty, the system uses the tenant default
  Subnet and default SecurityGroup. NetworkACL membership is
  inherited from the Subnet and is not a workload attachment field. When an
  attachment omits its subnet or SecurityGroup list, only those missing fields
  are defaulted; supplied fields are preserved. Traffic must pass both the
  SecurityGroup and effective NetworkACL layers. The tenant default
  SecurityGroup is used only with the tenant default VirtualNetwork; a
  non-default Subnet without a compatible explicit group is rejected. A
  selected Subnet without a Ready effective ACL is rejected until an ACL is
  associated. [User]

#### Auto External IP

- **FR-4:** VMs support `--external-ip-attachment`. When specified, the
  system auto-selects the IPv4 ExternalIPPool with the most available
  capacity, reserves capacity, and creates a Pending ExternalIP and
  ExternalIPAttachment for the VM's single network attachment. Allocation by
  every selected manager, VM IP discovery, DNAT programming, and activation are
  asynchronous; the ExternalIP and attachment are cleaned up when the VM is
  deleted. Default networking resources (virtual networks, subnets, SecurityGroup, NetworkACL,
  NATGateway) are not cleaned up as they are tenant-scoped and shared
  across resources. [User]

#### IP Address Discovery

- **FR-5:** The allocated IP address for the single network attachment is visible in the VM status after provisioning completes. When an external IP is attached to a VM, inbound traffic to the external IP is routed to that attachment's IP. [User]

#### Deployment Validation

- **FR-6:** When a VM is created, the platform validates that the target deployment supports virtualization. If the deployment only supports bare-metal servers, the create request fails with a clear error message explaining the limitation. [User]

#### API Shape Change

- **FR-7:** Before release, the VM networking field changes from the shared `NetworkAttachment` message to the resource-specific `ComputeNetworkAttachment` message. Only `network_attachments` is accepted; no old/new dual-field compatibility or conversion period is provided because there are no users or persisted resources yet. [User]

- **FR-8:** The complete resolved network attachment list on a ComputeInstance,
  including every Subnet and `primary` value, is immutable
  after creation. Update and patch requests for these fields are rejected;
  changing network configuration requires deleting and recreating the VM.
  Standard metadata and non-network VM fields remain governed by their own
  contracts. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Pool capacity validation and creation of Pending ExternalIP and
  ExternalIPAttachment records complete synchronously within the create request.
  Selected-manager allocation,
  VM IP discovery, DNAT programming, and the transition to Ready are
  asynchronous. The ExternalIP transitions `Pending -> Allocated`; the
  ExternalIPAttachment transitions `Pending -> Ready` only after the VM
  attachment IP is available and DNAT succeeds. If no pool has available
  capacity, the create request fails atomically with a clear error. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with zero or one `--network-attachment` value while the API field remains list-shaped
- [ ] The CLI maps the single `--network-attachment` value to `spec.network_attachments` containing a `ComputeNetworkAttachment`, rejects a second value, and never exposes `interface` or multi-NIC input
- [ ] The CLI maps `--external-ip-attachment` to `auto_external_ip_attachment: true`; omission maps to false and updates are rejected
- [ ] Creating a VM with more than one network attachment returns a single-interface validation error
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no explicit network configuration — the VM is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] Creating a VM in a bare-metal-only deployment returns an error with a clear message
- [ ] A single-interface VM is provisioned with its attachment operational and providing the default gateway
- [ ] VM status shows the allocated IP address for the single network attachment after provisioning completes
- [ ] External IP attachment with a VM target routes inbound traffic to the VM's attachment IP
- [ ] Auto-created external IPs and attachments are visible in list views with a `osac.openshift.io/auto-created: "true"` marker and exact immutable ComputeInstance owner relationship
- [ ] Deleting a VM with auto-provisioned external IP causes the auto-created IP and attachment to be cleaned up automatically
- [ ] The VM API accepts only the resource-specific `network_attachments` field and rejects the replaced shared attachment format
- [ ] A VM attachment may include zero or more unique typed SecurityGroup
  references; omitted groups receive the tenant default only when the resolved
  Subnet is in the tenant default VirtualNetwork, while every explicit group
  is Ready, same-tenant, and in the attachment's VN. A non-default-VN Subnet
  without a compatible explicit group is rejected
- [ ] A tenant-created SecurityGroup has at least one allow-only rule; the
  default SecurityGroup may be empty and means deny. A SecurityGroup action
  field or deny rule is rejected
- [ ] Creating a VM with `primary: false` on its sole attachment returns a single-interface validation error
- [ ] Updating or patching a VM's network attachment list or any attachment field is rejected; changing it requires delete and recreate under the [unified networking operation contract](/enhancements/OSAC-1433-unified-networking/prd.md#network-operation-contract)

## 6. Assumptions

- The tenant has default networking resources (VirtualNetwork and Subnet)
  pre-created by the platform (see Default Networking PRD), plus a default
  SecurityGroup and NetworkACL from the complete manager profile. If the
  required defaults are not
  configured, creating a VM without explicit network configuration fails with
  a clear error. Kubernetes NetworkPolicy alone is not a substitute for
  either policy contract.
- The target deployment supports virtualization. Bare-metal-only deployments do not support VMs.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, SecurityGroups, network ACLs, external IPs, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default subnet, SecurityGroup, and NetworkACL selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **OSAC-1712 (automatic pool selection)** — the auto external IP pool selection reuses the identical algorithm: pick the IPv4 pool with the most available capacity
- **OSAC-1511 or OSAC-1717** — a virtualization platform integration must exist for the platform to provision overlay networks on hosting clusters
- **OSAC-1457, OSAC-1458, OSAC-1460** — core provisioning infrastructure (in progress)
- **OSAC-1459** — multi-job tracking (new, required for subnet provisioning to trigger multiple backend jobs)

## 8. Risks

### 8.1 Virtualization platform integration blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** OSAC-1511 and OSAC-1717 are both in spike/blocked state. If neither lands, the manager's VM AAP operation uses the approved development no-op until a virtualization platform integration exists.

### 8.2 Multi-target dispatch tracking is unavailable

- **Owner:** Platform team
- **Mitigation:** OSAC-1459 is a prerequisite for per-resource dispatch to
  multiple manager targets. Until it is available, the combined deployment
  remains provider-blocked or routes the unfinished operation through the
  approved internal no-op; it never silently reduces a complete plan to one
  backend.

### 8.3 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### ~~9.1 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.
