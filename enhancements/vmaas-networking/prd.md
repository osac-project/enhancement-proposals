# VMaaS Networking — Optional Attachments and Auto External Access

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1435 |
| Date        | 2026-07-08 |

## 1. Problem Statement

ComputeInstance currently uses a shared `NetworkAttachment` message that lacks a `primary` field, making it impossible to support multi-NIC VMs with a designated default gateway. The networking API surface is inconsistent across resource types — ComputeInstance uses `network_attachments` while other resources use different mechanisms. Tenants must explicitly specify networking details on every VM, even when they want to use the same default subnet and security group for most resources. Creating a VM with external access requires manual ExternalIP and NATGateway setup, forcing tenants to understand outbound NAT routing before provisioning their first reachable VM.

## 2. Goals and Non-Goals

### 2.1 Goals

- A tenant can create a ComputeInstance with multiple network attachments, one designated as `primary` for the default gateway
- ComputeInstance supports resource-specific attachment message (`ComputeNetworkAttachment`) to enable multi-NIC KubeVirt provisioning
- A tenant can create a ComputeInstance with `--external-ip=auto` and have the system allocate an ExternalIP and attach it automatically
- A tenant can create a ComputeInstance with `--nat-gateway=auto` and have the system provision or reuse a NATGateway on the VM's VirtualNetwork for outbound connectivity
- Optional `network_attachments` field — when omitted, the system populates with tenant's default Subnet and SecurityGroup
- BM-only region validation rejects ComputeInstance creation when the target region has no `k8s_manager` configured

### 2.2 Non-Goals

- CaaS or BMaaS networking (this PRD covers VMaaS only; Cluster and BaremetalInstance are addressed in separate enhancements)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Kubernetes manager implementation (CUDN or EVPN fabric integration via k8s_manager roles)
- Multi-NIC provisioning for bare-metal resources (BM multi-NIC support is out of scope)

## 3. Requirements

### 3.1 Functional Requirements

#### ComputeNetworkAttachment Proto

- **FR-1:** Replace the shared `NetworkAttachment` message (used across multiple resource types) with `ComputeNetworkAttachment` specific to ComputeInstance. The message includes a `primary` field (boolean, immutable) to designate which attachment provides the default gateway for multi-NIC VMs. [Source: `.planning/vmaas-networking-design.md` — API Changes]

#### Primary Field

- **FR-2:** When a ComputeInstance has multiple `compute_network_attachments`, exactly one must have `primary: true`. When only one attachment exists, `primary` is optional and treated as implicit. The operator CRD validates this constraint via CEL. [Source: `.planning/vmaas-networking-design.md` — Operator CRD]

#### Optional Network Attachments with Defaults

- **FR-3:** The `compute_network_attachments` field on ComputeInstanceSpec is optional. When omitted, the fulfillment-service populates it with the tenant's default Subnet and default SecurityGroup (see Simplified Resource Creation PRD). The resolved attachments are stored in the resource spec so the resource is self-describing after creation. [Source: `.planning/vmaas-networking-design.md` — Proposed Flow, step 4]

#### Auto ExternalIP

- **FR-4:** ComputeInstanceSpec supports an `external_ip_mode` field with values `NONE` (default) and `AUTO`. When `AUTO`, the system auto-selects the READY ExternalIPPool with the most available capacity (identical algorithm to OSAC-1712), creates an ExternalIP, and creates an ExternalIPAttachment binding it to the VM's primary attachment subnet IP. The ExternalIP and ExternalIPAttachment are labeled `osac.openshift.io/auto-provisioned: "true"`. [Source: `.planning/vmaas-networking-design.md` — Proposed Flow, step 4]

#### Auto NATGateway

- **FR-5:** ComputeInstanceSpec supports a `nat_gateway_mode` field with values `NONE` (default) and `AUTO`. When `AUTO`, the system creates a NATGateway on the VM's VirtualNetwork (reuses existing NATGateway if one already exists, regardless of state or whether it was manually or auto-created). The NATGateway uses an auto-selected ExternalIP as the SNAT source. [Source: `.planning/vmaas-networking-design.md` — Proposed Flow, step 4]

#### BM-only Region Validation

- **FR-6:** When a ComputeInstance is created, the fulfillment-service validates that the target region's NetworkClass has a `k8s_manager` configured. If the region is bare-metal-only (no k8s_manager), the create API call returns an error and the resource is not persisted. [Source: `.planning/vmaas-networking-design.md` — Server Validation]

#### Multi-NIC Template Support

- **FR-7:** The AAP template `osac.templates.ocp_virt_vm` reads `compute_network_attachments` and creates KubeVirt VirtualMachine definitions with multiple network interfaces when multiple attachments are present. The primary attachment configures the default gateway, DNS, and IP (via DHCP or static). Non-primary attachments configure IP and connected route only. Each attachment maps to a KubeVirt interface with `l2bridge` binding referencing the attachment's subnet's CUDN NAD. [Source: `.planning/vmaas-networking-design.md` — Template Changes]

#### Backward Compatibility

