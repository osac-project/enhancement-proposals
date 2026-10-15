# VMaaS Networking — Single Attachment VMs and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support only Create, List/Get, and Delete. A VM's network
selection is fixed at creation; changing it requires replacing the VM.

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

Creating a VM with external access requires manual IP allocation and NAT configuration, forcing tenants to understand inbound and outbound routing before provisioning their first reachable VM. The default networking experience varies across resource types — some resources have simplified creation flows while VMs require explicit networking details on every create. VMaaS supports at most one tenant network attachment per VM.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a VM with zero or one network attachment; the sole attachment is the primary/default route
- A tenant can create a VM with `--external-ip-attachment` and have the system allocate an external IP and attach it automatically for inbound access
- A tenant can create a VM without specifying networking details — the system uses the tenant's default subnet and security group
- The platform prevents VM creation in deployments that do not support virtualization

### 2.2 Non-Goals

- Cluster or bare-metal server networking (this PRD covers VMs only; clusters and bare-metal servers are addressed in separate enhancements)
- Multi-NIC VM networking (future scope)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a VM with one network attachment, so that it receives connectivity on the selected subnet
- As a Tenant User, I want the VM's sole network attachment to provide its default gateway and DNS configuration without making a separate primary-network choice
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

- **FR-1:** A tenant can create a VM with no more than one tenant network attachment. That attachment provides the VM's primary route and network context for inbound access; optional outbound translation is provided by the selected VirtualNetwork's NATGateway. A request that selects more than one attachment is rejected. [User]
- **FR-2:** A VM's sole attachment is its primary attachment and supplies the default route. Tenants do not need to make a separate primary-network choice. [User]

#### Optional Network Configuration with Defaults

- **FR-3:** Network configuration is optional when creating a VM. If the tenant omits it, OSAC uses that tenant's defaults. If the tenant supplies a partial selection, OSAC fills only the missing choices and preserves the supplied ones. The default SecurityGroup is used only when it belongs to the selected Subnet's VirtualNetwork; otherwise the tenant must choose SecurityGroups from that VirtualNetwork. The VM's resolved network is visible after creation. [User]

#### Auto External IP

- **FR-4:** A tenant can request `--external-ip-attachment` when creating a VM. OSAC accepts the request only when address capacity is available; address assignment may finish asynchronously. Inbound access becomes available only after the provider assigns a real address and the VM endpoint is ready. If automatic cleanup fails during deletion, the VM remains pending deletion with an actionable diagnostic until cleanup can continue. Shared tenant defaults remain available. [User]

#### IP Address Discovery

- **FR-5:** The allocated IP address for the network attachment is visible in the VM status after provisioning completes. When an external IP is attached to a VM, inbound traffic to the external IP is routed to the VM's sole/primary attachment IP. [User]

#### Deployment Validation

- **FR-6:** When a VM is created, the platform validates that the target deployment supports virtualization. If the deployment only supports bare-metal servers, the create request fails with a clear error message explaining the limitation. [User]

#### API Compatibility

- **FR-7:** Existing VM creation requests remain compatible with the documented network-selection experience; tenants do not need to migrate to a second network-selection method. [User]

#### Provider Networking Disabled

- **FR-8:** A Cloud Provider Admin can disable provider networking during installation or upgrade while keeping ordinary VM provisioning and the networking APIs available. The setting takes effect after rollout. When disabled, ordinary VMs can use the platform's default connectivity; OSAC does not claim that a tenant Subnet, ExternalIP, or provider route was configured. Network requests retain their normal validation and dependency rules. Automatic external-address requests do not block VM provisioning, but inbound access is unavailable until a real address and ready VM endpoint exist. VM deletion and logical networking cleanup remain available; skipped provider work and any required provider-side cleanup are made clear to administrators. [User]

An ordinary VM without tenant network selection still provisions using the
platform's default connectivity. Disabling provider integration does not add a
tenant-network requirement to VM provisioning. User-supplied network choices
remain subject to the documented validation and dependency rules while
provider work is skipped. [User]

#### Stateful Attachment Policy

- **FR-9:** A VM's selected SecurityGroups define its stateful ingress and egress policy. Rules from the selected groups combine; established replies are allowed and unmatched new traffic is denied. OSAC reports tenant network connectivity only after the policy is applied and the tenant address is known; a policy failure is visible and does not report successful connectivity. [User]

Re-enabling provider networking requires the Cloud Provider Admin to drain/delete all existing deployment workloads, including managed cluster workers, finish or account for outstanding network operations, and arrange cleanup of leftover provider state. Workloads remain readable/deletable during the transition, but new workload creation is blocked. After deployment activation, each new workload requires its own provider-backed network dependencies to be ready; a failure in one tenant's defaults does not block other ready tenants. OSAC does not automatically move existing baseline workloads into tenant networks. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** OSAC checks address capacity before accepting an automatic external-access request. If capacity is unavailable, the request fails with a clear error; provider address assignment may continue asynchronously. [User]

