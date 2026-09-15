---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# VMaaS Networking — Single Interface, Optional Attachments and Auto External Access

This enhancement extends the unified networking API to support VMaaS-specific requirements: a list-shaped but single-entry ComputeInstance attachment contract, optional network attachments with tenant defaults, and auto-provisioned external access (ExternalIP). Multi-interface VM support is unsupported in the current contract.

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md), providing the detailed per-service flow for this service type. The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how this specific service consumes that architecture.

Shared field types, formats, presence rules, allowed values, and validation
are defined by the [Unified Networking field contract](/enhancements/OSAC-1433-unified-networking/design.md#field-types-formats-and-validation).

The shared networking resource model, IPv4-only scope, and connected
single-hub deployment boundary are defined by the [Unified Networking
design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).
The shared operation contract is defined by [Supported Operations and
Immutability](/enhancements/OSAC-1433-unified-networking/design.md#supported-operations-and-immutability).

ComputeInstance exposes the repeated `network_attachments` API field,
whose values are `ComputeNetworkAttachment` messages. The field remains
optional and list-shaped while
accepting at most one entry, and `auto_external_ip_attachment` enables fully
connected VMs in a single API call. See [PRD](prd.md) for detailed
requirements.

## Motivation

ComputeInstance already participates in the networking API. The legacy flow
being replaced by the shared dispatcher was:

1. Tenant creates VirtualNetwork, Subnet, NetworkACL via API
2. osac-operator's networking controllers reconcile each resource as a standalone AAP job, using `implementation_strategy` to select the Ansible role (e.g., `osac.templates.cudn_net.create_subnet`)
3. Tenant creates ComputeInstance with `network_attachments` (resource-specific message, single-interface only)
4. osac-operator's ComputeInstance controller resolves subnet → namespace, triggers AAP job
5. AAP template (`osac.templates.ocp_virt_vm`) creates KubeVirt VirtualMachine with one `l2bridge` interface in the subnet's CUDN namespace

### What Already Works

- `network_attachments` is the ComputeInstanceSpec attachment field for ComputeInstance
- Operator CRD has `NetworkAttachments []ComputeNetworkAttachment` with CEL immutability rules (the complete list and every network field are immutable)
- Subnet-to-namespace resolution is implemented
- The template creates VMs in the correct namespace
- ExternalIPAttachment with `compute_instance` target works end-to-end

### What's Missing

- Single-NIC only — template creates one `l2bridge` interface
- BM-only deployment validation (reject VM when no k8sManager)
- Auto ExternalIP allocation (tenant must manually create ExternalIP + ExternalIPAttachment)

### Goals

- Single-interface support with a list-shaped attachment field
- Resource-specific attachment message (`ComputeNetworkAttachment`) with a `primary` field
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- BM-only deployment validation to reject VM provisioning when no k8s_manager is available

### Non-Goals

- CaaS or BMaaS networking (this EP covers VMaaS only)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Kubernetes manager implementation (CUDN or EVPN fabric integration via k8s_manager roles)

## Proposal

### Workflow Description

#### Networking Setup (unchanged pattern, new dispatch mechanism)

1. **Tenant creates VirtualNetwork:**
   ```bash
   osac create virtualnetwork --cidr 10.0.0.0/16 --name my-net
   ```
   - fulfillment-service → creates VirtualNetwork CR
   - osac-operator VirtualNetwork controller → dispatcher resolves the single deployment NetworkClass and its `implementation_strategy`
   - The configured manager creates the isolated tenant segment

2. **Tenant creates Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   - osac-operator Subnet controller → dispatcher resolves NetworkClass → triggers TWO AAP jobs (multi-job tracking per OSAC-1459):
     - the configured manager creates the subnet backend; when both managers are configured, the Fabric Manager creates the VLAN/fabric segment and the K8s Manager creates the CUDN overlay and bridge
   - After both complete: subnet is Ready. The CUDN namespace is the deployment target for VMs.

3. **Tenant creates NetworkACL:**
   ```bash
   osac create network-acl --virtual-network my-net --subnet my-subnet --name my-nacl \
     --rule "action:allow,direction:ingress,protocol:tcp,port:443,source-cidr:0.0.0.0/0"
   ```
   - The NetworkACL is associated with the Subnet. It is not attached to an
     individual VM.
   - Dispatcher → the configured network manager's `create_network_acl` operation

#### VM Creation

4. **Tenant creates ComputeInstance:**
   ```bash
   # Explicit networking:
   osac create computeinstance --template ocp_virt_vm \
     --network-attachment subnet=my-subnet \
     --name my-vm

   # Or with defaults + auto external access:
   osac create computeinstance --template ocp_virt_vm \
     --external-ip-attachment --name my-vm
   ```
   - fulfillment-service:
   - If `network_attachments` is omitted or empty: populates the tenant default Subnet. For a supplied attachment, defaults only a missing subnet (see Default Networking PRD)
     - Validates: at most one attachment, the resolved Subnet exists and is Ready, the Subnet has an effective NetworkACL, and the single-entry primary rule is satisfied
     - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity), creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
   - Creates ComputeInstance CR with `network_attachments`

5. **osac-operator ComputeInstance controller:**

   a. `resolveNetworking` (existing logic, extended):
      - `PrimarySubnetRef()` → returns the sole attachment's subnet (the entry is implicitly primary when `primary` is omitted)
      - `resolveSubnetTargetNamespace()` → looks up Subnet CR → namespace (same as today)
      - Stamps `osac.openshift.io/subnet-target-namespace` annotation
      - **No dispatcher call for network attachments** — VMs don't need switch port configuration. The k8sManager's work was done at subnet creation (step 2). The overlay already exists.

   b. Triggers AAP job: `osac-create-compute-instance`

6. **AAP template (`osac.templates.ocp_virt_vm`):**
   - Reads `subnet-target-namespace` → deployment namespace
   - Reads `network_attachments`:
     - Empty list: this is resolved to the tenant defaults before the CR is created
     - Single attachment: creates VM with one `l2bridge` interface in the subnet's CUDN namespace
     - Multiple entries are rejected by fulfillment-service and never reach the template
   - Reads the effective NetworkACL from the selected Subnet; no ACL reference
     is copied into the VM attachment or pod labels
   - Creates DataVolume + KubeVirt VirtualMachine
   - VM gets IP from each CUDN (via DHCP)
   - VM is on the fabric (overlay bridged at subnet creation)
   - **No networking logic** — template does OS/VM provisioning only. VMs join the fabric through the overlay, not through switch ports.

#### IP Discovery (feedback loop)

7. **osac-operator ComputeInstance feedback controller** discovers VM IPs:
   - Watches KubeVirt VMI (VirtualMachineInstance) network status
   - Reads the assigned IP from the sole `vmi.status.interfaces[].ipAddress`
   - Maps the interface to the sole `ComputeNetworkAttachment` value from
     `network_attachments` by CUDN NAD reference
   - Fires Signal RPC to fulfillment-service with per-attachment IP data
   - fulfillment-service writes at most one `compute_network_attachment_statuses` entry on ComputeInstanceStatus (`subnet` typed reference, `ip_address`, `primary`)
   - Tenant can inspect: `osac get computeinstance my-vm -o yaml` shows the assigned IP for the attachment

#### External Access (optional, auto-provisioned when `auto_external_ip_attachment=true`)

8. **fulfillment-service creates ExternalIP and ExternalIPAttachment:**
   - Auto-selects an IPv4 ExternalIPPool (READY, most available capacity)
   - Creates ExternalIP from pool, labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <compute-instance-id>`
   - Creates ExternalIPAttachment binding ExternalIP to VM's primary subnet IP, labeled `osac.openshift.io/auto-created: "true"`
   - Both start in **Pending** state. The ExternalIPAttachment controller checks two preconditions before dispatching (requeues if either is not met):
     1. ExternalIP must be Allocated (have an allocated address from the fabric manager)
     2. ComputeInstance must have `compute_network_attachment_statuses` populated with the primary attachment's `ip_address` (VM IP discovered from KubeVirt VMI)
   - Once both are met: dispatcher → the configured network manager's external-IP attachment operation
   - The configured network manager creates DNAT: external IP → VM's primary subnet IP (from `compute_network_attachment_statuses`)
   - ExternalIPAttachment transitions from Pending to Ready

#### Deletion (reverse order)

9. **Delete ComputeInstance:**
   - **Auto-provisioned cleanup:** If ExternalIP/ExternalIPAttachment were created by the system (`auto_external_ip_attachment=true`, labeled `osac.openshift.io/auto-created: "true"`): parent finalizer deletes ExternalIPAttachment first, then ExternalIP.
   - **Manually created resources are NOT cleaned up** — if the tenant created an ExternalIP explicitly, it persists until the tenant deletes it. A manually created ExternalIPAttachment that targets the ComputeInstance remains a reverse reference and blocks ComputeInstance deletion until the tenant deletes the attachment; it is not detached or changed to Pending implicitly.
   - **Default networking resources (VN, Subnet, NetworkACL, NATGateway) are NOT cleaned up** — they are tenant-scoped and shared across resources.
   - osac-operator triggers `osac-delete-compute-instance` AAP job
   - Template deletes KubeVirt VM + DataVolume
   - No `move_network_attachment` call — the VM lives on the CUDN overlay, not a fabric switch port, so it is never parked or port-moved (the port-move primitive and parking apply only to fabric-attached BM servers and CaaS agents)

10. **Delete networking resources:**
    - Each networking resource controller triggers its delete AAP job
    - Dispatcher calls the appropriate manager role for each

### CLI networking contract

VMaaS inherits the shared [Unified Networking CLI contract](../OSAC-1433-unified-networking/design.md#normative-cli-contract).
The VM-specific mapping is:

| API field | CLI form | Allowed values |
|---|---|---|
| `spec.network_attachments` | One optional `--network-attachment` | Zero or one attachment; repeating the option is rejected |
| `ComputeNetworkAttachment.subnet` | `subnet=<name>` inside the attachment value | Optional; omission receives only the tenant default Subnet |
| `ComputeNetworkAttachment.primary` | Not emitted by the CLI | Omission is implicitly primary; `true` is accepted only through a structured client; `false` is rejected |
| `auto_external_ip_attachment` | `--external-ip-attachment` | Presence means `true`; omission means `false`; create-time only |

The canonical explicit command is:

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet \
  --name my-vm
```

The CLI must not expose `--network-attachments`, `interface=...`, or a
multi-NIC mode for VMaaS. Omitting `--network-attachment` invokes the tenant
default Subnet. The CLI constructs a typed local Subnet reference and sends
the resource-specific `ComputeNetworkAttachment` message. NetworkACL
association is managed through the NetworkACL resource. VM network fields and
`auto_external_ip_attachment` cannot be changed through update or patch
commands; delete and recreate is required.

### API Extensions

#### Proto (fulfillment-service)

Replace the shared `NetworkAttachment` with `ComputeNetworkAttachment`:

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  optional bool primary = 2;            // one attachment is implicitly primary
}

