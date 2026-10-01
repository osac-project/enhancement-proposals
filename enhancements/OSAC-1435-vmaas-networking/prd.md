# VMaaS Networking — Single Attachment VMs and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-09-24 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support read (List/Get), create, and delete. NetworkACL
rules and Subnet-to-ACL associations are immutable after creation. VM network
attachment fields are also create-time-only; changing one requires delete and
recreate.

VMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## 1. Problem Statement

Creating a VM with external access requires manual IP allocation and NAT configuration, forcing tenants to understand inbound and outbound routing before provisioning their first reachable VM. The default networking experience varies across resource types — some resources have simplified creation flows while VMs require explicit networking details on every create. VMaaS currently supports at most one network attachment per VM; the plural API field is retained for compatibility.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with zero or one network attachment; the sole attachment is the primary/default route
- A tenant can create a VM with `--external-ip-attachment` and have the system allocate an external IP and attach it automatically; inbound reachability follows the effective Subnet policy
- A tenant can create a VM without specifying networking details — the system uses the tenant's default Subnet, which has no ACL association, under the deployment default ACL policy
- The platform prevents VM creation in deployments that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (this PRD covers VMs only; clusters and bare-metal servers are addressed in separate enhancements)
- Multi-NIC VM networking (future scope; the repeated field does not enable it)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment, so that it receives connectivity on the selected subnet
- As a Tenant User, I want the sole network attachment to provide the VM's default gateway and DNS configuration without requiring a second API field
- As a Tenant User, I want to create a VM with `--external-ip-attachment`, so that the system provisions an external IP automatically and inbound reachability follows the effective Subnet policy
- As a Tenant User, I want to create a VM without specifying network details, so that the system uses my default Subnet under the deployment default ACL policy and I can get started quickly
- As a Tenant User, I want clear error messages when I try to create a VM in a deployment that only supports bare-metal servers, so that I understand the limitation and can choose a different deployment

### Tenant Admin Stories

- As a Tenant Admin, I want to inspect and manage the optional NetworkACL associated with the subnet used by VMs so that I can refine the deployment default traffic policy for every workload on that subnet
- As a Tenant Admin, I want to see which subnet each VM uses and which NetworkACL governs that subnet, along with the IP address allocated to each interface, so I can audit my organization's network topology

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

- **FR-3:** Network configuration is optional when creating a VM. When the attachment list is omitted or empty, the system uses the tenant's default Subnet, which has no ACL association (see Default Networking PRD). When a single attachment is supplied with a missing Subnet, only the Subnet is defaulted; supplied values are preserved. If an explicitly selected Subnet has an associated NetworkACL, its rules refine the deployment default ACL policy; otherwise that deployment policy applies directly. The resolved Subnet is stored with the VM so it is self-describing after creation. [User]

#### Auto External IP

- **FR-4:** VMs support `--external-ip-attachment`. When specified, the system selects an available external IP pool with the most capacity and reserves capacity for an IP with the VM create request. The IP is allocated asynchronously; its attachment routes inbound traffic to the VM's primary interface only after the IP is Allocated and the VM is Ready. ExternalIP routing does not bypass the effective Subnet policy: on the unassociated default Subnet, unmatched ingress and egress are denied when the deployment action is `DENY`. Under `DENY`, inbound external access requires a Subnet created with a NetworkACL that permits the inbound flow and its return traffic. Outbound SNAT through a NATGateway likewise requires ACL rules that permit the egress flow and its return traffic, plus a configured egress path. A `PERMIT` deployment fallback allows unmatched flows on the default Subnet. The IP and attachment are automatically cleaned up when the VM is deleted. Default networking resources (virtual networks, subnets, NATGateways) are not cleaned up as they are tenant-scoped and shared across resources. Tenant-created NetworkACLs are not auto-deleted because they may be shared by multiple Subnets. [User; PR review: CodeRabbit]

#### IP Address Discovery

- **FR-5:** The allocated IP address for the network attachment is visible in the VM status after provisioning completes. When an external IP is attached to a VM, inbound traffic to the external IP is routed to the VM's sole/primary attachment IP. [User]

