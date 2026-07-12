---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-07-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/unified-networking"
  - "Default Networking: /enhancements/default-networking"
  - "baremetal-instance-api: https://github.com/osac-project/baremetal-instance-api"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking — Switch Port Configuration and Tenant-Defined Interface Mapping

This enhancement extends the unified networking API to support BMaaS-specific requirements: multi-NIC BaremetalInstance provisioning with tenant-specified physical interface mapping, switch port configuration via dispatcher, IP address feedback through CR status, and auto-provisioned external access (ExternalIP + NATGateway).

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/unified-networking/design.md), providing the detailed per-service flow for this service type. The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how this specific service consumes that architecture.

BaremetalInstance currently has NO networking fields. The bare-metal-fulfillment-operator allocates hosts from inventory (Ironic or Metal3) but does not configure switch ports or integrate with the OSAC Networking API. This enhancement introduces `BareMetalNetworkAttachment` with explicit `interface` and `primary` fields, adds `reconcileNetworking` phase to the operator, and enables IP address feedback via CR status for DNAT rule creation. See [PRD](prd.md) for detailed requirements.

## Motivation

BaremetalInstance does NOT participate in the networking API today. Current flow:

1. Tenant creates BaremetalInstance with template + template_parameters (no networking parameters)
2. fulfillment-service creates BaremetalInstance CR on hub (sets TemplateID, TemplateParameters, RunStrategy, labels, annotations)
3. bare-metal-fulfillment-operator BareMetalInstance controller:
   - `reconcileInventory`: FindFreeHost → AssignHost (Ironic or Metal3 backend). Populates HostClass and NetworkClass from inventory.
   - `reconcileProvisioning`: triggers AAP job via `RunProvisioningLifecycle` — full CR serialized as payload. Template does BM-specific provisioning (OS install, user-data).
   - `reconcilePower`: manages power state (Ironic/Metal3 API).
   - Updates CR status (phase, conditions).
4. osac-operator feedback controller: watches CR status changes, fires Signal RPC to fulfillment-service.
5. fulfillment-service syncs status back to its database.

### Architecture: Two Operators on One CR

```
fulfillment-service → creates BaremetalInstance CR → hub cluster
                                                        │
    bare-metal-fulfillment-operator ─────────────────────┤ (provisioning)
      - reconcileInventory (Ironic/Metal3)               │
      - reconcileProvisioning (AAP)                      │
      - reconcilePower (Ironic/Metal3)                   │
      - finalizers: inventory, baremetalinstance          │
                                                         │
    osac-operator ───────────────────────────────────────┘ (feedback only)
      - BareMetalInstanceFeedbackReconciler
      - fires Signal RPC on status change
      - finalizer: baremetalinstance-feedback (removed last)
```

### What Already Works

- Two-operator architecture is stable (bare-metal-fulfillment-operator for provisioning, osac-operator for feedback)
- Inventory assignment (host allocation from Ironic/Metal3)
- OS provisioning via AAP templates
- Power management via Ironic/Metal3 API
- Status feedback to fulfillment-service

### What's Missing

