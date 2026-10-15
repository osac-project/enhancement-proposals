# BMaaS Networking — Single Attachment and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1437 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support only Create, List/Get, and Delete. A bare-metal
server's network selection is fixed at creation; changing it requires replacing
the server.

BMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

Provider-dependent connectivity, allocation, and cleanup in this document
describe the enabled mode. FR-13 defines the shared installation/upgrade
setting and disabled experience. Networking APIs retain the published default
SecurityGroup selection, immutability, validation, and dependency rules in
both modes. [User]

## 1. Problem Statement

Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. Tenants cannot attach bare-metal servers to subnets, apply security groups, or configure external access through the API. The system does not expose which physical network interfaces are available on a bare-metal server, forcing tenants to discover interface names through out-of-band documentation. Creating a reachable bare-metal server with both inbound and outbound connectivity requires sequential API calls to create networking resources and manual coordination with infrastructure administrators for switch port configuration.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can provision a bare-metal server with one explicit network attachment, optionally specifying which physical interface connects to its subnet
- A tenant can create a bare-metal server with `--external-ip-attachment` and have the system allocate an external IP for inbound access automatically
- Network attachments are optional — when omitted, the system attaches the server to the tenant's default subnet and security group
- Tenants and administrators can discover the physical interfaces available for each server type and identify which can carry tenant traffic
- Bare-metal servers receive tenant connectivity on the selected interface after host provisioning completes
- External IP attachments support bare-metal servers as a target type
- Cloud Provider Admins can select the deployment's networking implementation without exposing provider selection to tenants

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| BM provisioning time with networking | <5 min | N/A (no baseline) |
| Network connectivity configuration success rate | >95% | N/A |

### 2.3 Non-Goals

- Cluster or VM networking (this PRD covers bare-metal servers only; clusters and VMs are addressed in separate enhancements)
- Provider-specific networking implementation details; this PRD defines bare-metal networking outcomes and depends on the shared networking and manager contracts
- Multi-interface failover or bonding (out of scope for initial implementation)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a bare-metal server with one explicit network attachment so that I can connect a selected physical interface to a subnet
- As a Tenant User, I want to see which physical network ports are available on a BareMetalInstanceType so that I can select the appropriate interface when creating the attachment
- As a Tenant User, I want to create a bare-metal server with `--external-ip-attachment` and have it externally reachable in a single API call, without manually creating external IP and attachment resources
- As a Tenant User, I want the sole network attachment to provide the default gateway without needing a second attachment
- As a Tenant User, I want auto-provisioned external IPs to be automatically cleaned up when I delete the server, so that I do not accumulate orphaned resources
- As a Tenant User, I want network interface validation when creating the attachment so that I get a clear error if I specify a port that does not exist or is not tenant-attachable

### Tenant Admin Stories

- As a Tenant Admin, I want visibility into which physical interfaces are connected to which subnets for a bare-metal server so that I can troubleshoot network connectivity issues

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define which physical interfaces are available for tenant networking on each server type, so tenants can choose a suitable connection

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want bare-metal networking to use the deployment's selected networking implementation, so that tenants do not need to choose a provider backend
- As a Cloud Provider Admin, I want to see which IP addresses were allocated to each network interface on a bare-metal server so that I can troubleshoot connectivity and external access configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment Specification

- **FR-1:** A tenant can create a bare-metal server with no more than one tenant network attachment. The tenant can leave network choices to the platform or provide a partial selection; supplied choices are preserved and the resolved selection is fixed after creation. Requests for multiple attachments are rejected. [User]

#### Physical Interface Discovery

- **FR-2:** Tenants and administrators can discover the available network interfaces for each bare-metal instance type, including the information needed to distinguish tenant-facing and system interfaces. When several suitable tenant-facing interfaces are available, the platform has a consistent default selection. [User]

#### Interface Validation

- **FR-3:** OSAC rejects a request that selects an unavailable or system-only interface, or that asks to attach a server to multiple tenant networks. The error identifies the invalid choice. [User]

#### Primary Gateway Designation

- **FR-4:** The server's sole tenant network attachment is its primary route and gateway. Tenants do not need to make a separate primary-network choice. [User]

#### Optional Network Attachments with Defaults

- **FR-5:** Network selection is optional. If omitted, OSAC uses the tenant's default Subnet and compatible SecurityGroup and selects a suitable tenant-facing interface for the server's instance type. For a partial selection, OSAC fills only missing choices and preserves supplied values. A default SecurityGroup is used only when it belongs to the selected Subnet's VirtualNetwork; otherwise the tenant must select SecurityGroups from that VirtualNetwork. The resolved network remains visible with the server after creation. [User]