- **FR-8:** During migration, the fulfillment-service accepts both the old `network_attachments` field (field 14) and the new `compute_network_attachments` field (field 15). If both are set, the create API call returns an error. If the old field is set, the server converts it internally to the new format. [Source: `.planning/vmaas-networking-design.md` — Server Validation]

### 3.2 Non-Functional Requirements

- **NFR-1:** Auto ExternalIP allocation completes synchronously within the create API call (no async allocation delay). If no pool has available capacity, the create API call returns an error. [Source: Simplified Resource Creation PRD]

## 4. Acceptance Criteria

- [ ] A Tenant User can create a ComputeInstance with multiple `--network-attachment` flags and designate one as `--primary`
- [ ] A Tenant User can create a ComputeInstance with `--external-ip=auto` and no explicit `network_attachments` — the VM is created on the default subnet with an auto-provisioned ExternalIP for inbound access
- [ ] A Tenant User can create a ComputeInstance with `--nat-gateway=auto` and no explicit `network_attachments` — the VM is provisioned with a NATGateway for outbound connectivity
- [ ] A Tenant User can create a ComputeInstance with both `--external-ip=auto` and `--nat-gateway=auto` — the VM is fully connected (inbound + outbound) in a single API call
- [ ] Creating a ComputeInstance in a BM-only region (no k8s_manager in NetworkClass) returns an error with a clear message
- [ ] A multi-NIC VM (multiple `compute_network_attachments`) is provisioned by the template with multiple KubeVirt interfaces, primary attachment providing default gateway
- [ ] Auto-created ExternalIP and ExternalIPAttachment are labeled `osac.openshift.io/auto-provisioned: "true"` and visible in list views
- [ ] Deleting a ComputeInstance with auto-provisioned ExternalIP causes the auto-created ExternalIP and ExternalIPAttachment to be cleaned up via the parent's finalizer
- [ ] Creating a ComputeInstance with the old `network_attachments` field (field 14) succeeds and is internally converted to the new format
- [ ] Creating a ComputeInstance with both old and new attachment fields returns an error

## 5. Assumptions

- The tenant has default networking resources (VirtualNetwork, Subnet, SecurityGroup) pre-created by the Tenant controller (see Simplified Resource Creation PRD). If defaults are not configured, creating a VM without explicit `network_attachments` fails with a clear error.
- The target region's NetworkClass has `k8s_manager` configured (either CUDN or EVPN fabric integration). BM-only regions do not support VMaaS.

## 6. Dependencies

- **Unified Networking EP** — this PRD builds on the unified networking resource model (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) defined in the [Unified Networking EP](/enhancements/unified-networking)
- **Simplified Resource Creation PRD** — default Subnet and SecurityGroup selection behavior defined in [Simplified Resource Creation PRD](/enhancements/simplified-resource-creation)
- **OSAC-1712 (automatic pool selection)** — the auto ExternalIP pool selection reuses the identical algorithm: pick the READY pool with the most available capacity matching the IP family
- **OSAC-1511 or OSAC-1717** — a k8s_manager implementation (CUDN or EVPN) must exist for the operator's Subnet controller to provision overlay networks on hosting clusters
- **Dispatcher core** — Jira OSAC-1457, OSAC-1458, OSAC-1460 (in progress)
- **Multi-job tracking** — Jira OSAC-1459 (new, required for Subnet controller to trigger both fabric_manager and k8s_manager AAP jobs)

## 7. Risks

### 7.1 k8s_manager implementation blocked or delayed

- **Owner:** Engineering / Product
- **Mitigation:** OSAC-1511 (CUDN) and OSAC-1717 (EVPN) are both in spike/blocked state. If neither lands, VMaaS networking cannot function. Prioritize unblocking one of these dependencies or accept that VMaaS remains unavailable until a k8s_manager exists.

### 7.2 Multi-job tracking not implemented

- **Owner:** osac-operator team
- **Mitigation:** OSAC-1459 is a prerequisite for Subnet controller to call both fabric_manager and k8s_manager. If not implemented, Subnet controller can only call one manager — defer multi-manager support or accept single-manager-only subnet provisioning.

### 7.3 ExternalIPPool exhaustion

- **Owner:** Cloud Provider Admin
- **Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool

### 7.4 Auto NATGateway reuses failed or deleting NATGateway

- **Owner:** fulfillment-service / osac-operator
- **Mitigation:** Auto NATGateway reuses existing NATGateway regardless of state. If the existing NATGateway is Failed or Deleting, the VM's outbound connectivity will not work. Document expected behavior: tenants must manually delete failed NATGateway and retry VM creation.

## 8. Open Questions

### 8.1 Should auto NATGateway check existing NATGateway state before reusing?

- **Owner:** API design team
- **Impact:** Affects FR-5. Current proposal reuses any existing NATGateway (simplest, avoids conflict). Alternative: only reuse if READY, otherwise create a new one (more complex, could create duplicate NATGateways during transient failures).

### 8.2 Should capacity exhaustion return an API error or create a Failed resource?

- **Owner:** API design team
- **Impact:** Affects FR-4 and NFR-1. Returning an error (resource not persisted) is simpler but gives no audit trail. Creating a Failed resource provides visibility but adds cleanup burden.
