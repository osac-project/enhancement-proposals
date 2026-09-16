---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-16
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

# VMaaS Networking — Optional Attachments and Auto External Access

This enhancement extends the unified networking API to support VMaaS-specific requirements: a single ComputeInstance network attachment with an implicit primary/default route, optional network attachments with tenant defaults, and auto-provisioned external access (ExternalIP). The repeated attachment field is retained for API compatibility and is validated to contain at most one entry.

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md), providing the detailed per-service flow for this service type. The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how this specific service consumes that architecture.

VMaaS inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary):
VM networking supports connected deployments only and does not add air-gapped
or disconnected networking support.

VMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

ComputeInstance currently uses a `ComputeNetworkAttachment` message. This enhancement keeps the existing repeated attachment field optional (populating it with tenant defaults when omitted), enforces a maximum of one entry, and adds `auto_external_ip_attachment` to enable fully connected VMs in a single API call. VMaaS has no primary field: the sole attachment is implicitly the default route. See [PRD](prd.md) for detailed requirements.

## Motivation

ComputeInstance already participates in the networking API. Today's flow:

1. Tenant creates VirtualNetwork, Subnet, SecurityGroup via API
2. osac-operator's networking controllers reconcile each resource as a standalone AAP job, using `implementation_strategy` to select the Ansible role (e.g., `osac.templates.cudn_net.create_subnet`)
3. Tenant creates ComputeInstance with `network_attachments` (`ComputeNetworkAttachment`, no `primary` field, single-NIC only)
4. osac-operator's ComputeInstance controller resolves subnet → namespace, triggers AAP job
5. AAP template (`osac.templates.ocp_virt_vm`) creates KubeVirt VirtualMachine with one `l2bridge` interface in the subnet's CUDN namespace

### What Already Works

- `network_attachments` field exists on ComputeInstanceSpec (field 14)
- Operator CRD has `NetworkAttachments []ComputeNetworkAttachment` with CEL cardinality and immutability rules; the complete resolved attachment is immutable
- Subnet-to-namespace resolution is implemented
- The template creates VMs in the correct namespace
- ExternalIPAttachment with `compute_instance` target works end-to-end

### What's Missing

- Existing `ComputeNetworkAttachment` has no `primary` field; the compatibility field remains single-attachment only
- Service-level maximum-one validation and field-level defaulting are still required
- At most one attachment — template creates one `l2bridge` interface
- No dispatcher — uses `implementation_strategy` annotation
- BM-only deployment validation (reject VM when no k8sManager)
- Auto ExternalIP allocation (tenant must manually create ExternalIP + ExternalIPAttachment)

### Goals

- Single-NIC support with an implicit primary attachment for the default gateway
- Resource-specific attachment message (`ComputeNetworkAttachment`); the sole attachment is implicitly primary
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
   osac create virtualnetwork --network-class moc-bm-virt --cidr 10.0.0.0/16 --name my-net
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
     - If `network_attachments` is omitted or empty: populates the sole attachment with the tenant's default Subnet and default SecurityGroup (see Default Networking PRD)
     - If one attachment is supplied, defaults only missing fields: a missing Subnet receives the tenant default Subnet, and a missing or empty SecurityGroup list receives the tenant default SecurityGroup only when the resolved Subnet belongs to the tenant's default VirtualNetwork; otherwise the caller must provide SecurityGroups from the resolved Subnet's VirtualNetwork; supplied values are preserved
     - Validates: at most one attachment; the subnet is Ready and the security groups belong to the same VN
     - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity), creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow.
   - Creates ComputeInstance CR with `network_attachments`

5. **osac-operator ComputeInstance controller:**

   a. `resolveNetworking` (existing logic, extended):
      - `PrimarySubnetRef()` → returns the sole attachment's subnet
      - `resolveSubnetTargetNamespace()` → looks up Subnet CR → namespace (same as today)
      - Stamps `osac.openshift.io/subnet-target-namespace` annotation
      - **No dispatcher call for network attachments** — VMs don't need switch port configuration. The k8sManager's work was done at subnet creation (step 2). The overlay already exists.

   b. Triggers AAP job: `osac-create-compute-instance`

6. **AAP template (`osac.templates.ocp_virt_vm`):**
   - Reads `subnet-target-namespace` → deployment namespace
   - Reads `network_attachments`:
     - With one attachment: creates VM with one `l2bridge` interface in the subnet's CUDN namespace. That attachment gets the default gateway.
   - Reads `securityGroupRefs` → adds as pod labels
   - Creates DataVolume + KubeVirt VirtualMachine
   - VM gets IP from each CUDN (via DHCP)
   - VM is on the fabric (overlay bridged at subnet creation)
   - **No networking logic** — template does OS/VM provisioning only. VMs join the fabric through the overlay, not through switch ports.

