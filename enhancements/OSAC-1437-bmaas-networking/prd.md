# BMaaS Networking — Network Attachments and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1437 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared networking resources and operation contract; the [Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology) defines the IPv4 topology, and its [deployment support boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary) requires connected deployments and excludes air-gapped deployments. This document defines the BMaaS-specific requirements and user stories.

BMaaS follows the shared [strict dependency-ready creation
contract](/enhancements/OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation): resolved networking references, BareMetalInstanceType, and provisioning inputs must be Ready before BaremetalInstance or private worker persistence. Only OSAC-owned automatic ExternalIP children may be created Pending after a Ready pool and capacity validation.

## 1. Problem Statement

Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. Tenants cannot attach bare-metal servers to subnets, apply SecurityGroups and network ACLs, or configure external access through the API. The system does not expose which physical network interfaces are available on a bare-metal server, forcing tenants to discover interface names through out-of-band documentation. Creating a reachable bare-metal server with both inbound and outbound connectivity requires sequential API calls to create networking resources and manual coordination with infrastructure administrators for switch port configuration.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can provision a bare-metal server with one explicit network attachment specifying which physical interface connects to which subnet
- A tenant can create a bare-metal server with `--external-ip-attachment` and have the system allocate an external IP for inbound access automatically
- Network attachments are optional — when omitted or empty, the system
  attaches the server to the tenant's default Subnet and default SecurityGroup;
  the effective NetworkACL is inherited from that Subnet
- BareMetalInstanceTypes expose available physical network ports through the API (name, role, type, speed) for bare-metal servers
- BMaaS provisions the host on a provisioning network and establishes the tenant attachment after OS provisioning, before the server becomes Ready
- External IP attachments support bare-metal servers as a target type
- The system uses a distinct configuration parameter for network automation backend selection, separate from the networking resource hierarchy

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| BM provisioning time with networking | <5 min | N/A (no baseline) |
| Network connectivity configuration success rate | >95% | N/A |

### 2.3 Non-Goals

- Cluster or VM networking (this PRD covers bare-metal servers only; clusters and VMs are addressed in separate enhancements)
- Network provisioning infrastructure implementation (deferred to Unified Networking EP implementation)
- Fabric manager implementation (network fabric automation via templates)
- NIC failover or bonding (out of scope)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a bare-metal server with one explicit network attachment so that I can connect one physical interface to one subnet
- As a Tenant User, I want to see which physical network ports are available on a BareMetalInstanceType so that I can select the one interface used for my tenant network
- As a Tenant User, I want to create a bare-metal server with `--external-ip-attachment` and have it externally reachable in a single API call, without manually creating external IP and attachment resources
- As a Tenant User, I want auto-provisioned external IPs to be automatically cleaned up when I delete the server, so that I do not accumulate orphaned resources
- As a Tenant User, I want network interface validation when creating the attachment so that I get a clear error if I specify an interface that doesn't exist

### Tenant Admin Stories

- As a Tenant Admin, I want visibility into which physical interface is connected to the server's subnet so that I can troubleshoot network connectivity issues

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define available physical ports in each BareMetalInstanceType (name, role, type, speed) so that tenants can discover and select the correct interface

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see the IP address allocated to the selected network interface on a bare-metal server so that I can troubleshoot connectivity and external access configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment Specification

- **FR-1:** Tenants can specify the repeated `network_attachments` field, carrying `BareMetalNetworkAttachment` values, when creating a bare-metal server, but validation accepts at most one entry. The entry identifies an optional Subnet, SecurityGroup list, and physical interface to use; its effective NetworkACL is inherited from the Subnet. The complete list and every entry field are immutable after creation; the single entry is implicitly the default gateway. [User]

#### BareMetalInstanceType Network Port Discovery

- **FR-2:** The BareMetalInstanceType API exposes available physical network ports. Each port includes a name (e.g., "data-0"), role (e.g., "fabric", "management", "storage"), type, and speed. Ports are ordered; when multiple ports share the same role, the first in the list is the default for that role. [User]

#### Interface Validation

- **FR-3:** The system validates that the physical interface specified in the attachment exists in the BareMetalInstanceType's `network_ports` list. A request containing more than one attachment is rejected. [User]

#### Default Gateway

- **FR-4:** The single network attachment is implicitly the primary attachment and provides the default gateway. [User]

#### Optional Network Attachments with Defaults