Connectivity, allocation, provider policy enforcement/cleanup, and related
provider-work timing requirements described here apply when provider networking is
enabled. Disabled mode retains API prerequisites and explicitly identifies
skipped provider work; it does not claim those provider outcomes. [User]

## 5. Acceptance Criteria

- [ ] Re-enabling networking with existing workloads is blocked; users can inspect and delete them. After all workloads and outstanding network work are drained and backend leftovers repaired, activation reconciles real network readiness before accepting new workloads. No baseline workload is migrated in place. [User]

- [ ] Two VMs in one subnet with different groups receive their respective stateful traffic policies; a failed policy operation leaves the affected VM non-ready
- [ ] Persistent automatic external cleanup failure leaves VM deletion pending with a diagnostic until repair, then resumes without losing address ownership [User]


- [ ] A Tenant User can create a VM with zero or one `--network-attachment` flag; a second flag is rejected with a clear maximum-one error
- [ ] A Tenant User can create a VM with `--external-ip-attachment` and no explicit network configuration — the VM is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] Creating a VM in a bare-metal-only deployment returns an error with a clear message
- [ ] A VM with one attachment is provisioned with that attachment providing the default gateway
- [ ] VM status shows the allocated IP address for the sole network attachment after provisioning completes
- [ ] External IP attachment with a VM target routes inbound traffic to the VM's primary attachment IP
- [ ] Auto-created external IPs and attachments are visible in list views with a label indicating they were auto-provisioned
- [ ] Deleting a VM with auto-provisioned external IP causes the auto-created IP and attachment to be cleaned up automatically
- [ ] Creating a VM with an omitted or empty attachment list receives the tenant defaults
- [ ] Creating a VM with a partial network selection defaults only the missing choices

- [ ] With the shared setting disabled after rollout, an API-valid ordinary workload request still provisions using the stated platform/provisioning connectivity
- [ ] With provider networking disabled, ordinary VM provisioning remains available on platform connectivity, while API results do not imply tenant-network connectivity, inbound access, or provider-side cleanup
- [ ] Default SecurityGroup resolution, invalid-reference/non-ready-dependency rejection, tenant boundaries, and existing interface/cardinality/immutability rules remain active
- [ ] Networking specification and metadata updates, including SecurityGroup rules, remain rejected in both modes
- [ ] Deletion awaits active network-operation cancellation and preserves dependency/cascade order without provider cleanup; ordinary workload deletion stays active
- [ ] An automatic external-address request does not block VM provisioning while networking is disabled; OSAC exposes no fabricated address or inbound attachment, and only activates inbound access after real allocation and a ready VM endpoint [User]

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created by the platform (see Default Networking PRD). If defaults are not configured, creating a VM without explicit network configuration fails with a clear error.
- The target deployment supports virtualization. Bare-metal-only deployments do not support VMs.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (virtual networks, subnets, security groups, external IPs, NAT gateways) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default subnet and security group selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **Network Manager Integration Contract** — defines how providers register and select compatible managers and how OSAC validates their shared networking work; this PRD defines the VM-specific behavior that uses that contract ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))
- **OSAC-1712 (automatic pool selection)** — the auto external IP pool selection reuses the identical algorithm: pick the pool with the most available capacity matching the IP family
- **Qualified Kubernetes Manager** — VM overlay networking requires a deployment-selected manager that is compatible with the Fabric Manager and meets the shared manager contract. OSAC-1511 and OSAC-1717 were evaluation spikes; their closure does not establish that a manager is deployed or qualified.

## 8. Risks

### 8.1 Virtualization platform integration blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** OSAC-1511 and OSAC-1717 are closed evaluation spikes, not delivery or qualification of a deployment's Kubernetes Manager. Gate VM overlay networking on a compatible, registered manager that passes provider qualification; without one, VM overlay networking remains unavailable.

### 8.2 Shared manager support is delayed

- **Owner:** Platform team
- **Mitigation:** Deliver the shared manager registration, dispatch, result validation, and recovery behavior before enabling provider-backed VM networking. The completed legacy multi-job tracking work is groundwork and does not by itself satisfy the Network Manager Integration Contract.

### 8.3 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### ~~9.1 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

---

## Provenance

Authored: revise @ prd 0.11.5 - 6d28c88, workspace docs/OSAC-1433-network-manager-provider-guide @ eabff3b59 (76 behind origin/main, dirty)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace docs/OSAC-1433-network-manager-provider-guide @ 639af2dba

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"639af2dba","source_repo_branch":"docs/OSAC-1433-network-manager-provider-guide","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
