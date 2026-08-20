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
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "baremetal-instance-api: https://github.com/osac-project/baremetal-instance-api"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking — Switch Port Configuration and Tenant-Defined Interface Mapping

BMaaS networking provides multi-NIC BaremetalInstance provisioning with tenant-specified physical interface mapping, switch port configuration via dispatcher, IP address feedback through CR status, and auto-provisioned external access (ExternalIP).

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how BMaaS consumes that architecture.

BaremetalInstance supports `BareMetalNetworkAttachment` with explicit `interface` and `primary` fields. The bare-metal-fulfillment-operator's `reconcileNetworking` phase configures switch ports via dispatcher, and IP address feedback via CR status enables DNAT rule creation. See [PRD](prd.md) for detailed requirements.

## Motivation

Bare-metal servers require explicit switch port configuration to participate in the OSAC Networking API. Unlike VMs (which live inside an OVN overlay bridged to the fabric), BM servers connect directly to the physical fabric — each NIC's switch port must be moved between network segments during the provisioning lifecycle.

### Architecture: Two Operators on One CR

```
fulfillment-service → creates BaremetalInstance CR → hub cluster
                                                        │
    bare-metal-fulfillment-operator ─────────────────────┤ (provisioning)
      - reconcileInventory (Ironic/Metal3)               │
      - reconcileProvisioning (AAP)                      │
      - reconcileNetworking (dispatcher)                 │
      - reconcileReboot (handoff)                        │
      - reconcileIPDiscovery (DHCP lease query)          │
      - reconcilePower (Ironic/Metal3)                   │
      - finalizers: inventory, baremetalinstance,         │
        baremetalinstance-networking                      │
                                                         │
    osac-operator ───────────────────────────────────────┘ (feedback + cleanup)
      - BareMetalInstanceFeedbackReconciler
      - fires Signal RPC on status change
      - finalizer: baremetalinstance-feedback (removed last)
      - BareMetalInstance cleanup controller (auto ExternalIP)
```

### Goals

**Core Design Goals (G1–G5):**

- **G1 — OS-agnostic host networking.** All host addressing via DHCP; no per-OS host-side config. Corollary: exactly one default route at any moment.
- **G2 — Provisioning connectivity.** During inspect + deploy the server can reach its image source and the Ironic conductor.
- **G3 — Correct, minimal final state.** After provisioning: attached to exactly the tenant network segment(s), single default route, no residual provisioning network.
- **G4 — Isolated until ready.** The tenant reaches the server only after it is fully provisioned and in its final network state; provisioning traffic is never exposed to the tenant.
- **G5 — Achievable on stock metal3 + fabric manager today.**

**Implementation Goals:**

