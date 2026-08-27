# Fabric Manager — Agentless VLAN

| Field       | Value   |
|-------------|---------|
| Author(s)   | Yoni Bettan (ybettan@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3664 |
| Date        | 2026-08-27 |

> This PRD covers the **agentless VLAN fabric manager** — a networking backend for
> OSAC. It builds on the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md),
> which defines the shared networking model, resources, and API. This document
> defines the requirements for delivering that model on environments that use
> traditional managed switches (without Netris). It adds a backend, not new API.

## 1. Problem Statement

Today OSAC's networking API is served by a single fabric manager (Netris). Cloud
providers whose environments use traditional managed switches — without Netris —
have no supported way to deliver API-driven tenant networking, and are effectively
locked to Netris to offer subnets, external access, and NAT through the API. In
such environments, cluster (CaaS) networking exists only as an inline path that
bypasses the networking API and does not serve bare-metal or VM workloads, so
tenants get an inconsistent, partial networking experience. Without a second
fabric manager, OSAC cannot be deployed with API-driven networking on common
managed-switch infrastructure, limiting where the platform can run.

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cloud Infrastructure Admin can deploy OSAC with API-driven tenant networking
  in an environment that uses traditional managed switches (no Netris), by
  selecting the agentless VLAN backend. [Clarify: D6]
- Tenants get the same networking API and observable behavior — virtual networks,
  subnets, security groups, inbound external access, and outbound NAT — regardless
  of whether the deployment's backend is Netris or agentless VLAN. [Clarify: D6, D8]
- Bare-metal servers, clusters, and compute instances all use the agentless VLAN
  backend for their fabric networking through the existing networking API, with no
  changes to the service provisioning flows (VM IP addressing and VM-to-fabric
  bridging are provided outside the backend — see Assumptions/Dependencies).
  [Clarify: D1, D5, D8; PR review: CodeRabbit]
- A tenant can create a virtual network with multiple subnets: machines in the
  same subnet share a broadcast domain, machines in different subnets of the same
  network can reach each other when permitted by SecurityGroup rules, and machines
  in different networks stay isolated. [Clarify: D12]
- Backend networking failures are visible to operators on the affected networking
  resource's status. [Clarify: D9]

### 2.2 Non-Goals

- No changes to the OSAC networking API or its resource model — the API is
  inherited from the unified networking work (OSAC-1433) and consumed as-is.
  [Clarify: D3, D5]
- The backend does not create networking resources (including default networking);
  it configures the fabric only for resources — machines, clusters, VMs — attached
  to a network resource. [PR review: CodeRabbit]
- Does not deprecate or remove the existing inline (non-API) CaaS networking path;
  that transition is handled separately by the CaaS agentless-VLAN follow-up.
  [Clarify: D4]
- DNS record creation is not part of this backend — DNS is a service-integration
  concern handled outside the networking API. [Clarify: D10]
- IPv6 and dual-stack networking are not delivered in this milestone; the backend
  supports IPv4, matching the Netris baseline. [Clarify: D11]
- Per-service integration and end-to-end validation for BMaaS, CaaS, and VMaaS are
  tracked as separate follow-up features (OSAC-1562, OSAC-1611, OSAC-3665), not
  delivered here. [Clarify: D1, D2]
- The VM-to-fabric bridging required for VMaaS is provided separately and is not
  part of this backend. [Clarify: D8]
- No UI is delivered in this milestone; backend selection and networking
  operations are available through configuration and the CLI. [Clarify: D7]
- Broad multi-vendor switch support and switch-configuration concurrency beyond the
  initially supported platform(s) are follow-up work; the supported-switch set for
  this milestone is specified in the design EP. [PR review: CodeRabbit]
- Admin/deployment documentation for enabling, selecting, and operating the
  agentless VLAN backend is deferred to the design EP; its scope and plan are
  addressed there rather than in this PRD. [PR review: eranco74]

## 3. User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to deploy OSAC networking on an
  environment with traditional managed switches (no Netris) by selecting the
  agentless VLAN backend, so that I can offer API-driven tenant networking without
  Netris. [Clarify: D6]
- As a Cloud Infrastructure Admin, I want to select the networking backend (Netris
  or agentless VLAN) through the same configuration mechanism, so that the choice
  is consistent and requires no API or tenant changes. [Clarify: D7]
- As a Cloud Infrastructure Admin, I want external IP ranges I define to be usable
  for tenant external access with the agentless VLAN backend, so that inbound and
  outbound external connectivity works without Netris.