- BaremetalInstance spec has no `network_attachments` field
- No switch port configuration during BM provisioning
- No integration with the OSAC Networking API
- The `NetworkClass` field populated from inventory is stored but unused. This is a static config string (e.g., "openstack") set at operator startup — NOT the OSAC NetworkClass CRD. Should be renamed to `NetworkFabricManager` to avoid collision.
- No ExternalIPAttachment support for `baremetal_instance` target
- No IP address feedback mechanism (ExternalIPAttachment controller needs BM's IP to create DNAT rules)

### Goals

- Multi-NIC support with explicit physical interface mapping (tenant specifies interface name from HostType)
- Resource-specific attachment message (`BareMetalNetworkAttachment`) with `interface` and `primary` fields
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP mode (`external_ip_mode: AUTO`) for single-call inbound connectivity
- Auto NATGateway mode (`nat_gateway_mode: AUTO`) for single-call outbound connectivity
- bare-metal-fulfillment-operator `reconcileNetworking` phase: dispatcher calls `create_network_attachment` per interface to configure switch ports
- IP discovery after DHCP: host receives IP from fabric's DHCP server, IP discovered from host/inventory system, written to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP for DNAT
- HostType resource extended with structured `NetworkInterface` list (name, role, description) for BM host types only
- Rename `networkClass` → `networkFabricManager` to avoid collision with OSAC NetworkClass CRD

### Non-Goals

- CaaS or VMaaS networking (this EP covers BMaaS only)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Fabric manager implementation (Netris create/delete_network_attachment roles deferred to OSAC-2081)

## Proposal

### HostType and Interface Validation

#### HostType Resource (shared with CaaS)

The `HostType` resource in the fulfillment-service describes a class of hardware — physical (BM) or virtual (VM). Today it only has `id`, `title`, `description` (free text). For networking, BM host types need a structured interface list:

```protobuf
message HostType {
  string id = 1;
  Metadata metadata = 2;
  string title = 3;
  string description = 4;
  repeated NetworkInterface interfaces = 5;  // BM only, empty for VM host types
}

message NetworkInterface {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0"
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string description = 3; // e.g., "100GbE data interface"
}
```

**The `interfaces` list is only populated for BM host types.** VM host types have an empty list — VMs get virtual NICs from the CUDN overlay, not physical interfaces. This also serves as the BM-vs-VM discriminator: if a HostType has interfaces → BM. If empty → VM.

Interfaces are ordered. When multiple interfaces share the same role, the first one in the list is the default for that role (used by CaaS for automatic resolution — see CaaS design).

#### How BMaaS Uses HostType

The tenant provides `BareMetalNetworkAttachment` with an explicit `interface` field. The fulfillment-service validates:
- The `interface` name exists in the HostType's `interfaces` list
- The HostType is resolved from the catalog_item / template

Unlike CaaS (which picks the interface automatically by role), BMaaS gives the tenant direct control over which physical interface maps to which subnet. The tenant can see the available interfaces via the HostType API before creating the BaremetalInstance.

#### Interface Role Convention

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) |

Roles are conventions, not enforced enums. BMaaS uses them for display/documentation; the tenant selects by interface name, not role. The `lifecycle` interface is used by the provisioning system (Ironic, Metal3) for PXE boot and BMC operations — it is NOT tenant-attachable and should not appear in `network_attachments`.

### Workflow Description

#### Phase 1: Tenant Creates Networking Resources

Same as VMaaS/CaaS — the networking API is uniform.

