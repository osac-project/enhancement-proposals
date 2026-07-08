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
  - "Simplified Resource Creation: /enhancements/simplified-resource-creation"
  - "BareMetal Instance API: /enhancements/baremetal-instance-api"
replaces:
  - N/A
superseded-by:
  - N/A
---

# BMaaS Networking

## Summary

This enhancement describes the detailed design for integrating BMaaS
(Bare-Metal-as-a-Service) with the unified networking API. BaremetalInstance
currently has no networking fields; this design adds
BareMetalNetworkAttachment with per-interface subnet mapping, operator-side
network attachment via the dispatcher, and IP address feedback for
ExternalIPAttachment DNAT. See [PRD](prd.md) for requirements.

## Motivation

BaremetalInstance has no networking fields today. The provisioning flow is
handled by the bare-metal-fulfillment-operator (separate from osac-operator),
which manages inventory assignment (Ironic/Metal3), AAP-based provisioning,
and power management. The osac-operator only has a feedback controller for
BM. There is no switch port configuration, no integration with the OSAC
Networking API, and no ExternalIPAttachment support for BM targets.

The `NetworkClass` field on BareMetalInstanceSpec (populated from inventory)
collides with the OSAC NetworkClass CRD name and should be renamed to
`NetworkFabricManager`.

### Goals

- BareMetalInstance consumes the unified networking API with per-interface
  subnet mapping via BareMetalNetworkAttachment
- Operator handles network attachment (switch port config) before
  provisioning via the dispatcher
- Tenants discover available interfaces via the HostType API
- Auto ExternalIP and NATGateway support
- IP address feedback for ExternalIPAttachment DNAT

### Non-Goals

- Dispatcher infrastructure (see OSAC-1440)
- ExternalIPAttachment BM target controller (see OSAC-1444)
- NIC bonding, VLAN trunking (basic per-interface attachment only)

## Proposal

### HostType and Interface Validation

The HostType resource lists physical interfaces for BM host types (empty
for VM). The tenant specifies interface names directly on
BareMetalNetworkAttachment, validated against the HostType's interface list.

Interface roles: `fabric` (tenant workloads), `management` (control plane),
`storage` (storage fabric), `lifecycle` (PXE/BMC — not tenant-attachable).

### Architecture: Two Operators on One CR

```
fulfillment-service → creates BaremetalInstance CR → hub cluster
                                                        │
    bare-metal-fulfillment-operator ────────────────────┤ (provisioning)
      - reconcileInventory (Ironic/Metal3)              │
      - reconcileNetworking (NEW — dispatcher)          │
      - reconcileProvisioning (AAP)                     │
      - reconcilePower (Ironic/Metal3)                  │
                                                        │
    osac-operator ──────────────────────────────────────┘ (feedback only)
      - BareMetalInstanceFeedbackReconciler
```

### Proposed Flow

#### Phase 1: Tenant Creates Networking Resources

1. Create VirtualNetwork → dispatcher calls fabricManager
2. Create Subnet → dispatcher calls fabricManager (+ k8sManager if region
   hosts VMs)
3. Create SecurityGroup → dispatcher calls fabricManager

#### Phase 2: Tenant Creates BM Server

4. Create BaremetalInstance (explicit or with defaults + auto external
   access):
   ```bash
   osac create baremetalinstance --template bcm_h100 \
     --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
     --external-ip=auto --name my-server
   ```

5. fulfillment-service:
   - If network_attachments omitted: populates with tenant defaults
   - Validates: subnets Ready, same VN, interface valid from HostType,
     no duplicate interfaces, primary rules
   - If external_ip_mode == AUTO: creates ExternalIP + Attachment
   - If nat_gateway_mode == AUTO: creates NATGateway on VN
   - Creates BaremetalInstance CR with network_attachments

6. bare-metal-fulfillment-operator:
   - reconcileInventory: FindFreeHost → AssignHost (unchanged)
   - reconcileNetworking (NEW): dispatcher calls
     create_network_attachment per interface (host_id, host_class,
     interface, subnet_ref). Fabric manager adds server interface to
     subnet's fabric segment. Must be Ready before provisioning.
   - reconcileProvisioning: AAP job for OS install (unchanged, no
     networking logic in template)
   - reconcilePower: unchanged

7. osac-operator feedback controller: unchanged

#### Phase 3: External Access (optional)

8. Create ExternalIP → fabricManager allocates from IPAM
9. Create ExternalIPAttachment → reads BM primary subnet IP → DNAT

#### Phase 4: Outbound NAT (optional)

10. Create NATGateway → fabricManager creates SNAT rule

#### Deletion

11. Delete BaremetalInstance:
    - Auto-provisioned cleanup (ExternalIP/Attachment if AUTO)
    - Manually created resources NOT cleaned up
    - Default resources (VN, Subnet, SG) NOT cleaned up
    - reconcileDeprovisioning: AAP delete job for OS teardown
    - reconcileNetworking (delete): delete_network_attachment per
      interface — removes server from fabric segments
    - reconcileInventory deletion: UnassignHost
    - Feedback controller: final Signal