- **FR-5:** Network attachments are optional when creating a bare-metal server.
  When omitted or empty, the system attaches the server to the tenant's
  default Subnet, uses the default SecurityGroup, and selects
  the BareMetalInstanceType's first `fabric` port. The effective NetworkACL is
  inherited from the selected Subnet. When a Subnet, SecurityGroup list, or
  interface is missing from a supplied attachment, only that field is
  defaulted. The tenant default SecurityGroup is used only with the tenant
  default VirtualNetwork; a non-default Subnet without a compatible explicit
  group is rejected. A selected Subnet without a Ready effective ACL is
  rejected until an ACL is associated. If the profile has no fabric port, creating a server without an
  explicit interface fails with a clear error. The resolved attachment is
  stored with the server so it is self-describing after creation. [User]

#### Auto External IP

- **FR-6:** Bare-metal servers support `--external-ip-attachment`. When
  enabled, the system reserves capacity in the ExternalIPPool and creates a
  Pending ExternalIP and ExternalIPAttachment binding it to the server's
  single attachment subnet IP. Selected-manager allocation, server IP discovery, DNAT
  programming, and activation occur asynchronously. The external IP and
  attachment are labeled with `osac.openshift.io/auto-created: "true"`. [User]

#### Network Connectivity Configuration

- **FR-7:** BMaaS provisions the server on the deployment provisioning network, then moves the selected fabric port to the tenant subnet after OS provisioning, reboots the server, and discovers its tenant-network IP before the server becomes Ready. [User]

#### IP Address Visibility

- **FR-8:** The allocated IP address for the single network attachment is visible in the bare-metal server status after network connectivity is configured. [User]

#### External IP Attachment for Bare-Metal

- **FR-9:** External IP attachments support bare-metal servers as an attachment target type. When an external IP is attached to a bare-metal server, inbound traffic to the external IP is routed to the single attachment's IP. [User]

#### Network Automation Backend Configuration

- **FR-10:** The system manages network automation backend selection without tenant involvement. The provider configures which network automation backend handles bare-metal networking; this configuration is separate from the networking resource hierarchy and is not visible to tenants. [User]

#### Auto-Cleanup on Deletion

- **FR-11:** When a bare-metal server is deleted, only an ExternalIP and ExternalIPAttachment carrying the canonical auto-created marker and an exact immutable BaremetalInstance owner relationship are eligible for cleanup. The system deletes the ExternalIPAttachment first, then the ExternalIP. A label or target reference alone is not sufficient ownership proof. Manually created resources are NOT cleaned up. Default networking resources (VirtualNetwork, Subnet, SecurityGroup, NetworkACL, NATGateway) are NOT cleaned up. [User]

#### Network Attachment Deletion

- **FR-12:** During bare-metal server deletion, the system deconfigures the selected network interface and releases its allocated IP address. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Pool capacity validation and creation of Pending ExternalIP
  and ExternalIPAttachment records complete synchronously within the create
  API call. Selected-manager allocation, server IP discovery, DNAT programming, and the
  transition to Ready are asynchronous. The ExternalIP transitions
  `Pending -> Allocated`; the ExternalIPAttachment transitions
  `Pending -> Ready` only after the server attachment IP is discovered and
  DNAT succeeds. If no pool has available capacity, the create call fails
  atomically. [User]

- **NFR-2:** Network attachment provisioning (connectivity configuration) completes within 2 minutes for the server's single attachment. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a bare-metal server with one explicit network attachment specifying a physical interface from the BareMetalInstanceType
- [ ] A bare-metal attachment may include a unique typed SecurityGroup list;
  omitted groups receive the tenant default only when the resolved Subnet is in
  the tenant default VirtualNetwork, while every explicit group is Ready,
  same-tenant, and in the attachment's VN. A non-default-VN Subnet without a
  compatible explicit group is rejected
- [ ] Tenant-created SecurityGroups require at least one allow-only rule;
  default SecurityGroups may be empty and mean deny. A SecurityGroup action
  field or deny rule is rejected