1. **Create VirtualNetwork:**
   ```bash
   osac create virtualnetwork --region moc-region-1 --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_virtual_network`

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → fabric_manager creates VLAN/fabric segment. If the region has a k8s_manager: also creates CUDN overlay (but BM doesn't use it — the overlay exists for VMs that may share the same subnet).

3. **Create SecurityGroup:**
   ```bash
   osac create security-group --virtual-network my-net --name my-sg \
     --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_security_group`

#### Phase 2: Tenant Creates BM Server

4. **Create BaremetalInstance with network_attachments:**

   Single interface (simple case):
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
     --name my-server
   ```

   Multiple interfaces:
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --network-attachment interface=data-0,subnet=data-subnet,security-groups=my-sg,primary \
     --network-attachment interface=data-1,subnet=storage-subnet \
     --name my-server
   ```

   With defaults + auto external access:
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --external-ip=auto --name my-server
   ```

5. **fulfillment-service:**
   - If `network_attachments` omitted: populates with tenant's default Subnet + default SecurityGroup (see [Default Networking PRD](/enhancements/default-networking))
   - Validates:
     - Each subnet exists, is Ready
     - All subnets belong to the same VirtualNetwork
     - Each SecurityGroup exists, is Ready, belongs to the same VN
     - Each `interface` references a valid interface from the HostType's NetworkInterface list
     - No duplicate interfaces across attachments
     - If >1 attachment without `interface`, reject (explicit interface required when multi-homed)
     - Number of attachments ≤ number of available interfaces on template
     - If multiple attachments, exactly one is `primary`; if single attachment, `primary` is implicit
   - If `external_ip_mode == AUTO`: auto-selects ExternalIPPool (READY, most available capacity, matching IP family), creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. The ExternalIPAttachment references the BaremetalInstance but does not yet have a DNAT target IP (the BM's IP is unknown until `reconcileNetworking` runs). Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted (including the BaremetalInstance). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
   - If `nat_gateway_mode == AUTO`: checks if NATGateway already exists on the VN. If exists: reuse (regardless of state). If not exists: creates a **separate** ExternalIP for the NATGateway's SNAT source (ExternalIP exclusivity means one consumer each) and creates NATGateway in a **separate DB transaction** after the parent resource is persisted, both labeled `osac.openshift.io/auto-provisioned: "true"`. Pool capacity is decremented for this additional ExternalIP; if the pool is exhausted, the NATGateway is not created but the BaremetalInstance creation still succeeds (outbound NAT is best-effort).
   - Creates BaremetalInstance CR with `network_attachments` in spec

6. **bare-metal-fulfillment-operator BareMetalInstance controller:**

   a. `reconcileInventory` (unchanged):
      - FindFreeHost → AssignHost (Ironic/Metal3)
      - Populates HostClass, NetworkFabricManager from inventory

   b. **`reconcileNetworking` (NEW — runs after inventory, before provisioning):**
      - Reads `network_attachments` from the CR spec
      - **Operator dispatches switch-side config:** For each attachment, dispatcher calls `osac.templates.{{ fabric_manager }}.create_network_attachment` passing `host_name` (Netris server name from ExternalHostID), `logical_interface_name` (Netris port name from HostType), `subnet_ref`. The fabric manager adds the server's port to the subnet's V-Net. The host will receive an IP from the fabric's DHCP server once it boots on the V-Net.
      - Network attachments must be Ready before provisioning proceeds

   c. `reconcileProvisioning` (runs after networking):
      - Triggers AAP job via `RunProvisioningLifecycle`
      - Template does OS provisioning (PXE boot, user-data, etc.)
      - Host-side networking is handled by DHCP — the template does NOT configure static IPs, gateway, or DNS. The host receives its IP automatically when it boots on the V-Net.

   d. `reconcilePower` (unchanged)

7. **IP discovery and feedback:**
   - After the host boots and receives a DHCP-assigned IP on the tenant V-Net, the IP must be discovered and written to `status.networkAttachments[].ipAddress` on the CR
   - **Discovery mechanism (open question — see OQ#4):** Metal3 `BareMetalHost.status.hardware.nics[].ip` reflects the inspection-time IP, not the runtime IP after network reconfiguration. The runtime IP must be discovered via one of: (a) the `create_network_attachment` Ansible role queries the fabric manager's DHCP lease table and returns the assigned IP, (b) the fabric manager exposes a DHCP lease API that the operator polls, or (c) a phone-home callback from the host reports its IP
   - Operator writes the discovered IP to `status.networkAttachments[].ipAddress` on the BaremetalInstance CR
   - Feedback controller watches CR status changes → fires Signal RPC to fulfillment-service
   - fulfillment-service reconciler syncs the discovered IP to the DB via existing `syncStatus()` pattern

#### Phase 3: External Access (optional)

8. **Create ExternalIP:**
   ```bash
   osac create externalip --pool external-pool-1 --name my-ip
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_external_ip`

9. **Create ExternalIPAttachment:**
    ```bash
    osac create externalipattachment --externalip my-ip \
      --baremetal-instance my-server --name bm-att
    ```
    - ExternalIPAttachment controller resolves the BaremetalInstance target by UUID label
    - Checks two preconditions before dispatching (requeues if either is not met):
      1. **ExternalIP must be Allocated** (have an allocated address from the fabric manager)
      2. **BaremetalInstance must have a primary IP** — reads `status.networkAttachments[].ipAddress` for the attachment where `primary: true`. This IP is written by the operator during `reconcileNetworking` (step 6b) and synced to the fulfillment-service via the feedback controller (step 7).
    - Once both preconditions are met: writes `osac.openshift.io/target-ip` annotation on the ExternalIPAttachment CR
    - Calls `osac.templates.{{ fabric_manager }}.create_external_ip_attachment`
    - Fabric manager creates DNAT rule: external IP → BM's primary subnet IP
    - ExternalIPAttachment transitions from Pending to Ready

    For auto-provisioned ExternalIPAttachments (`external_ip_mode=AUTO`), the same flow applies — the attachment is created at API time in Pending state and the controller activates it once the BM's IP becomes known. The wait time depends on `reconcileNetworking` completion (IP allocation by the operator + switch port configuration by the fabric manager).

#### Phase 4: Outbound NAT (optional)

10. **Create NATGateway:**
    ```bash
    osac create externalip --pool external-pool-1 --name nat-ip
    osac create natgateway --virtual-network my-net --externalip nat-ip --name my-nat
    ```
    Dispatcher → `osac.templates.{{ fabric_manager }}.create_nat_gateway` → SNAT rule for the VN's CIDR

#### Deletion (reverse order)

11. **Delete BaremetalInstance:**
    - **Auto-provisioned cleanup (osac-operator):** The osac-operator adds a cleanup finalizer (`osac.openshift.io/baremetalinstance-cleanup`) on BaremetalInstance CRs that have `external_ip_mode=AUTO`. On deletion, it performs the phased requeue cleanup: deletes ExternalIPAttachment first (by target reference), waits, then deletes ExternalIP (by `auto-provisioned-for` label), waits, then removes its finalizer. See [Unified Networking — Auto-provisioned resource cleanup](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the pattern. This runs concurrently with the bare-metal-fulfillment-operator's deletion flow but does not conflict (different CRs).
    - **Auto-provisioned NATGateway is NOT cleaned up** — NATGateway is a shared per-VN resource that may serve other resources on the same VirtualNetwork.
    - **Manually created resources are NOT cleaned up** — tenant manages their lifecycle.
    - **Default networking resources (VN, Subnet, SG) are NOT cleaned up** — tenant-scoped and shared.
    - bare-metal-fulfillment-operator:
      - `reconcileDeprovisioning`: triggers AAP delete job for OS teardown
      - `reconcileNetworking` (delete): dispatcher calls `osac.templates.{{ fabric_manager }}.delete_network_attachment` per attachment (passing host_name, logical_interface_name, subnet_ref) to remove the server's port from the subnet's V-Net.
      - Removes management finalizer
    - `reconcileInventory` deletion: UnassignHost from Ironic/Metal3, removes inventory finalizer
    - osac-operator feedback controller: waits for other finalizers, removes feedback finalizer, fires final Signal

12. **Tenant deletes networking resources** (independently):
    - Delete ExternalIPAttachments, ExternalIPs, NATGateway, SecurityGroup, Subnet, VirtualNetwork — each via its own dispatcher-triggered delete job

### API Extensions

#### Proto (fulfillment-service)

```protobuf
message BareMetalNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, mutable
  string interface = 3;                 // optional, immutable: physical interface
                                        // from HostType
  bool primary = 4;                     // optional, immutable: default gateway
}

