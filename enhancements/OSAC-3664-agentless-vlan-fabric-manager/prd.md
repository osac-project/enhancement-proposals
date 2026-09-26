# Fabric Manager — Agentless VLAN

| Field       | Value   |
|-------------|---------|
| Author(s)   | Yoni Bettan (ybettan@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3664 |
| Date        | 2026-09-24 |

> This PRD covers the **agentless VLAN fabric manager** — a networking backend for
> OSAC. It builds on the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md),
> which defines the shared networking model, resources, API, and connected-only
> deployment support boundary. Air-gapped and disconnected networking
> deployments are not supported. This document defines the requirements for
> delivering that model on environments that use traditional managed switches
> (without fabric manager). It adds a backend, not new API. This milestone does
> not implement the mandatory NetworkACL readiness contract, so the backend
> cannot serve the shared API or be selected as a supported fabric manager yet.

This PRD also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## 1. Problem Statement

Today OSAC's networking API is served by the existing physical fabric manager. Cloud
providers whose environments use traditional managed switches — without fabric manager —
have no supported way to deliver API-driven tenant networking, and are effectively
locked to fabric manager to offer subnets, external access, and NAT through the API. In
such environments, cluster (CaaS) networking exists only as an inline path that
bypasses the networking API and does not serve bare-metal or VM workloads, so
tenants get an inconsistent, partial networking experience. Without a second
fabric manager, OSAC cannot be deployed with API-driven networking on common
managed-switch infrastructure, limiting where the platform can run.

## 2. Goals and Non-Goals

### 2.1 Goals

- After mandatory NetworkACL enforcement is implemented, a Cloud Infrastructure
  Admin can deploy OSAC with API-driven tenant networking on environments that
  use traditional managed switches by selecting the agentless VLAN backend.
  This milestone does not make that backend selectable. [Clarify: D6; User direction]
- After the backend satisfies the shared NetworkACL readiness contract, tenants
  use the same networking API and get equivalent behavior. Until then, the
  backend cannot serve as a supported fabric manager. [Clarify: D6, D8; User direction]
- After the backend is eligible for supported selection, bare-metal servers,
  clusters, and compute instances can use its attachment operations through the
  existing API. Service provisioning flows do not change (VM IP addressing and
  VM-to-fabric bridging remain outside this backend — see Assumptions/Dependencies).
  [Clarify: D1, D5, D8; PR review: CodeRabbit]
- A tenant can create a virtual network with multiple subnets: machines in the
  same subnet share a broadcast domain, machines in different subnets of the same
  network can reach each other through the VirtualNetwork routing path when
  allowed by their Subnet NetworkACL rules, and
  machines in different networks stay isolated. [Clarify: D12; User direction]
- Backend networking failures are visible to operators on the affected networking
  resource's status. [Clarify: D9]

### 2.2 Non-Goals

- This feature does not define the OSAC networking API or resource model. The
  unified networking work (OSAC-1433) defines the NetworkACL resource, stateless
  ingress and egress rules, and the Subnet association. This backend consumes
  that shared contract. [Clarify: D3, D5]
- The backend does not create tenant networking resources, including default
  networking or a default NetworkACL; tenant onboarding owns those resources.
  This backend configures networking only for machines, clusters, and VMs
  attached to a network resource. [User direction]
- Does not deprecate or remove the existing inline (non-API) CaaS networking path;
  that transition is handled separately by the CaaS agentless-VLAN follow-up.
  [Clarify: D4]
- DNS record creation is not part of this backend — DNS is a service-integration
  concern handled outside the networking API. [Clarify: D10]
- IPv6 and dual-stack networking are not supported; the backend supports IPv4,
  matching the unified networking contract. [Clarify: D11]
- Per-service integration and end-to-end validation for BMaaS, CaaS, and VMaaS are
  tracked as separate follow-up features (OSAC-1562, OSAC-1611, OSAC-3665), not
  delivered here. [Clarify: D1, D2]
- The VM-to-fabric bridging required for VMaaS is provided separately and is not
  part of this backend. [Clarify: D8]
- No UI is delivered in this milestone; backend selection and networking
  operations are available through configuration and the CLI. [Clarify: D7]
- NetworkACL data-plane provisioning and rule enforcement are out of scope for
  this backend milestone. OSAC-1433 defines the NetworkACL resource, stateless
  ingress and egress rules, a required Subnet association, and mandatory active
  policy before a Subnet can be Ready in every supported profile. This backend
  does not satisfy that contract and cannot serve the shared API or be selected
  as a supported fabric manager until it implements NetworkACL enforcement.
  Selection validation must reject it; a mismatched configuration must leave the
  Subnet and dependent resources not Ready. Same-Subnet L2 traffic remains
  outside subnet ACL filtering.
  [User direction]