#### Auto External IP

- **FR-6:** A tenant can request `--external-ip-attachment` when creating a bare-metal server. OSAC accepts the request only when address capacity is available; address assignment may finish asynchronously. Inbound access becomes available only after the provider assigns a real address and the server's tenant endpoint is ready. Automatically created addresses and routes are identifiable and visible. If provider networking is disabled, this request does not block server provisioning but does not provide inbound access until real provider work is available. [User]

#### Network Connectivity Configuration

- **FR-7:** With provider networking enabled, the server receives tenant connectivity on the selected interface after host provisioning. OSAC reports tenant connectivity only after the selected interface has a known tenant address and the requested network policy is in effect; a provisioning-network address is not presented as the tenant address. [User]

#### IP Address Visibility

- **FR-8:** The tenant IPv4 address for the selected interface is visible with the server after discovery. If the platform cannot identify that interface or its address, it reports the issue clearly and does not substitute an address from another interface or from host provisioning. [User]

#### External IP Attachment for Bare-Metal

- **FR-9:** A tenant can use an ExternalIPAttachment to provide inbound access to a bare-metal server. Traffic to that ExternalIP reaches the server's primary tenant address. [User]

#### Provider Networking Selection

- **FR-10:** Bare-metal networking uses the networking implementation selected by the Cloud Infrastructure Admin. Tenants do not select or need to understand the provider implementation. [User]

#### Auto-Cleanup on Deletion

- **FR-11:** Deleting a server removes its automatically created inbound routes and external addresses. If provider cleanup fails, deletion remains pending with an actionable diagnostic and the resources remain owned for retry. The tenant removes manually created routes first; shared tenant defaults remain available. [User]

#### Network Attachment Deletion

- **FR-12:** Server deletion does not return a host to the available inventory until required tenant-network cleanup has completed and the host can be safely reused. If cleanup fails, deletion remains pending and the failure is visible. When provider networking is disabled, OSAC does not claim to have restored a host to provisioning connectivity; provider-side repair may be needed before reuse. [User]

#### Provider Networking Disabled

- **FR-13:** A Cloud Provider Admin can disable provider networking during installation or upgrade while keeping normal bare-metal host provisioning, management, and deprovisioning available. The setting takes effect after rollout. When disabled, OSAC does not move tenant interfaces, discover tenant addresses, or promise tenant routing or ExternalIP access. The bare-metal service can continue to use the platform's provisioning network when its other requirements are met. Networking APIs retain their validation and dependency rules, and their status makes clear when provider work was skipped. Logical deletion remains available, but a host that was already moved to a tenant network may need provider-side restoration before it can be safely reused. [User]

#### Stateful Attachment Policy

- **FR-14:** The selected SecurityGroups define the server's stateful ingress and egress policy. Rules from selected groups combine; established replies are allowed and unmatched new traffic is denied. OSAC reports tenant connectivity only after policy is active and makes policy failures visible. [User]

Re-enabling provider networking requires the Cloud Provider Admin to drain/delete all existing deployment workloads, including managed cluster workers, finish or account for outstanding network operations, and arrange cleanup of leftover provider state. Workloads remain readable/deletable during the transition, but new workload creation is blocked. After deployment activation, each new workload requires its own provider-backed network dependencies to be ready; a failure in one tenant's defaults does not block other ready tenants. OSAC does not automatically move existing baseline workloads into tenant networks. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** OSAC checks address capacity before accepting an automatic external-access request. If capacity is unavailable, the request fails clearly; provider address assignment may continue asynchronously. [User]

- **NFR-2:** Network attachment provisioning (connectivity configuration) completes within 2 minutes for the selected interface. [User]

Connectivity, allocation, provider policy enforcement/cleanup, and related
provider-work timing requirements described here apply when provider networking is
enabled. Disabled mode retains API prerequisites and explicitly identifies
skipped provider work; it does not claim those provider outcomes. [User]

## 5. Acceptance Criteria

- [ ] Re-enabling networking with existing workloads is blocked; users can inspect and delete them. After all workloads and outstanding network work are drained and backend leftovers repaired, activation reconciles real network readiness before accepting new workloads. No baseline workload is migrated in place. [User]

