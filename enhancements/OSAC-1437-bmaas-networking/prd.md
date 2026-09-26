# BMaaS Networking — Single Attachment and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1437 |
| Date        | 2026-09-24 |

> This PRD is an expansion of the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md), scoped to the specific service type. The unified PRD defines the shared architectural requirements and requires connected deployments only; air-gapped and disconnected networking deployments are not supported. This document defines the service-specific requirements and user stories.
Networking resources support read (List/Get), create, and delete. NetworkACL
rules and Subnet-to-ACL associations are immutable after creation. Bare-metal
network attachment fields are also create-time-only; changing one requires
delete and recreate.

BMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## 1. Problem Statement

Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. Tenants cannot attach bare-metal servers to subnets or configure external access through the API, and cannot manage subnet traffic policy through the networking API. The system does not expose which physical network interfaces are available on a bare-metal server, forcing tenants to discover interface names through out-of-band documentation. Creating a reachable bare-metal server with both inbound and outbound connectivity requires sequential API calls to create networking resources and manual coordination with infrastructure administrators for switch port configuration.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can provision a bare-metal server with one explicit network attachment, optionally specifying which physical interface connects to its subnet
- A tenant can create a bare-metal server with `--external-ip-attachment` and have the system allocate an external IP for inbound access automatically
- Network attachments are optional — when omitted, the system attaches the server to the tenant's default subnet, whose associated NetworkACL governs its traffic
- BareMetalInstanceTypes expose available physical network ports through the API (name, role, type, speed) for bare-metal servers
- Bare-metal provisioning uses the provisioning network for inventory and OS provisioning, then moves the selected fabric port to the tenant network and reboots the host so it receives its tenant-network IP
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

- As a Tenant User, I want to create a bare-metal server with one explicit network attachment so that I can connect a selected physical interface to a subnet
- As a Tenant User, I want to see which physical network ports are available on a BareMetalInstanceType so that I can select the appropriate interface when creating the attachment
- As a Tenant User, I want to create a bare-metal server with `--external-ip-attachment` and have it externally reachable in a single API call, without manually creating external IP and attachment resources
- As a Tenant User, I want the sole network attachment to provide the default gateway without needing a second attachment
- As a Tenant User, I want auto-provisioned external IPs to be automatically cleaned up when I delete the server, so that I do not accumulate orphaned resources
- As a Tenant User, I want network interface validation when creating the attachment so that I get a clear error if I specify a port that does not exist or is not tenant-attachable

### Tenant Admin Stories

- As a Tenant Admin, I want visibility into which physical interfaces are connected to which subnets and which NetworkACL governs each subnet so that I can troubleshoot connectivity and understand its traffic policy

### Cloud Infrastructure Admin Stories

- As a Cloud Infrastructure Admin, I want to define available physical ports for each BareMetalInstanceType (name, role, type, speed) so that tenants can discover and select the correct interface

### Cloud Provider Admin Stories

- As a Cloud Provider Admin, I want to see which IP addresses were allocated to each network interface on a bare-metal server so that I can troubleshoot connectivity and external access configuration

## 4. Requirements

### 4.1 Functional Requirements

#### Network Attachment Specification

- **FR-1:** Tenants can specify zero or one entry in the repeated `network_attachments` field when creating a bare-metal server. The attachment may omit its subnet or physical interface; missing fields are defaulted without replacing supplied values. The complete resolved list and every entry field are immutable after creation. The repeated field is retained for API compatibility; more than one entry is rejected. Traffic policy comes from the NetworkACL associated with the resolved Subnet, not from the attachment. [User]

#### BareMetalInstanceType Network Port Discovery

- **FR-2:** The BareMetalInstanceType API exposes available physical network ports. Each port includes a name (e.g., "data-0"), role (e.g., "fabric", "management", "storage"), type, and speed. Ports are ordered; when multiple ports share the same role, the first in the list is the default for that role. [User]

#### Interface Validation

- **FR-3:** The system validates that the physical interface specified in the sole network attachment exists in the BareMetalInstanceType's `network_ports` list. A request containing more than one attachment is rejected. [User]

#### Primary Gateway Designation

- **FR-4:** When one network attachment exists, it is the primary attachment and provides the default gateway. The `primary` designation is optional; omission or `primary: true` has the same meaning, while `primary: false` is rejected. [User]

#### Optional Network Attachments with Defaults

- **FR-5:** Network attachments are optional when creating a bare-metal server. When omitted or empty, the system attaches the server to the tenant's default subnet and uses the first `fabric` port from the BareMetalInstanceType (see Default Networking PRD). When a single attachment is supplied, only missing subnet or interface fields are defaulted; supplied values are preserved. The NetworkACL associated with the resolved Subnet governs the server's traffic. If the BareMetalInstanceType has no valid fabric port, creating a server without an explicit interface fails with a clear error. The resolved attachment is stored with the server so the server is self-describing after creation. [User]

#### Auto External IP

- **FR-6:** Bare-metal servers support `--external-ip-attachment`. When enabled, the system auto-selects the external IP pool with the most available capacity, allocates an external IP, and creates an external IP attachment binding it to the server's primary attachment subnet IP. The external IP and attachment are labeled as auto-provisioned. [User]

#### Network Connectivity Configuration

- **FR-7:** The host remains on the provisioning network through OS provisioning. After provisioning completes, the system moves the selected fabric port to the tenant network, reboots the host, and allows the host to obtain an IP through tenant-network DHCP. [User]

#### IP Address Visibility