#### IP Discovery (feedback loop)

7. **osac-operator ComputeInstance feedback controller** discovers VM IPs:
   - Watches KubeVirt VMI (VirtualMachineInstance) network status
   - Reads the assigned IP from the VM's sole `vmi.status.interfaces[].ipAddress`
   - Maps the interface to the corresponding `compute_network_attachment` by CUDN NAD reference
   - Fires Signal RPC to fulfillment-service with per-attachment IP data
   - fulfillment-service writes `compute_network_attachment_statuses` on ComputeInstanceStatus (each entry: `subnet_ref`, `ip_address`)
   - Tenant can inspect: `osac get computeinstance my-vm -o yaml` shows the assigned IP for the attachment

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

9. **Delete ComputeInstance:**
   - **Auto-provisioned cleanup:** If ExternalIP/ExternalIPAttachment were created by the system (`auto_external_ip_attachment=true`, labeled `osac.openshift.io/auto-provisioned: "true"`): parent finalizer deletes ExternalIPAttachment first, then ExternalIP.
   - **Manually created resources are NOT cleaned up** — if the tenant created ExternalIP/ExternalIPAttachment explicitly, they persist after the resource is deleted. The tenant manages their lifecycle.
   - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — they are tenant-scoped and shared across resources.
   - osac-operator triggers `osac-delete-compute-instance` AAP job
   - Template deletes KubeVirt VM + DataVolume
   - No `move_network_attachment` call — the VM lives on the CUDN overlay, not a fabric switch port, so it is never parked or port-moved (the port-move primitive and parking apply only to fabric-attached BM servers and CaaS agents)

10. **Delete networking resources:**
    - Each networking resource controller triggers its delete AAP job
    - Dispatcher calls the appropriate manager role for each

### API Extensions

#### Proto (fulfillment-service)

Use the existing `ComputeNetworkAttachment` field with a single-entry limit:

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
}

message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 14; // optional; max 1
  optional bool auto_external_ip_attachment = 18;  // auto-provision ExternalIP + ExternalIPAttachment
}

message ComputeNetworkAttachmentStatus {
  string subnet_ref = 1;               // Subnet ID (echoed from spec)
  string ip_address = 2;               // Discovered from KubeVirt VMI network status after DHCP/overlay assignment
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = N; // NEW
}
```

#### Operator CRD (osac-operator)

Update `ComputeInstanceSpec.NetworkAttachments` struct:
- Add validation that the repeated field contains at most one attachment
- `PrimarySubnetRef()` returns the sole attachment (or no subnet when the list is empty)

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() <= 1"
  message: "at most one network attachment is supported"
```

Add `ComputeNetworkAttachmentStatus` to `ComputeInstanceStatus`:

```go
type ComputeInstanceStatus struct {
    // ... existing fields ...
    ComputeNetworkAttachmentStatuses []ComputeNetworkAttachmentStatus `json:"computeNetworkAttachmentStatuses,omitempty"`
}

type ComputeNetworkAttachmentStatus struct {
    SubnetRef string `json:"subnetRef"`
    IPAddress string `json:"ipAddress,omitempty"` // Discovered from KubeVirt VMI after DHCP/overlay assignment
}
```

The feedback controller populates `ComputeNetworkAttachmentStatuses` by watching the KubeVirt VMI `status.interfaces` and mapping each interface IP to the corresponding attachment by CUDN NAD reference.

#### Server Validation (fulfillment-service)

- Validate that `network_attachments` contains at most one entry.
- Primary/default-route resolution: the sole attachment is implicitly primary; VMaaS has no primary field
- BM-only deployment check: if the NetworkClass has no k8sManager, reject ComputeInstance creation

#### Template Changes (osac-aap)

- `osac.templates.ocp_virt_vm/tasks/create_build_spec.yaml`: create one KubeVirt network/interface definition from `network_attachments`
- The attachment maps to a KubeVirt interface with `l2bridge` binding referencing the subnet's CUDN NAD
- The sole attachment receives IP + default gateway + DNS via DHCP

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, auto-provision ExternalIP, write `compute_network_attachment_statuses` from feedback |
| osac-operator ComputeInstance controller | Resolve subnet → namespace, trigger AAP, clean up auto-provisioned resources |
| osac-operator ComputeInstance feedback controller | Watch KubeVirt VMI network status, discover per-attachment IPs, Signal fulfillment-service |
| osac-operator networking controllers | Dispatch to managers via dispatcher (VN, Subnet, SG, ExternalIP) |
| AAP template (ocp_virt_vm) | Create single-NIC KubeVirt VM in correct namespace |
| fabric_manager (Ansible role) | VN/Subnet/SG/ExternalIP provisioning; no per-VM call |
| k8s_manager (Ansible role) | Create CUDN overlay at subnet creation; no per-VM call |