- [ ] A policy application failure leaves the server non-ready; a missing selected-interface identity does not expose a provisioning or another-interface address
- [ ] Enabled-mode deletion keeps the host unavailable for reuse until required network and external-address cleanup is complete; after provider repair, deletion continues without losing resource ownership [User]
- [ ] A Tenant User can create a bare-metal server with one tenant network attachment and, when needed, select an available tenant-facing interface
- [ ] A Tenant User can create a bare-metal server with `--external-ip-attachment` and no explicit network selection; OSAC uses the tenant defaults and provides inbound access after the server and address are ready
- [ ] The server's sole network attachment provides its primary route, and its tenant address is visible after connectivity is established
- [ ] Available physical interfaces are discoverable, and unavailable or system-only interfaces are rejected with a clear error
- [ ] Auto-created external addresses and routes are visible and are removed when their server is deleted
- [ ] An ExternalIPAttachment can target a bare-metal server and sends inbound traffic to its primary tenant address
- [ ] With provider networking disabled, host provisioning remains available when platform prerequisites are met; server readiness does not imply tenant routing, external-address allocation, or provider cleanup
- [ ] Default SecurityGroup resolution, invalid network/interface rejection, tenant boundaries, and network immutability remain active in both modes
- [ ] Networking specification and metadata changes, including SecurityGroup rules, require resource replacement in both modes
- [ ] Deletion and host deprovisioning remain available with provider networking disabled; if a host was previously attached to a tenant network, OSAC does not claim it has been restored to provisioning connectivity
- [ ] An automatic external-access request exposes no fabricated address or route; inbound access becomes available only after a real address and ready server endpoint exist [User]
- [ ] Disabled-mode deletion does not claim that an interface has been restored to the provisioning network unless that restoration actually occurred [User]

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created at onboarding (see Default Networking PRD). If defaults are not configured, creating a server without explicit network attachments fails with a clear error.
- The NetworkClass has a fabric manager configured (the system can resolve which network automation to use).
- The selected instance type exposes at least one suitable tenant-facing interface. If it does not, creating a server without an explicit valid interface fails with a clear error.
- System provisioning interfaces are reserved for system use and cannot be selected for tenant networking.

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default Subnet and SecurityGroup selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **Network Manager Integration Contract** — defines provider manager selection, shared operation dispatch, and the requirements an implementation must meet; this PRD defines bare-metal workload behavior on top of that shared contract ([PRD](/enhancements/OSAC-1433-network-manager-integration-contract-networking/prd.md), [design](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md))
- **NAT gateway support** — outbound NAT must be available as a networking resource
- **External access for BM targets** — the external IP attachment system must support bare-metal servers as targets
- **CLI support** — the CLI must support specifying network attachments when creating bare-metal servers
- **Qualified Fabric Manager** — the selected Fabric Manager must pass the shared qualification for physical attachment, policy, lease lookup, and cleanup behavior

## 8. Risks

### 8.1 Shared manager platform support blocked or delayed

- **Owner:** Platform team
- **Mitigation:** Bare-metal provider networking depends on the Network Manager Integration Contract's registration APIs, validation, generic dispatch, and result handling. Gate the service implementation on that shared support and track its implementation work separately from the closed legacy dispatcher groundwork.

### 8.2 Fabric manager bare-metal support blocked

- **Owner:** Network automation team
- **Mitigation:** Require the selected Fabric Manager to pass the shared provider qualification for physical attachment, stateful policy, selected-port lease discovery, and cleanup before enabling bare-metal networking. Registration or a successful task result alone is not evidence of those behaviors.

### 8.3 IP address feedback mechanism fails

- **Owner:** Platform team
- **Mitigation:** A missing or ambiguous tenant address on the selected interface keeps connectivity unready and prevents inbound access. Repair the interface identity or address source and retry; the service does not substitute another interface or a provisioning-network address. [User]

### 8.4 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### ~~9.1 Should the out-of-band provisioning interface be explicitly excluded from validation or just documented?~~ — Resolved

Resolved: Explicitly excluded in validation. Lifecycle and BMC interfaces are not tenant-attachable and are rejected during server validation. This is not just documented — it is enforced.

### ~~9.2 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

No product questions remain open. The design documents the resolved interface
selection and fallback behavior.

---

## Provenance

Authored: revise @ prd 0.11.5 - 6d28c88, workspace docs/OSAC-1433-network-manager-provider-guide @ eabff3b59 (76 behind origin/main, dirty)
Final: revise @ prd 0.11.5 - 1c6e8de, workspace docs/OSAC-1433-network-manager-provider-guide @ 639af2dba

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"639af2dba","source_repo_branch":"docs/OSAC-1433-network-manager-provider-guide","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