- Multi-NIC support with explicit physical interface mapping (tenant specifies interface name from HostType)
- Resource-specific attachment message (`BareMetalNetworkAttachment`) with `interface` and `primary` fields
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- bare-metal-fulfillment-operator `reconcileNetworking` phase: dispatcher moves each interface's fabric port onto the tenant subnet's network segment (provisioning network → tenant) via the generic `move_network_attachment` role
- Provisioning network: an idle (unassigned) server keeps its fabric NIC on an OSAC-owned provisioning network (DHCP + gateway + SNAT) so it has internet during metal3 inspection; provisioning moves the port provisioning network → tenant, deletion moves it tenant → provisioning network (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- IP discovery after provisioning: operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role), matches the port MAC (resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to the DHCP-assigned IP, writes to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP for DNAT
- HostType resource with structured NetworkInterface list (name, role, description)
- Remove unused `networkClass` field from BareMetalInstance spec entirely (unused per reviewer feedback)

### The Three Network Planes

BMaaS involves three planes; this design owns only the data-plane ones. Do not conflate them.

| Plane | Carries | OS sees it? | Fabric-managed? | Owned by |
|-------|---------|-------------|-----------------|----------|
| **BMC / OOB** | Redfish/IPMI: power, virtual-media | Depends on wiring (dedicated port: no; shared-LOM: yes, own VLAN) | Not for now (separate mgmt network) | metal3 (prerequisite) |
| **Provisioning network** | host DHCP, image download, IPA→conductor callback | Yes (in-band, fabric NIC) | **Yes** | this design |
| **Tenant network** | tenant workload | Yes (fabric NIC after handoff) | Yes | this design |

"OOB" refers only to the BMC plane. The provisioning network is **in-band** (the OS/IPA uses it) — never call it OOB.

**Note on terminology:** In the current code and configuration, the provisioning network is identified as `netris_bm_parking_vnet`. This identifier is retained for deployment stability; the docs-only rename to "provisioning network" clarifies its purpose without requiring immediate config changes.

#### Connectivity Paths

| Path | Network |
|------|---------|
| Ironic → BMC (power/virtual-media) | mgmt/BMC network; conductor routes to BMC IPs |
| IPA → Ironic (callback) | provisioning network |
| Image download | provisioning network → local mirror (or internet) |
| Tenant DHCP + lease discovery | tenant network (fabric manager) |
| Fabric-port network move | fabric manager |

Ironic reaching two planes at once is ordinary **multi-homing**: the conductor host has a NIC/route to each network; it listens on all interfaces for inbound callbacks and the kernel selects egress NIC + source IP per destination. Which network carries the callback is set by the metal3 **`Provisioning` CR** (`provisioningNetwork`, `provisioningIP`/`provisioningInterface`, `virtualMediaViaExternalNetwork`), and each BMC address is per-host on the `BareMetalHost` (`spec.bmc.address`) — none of this is OSAC operator code.

### Non-Goals

- CaaS or VMaaS networking (this EP covers BMaaS only)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Creating the provisioning network (network segment + DHCP + gateway + SNAT) and the initial per-server attach — a deployment prerequisite handled by the fabric infrastructure / deployment infrastructure, not the operator (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- Re-provision handoff reset: NetworkHandoffComplete is never reset after initial provisioning, so an in-place re-provision (config-version change after Ready) would run over the tenant network (deferred to long-term design)

## Proposal

### HostType and Interface Validation

#### HostType Resource

The `HostType` resource in the fulfillment-service describes a class of hardware. For networking, BM host types include a structured interface list:

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
  string description = 3; // e.g., "100GbE fabric interface"
}
```

**The `interfaces` list is only populated for BM host types.** VM host types have an empty list — VMs get virtual NICs from the CUDN overlay, not physical interfaces. This also serves as the BM-vs-VM discriminator: if a HostType has interfaces → BM. If empty → VM.

Interfaces are ordered. When multiple interfaces share the same role, the first one in the list is the default for that role (used by CaaS for automatic resolution — see CaaS design).

#### How BMaaS Uses HostType

The tenant provides `BareMetalNetworkAttachment` with an explicit `interface` field referencing an interface `name` from the HostType's `interfaces` list. The fulfillment-service validates:
- The `interface` name exists in the HostType's `interfaces` list
- The HostType is resolved from the catalog_item / template's `host_type` field

Unlike CaaS (which picks the interface automatically by role), BMaaS gives the tenant direct control over which physical interface maps to which subnet.

#### Future: BareMetalInstanceType Integration

The [BareMetalInstanceType EP](/enhancements/OSAC-1201-baremetal-instance-types) introduces a tenant-facing hardware catalog for BMaaS. Once it lands, `BareMetalInstanceType` will provide richer tenant discovery (hardware specs, network port type and speed) and map to a HostType via `host_label_selector["hostType"]`.

When BareMetalInstanceType is available with enhanced `network_ports` (including `name` and `role` fields — see our [requested enhancements](https://github.com/osac-project/enhancement-proposals/pull/119#issuecomment-5088323110)):
- BMaaS tenants will discover available interfaces via the BareMetalInstanceType API (with type + speed info)
- Interface validation will switch from HostType to BareMetalInstanceType
- Interface/port names will be consistent across both resources (same physical NICs)
- HostType remains the system-level resource used by the operator and by CaaS

Until then, BMaaS uses HostType directly for interface validation — the same resource CaaS uses.

#### Interface Role Convention

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) |

Roles are conventions, not enforced enums. BMaaS uses them for display/documentation; the tenant selects by port name, not role. Ports with role `lifecycle` are used by the provisioning system (Ironic, Metal3) for PXE boot and BMC operations — they are NOT tenant-attachable and should not appear in `network_attachments`.

### Workflow Description

#### Phase 1: Tenant Creates Networking Resources

Same as VMaaS/CaaS — the networking API is uniform.

1. **Create VirtualNetwork:**
   ```bash
   osac create virtualnetwork --network-class moc --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_virtual_network`

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → fabric_manager creates VLAN/fabric segment. If the NetworkClass has a k8s_manager: also creates CUDN overlay (but BM doesn't use it — the overlay exists for VMs that may share the same subnet).

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
     --external-ip-attachment --name my-server
   ```

   After provisioning completes, `osac get baremetalinstance` shows the discovered internal IP:
   ```
   ID          NAME       CATALOG ITEM   STATE    INTERNAL IP
   01a0...     my-server  ci-bm-default  RUNNING  10.100.0.2
   ```

5. **fulfillment-service:**
   - If `network_attachments` omitted: populates with tenant's default Subnet + default SecurityGroup (see [Default Networking PRD](/enhancements/OSAC-1433-default-networking)). The system selects the first interface with role `fabric` from the HostType as the default interface for the single attachment (matching PRD FR-5).
   - Validates:
     - Each subnet exists, is Ready
     - All subnets belong to the same VirtualNetwork
     - Each SecurityGroup exists, is Ready, belongs to the same VN
     - Each `interface` references a valid interface name from the HostType's interfaces list
     - No duplicate interfaces across attachments
     - If >1 attachment without `interface`, reject (explicit interface required when multi-homed)
     - Number of attachments ≤ number of available interfaces on template
     - If multiple attachments, exactly one is `primary`; if single attachment, `primary` is implicit
   - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity, matching IP family), creates ExternalIP (labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <baremetal-instance-id>`) + ExternalIPAttachment (labeled `osac.openshift.io/auto-created: "true"`) in the same DB transaction — both start in **Pending** state. The ExternalIPAttachment references the BaremetalInstance but does not yet have a DNAT target IP (the BM's IP is unknown until `reconcileNetworking` runs). Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted (including the BaremetalInstance). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
   - Creates BaremetalInstance CR with `network_attachments` in spec

6. **bare-metal-fulfillment-operator BareMetalInstance controller:**

   a. `reconcileInventory` (unchanged):
      - FindFreeHost → AssignHost (Ironic/Metal3)
      - Populates HostClass from inventory

   b. `reconcileProvisioning` (runs after inventory):
      - Triggers AAP job via `RunProvisioningLifecycle`
      - Template does OS provisioning (PXE boot, user-data, etc.)
      - Server stays on the provisioning network during this phase
      - Host-side networking is handled by DHCP — the template does NOT configure static IPs, gateway, or DNS. The host receives its IP automatically from the provisioning network DHCP server.

   c. **`reconcileNetworking` (runs after provisioning is complete):**
      - Reads `network_attachments` from the CR spec
      - **Operator dispatches switch-side config:** For each attachment, the operator dispatches the `osac-move-network-attachment` job, which resolves `subnetRef` → tenant network segment name and moves the server's fabric port **provisioning network → tenant network** via `osac.templates.{{ fabric_manager }}.move_network_attachment` (`host_name` = fabric server name from ExternalHostID, `logical_interface_name` = interface name from HostType, `from_vnet_name` = provisioning network, `to_vnet_name` = tenant network segment). See [Provisioning Network and Port Moves](#provisioning-network-and-port-moves).
      - **Network segment readiness wait:** After each port attach, the move playbook polls the fabric manager until the target network segment reaches active/ready state. This ensures the switch fabric has fully converged before the operator triggers the handoff reboot — without this wait, the host may DHCP on the wrong network.
      - Sets condition: `NetworkAttachmentsReady=True`

   d. **`reconcileReboot` (runs after networking):**
      - Issues reboot via BareMetalHost annotation so the OS re-DHCPs on the tenant network
      - Waits for reboot to complete
      - Sets condition: `NetworkHandoffComplete=True`

   e. `reconcilePower` (unchanged)

7. **IP discovery and feedback (`reconcileIPDiscovery` — runs after reboot):**
   - After `reconcileReboot` completes and the host has received a DHCP lease on the tenant network, the operator queries the fabric manager's DHCP lease API via dispatcher (`osac.templates.{{ fabric_manager }}.query_dhcp_lease`). The role queries DHCP leases for the tenant subnet and matches the server's port MAC address (resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation — see [IP Discovery](#ip-discovery)) to find the corresponding DHCP-assigned IP on the tenant network.
   - Operator writes the discovered IP to `status.networkAttachmentStatuses[].ipAddress` on the BaremetalInstance CR
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
      2. **BaremetalInstance must have a primary IP** — reads `status.networkAttachmentStatuses[].ipAddress` for the attachment where `primary: true`. This IP is written by the operator during `reconcileIPDiscovery` (step 7) and synced to the fulfillment-service via the feedback controller.
    - Once both preconditions are met: writes `osac.openshift.io/target-ip` annotation on the ExternalIPAttachment CR
    - Calls `osac.templates.{{ fabric_manager }}.create_external_ip_attachment`
    - Fabric manager creates DNAT rule: external IP → BM's primary subnet IP
    - ExternalIPAttachment transitions from Pending to Ready

    For auto-provisioned ExternalIPAttachments (`auto_external_ip_attachment=true`), the same flow applies — the attachment is created at API time in Pending state and the controller activates it once the BM's IP becomes known. The wait time depends on `reconcileIPDiscovery` completion (IP discovery by the operator after provisioning completes and the host has received a DHCP lease).

#### Deletion (reverse order)

10. **Delete BaremetalInstance:**
    - **Auto-provisioned cleanup (osac-operator):** The osac-operator adds a cleanup finalizer (`osac.openshift.io/baremetalinstance-cleanup`) on BaremetalInstance CRs that have `auto_external_ip_attachment=true`. On deletion, it performs the phased requeue cleanup: deletes ExternalIPAttachment first (by target reference), waits, then deletes ExternalIP (by `auto-created-for` label), waits, then removes its finalizer. See [Unified Networking — Auto-provisioned resource cleanup](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the pattern. This runs concurrently with the bare-metal-fulfillment-operator's deletion flow but does not conflict (different CRs).
    - **Manually created resources are NOT cleaned up** — tenant manages their lifecycle.
    - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — tenant-scoped and shared.
    - bare-metal-fulfillment-operator (power-off-first ordering ensures tenant workloads **never** run on the provisioning network):
      - `reconcileNetworkOffboardShutdown`: powers off the host **while the port is still on the tenant network**, tracked by `NetworkOffboardComplete` condition. If the host is already powered off, this is a no-op. This guarantees the tenant workload stops before the port moves to the provisioning network.
      - `reconcileNetworking` (delete): dispatches the same `osac-move-network-attachment` job — because the CR now carries a `deletionTimestamp`, the playbook moves each port **tenant network → provisioning network** (`from_vnet_name` = tenant network segment, `to_vnet_name` = provisioning network), returning the fabric NIC to the provisioning network so the freed server keeps internet for its next inspection. The host is off at this point, so nothing runs on the provisioning network. A missing tenant Subnet CR is tolerated (detach skipped, port still returned to provisioning network).
      - `reconcileDeprovisioning`: triggers AAP delete job for OS teardown. Ironic powers the host back on via BMC and PXE-boots a cleaning ramdisk on the provisioning network — not the tenant OS.
      - Removes management finalizer
    - `reconcileInventory` deletion: UnassignHost from Ironic/Metal3, removes inventory finalizer
    - osac-operator feedback controller: waits for other finalizers, removes feedback finalizer, fires final Signal

11. **Tenant deletes networking resources** (independently):
    - Delete ExternalIPAttachments, ExternalIPs, SecurityGroup, Subnet, VirtualNetwork — each via its own dispatcher-triggered delete job

### API Extensions

#### Proto (fulfillment-service)

```protobuf
message BareMetalNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, mutable
  string interface = 3;                 // optional, immutable: physical interface
                                        // from BareMetalInstanceType
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
  bool auto_external_ip_attachment = 9;  // NEW, auto-provision ExternalIP + ExternalIPAttachment
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachment_statuses = N; // NEW
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
    NetworkAttachmentStatuses []BareMetalNetworkAttachmentStatus `json:"networkAttachmentStatuses,omitempty"`
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
- The `interface` must reference a valid port name from the BareMetalInstanceType (its network ports list defines available ports)
- Interfaces with role `lifecycle` are rejected in `network_attachments` — lifecycle interfaces (PXE boot, BMC) are reserved for the provisioning system and are not tenant-attachable
- If >1 attachment specified, each must have an explicit `interface` (multiple attachments without `interface` is invalid)
- Number of attachments ≤ number of available interfaces on the template
- If multiple attachments: exactly one must be `primary: true`
- If single attachment: `primary` is implicit (true by default)
- network_attachments are immutable after creation

### Implementation Details/Notes/Constraints

#### Provisioning Network and Port Moves

Bare-metal servers configure host-side networking entirely via DHCP. An
**unassigned** server (owned by no tenant) has no tenant network segment, so without
intervention it has no default gateway and no internet — which breaks the Ironic
Python Agent (IPA) during metal3 inspection/cleaning (it cannot download its
rootfs). Hanging the default gateway off the management/BMC NIC is not an option:
the host would then have two DHCP default routes (management + fabric) once a
tenant subnet is attached, causing a default-gateway race.

**Solution — a provisioning network.** A fabric manager **provisioning network
segment** (DHCP + default gateway + SNAT for outbound internet) holds every
server's **fabric NIC** while the server is idle and during provisioning, so an
unassigned server always has internet via its fabric NIC. The provisioning
network exists **only in the fabric manager** — it has no OSAC Subnet CR — and
its name is a fabric-manager configuration value (`netris_bm_provisioning_vnet`,
sourced from the `NETRIS_BM_PROVISIONING_VNET` environment variable, with
backward-compatible fallback to `NETRIS_BM_PARKING_VNET`), not operator state.

**Provision and deprovision are the same primitive: move a fabric port from one
network segment to another.** The port lifecycle is:

| Flow | Trigger | Move (from → to) | When |
|------|---------|------------------|------|
| Initial | Deployment bootstrap (deployment infrastructure) | — → provisioning network | Pre-deployment |
| Provision | BMI `reconcileNetworking` (after ProvisionTemplateComplete) | provisioning network → tenant subnet's network segment | **POST-provisioning** |
| Deprovision | BMI deletion (networking cleanup) | tenant subnet's network segment → provisioning network | Deletion |

**Key difference from the previous design:** The port move now happens **AFTER
provisioning is complete**, not before. The server is provisioned while on the
provisioning network, then moved to the tenant network and rebooted so the OS
re-DHCPs there. This achieves isolation-until-ready (G4): the tenant cannot reach
the server during imaging/first-boot, and provisioning traffic (image
pull/cloud-init) never traverses the tenant network.

Creating the provisioning network (network segment + DHCP + gateway + SNAT) and
performing the initial per-server attach are deployment prerequisites (handled by
the fabric infrastructure / deployment infrastructure), not operator responsibilities. The
provisioning network name configured for the fabric manager must match the one
used at bootstrap.

**Generic `move_network_attachment` role.** The fabric manager exposes a single
generic primitive, keyed on plain network segment **names**:

```
move_network_attachment(host_name, logical_interface_name,
                        from_vnet_name, to_vnet_name)
    → detach the server's fabric port from from_vnet_name (if set),
      then attach it to to_vnet_name (if set)
```

- The role resolves host → fabric server → fabric port, then detaches from the
  source network segment and attaches to the target. Either side may be empty (a
  pure attach or pure detach).
- Detach is a **no-op when the port is not on the named segment** (robust to
  retries and unexpected state); attach fails if the target segment or port
  cannot be resolved.
- It operates purely against the fabric manager — **no Subnet CR lookup inside
  the role**. Callers resolve a `subnetRef` → tenant network segment name and
  pass the provisioning network name from configuration.
- The primitive is backend-/lifecycle-agnostic: callers decide what the segments
  mean (tenant, provisioning, …), so CaaS can reuse it for its own
  provisioning-network flow.

**Single move playbook, direction from the CR.** One AAP job template
(`osac-move-network-attachment`, playbook
`playbook_osac_move_network_attachment.yml`) serves both provision and
deprovision. It derives direction from the CR: a resource carrying
`metadata.deletionTimestamp` is **offboarding** (tenant → provisioning network);
otherwise it is **onboarding** (provisioning network → tenant). The tenant network
segment is resolved per attachment from `subnetRef` (Subnet CR `metadata.name`
== fabric network segment name); the provisioning network name comes from
configuration. The
bare-metal-fulfillment-operator therefore points **both** its networking-provision
and networking-deprovision providers at the same `osac-move-network-attachment`
template — no direction plumbing in the operator.

#### Topology-Agnostic Operator (Transport is Environment Config)

The operator owns **network segment membership + lifecycle orchestration only**,
referenced by segment **name** (config/CR), never by physical transport:

- moves the fabric port between provisioning and tenant network segments,
- patches `spec.image`, reboots via the BMH annotation,
- discovers the tenant lease (`query_dhcp_lease`, MAC match).

The **transport** is environment config, not code:

- image source = `BareMetalHost.spec.image.url` / template param (local mirror or internet via provisioning network),
- callback/PXE/DHCP network = the metal3 `Provisioning` CR (`Managed`/`Unmanaged`/`Disabled` depending on deployment).

The operator must never assume the provisioning network carries the
image/callback (no egress checks, no SNAT logic).

#### Assumptions

- Single fabric NIC per server on the fabric (moves provisioning↔tenant).
- BMC reachability (Ironic↔BMC) is a deployment prerequisite on a tenant-isolated
  mgmt network; not fabric-managed for now.
- The provisioning network (network segment + DHCP + gateway + egress) and the
  initial per-server attach are deployment prerequisites (deployment infrastructure / inventory
  tooling), as today.
- Inventory tooling sets the `osac.openshift.io/interface-macs` annotation for
  the tenant NIC.
- **Self-contained images**: first boot needs no *tenant-side* internet
  (first-boot egress happens on the provisioning network during boot #1). A
  robust "cloud-init done" signal is a long-term item.

#### Tenant Handoff Signaling

The operator uses conditions and phase to signal tenant handoff readiness:

- `NetworkAttachmentsReady` — the tenant port is attached to the tenant network
  segment (set after the move + segment active wait).
- `NetworkHandoffComplete` — the port has been moved and the server has been
  rebooted; the OS is running on the tenant network.
- `IPDiscoveryComplete` — the tenant-network DHCP IP is discovered and valid.
  The orchestration function (`reconcileNetworkProvisionAndDiscovery`)
  explicitly checks this condition after `reconcileIPDiscovery` returns —
  if `IPDiscoveryComplete=False/TemplateFailed`, the phase is set to `Failed`
  and the flow stops. Without this explicit check, the phase could briefly
  reach `Ready` between IP discovery retry cycles.
- `NetworkOffboardComplete` (deletion only) — the host has been powered off
  while still on the tenant network, prior to the port moving back to the
  provisioning network. Tracked by `reconcileNetworkOffboardShutdown`.
- Phase `Ready` — fully provisioned + on the tenant network + IP known.

**Gating rule:** the operator must not surface a tenant IP or report `Ready`
until after move + segment active + reboot + discovery. The provisioning-network
IP is never exposed to the tenant. External access is signaled separately by
the `ExternalIPAttachment` (DNAT) and `NATGateway` (SNAT) CR statuses.

#### IP Discovery

IP discovery is decoupled from switch port configuration. The `move_network_attachment` role is switch-side only — it moves the server's fabric port onto the tenant subnet's network segment during `reconcileNetworking`, before the host boots. It does not query DHCP leases or return an IP address.

After `reconcileProvisioning` completes and the host has received a DHCP lease from the fabric's DHCP server, the operator runs `reconcileIPDiscovery`. This phase dispatches `osac.templates.{{ fabric_manager }}.query_dhcp_lease`, passing, per attachment, the subnet reference and the server's port MAC address. The role queries the fabric manager's DHCP lease API for the subnet, matches the port MAC to find the corresponding DHCP-assigned IP, and returns it. The operator writes the discovered IP to `status.networkAttachmentStatuses[].ipAddress` on the BaremetalInstance CR.

**MAC resolution — the `osac.openshift.io/interface-macs` contract.** Bare-metal servers are not registered as named fabric servers, so their DHCP leases appear in the fabric manager's IPAM as MAC-only host entries (no server name). To match a lease, the operator must know each attachment's NIC MAC. Inventory tooling annotates each `BareMetalHost` with a JSON map of OSAC interface name → NIC MAC, e.g. `{"eth9":"52:54:00:16:04:83"}`, under the `osac.openshift.io/interface-macs` annotation. During `reconcileIPDiscovery` the operator reads this annotation, builds a `subnetRef → MAC` map, and passes it to the job as an extra var (`network_attachment_macs`). The `query_dhcp_lease` role matches the IPAM host by MAC (the fabric manager stores lease MACs lowercase; the role compares against the lowercased `mac[].address` values). When no MAC is supplied, the role falls back to matching by server name — the path named CaaS fabric servers use, which BMaaS is converging onto.

The feedback controller syncs this to the fulfillment-service DB via the existing Signal / `syncStatus()` pattern. The ExternalIPAttachment controller reads the primary IP from CR status for DNAT creation.

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, copy to K8s CR via mutateBMI, auto-provision ExternalIP |
| bare-metal-fulfillment-operator | Inventory assignment, switch-side networking (dispatcher), OS provisioning (AAP), **IP discovery** via `query_dhcp_lease` dispatcher call after provisioning, power management |
| AAP BM provisioning template | OS provisioning only (host-side networking handled by DHCP) |
| osac-operator feedback controller | Signal fulfillment-service on status changes (unchanged), sync IP addresses from CR status to DB |
| osac-operator BMI cleanup controller | Clean up auto-provisioned ExternalIPAttachment → ExternalIP on BaremetalInstance deletion (phased requeue, `baremetalinstance-cleanup` finalizer) |
| osac-operator ExternalIPAttachment controller | Read BM's primary IP from CR status, create DNAT via fabric_manager |
| fabric_manager role (move_network_attachment) | Switch-side only: resolve host → fabric server → fabric port, detach from the source network segment (if set) and attach to the target segment (if set). Waits for target segment active state after attach. Serves both provisioning → tenant (provision) and tenant → provisioning (deprovision) |
| fabric_manager role (query_dhcp_lease) | Query fabric manager's DHCP lease API for a subnet, match the port MAC (or fall back to server name) to find the DHCP-assigned IP, return it |

#### Reconciliation Phase Ordering

**Target reconcile flow (provision-then-handoff):**

```
bare-metal-fulfillment-operator BareMetalInstance controller phases:
1. reconcileInventory → allocate host, populate HostClass
   Sets condition: InventoryAssigned=True

2. reconcileProvisioning → OS provisioning (AAP). Server stays on the provisioning network.
   Host PXE boots and gets IP from DHCP on the provisioning network.
   Requires: InventoryAssigned=True
   Sets condition: ProvisionTemplateComplete=True

3. reconcileNetworking → move fabric port provisioning network → tenant network
   (dispatcher, switch-side only; waits for network segment active after attach)
   Requires: ProvisionTemplateComplete=True
   Sets condition: NetworkAttachmentsReady=True

4. reconcileReboot → reboot server (BMH annotation) so OS re-DHCPs on tenant network
   Requires: NetworkAttachmentsReady=True
   Sets condition: NetworkHandoffComplete=True

5. reconcileIPDiscovery → query fabric manager's DHCP lease API via dispatcher
   (query_dhcp_lease), match port MAC to assigned IP on tenant network, write to CR status
   Requires: NetworkHandoffComplete=True
   Sets condition: IPDiscoveryComplete=True

6. Phase Ready → fully provisioned + on tenant network + IP known
   Requires: IPDiscoveryComplete=True

7. reconcilePower → power state management (independent)

Deletion (power-off-first — tenant workloads never touch provisioning network):
1. reconcileNetworkOffboardShutdown → power off while port is still on tenant network
   Sets condition: NetworkOffboardComplete=True
2. reconcileNetworking (delete) → move port tenant network → provisioning network
   Host is off — nothing runs on provisioning network
3. reconcileDeprovisioning → Ironic PXE boots cleaning ramdisk (not tenant OS)
4. reconcileInventory (delete) → unassign host
```

The server sits on the **provisioning network** (config identifier `netris_bm_provisioning_vnet`, with DHCP + gateway + egress) from bootstrap through the entire metal3 deploy and first boot. First-boot cloud-init runs there **with egress**, so first-boot pulls succeed. Only after `ProvisionTemplateComplete` does the operator move the fabric port to the tenant network (waiting for the network segment to reach active state) and issue **one reboot** so the OS re-DHCPs on the tenant network.

**Known behavior (Netris-specific) — DHCP cross-VLAN lease persistence:** The Netris softgate DHCP server is not VLAN-scoped — it serves all V-Nets through the softgate. When the OS reboots after a port move, NetworkManager may attempt a DHCP REQUEST renewal for the old (provisioning) IP. The softgate can ACK this renewal even though the port is on the tenant VLAN, resulting in the host keeping the provisioning IP. The network segment readiness wait mitigates this by ensuring the fabric has fully converged, but in some timing scenarios a second reboot (or DHCP release before reboot) may be needed. This is a known limitation of the Netris DHCP architecture; other fabric managers with VLAN-scoped DHCP would not exhibit this behavior.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent BaremetalInstance
- No new authentication or authorization changes
- SecurityGroup rules control BM inbound traffic (tenant-configurable via explicit SG or default SG)
- Multi-NIC BM servers on different subnets share the same SecurityGroup enforcement (fabric-level ACL rules apply to all interfaces)

### Failure Handling and Recovery

#### bare-metal-fulfillment-operator Reconciliation Failures

- Inventory assignment failure (no free hosts): BaremetalInstance enters Failed state with condition, retries when host becomes available
- Networking failure (dispatcher call failed, switch port config failed): BaremetalInstance enters Failed state with condition, retries on manual correction
- AAP job failure (template execution error): BaremetalInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types))
- ExternalIP provisioning failure: ExternalIP enters Failed state, BaremetalInstance remains in Pending (external access unavailable, BM may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach BM (BM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

The bare-metal-fulfillment-operator needs additional RBAC permissions: get/list/watch on Subnet and NetworkClass CRs, required for the dispatcher to resolve networking configuration during `reconcileNetworking`.

All new resources (BaremetalInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from BaremetalInstance to auto-created resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- bare-metal-fulfillment-operator: `NetworkingReconciled` (info), `NetworkingReconciliationFailed` (error), `SwitchPortConfigured` (info), `IPAddressAllocated` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error), `InterfaceValidationFailed` (error)

New Kubernetes events on BaremetalInstance:
- `NetworkingConfigured`: switch ports configured, IPs allocated
- `NetworkingConfigurationFailed`: networking reconciliation failed (dispatcher error, switch port config error)
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: fabric_manager implementation blocked or delayed

**Impact:** The fabric manager `move_network_attachment` role and a provisioned provisioning network segment are prerequisites for BMaaS networking. Without them, switch port configuration cannot function.

**Mitigation:** Prioritize Netris BM roles (OSAC-2081). Accept that BMaaS remains unavailable until a fabric_manager exists. Document as a hard dependency.

**Reviewed by:** Engineering / Product

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create BM with `auto_external_ip_attachment=true`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

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

## Open Questions

### ~~1. Should auto NATGateway treat a Deleting NATGateway as 'does not exist'?~~ — Resolved

Resolved: NATGateway reuse limited to Ready only. Failed/Deleting NATGateways cause the create request to fail with an error. NATGateway auto-provisioning per resource was removed — NATGateway is now a VN default created at tenant onboarding.

### ~~2. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity checked synchronously. No Failed resource.

### ~~3. IP address assignment~~ — Resolved

Resolved: DHCP handles IP assignment. The host receives its IP from the fabric's DHCP server after booting on the network segment. No operator IPAM needed.

### ~~4. How is the host's runtime IP discovered after network reconfiguration?~~ — Resolved

Resolved: After `reconcileProvisioning` completes and the host has received a DHCP lease, the operator queries the fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role). The role matches the server's port MAC address — resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation — to find the assigned IP (falling back to server-name matching for named fabric servers). The operator writes to `status.networkAttachmentStatuses[].ipAddress` on the BaremetalInstance CR. The feedback controller then syncs to fulfillment-service via Signal RPC. `move_network_attachment` remains switch-side only (moves the fabric port between network segments).

## Test Plan

### Unit Tests

- fulfillment-service: primary validation (reject >1 primary, accept single implicit primary, accept explicit primary)
- fulfillment-service: interface validation (reject interface not in BareMetalInstanceType, reject duplicate interfaces, reject >1 attachment without interface)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- bare-metal-fulfillment-operator: reconcileNetworking phase ordering (after inventory, before provisioning)
- bare-metal-fulfillment-operator: dispatcher call per attachment (move_network_attachment with correct from/to network segment params, direction from deletionTimestamp)
- bare-metal-fulfillment-operator: `buildSubnetMACMap` resolves subnetRef → MAC from the interface-macs annotation (single-NIC fallback when interface unset)

### Integration Tests

- E2E: create BaremetalInstance with multiple attachments, verify switch ports configured for each interface, IPs allocated from each subnet
- E2E: create BaremetalInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: delete BaremetalInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create BaremetalInstance with interface not in BareMetalInstanceType, verify error returned
- E2E: create BaremetalInstance with >1 attachment but no interface fields, verify error returned
- E2E: verify IP discovery (`query_dhcp_lease` role queries fabric manager DHCP lease API after provisioning + reboot, matches port MAC to assigned IP on tenant network, operator writes to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP)
- E2E: verify the port move and reboot flow — create BMI provisions on the provisioning network, then moves the fabric port provisioning network → tenant network + reboots; delete BMI returns it tenant → provisioning network (confirm in fabric manager; a freed server can re-inspect with internet)
- E2E: verify isolation-until-ready — before the move, a tenant vantage cannot reach the server; after move + reboot, it can, and the server is no longer on the provisioning network

### Tricky Test Cases

- Multi-NIC BM with primary on second interface (verify default gateway on correct interface)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)
- IP address feedback latency (verify ExternalIPAttachment controller waits for IP to appear in status)

