---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-29
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

This enhancement extends the unified networking API to support VMaaS-specific requirements: a single ComputeInstance network attachment with an implicit primary/default route, optional network attachments with tenant defaults, subnet-associated NetworkACL policy, and auto-provisioned external access (ExternalIP). The repeated attachment field is retained for API compatibility and is validated to contain at most one entry.

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

ComputeInstance currently uses a `ComputeNetworkAttachment` message. This enhancement keeps the existing repeated attachment field optional (populating its subnet from tenant defaults when omitted), enforces a maximum of one entry, applies the policy of the NetworkACL associated with that subnet, and adds `auto_external_ip_attachment` to enable fully connected VMs in a single API call. VMaaS has no primary field: the sole attachment is implicitly the default route. See [PRD](prd.md) for detailed requirements.

## Motivation

ComputeInstance already participates in the networking API. Today's flow:

1. Tenant creates VirtualNetwork and Subnet, and associates a NetworkACL with the Subnet via API
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
   - Wait until `VirtualNetwork.status.phase == "Ready"` before creating a NetworkACL or Subnet. This gate also applies when creating a Subnet without an ACL association.

2. **Tenant creates NetworkACL:**
   ```bash
   osac create network-acl --virtual-network my-net --name my-acl \
     --ingress-rule "action=ALLOW,protocol=TCP,ports=443,cidr=198.51.100.0/24" \
     --ingress-rule "action=ALLOW,protocol=TCP,ports=1024-65535,cidr=203.0.113.0/24" \
     --egress-rule "action=ALLOW,protocol=TCP,ports=443,cidr=203.0.113.0/24" \
     --egress-rule "action=ALLOW,protocol=TCP,ports=1024-65535,cidr=198.51.100.0/24"
   ```
   - NetworkACLs have no seeded rules. An ACL with empty ingress and egress lists contributes no matching decisions, so the required deployment default ACL action decides traffic. These example rules allow HTTPS from the illustrative client range and to the illustrative endpoint range and include explicit reverse-direction rules for replies. The higher destination-port ranges also permit new TCP connections from those peer CIDRs to ports in those ranges; a stateless ACL cannot distinguish replies from new connections. Restrict both peer CIDRs and port ranges to the intended trust boundary, and replace the documentation CIDRs with trusted deployment ranges. The reverse rules are needed to permit replies under a `DENY` fallback; with `PERMIT`, unmatched replies pass unless a matching reverse-direction `DENY` rule applies.
   - The NetworkACL has independent ingress and egress rules. Rules contain an allow or deny action, protocol, optional TCP/UDP destination port range, and IPv4 CIDR.
   - Rule precedence is derived from match specificity, not input order or action; the first matching rule decides the result, and unmatched traffic uses the required deployment default ACL action.
   - The ACL is stateless. Ingress and egress, including replies in the reverse direction, are evaluated independently. Under a `DENY` fallback, the reverse rules above permit response packets to their destination ephemeral ports; under `PERMIT`, unmatched replies pass unless a matching reverse-direction `DENY` rule applies.
   - Dispatcher → `osac.templates.{{ fabric_manager }}.create_network_acl`
   - NetworkACL rule lists are fixed at creation. Changing policy requires deleting and recreating the affected networking resources; workload attachments are also immutable.

