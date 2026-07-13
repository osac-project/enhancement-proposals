---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-07-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/unified-networking"
  - "Default Networking: /enhancements/default-networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# VMaaS Networking — Optional Attachments and Auto External Access

This enhancement extends the unified networking API to support VMaaS-specific requirements: multi-NIC ComputeInstance provisioning with a designated primary attachment, optional network attachments with tenant defaults, and auto-provisioned external access (ExternalIP).

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/unified-networking/design.md), providing the detailed per-service flow for this service type. The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how this specific service consumes that architecture.

ComputeInstance currently uses a shared `NetworkAttachment` message that lacks a `primary` field, preventing multi-NIC VM provisioning with a designated default gateway. This enhancement introduces `ComputeNetworkAttachment` with a `primary` field, makes the attachments field optional (populating with tenant defaults when omitted), and adds `auto_external_ip_attachment` to enable fully connected VMs in a single API call. See [PRD](prd.md) for detailed requirements.

## Motivation

ComputeInstance already participates in the networking API. Today's flow:

1. Tenant creates VirtualNetwork, Subnet, SecurityGroup via API
2. osac-operator's networking controllers reconcile each resource as a standalone AAP job, using `implementation_strategy` to select the Ansible role (e.g., `osac.templates.cudn_net.create_subnet`)
3. Tenant creates ComputeInstance with `network_attachments` (shared message, no `primary` field, single-NIC only)
4. osac-operator's ComputeInstance controller resolves subnet → namespace, triggers AAP job
5. AAP template (`osac.templates.ocp_virt_vm`) creates KubeVirt VirtualMachine with one `l2bridge` interface in the subnet's CUDN namespace

### What Already Works

- `network_attachments` field exists on ComputeInstanceSpec (field 14)
- Operator CRD has `NetworkAttachments []NetworkAttachment` with CEL immutability rules (subnet refs immutable, security group refs mutable)
- Subnet-to-namespace resolution is implemented
- The template creates VMs in the correct namespace
- ExternalIPAttachment with `compute_instance` target works end-to-end

### What's Missing

- Shared `NetworkAttachment` message — no `primary` field for multi-NIC
- No per-resource-type attachment message (`ComputeNetworkAttachment`)
- Single-NIC only — template creates one `l2bridge` interface
- No dispatcher — uses `implementation_strategy` annotation
- BM-only region validation (reject VM when no k8sManager)
- Auto ExternalIP allocation (tenant must manually create ExternalIP + ExternalIPAttachment)

### Goals

- Multi-NIC support with designated primary attachment for default gateway
- Resource-specific attachment message (`ComputeNetworkAttachment`) with `primary` field
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- BM-only region validation to reject VM provisioning when no k8s_manager is available

### Non-Goals

- CaaS or BMaaS networking (this EP covers VMaaS only)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- Kubernetes manager implementation (CUDN or EVPN fabric integration via k8s_manager roles)

## Proposal

### Workflow Description

#### Networking Setup (unchanged pattern, new dispatch mechanism)

1. **Tenant creates VirtualNetwork:**
   ```bash
   osac create virtualnetwork --region moc-region-1 --cidr 10.0.0.0/16 --name my-net
   ```
   - fulfillment-service → creates VirtualNetwork CR
   - osac-operator VirtualNetwork controller → dispatcher resolves NetworkClass → calls `osac.templates.{{ fabric_manager }}.create_virtual_network`
   - Fabric manager creates isolated tenant segment on the fabric

2. **Tenant creates Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   - osac-operator Subnet controller → dispatcher resolves NetworkClass → triggers TWO AAP jobs (multi-job tracking per OSAC-1459):
     - `osac.templates.{{ fabric_manager }}.create_subnet` — creates VLAN / fabric segment
     - `osac.templates.{{ k8s_manager }}.create_subnet` — creates CUDN overlay on each hosting cluster, bridges to the fabric segment
   - After both complete: subnet is Ready. The CUDN namespace is the deployment target for VMs.

