# VMaaS Networking — Single Attachment VMs and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support only Create, List/Get, and Delete, and the VM
network attachment fields are create-time-only; changes require delete and
recreate.

VMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

Provider-dependent connectivity, allocation, and cleanup in this document
describe the enabled mode. FR-8 defines the shared installation/upgrade
setting and disabled experience. Networking APIs retain the published default
SecurityGroup selection, immutability, validation, and dependency rules in
both modes. [User]

## 1. Problem Statement

Creating a VM with external access requires manual IP allocation and NAT configuration, forcing tenants to understand inbound and outbound routing before provisioning their first reachable VM. The default networking experience varies across resource types — some resources have simplified creation flows while VMs require explicit networking details on every create. VMaaS currently supports at most one network attachment per VM; the plural API field is retained for compatibility.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with zero or one network attachment; the sole attachment is the primary/default route
- A tenant can create a VM with `--external-ip-attachment` and have the system allocate an external IP and attach it automatically for inbound access
- A tenant can create a VM without specifying networking details — the system uses the tenant's default subnet and security group
- The platform prevents VM creation in deployments that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (this PRD covers VMs only; clusters and bare-metal servers are addressed in separate enhancements)
- Multi-NIC VM networking (future scope; the repeated field does not enable it)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment, so that it receives connectivity on the selected subnet
- As a Tenant User, I want the sole network attachment to provide the VM's default gateway and DNS configuration without requiring a second API field
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that the VM is externally reachable without manually allocating an IP
- As a Tenant User, I want to create a VM without specifying network details, so that the system uses my default subnet and security group and I can get started quickly
- As a Tenant User, I want clear error messages when I try to create a VM in a deployment that only supports bare-metal servers, so that I understand the limitation and can choose a different deployment

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect the default networking resources (subnet, security group) used when VMs are created without explicit network configuration and create replacements when different settings are needed
- As a Tenant Admin, I want to see which subnet and security groups each VM is attached to, and the IP address allocated to each interface, so I can audit my organization's network topology

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to configure which deployments support VM provisioning, so that VM creation is rejected with a clear error in BM-only deployments

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want visibility into auto-provisioned networking resources (external IPs), so I can monitor capacity and troubleshoot connectivity issues

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment Constraint

- **FR-1:** A tenant can create a VM with zero or one network attachment. The sole attachment provides the default gateway, DNS, and inbound external access target; outbound SNAT, when configured, is provided by the VirtualNetwork's NATGateway. The repeated `network_attachments` field is retained for API compatibility, but a request with more than one entry is rejected. [User]
- **FR-2:** When one network attachment is present, it is implicitly primary and provides the default route. VMaaS does not expose a `primary` field. [User]

#### Optional Network Configuration with Defaults

- **FR-3:** Network configuration is optional when creating a VM. When the attachment list is omitted or empty, the system uses the tenant's default subnet and default security group (see Default Networking PRD). When a single attachment is supplied with a missing subnet, or with a missing or explicitly empty security-group list, only the missing field is defaulted; the default security group is used only when the resolved subnet belongs to the tenant's default VirtualNetwork, otherwise the caller must provide security groups from the resolved subnet's VirtualNetwork. Supplied values are preserved. The resolved configuration is stored with the VM so the VM is self-describing after creation. [User]

#### Auto External IP

- **FR-4:** VMs support `--external-ip-attachment`. When specified, the system synchronously selects and capacity-checks an ExternalIPPool, creates a Pending ExternalIP request that reserves one pool-capacity slot, and requests an address from the provider backend asynchronously. After a real allocation and VM Ready are confirmed, it creates an ExternalIPAttachment to the VM's primary interface for inbound access. The IP and any attachment are automatically cleaned up when the VM is deleted. Default networking resources (VirtualNetworks, Subnets, SecurityGroups, and NATGateways) are not cleaned up as they are tenant-scoped and shared across resources. [User]

#### IP Address Discovery

- **FR-5:** The allocated IP address for the network attachment is visible in the VM status after provisioning completes. When an external IP is attached to a VM, inbound traffic to the external IP is routed to the VM's sole/primary attachment IP. [User]

#### Deployment Validation

- **FR-6:** When a VM is created, the platform validates that the target deployment supports virtualization. If the deployment only supports bare-metal servers, the create request fails with a clear error message explaining the limitation. [User]

#### API Compatibility

