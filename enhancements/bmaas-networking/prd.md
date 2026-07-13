# BMaaS Networking — Network Attachments and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1437 |
| Date        | 2026-07-08 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements; this document defines the service-specific requirements and user stories.

## 1. Problem Statement

Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. Tenants cannot attach bare-metal servers to subnets, apply security groups, or configure external access through the API. The system does not expose which physical network interfaces are available on a bare-metal server, forcing tenants to discover interface names through out-of-band documentation. Creating a reachable bare-metal server with both inbound and outbound connectivity requires sequential API calls to create networking resources and manual coordination with infrastructure administrators for switch port configuration.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can provision a bare-metal server with explicit network attachments, each specifying which physical interface connects to which subnet
- A tenant can create a bare-metal server with `--external-ip-attachment` and have the system allocate an external IP for inbound access automatically
- Network attachments are optional — when omitted, the system attaches the server to the tenant's default subnet and security group
- Host types expose available physical network interfaces through the API (name, role, description) for bare-metal servers
- Network connectivity for each attachment is established before bare-metal OS provisioning begins
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
- Multi-interface failover or bonding (out of scope for initial implementation)

## 3. User Stories

### Tenant User Stories

- As a Tenant User, I want to create a bare-metal server with explicit network attachments so that I can connect specific physical interfaces to specific subnets
- As a Tenant User, I want to see which physical network interfaces are available on a host type so that I can select the appropriate interface when creating network attachments
- As a Tenant User, I want to create a bare-metal server with `--external-ip-attachment` and have it externally reachable in a single API call, without manually creating external IP and attachment resources
- As a Tenant User, I want to create a multi-homed bare-metal server (multiple network attachments) and designate which interface provides the default gateway
- As a Tenant User, I want auto-provisioned external IPs to be automatically cleaned up when I delete the server, so that I do not accumulate orphaned resources
- As a Tenant User, I want network interface validation when creating attachments so that I get clear errors if I specify an interface that doesn't exist or attach the same interface to multiple subnets

### Tenant Admin Stories

- As a Tenant Admin, I want visibility into which physical interfaces are connected to which subnets for a bare-metal server so that I can troubleshoot network connectivity issues

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define available physical interfaces for each host type (name, role, description) so that tenants can discover and attach to the correct interfaces

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see which IP addresses were allocated to each network interface on a bare-metal server so that I can troubleshoot connectivity and external access configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment Specification

- **FR-1:** Tenants can specify network attachments when creating a bare-metal server. Each attachment identifies a subnet (required, immutable), security groups (modifiable), which physical interface to use (optional, immutable), and whether this attachment provides the default gateway for multi-homed servers (immutable). [User]

#### Host Type Interface Discovery

- **FR-2:** The host type API exposes available physical network interfaces for bare-metal host types. Each interface includes a name (e.g., "data-0"), role (e.g., "primary-traffic", "management", "storage"), and description (e.g., "100GbE primary traffic interface"). VM host types do not expose interface lists. Interfaces are ordered; when multiple interfaces share the same role, the first in the list is the default for that role. [User]

#### Interface Validation

- **FR-3:** The system validates that each physical interface specified in network attachments exists in the host type's interface list. The same interface cannot appear in multiple attachments. If more than one attachment is specified, each must identify an explicit physical interface (multiple attachments without interface names is invalid). The number of attachments cannot exceed the number of available interfaces on the host type. [User]

#### Primary Gateway Designation

- **FR-4:** When a bare-metal server has multiple network attachments, exactly one must be designated as the primary attachment (provides default gateway). When only one attachment exists, the primary designation is optional and treated as implicit. [User]

#### Optional Network Attachments with Defaults

- **FR-5:** Network attachments are optional when creating a bare-metal server. When omitted, the system attaches the server to the tenant's default subnet and default security group, using the host type's default interface (see Default Networking PRD). If the host type has no default interface, creating a server without explicit network attachments fails with a clear error. The resolved attachments are stored with the server so the server is self-describing after creation. [User]

#### Auto External IP

- **FR-6:** Bare-metal servers support `--external-ip-attachment`. When enabled, the system auto-selects the external IP pool with the most available capacity, allocates an external IP, and creates an external IP attachment binding it to the server's primary attachment subnet IP. The external IP and attachment are labeled as auto-provisioned. [User]

#### Network Connectivity Configuration

- **FR-7:** Network connectivity for each attachment is established before bare-metal OS provisioning begins. The system configures connectivity for each interface-to-subnet mapping; all attachments must be ready before provisioning proceeds. After the server boots, it receives an IP address on the configured subnet. [User]

#### IP Address Visibility

- **FR-8:** The allocated IP address for each network attachment is visible in the bare-metal server status after network connectivity is configured. [User]

#### External IP Attachment for Bare-Metal

- **FR-9:** External IP attachments support bare-metal servers as an attachment target type. When an external IP is attached to a bare-metal server, inbound traffic to the external IP is routed to the server's primary attachment IP. [User]

#### Network Automation Backend Configuration