3. **Tenant creates SecurityGroup:**
   ```bash
   osac create security-group --virtual-network my-net --name my-sg \
     --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
   ```
   - Dispatcher → `osac.templates.{{ fabric_manager }}.create_security_group`
   - Fabric manager creates ACL rules on the fabric

#### VM Creation

4. **Tenant creates ComputeInstance:**
   ```bash
   # Explicit networking:
   osac create computeinstance --template ocp_virt_vm \
     --network-attachment subnet=my-subnet,security-groups=my-sg \
     --name my-vm

   # Or with defaults + auto external access:
   osac create computeinstance --template ocp_virt_vm \
     --external-ip-attachment --name my-vm
   ```
   - fulfillment-service:
     - If `compute_network_attachments` omitted: populates with tenant's default Subnet + default SecurityGroup (see Default Networking PRD)
     - Validates: subnets exist, are Ready, same VN, primary rules
     - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity), creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
   - Creates ComputeInstance CR with `compute_network_attachments`

5. **osac-operator ComputeInstance controller:**

   a. `resolveNetworking` (existing logic, extended):
      - `PrimarySubnetRef()` → returns the primary attachment's subnet (explicit `primary: true`, or implicit if only one attachment)
      - `resolveSubnetTargetNamespace()` → looks up Subnet CR → namespace (same as today)
      - Stamps `osac.openshift.io/subnet-target-namespace` annotation
      - **No dispatcher call for network attachments** — VMs don't need switch port configuration. The k8sManager's work was done at subnet creation (step 2). The overlay already exists.

   b. Triggers AAP job: `osac-create-compute-instance`