- As a Cloud Infrastructure Admin, I want a failed networking operation (for
  example, a machine's port that could not be placed on a subnet's VLAN) reflected
  on the affected resource's status, so that I can diagnose fabric problems.
  [Clarify: D9]

### Tenant Admin / Tenant User

- As a Tenant Admin, I want to create and manage networking resources — virtual
  networks, subnets, security groups, external IPs, and NAT gateways — through the
  same API regardless of whether the deployment uses Netris or agentless VLAN, so
  that my experience is identical across environments. [Clarify: D6, D8]
- As a Tenant Admin, I want to create a virtual network with multiple subnets
  where machines in the same subnet share a broadcast domain and machines in
  different subnets of the same network can communicate, while machines in other
  networks are isolated, so that I can segment my network without losing
  connectivity or isolation. [Clarify: D12]
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

- **FR-1:** A provider can configure the agentless VLAN backend as the networking
  backend for a deployment, using the same configuration mechanism used to select
  Netris. Backend selection is not visible to tenants and requires no
  networking-API changes. [Clarify: D3, D7]

#### Fabric-Manager-Agnostic Networking

- **FR-2:** With the agentless VLAN backend configured, tenants can create and
  manage the full networking resource set — VirtualNetwork, Subnet, SecurityGroup,
  ExternalIP, ExternalIPAttachment, NATGateway — through the existing networking
  API, with behavior equivalent to the Netris backend. [Clarify: D1, D5, D8]

#### Multiple Subnets per Virtual Network

- **FR-3:** A tenant can create a VirtualNetwork containing multiple Subnets.
  Machines attached to the same Subnet share an L2 broadcast domain; machines on
  different Subnets of the same VirtualNetwork can reach each other **when
  permitted by the applicable SecurityGroup rules** (the VirtualNetwork provides
  the routing path; SecurityGroups govern which traffic is allowed); machines on
  different VirtualNetworks have no direct connectivity on the internal fabric,
  even when their address ranges overlap (see NFR-3). This follows the unified
  networking model (OSAC-1433). [Clarify: D12; PR review: CodeRabbit]

#### Automatic IP Assignment

- **FR-4:** A bare-metal server or cluster node attached to a subnet is
  automatically assigned an IP address within that subnet's range by the backend —
  the tenant does not configure addressing manually — and the assigned address is
  visible on the resource's status. VM addressing is provided by the OVN overlay
  and is out of scope (see Assumptions). [Clarify: D9, D13; PR review: CodeRabbit]

#### Inbound External Access

- **FR-5:** A tenant can make a machine reachable from outside its VirtualNetwork
  by attaching an ExternalIP; inbound traffic addressed to the external IP reaches
  the machine when permitted by the applicable SecurityGroup rules.
  [Jira: OSAC-3664; PR review: CodeRabbit]

#### Outbound External Connectivity

- **FR-6:** A tenant can provide outbound external connectivity for a subnet's
  machines through a NATGateway. Outbound traffic permitted by the applicable
  SecurityGroup rules is source-address translated so it egresses with the
  NATGateway's external IP as its source address; many machines share that one
  external IP for egress. [Jira: OSAC-3664; Clarify: D14; PR review: CodeRabbit]

#### External IP Pools

- **FR-7:** A Cloud Infrastructure Admin can define external IP ranges
  (ExternalIPPool) from which the agentless VLAN backend allocates ExternalIPs for
  tenant external access. [Jira: OSAC-3664]

#### Networking Across All Services

- **FR-8:** The backend implements the network-attachment operations that
  bare-metal, cluster, and compute-instance attachments require, so that all three
  service types can use agentless-VLAN subnets through their existing
  network-attachment API. End-to-end per-service provisioning and validation are
  delivered by the follow-up features (see Non-Goals). [Clarify: D1, D8; PR review: CodeRabbit]

- ~~**FR-9:**~~ Removed — default networking is a tenant-onboarding / generic-API
  concern, not this backend. The backend does not create networking resources; it
  configures the fabric only for resources attached to a network resource, and
  realizes any onboarding-created default resources like any other.
  [PR review: CodeRabbit]

#### Failure Visibility