- **FR-10:** The system manages network automation backend selection without tenant involvement. The provider configures which network automation backend handles bare-metal networking; this configuration is separate from the networking resource hierarchy and is not visible to tenants. [User]

#### Auto-Cleanup on Deletion

- **FR-11:** When a bare-metal server is deleted, if external IP and external IP attachment were auto-provisioned (labeled as auto-provisioned), the system deletes the external IP attachment first, then the external IP. Manually created resources are NOT cleaned up. Default networking resources (virtual network, subnet, security group, NATGateway) are NOT cleaned up. [User]

#### Network Attachment Deletion

- **FR-12:** During bare-metal server deletion, the system deconfigures network connectivity for each interface and releases allocated IP addresses. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Auto external IP allocation completes synchronously within the create API call (no async allocation delay). If no pool has available capacity, the create API call returns an error. [User]

- **NFR-2:** Network attachment provisioning (connectivity configuration) completes within 2 minutes per interface. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a bare-metal server with explicit network attachments, each specifying a physical interface from the host type
- [ ] A Tenant User can create a bare-metal server with `--external-ip-attachment` and no explicit network attachments — the server is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] A multi-interface bare-metal server (multiple network attachments) is provisioned with network connectivity configured for each interface, primary attachment providing default gateway
- [ ] Auto-created external IP and external IP attachment are labeled as auto-provisioned and visible in list views
- [ ] Deleting a bare-metal server with auto-provisioned external IP causes the auto-created external IP and external IP attachment to be cleaned up automatically
- [ ] Host type API returns structured physical network interface list for bare-metal host types (name, role, description)
- [ ] Creating a bare-metal server with an invalid interface (not in host type's list) returns an error
- [ ] Creating a bare-metal server with duplicate interfaces across attachments returns an error
- [ ] Bare-metal server primary attachment IP is visible in status after network connectivity is configured
- [ ] External IP attachment with bare-metal server target routes inbound traffic to the server's primary attachment IP

## 6. Assumptions

- The tenant has default networking resources (virtual network, subnet, security group) pre-created at onboarding (see Default Networking PRD). If defaults are not configured, creating a server without explicit network attachments fails with a clear error.
- The target region's networking infrastructure has fabric manager configured (the system can resolve which network automation to use).
- The host type for the bare-metal template has a populated physical network interface list. If the list is empty, creating a server with explicit network attachments fails with a clear error.
- Out-of-band provisioning interfaces (PXE boot, BMC) are reserved for system use and are NOT tenant-attachable (should not appear in network attachments).

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Default Networking PRD** — default Subnet and SecurityGroup selection behavior defined in [Default Networking PRD](/enhancements/default-networking)
- **Networking manager dispatch** — the system must be able to route networking operations to the correct fabric manager (in progress)
- **NAT gateway support** — outbound NAT must be available as a networking resource
- **External access for BM targets** — the external IP attachment system must support bare-metal servers as targets
- **CLI support** — the CLI must support specifying network attachments when creating bare-metal servers
- **Fabric manager BM networking role** — at least one fabric manager (e.g., Netris) must implement the switch port configuration role for bare-metal servers

## 8. Risks

### 8.1 Network automation implementation blocked or delayed

- **Owner:** Platform team
- **Mitigation:** Network automation core tasks (OSAC-1457, OSAC-1458, OSAC-1460) are in progress. If network automation is not ready, bare-metal networking cannot function. Prioritize completing network automation core before bare-metal networking implementation.

### 8.2 Fabric manager bare-metal support blocked

- **Owner:** Network automation team
- **Mitigation:** Fabric manager bare-metal networking role (OSAC-2081) is new. If fabric manager does not implement bare-metal network attachment creation and deletion, switch port configuration will fail. Coordinate with fabric manager team to prioritize bare-metal support.

### 8.3 IP address feedback mechanism fails

- **Owner:** Platform team
- **Mitigation:** If the fabric manager does not write the allocated IP to server status, external IP attachment cannot configure inbound NAT. Validate IP feedback mechanism during integration testing. Fallback: manual IP lookup from fabric manager API (deferred to future enhancement).

### 8.4 External IP pool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

## 9. Open Questions

### 9.1 Should the out-of-band provisioning interface be explicitly excluded from validation or just documented?

- **Owner:** API design team
- **Impact:** Affects FR-3. Current proposal: document that out-of-band interfaces are reserved for provisioning, do not enforce exclusion in validation. Alternative: explicitly reject attachments with out-of-band interfaces.

### 9.2 Should capacity exhaustion return an API error or create a failed resource?

- **Owner:** API design team
- **Impact:** Affects FR-6 and NFR-1. Returning an error (resource not persisted) is simpler but gives no audit trail. Creating a failed resource provides visibility but adds cleanup burden.

### 9.3 What is the interface selection logic when network attachments are omitted and the host type has multiple primary traffic interfaces?

- **Owner:** Platform team
- **Impact:** Affects FR-5. Current proposal: use the first primary traffic interface in the host type's ordered list. Alternative: require explicit interface when multiple primary traffic interfaces exist, or use a specific naming convention (e.g., "data-0").