- **FR-8:** The allocated IP address for the network attachment is visible in the bare-metal server status after network connectivity is configured. [User]

#### External IP Attachment for Bare-Metal

- **FR-9:** External IP attachments support bare-metal servers as an attachment target type. When an external IP is attached to a bare-metal server, inbound traffic to the external IP is routed to the server's primary attachment IP. [User]

#### Network Automation Backend Configuration

- **FR-10:** The system manages network automation backend selection without tenant involvement. The provider configures which network automation backend handles bare-metal networking; this configuration is separate from the networking resource hierarchy and is not visible to tenants. [User]

#### Auto-Cleanup on Deletion

- **FR-11:** When a bare-metal server is deleted, if external IP and external IP attachment were auto-provisioned (labeled as auto-provisioned), the system deletes the external IP attachment first, then the external IP. Manually created resources are NOT cleaned up. Default networking resources (virtual network, subnet, NetworkACL, NATGateway) are NOT cleaned up. [User]

#### Network Attachment Deletion

- **FR-12:** During bare-metal server deletion, the system deconfigures network connectivity for the selected interface and releases the allocated IP address. [User]

#### NetworkACL Policy

- **FR-13:** Bare-metal server traffic follows the NetworkACL associated with its Subnet. Each Subnet has exactly one active association, and an ACL may be reused by Subnets in the same VirtualNetwork. Ingress and egress rules are evaluated independently in ascending priority order; the first matching rule allows or denies traffic, and traffic with no matching rule is denied. The policy is stateless, so return traffic requires an explicit rule in the reverse direction. Traffic between workloads on the same Subnet is not filtered by the Subnet NetworkACL; traffic between Subnets must satisfy the source Subnet's egress policy and the destination Subnet's ingress policy. The same policy applies to every workload on the Subnet. [User]

### 4.2 Non-Functional Requirements

- **NFR-1:** Auto external IP allocation completes synchronously within the create API call (no async allocation delay). If no pool has available capacity, the create API call returns an error. [User]

- **NFR-2:** Network attachment provisioning (connectivity configuration) completes within 2 minutes for the selected interface. [User]

## 5. Acceptance Criteria

- [ ] A Tenant User can create a bare-metal server with one explicit network attachment and an optional physical interface from the BareMetalInstanceType; the server follows the NetworkACL associated with that Subnet
- [ ] A Tenant User can create a bare-metal server with `--external-ip-attachment` and no explicit network attachments — the server is created on the default subnet with an auto-provisioned external IP for inbound access
- [ ] A bare-metal server with one attachment is provisioned with that attachment providing the default gateway
- [ ] Auto-created external IP and external IP attachment are labeled as auto-provisioned and visible in list views
- [ ] Deleting a bare-metal server with auto-provisioned external IP causes the auto-created external IP and external IP attachment to be cleaned up automatically
- [ ] BareMetalInstanceType API returns structured physical network ports (name, role, type, speed)
- [ ] Creating a bare-metal server with an invalid interface (not in the BareMetalInstanceType's `network_ports` list) returns an error
- [ ] Creating a bare-metal server with `primary: false` returns an error
- [ ] Creating a bare-metal server with more than one network attachment returns a maximum-one error
- [ ] Bare-metal server primary attachment IP is visible in status after network connectivity is configured
- [ ] External IP attachment with bare-metal server target routes inbound traffic to the server's primary attachment IP
- [ ] Bare-metal traffic uses the first matching NetworkACL rule by priority, unmatched traffic is denied, and return traffic requires an explicit reverse-direction rule

## 6. Assumptions

- The tenant has a default VirtualNetwork and Subnet pre-created at onboarding, with a default NetworkACL associated with that Subnet (see Default Networking PRD). If defaults are not configured, creating a server without explicit network attachments fails with a clear error.
- The NetworkClass has a fabric manager configured (the system can resolve which network automation to use).
- The BareMetalInstanceType for the bare-metal template has a populated `network_ports` list with at least one `fabric` port. If no valid fabric port exists, creating a server without an explicit interface fails with a clear error.
- Out-of-band provisioning interfaces (PXE boot, BMC) are reserved for system use and are NOT tenant-attachable (should not appear in network attachments).

## 7. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, NetworkACL, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking)
- **Default Networking PRD** — default Subnet selection and associated NetworkACL behavior defined in [Default Networking PRD](/enhancements/OSAC-1433-default-networking)
- **Networking manager dispatch** — the system must be able to route networking operations to the correct fabric manager (in progress)
- **NAT gateway support** — outbound NAT must be available as a networking resource
- **External access for BM targets** — the external IP attachment system must support bare-metal servers as targets
- **CLI support** — the CLI must support specifying network attachments when creating bare-metal servers
- **Fabric manager BM networking role** — at least one fabric manager must implement the switch port configuration role for bare-metal servers

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

### ~~9.1 Should the out-of-band provisioning interface be explicitly excluded from validation or just documented?~~ — Resolved

Resolved: Explicitly excluded in validation. Lifecycle and BMC interfaces are not tenant-attachable and are rejected during server validation. This is not just documented — it is enforced.

### ~~9.2 Should capacity exhaustion return an API error or create a failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

### ~~9.3 What is the interface selection logic when network attachments are omitted and the BareMetalInstanceType has multiple fabric ports?~~ — Resolved

Resolved: First in the list. Ports are ordered in the BareMetalInstanceType; when multiple ports share the same role, the first one is the default. This is already defined in FR-2.

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"06d340f90","source_repo_branch":"main","commits_behind_main":43,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