3. **Tenant creates Subnet:**
   - If using `--network-acl`, first wait until
     `NetworkACL.status.phase == "Ready"`; the API rejects a non-READY ACL
     before persisting or provisioning the Subnet.
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 \
     --network-acl my-acl --name my-subnet
   ```
   - `Subnet.spec.network_acl` may be omitted or reference one READY NetworkACL in the same VirtualNetwork. An omitted reference remains unset and the deployment default ACL action applies where no rule matches. An ACL may be reused by other Subnets in that VirtualNetwork; any explicit association is immutable after Subnet creation.
   - osac-operator Subnet controller → dispatcher resolves NetworkClass → triggers TWO AAP jobs (multi-job tracking per OSAC-1459):
     - `osac.templates.{{ fabric_manager }}.create_subnet` — creates VLAN / fabric segment
     - `osac.templates.{{ k8s_manager }}.create_subnet` — creates CUDN overlay on each hosting cluster, bridges to the fabric segment
   - After subnet and ACL association are Ready: the CUDN namespace is the deployment target for VMs.

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
     - If `network_attachments` is omitted or empty: populates the sole attachment with the tenant's default Subnet (see Default Networking PRD)
     - If one attachment is supplied, defaults only a missing Subnet; supplied values are preserved
     - Validates: at most one attachment; the Subnet is Ready, including completion of any NetworkACL association. With the `cudn_evpn` manager, VM placement also requires that the parent VirtualNetwork has exactly one Subnet and that the target Subnet has a READY CUDN and an Active, non-terminating target Namespace, as defined in the OSAC-4291 design.
     - Any NetworkACL associated with the Subnet refines the deployment default policy for this VM and every other workload attached to the Subnet; if no ACL is associated, the deployment default action applies. ACL rules and the Subnet association are immutable after creation; changing them requires recreating the affected networking resources.
     - If `auto_external_ip_attachment == true`: selects a READY ExternalIPPool with the most available capacity, reserves capacity, and creates an ExternalIP in the same DB transaction as the ComputeInstance. The ExternalIP starts in **Pending** state. If the pool is exhausted, the API call fails and no resources are persisted. The ExternalIPAttachment is created only after the ExternalIP is Allocated and the ComputeInstance is READY. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioning-lifecycle-auto_external_ip_attachment).
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

8. **ExternalIP reconciliation:**
   - ExternalIP (created at step 4) is pushed to the hub cluster by the fulfillment-service reconciler
   - osac-operator ExternalIP controller dispatches to AAP → fabric manager allocates an address → ExternalIP transitions to **Allocated**
   - ExternalIP labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <compute-instance-id>`

9. **Deferred ExternalIPAttachment creation (fulfillment-service internal reconciler):**
   - Once ExternalIP is **Allocated** AND ComputeInstance is **Ready** (with `compute_network_attachment_statuses` populated): fulfillment-service internal reconciler creates ExternalIPAttachment, labeled `osac.openshift.io/auto-created: "true"`
   - This follows the standard creation readiness gate — no exceptions
   - osac-operator ExternalIPAttachment controller dispatches to AAP → fabric manager creates DNAT rule: external IP → VM's primary subnet IP (from `compute_network_attachment_statuses`)
   - ExternalIPAttachment transitions to **Ready**

#### Deletion (reverse order)

9. **Delete ComputeInstance:**
   - **Auto-provisioned cleanup:** If ExternalIP/ExternalIPAttachment were created by the system (`auto_external_ip_attachment=true`, labeled `osac.openshift.io/auto-created: "true"`): parent finalizer deletes ExternalIPAttachment first, then ExternalIP.
   - **Manually created ExternalIPAttachments block workload deletion** — the tenant must remove any active attachment targeting the ComputeInstance before deleting it. Other manually created ExternalIPs remain tenant-managed and are not cascade-deleted.
   - **Default networking resources (VirtualNetwork, Subnet, and NATGateway) are NOT cleaned up** — they are tenant-scoped and shared across resources.
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
  reserved 2; // Former attachment-level policy reference; policy is configured on Subnet
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
| osac-operator networking controllers | Dispatch VirtualNetwork, Subnet, NetworkACL, and ExternalIP operations; keep Subnet readiness gated on ACL association |
| AAP template (ocp_virt_vm) | Create single-NIC KubeVirt VM in correct namespace |
| fabric_manager (Ansible role) | VN/Subnet/NetworkACL/ExternalIP provisioning; no per-VM call |
| k8s_manager (Ansible role) | Create CUDN overlay at subnet creation; no per-VM call |

#### Primary Attachment Resolution

- The sole attachment is implicitly primary/default route
- More than one attachment is rejected

#### Auto-Provisioned Resource Lifecycle