#### Primary Attachment Resolution

- The sole attachment is implicitly primary/default route
- More than one attachment is rejected

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-provisioned: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

#### Backward Compatibility Strategy

The existing repeated `network_attachments` field is retained unchanged for API
compatibility. The server and operator validate that it contains at most one
entry; omitted and empty lists invoke default resolution, while a supplied
single entry receives defaults only for missing fields. No new singular field or
dual-field migration is required. The sole VM attachment is implicitly
primary/default, and changing any resolved attachment field requires deleting
and recreating the VM.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent ComputeInstance
- No new authentication or authorization changes
- SecurityGroup rules control VM inbound traffic (tenant-configurable via explicit SG or default SG)
- The sole VM attachment uses the same SecurityGroup enforcement as the rest of the fabric

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

No RBAC or tenancy changes. All new resources (ComputeInstance with its existing fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance to auto-created resources
- OPA policies enforce tenant-scoped operations according to each resource API;
  networking resources use create/list/get/delete and do not expose
  update/patch, while supported non-network workload updates remain available
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-provisioned: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- ComputeInstance controller: `ResolvedPrimarySubnet` (info), `SubnetResolutionFailed` (error), `MultiNICProvisioning` (info)
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

#### Single-attachment compatibility constraint

The repeated `network_attachments` field remains in place to avoid an API
shape change. New requests containing more than one entry are rejected by
validation.

## Alternatives (Not Implemented)

### Alternative 1: Single shared NetworkAttachment message with optional primary field

Instead of creating `ComputeNetworkAttachment`, extend the shared `NetworkAttachment` message with an optional `primary` field usable by all resource types.

**Rejected because:** Other resource types (Cluster, BaremetalInstance) have different attachment semantics. Resource-specific attachment messages provide cleaner API surface and type-specific validation; all current workload types enforce a single tenant attachment.

### Alternative 2: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed ComputeInstance with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.

## Open Questions

### ~~1. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity checked synchronously. No Failed resource.

## Test Plan

### Unit Tests

- fulfillment-service: max-one validation (accept no attachment or one attachment)
- fulfillment-service: max-one `network_attachments` validation
- fulfillment-service: omitted and partial attachment defaulting (empty `security_groups` is missing; supplied values are preserved; a missing group list defaults only for the tenant default VirtualNetwork and is rejected for a non-default subnet without caller-supplied groups)
- fulfillment-service: BM-only deployment validation (reject VM when no k8s_manager)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator ComputeInstance controller: `PrimarySubnetRef()` resolution (implicit single attachment)

### Integration Tests

- E2E: create ComputeInstance with two attachments, verify the API rejects the request
- E2E: create ComputeInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance in BM-only deployment, verify error returned
- E2E: create ComputeInstance with one `network_attachments` entry, verify it is used as the default route

### Tricky Test Cases

- ComputeInstance with one attachment (verify implicit default-route behavior)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachments`, `auto_external_ip_attachment`) implemented in fulfillment-service
- [ ] Operator CRD updated with max-one CEL validation
- [ ] Single-NIC template support (`osac.templates.ocp_virt_vm`) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] Integration tests pass (E2E coverage for max-one validation, auto ExternalIP)
- [ ] Documentation: API reference, user guide for simplified VM creation

GA criteria:
- [ ] k8s_manager implementation (OSAC-1511 or OSAC-1717) delivered and production-tested
- [ ] Multi-job tracking (OSAC-1459) implemented and stable
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- The repeated `network_attachments` field remains wire-compatible, with validation limiting new requests to one entry
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- The CLI and API continue using the existing `--network-attachment` flag and `network_attachments` field
- No breaking changes — existing single-attachment resources remain functional

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and osac-operator images to `N`
- Auto-provisioned ExternalIP resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment labeled `osac.openshift.io/auto-provisioned: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- The CLI uses the existing single `--network-attachment` flag and sends the existing `network_attachments` field

osac-cli (n) with fulfillment-service (n-1):
- The CLI remains compatible with the existing `network_attachments` field; a second attachment is rejected client-side and server-side

Recommendation: keep osac-cli and fulfillment-service within one minor version.

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

### Symptom: VM has no default gateway

**Detection:** VM cannot reach external networks, `ip route` shows no default route

**Cause:** The sole attachment was not resolved or the subnet did not provide DHCP gateway information

**Resolution:**
1. Check ComputeInstance spec: `kubectl get computeinstance <name> -n <namespace> -o yaml`
2. Verify the single `networkAttachments[]` entry resolves to the intended subnet
3. If missing or incorrect, delete and re-create ComputeInstance with the intended subnet

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

- AAP execution environment with `osac.templates.ocp_virt_vm` role updated for single-NIC support
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- Integration test environment with CUDN or EVPN fabric