6. **AAP template (`osac.templates.ocp_virt_vm`):**
   - Reads `subnet-target-namespace` → deployment namespace
   - Reads `compute_network_attachments`:
     - Single attachment (today's behavior): creates VM with one `l2bridge` interface in the subnet's CUDN namespace
     - Multiple attachments (NEW — multi-NIC): creates VM with multiple KubeVirt network/interface definitions, each referencing a different CUDN NAD. The `primary: true` attachment gets the default gateway.
   - Reads `securityGroupRefs` → adds as pod labels
   - Creates DataVolume + KubeVirt VirtualMachine
   - VM gets IP from each CUDN (via DHCP)
   - VM is on the fabric (overlay bridged at subnet creation)
   - **No networking logic** — template does OS/VM provisioning only. VMs join the fabric through the overlay, not through switch ports.

#### IP Discovery (feedback loop)

7. **osac-operator ComputeInstance feedback controller** discovers VM IPs:
   - Watches KubeVirt VMI (VirtualMachineInstance) network status
   - For each interface, reads the assigned IP from `vmi.status.interfaces[].ipAddress`
   - Maps each interface to the corresponding `compute_network_attachment` by CUDN NAD reference
   - Fires Signal RPC to fulfillment-service with per-attachment IP data
   - fulfillment-service writes `compute_network_attachment_statuses` on ComputeInstanceStatus (each entry: `subnet_ref`, `ip_address`, `primary`)
   - Tenant can inspect: `osac get computeinstance my-vm -o yaml` shows assigned IPs per attachment

#### External Access (optional, auto-provisioned when `auto_external_ip_attachment=true`)

8. **fulfillment-service creates ExternalIP and ExternalIPAttachment:**
   - Auto-selects ExternalIPPool (READY, most available capacity, matching IP family)
   - Creates ExternalIP from pool, labeled `osac.openshift.io/auto-provisioned: "true"` and `osac.openshift.io/auto-provisioned-for: <compute-instance-id>`
   - Creates ExternalIPAttachment binding ExternalIP to VM's primary subnet IP, labeled `osac.openshift.io/auto-provisioned: "true"`
   - Both start in **Pending** state. The ExternalIPAttachment controller checks two preconditions before dispatching (requeues if either is not met):
     1. ExternalIP must be Allocated (have an allocated address from the fabric manager)
     2. ComputeInstance must have `compute_network_attachment_statuses` populated with the primary attachment's `ip_address` (VM IP discovered from KubeVirt VMI)
   - Once both are met: dispatcher → `osac.templates.{{ fabric_manager }}.create_external_ip_attachment`
   - Fabric manager creates DNAT rule: external IP → VM's primary subnet IP (from `compute_network_attachment_statuses`)
   - ExternalIPAttachment transitions from Pending to Ready

#### Deletion (reverse order)

10. **Delete ComputeInstance:**
   - **Auto-provisioned cleanup:** If ExternalIP/ExternalIPAttachment were created by the system (`auto_external_ip_attachment=true`, labeled `osac.openshift.io/auto-provisioned: "true"`): parent finalizer deletes ExternalIPAttachment first, then ExternalIP.
   - **Manually created resources are NOT cleaned up** — if the tenant created ExternalIP/ExternalIPAttachment explicitly, they persist after the resource is deleted. The tenant manages their lifecycle.
   - **Default networking resources (VN, Subnet, SG) are NOT cleaned up** — they are tenant-scoped and shared across resources.
   - osac-operator triggers `osac-delete-compute-instance` AAP job
   - Template deletes KubeVirt VM + DataVolume
   - No `delete_network_attachment` call (VM was on overlay, not switch port)

11. **Delete networking resources:**
    - Each networking resource controller triggers its delete AAP job
    - Dispatcher calls the appropriate manager role for each

### API Extensions

#### Proto (fulfillment-service)

Replace the shared `NetworkAttachment` with `ComputeNetworkAttachment`:

```protobuf
message ComputeNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, mutable
  bool primary = 3;                     // immutable, designates default gateway
}

message ComputeInstanceSpec {
  // ... existing fields ...
  // DEPRECATED: field 14 (old shared NetworkAttachment)
  repeated ComputeNetworkAttachment compute_network_attachments = 18; // optional
  bool auto_external_ip_attachment = 19;  // NEW, auto-provision ExternalIP + ExternalIPAttachment
}

message ComputeNetworkAttachmentStatus {
  string subnet_ref = 1;               // Subnet ID (echoed from spec)
  string ip_address = 2;               // Discovered from KubeVirt VMI network status after DHCP/overlay assignment
  bool primary = 3;                     // Echoed from spec
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = N; // NEW
}
```

#### Operator CRD (osac-operator)

Update `ComputeInstanceSpec.NetworkAttachments` struct:
- Add `Primary bool` field with CEL immutability validation
- Add validation: if >1 attachment, exactly one must be `primary: true`
- `PrimarySubnetRef()` returns the attachment with `primary: true` (falls back to first attachment for backward compat)

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() > 1 ? self.networkAttachments.filter(x, x.primary == true).size() == 1 : true"
  message: "When multiple network attachments exist, exactly one must have primary: true"
```

Add `ComputeNetworkAttachmentStatus` to `ComputeInstanceStatus`:

```go
type ComputeInstanceStatus struct {
    // ... existing fields ...
    NetworkAttachmentStatuses []ComputeNetworkAttachmentStatus `json:"networkAttachmentStatuses,omitempty"`
}

type ComputeNetworkAttachmentStatus struct {
    SubnetRef string `json:"subnetRef"`
    IPAddress string `json:"ipAddress,omitempty"` // Discovered from KubeVirt VMI after DHCP/overlay assignment
    Primary   bool   `json:"primary,omitempty"`
}
```

The feedback controller populates `NetworkAttachmentStatuses` by watching the KubeVirt VMI `status.interfaces` and mapping each interface IP to the corresponding attachment by CUDN NAD reference.

#### Server Validation (fulfillment-service)

- During migration: accept both old field (14) and new field (18). If both set, reject. If old set, convert internally.
- Primary validation: if multiple attachments, exactly one primary
- BM-only region check: if region's NetworkClass has no k8sManager, reject ComputeInstance creation for that region

#### Template Changes (osac-aap)

- `osac.templates.ocp_virt_vm/tasks/create_build_spec.yaml`: support multiple KubeVirt network/interface definitions from `compute_network_attachments`
- Each attachment maps to a KubeVirt interface with `l2bridge` binding referencing the attachment's subnet's CUDN NAD
- Primary attachment: IP + default gateway + DNS (via DHCP)
- Non-primary: IP + connected route only (via DHCP)

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, auto-provision ExternalIP, write `compute_network_attachment_statuses` from feedback |
| osac-operator ComputeInstance controller | Resolve subnet → namespace, trigger AAP, clean up auto-provisioned resources |
| osac-operator ComputeInstance feedback controller | Watch KubeVirt VMI network status, discover per-attachment IPs, Signal fulfillment-service |
| osac-operator networking controllers | Dispatch to managers via dispatcher (VN, Subnet, SG, ExternalIP) |
| AAP template (ocp_virt_vm) | Create multi-NIC KubeVirt VM in correct namespace |
| fabric_manager (Ansible role) | VN/Subnet/SG/ExternalIP provisioning; no per-VM call |
| k8s_manager (Ansible role) | Create CUDN overlay at subnet creation; no per-VM call |

#### Primary Attachment Resolution

- Explicit: first attachment with `primary: true`
- Implicit: if only one attachment, treat as primary (no explicit flag required)
- Error: if >1 attachment and no `primary: true`, or >1 `primary: true`

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-provisioned: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

#### Backward Compatibility Strategy

Dual-field support during migration:
- Server accepts old `network_attachments` (field 14) or new `compute_network_attachments` (field 18)
- Reject if both set
- Internal conversion: old → new format (no `primary` on single attachment, implicit primary)
- Deprecation timeline: TBD (OSAC-1471)

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent ComputeInstance
- No new authentication or authorization changes
- SecurityGroup rules control VM inbound traffic (tenant-configurable via explicit SG or default SG)
- Multi-NIC VMs on different subnets share the same SecurityGroup enforcement (pod labels apply to all interfaces)

### Failure Handling and Recovery

#### ComputeInstance Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): ComputeInstance enters Failed state with condition, retries on Subnet status change
- Namespace resolution failure (subnet has no target namespace): ComputeInstance enters Failed state, retries after manual correction
- AAP job failure (template execution error): ComputeInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types))
- ExternalIP provisioning failure: ExternalIP enters Failed state, ComputeInstance remains in Pending (external access unavailable, VM may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach VM (VM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (ComputeInstance with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance to auto-created resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-provisioned: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- ComputeInstance controller: `ResolvedPrimarySubnet` (info), `SubnetResolutionFailed` (error), `MultiNICProvisioning` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on ComputeInstance:
- `NetworkingResolved`: subnet → namespace resolution succeeded
- `NetworkingResolutionFailed`: subnet resolution failed (not found, not Ready, BM-only region)
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

#### Dual-field migration complexity

Supporting both old `network_attachments` (field 14) and new `compute_network_attachments` (field 18) adds server validation complexity and migration burden. Tenants using the old field must eventually migrate.

**Trade-off:** Backward compatibility vs. clean API surface. Chosen approach: temporary dual-field support with documented migration timeline (OSAC-1471).

## Alternatives (Not Implemented)

### Alternative 1: Single shared NetworkAttachment message with optional primary field

Instead of creating `ComputeNetworkAttachment`, extend the shared `NetworkAttachment` message with an optional `primary` field usable by all resource types.

**Rejected because:** Other resource types (Cluster, BaremetalInstance) have different attachment semantics (CaaS needs separate API/ingress attachments, BMaaS has no multi-NIC concept). Resource-specific attachment messages provide cleaner API surface and type-specific validation.

### Alternative 2: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed ComputeInstance with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.

## Open Questions

### 1. Should capacity exhaustion return an API error or create a Failed resource?

Current proposal: return error, no resources persisted. Alternative: create Failed resource for audit trail.

**Owner:** API design team

**Impact:** Affects FR-4 and acceptance criteria.

## Test Plan

### Unit Tests

- fulfillment-service: primary validation (reject >1 primary, accept single implicit primary, accept explicit primary)
- fulfillment-service: dual-field validation (reject both old and new, convert old → new)
- fulfillment-service: BM-only region validation (reject VM when no k8s_manager)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator ComputeInstance controller: `PrimarySubnetRef()` resolution (explicit primary, implicit single-attachment)

### Integration Tests

- E2E: create ComputeInstance with multiple attachments, verify multi-NIC KubeVirt VM provisioned
- E2E: create ComputeInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance in BM-only region, verify error returned
- E2E: create ComputeInstance with old `network_attachments` field, verify backward compat (internal conversion)

### Tricky Test Cases

- Multi-NIC VM with primary on second attachment (verify default gateway on correct interface)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`compute_network_attachments`, `auto_external_ip_attachment`) implemented in fulfillment-service
- [ ] Operator CRD updated with `Primary` field and CEL validation
- [ ] Multi-NIC template support (`osac.templates.ocp_virt_vm`) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] Integration tests pass (E2E coverage for multi-NIC, auto ExternalIP)
- [ ] Documentation: API reference, user guide for simplified VM creation

GA criteria:
- [ ] k8s_manager implementation (OSAC-1511 or OSAC-1717) delivered and production-tested
- [ ] Multi-job tracking (OSAC-1459) implemented and stable
- [ ] Dual-field migration (OSAC-1471) completed, old `network_attachments` deprecated and removed
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`compute_network_attachments`, `auto_external_ip_attachment`) are additive — existing ComputeInstance resources continue to work with old `network_attachments` field (field 14)
- Server supports both old and new fields during migration (dual-field support)
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Deprecation warning added for old `network_attachments` field (field 14) in fulfillment-service API responses
- Tenant User encouraged to migrate to new field via CLI update (`osac-cli` supports new `--network-attachment` flag with `--primary`)
- No breaking changes — old field remains functional

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and osac-operator images to `N`
- Existing ComputeInstance resources with new `compute_network_attachments` field (field 18) will be unrecognized by `N` server
- Manual cleanup required: delete ComputeInstance resources created with new field, re-create with old field
- Auto-provisioned ExternalIP resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Delete CRs using new field (field 18)
- Re-create using old field (field 14)
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment labeled `osac.openshift.io/auto-provisioned: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI uses old `--network-attachments` flag → server accepts via dual-field support, converts internally
- New CLI uses new `--network-attachment` + `--primary` flags → server accepts new field

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses new `--network-attachment` flag → old server rejects unknown field
- Workaround: use old `--network-attachments` flag until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: ComputeInstance stuck in Pending, condition "NetworkingResolutionFailed"

**Detection:**
```bash
kubectl describe computeinstance <name> -n <namespace>
# Check status.conditions for NetworkingResolutionFailed
```

**Cause:** Subnet not found, not Ready, or BM-only region (no k8s_manager)

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. If BM-only region, tenant must create VM in a region with k8s_manager configured

### Symptom: Multi-NIC VM has no default gateway

**Detection:** VM cannot reach external networks, `ip route` shows no default route

**Cause:** Primary attachment not designated or incorrectly resolved

**Resolution:**
1. Check ComputeInstance spec: `kubectl get computeinstance <name> -n <namespace> -o yaml`
2. Verify exactly one `networkAttachments[].primary: true`
3. If missing or incorrect, delete and re-create ComputeInstance with correct `--primary` flag

### Symptom: Auto-provisioned ExternalIP not cleaned up after ComputeInstance deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` with no parent

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

- AAP execution environment with `osac.templates.ocp_virt_vm` role updated for multi-NIC support
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- Integration test environment with CUDN or EVPN fabric