message BareMetalInstanceSpec {
  string catalog_item = 1;              // immutable
  optional string ssh_public_key = 2;   // immutable
  optional string user_data = 3;        // immutable
  optional BareMetalInstanceRunStrategy run_strategy = 4;
  int64 restart_trigger = 5;
  map<string, google.protobuf.Any> template_parameters = 6;  // immutable
  optional BareMetalInstanceImage image = 7;                  // immutable
  repeated BareMetalNetworkAttachment network_attachments = 8; // NEW, optional
  ExternalIPMode external_ip_mode = 9;   // NONE (default) or AUTO
  NATGatewayMode nat_gateway_mode = 10;  // NONE (default) or AUTO
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachments = N; // NEW
}

message BareMetalNetworkAttachmentStatus {
  string interface = 1;
  string subnet_ref = 2;
  string ip_address = 3;  // Discovered after DHCP assignment, synced to fulfillment-service via feedback
  bool primary = 4;
}
```

#### Operator CRD (bare-metal-fulfillment-operator)

```go
type BareMetalInstanceSpec struct {
    // ... existing fields ...
    NetworkAttachments []BareMetalNetworkAttachment `json:"networkAttachments,omitempty"`
}

type BareMetalNetworkAttachment struct {
    SubnetRef         string   `json:"subnetRef"`
    SecurityGroupRefs []string `json:"securityGroupRefs,omitempty"`
    Interface         string   `json:"interface,omitempty"`
    Primary           bool     `json:"primary,omitempty"`
}

type BareMetalInstanceStatus struct {
    // ... existing fields ...
    NetworkAttachments []BareMetalNetworkAttachmentStatus `json:"networkAttachments,omitempty"`
}

type BareMetalNetworkAttachmentStatus struct {
    Interface  string `json:"interface,omitempty"`
    SubnetRef  string `json:"subnetRef,omitempty"`
    IPAddress  string `json:"ipAddress,omitempty"` // Discovered after DHCP assignment
    Primary    bool   `json:"primary,omitempty"`
}
```

CEL immutability: `network_attachments` list is immutable after creation (subnet refs, interface, primary are all immutable). Only `securityGroupRefs` is mutable.

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() > 1 ? self.networkAttachments.filter(x, x.primary == true).size() == 1 : true"
  message: "When multiple network attachments exist, exactly one must have primary: true"
```

#### fulfillment-service Controller (mutateBMI)

The `mutateBMI()` function in the fulfillment-service's BM reconciler currently sets TemplateID, TemplateParameters, RunStrategy on the K8s CR. It needs to also copy `network_attachments` from the proto spec to the K8s CR spec.

#### Server Validation Rules