- [ ] A Tenant User can create a bare-metal server with `--external-ip-attachment` and no explicit network attachments — the server is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] A bare-metal server with one network attachment is provisioned on the provisioning network, then handed off to the tenant subnet through the selected interface, which provides the default gateway
- [ ] Auto-created external IP and external IP attachment are labeled with `osac.openshift.io/auto-created: "true"` and visible in list views
- [ ] Deleting a bare-metal server with auto-provisioned external IP causes the auto-created external IP and external IP attachment to be cleaned up automatically
- [ ] BareMetalInstanceType API returns structured network port data (name, role, type, speed)
- [ ] Creating a bare-metal server with an invalid interface (not in the BareMetalInstanceType's `network_ports` list) returns an error
- [ ] Creating a bare-metal server with more than one network attachment returns a single-NIC validation error
- [ ] Bare-metal server attachment IP is visible in status after network connectivity is configured
- [ ] External IP attachment with bare-metal server target routes inbound traffic to the server's single attachment IP
- [ ] Updating or patching `network_attachments`, `auto_external_ip_attachment`, or any attachment field is rejected under the [unified networking operation contract](/enhancements/OSAC-1433-unified-networking/prd.md#network-operation-contract)

## 6. Assumptions

- The tenant has default networking resources (VirtualNetwork and Subnet),
  plus a default SecurityGroup and NetworkACL from the complete manager
  profile, pre-created at onboarding (see Default
  Networking PRD).
  If defaults are not configured, creating a server without explicit network
  attachments fails with a clear error.
- The deployment has a complete manager configured for BMaaS switch-port
  movement and DHCP operations; the per-resource dispatch targets are resolved
  by the provider from the deployment NetworkClass. Native Kubernetes
  NetworkPolicy alone is not sufficient for either OSAC policy contract. The
  BMaaS physical handoff uses the manager's BM operations.
- The BareMetalInstanceType for the bare-metal template has at least one `fabric` port. If it does not, creating a server with explicit network attachments fails with a clear error.
- Out-of-band provisioning interfaces (PXE boot, BMC) are reserved for system use and are NOT tenant-attachable (should not appear in network attachments).

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, NetworkACL, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default Subnet, SecurityGroup, and NetworkACL selection behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **Networking manager dispatch** — the system must route each shared
  networking resource operation to every configured manager; BM-specific port
  movement and DHCP discovery are part of the complete manager handoff
  operations
- **NAT gateway support** — outbound NAT is part of the complete manager
  contract; an unfinished backend may use the approved successful no-op AAP
  role
- **External access for BM targets** — the external IP attachment system must support bare-metal servers as targets
- **CLI support** — the CLI must support specifying network attachments when creating bare-metal servers
- **CLI contract** — one optional `--network-attachment` value maps to the repeated `network_attachments` field and carries `subnet`, optional `security-groups`, and optional `interface` keys; a second value, `network-acls`, lifecycle interface, `primary: false`, or any update/patch is rejected
- **Auto ExternalIP CLI contract** — `--external-ip-attachment` maps to `auto_external_ip_attachment: true`; omission maps to false and the field is immutable after creation
- **Fabric-manager BM handoff** — the complete manager profile includes
  bare-metal switch-port movement and DHCP discovery. While the provider
  implementation is being completed, the corresponding AAP operations may use
  the approved successful no-op path; no partial manager/API path is exposed.

## 8. Risks

### 8.1 Network automation implementation blocked or delayed

- **Owner:** Platform team
- **Mitigation:** Network automation core tasks (OSAC-1457, OSAC-1458, OSAC-1460) are in progress. If network automation is not ready, bare-metal networking cannot function. Prioritize completing network automation core before bare-metal networking implementation.

### 8.2 Fabric-manager BM handoff delayed

- **Owner:** Network automation team
- **Mitigation:** The provider admits only a complete manager profile. During
  development, unfinished `move_network_attachment` or `query_dhcp_lease`
  operations use the approved successful no-op AAP path; BMaaS does not expose
  a tenant-visible partial-manager flow.

### 8.3 IP address feedback mechanism fails

- **Owner:** Platform team
- **Mitigation:** If the DHCP lease query or operator status-feedback path fails, the external IP attachment cannot configure inbound NAT. Validate the `query_dhcp_lease` dispatcher call, MAC-to-lease matching, CR status update, and fulfillment-service feedback during integration testing. The BaremetalInstance remains non-Ready and the attachment remains Pending until the path recovers; there is no manual tenant fallback.

### 8.4 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### ~~9.1 Should the out-of-band provisioning interface be explicitly excluded from validation or just documented?~~ — Resolved

Resolved: Explicitly excluded in validation. Lifecycle and BMC interfaces are not tenant-attachable and are rejected during server validation. This is not just documented — it is enforced.

### ~~9.2 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

### ~~9.3 What is the interface selection logic when network attachments are omitted and the BareMetalInstanceType has multiple fabric ports?~~ — Resolved

Resolved: First in the list. Network ports are ordered in the BareMetalInstanceType; when multiple ports share the same role, the first one is the default. This is already defined in FR-2.
