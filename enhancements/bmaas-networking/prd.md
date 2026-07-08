# BMaaS Networking — Network Attachments and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1437 |
| Date        | 2026-07-08 |

## 1. Problem Statement

BaremetalInstance has no networking fields. Tenants cannot attach bare-metal servers to subnets, apply security groups, or configure switch ports for tenant workloads. Provisioning bare-metal servers requires manual switch configuration outside the OSAC API. The two-operator architecture (bare-metal-fulfillment-operator for provisioning, osac-operator for feedback) lacks a networking reconciliation phase to integrate with the unified networking API. ExternalIPAttachment does not support `baremetal_instance` as an attachment target, preventing inbound external access to BM servers. The `NetworkClass` field populated from inventory collides with the OSAC NetworkClass CRD (different concepts, same name).

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a BaremetalInstance with explicit network attachments, each specifying a physical interface from the HostType's interface list
- A tenant can create a BaremetalInstance with `--external-ip=auto` and have the system allocate an ExternalIP and attach it automatically
- A tenant can create a BaremetalInstance with `--nat-gateway=auto` and have the system provision or reuse a NATGateway on the BM's VirtualNetwork for outbound connectivity
- Optional `network_attachments` field — when omitted, the system populates with tenant's default Subnet and SecurityGroup
- HostType resource extended with structured NetworkInterface list (name, role, description) for BM host types to define available physical interfaces
- bare-metal-fulfillment-operator adds `reconcileNetworking` phase that calls dispatcher to configure switch ports for each attachment
- ExternalIPAttachment supports `baremetal_instance` target type
- Rename BaremetalInstance spec field `networkClass` → `networkFabricManager` to avoid CRD name collision

### 2.2 Success Metrics

| Metric | Target | Baseline |
|--------|--------|----------|
| BM provisioning time with networking | <5 min | N/A (no baseline) |
| Switch port configuration success rate | >95% | N/A |

### 2.3 Non-Goals

- CaaS or VMaaS networking (this PRD covers BMaaS only; Cluster and ComputeInstance are addressed in separate enhancements)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Fabric manager implementation (Netris BM role implementation via dispatcher)
- Multi-interface failover or bonding (out of scope for initial implementation)

## 3. Requirements

### 3.1 Functional Requirements

#### BareMetalNetworkAttachment Proto

- **FR-1:** Create `BareMetalNetworkAttachment` message with fields: `subnet` (Subnet ID, required, immutable), `security_groups` (SecurityGroup IDs, mutable), `interface` (physical interface name from HostType, optional, immutable), and `primary` (boolean, immutable) to designate which attachment provides the default gateway for multi-homed servers. [Source: `.planning/bmaas-networking-design.md` — API Changes]

#### HostType NetworkInterface List

- **FR-2:** Extend HostType proto with `repeated NetworkInterface interfaces` field. NetworkInterface message has `name` (e.g., "data-0"), `role` (e.g., "fabric", "management", "storage", "lifecycle"), and `description` (e.g., "100GbE data interface"). The field is only populated for BM host types (empty for VM host types). Interfaces are ordered; when multiple interfaces share the same role, the first in the list is the default for that role. [Source: `.planning/bmaas-networking-design.md` — HostType and Interface Validation]

#### Interface Validation

- **FR-3:** fulfillment-service validates that each `interface` in `network_attachments` exists in the HostType's NetworkInterface list. The same interface cannot appear in multiple attachments. If >1 attachment, each must have an explicit `interface` (multiple attachments without `interface` is invalid). Number of attachments ≤ number of available interfaces on the template. [Source: `.planning/bmaas-networking-design.md` — Server Validation Rules]

#### Primary Field

- **FR-4:** When a BaremetalInstance has multiple `network_attachments`, exactly one must have `primary: true`. When only one attachment exists, `primary` is optional and treated as implicit. The operator CRD validates this constraint via CEL. [Source: `.planning/bmaas-networking-design.md` — Operator CRD]

#### Optional Network Attachments with Defaults

- **FR-5:** The `network_attachments` field on BareMetalInstanceSpec is optional. When omitted, the fulfillment-service populates it with the tenant's default Subnet and default SecurityGroup, using the first "fabric" role interface from the HostType (see Simplified Resource Creation PRD). The resolved attachments are stored in the resource spec so the resource is self-describing after creation. [Source: `.planning/bmaas-networking-design.md` — Proposed Flow, step 5]

#### Auto ExternalIP

- **FR-6:** BareMetalInstanceSpec supports an `external_ip_mode` field with values `NONE` (default) and `AUTO`. When `AUTO`, the system auto-selects the READY ExternalIPPool with the most available capacity, creates an ExternalIP, and creates an ExternalIPAttachment binding it to the BM's primary attachment subnet IP. The ExternalIP and ExternalIPAttachment are labeled `osac.openshift.io/auto-provisioned: "true"`. [Source: `.planning/bmaas-networking-design.md` — Proposed Flow, step 5]

#### Auto NATGateway