- All referenced subnets must belong to the same VirtualNetwork
- The same interface cannot appear in multiple attachments
- The `interface` must reference a valid identifier from the HostType (its NetworkInterface list defines available interfaces)
- Interfaces with role `lifecycle` are rejected in `network_attachments` — lifecycle interfaces (PXE boot, BMC) are reserved for the provisioning system and are not tenant-attachable
- If >1 attachment specified, each must have an explicit `interface` (multiple attachments without `interface` is invalid)
- Number of attachments ≤ number of available interfaces on the template
- If multiple attachments: exactly one must be `primary: true`
- If single attachment: `primary` is implicit (true by default)
- network_attachments are immutable after creation

### Implementation Details/Notes/Constraints

#### The IP Address Feedback Question

#### IP Discovery

After `reconcileNetworking` adds the host's port to the V-Net and `reconcileProvisioning` boots the host, the host receives an IP from the fabric's DHCP server. The IP is discovered from the host/inventory system (Ironic/Metal3 reports the allocated IP after provisioning) and written to `status.networkAttachments[].ipAddress` on the BaremetalInstance CR.

The feedback controller syncs this to the fulfillment-service DB via the existing Signal / `syncStatus()` pattern. The ExternalIPAttachment controller reads the primary IP from CR status for DNAT creation.

The fabric manager role (`create_network_attachment`) handles switch-side only — adding the server's port to the subnet's V-Net. It does not allocate IPs. IP assignment is handled by the fabric's DHCP server, and IP discovery is handled by the host/inventory system.

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, copy to K8s CR via mutateBMI, auto-provision ExternalIP/NATGateway |
| bare-metal-fulfillment-operator | Inventory assignment, switch-side networking (dispatcher), **IP discovery** from host/inventory after DHCP, OS provisioning (AAP), power management |
| AAP BM provisioning template | OS provisioning only (host-side networking handled by DHCP) |
| osac-operator feedback controller | Signal fulfillment-service on status changes (unchanged), sync IP addresses from CR status to DB |
| osac-operator BMI cleanup controller | Clean up auto-provisioned ExternalIPAttachment → ExternalIP on BaremetalInstance deletion (phased requeue, `baremetalinstance-cleanup` finalizer) |
| osac-operator ExternalIPAttachment controller | Read BM's primary IP from CR status, create DNAT via fabric_manager |
| fabric_manager role (create_network_attachment) | Switch-side only: resolve host → fabric server, add server port to subnet's V-Net |
| fabric_manager role (delete_network_attachment) | Switch-side only: remove server port from V-Net |

#### Reconciliation Phase Ordering

```
bare-metal-fulfillment-operator BareMetalInstance controller phases:
1. reconcileInventory → allocate host, populate HostClass, NetworkFabricManager
   Sets condition: InventoryAssigned=True
2. reconcileNetworking → configure switch ports (dispatcher)
   Requires: InventoryAssigned=True
   Sets condition: NetworkingConfigured=True
3. reconcileProvisioning → OS provisioning (AAP). Host boots and gets IP from DHCP.
   Requires: NetworkingConfigured=True
4. reconcilePower → power state management
```

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway) inherit tenant annotation from parent BaremetalInstance
- No new authentication or authorization changes
- SecurityGroup rules control BM inbound traffic (tenant-configurable via explicit SG or default SG)
- Multi-NIC BM servers on different subnets share the same SecurityGroup enforcement (fabric-level ACL rules apply to all interfaces)

### Failure Handling and Recovery

#### bare-metal-fulfillment-operator Reconciliation Failures