12. Tenant deletes networking resources independently

### API Extensions

```protobuf
message BareMetalNetworkAttachment {
  string subnet = 1;                    // required, immutable
  repeated string security_groups = 2;  // mutable
  string interface = 3;                 // from HostType, immutable
  bool primary = 4;                     // immutable, default gateway
}

message BareMetalInstanceSpec {
  // ... existing fields ...
  repeated BareMetalNetworkAttachment network_attachments = 8;
  ExternalIPMode external_ip_mode = 9;
  NATGatewayMode nat_gateway_mode = 10;
}
```

Operator CRD (bare-metal-fulfillment-operator) adds
NetworkAttachments with CEL immutability. mutateBMI copies
network_attachments from proto to K8s CR.

### Implementation Details

#### IP Address Feedback

After switch port config, the BM server gets an IP. The
ExternalIPAttachment controller needs this IP for DNAT.

**Recommended (Option A):** The create_network_attachment role writes the
allocated IP to the BaremetalInstance CR status. The feedback controller
syncs it to the fulfillment-service. The ExternalIPAttachment controller
reads the primary IP from the BM's status.

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, copy to K8s CR via mutateBMI |
| bare-metal-fulfillment-operator | Inventory, networking (dispatcher), OS provisioning (AAP), power |
| AAP BM template | OS provisioning only — no networking |
| osac-operator feedback controller | Signal on status changes |
| osac-operator ExternalIPAttachment controller | Read BM primary IP, create DNAT |
| fabric_manager role (create_network_attachment) | Resolve host → fabric server, add interface to subnet segment, allocate IP |
| fabric_manager role (delete_network_attachment) | Remove interface from segment, release IP |

#### Server Validation Rules

- All subnets must belong to the same VirtualNetwork
- No duplicate interfaces
- Interface must exist in HostType's NetworkInterface list
- If >1 attachment, each must have explicit interface
- Number of attachments ≤ number of available interfaces
- If multiple attachments, exactly one primary
- If single attachment, primary is implicit
- network_attachments are immutable after creation

### Security Considerations

Inherits the existing tenant isolation model. Network attachments are
validated against tenant-scoped subnets and security groups.

### Failure Handling and Recovery

- If network attachment fails: BM stays in Progressing, does not proceed
  to OS provisioning
- If IP address feedback fails: ExternalIPAttachment stays Pending
- Auto-cleanup on deletion: if cleanup fails, finalizer removed, orphans
  remain

### RBAC / Tenancy

All resources include `osac.openshift.io/tenant` and
`osac.openshift.io/owner-reference` annotations.

### Observability and Monitoring

K8s events for: network attachment complete, IP address assigned,
deprovisioning complete.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| IP feedback mechanism complexity | Option A (CR status) is simplest |
| Two-operator coordination | Existing finalizer-based coordination unchanged |
| NetworkClass naming collision | Rename to NetworkFabricManager |

### Drawbacks

The bare-metal-fulfillment-operator needs access to the dispatcher
resolution utility (imported from osac-operator/pkg/). This coupling
already exists for the provisioning lifecycle.

## Alternatives (Not Implemented)

**Template handles networking inline.** BM provisioning template calls
create_network_attachment. Rejected: ordering concerns (switch ports
must be configured before PXE boot), consistency with CaaS model.

**osac-operator handles BM networking.** Add a provisioning controller
in osac-operator for BM networking. Rejected: the bare-metal-fulfillment-
operator already manages the BM lifecycle; adding networking there keeps
the flow in one operator.

## Open Questions

1. IP address feedback: Option A (recommended), B, or C?

## Test Plan

*To be completed when targeted at a release.*

## Graduation Criteria

*To be completed when targeted at a release.*

## Upgrade / Downgrade Strategy

*To be completed when targeted at a release.*

## Version Skew Strategy

*To be completed when targeted at a release.*

## Support Procedures

*To be completed when targeted at a release.*

## Infrastructure Needed

No additional infrastructure beyond existing OSAC components.

## Dependencies

| Dependency | Jira | Status |
|-----------|------|--------|
| Dispatcher core | OSAC-1457, OSAC-1458, OSAC-1460 | In Progress |
| NATGateway full stack | OSAC-1443 | 1/10 In Progress |
| ExternalIPAttachment BM target CRD | OSAC-2041 | New |
| BM DNAT flow | OSAC-1496 | New |
| BareMetalNetworkAttachment proto | OSAC-1508 | New |
| Primary field | OSAC-2042 | New |
| Validation | OSAC-1509 | New |
| CLI --network-attachment | OSAC-2075 | New |
| BM provisioning flow | OSAC-2047 | New |
| Netris create/delete_network_attachment | OSAC-2081 | New |
| BareMetalInstance CRD: NetworkAttachments | Not tracked | **GAP** |
| mutateBMI: copy network_attachments | Not tracked | **GAP** |
| IP address feedback | Not tracked | **GAP** |
| Rename networkClass → networkFabricManager | Not tracked | **GAP** |
| HostType: NetworkInterface list | Not tracked | **GAP** |