- **FR-7:** The existing repeated `network_attachments` field remains the only VM network-configuration field. No singular replacement field, parallel legacy field, or dual-field conversion period is introduced. [User]

#### Provider Networking Disabled

- **FR-8:** A Cloud Provider Admin can disable OSAC network-provider operations through the shared Helm setting or Enclave Wizard checkbox available during installation or upgrade while keeping networking APIs, their authorization/validation/defaulting, and ordinary VM provisioning available. The setting takes effect through rollout and is not an OSAC console live toggle. VM provisioning and deletion remain available on the platform default network. Ordinary VM creation does not require tenant Subnet or SecurityGroup provisioning; supplied network references still follow the existing API validation and precondition rules. Platform-reported VM addresses do not imply that a tenant Subnet or ExternalIP was provisioned. After logical prerequisites pass, non-allocating Networking API resources report `Ready=True`/`ProvisioningDisabled`; unmet prerequisites remain waiting. An ExternalIP without confirmed backend allocation reports `Pending`/`Progressing`, an empty address, and `Ready=False`/`ProvisioningDisabled`; a confirmed real allocation retains its address and `Allocated` state but reports `Progressing` and `Ready=False`/`ProvisioningDisabled` while networking is disabled. An automatic ExternalIP request reserves one validated pool-capacity slot, remains Pending without an address, and does not block the VM job; no attachment object is created until a real allocation and VM Ready are confirmed. Existing network operations are cancelled and awaited before skipped/deleted completion; logical cleanup preserves dependency order and may leave provider resources for manual/provider-side cleanup. [User]

An API-valid VM without tenant network attachments still provisions using
the platform default network. Disabling provider integration adds no tenant-
attachment requirement to ordinary VM provisioning. Supplied attachment fields
retain their API validation and reference checks while provider network work
is skipped. Existing API defaulting and precondition rules still apply. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** ExternalIP pool selection and capacity validation complete synchronously in the create request; provider address allocation is asynchronous. If no pool has available capacity, the request fails with a clear error. [User]

Connectivity, allocation, provider policy enforcement/cleanup, and related
provider-work timing requirements described here apply when provider networking is
enabled. Disabled mode retains API prerequisites and explicitly identifies
skipped provider work; it does not claim those provider outcomes. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with zero or one `--network-attachment` flag; a second flag is rejected with a clear maximum-one error
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no explicit network configuration — the VM is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] Creating a VM in a bare-metal-only deployment returns an error with a clear message
- [ ] A VM with one attachment is provisioned with that attachment providing the default gateway
- [ ] VM status shows the allocated IP address for the sole network attachment after provisioning completes
- [ ] External IP attachment with a VM target routes inbound traffic to the VM's primary attachment IP
- [ ] Auto-created external IPs and attachments are visible in list views with a label indicating they were auto-provisioned
- [ ] Deleting a VM with auto-provisioned external IP causes the auto-created IP and attachment to be cleaned up automatically
- [ ] Creating a VM with an omitted or empty attachment list receives the tenant defaults
- [ ] Creating a VM with a partial single attachment defaults only its missing subnet or security-group fields

- [ ] With the shared setting disabled after rollout, an API-valid ordinary workload request still provisions using the stated platform/provisioning connectivity
- [ ] Non-allocating Networking API resources report `Ready=True` with reason `ProvisioningDisabled` after logical prerequisites pass; VM Ready and platform-reported VMI addresses do not claim tenant/public routing, ExternalIP allocation, or provider cleanup
- [ ] Default SecurityGroup resolution, invalid-reference/non-ready-dependency rejection, tenant boundaries, and existing interface/cardinality/immutability rules remain active
- [ ] Networking specification and metadata updates, including SecurityGroup rules, remain rejected in both modes
- [ ] Deletion awaits active network-operation cancellation and preserves dependency/cascade order without provider cleanup; ordinary workload deletion stays active
- [ ] An unallocated ExternalIP reports Pending/Progressing with an empty address and Ready=False/ProvisioningDisabled; automatic ExternalIP requests do not block VM provisioning and no attachment is created until real allocation + VM Ready [User]

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created by the platform (see Default Networking PRD). If defaults are not configured, creating a VM without explicit network configuration fails with a clear error.
- The target deployment supports virtualization. Bare-metal-only deployments do not support VMs.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
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

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ prd 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (57 behind origin/main)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"1f3b63b82","source_repo_branch":"main","commits_behind_main":57,"commits_ahead_main":0,"main_ref":"main","phases":["revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