- Inventory assignment failure (no free hosts): BaremetalInstance enters Failed state with condition, retries when host becomes available
- Networking failure (dispatcher call failed, switch port config failed): BaremetalInstance enters Failed state with condition, retries on manual correction
- AAP job failure (template execution error): BaremetalInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types))
- ExternalIP provisioning failure: ExternalIP enters Failed state, BaremetalInstance remains in Pending (external access unavailable, BM may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach BM (BM functional, external access unavailable)

#### Auto NATGateway Provisioning Failures

- Pool exhaustion: NATGateway creation fails, BaremetalInstance proceeds without outbound NAT (BM may be isolated)
- Reusing failed NATGateway: if existing NATGateway on VN is Failed or Deleting, system reuses it (no new NATGateway created), outbound connectivity unavailable until tenant manually deletes failed NATGateway and retries
- NATGateway provisioning failure: NATGateway enters Failed state, outbound SNAT rule not created, BM has no outbound connectivity

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (BaremetalInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment/NATGateway) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from BaremetalInstance to auto-created resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-provisioned: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- bare-metal-fulfillment-operator: `NetworkingReconciled` (info), `NetworkingReconciliationFailed` (error), `SwitchPortConfigured` (info), `IPAddressAllocated` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `AutoProvisionedNATGateway` (info), `ExternalIPPoolExhausted` (error), `InterfaceValidationFailed` (error)

New Kubernetes events on BaremetalInstance:
- `NetworkingConfigured`: switch ports configured, IPs allocated
- `NetworkingConfigurationFailed`: networking reconciliation failed (dispatcher error, switch port config error)
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned
- `AutoNATGatewayCreated`: NATGateway auto-provisioned or reused

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: fabric_manager implementation blocked or delayed

**Impact:** Fabric manager `create_network_attachment` and `delete_network_attachment` roles are prerequisites for BMaaS networking. Without them, switch port configuration cannot function. (IP allocation is operator-managed and does not depend on fabric manager roles.)

**Mitigation:** Prioritize Netris BM roles (OSAC-2081). Accept that BMaaS remains unavailable until a fabric_manager exists. Document as a hard dependency.

**Reviewed by:** Engineering / Product

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create BM with `external_ip_mode=AUTO`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Auto NATGateway reuses failed or deleting NATGateway

**Impact:** If existing NATGateway on VN is Failed or Deleting, system reuses it (FR-5 design choice), BM's outbound connectivity will not work.

**Mitigation:** Document expected behavior: tenants must manually delete failed NATGateway and retry BM creation. Alternative: change FR-5 to check NATGateway state before reusing (deferred to implementation phase).

**Reviewed by:** API design team

#### Risk: Two-operator architecture synchronization

**Impact:** bare-metal-fulfillment-operator and osac-operator feedback controller both watch BaremetalInstance CR. Reconciliation phases must be carefully ordered to avoid race conditions.

**Mitigation:** Reconciliation phase ordering enforced via status conditions: inventory → networking → provisioning. Integration tests covering full lifecycle. Document finalizer dependencies.

**Reviewed by:** osac-operator / bare-metal-fulfillment-operator teams

### Drawbacks

#### Two-operator architecture complexity

bare-metal-fulfillment-operator handles provisioning and networking, osac-operator feedback controller only watches status changes. This split adds synchronization complexity compared to a single-operator model.

**Trade-off:** Separation of concerns (provisioning vs. feedback) vs. operational simplicity. Chosen approach: maintain two-operator architecture to avoid merging codebases. Document reconciliation phase ordering and finalizer dependencies.

## Alternatives (Not Implemented)

### Alternative 1: Single-operator architecture

Merge bare-metal-fulfillment-operator into osac-operator to simplify reconciliation and eliminate feedback controller.

**Rejected because:** bare-metal-fulfillment-operator is a separate codebase with its own Ironic/Metal3 integration. Merging would require significant refactoring and change ownership model. Current two-operator architecture is stable and proven.

### Alternative 2: Operator IPAM (pre-allocate IPs)

Operator pre-allocates IPs from subnet CIDR during reconcileNetworking and writes static config (IP, gateway, prefix, DNS) to CR status. Template applies static config to host.

**Rejected because:** DHCP is simpler, OS-agnostic, and already provided by the fabric infrastructure. Static config requires per-OS template logic (cloud-init, NMState, kickstart) and adds IPAM complexity (allocation tracking, cross-operator concurrency, gateway/DNS discovery). DHCP handles all of this automatically.

### Alternative 4: Auto NATGateway always creates new NATGateway

Instead of reusing existing NATGateway, always create a new one when `nat_gateway_mode=AUTO`.

**Rejected because:** Multiple NATGateways on the same VN would conflict at the fabric level (SNAT rules for the same CIDR would overlap). Reusing existing NATGateway avoids conflict.

## Open Questions

### 1. Should auto NATGateway treat a Deleting NATGateway as "does not exist"?

Design decision: reuse existing NATGateway in Ready or Failed state (avoids duplicate SNAT conflicts). Open question: should a NATGateway in **Deleting** state be treated as "does not exist" (create a new one), since the SNAT rule is being removed and the NATGateway will soon be fully deleted? Current behavior would silently attach to a disappearing resource.

**Owner:** API design team

**Impact:** Affects NATGateway reuse logic and user experience when NATGateway is being deleted concurrently.

### 2. Should capacity exhaustion return an API error or create a Failed resource?

Current proposal: return error, no resources persisted (pool capacity checked synchronously during the API call). Alternative: create Failed resource for audit trail.

**Owner:** API design team

**Impact:** Affects FR-4 and acceptance criteria.

### ~~3. IP address assignment~~ — Resolved

Resolved: DHCP handles IP assignment. The host receives its IP from the fabric's DHCP server after booting on the V-Net. No operator IPAM needed.

### 4. How is the host's runtime IP discovered after network reconfiguration?

Metal3 `BareMetalHost.status.hardware.nics[].ip` reflects the inspection-time IP (snapshot from initial hardware inspection), NOT the runtime IP after the host's port is moved to the tenant V-Net via `create_network_attachment`. After the host gets a new DHCP lease on the tenant subnet, this IP must be discovered and written to `status.networkAttachments[].ipAddress` on the BaremetalInstance CR.

Options:
- **(a)** The `create_network_attachment` Ansible role queries the fabric manager's DHCP lease table after moving the port and returns the assigned IP as a role output. The operator reads the role output and writes it to CR status.
- **(b)** The fabric manager exposes a DHCP lease API. The operator polls it until the host's lease appears.
- **(c)** A phone-home / cloud-init callback from the host reports its IP to a webhook or annotation on the CR.

**Owner:** Platform team / osac-aap team

**Impact:** Blocks ExternalIPAttachment for BMaaS targets — the DNAT controller needs `status.networkAttachments[].ipAddress` to create the inbound NAT rule. Without a working discovery mechanism, auto ExternalIP for bare-metal servers does not function.

## Test Plan

### Unit Tests

- fulfillment-service: primary validation (reject >1 primary, accept single implicit primary, accept explicit primary)
- fulfillment-service: interface validation (reject interface not in HostType, reject duplicate interfaces, reject >1 attachment without interface)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- fulfillment-service: auto NATGateway reuse (reuse existing, create new if none exists)
- bare-metal-fulfillment-operator: reconcileNetworking phase ordering (after inventory, before provisioning)
- bare-metal-fulfillment-operator: dispatcher call per attachment (create_network_attachment with correct params)

### Integration Tests

- E2E: create BaremetalInstance with multiple attachments, verify switch ports configured for each interface, IPs allocated from each subnet
- E2E: create BaremetalInstance with `--external-ip=auto`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: create BaremetalInstance with `--nat-gateway=auto`, verify auto NATGateway created or reused, SNAT rule functional
- E2E: create BaremetalInstance with `--external-ip=auto --nat-gateway=auto`, verify full connectivity (inbound + outbound)
- E2E: delete BaremetalInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create BaremetalInstance with interface not in HostType, verify error returned
- E2E: create BaremetalInstance with >1 attachment but no interface fields, verify error returned
- E2E: verify IP discovery (host receives IP from DHCP, IP discovered from host/inventory system, written to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP)

### Tricky Test Cases

- Multi-NIC BM with primary on second interface (verify default gateway on correct interface)
- Auto NATGateway when existing NATGateway is Failed (verify reuse, document expected behavior)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)
- IP address feedback latency (verify ExternalIPAttachment controller waits for IP to appear in status)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachments`, `external_ip_mode`, `nat_gateway_mode`) implemented in fulfillment-service
- [ ] BaremetalInstance CRD updated with `NetworkAttachments` field, CEL validation, and status field for IP addresses
- [ ] bare-metal-fulfillment-operator `reconcileNetworking` phase implemented
- [ ] Dispatcher integration for `create_network_attachment` and `delete_network_attachment`
- [ ] HostType proto extended with `NetworkInterface` list
- [ ] Auto ExternalIP and auto NATGateway provisioning functional
- [ ] IP discovery implemented (host receives IP from DHCP, IP discovered from host/inventory system, written to CR status, feedback syncs to fulfillment-service)
- [ ] Integration tests pass (E2E coverage for multi-NIC, auto ExternalIP, auto NATGateway, IP feedback)
- [ ] Documentation: API reference, user guide for simplified BM creation

GA criteria:
- [ ] fabric_manager implementation (Netris BM roles, OSAC-2081) delivered and production-tested
- [ ] Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460) implemented and stable
- [ ] NATGateway full stack (OSAC-1443) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`network_attachments`, `external_ip_mode`, `nat_gateway_mode`) are additive — existing BaremetalInstance resources continue to work without networking fields
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Tenant User encouraged to migrate to new networking fields via CLI update (`osac-cli` supports new `--network-attachment` flag with `--interface` and `--primary`)
- No breaking changes — networking fields remain optional

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and bare-metal-fulfillment-operator images to `N`
- Existing BaremetalInstance resources with new `network_attachments` field will be unrecognized by `N` operator
- Manual cleanup required: delete BaremetalInstance resources created with new field, re-create without networking fields
- Auto-provisioned ExternalIP/NATGateway resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Delete CRs using new field (`network_attachments`)
- Re-create without networking fields
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway labeled `osac.openshift.io/auto-provisioned: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service, osac-operator, and bare-metal-fulfillment-operator are deployed together in the same namespace and upgraded atomically (all controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not support `--network-attachment` flag → creates BM without networking fields (default behavior)
- New CLI uses new `--network-attachment` flag → server accepts new field

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses new `--network-attachment` flag → old server rejects unknown field
- Workaround: omit `--network-attachment` flag until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: BaremetalInstance stuck in Pending, condition "NetworkingConfigurationFailed"

**Detection:**
```bash
kubectl describe baremetalinstance <name> -n <namespace>
# Check status.conditions for NetworkingConfigurationFailed
```

**Cause:** Dispatcher call failed or switch port config failed

**Resolution:**
1. Check bare-metal-fulfillment-operator logs for networking phase errors (dispatcher)
2. Check AAP job logs for `create_network_attachment` role errors (switch-side)
3. If fabric manager unreachable, investigate connectivity
4. If switch port config failed, investigate switch configuration

### Symptom: Multi-NIC BM has no default gateway

**Detection:** BM cannot reach external networks, `ip route` shows no default route

**Cause:** Primary attachment not designated or incorrectly resolved

**Resolution:**
1. Check BaremetalInstance spec: `kubectl get baremetalinstance <name> -n <namespace> -o yaml`
2. Verify exactly one `networkAttachments[].primary: true`
3. If missing or incorrect, delete and re-create BaremetalInstance with correct `--primary` flag

### Symptom: Auto-provisioned ExternalIP not cleaned up after BaremetalInstance deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check BaremetalInstance deletion logs (bare-metal-fulfillment-operator logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Symptom: ExternalIPAttachment stuck in Pending, waiting for BM IP address

**Detection:** `kubectl describe externalipattachment <name> -n <namespace>` shows condition "WaitingForIPAddress"

**Cause:** Host has not yet received DHCP-assigned IP (provisioning still in progress or failed)

**Resolution:**
1. Check BaremetalInstance status: `kubectl get baremetalinstance <name> -n <namespace> -o jsonpath='{.status.networkAttachments[?(@.primary==true)].ipAddress}'`
2. If IP is missing, check bare-metal-fulfillment-operator logs for provisioning phase completion
3. If provisioning completed but IP missing, investigate IP discovery from host/inventory system (Ironic/Metal3)

### Disabling the feature

To disable auto ExternalIP and auto NATGateway:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP/NATGateway workflows remain functional
- No impact on existing running BM servers

## Infrastructure Needed

- AAP execution environment with fabric manager role (`create_network_attachment`, `delete_network_attachment`) for Netris (OSAC-2081)
- Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460)
- Integration test environment with Netris fabric manager and Ironic/Metal3 backend