## Long-Term Evolution (The Reboot is the Seam)

The structure `inventory → provision → establish-tenant-networking → discovery`
stays; only "establish-tenant-networking" changes:

**Ironic Standalone Networking** (metal3-docs PR #586; BMO PR #3469, ToR
networking part 1): Ironic switches the port VLAN per lifecycle phase
(provisioning→tenant) on one NIC — drop the reboot. Upstream assumes
`networking-generic-switch` (direct ToR control), which does not fit
The fabric manager owns the switch; adopting a new backend means implementing the fabric manager interface or aligning the model.

**Dedicated always-on provisioning NIC** (two NICs): attach the tenant NIC after
`provisioned`; no move of the provisioning NIC. Needs 2 NICs, a local registry,
gateway-less provisioning DHCP, and provisioning-network isolation.

**Static host-side networking + IPAM** (`networkData`): one boot, but not
OS-agnostic and reintroduces IPAM. Opt-in fast path for capable, self-contained
images.

Each evolution replaces just the reboot step while preserving the same overall
flow and operator structure.

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachments`, `auto_external_ip_attachment`) implemented in fulfillment-service
- [ ] BaremetalInstance CRD updated with `NetworkAttachments` field, CEL validation, and status field for IP addresses
- [ ] bare-metal-fulfillment-operator `reconcileNetworking` phase implemented (provision-then-handoff flow)
- [ ] bare-metal-fulfillment-operator `reconcileReboot` phase implemented (BMH annotation-based reboot after port move)
- [ ] Dispatcher integration for `move_network_attachment` (provision + deprovision via one job template); provisioning network provisioned and initial per-server attach done at deployment
- [ ] BareMetalInstanceType with network ports (`BareMetalNetworkPortSpec`) available and tested
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] IP discovery implemented (`query_dhcp_lease` role queries fabric manager DHCP lease API after provisioning + reboot, matches port MAC to assigned IP on tenant network, operator writes to CR status, feedback syncs to fulfillment-service)
- [ ] Tenant handoff signaling (NetworkAttachmentsReady, NetworkHandoffComplete, IPDiscoveryComplete, Ready) implemented
- [ ] Integration tests pass (E2E coverage for multi-NIC, auto ExternalIP, IP feedback, isolation-until-ready)
- [ ] Documentation: API reference, user guide for simplified BM creation

GA criteria:
- [ ] fabric_manager implementation (Netris BM roles, OSAC-2081) delivered and production-tested
- [ ] Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460) implemented and stable
- [ ] NATGateway full stack (OSAC-1443) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)
- [ ] Reboot-based short-term validated; evolution path to Ironic Standalone Networking or dedicated provisioning NIC confirmed

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`network_attachments`, `auto_external_ip_attachment`) are additive — existing BaremetalInstance resources continue to work without networking fields
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Tenant User encouraged to migrate to new networking fields via CLI update (`osac-cli` supports new `--network-attachment` flag with `--interface` and `--primary`)
- No breaking changes — networking fields remain optional

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and bare-metal-fulfillment-operator images to `N`
- Existing BaremetalInstance resources with new `network_attachments` field will be unrecognized by `N` operator
- Manual cleanup required: delete BaremetalInstance resources created with new field, re-create without networking fields
- Auto-provisioned ExternalIP resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Delete CRs using new field (`network_attachments`)
- Re-create without networking fields
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment labeled `osac.openshift.io/auto-created: "true"`)

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
2. Check AAP job logs for `move_network_attachment` role errors (switch-side) — e.g. port not found on the server, or the provisioning/tenant network segment not resolvable
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

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-created: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check BaremetalInstance deletion logs (bare-metal-fulfillment-operator logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Symptom: ExternalIPAttachment stuck in Pending, waiting for BM IP address

**Detection:** `kubectl describe externalipattachment <name> -n <namespace>` shows condition "WaitingForIPAddress"

**Cause:** Host has not yet received DHCP-assigned IP (provisioning still in progress or failed)

**Resolution:**
1. Check BaremetalInstance status: `kubectl get baremetalinstance <name> -n <namespace> -o jsonpath='{.status.networkAttachmentStatuses[?(@.primary==true)].ipAddress}'`
2. If IP is missing, check bare-metal-fulfillment-operator logs for provisioning phase completion
3. If provisioning completed but IP missing, investigate `query_dhcp_lease` dispatcher call (DHCP lease query may have failed, returned empty, or port MAC did not match any lease). Confirm the BareMetalHost carries the `osac.openshift.io/interface-macs` annotation with the attachment's interface — without it, MAC matching is skipped and only named fabric servers resolve

### Disabling the feature

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running BM servers

## Infrastructure Needed

- AAP execution environment with the fabric manager `move_network_attachment` role
- A provisioned provisioning network segment (DHCP + gateway + SNAT, config identifier `netris_bm_provisioning_vnet`) and the initial per-server attach, plus the BareMetalHost `osac.openshift.io/interface-macs` annotation — deployment prerequisites (deployment infrastructure)
- Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460)
- Integration test environment with fabric manager and Ironic/Metal3 backend

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
| BM provisioning flow (operator reconcileNetworking dispatches move_network_attachment after provisioning, provisioning network → tenant) | OSAC-2047 | New |
| BM reboot flow (reconcileReboot issues BMH annotation-based reboot after port move) | Not tracked | **GAP** |
| Integration test | OSAC-1510 | New |
| Fabric manager `move_network_attachment` role (generic port move) | OSAC-2081 (Netris BM) | New |
| Provisioning network segment (DHCP + gateway + SNAT, config identifier `netris_bm_provisioning_vnet`) + initial per-server attach in setup-bmaas | osac-deployment infrastructure | New |
| BareMetalHost `osac.openshift.io/interface-macs` annotation (inventory tooling) | osac-deployment infrastructure | New |
| BareMetalInstance CRD: add NetworkAttachments | Not tracked | **GAP** |
| mutateBMI: copy network_attachments to K8s CR | Not tracked | **GAP** |
| IP discovery: `query_dhcp_lease` role matches port MAC (from interface-macs annotation) to lease, operator writes to CR status | Not tracked | **GAP** |
| bare-metal-fulfillment-operator dispatcher capability + RBAC for Subnet/NetworkClass CRs | Not tracked | **GAP** |
| Remove unused BareMetalInstance spec.networkClass field | Not tracked | **GAP** |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed, description | Not tracked | **GAP** |