- ExternalIP created at workload creation time (pool is Ready, creation readiness gate satisfied). ExternalIPAttachment created later by fulfillment-service internal reconciler (after ExternalIP Allocated + ComputeInstance Ready)
- Labeled `osac.openshift.io/auto-created: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

#### Backward Compatibility Strategy

The existing repeated `network_attachments` field is retained unchanged for API
compatibility. The server and operator validate that it contains at most one
entry; omitted and empty lists resolve to the tenant's default Subnet, while a
supplied single entry receives a default only for a missing Subnet. The
attachment carries no policy reference: the Subnet's `network_acl` association
controls traffic for every attached workload. The sole VM attachment is
implicitly primary/default, and changing its resolved Subnet requires deleting
and recreating the VM. NetworkACL rules and Subnet-to-ACL associations are
immutable after creation; changing policy requires recreating affected
networking resources and may require recreating dependent workloads.

### Security Considerations

This feature inherits the existing tenant isolation model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent ComputeInstance
- No new authentication or authorization changes
- Any NetworkACL associated with the VM's Subnet refines the deployment default policy for every workload on that Subnet; if no ACL is associated, the deployment default action applies. The ACL is not stored on the VM attachment
- Ingress and egress are evaluated independently using the shared match-specificity order; the first matching rule allows or denies traffic, and unmatched traffic uses the deployment default ACL action
- Return traffic is evaluated independently in the reverse direction. With a `DENY` deployment fallback, a matching reverse-direction `ALLOW` rule must win precedence to permit a reply; with `PERMIT`, unmatched replies pass unless a matching reverse-direction `DENY` rule applies.
- Same-Subnet traffic is not filtered by the Subnet NetworkACL. Cross-Subnet traffic must pass source-Subnet egress and destination-Subnet ingress policy

### Failure Handling and Recovery

#### ComputeInstance Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): the API rejects the create request with a `FailedPrecondition` error; the ComputeInstance is never created. See [Unified Networking — Creation Readiness Gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)
- Namespace resolution failure (subnet has no target namespace): ComputeInstance enters Failed state, retries after manual correction
- AAP job failure (template execution error): ComputeInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioning-lifecycle-auto_external_ip_attachment))
- ExternalIP provisioning failure: ExternalIP enters Failed state, ComputeInstance remains in Pending (external access unavailable, VM may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach VM (VM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (ComputeInstance with its existing fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance to auto-created resources
- OPA policies enforce tenant-scoped operations according to each resource API;
  networking resources use read/create/delete; NetworkACL rules and
  Subnet-to-ACL associations are immutable after creation. Supported
  non-network workload updates remain available
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via standard API

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
- fulfillment-service: omitted and partial attachment defaulting (an omitted Subnet resolves to the unassociated tenant default Subnet and uses the deployment default action; an explicitly selected Subnet may have an optional NetworkACL association that refines the deployment default policy for all workloads there)
- fulfillment-service: BM-only deployment validation (reject VM when no k8s_manager)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator ComputeInstance controller: `PrimarySubnetRef()` resolution (implicit single attachment)

### Integration Tests

- E2E: create ComputeInstance with two attachments, verify the API rejects the request
- E2E on `cudn_evpn`: reject VM placement unless the parent VirtualNetwork has exactly one Subnet and the target Subnet has a READY CUDN and Active, non-terminating Namespace
- E2E: create ComputeInstance with `--external-ip-attachment`, verify the ExternalIPAttachment is created only after the ExternalIP is Allocated and the ComputeInstance is READY, then verify DNAT is functional
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance in BM-only deployment, verify error returned
- E2E: create ComputeInstance with one `network_attachments` entry, verify it is used as the default route and any ACL associated with the Subnet refines the deployment default policy; otherwise the deployment default action governs unmatched traffic
- E2E: verify specificity-based matching, first-match allow/deny, both deployment fallback actions, unmatched replies under `PERMIT`, reverse-direction `ALLOW` rules under `DENY`, same-Subnet bypass, and independent source-egress/destination-ingress checks across Subnets

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
- The repeated `network_attachments` field remains wire-compatible for the Subnet-only attachment shape. Existing network policies must be mapped to NetworkACL rules on READY Subnets, including reverse-direction rules when needed to permit replies under the selected deployment fallback and matching rules.
- Tenants may need to recreate workloads when different policies require separate Subnets. Existing single-attachment resources remain usable after their Subnets have READY NetworkACL associations.

Minor version upgrades (`x.N → x.N+1`):
- The CLI and API continue using the existing `--network-attachment` flag and `network_attachments` field
- The single-attachment shape remains compatible after each workload's Subnet has a READY NetworkACL association. Workloads that need policy separation across Subnets require recreation.

### Downgrade

VMaaS rollback follows the coordinated procedure in the
[Unified Networking Downgrade section](/enhancements/OSAC-1433-unified-networking/design.md#downgrade).
After ACL cutover begins, rolling back only fulfillment-service or
osac-operator is unsupported. Freeze network and workload writes, restore the
pre-upgrade database, networking resources, NetworkClass configuration, and
workload attachment state with no ACL-only objects or Subnet associations,
then roll back the API and CRD schemas, fulfillment-service, osac-operator,
networking controllers, configured networking manager, and clients together.
If the pre-upgrade state cannot be restored, keep the ACL-aware release and
fix forward.

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

- AAP execution environment with `osac.templates.ocp_virt_vm` role updated for single-NIC support
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- Integration test environment with CUDN or EVPN fabric

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: respond @ design 0.11.3 - 2bd6607, workspace main @ 2293f9140 (3 behind origin/main)

> Context changed between revise and respond.
> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":3,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","respond","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