## Dependencies

| Dependency | Jira | Status |
|-----------|------|--------|
| Dispatcher core | OSAC-1457, OSAC-1458, OSAC-1460 | In Progress |
| NATGateway full stack | OSAC-1443 (10 tasks) | 1/10 In Progress |
| ExternalIPAttachment BM target in CRD | OSAC-2041 | New |
| BM DNAT flow in controller | OSAC-1496 | New |
| BareMetalNetworkAttachment proto | OSAC-1508 | New |
| Primary field on BareMetalNetworkAttachment | OSAC-2042 | New |
| Immutability + interface + primary validation | OSAC-1509 | New |
| CLI --network-attachment for BareMetalInstance | OSAC-2075 | New |
| BM provisioning flow (operator reconcileNetworking calls create_network_attachment) | OSAC-2047 | New |
| Integration test | OSAC-1510 | New |
| Fabric manager create/delete_network_attachment role | OSAC-2081 (Netris BM) | New |
| BareMetalInstance CRD: add NetworkAttachments | Not tracked | **GAP** |
| mutateBMI: copy network_attachments to K8s CR | Not tracked | **GAP** |
| IP discovery: discover DHCP-assigned IP from host/inventory, write to CR status | Not tracked | **GAP** |
| bare-metal-fulfillment-operator dispatcher capability + RBAC for Subnet/NetworkClass CRs | Not tracked | **GAP** |
| Rename BareMetalInstance spec.networkClass → networkFabricManager | Not tracked | **GAP** |
| HostType: add structured NetworkInterface list (name, description) | Not tracked | **GAP** |