- **FR-10:** When a backend networking operation fails (for example, a machine's
  port cannot be placed on the requested subnet's VLAN), the failure is reflected
  on the affected networking resource's status with a diagnostic message.
  [Clarify: D9]

#### Lifecycle Cleanup

- **FR-11:** When a networking resource is deleted, the backend removes that
  resource's fabric configuration and releases any addresses it allocated, without
  affecting other resources. Teardown respects dependency order — an
  ExternalIPAttachment's inbound DNAT is removed before its ExternalIP is released
  back to its pool. [Jira: OSAC-3664; PR review: CodeRabbit]

### 4.2 Non-Functional Requirements

- **NFR-1:** The agentless VLAN backend provides networking for the IPv4 address
  family. IPv6 and dual-stack are not supported in this milestone. [Clarify: D11]
- **NFR-2:** Tenant-observable networking behavior — reachability, isolation,
  external access — is equivalent between the agentless VLAN and Netris backends;
  changing the deployment's backend does not change the tenant-facing API
  contract. [Clarify: D8]
- **NFR-3:** Different VirtualNetworks have no direct connectivity on the internal
  fabric — a machine in one VirtualNetwork cannot reach another VirtualNetwork's
  private subnet addresses, even when their address ranges overlap. Machines
  remain reachable across VirtualNetworks only via their external IPs over the
  external network path (inbound ExternalIP + outbound NATGateway), the same as
  reaching any external endpoint — this is not internal cross-VN routing.
  [Clarify: D12, D15]

## 5. Acceptance Criteria

- [ ] With the agentless VLAN backend configured, a tenant creates a
  VirtualNetwork, Subnet, and SecurityGroup through the API and they reach a ready
  state.
- [ ] A bare-metal server or cluster node attached to an agentless-VLAN subnet
  automatically receives an IP on that subnet, visible in its status.
- [ ] A tenant attaches an ExternalIP to a machine; inbound traffic permitted by
  the machine's SecurityGroup rules reaches the machine.
- [ ] Inbound traffic to a machine's ExternalIP that is not permitted by any
  SecurityGroup rule is blocked.
- [ ] A tenant creates a NATGateway; a subnet machine's permitted outbound traffic
  reaches an external endpoint, which observes the NATGateway's external IP as the
  source address.
- [ ] Outbound traffic not permitted by any SecurityGroup rule cannot leave through
  the NATGateway.
- [ ] A tenant creates a VirtualNetwork with two subnets: machines in the same
  subnet share a broadcast domain, machines in different subnets of that network
  can reach each other when permitted by SecurityGroup rules, and machines in a
  different VirtualNetwork with the same address range cannot reach those private
  addresses directly on the fabric.
- [ ] A machine in one VirtualNetwork can reach a machine in another VirtualNetwork
  via the target's ExternalIP over the external path, even though the target's
  private subnet address remains directly unreachable.
- [ ] Cross-subnet traffic within a VirtualNetwork that is **permitted** by a
  SecurityGroup rule succeeds.
- [ ] Cross-subnet traffic within a VirtualNetwork that is **not permitted** by
  any SecurityGroup rule is blocked.
- [ ] A bare-metal server provisions networking end-to-end through the agentless
  VLAN backend using the same networking API as with Netris (the reference
  validation path this milestone).
- [ ] The backend performs the network-attachment operations required by cluster
  and compute-instance attachments on agentless-VLAN subnets; full end-to-end
  validation for CaaS and VMaaS is covered by their follow-up features
  (OSAC-1611, OSAC-3665).
- [ ] A switch-port/VLAN configuration failure is reflected on the affected
  networking resource's status with a diagnostic message.
- [ ] The same networking API requests produce equivalent tenant-observable
  results on an agentless-VLAN deployment as on a Netris deployment.
- [ ] Selecting between the Netris and agentless VLAN backends is a provider
  configuration — not visible to tenants and requiring no API change.
- [ ] Deleting an ExternalIPAttachment removes the inbound DNAT; deleting its
  ExternalIP releases it back to the pool; neither affects other resources.
- [ ] Deleting a Subnet or VirtualNetwork tears down its fabric configuration and
  releases its addresses without affecting other VirtualNetworks or their
  resources.

## 6. Assumptions

- The OSAC networking API and resource model are complete and stable, inherited
  from the unified networking work and already exercised by the Netris backend;
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

### 8.1 Feature-parity gaps with the Netris backend

- **Owner:** Connectivity & Fabric team
- **Mitigation:** Mirror the closed Netris fabric-manager feature (OSAC-2043) as
  the structural template and validate the agentless VLAN backend
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

Authored: respond @ prd 0.9.0 - a17a43d, workspace main @ 63b090a
Phases: draft, revise, revise, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"a17a43d","source_repo":"63b090a","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["draft","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true} -->