message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 18; // optional; zero or one supported
  optional bool auto_external_ip_attachment = 19; // NEW, create-time only; omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment
}

message ComputeNetworkAttachmentStatus {
  SubnetLocalReference subnet = 1;     // Controller-owned resolved reference
  string ip_address = 2;               // Discovered from KubeVirt VMI network status after DHCP/overlay assignment
  bool primary = 3;                     // Echoed from spec
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = N; // NEW; at most one entry
}
```

#### Operator CRD (osac-operator)

The public fulfillment API field `spec.network_attachments` maps to the
operator CRD field `spec.networkAttachments` (Go field
`ComputeInstanceSpec.NetworkAttachments`). Fulfillment-service performs this
API-to-CRD conversion when it creates the private CR; the operator does not
accept the public snake_case field directly. The CRD field is the same
resource-specific `ComputeNetworkAttachment` message, not the replaced shared
`NetworkAttachment` message. There is no legacy conversion path because the
shared field has no users or persisted resources.

Define/extend `ComputeInstanceSpec.NetworkAttachments` with:
- `Primary bool` field with CEL immutability validation
- CEL immutability validation for the complete attachment list and every entry field
- Add validation: the list contains at most one attachment; if present, `primary` must be omitted or `true`
- `PrimarySubnetRef()` returns the sole attachment (or no attachment before default resolution)

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() <= 1 && (self.networkAttachments.size() == 0 || !has(self.networkAttachments[0].primary) || self.networkAttachments[0].primary == true)"
  message: "ComputeInstance supports at most one network attachment and it cannot set primary: false"
```