#### Deployment Validation

- **FR-6:** When a VM is created, the platform validates that the target deployment supports virtualization. If the deployment only supports bare-metal servers, the create request fails with a clear error message explaining the limitation. [User]

#### API Compatibility

- **FR-7:** The existing repeated `network_attachments` field remains the only VM network-configuration field. No singular replacement field, parallel legacy field, or dual-field conversion period is introduced. [User]

#### NetworkACL Policy

- **FR-8:** A VM receives the deployment default ACL policy, refined by any NetworkACL associated with its Subnet; each Subnet has zero or one active association, and an ACL may be reused by Subnets in the same VirtualNetwork. Tenants configure this policy on the Subnet and it applies uniformly to all workloads attached to that Subnet. Ingress and egress rules are evaluated independently using the shared match-specificity order; action and request order do not determine precedence. The first matching rule allows or denies traffic, and traffic with no matching rule uses the required deployment default ACL action, which also applies when no ACL is associated. The policy is stateless, so return traffic is evaluated independently in the reverse direction. With a `DENY` fallback, permitting a reply requires a matching reverse-direction `ALLOW` rule to win precedence; with `PERMIT`, an unmatched reply passes unless a matching reverse-direction `DENY` rule applies. Traffic between workloads on the same Subnet is not filtered by the Subnet NetworkACL; traffic between Subnets must satisfy the source Subnet's egress policy and the destination Subnet's ingress policy. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** ExternalIPPool selection and capacity reservation complete synchronously with the create request. ExternalIP allocation proceeds asynchronously. If no pool has available capacity, the create request fails with a clear error. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a VM with zero or one `--network-attachment` flag; a second flag is rejected with a clear maximum-one error
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no explicit network configuration — the VM is created on the default subnet with an auto-provisioned external IP; inbound reachability follows the effective Subnet policy, and unmatched inbound traffic is denied when the deployment action is `DENY`
- [ ] Creating a VM in a bare-metal-only deployment returns an error with a clear message
- [ ] A VM with one attachment is provisioned with that attachment providing the default gateway
- [ ] VM status shows the allocated IP address for the sole network attachment after provisioning completes
- [ ] External IP attachment with a VM target routes inbound traffic to the VM's primary attachment IP
- [ ] Auto-created external IPs and attachments are visible in list views with a label indicating they were auto-provisioned
- [ ] Deleting a VM with auto-provisioned external IP causes the auto-created IP and attachment to be cleaned up automatically
- [ ] Deleting a VM with an active, manually created ExternalIPAttachment targeting it is rejected until the tenant removes that attachment
- [ ] An auto-created ExternalIPAttachment is created only after the ExternalIP is Allocated and the VM is Ready
- [ ] Creating a VM with an omitted or empty attachment list receives the tenant default Subnet, which has no ACL association, so the deployment default action decides unmatched traffic
- [ ] Creating a VM with a partial single attachment defaults only its missing subnet; its resolved Subnet's optional NetworkACL refines the deployment default policy
- [ ] Ingress and egress use the first matching rule under the shared match-specificity order and unmatched traffic uses the deployment default ACL action; under `DENY`, permitting return traffic requires a matching reverse-direction `ALLOW` rule to win precedence, while under `PERMIT`, unmatched replies pass unless a reverse-direction `DENY` rule applies

## 6. Assumptions

- The tenant has a default VirtualNetwork and Subnet pre-created by the platform, with no ACL association on the default Subnet; unmatched traffic uses the required deployment-wide default ACL action (see Default Networking PRD). If defaults are not configured, creating a VM without explicit network configuration fails with a clear error.
- The target deployment supports virtualization. Bare-metal-only deployments do not support VMs.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, NetworkACLs, external IPs, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default Subnet selection, optional ACL association, and deployment fallback action defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
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

Authored: respond @ prd 0.11.3 - 2bd6607, workspace main @ 2293f9140
Phases: respond, respond

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