- Broad multi-vendor switch support and switch-configuration concurrency beyond the
  initially supported platform(s) are follow-up work; the supported-switch set for
  this milestone is specified in the design EP. [PR review: CodeRabbit]
- Admin/deployment documentation for enabling, selecting, and operating the
  agentless VLAN backend is deferred to the design EP; its scope and plan are
  addressed there rather than in this PRD. [PR review: eranco74]

## 3. User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to deploy OSAC networking on an
  environment that uses the agentless VLAN backend, so that I can offer
  API-driven tenant networking on that infrastructure. [Clarify: D6]
- As a Cloud Infrastructure Admin, I want to select the networking backend
  through deployment configuration, so that backend choice is consistent and
  requires no tenant-facing API change. This backend is unavailable for supported
  selection until it implements mandatory NetworkACL enforcement. [Clarify: D7]
- As a Cloud Infrastructure Admin, I want external IP ranges I define to be usable
  for tenant external access with the agentless VLAN backend, so that inbound and
  outbound external connectivity works through the supported deployment path.
- As a Cloud Infrastructure Admin, I want a failed networking operation (for
  example, a machine's port that could not be placed on a subnet's VLAN) reflected
  on the affected resource's status, so that I can diagnose fabric problems.
  [Clarify: D9]

### Tenant Admin / Tenant User

- As a Tenant Admin, I want to create and manage networking resources — virtual
  networks, subnets, external IPs, and NAT gateways — through the shared API,
  while each supported Subnet becomes Ready only after its associated NetworkACL
  is actively enforced. The agentless backend remains unsupported until it meets
  that contract.
  [Clarify: D6, D8]
- As a Tenant Admin, I want to create a virtual network with multiple subnets
  where machines in the same subnet share a broadcast domain and machines in
  different subnets of the same network can communicate when allowed by their
  Subnet NetworkACL rules, while machines in other networks are isolated, so that
  I can segment my network without losing connectivity or isolation. [Clarify: D12]
- As a Tenant User, I want a machine I attach to a subnet to receive an IP address
  automatically and be reachable on that subnet, so that I don't configure
  addressing by hand.
- As a Tenant User, I want to make a machine reachable from outside by attaching
  an external IP, so that I can expose my workloads.
- As a Tenant User, I want my machines to have outbound external connectivity
  through a NAT gateway, so that they can reach external services.

## 4. Requirements

### 4.1 Functional Requirements

#### Backend Selection

- **FR-1:** The agentless VLAN backend is not advertised or selectable as a
  supported fabric manager in this milestone because every supported profile
  requires active NetworkACL enforcement. Selection validation must reject it
  until the backend implements that contract. The eventual selection remains
  provider configuration and requires no networking-API changes.
  [Clarify: D3, D7]

#### Fabric-Manager-Agnostic Networking

- **FR-2:** The shared VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment,
  NATGateway, and NetworkACL APIs remain unchanged. This backend milestone does
  not satisfy their shared networking readiness contract and cannot serve them
  through supported selection. If a mismatched selection reaches reconciliation,
  the Subnet and dependent resources remain not Ready. [Clarify: D1, D5, D8; User direction]

#### Multiple Subnets per Virtual Network

- **FR-3:** Topology-level tests may exercise the backend's multiple-VLAN and
  VirtualNetwork-routing primitives with raw fixtures. They do not create
  API-Ready Subnets or workloads and do not establish support for the shared
  networking contract. Once NetworkACL enforcement is implemented, Subnets can
  provide broadcast segmentation and routed connectivity subject to their
  associated ACL rules; different VirtualNetworks remain isolated (see NFR-3).
  [Clarify: D12; User direction]

#### Automatic IP Assignment

- **FR-4:** After this backend implements ACL enforcement and can report the
  associated NetworkACL active, a bare-metal server or cluster node can receive
  an IP address on its Subnet and report it in status. This behavior is not
  available through this milestone's unsupported backend. VM addressing is
  provided by the OVN overlay and is out of scope. [Clarify: D9, D13; PR review: CodeRabbit]

#### Inbound External Access

- **FR-5:** After this backend implements mandatory ACL enforcement and becomes
  selectable, an ExternalIP can expose a machine through the external path only
  when the target Subnet and its NetworkACL are Ready. This milestone cannot
  report that readiness or permit workload use.
  [Jira: OSAC-3664; User direction]

#### Outbound External Connectivity