Add `ComputeNetworkAttachmentStatus` to `ComputeInstanceStatus`:

```go
type ComputeInstanceStatus struct {
    // ... existing fields ...
    ComputeNetworkAttachmentStatuses []ComputeNetworkAttachmentStatus `json:"computeNetworkAttachmentStatuses,omitempty"`
}

type ComputeNetworkAttachmentStatus struct {
    Subnet *SubnetLocalReference `json:"subnet,omitempty"`
    IPAddress string `json:"ipAddress,omitempty"` // Discovered from KubeVirt VMI after DHCP/overlay assignment
    Primary   bool   `json:"primary,omitempty"`
}
```

The feedback controller populates `ComputeNetworkAttachmentStatuses` by watching the sole KubeVirt VMI interface in `status.interfaces` and mapping its IP to the single attachment by CUDN NAD reference.

#### Server Validation (fulfillment-service)

VMaaS performs validation in the shared order defined by the [Unified
Networking validation pipeline](/enhancements/OSAC-1433-unified-networking/design.md#validation-and-enforcement-pipeline).
The following checks are VMaaS-specific and are required on every direct,
Template-based, and Catalog-based ComputeInstance create path.

**Request shape validation:**

- `network_attachments` must contain zero or one entry. A second entry is
  rejected before reference lookup, defaulting, capacity reservation, or CR
  creation with a single-interface cardinality error.
- The optional `primary` presence bit is significant. Omitted and `true` are
  accepted for the sole entry; explicit `false` is rejected. A defaulted entry
  is persisted with the canonical primary meaning, but an explicit `false`
  must never be rewritten to `true`.
- Unknown attachment fields, a malformed subnet reference, or a malformed
  Boolean presence encoding is
  rejected by the API shape layer.

**Attachment resolution and references:**

- Missing or empty attachment input resolves to exactly one attachment
  containing the tenant's default Subnet. If the default Subnet is absent or
  not Ready, return the shared no-default or readiness error; do not create a
  VM with an unresolved attachment. The effective NetworkACL is inherited
  from that Subnet.
- A supplied single attachment defaults only a missing subnet. After
  resolution, the Subnet must exist, be `Ready`, be IPv4, and belong to the
  effective tenant/project. The Subnet must have an effective NetworkACL.
- The resolved attachment references one VirtualNetwork. A Catalog or
  Template value that resolves to an invalid Subnet is rejected; defaulting
  must not silently replace an explicitly supplied Subnet.
- The resolved Subnet must have the hosting namespace/CUDN placement required
  by the selected K8s manager. Missing placement status, a failed CUDN, or an
  unsupported manager capability is a provisioning precondition failure, not
  a reason to create a second attachment or fall back to another Subnet.

**Deployment and capability validation:**

- ComputeInstance creation requires a `k8s_manager` in the resolved
  NetworkClass. A Fabric-only/BM-only deployment is rejected before the
  ComputeInstance is persisted because VM placement cannot be performed.
- The selected K8s manager must advertise Compute/VM placement support for
  the requested Subnet and the selected address family. An EVPN or other
  prerequisite-gated manager is accepted only when its own design's placement
  checks pass.
- VMaaS must not require a Fabric Manager when the K8s-only manager advertises
  the complete supported VM networking surface. It must, however, reject any
  VM request that would require an unsupported NATGateway or unsupported
  manager operation.

**CRD and controller validation:**

- The ComputeInstance CRD repeats the maximum-cardinality and optional
  `primary` checks with CEL. It also makes the entire resolved attachment
  list, every Subnet reference, and `primary` immutable after creation.
- `PrimarySubnetRef()` returns the sole resolved attachment's Subnet and
  returns no value only before default resolution has populated the CR. It
  must never select an arbitrary first entry from an invalid multi-entry list.
- The AAP template receives one resolved attachment and creates exactly one
  KubeVirt network interface. It must fail closed if the CR contains more
  than one entry rather than provisioning only the first entry.
- The feedback controller accepts zero or one VMI network status entry, maps
  the sole interface by the CUDN NAD reference, and writes only a canonical
  IPv4 address that belongs to the resolved Subnet. Duplicate, mismatched,
  non-IPv4, or more-than-one status entries are not published as Ready.

**Automatic ExternalIP validation:**

- When `auto_external_ip_attachment` is true, the same request first passes
  normal VM attachment validation. Automatic external access cannot bypass
  the required default Subnet or its effective NetworkACL.
- The selected pool must be Ready, IPv4, and have capacity. Pool selection is
  deterministic among equal-capacity pools. Capacity reservation, the parent
  ComputeInstance, ExternalIP, and Pending ExternalIPAttachment are persisted
  atomically; any validation or capacity failure rolls back all of them.
- The auto-created ExternalIPAttachment target is the ComputeInstance and its
  endpoint is `UNSPECIFIED`. The service never accepts a tenant-supplied
  target endpoint IP for this path.
- The ExternalIPAttachment controller dispatches only after the ExternalIP
  is `Allocated` and the VM status contains the sole attachment's canonical
  IPv4 address. Until then it requeues and leaves the attachment Pending.
- The auto-created ExternalIPAttachment DNAT target is the sole attachment's
  IP. A VM with no discovered attachment IP cannot transition the attachment
  to Ready.

**Update, delete, and status validation:**

- Update, patch, replace, and field-mask requests that change either
  attachment field, any nested Subnet/primary value, or
  `auto_external_ip_attachment` are rejected. The supported change is delete
  and recreate.
- A delete is blocked by the shared dependency guards while the VM has a
  manually created ExternalIPAttachment reference or while an auto-created
  ExternalIPAttachment still protects a Subnet, ExternalIP, or ExternalIPPool.
  Auto-created children are deleted in attachment-then-IP order before parent
  finalizer removal.
- Status writes may update only controller-owned conditions, provisioning
  state, discovered IP, and finalizers. A status callback cannot mutate the
  resolved network spec or make an unready Subnet or its effective NetworkACL
  usable.

Any validation failure above is surfaced with a field path where possible,
for example `spec.network_attachments[1]`,
`spec.network_attachments[0].subnet`, or
`spec.network_attachments[0].primary`. The request is not persisted
when the failure is found during create.

#### Catalog Item interaction

Catalog Item v2 governs the canonical `network_attachments` field as
one complete list. It may lock the list or make it editable with an optional
default. The field is the only supported ComputeInstance networking input.

Catalog resolution happens before tenant default networking. A locked list
rejects conflicting tenant input. An editable list accepts tenant input,
otherwise uses its Catalog default, then the Template default, and finally
defaults only a missing Subnet from the tenant's default Subnet. An
explicitly supplied Subnet is never replaced; NetworkACL association is not a
Catalog or workload field.

The editable policy applies only while creating the ComputeInstance. After
creation, the complete resolved attachment list and every network field are
read-only; changing them requires deleting and recreating the VM. Catalog Item
definitions and metadata remain governed by Catalog Items v2 and are not
changed here.

The Catalog list must obey the same Compute rules as direct creation: it may
contain zero or one attachment, and a supplied attachment is implicit primary
when `primary` is omitted. Catalog policy can govern the Subnet and the
compatible `primary` value; NetworkACL association, CUDN/NAD placement, and
hosting-cluster selection remain system concerns. A shared Catalog Item cannot
lock or default a tenant-local Subnet reference.

#### Template Changes (osac-aap)

- `osac.templates.ocp_virt_vm/tasks/create_build_spec.yaml`: consume the single resolved entry from `network_attachments`
- The entry maps to one KubeVirt interface with `l2bridge` binding referencing the attachment's subnet's CUDN NAD
- The sole attachment supplies the IP, default gateway, and DNS via DHCP

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate `network_attachments`, create CR, auto-provision ExternalIP, write `compute_network_attachment_statuses` from feedback |
| osac-operator ComputeInstance controller | Resolve subnet → namespace, trigger AAP, clean up auto-provisioned resources |
| osac-operator ComputeInstance feedback controller | Watch the sole KubeVirt VMI interface status, discover the attachment IP, Signal fulfillment-service |
| osac-operator networking controllers | Dispatch to managers via dispatcher (VN, Subnet, NetworkACL, ExternalIP) |
| AAP template (ocp_virt_vm) | Create single-interface KubeVirt VM in the correct namespace |
| configured network manager(s) | VN/Subnet/NetworkACL/ExternalIP provisioning; no per-VM call after subnet setup |
| k8s_manager (Ansible role, when configured) | Create/bridge the CUDN overlay at subnet creation; no per-VM call |

#### Single Attachment Resolution

- The list may contain zero or one entry at API input time; more than one is rejected.
- After default resolution, the sole entry is primary when `primary` is omitted or `true`.
- Explicit `primary: false` is rejected.

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-created: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

#### API Change

The ComputeInstance networking API changes from the shared
`NetworkAttachment` shape to the resource-specific
`ComputeNetworkAttachment` shape before release. Only
`network_attachments` is accepted. The previous shared field and
message are not exposed as a compatibility path because no users or persisted
resources depend on them yet.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent ComputeInstance
- No new authentication or authorization changes
- NetworkACL enforcement follows the [Unified Networking NetworkACL rule semantics](/enhancements/OSAC-1433-unified-networking/design.md#networkacl-rule-semantics) for explicit and default NetworkACLs.
- The VM's single network interface uses the same NetworkACL enforcement as the shared networking contract.

### Failure Handling and Recovery

#### ComputeInstance Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): ComputeInstance enters Failed state with condition, retries on Subnet status change
- Namespace resolution failure (subnet has no target namespace): ComputeInstance enters Failed state, retries after manual correction
- AAP job failure (template execution error): ComputeInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types))
- ExternalIP provisioning failure: ExternalIP enters Failed state, ComputeInstance remains in Pending (external access unavailable, VM may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach VM (VM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (ComputeInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance to auto-created resources
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected
- Tenant User can view auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via the standard API; their network-owned fields are not editable.

### Observability and Monitoring

New structured log events:
- ComputeInstance controller: `ResolvedPrimarySubnet` (info), `SubnetResolutionFailed` (error), `NetworkAttachmentCardinalityRejected` (error)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on ComputeInstance:
- `NetworkingResolved`: subnet → namespace resolution succeeded
- `NetworkingResolutionFailed`: subnet resolution failed (not found, not Ready, BM-only deployment)
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: k8s_manager implementation blocked or delayed

**Impact:** OSAC-1511 (CUDN) and OSAC-1717 (EVPN) are both in spike/blocked state. Without a k8s_manager, the Subnet controller cannot provision overlay networks, and VMaaS networking does not function.

**Mitigation:** Prioritize unblocking one of these dependencies. Accept that VMaaS remains unavailable until a k8s_manager exists. Document as a hard dependency.

**Reviewed by:** Engineering / Product

#### Risk: Multi-job tracking not implemented

**Impact:** OSAC-1459 is a prerequisite for Subnet controller to call both fabric_manager and k8s_manager. Without it, Subnet controller can only call one manager.

**Mitigation:** Defer multi-manager support or accept single-manager-only subnet provisioning. Document limitation.

**Reviewed by:** osac-operator team

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create VM with `auto_external_ip_attachment=true`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

### Drawbacks

#### API shape change

The resource-specific attachment message adds a small pre-release API change,
but removes dual-field validation and avoids a compatibility and migration
period before the API has users.

## Alternatives (Not Implemented)

### Alternative 1: Single shared NetworkAttachment message with optional primary field

Instead of creating `ComputeNetworkAttachment`, extend the shared `NetworkAttachment` message with an optional `primary` field usable by all resource types.

**Rejected because:** Other resource types (Cluster, BaremetalInstance) have different attachment semantics (CaaS needs separate API/ingress attachments, while BMaaS supports exactly one tenant network attachment on one physical NIC). Resource-specific attachment messages provide cleaner API surface and type-specific validation.

### Alternative 2: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed ComputeInstance with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.

## Open Questions

### ~~1. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity checked synchronously. No Failed resource.

## Test Plan

The executable, reviewable plan for VMaaS Networking is maintained in
[testplan.md](testplan.md). It covers the one-or-less interface contract,
attachment defaulting, provisioning and status, automatic ExternalIP behavior,
immutability, cleanup, Catalog parity, and unsupported behavior. Shared
networking contracts are covered by the [Unified Networking test
plan](../OSAC-1433-unified-networking/testplan.md).
## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachments`, `auto_external_ip_attachment`) implemented in fulfillment-service
- [ ] Operator CRD updated with `Primary` field and CEL validation
- [ ] Single-interface template support (`osac.templates.ocp_virt_vm`) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] Integration tests pass (E2E coverage for single-interface cardinality, auto ExternalIP)
- [ ] Documentation: API reference, user guide for simplified VM creation

GA criteria:
- [ ] k8s_manager implementation (OSAC-1511 or OSAC-1717) delivered and production-tested
- [ ] Multi-job tracking (OSAC-1459) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

The resource-specific attachment schema and its server and operator consumers
are deployed atomically. Because the API change occurs before users or
persisted resources exist, no dual-field compatibility period or client
migration is required.

### Downgrade

If `N+1` upgrade fails, downgrade across the attachment schema change is not
supported. The fulfillment-service and operator versions must be rolled back
as one unit before any ComputeInstance resources are created.

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

The CLI and fulfillment-service must be upgraded together with the
resource-specific attachment schema. Mixed client/server versions across this
pre-release API change are unsupported.

## Support Procedures

### Symptom: ComputeInstance stuck in Pending, condition "NetworkingResolutionFailed"

**Detection:**
```bash
kubectl describe computeinstance <name> -n <namespace>
# Check status.conditions for NetworkingResolutionFailed
```

**Cause:** Subnet not found, not Ready, or BM-only deployment (no k8s_manager)

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. If BM-only deployment, tenant must create VM in a deployment with k8s_manager configured

### Symptom: ComputeInstance has an invalid attachment cardinality

**Detection:** Create request is rejected with a single-interface validation error

**Cause:** The request supplied more than one entry, or set `primary: false` on the sole entry

**Resolution:**
1. Submit zero or one entry in `network_attachments`
2. Omit `primary` or set it to `true`; multi-interface placement is not supported yet

### Symptom: Auto-provisioned ExternalIP not cleaned up after ComputeInstance deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-created: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check ComputeInstance deletion logs (controller logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Disabling the feature

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running VMs

## Infrastructure Needed

- AAP execution environment with `osac.templates.ocp_virt_vm` role updated for the single resolved network attachment
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- Integration test environment with CUDN or EVPN fabric