- **FR-7:** BareMetalInstanceSpec supports a `nat_gateway_mode` field with values `NONE` (default) and `AUTO`. When `AUTO`, the system creates a NATGateway on the BM's VirtualNetwork (reuses existing NATGateway if one already exists, regardless of state or whether it was manually or auto-created). The NATGateway uses an auto-selected ExternalIP as the SNAT source. [Source: `.planning/bmaas-networking-design.md` — Proposed Flow, step 5]

#### bare-metal-fulfillment-operator reconcileNetworking Phase

- **FR-8:** bare-metal-fulfillment-operator BareMetalInstance controller adds a `reconcileNetworking` phase that runs after `reconcileInventory` (host assignment) and before `reconcileProvisioning` (OS provisioning). For each attachment, the controller calls dispatcher → `osac.templates.{{ fabric_manager }}.create_network_attachment` passing `host_id` (ExternalHostID), `host_class`, `interface`, `subnet_ref`, `security_group_refs`, `primary`. The fabric manager resolves the host identity to a fabric server, adds the server's interface to the subnet's fabric segment, and allocates an IP (DHCP or static). Network attachments must be Ready before provisioning proceeds. [Source: `.planning/bmaas-networking-design.md` — Proposed Flow, step 6b]

#### IP Address Feedback

- **FR-9:** The `create_network_attachment` role writes the allocated IP to the BaremetalInstance CR status (`networkAttachments[].ipAddress`). The feedback controller syncs this to fulfillment-service. The ExternalIPAttachment controller reads the primary IP from the BM's status to create the DNAT rule. [Source: `.planning/bmaas-networking-design.md` — The IP Address Feedback Question, Option A]

#### ExternalIPAttachment BM Target Support

- **FR-10:** ExternalIPAttachment CRD and proto support `baremetal_instance` as an attachment target type. The controller reads the BM's primary attachment IP from status and passes it to the fabric manager's `create_external_ip_attachment` role to create the DNAT rule. [Source: `.planning/bmaas-networking-design.md` — Proposed Flow, step 9]

#### NetworkFabricManager Rename