- **FR-6:** After this backend implements mandatory ACL enforcement and becomes
  selectable, a NATGateway can provide outbound connectivity only after each
  source Subnet and its NetworkACL are Ready. This milestone cannot report that
  readiness or permit workload use.
  [Jira: OSAC-3664; Clarify: D14; User direction]

#### External IP Pools

- **FR-7:** After this backend implements mandatory NetworkACL enforcement and
  becomes selectable as a supported fabric manager, a Cloud Infrastructure
  Admin can define external IP ranges (ExternalIPPool) from which tenant
  ExternalIPs can be allocated for external access. This milestone does not
  expose tenant ExternalIP allocation through this backend. [Jira: OSAC-3664;
  User direction]

#### Networking Across All Services

- **FR-8:** This backend cannot serve workload network attachments through the
  supported API until it implements mandatory NetworkACL enforcement. After that
  support is added, service-specific end-to-end provisioning and validation are
  delivered by the follow-up features (see Non-Goals). [Clarify: D1, D8; PR review: CodeRabbit]

#### Failure Visibility

- **FR-9:** When a backend networking operation fails (for example, a machine's
  port cannot be placed on the requested subnet's VLAN), the failure is reflected
  on the affected networking resource's status with a diagnostic message.
  [Clarify: D9]

#### Lifecycle Cleanup

- **FR-10:** When a networking resource is deleted, the backend removes that
  resource's fabric configuration and releases any addresses it allocated, without
  affecting other resources. Teardown respects dependency order — an
  ExternalIPAttachment's inbound DNAT is removed before its ExternalIP is released
  back to its pool. [Jira: OSAC-3664; PR review: CodeRabbit]

### 4.2 Non-Functional Requirements

- **NFR-1:** The agentless VLAN backend provides networking for the IPv4 address
  family. IPv6 and dual-stack are not supported. [Clarify: D11]
- **NFR-2:** A supported fabric manager must satisfy the complete shared
  networking contract, including mandatory NetworkACL enforcement. This milestone
  does not satisfy it and cannot claim tenant-observable API parity or supported
  manager eligibility until enforcement is implemented. [Clarify: D8; User direction]
- **NFR-3:** Different VirtualNetworks have no direct connectivity on the internal
  fabric — a machine in one VirtualNetwork cannot reach another VirtualNetwork's
  private subnet addresses, even when their address ranges overlap. Machines
  remain reachable across VirtualNetworks only via their external IPs over the
  external network path (inbound ExternalIP + outbound NATGateway), the same as
  reaching any external endpoint — this is not internal cross-VN routing.
  [Clarify: D12, D15]

## 5. Acceptance Criteria

### Current Milestone

- [ ] The agentless implementation is not advertised or selectable as a supported
  fabric manager until it implements NetworkACL enforcement for the mandatory
  Subnet readiness contract.
- [ ] If a stale or otherwise mismatched configuration reaches reconciliation,
  the Subnet and dependent resources remain not Ready and cannot be used by
  workloads. No permit-all fallback reports success.
- [ ] Topology-level checks use raw backend fixtures only. They do not create or
  claim API-Ready Subnets, API-ready workload attachments, or NetworkACL
  enforcement by this backend.

### Future Acceptance After NetworkACL Support

The following criteria are not met by this milestone. They become eligible for
acceptance only after this backend implements NetworkACL enforcement and can be
selected as a supported fabric manager.

- [ ] A bare-metal server or cluster node attached to a Ready Subnet receives an
  IP on that Subnet, visible in its status.
- [ ] Inbound ExternalIP data-plane checks reach a target only after its Subnet
  NetworkACL is Ready and its rules are enforced.
- [ ] Outbound NATGateway data-plane checks use its ExternalIP only after the
  source Subnet NetworkACL is Ready and its rules are enforced.
- [ ] ExternalIPAttachment and NATGateway resources become Ready only when their
  dependent Subnet NetworkACL is Ready and enforced.
- [ ] Permitted cross-Subnet traffic follows the associated ingress and egress
  rules, and directly routed traffic between overlapping VirtualNetworks remains
  unreachable.
- [ ] Same-Subnet traffic remains at L2 and is not filtered by the Subnet ACL,
  consistent with OSAC-1433.
- [ ] A machine in one VirtualNetwork can reach a machine in another VirtualNetwork
  through the target's ExternalIP when the policy permits the flow, while the
  target's private Subnet address remains unreachable.
- [ ] Bare-metal, cluster, and compute-instance attachments use the backend only
  after the Subnet and its NetworkACL are Ready; their end-to-end validation is
  covered by the follow-up features (OSAC-1611, OSAC-3665).
- [ ] Backend failures surface diagnostics on affected resources after the
  backend is eligible to manage those resources.
- [ ] Requests produce equivalent tenant-observable results for capabilities
  advertised by both supported backends, without any ACL-unaware permit-all
  fallback.
- [ ] Backend selection remains provider configuration with no tenant-facing API
  change. Deleting attachments, Subnets, or VirtualNetworks removes only owned
  state and leaves unrelated resources intact.

## 6. Assumptions

- The OSAC networking API and resource model are complete and stable, inherited
  from the unified networking work and already exercised by the fabric manager backend;
  this feature adds a backend, not API changes. [Clarify: D3]
- The agentless VLAN backend's lower-level building blocks already exist and are
  reused; they are extended only if a gap is found. [Clarify: D3]
- Target environments use managed switches supported by the backend's switch
  automation. The specific set of supported switch platforms is determined by that
  automation and defined in the design EP; this PRD does not claim universal switch
  support.
- The current one-subnet-per-VirtualNetwork limitation is lifted so that multiple
  subnets per network are allowed end-to-end. [Clarify: D12, C1]
- Machines never manage their own addressing. The agentless VLAN backend assigns
  addresses for bare-metal and cluster nodes on the fabric side; VM addressing is
  provided by the OVN overlay via the separate bridging mechanism (k8sManager) and
  is outside this backend's scope. The specific mechanism is a design decision.
  [Clarify: D8, D13]
- VMaaS additionally requires a separate VM-to-fabric bridging mechanism, provided
  outside this feature. [Clarify: D8]
- BMaaS is the first service validated with this backend; CaaS and VMaaS are
  validated by their follow-up features. [Clarify: D2]

## 7. Dependencies

- **Unified Networking EP (OSAC-1433)** — defines the networking model and API
  this backend implements ([Unified Networking EP](/enhancements/OSAC-1433-unified-networking)).
- **Multi-subnet enablement** — the service-layer change lifting the
  one-subnet-per-VirtualNetwork limitation must land so multiple subnets per
  network work end-to-end. [Clarify: C1]
- **Networking manager dispatch** — networking operations must be routed to the
  configured backend.
- **VM-to-fabric bridging (k8sManager)** — required for VMaaS to use this backend
  (e.g., OSAC-1511 / OSAC-1717); out of scope here. [Clarify: D8]
- **DNS** — external DNS records for clusters are created outside this backend, in
  the service flow and the separate DNS API (OSAC-1050). [Clarify: D10]
- **CLI** — networking operations must be available via the CLI (no UI this
  milestone). [Clarify: D7]
- **Downstream consumers** — OSAC-1562 (BMaaS), OSAC-1611 (CaaS), and OSAC-3665
  (VMaaS) integrate and validate this backend per service. [Clarify: D1]

## 8. Risks

### 8.1 Feature-parity gaps with the fabric manager backend

- **Owner:** Connectivity & Fabric team
- **Mitigation:** Use the existing physical fabric manager implementation
  (OSAC-2043) as the structural template and validate the agentless VLAN backend
  capability-by-capability against the same networking API contract. [Clarify: C2]

### 8.2 Multi-subnet enablement not ready in time

- **Owner:** Connectivity & Fabric team
- **Mitigation:** The accepted design requires inter-subnet routing within a
  VirtualNetwork; coordinate the service-layer change that lifts the
  one-subnet-per-network limitation alongside backend work so multi-subnet is
  usable end-to-end. [Clarify: C1]

### 8.3 Managed-switch compatibility

- **Owner:** Cloud Infrastructure Admin / Connectivity & Fabric team
- **Mitigation:** Validate the backend against the target managed-switch models
  during BMaaS integration (the first supported service).

### 8.4 IP discovery reliability

- **Owner:** Connectivity & Fabric team
- **Mitigation:** If a machine's assigned IP is not surfaced to its status,
  inbound external access cannot be configured. Validate automatic IP discovery
  and status feedback during BMaaS integration.

### 8.5 VLAN ID space limits fabric scale

- **Owner:** Connectivity & Fabric team
- **Mitigation:** The backend maps each Subnet to an 802.1Q VLAN, and VLAN-ID
  uniqueness per fabric is what enforces L2 isolation between VirtualNetworks — so
  each Subnet consumes one of the ~4094 usable VLAN IDs per physical fabric, a hard
  ceiling on the number of subnets (and therefore, transitively, of VirtualNetworks
  and tenants) a single agentless-VLAN fabric can host. IDs cannot be reused
  without breaking isolation. Document the per-fabric subnet ceiling as a known
  scale limit; if higher density is required, a stacked-VLAN (QinQ) or overlay
  (e.g., VXLAN) escape hatch is follow-up work, out of scope this milestone.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace HEAD @ 43141585d

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"43141585d","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
