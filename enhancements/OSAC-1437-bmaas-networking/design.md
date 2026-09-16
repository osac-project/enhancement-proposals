---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "K8s-only Networking Manager: /enhancements/OSAC-1433-k8s-only-k8s-manager"
  - "baremetal-instance-api: https://github.com/osac-project/baremetal-instance-api"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking — Switch Port Configuration and Tenant-Defined Interface Mapping

BMaaS networking provides single-NIC BaremetalInstance provisioning with
tenant-selected physical interface mapping, switch port configuration via
dispatcher, IP address feedback through CR status, and auto-provisioned
external access (ExternalIP). Each BaremetalInstance has exactly one tenant
network attachment; multi-NIC and multi-homed tenant attachments are not
supported.

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how BMaaS consumes that architecture.

Shared field types, formats, presence rules, allowed values, and validation
are defined by the [Unified Networking field contract](/enhancements/OSAC-1433-unified-networking/design.md#field-types-formats-and-validation).

The shared networking resource model and IPv4-only scope are defined by the
[Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).
The connected-only deployment boundary, including the exclusion of air-gapped
deployments, is defined by the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary).
The shared operation contract is defined by [Supported Operations and
Immutability](/enhancements/OSAC-1433-unified-networking/design.md#supported-operations-and-immutability).

BMaaS inherits the Unified Networking [strict dependency-ready creation
contract](/enhancements/OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation): the resolved Subnet, SecurityGroups,
effective NetworkACL, BareMetalInstanceType, and provisioning inputs must be
Ready before a BaremetalInstance or private worker request is persisted. The
OSAC-owned automatic ExternalIP/ExternalIPAttachment pair is the only
allowlisted Pending-child exception; BMaaS never creates a workload merely to
wait for a Pending network dependency.

BaremetalInstance exposes the repeated `network_attachments` API field, whose
values are `BareMetalNetworkAttachment` messages. The field remains
list-shaped for API compatibility but accepts zero or one entry; its single
attachment is implicitly primary. The
bare-metal-fulfillment-operator's `reconcileNetworking` phase configures the
selected switch port via dispatcher, and IP address feedback via CR status
enables DNAT rule creation. See [PRD](prd.md) for detailed requirements.

## Motivation

Bare-metal servers require explicit switch port configuration to participate in the OSAC Networking API. Unlike VMs (which live inside an OVN overlay bridged to the fabric), BM servers connect directly to the physical fabric — the selected tenant NIC's switch port must be moved between network segments during the provisioning lifecycle.

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
- **G3 — Correct, minimal final state.** After provisioning: attached to exactly the tenant network segment, single default route, no residual provisioning network.
- **G4 — Isolated until ready.** The tenant reaches the server only after it is fully provisioned and in its final network state; provisioning traffic is never exposed to the tenant.
- **G5 — Achievable on stock metal3 + fabric manager today.**

**Implementation Goals:**

- Single-NIC support with explicit physical interface mapping (tenant specifies one interface name from BareMetalInstanceType)
- Resource-specific attachment message (`BareMetalNetworkAttachment`) with one optional `interface` selector
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- bare-metal-fulfillment-operator `reconcileNetworking` phase: dispatcher moves the selected interface's fabric port onto the tenant subnet's network segment (provisioning network → tenant) via the generic `move_network_attachment` role
- Provisioning network: an idle (unassigned) server keeps its fabric NIC on an OSAC-owned provisioning network (DHCP + gateway + SNAT) so it has internet during metal3 inspection; provisioning moves the port provisioning network → tenant, deletion moves it tenant → provisioning network (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- IP discovery after provisioning: operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role), matches the selected port MAC (resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to the DHCP-assigned IP, writes to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads the single tenant IP for DNAT
- BareMetalInstanceType `network_ports` list with structured port definitions (name, role, type, speed)
- Remove unused `networkClass` field from BareMetalInstance spec entirely (unused per reviewer feedback)

### The Three Network Planes

BMaaS involves three planes; this design owns only the data-plane ones. Do not conflate them.

| Plane | Carries | OS sees it? | Fabric-managed? | Owned by |
|-------|---------|-------------|-----------------|----------|
| **BMC / OOB** | Redfish/IPMI: power, virtual-media | Depends on wiring (dedicated port: no; shared-LOM: yes, own VLAN) | Not for now (separate mgmt network) | metal3 (prerequisite) |
| **Provisioning network** | host DHCP, image download, IPA→conductor callback | Yes (in-band, fabric NIC) | **Yes** | this design |
| **Tenant network** | tenant workload | Yes (fabric NIC after handoff) | Yes | this design |

"OOB" refers only to the BMC plane. The provisioning network is **in-band** (the OS/IPA uses it) — never call it OOB.

**Note on terminology:** The deployment-specific provisioning-network
identifier is retained for deployment stability; the docs use
"provisioning network" to clarify its purpose without requiring a config
rename.

#### Connectivity Paths

| Path | Network |
|------|---------|
| Ironic → BMC (power/virtual-media) | mgmt/BMC network; conductor routes to BMC IPs |
| IPA → Ironic (callback) | provisioning network |
| Image download | provisioning network → local mirror (or internet) |
| Tenant DHCP + lease discovery | tenant network (fabric manager) |
| Fabric-port network move | fabric manager |

Ironic reaching two planes at once is ordinary conductor-side **multi-homing**;
this is infrastructure connectivity and is not a BMaaS tenant attachment. The
conductor host has a NIC/route to each network; it listens on all interfaces
for inbound callbacks and the kernel selects egress NIC + source IP per
destination. Which network carries the callback is set by the metal3
**`Provisioning` CR** (`provisioningNetwork`, `provisioningIP`/`provisioningInterface`,
`virtualMediaViaExternalNetwork`), and each BMC address is per-host on the
`BareMetalHost` (`spec.bmc.address`).

### Non-Goals

- CaaS or VMaaS networking (this EP covers BMaaS only)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Creating the provisioning network (network segment + DHCP + gateway + SNAT) and the initial per-server attach — a deployment prerequisite handled by the fabric infrastructure / deployment infrastructure, not the operator (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- Re-provision handoff reset: NetworkHandoffComplete is never reset after initial provisioning, so an in-place re-provision (config-version change after Ready) would run over the tenant network (deferred to long-term design)

## Proposal

### BareMetalInstanceType and Interface Validation

#### BareMetalInstanceType Network Ports

The `BareMetalInstanceType` resource in the fulfillment-service (OSAC-1201) describes a class of bare-metal hardware. For networking, BareMetalInstanceTypes include a structured network ports list:

```protobuf
message BareMetalNetworkPortSpec {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0"
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string type = 3;        // e.g., "Ethernet"
  string speed = 4;       // e.g., "100Gbps", "1Gbps"
}
```

`BareMetalInstanceType` is a bare-metal-only resource (OSAC-1201) — BM vs VM is classified by resource type (`BareMetalInstance` vs `ComputeInstance`), not by the contents of `network_ports`. Every `BareMetalInstanceType` must declare at least one `network_ports` entry with `role=fabric`; a bare-metal profile with no fabric port is rejected at creation time because both the operator (provisioning-network port move) and the default-interface resolution (first `role=fabric` port) depend on it. OSAC-1201 structurally validates that `role` is non-empty; BMaaS applies the supported attachment-role rules when a port is selected, and does not treat an unknown role as `fabric`.

Interfaces are ordered. When multiple interfaces share the same role, the first one in the list is the default for that role (used by CaaS for automatic resolution — see CaaS design).

**Interface-name identity contract.** `BareMetalNetworkAttachment.interface` selects a port by `BareMetalNetworkPortSpec.name`. The operator passes this name as `logical_interface_name` to `move_network_attachment`, and the `osac.openshift.io/interface-macs` annotation keys use the same name. These three identifiers — catalog port name, fabric-manager logical interface, and interface-macs annotation key — must be consistent; a mismatch causes the port move or DHCP lease query to target the wrong NIC. Inventory tooling and BareMetalInstanceType registration must align on the same naming convention.

The interface catalog may contain multiple physical NICs, but BMaaS selects
only one for the tenant network. The presence of additional interfaces does
not enable multiple network attachments on a BaremetalInstance.

#### How BMaaS Uses BareMetalInstanceType

The tenant provides `BareMetalNetworkAttachment` with an explicit `interface` field referencing a port `name` from the BareMetalInstanceType's `network_ports` list. The fulfillment-service validates:
- The `interface` name exists in the BareMetalInstanceType's `network_ports` list
- The BareMetalInstanceType is resolved from the instance's `instance_type` field

Unlike CaaS (which picks the interface automatically by role), BMaaS gives the tenant direct control over which physical interface maps to which subnet.

#### BareMetalInstanceType as the Authoritative Model

The [BareMetalInstanceType EP](/enhancements/OSAC-1201-baremetal-instance-types) provides the tenant-facing hardware catalog for BMaaS, with full hardware specs and network port definitions (name, role, type, speed). Per [OSAC-2135 (CaaS Bare-Metal Worker Node Provisioning)](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), `HostType` is deprecated and decommissioned — `BareMetalInstanceType` is now the sole source of truth for hardware profiles and interface resolution:

- BMaaS tenants discover available interfaces via the BareMetalInstanceType API (with type + speed info)
- Interface validation uses BareMetalInstanceType's `network_ports` list
- CaaS resolves the fabric interface from `BareMetalInstanceType.network_ports[].role=fabric`
- `BareMetalInstanceType.host_label_selector` provides direct inventory matching (OSAC-1201), replacing the former HostType reverse lookup

> **CaaS network attachment source:** For CaaS bare-metal workers, the typed
> network attachment originates from `ClusterOrder.spec.networkAttachment`
> (`ClusterNetworkAttachment`) and is enriched per-BMI by the
> `BareMetalWorkerReconciler`, using the immutable `fabric_interface` resolved
> once by fulfillment-service from the node set's `BareMetalInstanceType.network_ports[]`
> (first port with `role=fabric`). See [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md)
> for the full enrichment flow.

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
   osac create virtualnetwork --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → one `create_virtual_network` job for each configured manager

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → one job for each configured manager. BMaaS itself does not use a K8s
   overlay, but a combined deployment may create one for VMs sharing the
   subnet.

3. **Create policy resources through every configured manager target:**
   ```bash
   osac create network-acl --virtual-network my-net --name my-nacl \
     --subnet my-subnet \
     --rule "action=allow,direction=ingress,protocol=tcp,port=443,source-cidr=0.0.0.0/0"
   ```
   The NetworkACL is Subnet-associated. A SecurityGroup, when used, is carried
   by the BareMetalNetworkAttachment and contains stateful allow-only rules.
   Dispatcher → every configured manager; if both are configured, both
   internal targets must reconcile. A temporary unfinished operation may use a
   successful no-op AAP role.

#### Phase 2: Tenant Creates BM Server

4. **Create BaremetalInstance with network_attachments:**

   Single interface (simple case):
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --network-attachment interface=data-0,subnet=my-subnet \
     --name my-server
   ```
   The CLI's singular `--network-attachment` option populates the repeated
   `network_attachments` API field with its one allowed entry.

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
   - If `network_attachments` is omitted or empty: populates the tenant
     default Subnet, and the default SecurityGroup only when that Subnet is in
     the tenant default VirtualNetwork, and selects the
     first interface with role `fabric` from the BareMetalInstanceType. For a
     supplied single entry, defaults only missing Subnet, SecurityGroup, or
     interface fields (see [Default Networking PRD](/enhancements/OSAC-1433-default-networking)).
     The effective interface source is the BareMetalInstanceType's
     `network_ports` list.
   - Validates:
     - The Subnet exists and is Ready; its effective NetworkACL is Ready
     - The Subnet and effective NetworkACL belong to the same VirtualNetwork
     - Every referenced/default SecurityGroup is Ready, unique, same-tenant,
       and in the same VirtualNetwork
     - If the supplied Subnet is outside the tenant default VirtualNetwork and
       no compatible SecurityGroup is supplied, reject with `InvalidArgument`;
       never apply the default-VN SecurityGroup. A Subnet without a Ready
       effective ACL is rejected for BM placement with `FailedPrecondition`.
     - At most one network attachment is accepted for each BaremetalInstance
     - If an attachment is provided, its `interface` references a valid interface name from the BareMetalInstanceType's network ports list
     - If an attachment's `interface` is omitted, it defaults to the first port with `role=fabric` from the BareMetalInstanceType
     - The single attachment is implicitly primary and supplies the default gateway
   - If `auto_external_ip_attachment == true`: auto-selects an IPv4 ExternalIPPool (READY, most available capacity), creates an ExternalIP and ExternalIPAttachment with the canonical `osac.openshift.io/auto-created: "true"` marker and an exact immutable BaremetalInstance owner relationship in the same DB transaction — both start in **Pending** state. The ExternalIP may also expose `osac.openshift.io/auto-created-for: <baremetal-instance-id>` for indexed discovery, but that label is not ownership proof. The ExternalIPAttachment references the BaremetalInstance but does not yet have a DNAT target IP (the BM's IP is unknown until `reconcileNetworking` runs). Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted (including the BaremetalInstance). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
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
      - Reads the sole entry from the `network_attachments` list in the CR spec
        (the API keeps the repeated field for compatibility; validation rejects
        lists with more than one entry)
      - **Operator dispatches switch-side config:** The operator dispatches the `osac-move-network-attachment` job, which resolves the typed `subnet` reference → tenant network segment name and moves the server's selected fabric port **provisioning network → tenant network** via `osac.templates.{{ fabric_manager }}.move_network_attachment` (`host_name` = fabric server name from ExternalHostID, `logical_interface_name` = interface name from BareMetalInstanceType, `from_vnet_name` = provisioning network, `to_vnet_name` = tenant network segment). See [Provisioning Network and Port Moves](#provisioning-network-and-port-moves).
      - **Network segment readiness wait:** After the port attach, the move playbook polls the fabric manager until the target network segment reaches active/ready state. This ensures the switch fabric has fully converged before the operator triggers the handoff reboot — without this wait, the host may DHCP on the wrong network.
      - Sets condition: `NetworkAttachmentsReady=True`

   d. **`reconcileReboot` (runs after networking):**
      - Issues reboot via BareMetalHost annotation so the OS re-DHCPs on the tenant network
      - Waits for reboot to complete
      - Sets condition: `NetworkHandoffComplete=True`

   e. `reconcilePower` (unchanged)

7. **IP discovery and feedback (`reconcileIPDiscovery` — runs after reboot):**
   - After `reconcileReboot` completes and the host has received a DHCP lease on the tenant network, the operator queries the fabric manager's DHCP lease API via dispatcher (`osac.templates.{{ fabric_manager }}.query_dhcp_lease`). The role queries DHCP leases for the tenant subnet and matches the server's port MAC address (resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation — see [IP Discovery](#ip-discovery)) to find the corresponding DHCP-assigned IP on the tenant network.
   - Operator writes the discovered IP to the single `status.networkAttachmentStatuses` entry on the BaremetalInstance CR
   - Feedback controller watches CR status changes → fires Signal RPC to fulfillment-service
   - fulfillment-service reconciler syncs the discovered IP to the DB via existing `syncStatus()` pattern

#### Phase 3: External Access (optional)

8. **Create ExternalIP:**
   ```bash
   osac create externalip --pool external-pool-1 --name my-ip
   ```
   Dispatcher → one `create_external_ip` job for each configured manager

9. **Create ExternalIPAttachment:**
    ```bash
    osac create externalipattachment --externalip my-ip \
      --baremetal-instance my-server --name bm-att
    ```
    - ExternalIPAttachment controller resolves the BaremetalInstance target by UUID label
    - Checks two preconditions before dispatching (requeues if either is not met):
      1. **ExternalIP must be Allocated** by every selected manager
      2. **BaremetalInstance must have its tenant IP** — reads the single `status.networkAttachmentStatuses[].ipAddress` entry. This IP is written by the operator during `reconcileIPDiscovery` (step 7) and synced to the fulfillment-service via the feedback controller.
    - Once both preconditions are met: writes `osac.openshift.io/target-ip` annotation on the ExternalIPAttachment CR
      - Calls the external-IP attachment operation on every selected
      manager for that resource
    - The selected manager implementation(s) create the DNAT rule: external
      IP → BM's primary subnet IP
    - ExternalIPAttachment transitions from Pending to Ready

    For auto-provisioned ExternalIPAttachments (`auto_external_ip_attachment=true`), the same flow applies — the attachment is created at API time in Pending state and the controller activates it once the BM's IP becomes known. The wait time depends on `reconcileIPDiscovery` completion (IP discovery by the operator after provisioning completes and the host has received a DHCP lease).

#### Deletion (reverse order)

10. **Delete BaremetalInstance:**
    - **Auto-provisioned cleanup (osac-operator):** The osac-operator adds a cleanup finalizer (`osac.openshift.io/baremetalinstance-cleanup`) on BaremetalInstance CRs that have `auto_external_ip_attachment=true`. On deletion, it cleans only allowlisted ExternalIPAttachment and ExternalIP resources whose immutable owner is exactly this BaremetalInstance: attachment first, waits for full removal, then ExternalIP, waits for full removal, and only then removes its finalizer. A label alone is not sufficient ownership proof. See [Unified Networking — auto-provisioned resource cleanup](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared pattern. This runs concurrently with the bare-metal-fulfillment-operator's deletion flow but does not conflict (different CRs).
    - **Manually created resources are NOT cleaned up** — a manually created
      ExternalIP persists until the tenant deletes it. A manually created
      ExternalIPAttachment targeting the BaremetalInstance remains a reverse
      reference and blocks BaremetalInstance deletion until the tenant deletes
      the attachment; it is not detached or changed to Pending implicitly.
    - **Default networking resources (VN, Subnet, SecurityGroup, NetworkACL, NATGateway) are NOT cleaned up** — tenant-scoped and shared.
    - bare-metal-fulfillment-operator (power-off-first ordering ensures tenant workloads **never** run on the provisioning network):
      - `reconcileNetworkOffboardShutdown`: powers off the host **while the port is still on the tenant network**, tracked by `NetworkOffboardComplete` condition. If the host is already powered off, this is a no-op. This guarantees the tenant workload stops before the port moves to the provisioning network.
      - `reconcileNetworking` (delete): dispatches the same `osac-move-network-attachment` job — because the CR now carries a `deletionTimestamp`, the playbook moves the selected port **tenant network → provisioning network** (`from_vnet_name` = tenant network segment, `to_vnet_name` = provisioning network), returning the fabric NIC to the provisioning network so the freed server keeps internet for its next inspection. The host is off at this point, so nothing runs on the provisioning network. A missing tenant Subnet CR is tolerated (detach skipped, port still returned to provisioning network). The port move invalidates/releases the tenant-network DHCP lease. The operator must confirm through the fabric manager's deprovision result or lease query that the selected port no longer holds a tenant-network address before completing network cleanup. If the lease remains, the networking finalizer stays in place and reconciliation retries; the BaremetalInstance status must not continue to advertise the released tenant address after cleanup completes.
      - `reconcileDeprovisioning`: triggers AAP delete job for OS teardown. Ironic powers the host back on via BMC and PXE-boots a cleaning ramdisk on the provisioning network — not the tenant OS.
      - Removes management finalizer
    - `reconcileInventory` deletion: UnassignHost from Ironic/Metal3, removes inventory finalizer
    - osac-operator feedback controller: waits for other finalizers, removes feedback finalizer, fires final Signal

11. **Tenant deletes networking resources** (independently and leaf-first):
    - Delete tenant-managed ExternalIPAttachments, SecurityGroups, NetworkACLs, and other workload references first.
    - Delete ExternalIPs only after all consuming ExternalIPAttachments and NATGateways are fully gone.
    - Delete Subnets only after all BaremetalInstances, ComputeInstances, Clusters, and NetworkACL associations are fully gone.
    - Delete VirtualNetworks only after all Subnets, SecurityGroups, NetworkACLs, and NATGateways are fully gone.
    - Each accepted delete uses the shared transactional blocker contract and each rejected delete reports the blocking resource kind, ID/name, relationship, and required next action.

**BMaaS-specific deletion dependency guard:**

The Subnet deletion path uses the shared transactional reverse-reference
guard. It reports every direct BaremetalInstance attachment and every
NetworkACL association that still exists, including resources already marked
for deletion but not yet archived. The controller may wait for backend
finalizers only after API admission succeeds; it must not use a delayed
controller list as a replacement for the API guard. See [Unified Networking —
Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)
for the full guard table covering all networking resources.

**IP discovery lease validation:**

The IP discovery phase (`reconcileIPDiscovery`) requires that the single
network attachment has a valid DHCP lease before marking
`IPDiscoveryComplete=True`.
If the AAP `query_dhcp_lease` job returns no artifacts, or returns leases
that do not cover the selected attachment, the operator treats this as a
failure and backs off with exponential retry. A BareMetalInstance cannot
reach `Ready` phase (and therefore `RUNNING` state) without its tenant IP
discovered. This prevents the scenario where a DHCP lease is not yet
available (e.g., the fabric manager's DHCP server has not propagated the
lease to the new network segment) and the BMI appears as RUNNING with
no internal IP.

### CLI networking contract

BMaaS inherits the shared [Unified Networking CLI contract](../OSAC-1433-unified-networking/design.md#normative-cli-contract).
The BM-specific mapping is:

| API field | CLI form | Allowed values |
|---|---|---|
| `spec.network_attachments` | One optional `--network-attachment` | Zero or one attachment; repeating the option is rejected |
| `BareMetalNetworkAttachment.subnet` | `subnet=<name>` inside the attachment value | Optional; omission receives only the tenant default Subnet |
| `BareMetalNetworkAttachment.security_groups` | `security-groups=<name>[,...]` inside the attachment value | Optional; omission receives the tenant default SecurityGroup only when the resolved Subnet is in the tenant default VirtualNetwork; explicit list is typed, unique, same-tenant, same-VN, and Ready |
| `network-acls` attachment key | Not accepted in the attachment value | NetworkACLs are associated with Subnets; the effective ACL is inherited by the attachment |
| `BareMetalNetworkAttachment.interface` | Optional `interface=<port-name>` inside the attachment value | Must name a valid non-lifecycle port; omission selects the first valid `fabric` port |
| `BareMetalNetworkAttachment.primary` | Not emitted by the CLI | Omission is implicitly primary; `true` is accepted only through a structured client; `false` is rejected |
| `auto_external_ip_attachment` | `--external-ip-attachment` | Presence means `true`; omission means `false`; create-time only |

The canonical explicit command is:

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=my-subnet \
  --name my-server
```

The CLI must not expose `--network-attachments`, a second attachment, a
lifecycle interface, or a multi-NIC mode. The `interface` key is part of the
single compound `--network-attachment` value; a separate `--interface` flag
is not a second syntax. Omitting the option invokes the tenant default Subnet
and selects the default fabric interface. Omitting only one attachment key
invokes field-level defaulting for that key. The CLI constructs typed local
Subnet and SecurityGroup references and sends the resource-specific
`BareMetalNetworkAttachment` message. The effective NetworkACL is resolved
from that Subnet association.
Network fields and
`auto_external_ip_attachment` cannot be changed through update or patch
commands; delete and recreate is required.

### API Extensions

#### Proto (fulfillment-service)

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  string interface = 2;                            // omitted -> first fabric interface
  optional bool primary = 3;                       // the single attachment is implicitly primary
  repeated SecurityGroupLocalReference security_groups = 4; // omitted -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}

message BareMetalInstanceSpec {
  BareMetalInstanceCatalogItemReference catalog_item = 1; // immutable
  optional string ssh_public_key = 2;   // immutable
  optional string user_data = 3;        // immutable
  optional BareMetalInstanceRunStrategy run_strategy = 4;
  int64 restart_trigger = 5;
  map<string, google.protobuf.Any> template_parameters = 6;  // immutable
  optional BareMetalInstanceImage image = 7;                  // immutable
  repeated BareMetalNetworkAttachment network_attachments = 8; // NEW, optional; at most one entry; immutable after create
  BareMetalInstanceTemplateReference template = 10;            // immutable; materialized provisioning source
  BareMetalInstanceTypeReference instance_type = 20;           // immutable hardware profile reference
  optional bool auto_external_ip_attachment = 9;  // NEW, create-time only; omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachment_statuses = N; // NEW; at most one entry
}

message BareMetalNetworkAttachmentStatus {
  string interface = 1;
  SubnetLocalReference subnet = 2;      // Controller-owned resolved reference
  string ip_address = 3;  // Discovered after DHCP assignment, synced to fulfillment-service via feedback
  bool primary = 4;
}
```

The API intentionally retains the repeated `network_attachments` field rather
than introducing a singular or resource-name-prefixed replacement. Its values
are `BareMetalNetworkAttachment` messages and its maximum cardinality is one; an
omitted or empty list invokes default resolution, while a supplied list must
contain exactly one attachment after field-level defaulting.

#### Operator CRD (bare-metal-fulfillment-operator)

```go
type BareMetalInstanceSpec struct {
    // ... existing fields ...
    NetworkAttachments []BareMetalNetworkAttachment `json:"networkAttachments,omitempty"`
}

type BareMetalNetworkAttachment struct {
    Subnet         *SubnetLocalReference `json:"subnet,omitempty"` // resolved before provisioning
    Interface      string                `json:"interface,omitempty"`
    Primary        *bool                 `json:"primary,omitempty"` // omitted or true for the single attachment
    SecurityGroups []SecurityGroupLocalReference `json:"securityGroups,omitempty"` // omitted -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}

type BareMetalInstanceStatus struct {
    // ... existing fields ...
    NetworkAttachmentStatuses []BareMetalNetworkAttachmentStatus `json:"networkAttachmentStatuses,omitempty"`
}

type BareMetalNetworkAttachmentStatus struct {
    Interface  string `json:"interface,omitempty"`
    Subnet      *SubnetLocalReference `json:"subnet,omitempty"`
    IPAddress  string `json:"ipAddress,omitempty"` // Discovered after DHCP assignment
    Primary    bool   `json:"primary,omitempty"` // implicitly true for the single attachment
}
```

CEL immutability: `network_attachments` list and every network-owned field are
immutable after creation, including subnet, SecurityGroup list, NetworkACL
membership, interface, and primary designation. `auto_external_ip_attachment`
is also create-time only.
BMaaS accepts at most one network attachment, and that attachment is
implicitly primary.

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() <= 1"
  message: "BMaaS supports at most one network attachment"
```

#### fulfillment-service Controller (mutateBMI)

The `mutateBMI()` function in the fulfillment-service's BM reconciler currently sets TemplateID, TemplateParameters, RunStrategy on the K8s CR. It needs to also copy `network_attachments` from the proto spec to the K8s CR spec.

#### Server Validation Rules

BMaaS applies the shared [Unified Networking validation
pipeline](/enhancements/OSAC-1433-unified-networking/design.md#validation-and-enforcement-pipeline)
first and then applies the physical-interface rules below. These rules are required for standalone
BaremetalInstance creates, Catalog-based creates, and the private create path
used by CaaS worker provisioning.

**Request shape and cardinality:**

- `network_attachments` remains a repeated field for compatibility, but it
  accepts zero or one entry at API input. A second entry is rejected before
  reference lookup, interface discovery, or persistence with a single-NIC
  cardinality error.
- Missing or empty input means “use the default attachment”; it does not mean
  “provision a server with no tenant interface.” After default resolution the
  persisted BM resource contains exactly one attachment.
- A supplied attachment must contain no unknown fields. Its optional
  `primary` value may be omitted or `true`; explicit `false` is rejected.
  The sole attachment is always the tenant-facing primary/default-route
  attachment.
- The repeated status field is also limited to zero or one entry while the
  server is provisioning. A Ready BM must eventually report the single
  selected interface and its canonical IPv4 address.

**Deployment complete-manager validation:**

- Before accepting a standalone, Catalog-based, or private CaaS
  BaremetalInstance create, resolve the single deployment NetworkClass and
  verify that the selected complete manager profile includes the full BMaaS
  policy/resource lifecycle. The selected manager for physical BM handoff must provide both
  `move_network_attachment` for the provisioning-to-tenant port handoff and
  `query_dhcp_lease` for tenant IP discovery, in addition to the ordinary
  networking resource lifecycle.
- A missing BM operation or disabled required manager returns a provider
  configuration `FailedPrecondition` before the BaremetalInstance,
  auto-ExternalIP records, or operator CR are persisted. A backend operation
  still under development may use a successful no-op AAP role; BMaaS does not
  expose a partial manager path. The same complete-profile check is
  repeated before private CaaS worker dispatch.

**Attachment and dependency resolution:**

- A missing or empty list resolves the tenant default Subnet, default
  SecurityGroup, and the first eligible `fabric` interface from the effective
  BareMetalInstanceType. The effective NetworkACL is inherited from the
  selected Subnet.
- A supplied attachment defaults only missing Subnet, SecurityGroup, or
  interface fields. A NetworkACL supplied inside the attachment is rejected;
  ACL association is a Subnet property. Explicit/default SecurityGroups must
  be unique, Ready, same-tenant, and in the selected Subnet's
  VirtualNetwork.
- For standalone, Catalog-based, and tenant-facing creates, the resolved
  Subnet and its effective NetworkACL must exist and be Ready, be in the
  caller's effective tenant/project, and belong to the same
  VirtualNetwork.
- For the trusted private CaaS worker create path, the resolved Subnet and
  SecurityGroup references and effective NetworkACL are resolved in the source
  Cluster's effective tenant/project and must be Ready and
  belong to the same VirtualNetwork. The
  destination BMI's `system` tenant is not required to match that
  networking-resource scope; this exception does not apply to public or
  Catalog-based BMI creates.
- The effective BareMetalInstanceType must exist, be Ready/usable for
  allocation, and expose at least one valid network port with role `fabric`.
  A missing, Pending, or Failed instance type is a create precondition
  failure, not a reason to accept an unresolved interface.

**Physical-interface validation:**

- If `interface` is supplied, it must exactly identify one named port in the
  effective BareMetalInstanceType. Matching is by the canonical port name,
  not by list position, display label, MAC address supplied by the tenant, or
  an arbitrary interface string.
- The selected port must be tenant-attachable. Ports with role `lifecycle`
  are reserved for PXE, BMC, and provisioning operations and are rejected.
  The `role` field is a non-empty, extensible string rather than an enum. An
  unknown role is therefore not treated as `fabric`, is never selected by the
  implicit defaulting rule, and is rejected when explicitly selected for a
  tenant attachment because its port semantics cannot be validated. This is
  BMaaS attachment validation, not a claim that OSAC-1201 defines a closed
  role enum.
- If `interface` is omitted, select the first ordered port with role
  `fabric`. If no such port exists, reject the create; never select a
  management, storage, lifecycle, or arbitrary first port as a fallback.
- The selected port must be compatible with the inventory host that will be
  allocated. If inventory cannot provide the named port, the resource stays
  Pending/Failed according to the BM provisioning lifecycle and must not be
  marked Ready with a different port.
- The resolved interface is copied into the operator CR and is immutable. A
  later BareMetalInstanceType edit or port reordering cannot silently move an
  existing server to another interface.

**Provisioning and status validation:**

- Before dispatching `move_network_attachment`, validate that the selected
  port has a known fabric MAC and that the provisioning-network handoff is
  possible. The system must not move a lifecycle or unknown port.
- The operator may move only the selected fabric port from the provisioning
  network to the resolved tenant Subnet. It must not move every port on the
  host and must not infer a second tenant attachment from inventory.
- After DHCP, the discovered address must be canonical IPv4, belong to the
  resolved Subnet, and match the selected port MAC or the documented named
  fabric-server fallback. A lease for another port is rejected and retried.
- The operator writes at most one `BareMetalNetworkAttachmentStatus` entry,
  with the resolved interface, Subnet reference, IPv4 address, and implicit
  primary value. Status cannot change the spec attachment.
- ExternalIPAttachment dispatch waits for both the BM resource's discovered
  IP and the ExternalIP's `Allocated` state. Until both are true, the
  attachment remains Pending and the controller requeues.

**Automatic ExternalIP validation:**

- Auto ExternalIP allocation is available only after the normal one-entry,
  interface, Subnet, effective NetworkACL, and instance-type validations pass.
- The selected pool must be Ready, IPv4, and have capacity. Parent BM,
  ExternalIP, and Pending ExternalIPAttachment records are created in one
  transaction; capacity or validation failure leaves no parent or child
  records.
- The auto-created attachment targets the BaremetalInstance and uses
  `target_endpoint == UNSPECIFIED`. Its DNAT target is the discovered IP of
  the selected physical interface, never an IP supplied by the tenant.

**Update, delete, and private CaaS handoff:**

- Update, patch, replace, or field-mask changes to the attachment list,
  Subnet, SecurityGroup list, interface, primary value, or
  `auto_external_ip_attachment` are rejected after create. Changing the
  network requires delete and recreate.
- The CaaS private create path must send exactly one enriched attachment:
  the Subnet and SecurityGroup list from the Cluster attachment plus the
  immutable node-set `fabric_interface`. The effective NetworkACL is inherited
  from the Subnet.
  BMaaS re-validates that attachment against the selected
  BareMetalInstanceType; private callers do not bypass the physical-port and
  lifecycle-port checks.
- The BM delete path returns the selected port to the provisioning network
  only after its OSAC-owned auto ExternalIPAttachment cleanup is handled.
  Tenant-created ExternalIPAttachments targeting the BMI block BMI deletion;
  they are never detached implicitly. Subnet, ExternalIP, and VirtualNetwork
  deletion is separately blocked by the direct reverse references defined by
  Unified Networking; an ExternalIPPool is not a direct BMI dependency.

Every rejected request identifies the most specific field path available, for
example `spec.network_attachments[1]`,
`spec.network_attachments[0].interface`, or
`spec.network_attachments[0].primary`. No invalid input is persisted.

#### Catalog Item interaction

Catalog Item v2 may govern the complete `network_attachments` list. It may
  lock the single attachment or make it editable with an optional default. The
  same Bare Metal rules apply after Catalog resolution: at most one attachment,
  one implicit primary, a valid interface from the effective
  BareMetalInstanceType, no lifecycle interface, and a Subnet with its
  effective NetworkACL in the same VirtualNetwork. Its SecurityGroup list is
  validated with the shared typed-reference and readiness rules.

Resolution occurs before the tenant default network is applied. A locked list
rejects conflicting tenant input; an editable list accepts tenant input,
otherwise uses its Catalog default and Template defaults, then defaults only
missing fields from the tenant's default Subnet, SecurityGroup, and fabric
interface. The tenant default SecurityGroup is used only when the resolved
Subnet belongs to the tenant default VirtualNetwork; a non-default-
VirtualNetwork Subnet without a compatible explicit group is rejected. The
effective NetworkACL is inherited from the selected Subnet.
Supplied fields are preserved. A shared Catalog Item cannot lock or
default tenant-local network references.

The editable policy applies only during BaremetalInstance creation. After
creation, the resolved attachment list, every network field, and
`auto_external_ip_attachment` are read-only. Catalog Item definitions and
metadata remain governed by Catalog Items v2 and are not changed here.

The provisioning network, lifecycle interfaces, port moves, and DHCP lease
discovery are infrastructure behavior and are never Catalog-governed fields.

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
its name is a fabric-manager configuration value sourced from deployment
configuration, not operator state. Any compatibility fallback for that
configuration is deployment-owned.

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
  the role**. Callers resolve the typed `subnet` reference → tenant network segment name and
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
segment is resolved from the single attachment's typed `subnet` reference (Subnet CR
`metadata.name` == fabric network segment name); the provisioning network name comes from
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

IP discovery is decoupled from switch port configuration. The
`move_network_attachment` role is switch-side only — it moves the server's
fabric port onto the tenant subnet's network segment during
`reconcileNetworking`, after OS provisioning and before the handoff reboot. It
does not query DHCP leases or return an IP address.

After `reconcileProvisioning` completes and the host has received a DHCP lease from the fabric's DHCP server, the operator runs `reconcileIPDiscovery`. This phase dispatches `osac.templates.{{ fabric_manager }}.query_dhcp_lease`, passing the single subnet reference and the server's selected port MAC address. The role queries the fabric manager's DHCP lease API for the subnet, matches the port MAC to find the corresponding DHCP-assigned IP, and returns it. The operator writes the discovered IP to the single `status.networkAttachmentStatuses[].ipAddress` entry on the BaremetalInstance CR.

**MAC resolution — the `osac.openshift.io/interface-macs` contract.** Bare-metal servers are not registered as named fabric servers, so their DHCP leases appear in the fabric manager's IPAM as MAC-only host entries (no server name). To match a lease, the operator must know the selected attachment's NIC MAC. Inventory tooling annotates each `BareMetalHost` with a JSON map of OSAC interface name → NIC MAC, e.g. `{"eth9":"52:54:00:16:04:83"}`, under the `osac.openshift.io/interface-macs` annotation. During `reconcileIPDiscovery` the operator reads this annotation and passes the selected interface MAC to the job as an extra var (`network_attachment_macs`). The `query_dhcp_lease` role matches the IPAM host by MAC (the fabric manager stores lease MACs lowercase; the role compares against the lowercased `mac[].address` values). When no MAC is supplied, the role falls back to matching by server name — the path named CaaS fabric servers use.

The feedback controller syncs this to the fulfillment-service DB via the existing Signal / `syncStatus()` pattern. The ExternalIPAttachment controller reads the single tenant IP from CR status for DNAT creation.

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, copy to K8s CR via mutateBMI, auto-provision ExternalIP |
| bare-metal-fulfillment-operator | Inventory assignment, switch-side networking (dispatcher), OS provisioning (AAP), **IP discovery** via `query_dhcp_lease` dispatcher call after provisioning, power management |
| AAP BM provisioning template | OS provisioning only (host-side networking handled by DHCP) |
| osac-operator feedback controller | Signal fulfillment-service on status changes (unchanged), sync IP addresses from CR status to DB |
| osac-operator BMI cleanup controller | Clean up auto-provisioned ExternalIPAttachment → ExternalIP on BaremetalInstance deletion (phased requeue, `baremetalinstance-cleanup` finalizer) |
| osac-operator ExternalIPAttachment controller | Read BM's single tenant IP from CR status, dispatch DNAT to every selected manager |
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

The server sits on the **provisioning network** (with DHCP, gateway, and
egress) from bootstrap through the entire metal3 deploy and first boot.
First-boot cloud-init runs there **with egress**, so first-boot pulls succeed.
Only after `ProvisionTemplateComplete` does the operator move the fabric port
to the tenant network (waiting for the network segment to reach active state)
and perform the handoff reboots so the OS re-DHCPs on the tenant network (see
DHCP lease handoff below).

**DHCP lease handoff — deterministic second reboot.** Moving the fabric port from the provisioning network to the tenant network moves the host's NIC to the tenant V-Net, so the host must obtain a fresh DHCP lease there. This does not complete on the first post-switch reboot; a second reboot is deterministically required before the host holds a tenant-V-Net lease. This is expected, deterministic behavior — not a timing or race condition. The operator performs the second reboot as a standard step of the handoff, after which `reconcileIPDiscovery` reads the tenant-V-Net lease. (Fabric managers that scope DHCP strictly per segment may not require the second reboot.)

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent BaremetalInstance
- No new authentication or authorization changes
- SecurityGroup enforcement follows the [Unified Networking SecurityGroup rule
  semantics](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup-rule-semantics),
  and the single BMaaS tenant attachment uses the effective NetworkACL rules
  for its Subnet. The hard-coded deployment `permit` baseline is separate from
  the tenant default ACL; native Kubernetes NetworkPolicy alone is not a
  substitute for either OSAC policy contract.

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

- Auto-provisioned resource cleanup transient failure: the parent remains
  `Deleting`, its finalizer is retained, and reconciliation retries
  `ExternalIPAttachment -> ExternalIP` in that order.
- A permanent or unknown cleanup failure has the same safe outcome: the parent
  remains `Deleting` and the finalizer is retained. The controller must not
  remove the finalizer to leave an orphan, and it must not touch a resource
  unless the canonical marker and exact immutable BaremetalInstance owner
  relationship match.

### RBAC / Tenancy

The bare-metal-fulfillment-operator needs additional RBAC permissions: get/list/watch on Subnet and NetworkClass CRs, required for the dispatcher to resolve networking configuration during `reconcileNetworking`.

All new resources (BaremetalInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from BaremetalInstance to auto-created resources
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected
- Tenant User can view auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via the standard API; their network-owned fields are not editable

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

**Mitigation:** Prioritize the BM networking roles (OSAC-2081). Accept that
BMaaS remains unavailable until a fabric_manager exists. Document as a hard
dependency.

**Reviewed by:** Engineering / Product

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create BM with `auto_external_ip_attachment=true`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Two-operator architecture synchronization

**Impact:** bare-metal-fulfillment-operator and osac-operator feedback controller both watch BaremetalInstance CR. Reconciliation phases must be carefully ordered to avoid race conditions.

**Mitigation:** Reconciliation phase ordering enforced via status conditions: inventory → provisioning → networking → reboot → IP discovery. Integration tests covering full lifecycle. Document finalizer dependencies.

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

Resolved: After `reconcileProvisioning` completes and the host has received a DHCP lease, the operator queries the fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role). The role matches the server's selected port MAC address — resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation — to find the assigned IP (falling back to server-name matching for named fabric servers). The operator writes the discovered IP to the single `status.networkAttachmentStatuses` entry on the BaremetalInstance CR. The feedback controller then syncs to fulfillment-service via Signal RPC. `move_network_attachment` remains switch-side only (moves the fabric port between network segments).

## Test Plan

The executable, reviewable plan for BMaaS Networking is maintained in
[testplan.md](testplan.md). It covers one-attachment and field-level
defaulting, physical-interface resolution, provisioning and handoff, DHCP
status, automatic ExternalIP behavior, CaaS private handoff, Catalog parity,
immutability, cleanup, and unsupported behavior. Shared networking contracts
are covered by the [Unified Networking test
plan](../OSAC-1433-unified-networking/testplan.md).
## Long-Term Evolution (The Reboot is the Seam)

The structure `inventory → provision → establish-tenant-networking → discovery`
stays; only "establish-tenant-networking" changes:

**Ironic Standalone Networking** (metal3-docs PR #586; BMO PR #3469, ToR
networking part 1): Ironic switches the port VLAN per lifecycle phase
(provisioning→tenant) on one NIC — drop the reboot. Upstream assumes
`networking-generic-switch` (direct ToR control), which does not fit
The fabric manager owns the switch; adopting a new backend means implementing the fabric manager interface or aligning the model.

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
- [ ] Integration tests pass (E2E coverage for single-NIC, auto ExternalIP, IP feedback, isolation-until-ready)
- [ ] Documentation: API reference, user guide for simplified BM creation

GA criteria:
- [ ] fabric_manager implementation (BM networking roles, OSAC-2081) delivered and production-tested
- [ ] Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460) implemented and stable
- [ ] NATGateway full stack (OSAC-1443) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)
- [ ] Reboot-based short-term validated; evolution path to Ironic Standalone Networking confirmed

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`network_attachments`, `auto_external_ip_attachment`) are additive — existing BaremetalInstance resources continue to work without networking fields
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Tenant User is encouraged to migrate by creating a replacement BaremetalInstance with the new networking fields. `osac-cli` supports the single compound `--network-attachment` value with an optional `interface=<port-name>` key; an existing instance's network fields are not updated.
- No breaking changes — networking fields remain optional

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and bare-metal-fulfillment-operator images to `N`
- Existing BaremetalInstance resources with new `network_attachments` field will be unrecognized by `N` operator
- Manual cleanup required: delete BaremetalInstance resources created with new field, re-create without networking fields
- Auto-provisioned ExternalIP resources remain protected by their owner
  relationship and parent finalizer until a compatible controller resumes the
  ordered cleanup.

Acceptable downgrade steps:
- Delete CRs using new field (`network_attachments`)
- Re-create without networking fields
- Restore a compatible control plane and let the retained finalizer retry the
  owned `ExternalIPAttachment -> ExternalIP` cleanup. Do not delete resources
  based on the auto-created label alone; verify the immutable owner
  relationship and use the shared dependency guards for any manual cleanup.

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

### Symptom: BM has no default gateway

**Detection:** BM cannot reach external networks, `ip route` shows no default route

**Cause:** The single tenant attachment was not resolved or its network segment is not ready

**Resolution:**
1. Check BaremetalInstance spec: `kubectl get baremetalinstance <name> -n <namespace> -o yaml`
2. Verify exactly one `networkAttachments` entry and that its Subnet is Ready
3. If the attachment or Subnet is incorrect, delete and re-create the BaremetalInstance with the intended single attachment

### Symptom: BaremetalInstance remains Deleting during auto-provisioned ExternalIP cleanup

**Detection:** `kubectl get baremetalinstance` shows the parent in `Deleting`,
and controller logs show a cleanup retry for its owned
`ExternalIPAttachment` or `ExternalIP`.

**Cause:** Cleanup is waiting for a transient backend/API dependency or failed
after the parent deletion was admitted.

**Resolution:**
1. Check BaremetalInstance deletion logs (bare-metal-fulfillment-operator logs) for cleanup errors
2. Verify the child resources carry the canonical auto-created marker and the
   exact immutable BaremetalInstance owner relationship
3. Resolve the backend/API failure and allow reconciliation to delete the
   attachment first and the ExternalIP second; do not remove the finalizer

### Symptom: ExternalIPAttachment stuck in Pending, waiting for BM IP address

**Detection:** `kubectl describe externalipattachment <name> -n <namespace>` shows condition "WaitingForIPAddress"

**Cause:** Host has not yet received DHCP-assigned IP (provisioning still in progress or failed)

**Resolution:**
1. Check BaremetalInstance status: `kubectl get baremetalinstance <name> -n <namespace> -o jsonpath='{.status.networkAttachmentStatuses[0].ipAddress}'`
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
- A provisioned provisioning network segment (DHCP + gateway + SNAT) and the
  initial per-server attach, plus the BareMetalHost
  `osac.openshift.io/interface-macs` annotation — deployment prerequisites
  (deployment infrastructure)
- Dispatcher core (OSAC-1457, OSAC-1458, OSAC-1460)
- Integration test environment with fabric manager and Ironic/Metal3 backend

## Dependencies

| Dependency | Jira | Status |
|-----------|------|--------|
| Dispatcher core | OSAC-1457, OSAC-1458, OSAC-1460 | Closed |
| NATGateway full stack | OSAC-1443 (10 tasks) | 1/10 In Progress |
| ExternalIPAttachment BM target in CRD | OSAC-2041 | New |
| BM DNAT flow in controller | OSAC-1496 | New |
| BareMetalNetworkAttachment proto | OSAC-1508 | New |
| Single-attachment and interface validation | OSAC-1509 | New |
| CLI --network-attachment for BareMetalInstance | OSAC-2075 | New |
| BM provisioning flow — reconcileNetworking dispatcher logic (dispatches move_network_attachment after provisioning, provisioning network → tenant). Note: the upstream producers that populate `network_attachments` on the K8s CR — BareMetalInstance CRD field and mutateBMI copy — are tracked separately below as open GAPs | OSAC-2047 | Closed |
| BM reboot flow (reconcileReboot issues BMH annotation-based reboot after port move) | Not tracked | **GAP** |
| Integration test | OSAC-1510 | New |
| Fabric manager `move_network_attachment` role (generic port move) | OSAC-2081 (BM networking role) | Closed |
| Provisioning network segment (DHCP + gateway + SNAT) + initial per-server attach in setup-bmaas | osac-deployment infrastructure | New |
| BareMetalHost `osac.openshift.io/interface-macs` annotation (inventory tooling) | osac-deployment infrastructure | New |
| BareMetalInstance CRD: add NetworkAttachments | Not tracked | **GAP** |
| mutateBMI: copy network_attachments to K8s CR | Not tracked | **GAP** |
| IP discovery: `query_dhcp_lease` role matches port MAC (from interface-macs annotation) to lease, operator writes to CR status | Not tracked | **GAP** |
| bare-metal-fulfillment-operator dispatcher capability + RBAC for Subnet/NetworkClass CRs | Not tracked | **GAP** |
| Remove unused BareMetalInstance spec.networkClass field | Not tracked | **GAP** |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed | Not tracked | **GAP** |