- **FR-11:** Rename BaremetalInstance spec field `networkClass` → `networkFabricManager`. Update fulfillment-service proto, operator CRD, and bare-metal-fulfillment-operator to use the new field name. The field is a static config string set at operator startup (e.g., "openstack"), not a reference to the OSAC NetworkClass CRD. [Source: `.planning/bmaas-networking-design.md` — Current State, What's Missing]

#### mutateBMI Update

- **FR-12:** The `mutateBMI()` function in fulfillment-service's BM reconciler must copy `network_attachments` from the proto spec to the K8s CR spec when creating or updating the BaremetalInstance CR. [Source: `.planning/bmaas-networking-design.md` — fulfillment-service Controller (mutateBMI)]

#### Auto-Cleanup on Deletion

- **FR-13:** When a BaremetalInstance is deleted, if ExternalIP/ExternalIPAttachment were created by the system (`external_ip_mode=AUTO`, labeled `osac.openshift.io/auto-provisioned: "true"`), the parent finalizer deletes ExternalIPAttachment first, then ExternalIP. Manually created resources are NOT cleaned up. Default networking resources (VN, Subnet, SG) are NOT cleaned up. [Source: `.planning/bmaas-networking-design.md` — Deletion, step 11]

#### Network Attachment Deletion

- **FR-14:** During BaremetalInstance deletion, `reconcileNetworking` (delete) calls dispatcher → `osac.templates.{{ fabric_manager }}.delete_network_attachment` per interface, passing `host_id`, `host_class`, `interface`, `subnet_ref`. The fabric manager removes the server's interfaces from the subnets' fabric segments and releases IPs. [Source: `.planning/bmaas-networking-design.md` — Deletion, step 11]

### 3.2 Non-Functional Requirements

- **NFR-1:** Auto ExternalIP allocation completes synchronously within the create API call (no async allocation delay). If no pool has available capacity, the create API call returns an error. [Source: Simplified Resource Creation PRD]

- **NFR-2:** Network attachment provisioning (switch port configuration) completes within 2 minutes per interface. [Source: inferred from success metrics]

## 4. Acceptance Criteria

- [ ] A Tenant User can create a BaremetalInstance with explicit `--network-attachment` flags, each specifying an `interface` from the HostType
- [ ] A Tenant User can create a BaremetalInstance with `--external-ip=auto` and no explicit `network_attachments` — the BM is created on the default subnet with an auto-provisioned ExternalIP for inbound access
- [ ] A Tenant User can create a BaremetalInstance with `--nat-gateway=auto` and no explicit `network_attachments` — the BM is provisioned with a NATGateway for outbound connectivity
- [ ] A Tenant User can create a BaremetalInstance with both `--external-ip=auto` and `--nat-gateway=auto` — the BM is fully connected (inbound + outbound) in a single API call
- [ ] A multi-interface BM (multiple `network_attachments`) is provisioned with switch ports configured for each interface, primary attachment providing default gateway
- [ ] Auto-created ExternalIP and ExternalIPAttachment are labeled `osac.openshift.io/auto-provisioned: "true"` and visible in list views
- [ ] Deleting a BaremetalInstance with auto-provisioned ExternalIP causes the auto-created ExternalIP and ExternalIPAttachment to be cleaned up via the parent's finalizer
- [ ] HostType API returns structured NetworkInterface list for BM host types (name, role, description)
- [ ] Creating a BaremetalInstance with an invalid `interface` (not in HostType's list) returns an error
- [ ] Creating a BaremetalInstance with duplicate interfaces across attachments returns an error
- [ ] BM primary attachment IP is written to CR status and synced to fulfillment-service
- [ ] ExternalIPAttachment with `baremetal_instance` target creates DNAT rule using BM's primary IP from status

## 5. Assumptions

- The tenant has default networking resources (VirtualNetwork, Subnet, SecurityGroup) pre-created by the Tenant controller (see Simplified Resource Creation PRD). If defaults are not configured, creating a BM without explicit `network_attachments` fails with a clear error.
- The target region's NetworkClass has `fabric_manager` configured (dispatcher can resolve fabric manager role).
- The HostType for the BM template has a populated NetworkInterface list. If the list is empty, creating a BM with explicit `network_attachments` fails with a clear error.
- The `lifecycle` role interface is reserved for out-of-band provisioning (PXE boot, Redfish/BMC) and is NOT tenant-attachable (should not appear in `network_attachments`).

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Simplified Resource Creation PRD** — default Subnet and SecurityGroup selection behavior defined in [Simplified Resource Creation PRD](/enhancements/simplified-resource-creation)
- **Dispatcher core** — Jira OSAC-1457, OSAC-1458, OSAC-1460 (in progress)
- **NATGateway full stack** — Jira OSAC-1443 (10 tasks, 1/10 in progress)
- **ExternalIPAttachment BM target in CRD** — Jira OSAC-2041 (new)
- **BM DNAT flow in controller** — Jira OSAC-1496 (new)
- **BareMetalNetworkAttachment proto** — Jira OSAC-1508 (new)
- **Primary field on BareMetalNetworkAttachment** — Jira OSAC-2042 (new)
- **Immutability + interface + primary validation** — Jira OSAC-1509 (new)
- **CLI --network-attachment for BareMetalInstance** — Jira OSAC-2075 (new)
- **BM provisioning flow (operator reconcileNetworking calls create_network_attachment)** — Jira OSAC-2047 (new)
- **Integration test** — Jira OSAC-1510 (new)
- **Fabric manager create/delete_network_attachment role (Netris BM)** — Jira OSAC-2081 (new)

## 7. Risks

### 7.1 Dispatcher implementation blocked or delayed

- **Owner:** osac-operator team
- **Mitigation:** OSAC-1457, OSAC-1458, OSAC-1460 are in progress. If dispatcher is not ready, BMaaS networking cannot function. Prioritize completing dispatcher core before BMaaS networking implementation.

### 7.2 Fabric manager BM role implementation blocked

- **Owner:** osac-aap team
- **Mitigation:** OSAC-2081 (Netris BM networking role) is new. If fabric manager does not implement `create_network_attachment` and `delete_network_attachment` for BM, switch port configuration will fail. Coordinate with fabric manager team to prioritize BM support.

### 7.3 IP address feedback mechanism fails

- **Owner:** bare-metal-fulfillment-operator / osac-operator
- **Mitigation:** If the fabric manager role does not write the allocated IP to CR status, ExternalIPAttachment controller cannot create DNAT rule. Validate IP feedback mechanism during integration testing. Fallback: manual IP lookup from fabric manager API (deferred to future enhancement).

### 7.4 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

### 7.5 Auto NATGateway reuses failed or deleting NATGateway

- **Owner:** fulfillment-service / osac-operator
- **Mitigation:** Auto NATGateway reuses existing NATGateway regardless of state. If the existing NATGateway is Failed or Deleting, the BM's outbound connectivity will not work. Document expected behavior: tenants must manually delete failed NATGateway and retry BM creation.

## 8. Open Questions

### 8.1 Should the `lifecycle` interface be explicitly excluded from validation or just documented?

- **Owner:** API design team
- **Impact:** Affects FR-3. Current proposal: document that `lifecycle` is reserved for provisioning, do not enforce exclusion in validation. Alternative: explicitly reject attachments with `role: "lifecycle"`.

### 8.2 Should auto NATGateway check existing NATGateway state before reusing?

- **Owner:** API design team
- **Impact:** Affects FR-7. Current proposal reuses any existing NATGateway (simplest, avoids conflict). Alternative: only reuse if READY, otherwise create a new one (more complex, could create duplicate NATGateways during transient failures).

### 8.3 Should capacity exhaustion return an API error or create a Failed resource?

- **Owner:** API design team
- **Impact:** Affects FR-6 and NFR-1. Returning an error (resource not persisted) is simpler but gives no audit trail. Creating a Failed resource provides visibility but adds cleanup burden.

### 8.4 What is the interface selection logic when network_attachments are omitted and the HostType has multiple "fabric" role interfaces?

- **Owner:** fulfillment-service team
- **Impact:** Affects FR-5. Current proposal: use the first "fabric" role interface in the HostType's ordered list. Alternative: require explicit interface when multiple "fabric" interfaces exist, or use a specific naming convention (e.g., "data-0").
