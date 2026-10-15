---
title: bmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-12
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md"
  - "baremetal-instance-api: https://github.com/osac-project/baremetal-instance-api"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking — Switch Port Configuration and Tenant-Defined Interface Mapping

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
  - [Architecture: Two Operators on One CR](#architecture-two-operators-on-one-cr)
  - [The Three Network Planes](#the-three-network-planes)
- [Proposal](#proposal)
  - [Working with provider-supplied managers](#working-with-provider-supplied-managers)
  - [CaaS worker ownership](#caas-worker-ownership)
  - [BareMetalInstanceType and Interface Validation](#baremetalinstancetype-and-interface-validation)
  - [Workflow Description](#workflow-description)
  - [API contract](#api-contract)
  - [Component behavior and constraints](#component-behavior-and-constraints)
- [Security Considerations](#security-considerations)
- [Failure Handling and Recovery](#failure-handling-and-recovery)
- [RBAC and Tenancy](#rbac-and-tenancy)
- [Observability and Monitoring](#observability-and-monitoring)
- [Risks and Mitigations](#risks-and-mitigations)
- [Drawbacks](#drawbacks)
- [Provider Networking Disabled](#provider-networking-disabled)
- [Alternatives Considered](#alternatives-considered)
- [Open Questions](#open-questions)
- [Test Plan](#test-plan)
- [Long-Term Evolution](#long-term-evolution-the-reboot-is-the-seam)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)
- [Dependencies](#dependencies)

BMaaS networking provides single-NIC BaremetalInstance provisioning with optional tenant-specified physical interface mapping, switch port configuration via dispatcher, IP address feedback through CR status, and auto-provisioned external access (ExternalIP).

## Summary

This document is a service-specific extension of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture and [deployment support boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary); BMaaS networking supports connected deployments only and does not add air-gapped or disconnected networking support. This document defines how BMaaS consumes that architecture.
Networking resources support only Create, List/Get, and Delete, and
`BaremetalInstance` network attachment fields are immutable after creation;
changes require delete and recreate.

BMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

BaremetalInstance supports a repeated `BareMetalNetworkAttachment` field for API compatibility, but accepts at most one entry. The optional `interface` and `primary` fields retain their existing semantics; with one entry, `primary` is implicit, omission and `true` are accepted, and `false` is rejected. The bare-metal-fulfillment-operator's `reconcileNetworking` phase creates and waits for its SubnetAttachment; networking reconciliation dispatches Fabric policy/attachment and lease jobs. The workload mirrors discovered address status for DNAT target resolution. See [PRD](prd.md) for detailed requirements.

The manager-backed resource flows and provider IP-discovery/readiness behavior
in this document describe the enabled mode. The feature-gated disabled behavior
is specified at the end of the Proposal section. API-level SecurityGroup rule
validation and reference checks remain active in disabled mode. OSAC submits no
provider operation to apply or remove SecurityGroup rules; rules already
programmed in the backend may continue to affect traffic until provider-side
cleanup. [User]

The [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)
owns registration, task/input/result schemas, no-op requirements, overlapping
address spaces, stable API ownership, NetworkData, retries and shared cleanup.
The [internal request protocol](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#workload-attachment-policy-lifecycle)
defines attachment status and projection recovery. This design specifies the
service's handoffs and readiness gates, not another copy of those rules.

## Motivation

Bare-metal servers require explicit switch-port configuration to participate in the OSAC Networking API. VM interfaces are provided through Kubernetes networking; bare-metal NICs connect directly to the physical fabric, so the selected NIC's switch port must be assigned to the network segment backing its requested Subnet during provisioning.

### Architecture: Two Operators on One CR

The fulfillment-service creates the BMI in the hub. BMF owns inventory,
provisioning, power, one handoff reboot and the gates around its target-only
SubnetAttachment. The osac-operator networking controller owns that request's
provider jobs, stateful policy, attachment/discovery status and cleanup. BMF
mirrors request readiness/IP into BMI status; the feedback reconciler signals
fulfillment and removes its feedback finalizer last.

On deletion, the automatic external cleanup controller completes child cleanup,
BMF confirms the host is powered off, then requests attachment deletion. The
networking controller restores provisioning connectivity and confirms cleanup
before BMF releases inventory/host ownership. [User]

### Goals

**Core Design Goals (G1–G5):**

- **G1 — OS-agnostic host networking.** All host addressing via DHCP; no per-OS host-side config. Corollary: exactly one default route at any moment.
- **G2 — Provisioning connectivity.** During inspect + deploy the server can reach its image source and the Ironic conductor.
- **G3 — Correct, minimal final state.** After provisioning: attached to exactly one tenant network segment, single default route, no residual provisioning network.
- **G4 — Isolated until ready.** The tenant reaches the server only after it is fully provisioned and in its final network state; provisioning traffic is never exposed to the tenant.
- **G5 — Achievable on stock metal3 + fabric manager today.**

**Implementation Goals:**

- Single-NIC support with optional physical interface mapping (tenant specifies one interface name from BareMetalInstanceType)
- Resource-specific attachment message (`BareMetalNetworkAttachment`) with `interface` and `primary` fields
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- bare-metal-fulfillment-operator creates and waits for a target-only SubnetAttachment after provisioning; the networking controller dispatches attachment policy work. [User]
- Provisioning network: an idle (unassigned) server keeps its fabric NIC on an OSAC-owned provisioning network (DHCP + gateway + SNAT) so it has internet during metal3 inspection; provisioning moves the port provisioning network → tenant, deletion moves it tenant → provisioning network (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- IP discovery after provisioning: the SubnetAttachment controller queries the Fabric lease API via its separate `query_dhcp_lease` job, matches the required selected-port MAC (resolved from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to the DHCP-assigned IP, writes to CR status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP for DNAT
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
- Implementation of the shared manager dispatch contract, which is defined by the Network Manager Integration Contract.
- Creating the provisioning network (network segment + DHCP + gateway + SNAT) and the initial per-server attach — a deployment prerequisite handled by the fabric infrastructure / deployment infrastructure, not the operator (see [Provisioning Network and Port Moves](#provisioning-network-and-port-moves))
- Re-provision handoff reset: NetworkHandoffComplete is never reset after initial provisioning, so an in-place re-provision (config-version change after Ready) would run over the tenant network (deferred to long-term design)

## Proposal

### Working with provider-supplied managers

BMaaS uses the NetworkClass-selected Fabric Manager for physical attachment,
policy and lease lookup. A Kubernetes Manager is unnecessary for a physical
workload; if the Subnet also hosts VMs, its Kubernetes realization follows the
shared lifecycle independently. The bare-metal provisioning backend remains
responsible for image installation and power control.

| Phase | BMaaS/BMF responsibility | Fabric Manager responsibility |
|---|---|---|
| Prepare | Select host/port, record real MAC, provision on the provisioning network. | No tenant port handoff before the provisioning gate. |
| Attach | Create a BMI-target request with complete resolved physical identity. | Apply policy and move the selected interface to the tenant Subnet. |
| Handoff | After accepted apply, perform the single tracked reboot and report completion. | No duplicate reboot; provider role only owns its assigned network changes. |
| Discover | After handoff, dispatch lookup with selected MAC/Subnet; mirror the validated address. | Return the unambiguous real DHCP lease in the shared envelope. |
| Delete | Finish external cleanup, confirm host powered off, await network cleanup, then deprovision/release host. | Remove tenant policy and restore captured provisioning connectivity before success. |

A provider may implement these tasks through its own switch/router/DHCP APIs.
BMF uses the same gates regardless of those internals; providers receive stable
BMI/Subnet API IDs and concrete host/port/MAC identity. Detailed physical
handoff and offboarding rules below apply equally to CaaS worker BMIs. [User]

### CaaS worker ownership

Standalone BMIs use their own tenant for network validation. Hidden CaaS worker
BMIs remain in the `system` tenant but use their owning Cluster's network
tenant only through the authenticated, immutable parent binding defined in
[CaaS worker network authorization](/enhancements/OSAC-1436-caas-networking/design.md#caas-worker-network-authorization).
BMF keeps infrastructure tenant/owner metadata on the BMI and request; the
networking controller verifies that binding and passes the effective tenant
to Fabric. No blanket cross-tenant exemption is permitted. Creation,
observation, adoption and deletion must all use the same verified binding.

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

`BareMetalInstanceType` is a bare-metal-only resource (OSAC-1201) — BM vs VM is classified by resource type (`BareMetalInstance` vs `ComputeInstance`), not by the contents of `network_ports`. Every `BareMetalInstanceType` must declare at least one `network_ports` entry with `role=fabric`; a bare-metal profile with no fabric port is rejected at creation time because both the operator (provisioning-network port move) and the default-interface resolution (first `role=fabric` port) depend on it. Canonical port-role validation (rejecting unknown or misspelled role values) is owned by OSAC-1201's BareMetalInstanceType schema.

Interfaces are ordered. When multiple interfaces share the same role, the first one in the list is the default for that role (used by CaaS for automatic resolution — see CaaS design).

**Interface-name identity contract.** `BareMetalNetworkAttachment.interface` selects a port by `BareMetalNetworkPortSpec.name`. Networking reconciliation passes this name as `network_attachment.interface.name` to `apply_subnet_attachment`, and the `osac.openshift.io/interface-macs` annotation keys use the same name. These three identifiers — catalog port name, fabric-manager logical interface, and interface-macs annotation key — must be consistent; a mismatch causes the port move or DHCP lease query to target the wrong NIC. Inventory tooling and BareMetalInstanceType registration must align on the same naming convention.

#### How BMaaS Uses BareMetalInstanceType

The tenant provides `BareMetalNetworkAttachment` with an explicit `interface` field referencing a port `name` from the BareMetalInstanceType's `network_ports` list. The fulfillment-service validates:
- The `interface` name exists in the BareMetalInstanceType's `network_ports` list
- The BareMetalInstanceType is resolved from the instance's `instance_type` field

Unlike CaaS (which picks the interface automatically by role), BMaaS gives the tenant direct control over which physical interface maps to which subnet.

#### BareMetalInstanceType as the Authoritative Model

The [BareMetalInstanceType EP](/enhancements/OSAC-1201-baremetal-instance-types) provides the tenant-facing hardware catalog for BMaaS, with full hardware specs and network port definitions (name, role, type, speed). Per [OSAC-2135 (CaaS Bare-Metal Worker Node Provisioning)](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), `HostType` is deprecated and decommissioned — `BareMetalInstanceType` is now the sole source of truth for hardware profiles and interface resolution:

- BMaaS tenants discover available interfaces via the BareMetalInstanceType API (with type + speed info)
- Interface validation uses BareMetalInstanceType's `network_ports` list
- CaaS fulfillment resolves the fabric interface from `BareMetalInstanceType.network_ports[].role=fabric` at cluster creation and stores it on the node set
- `BareMetalInstanceType.host_label_selector` provides direct inventory matching (OSAC-1201), replacing the former HostType reverse lookup

> **CaaS network attachment source:** For CaaS bare-metal workers, the network attachment originates from the private `ClusterOrder.spec.networkAttachment` (`ClusterNetworkAttachment`) and is enriched per-BMI by the `BareMetalWorkerReconciler` with the immutable `fabric_interface` already resolved and stored on the node set during cluster creation. See [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md) for the full enrichment flow.

#### Interface Role Convention

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) |

Roles are conventions, not enforced enums. BMaaS uses them for display/documentation; the tenant selects by port name, not role. Ports with role `lifecycle` are used by the provisioning system (Ironic, Metal3) for PXE boot and BMC operations — they are NOT tenant-attachable and should not appear in `network_attachments`.

### Workflow Description

#### Phase 1: Networking prerequisites

Use the shared [creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates) and [deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards), together with [tenant defaults](/enhancements/OSAC-1433-default-networking/design.md).
Require the resolved tenant Subnet and SecurityGroups ready before creating
the workload. Shared network creation, data persistence and optional external
address resources follow unified rules; this service adds no backend-specific
selection or allocation path.

#### Phase 2: Tenant Creates BM Server

1. **Create BaremetalInstance with network_attachments:**

   Single interface (simple case):
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
     --name my-server
   ```

   A second `--network-attachment` flag is rejected; multi-NIC BMaaS is not
   supported.

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

2. **fulfillment-service:**
   - If `network_attachments` is omitted or empty: populates the sole attachment with the tenant's default Subnet, default SecurityGroup, and the first port with role `fabric` from `BareMetalInstanceType.network_ports` (see [Default Networking PRD](/enhancements/OSAC-1433-default-networking)).
   - If one attachment is supplied, defaults only missing fields: a missing Subnet receives the tenant default Subnet, a missing or empty SecurityGroup list receives the tenant default SecurityGroup only when the resolved Subnet belongs to the tenant's default VirtualNetwork, and a missing interface receives the first `fabric` port from `BareMetalInstanceType.network_ports`; supplied values are preserved.
   - Validates:
     - At most one network attachment is specified
     - Each subnet exists, is Ready
     - The subnet and each SecurityGroup belong to the same VirtualNetwork
     - The optional `interface` references a valid interface name from the BareMetalInstanceType's network ports list
     - If `interface` is omitted, defaults to the first port with `role=fabric` from the BareMetalInstanceType
     - If one attachment is present, it is the implicit primary; omitted or `primary: true` is accepted but redundant, while `primary: false` is rejected
   - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity, matching IP family), creates ExternalIP (labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <baremetal-instance-id>`) in the same DB transaction as the BaremetalInstance. The ExternalIP starts in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted (including the BaremetalInstance). The ExternalIPAttachment is **not** created at this point — it is deferred to the fulfillment-service internal reconciler, which creates it only after the ExternalIP is Allocated and the BaremetalInstance is Ready (has a known IP from `reconcileIPDiscovery`). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access) for the full stepped flow.
   - Creates BaremetalInstance CR with `network_attachments` in spec

3. **bare-metal-fulfillment-operator BareMetalInstance controller:**

   a. `reconcileInventory` (unchanged):
      - FindFreeHost → AssignHost (Ironic/Metal3)
      - Populates HostClass from inventory

   b. `reconcileProvisioning` (runs after inventory):
      - Triggers AAP job via `RunProvisioningLifecycle`
      - Template does OS provisioning (PXE boot, user-data, etc.)
      - Server stays on the provisioning network during this phase
      - Host-side networking is handled by DHCP — the template does NOT configure static IPs, gateway, or DNS. The host receives its IP automatically from the provisioning network DHCP server.

   c. **`reconcileNetworking` (after provisioning completes):**
      - Creates one internal target-only `SubnetAttachment` referencing the BMI. The request does not copy Subnet, interface, policy, or IP values; it tracks the apply job, readiness, lease-discovery status and cleanup finalizer. It is not the switch-port binding itself.
      - The networking controller reads the BMI, resolves its immutable Subnet/selected interface/SecurityGroup rules and NetworkData, and requires the exact selected-port MAC from the BareMetalHost interface-macs annotation before physical dispatch. It then dispatches Fabric `apply_subnet_attachment` with request `resource`, workload `target`, and normalized `network_attachment`.
      - The Fabric Manager installs effective stateful policy and synchronizes the selected physical port's membership with the fabric segment backing the requested Subnet. Tenant traffic remains unavailable until both segment membership and policy are confirmed.
      - The request controller owns the AAP job and readiness; BMF mirrors `NetworkAttachmentsReady=True` only after the exact Fabric job result is accepted and the port membership and policy are confirmed. Apply failure leaves the interface unavailable and BMI non-ready.

   d. **`reconcileReboot` (after attachment readiness):**
      - Performs one handoff reboot via the BareMetalHost annotation and waits for completion so the OS requests tenant DHCP configuration.
      - Sets `NetworkHandoffComplete=True`. The shared lifecycle specifies one reboot; provider-specific lease behavior is resolved by its DHCP integration, not by an unconditional second reboot. [User]

   e. `reconcilePower` remains the ordinary workload power lifecycle.

4. **IP discovery and feedback:**
   - The SubnetAttachment controller waits for BMI `NetworkHandoffComplete=True` and resolves the selected physical-port MAC from BareMetalHost `osac.openshift.io/interface-macs`.
   - No DHCP query is dispatched until that MAC is available. `query_dhcp_lease` is a separate Fabric job on the same request and normalized attachment; no hostname fallback is defined for BMI targets, including CaaS worker BMIs.
   - The networking controller validates one unambiguous tenant-Subnet IPv4 lease for the selected MAC, writes IP/`IPDiscoveryComplete` to request status, and retains the request's job history.
   - BMF `reconcileIPDiscovery` mirrors request status into `networkAttachmentStatuses`; the feedback controller signals fulfillment-service to persist tenant-visible status. BMI Ready requires successful apply, handoff, and valid discovery. [User]

#### Phase 3: External Access (optional)

5. **Create ExternalIP:**
   ```bash
   osac create externalip --pool external-pool-1 --name my-ip
   ```
   Dispatcher → Fabric `create_external_ip` through `osac.networking.<selected managerName>`

6. **Create ExternalIPAttachment:**
    ```bash
    osac create externalipattachment --externalip my-ip \
      --baremetal-instance my-server --name bm-att
    ```
    - ExternalIPAttachment controller resolves the BaremetalInstance target by UUID label
    - Checks two preconditions before dispatching (requeues if either is not met):
      1. **ExternalIP must be Allocated** (have an allocated address from the fabric manager)
      2. **BaremetalInstance must have a primary IP** — reads `status.networkAttachmentStatuses[].ipAddress` for the attachment where `primary: true`. This IP is written by the operator during `reconcileIPDiscovery` (step 4) and synced to the fulfillment-service via the feedback controller.
    - Once both preconditions are met: writes `osac.openshift.io/target-ip` annotation on the ExternalIPAttachment CR
    - Calls Fabric `attach_external_ip` through `osac.networking.<selected managerName>`
    - Fabric manager creates DNAT rule: external IP → BM's primary subnet IP
    - ExternalIPAttachment transitions from Pending to Ready

    For auto-provisioned ExternalIPAttachments (`auto_external_ip_attachment=true`), the same operator-side flow applies once the ExternalIPAttachment exists. The fulfillment-service internal reconciler creates the ExternalIPAttachment only after the ExternalIP is Allocated and the BaremetalInstance is Ready (has a known IP from `reconcileIPDiscovery`). At that point the operator-side precondition checks are already satisfied, so the DNAT rule is created promptly. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access).

#### Deletion (reverse order)

7. **Delete BaremetalInstance:**
    - **Auto-provisioned cleanup (osac-operator):** The osac-operator adds a cleanup finalizer (`osac.openshift.io/baremetalinstance-cleanup`) on BaremetalInstance CRs that have `auto_external_ip_attachment=true`. On deletion, it performs the phased requeue cleanup: deletes ExternalIPAttachment first (by target reference), waits, then deletes ExternalIP (by `auto-created-for` label), waits, then removes its finalizer. See [Unified Networking — Auto-provisioned resource cleanup](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access) for the pattern. BMF waits for this external child cleanup to complete before attachment cleanup, OS teardown, or inventory release; independent finalizers do not imply a safe execution order. [User]
    - **Manually created ExternalIPAttachments block deletion** — if the tenant created ExternalIPAttachments explicitly (not labeled `osac.openshift.io/auto-created`), they block the BaremetalInstance's deletion. The tenant must remove them first. See [Unified Networking — Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards).
    - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — tenant-scoped and shared.
    - bare-metal-fulfillment-operator (stops the tenant OS before returning the port to provisioning connectivity):
      - `reconcileNetworkOffboardShutdown`: powers off the host **while the port is still on the tenant network** and reports `NetworkOffboardShutdownComplete=True` only after power-off is confirmed. If the host is already powered off, the step is an idempotent no-op that still confirms the condition. This guarantees the tenant workload stops before the port moves to the provisioning network.
      - Only after `NetworkOffboardShutdownComplete=True`, BMF deletes the SubnetAttachment. The networking controller dispatches Fabric `delete_subnet_attachment`, removes workload policy, and restores the selected port to provisioning connectivity. It reports `NetworkOffboardComplete=True` on the request only after the exact cleanup job succeeds. BMF waits for that condition and request finalization before deprovisioning or releasing the host. The request retains the same resolved target/attachment context until successful cleanup; missing dependencies do not justify inventing successful provider cleanup. [User]
      - `reconcileDeprovisioning`: triggers AAP delete job for OS teardown. Ironic powers the host back on via BMC and PXE-boots a cleaning ramdisk on the provisioning network — not the tenant OS.
      - Removes management finalizer
    - `reconcileInventory` deletion: UnassignHost from Ironic/Metal3, removes inventory finalizer
    - osac-operator feedback controller: waits for other finalizers, removes feedback finalizer, fires final Signal

8. **Tenant deletes networking resources** (independently):
    - Delete ExternalIPAttachments and ExternalIPs before shared-network cleanup. Subnet cleanup runs Kubernetes placements before Fabric, and VirtualNetwork follows its children. SecurityGroup has no provider delete task.

**BMaaS-specific deletion dependency guard:**

The Subnet controller gates its deprovision job on the complete removal
of all BareMetalInstance CRs with `spec.networkAttachments[].subnetRef`
referencing the subnet. This prevents the infrastructure backend from
rejecting the subnet deletion because bare-metal servers are still
attached to it. The guard lists BMI CRs in the namespace and filters by
`subnetRef` in-memory, requeuing every 10 seconds until all BMIs are gone.
See [Unified Networking — Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)
for the full guard table covering all networking resources.

**IP discovery lease validation:**

The SubnetAttachment controller requires a valid manager result containing one
unambiguous `osac_result.data.dhcp_leases` match for the sole selected-port MAC
and tenant Subnet. A missing result, empty lease, conflicting matches or an
out-of-Subnet address leaves `IPDiscoveryComplete` false with retry/diagnostic
behavior. BMF mirrors the request result; BMI Ready/RUNNING requires apply,
handoff and discovery completion. It cannot appear RUNNING without a real
tenant address because a lease has not propagated yet. [User]

<a id="api-extensions"></a>

### API contract

#### Proto (fulfillment-service)

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
  string interface = 3;                 // optional, immutable: physical interface
                                        // from BareMetalInstanceType
  optional bool primary = 4;            // omitted or true: implicit default gateway; false is rejected
}

message BareMetalInstanceSpec {
  string catalog_item = 1;              // immutable
  optional string ssh_public_key = 2;   // immutable
  optional string user_data = 3;        // immutable
  optional BareMetalInstanceRunStrategy run_strategy = 4;
  int64 restart_trigger = 5;
  map<string, google.protobuf.Any> template_parameters = 6;  // immutable
  optional BareMetalInstanceImage image = 7;                  // immutable
  repeated BareMetalNetworkAttachment network_attachments = 8; // NEW, optional; max 1 for compatibility
  optional bool auto_external_ip_attachment = 9;  // NEW, auto-provision ExternalIP + ExternalIPAttachment
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachment_statuses = 4; // Existing field
}

message BareMetalNetworkAttachmentStatus {
  string interface = 1;
  string subnet_ref = 2;
  string ip_address = 3;  // Discovered after DHCP assignment, synced to fulfillment-service via feedback
  bool primary = 4;       // true for the sole resolved attachment; normalized from spec
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
    Primary    bool   `json:"primary,omitempty"` // true for the sole resolved attachment
}
```

CEL immutability: the `network_attachments` list and every field in each
attachment are immutable after creation, including `subnetRef`,
`securityGroupRefs`, `interface`, and `primary`.

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() <= 1"
  message: "at most one network attachment is supported"
```

#### fulfillment-service Controller (mutateBMI)

The fulfillment-service BM reconciler's `mutateBMI()` function projects TemplateID, TemplateParameters, RunStrategy and the sole `network_attachments` entry from the proto spec to the K8s CR spec. Before persistence, it normalizes the sole attachment to `primary: true` (the implicit-primary rule); a single attachment is never persisted with `primary: false`.

#### Server Validation Rules

- At most one network attachment may be specified
- An omitted or empty list receives the tenant defaults; a supplied single entry receives defaults only for missing fields
- The resolved subnet and security groups must belong to the same VirtualNetwork
- The `interface` must reference a valid port name from the BareMetalInstanceType (its network ports list defines available ports)
- Interfaces with role `lifecycle` are rejected in `network_attachments` — lifecycle interfaces (PXE boot, BMC) are reserved for the provisioning system and are not tenant-attachable
- If `interface` is omitted: defaults to the first port with `role=fabric` from the BareMetalInstanceType (consistent with the omitted-list default)
- If a single attachment is present: `primary` is implicit; omitted or `true` is accepted and `false` is rejected
- The complete resolved `network_attachments` list is immutable after creation; changing it requires deleting and recreating the BaremetalInstance

<a id="implementation-detailsnotesconstraints"></a>

### Component behavior and constraints

#### Provisioning Network and Port Moves

Bare-metal servers configure host-side networking entirely via DHCP. An
**unassigned** server (owned by no tenant) has no tenant network segment, so without
intervention it has no default gateway and no internet — which breaks the Ironic
Python Agent (IPA) during metal3 inspection/cleaning (it cannot download its
rootfs). Hanging the default gateway off the management/BMC NIC is not an option:
the host would then have two DHCP default routes (management + fabric) once a
tenant subnet is attached, causing a default-gateway race.

**Solution — a provisioning network.** A provider-managed provisioning network
segment (DHCP + default gateway + SNAT for outbound internet) holds every
server's **fabric NIC** while the server is idle and during provisioning, so an
unassigned server always has internet via its fabric NIC. The provisioning
network exists in the selected Fabric Manager only — it has no OSAC Subnet CR.
Its backend identifier and environment-variable name are provider configuration
owned by that manager, not operator state or part of the shared task contract.
For example, the current Netris deployment uses
`NETRIS_BM_PROVISIONING_VNET` with a backward-compatible
`NETRIS_BM_PARKING_VNET` fallback; those names are not requirements for other
Fabric Managers.

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

**Attachment manager contract.** The networking controller dispatches
`apply_subnet_attachment` and `delete_subnet_attachment` through the fixed
Fabric Manager entry points. It passes the target-only request as `resource`,
the BMI as `target`, and the resolved Subnet, selected physical port, complete
SecurityGroup rules, and scoped NetworkData separately. Apply installs policy
before tenant connectivity; delete removes policy and restores provisioning
connectivity after BMF confirms host shutdown. Provider segment identifiers and
credentials are manager environment/context, not workload API selectors.
AAP jobs, results and finalizer state belong to the request. The lifecycle owner
waits for apply/delete status and does not launch a parallel raw port-move job.
Backend operations remain idempotent by BMI API ID, selected logical interface and placement; request/target CR UIDs fence projections and result correlation. [User]

#### Topology-Agnostic Operator (Transport is Environment Config)

The operator owns **network segment membership + lifecycle orchestration only**,
with provider operations delegated to the networking controller, never by physical transport:

- creates the attachment request and waits for its apply/delete status,
- patches `spec.image`, reboots via the BMH annotation,
- mirrors the tenant lease discovered by the networking controller (selected-port MAC match).

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

- `NetworkAttachmentsReady` — the SubnetAttachment manager job succeeded and
  the Fabric Manager confirmed the tenant segment membership and policy. BMF
  mirrors this request condition; it does not mean the host has completed its
  tenant handoff.
- `NetworkHandoffComplete` — the port has been moved and the server has been
  rebooted; the OS is running on the tenant network.
- `IPDiscoveryComplete` — the tenant-network DHCP IP is discovered and valid.
  The orchestration function (`reconcileNetworkProvisionAndDiscovery`)
  explicitly checks this condition after `reconcileIPDiscovery` returns —
  if `IPDiscoveryComplete=False/TemplateFailed`, the phase is set to `Failed`
  and the flow stops. Without this explicit check, the phase could briefly
  reach `Ready` between IP discovery retry cycles.
- `NetworkOffboardShutdownComplete` on the BMI (enabled-mode deletion only) —
  the host is confirmed powered off while still on the tenant network.
  `NetworkOffboardComplete` on the SubnetAttachment request means the Fabric
  Manager has removed attachment policy and restored the port to provisioning
  connectivity. BMF does not start OS deprovisioning or release inventory until
  request cleanup has succeeded and finalized.
- With provider networking enabled, phase `Ready` means fully provisioned, on
  the tenant network, and tenant IP known. With provider networking disabled,
  Ready means OS provisioning completed; it does not assert tenant placement or
  tenant IP discovery (see [Provider Networking Disabled](#provider-networking-disabled)).

**Enabled-mode gating rule:** the operator must not surface a tenant IP or
report `Ready` until after move + segment active + reboot + discovery. The
provisioning-network IP is never exposed to the tenant. External access is
signaled separately by the `ExternalIPAttachment` (DNAT) and `NATGateway`
(SNAT) CR statuses. In disabled mode, no tenant IP is surfaced and the skipped
stages follow the separate contract below.

#### IP Discovery

Attachment apply and lease lookup are separate phases on one SubnetAttachment.
The networking controller waits for BMF `NetworkHandoffComplete` before its
`query_dhcp_lease` job. It reads the selected NIC MAC from the BareMetalHost
`osac.openshift.io/interface-macs` JSON map; keys are exactly the catalog port
names. A missing or invalid selected-port MAC keeps discovery waiting and no
query is launched. Hostname-only fallback is not part of this BMI contract.
The query result must contain one unambiguous canonical IPv4 lease in the
resolved Subnet for that MAC. The request stores IP and discovery readiness;
BMF mirrors both to workload status, and feedback synchronizes fulfillment.
The sole status attachment has `primary: true`. [User]

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, copy to K8s CR via mutateBMI, auto-provision ExternalIP |
| bare-metal-fulfillment-operator | Inventory/OS/power lifecycle, target-only attachment request, one handoff reboot, request readiness/IP mirror, shutdown before request deletion, and inventory release after cleanup |
| AAP BM provisioning template | OS provisioning only (host-side networking handled by DHCP) |
| osac-operator feedback controller | Signal fulfillment-service on status changes (unchanged), sync IP addresses from CR status to DB |
| osac-operator BMI cleanup controller | Clean up auto-provisioned ExternalIPAttachment → ExternalIP on BaremetalInstance deletion (phased requeue, `baremetalinstance-cleanup` finalizer) |
| osac-operator ExternalIPAttachment controller | Read BM's primary IP from CR status, create DNAT via fabric_manager |
| SubnetAttachment controller and Fabric Manager | Controller resolves policy/context and owns jobs; manager apply installs policy/connectivity, delete removes policy/restores provisioning port, and separate query returns selected-MAC lease |
| Fabric query_dhcp_lease task | Return one unambiguous tenant-Subnet lease matching the required selected-port MAC |

#### Reconciliation Phase Ordering

Create follows inventory → OS provisioning on provisioning connectivity →
SubnetAttachment apply with complete policy → one BMF handoff reboot →
`NetworkHandoffComplete` → networking-controller selected-MAC DHCP query →
request/workload status mirror → BMI Ready. Neither a provisioning lease nor
attachment apply alone can satisfy tenant IP discovery. [User]

Enabled-mode delete follows auto ExternalIPAttachment cleanup and wait →
auto ExternalIP release and wait → BMF shutdown while still on tenant network
(`NetworkOffboardShutdownComplete=True`) → request deletion and manager policy/
port cleanup (`NetworkOffboardComplete=True`) and request finalization → Ironic
cleaning/OS teardown → inventory release. BMF confirms shutdown before it asks
for request cleanup and waits for cleanup before deprovisioning, so the tenant
OS stays powered off while the port returns to provisioning connectivity;
Ironic's later boot starts only the cleaning ramdisk. Any provider cleanup failure retains
the relevant finalizers and host ownership.
The disabled-mode exception is specified below. [User]

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent BaremetalInstance
- Ordinary BMI authentication and same-tenant access remain. CaaS-owned system-tenant workers additionally require the [parent-bound network authorization](/enhancements/OSAC-1436-caas-networking/design.md#caas-worker-network-authorization); possession of private API credentials alone does not authorize a foreign network.
- SecurityGroup rules control BM inbound traffic (tenant-configurable via explicit SG or default SG)
- The single BM network attachment uses the same SecurityGroup enforcement as the rest of the fabric

### Failure Handling and Recovery

#### bare-metal-fulfillment-operator Reconciliation Failures

- Inventory assignment failure (no free hosts): BaremetalInstance enters Failed state with condition, retries when host becomes available
- Networking failure (dispatcher call failed, switch port config failed): BaremetalInstance enters Failed state with condition, retries on manual correction
- AAP job failure (template execution error): BaremetalInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access))
- ExternalIP provisioning failure: ExternalIP reports failure and optional public access remains unavailable. BaremetalInstance readiness follows its ordinary provisioning, attachment, handoff and real-IP gates; it does not wait for the optional ExternalIP
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach BM (BM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]

### RBAC and Tenancy

BMF requires create/get/list/watch/delete access to its target-only SubnetAttachment requests. The networking controller requires target BMI/BareMetalHost and Subnet/SecurityGroup/NetworkClass read access and owns request status/finalizer updates. It reads runtime NetworkData through the authorized fulfillment private API; the fulfillment service also projects NetworkData records as CRs in the networking hub, but AAP manager jobs have no Kubernetes access to those projections. The operator passes validated values to jobs through the manager contract. Tenant and target ownership are validated before dispatch. [User]

All new resources (BaremetalInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from BaremetalInstance to auto-created resources
- OPA policies enforce tenant-scoped operations according to each resource API;
  networking resources use create/list/get/delete and do not expose
  update/patch, while supported non-network workload updates remain available
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

**Impact:** The fabric manager `apply_subnet_attachment` role and a provisioned provisioning network segment are prerequisites for BMaaS networking. Without them, switch port configuration cannot function.

**Mitigation:** Require the selected Fabric Manager to pass the shared provider qualification for physical attachment, policy, selected-port lease discovery, and cleanup. The closed Netris port-move work is historical backend groundwork, not proof that another manager meets this contract.

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

### Provider Networking Disabled

This service follows the shared provider-networking setting and disabled-mode
contract in [Unified Networking](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control).
The setting is changed during installation or upgrade and takes effect after
the coordinated rollout. Networking APIs, authorization, validation and
defaulting, and ordinary service provisioning remain available while provider
networking is disabled.
[PRD: FR-13] [User]

1. Inventory allocation, hardware management, power management, and ordinary
   host operating-system provisioning and deprovisioning remain active. New
   hosts keep their baseline provisioning connectivity throughout host
   provisioning. `--auto-up` (`RunStrategy=Always`) still turns the host on; it
   stays on the provisioning network because the tenant port move, handoff
   reboot, and tenant DHCP discovery are skipped.
2. Any network move or DHCP query already in progress reaches terminal state
   before the phase is reported skipped. No port move, handoff reboot, tenant
   DHCP query, or substitute work is started while disabled. Each incomplete
   phase skipped after disablement uses `Status=Unknown`, reason
   `ProvisioningDisabled`, and a message naming the skipped operation. Preserve
   `True` conditions for provider phases confirmed complete before disablement.
   A skipped network phase counts as complete only while the accepted current
   mode is disabled and its condition is `Unknown` with the exact reason
   `ProvisioningDisabled`; any other `Unknown` remains incomplete. Enabled
   reconciliation never consumes that skipped condition as provider success.
   Host provisioning can reach Ready without a tenant IP; that Ready state
   describes OS provisioning, not tenant connectivity.
3. No provisioning-network address is relabeled as a tenant-network address;
   no tenant IP is fabricated or discovered through the skipped path, and no
   new public ExternalIP routing operation is submitted. Disabling networking
   does not withdraw an existing `ExternalIPAttachment` DNAT route. A route
   configured before disablement may remain active until manual/provider-side
   cleanup, so the disabled setting does not guarantee that prior public
   exposure ends.
4. Deletion preserves normal host shutdown, teardown, inventory release, and
   logical auto-created child deletion order. It waits for active network work
   to become terminal and performs no tenant-to-provisioning port movement or
   other provider cleanup. A host is not powered off solely to precede a port
   move that will not occur. Disabled mode does not create or change
   `NetworkOffboardComplete` on a SubnetAttachment to report skipped cleanup.
   Preserve any existing `NetworkOffboardShutdownComplete` as a record of the
   prior enabled-mode shutdown: `True` confirms host power-off; `False` means
   completion was not observed before disablement. Neither condition proves
   the port moved. Newly created disabled-mode hosts were never moved
   off provisioning connectivity, so ordinary deprovisioning can use that
   baseline. A host
   previously moved to a tenant network is not moved back when the setting is
   disabled; provider/manual restoration may be required before Ironic cleaning
   can use provisioning connectivity.

Shared resource status, validation and automatic ExternalIP behavior follow
[Unified Networking](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control).
The BMI's Ready condition attests only to OS provisioning in this mode.

Re-enabling provider networking follows the [shared activation preflight](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control). For this extension, drain and delete every BaremetalInstance through the normal BMaaS teardown path. When a BaremetalInstance is a worker owned by a Cluster, delete the parent Cluster through the CaaS extension so the worker handoff and host cleanup finish in order. The shared gate also waits for workloads owned by other extensions and blocks new workload Creates while activation is pending. Reads and deletes remain available. After the deployment profile and configured pools regain real provider readiness, each new BaremetalInstance still waits for its own ready networking references. A disabled-mode ProvisioningDisabled state does not satisfy enabled readiness. An ordinary restart of an already enabled deployment does not require a new drain. [User]

## Alternatives Considered

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

Resolved: After request apply and BMF's one handoff reboot complete, the networking controller dispatches a separate `query_dhcp_lease` job using the required selected-port MAC and immutable tenant Subnet context. It validates the manager result and stores the real address and IPDiscoveryComplete on the request; BMF mirrors it into BMI status and feedback synchronizes fulfillment. `apply_subnet_attachment` applies switch-side connectivity and stateful policy without changing host OS configuration. [User]

## Test Plan

- **[DEV/QE] Tenant boundary:** standalone BMIs reject foreign networks. CaaS workers require the immutable authorized parent binding before apply/lease lookup and retain its original context through cleanup; ordinary system resources gain no exception. The extension owns these parent-authorization cases; generic owner/context rejection is covered by [TC-FR6-01](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md#tc-fr6-01-reject-invalid-json-schemas-declarations-and-manager-results).

### Attachment Lifecycle and Provider Contract

- **[DEV] Contract:** request-as-resource/BMI-as-target and normalized stateful policy payload; mandatory Fabric entry points; apply success without invented address data; selected MAC required and malformed/ambiguous lease rejected.
- **[DEV] Envtest:** accepted apply readiness enables exactly one handoff reboot; DHCP job waits for handoff and MAC; BMF mirrors request status; `NetworkOffboardShutdownComplete=True` precedes request deletion; deprovision waits for request `NetworkOffboardComplete=True` and finalization; all cleanup failures retain finalizers and inventory ownership.
- **[QE] E2E:** provision/discover/delete BMI and CaaS worker on one Subnet; policy failure prevents tenant traffic; a restart during offboard boots only the Ironic cleaning ramdisk after port restoration while the tenant OS remains powered off; persistent DNAT or attachment failure prevents host reuse. [User]


### Provider Networking Control (FR-13)

- **[DEV] Envtest / [QE] E2E:** request re-enablement with a baseline workload or a workload whose networking was suspended by disablement still present. Assert activation and new workload creates are blocked, existing Read/Delete remain available, and no apply/lease/reservation or tenant attachment mutation runs. Drain workloads and jobs, repair backend leftovers, then activate; stale skipped readiness cannot admit new workloads until genuine network prerequisites are ready. Repeated enabled restarts do not invoke a fresh drain.

- Verify normal bare-metal server provision/delete jobs still run with the shared setting
  disabled and sufficient baseline connectivity; no network provider job runs.
- Verify in-progress network work reaches terminal state before skipped status
  or deletion completion, including retryable status errors.
- Verify non-allocating Networking API resources report `Ready=True`, reason
  `ProvisioningDisabled`, with a skipped-work message after logical
  preconditions pass. Verify ExternalIP pending and previously allocated
  statuses match the shared contract. Verify incomplete BMI networking phases
  skipped after disablement report `Status=Unknown`, reason
  `ProvisioningDisabled`, confirmed prior successes remain `True`, and legacy
  `True`/`Skipped` conditions are normalized; no tenant IP or ExternalIP address
  is fabricated. Verify disabled deletion does not synthesize
  `NetworkOffboardComplete` on the request or create
  `NetworkOffboardShutdownComplete` solely to claim that a skipped port cleanup
  gate completed. Enabled mode retains normal provider behavior.
- Verify invalid API/defaulting/dependency requests remain rejected,
  SecurityGroup defaulting/immutability remains unchanged, and automatic
  attachments still wait for Allocated + workload Ready.

### Unit Tests

- fulfillment-service: max-one attachment and primary validation (accept single implicit primary, accept explicit primary)
- fulfillment-service: omitted and partial attachment defaulting (empty `security_groups` is missing; supplied values are preserved; a missing group list defaults only for the tenant default VirtualNetwork and is rejected for a non-default subnet without caller-supplied groups)
- fulfillment-service: interface validation (reject an interface not in BareMetalInstanceType)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- bare-metal-fulfillment-operator creates and waits for a target-only SubnetAttachment after provisioning; the networking controller dispatches attachment policy work. [User]
- osac-operator networking controller: apply/delete jobs use request identity, workload target, complete stateful policy, selected interface and durable normalized provider context; BMF waits for and mirrors request status
- networking controller: the immutable selected physical interface resolves to exactly one MAC in the interface-macs annotation; missing/ambiguous mappings block lease dispatch, including CaaS workers

### Integration Tests

- **[DEV/QE] Optional external access:** fail asynchronous ExternalIP allocation after an admitted workload Create. Core workload readiness still follows its ordinary provision/attachment/IP gates; the ExternalIP reports failure and no ExternalIPAttachment is created until a real allocation and Ready target exist. Pool exhaustion at initial admission still fails atomically.

- E2E: create BaremetalInstance with two attachments, verify the API rejects the request
- E2E: create BaremetalInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: delete BaremetalInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create BaremetalInstance with interface not in BareMetalInstanceType, verify error returned
- E2E: create BaremetalInstance with a second `--network-attachment`, verify the CLI and API return a maximum-one error
- E2E: verify IP discovery (`query_dhcp_lease` role queries fabric manager DHCP lease API after provisioning + reboot, matches port MAC to assigned IP on tenant network, request controller records the IP, BMF mirrors BMI status, feedback controller syncs to fulfillment-service, ExternalIPAttachment controller reads primary IP)
- E2E: verify the port move and reboot flow — create BMI provisions on the provisioning network, then moves the fabric port provisioning network → tenant network + reboots; delete BMI returns it tenant → provisioning network (confirm in fabric manager; a freed server can re-inspect with internet)
- E2E: verify isolation-until-ready — before the move, a tenant vantage cannot reach the server; after move + reboot, it can, and the server is no longer on the provisioning network

### Tricky Test Cases

- BM with one attachment and omitted `primary` (verify the sole attachment is normalized to `primary: true` in the CR/status and is the default route)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify retained finalizer/ownership on persistent failure, successful cleanup after repair)
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
- [ ] Request-owned fixed `apply_subnet_attachment`, `delete_subnet_attachment` and separate `query_dhcp_lease` jobs tracked durably; provisioning network and initial per-server attachment exist as deployment prerequisites
- [ ] BareMetalInstanceType with network ports (`BareMetalNetworkPortSpec`) available and tested
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] IP discovery implemented (`query_dhcp_lease` role queries fabric manager DHCP lease API after provisioning + reboot, matches port MAC to assigned IP on tenant network, request controller records the IP, BMF mirrors BMI status, feedback syncs to fulfillment-service)
- [ ] Tenant handoff signaling (NetworkAttachmentsReady, NetworkHandoffComplete, IPDiscoveryComplete, Ready) implemented
- [ ] Integration tests pass (E2E coverage for max-one validation, auto ExternalIP, IP feedback, isolation-until-ready)
- [ ] Documentation: API reference, user guide for simplified BM creation

GA criteria:
- [ ] Selected Fabric Manager passes provider qualification for physical attachment, stateful policy, selected-port lease discovery, and cleanup
- [ ] Network Manager Integration Contract registration, generic dispatch, result validation, and durable recovery implemented and stable
- [ ] NATGateway full stack (OSAC-1443) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)
- [ ] Reboot-based short-term validated; evolution path to Ironic Standalone Networking or dedicated provisioning NIC confirmed

## Upgrade and Downgrade Strategy

### Configuration compatibility

**Note on terminology:** In the current code and configuration, the provisioning network is identified as `netris_bm_parking_vnet`. This identifier is retained for deployment stability; the docs-only rename to "provisioning network" clarifies its purpose without requiring immediate config changes.

### Upgrade and downgrade gates

Follow the [shared coordinated rollout and rollback requirements](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy).
Preserve existing resource/provider bindings, accepted results and cleanup
context. Wire compatibility does not establish backend migration safety.
Drain or verifiably adopt legacy state before using new ownership keys; finish
cleanup with compatible components before downgrading to a version that cannot
interpret the retained state. Disabled-mode provider leftovers still require
confirmed provider/manual cleanup before their addresses or hosts are reused.

### Service compatibility

Existing `network_attachments` and attachment-status fields retain their
wire shapes; the one-entry limit and defaulting follow the unified contract.
An omitted attachment uses tenant defaults after resolution, rather than
implicitly bypassing networking. The new handoff/cleanup contract requires
compatible BMF and networking controllers, including confirmed shutdown before
port restoration. Existing hosts require verified adoption or drain/recreation;
do not delete their CRs to bypass cleanup.

## Version Skew Strategy

### Control Plane Skew

Use the [shared version-skew rules](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy).
Fulfillment, the workload/networking controllers and AAP content must agree on
the handoff and cleanup protocol. A coordinated installer release still has a
rolling transition; incompatible components must not dispatch new work.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- A client omitting `network_attachments` receives server-resolved tenant defaults under the unified admission contract
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
2. Check AAP job logs for `apply_subnet_attachment` role errors (switch-side) — e.g. port not found on the server, or the provisioning/tenant network segment not resolvable
3. If fabric manager unreachable, investigate connectivity
4. If switch port config failed, investigate switch configuration

### Symptom: BM has no default gateway

**Detection:** BM cannot reach external networks, `ip route` shows no default route

**Cause:** The resolved sole attachment/interface is missing or not Ready. Omission of `primary` is valid and means the sole attachment is implicitly primary.

**Resolution:**
1. Check BaremetalInstance spec: `kubectl get baremetalinstance <name> -n <namespace> -o yaml`
2. Verify there is exactly one `networkAttachments[]` entry
3. Inspect the resolved attachment and interface status, then correct the attachment or underlying network resource and recreate the BaremetalInstance if necessary

### Symptom: Deletion waits for automatic external cleanup

**Detection:** The parent remains Deleting with its finalizer and child references; an auto-created ExternalIPAttachment or ExternalIP reports a failed cleanup operation.

**Cause:** The provider has not confirmed DNAT removal or address release.

**Resolution:**
1. Inspect parent, child and AAP operation diagnostics to identify the failed task.
2. Repair provider connectivity/configuration or the backend operation; let reconciliation retry with the same durable operation identity.
3. Confirm attachment deletion before address release and parent deletion. Preserve finalizers and address ownership until successful cleanup; do not force-remove finalizers. [User]

### Symptom: ExternalIPAttachment stuck in Pending, waiting for BM IP address

**Detection:** `kubectl describe externalipattachment <name> -n <namespace>` shows condition "WaitingForIPAddress"

**Cause:** Host has not yet received DHCP-assigned IP (provisioning still in progress or failed)

**Resolution:**
1. Check BaremetalInstance status: `kubectl get baremetalinstance <name> -n <namespace> -o jsonpath='{.status.networkAttachmentStatuses[?(@.primary==true)].ipAddress}'`
2. If IP is missing, check bare-metal-fulfillment-operator logs for provisioning phase completion
3. If provisioning completed but IP missing, investigate `query_dhcp_lease` dispatcher call (DHCP lease query may have failed, returned empty, or port MAC did not match any lease). Confirm the BareMetalHost carries the `osac.openshift.io/interface-macs` annotation with the attachment's interface — without it, discovery waits and no query is dispatched

### Disabling automatic ExternalIP requests

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running BM servers

### Provider networking intentionally skipped

Set `global.networking.provisioningEnabled=false` through the Helm setting or Enclave Wizard checkbox
installation/upgrade value map and complete both operator rollouts. Inspect
`Ready=True`/`ProvisioningDisabled` conditions on non-allocating Networking API
resources, `Unknown`/`ProvisioningDisabled` conditions on BMI network phases,
and tracked network job states. Ordinary workload provisioning remains active
with the baseline connectivity described
above. Networking APIs remain available; no provider allocation, routing,
port movement, DHCP discovery, or cleanup is supplied by the skipped path.
Existing provider resources may require manual/provider-side cleanup. [User]

## Infrastructure Needed

- AAP execution environment with the fabric manager `apply_subnet_attachment` role
- A provisioned manager-owned provisioning network segment (DHCP + gateway + SNAT) and the initial per-server attach, plus the BareMetalHost `osac.openshift.io/interface-macs` annotation — deployment prerequisites (deployment infrastructure)
- Network Manager Integration Contract implementation for registration, generic dispatch, result validation, and durable recovery
- Integration test environment with fabric manager and Ironic/Metal3 backend

## Dependencies

Jira states below were checked on 2026-10-12. Closed legacy or service issues are implementation history; they do not satisfy the target Network Manager Integration Contract, which remains required before provider networking is enabled.

| Dependency | Jira | Status (2026-10-12) |
|-----------|------|---------------------|
| Legacy dispatcher groundwork (not the new NetworkManager/NetworkData contract) | OSAC-1457, OSAC-1458, OSAC-1460 | Closed |
| Network Manager Integration Contract registration, generic dispatch, result validation, and durable recovery | N/A — defined by the linked contract design; platform implementation remains required | Required before provider networking is enabled |
| NATGateway full stack | OSAC-1443 (10 tasks) | Closed |
| ExternalIPAttachment BM target in CRD | OSAC-2041 | Closed |
| BM DNAT flow in controller | OSAC-1496 | Closed |
| BareMetalNetworkAttachment proto | OSAC-1508 | Closed |
| Primary field on BareMetalNetworkAttachment | OSAC-2042 | Closed |
| Immutability + interface + primary validation | OSAC-1509 | Closed |
| CLI --network-attachment for BareMetalInstance | OSAC-2075 | Closed |
| Historical BM direct-dispatch port-move groundwork. Target-only SubnetAttachment lifecycle, fixed adapter jobs and immutable dispatched context are shared target implementation work; the CR field/mutateBMI producers remain tracked below | OSAC-2047 | Closed (historical groundwork) |
| BM reboot flow (reconcileReboot issues BMH annotation-based reboot after port move) | Not tracked | **GAP** |
| Integration test | OSAC-1510 | Closed |
| Historical Fabric port-move backend groundwork; fixed apply/delete attachment adapters and policy semantics remain target implementation work | OSAC-2081 (Netris BM) | Closed (historical groundwork) |
| Provider provisioning network segment (DHCP + gateway + SNAT) and initial per-server attach in setup-bmaas | osac-deployment infrastructure | Deployment prerequisite; tracked outside Jira |
| BareMetalHost `osac.openshift.io/interface-macs` annotation (inventory tooling) | osac-deployment infrastructure | Deployment prerequisite; tracked outside Jira |
| BareMetalInstance CRD: add NetworkAttachments | Not tracked | **GAP** |
| mutateBMI: copy network_attachments to K8s CR | Not tracked | **GAP** |
| Request-owned DHCP query validates selected-MAC lease and result; BMF mirrors discovery status | Not tracked | **GAP** |
| bare-metal-fulfillment-operator dispatcher capability + RBAC for Subnet/NetworkClass CRs | Not tracked | **GAP** |
| Remove unused BareMetalInstance spec.networkClass field | Not tracked | **GAP** |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed | Not tracked | **GAP** |

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ design 0.11.5 - 1c6e8de, workspace main @ 04cc50101

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"04cc50101","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
