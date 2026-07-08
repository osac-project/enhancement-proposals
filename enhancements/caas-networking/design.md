---
title: caas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-07-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1436
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/unified-networking"
  - "Simplified Resource Creation: /enhancements/simplified-resource-creation"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking

## Summary

This enhancement describes the detailed design for integrating CaaS
(Cluster-as-a-Service) with the unified networking API. CaaS currently
handles all networking inline via step collections; this design moves
networking lifecycle to the OSAC Networking API and limits the CaaS
template to cluster provisioning and MetalLB VIP discovery. See
[PRD](prd.md) for requirements.

## Motivation

Cluster has no networking fields today. All networking — VLAN creation,
SNAT, DNAT, IP allocation, DNS, MetalLB — is handled inline by the CaaS
template via step collections (`netris.steps`, `agentless_net.steps`).
Tenants have zero control over which VirtualNetwork or Subnet their
cluster nodes use. The `NETWORK_STEPS_COLLECTION` env var selects the
entire networking backend deployment-wide. Step collections duplicate
functionality that should be in the networking API.

### Goals

- Clusters consume the unified networking API (VN, Subnet, SG, ExternalIP,
  NATGateway) the same way VMaaS and BMaaS do
- Operator handles agent selection and network attachment before
  provisioning (replaces template-side agent selection and networking)
- Step collections (cluster_infra, external_access) are removed
- CaaS is BM-only for v0.2; VM node sets are architecturally possible
  but deferred

### Non-Goals

- VM-based cluster node sets (HyperShift + CUDN integration deferred)
- DNS API (DNS records stay inline in the template)
- Dispatcher infrastructure (see OSAC-1440 under OSAC-1433)
- ExternalIPAttachment cluster target controller flows (see OSAC-1444)

## Proposal

### HostType and Interface Resolution

The HostType resource describes physical hardware with a structured
interface list. For CaaS, the fulfillment-service resolves the interface
automatically — the tenant does not specify interfaces.

Resolution chain:
1. `ClusterNetworkAttachment.node_set` = "gpu"
2. `ClusterSpec.node_sets["gpu"].host_type` = "acme_1tb_h100"
3. HostType has interfaces: `[{data-0, fabric}, {data-1, fabric}, {mgmt-0, management}]`
4. fulfillment-service picks first interface with role `fabric` → `data-0`
5. Stores as `fabric_interface` on the attachment

For v0.2: **CaaS supports BM node sets only.** VM node sets are deferred.
**One attachment per node set → one subnet → one interface.**

Interface roles: `fabric` (tenant workloads), `management` (control plane),
`storage` (storage fabric), `lifecycle` (PXE/BMC — not tenant-attachable).

### Proposed Flow

#### Phase 1: Tenant Creates Networking Resources

1. Create VirtualNetwork → dispatcher calls fabricManager
2. Create Subnet → dispatcher calls fabricManager + k8sManager
3. Create SecurityGroup → dispatcher calls fabricManager

#### Phase 2: Tenant Creates Cluster

4. Create Cluster (explicit or with defaults + auto external access):
   ```bash
   osac create cluster --template ocp_4_17_small \
     --network-attachment subnet=my-subnet,security-groups=my-sg \
     --node-set compute=large,size=3 --name my-cluster
   ```

5. fulfillment-service:
   - If network_attachments omitted: populates with tenant defaults
   - Validates: subnet Ready, SGs same VN, node_set refs valid
   - Resolves host_type → HostType → picks first fabric interface →
     stores as `fabric_interface`
   - If external_ip_mode == AUTO_ALL: creates ExternalIPs + Attachments
     (Pending) before ClusterOrder
   - If nat_gateway_mode == AUTO: creates NATGateway on VN
   - Creates ClusterOrder CR with enriched network_attachments

6. osac-operator ClusterOrder controller:
   - Creates namespace, SA, RoleBindings
   - reconcileAgentSelection: selects agents per node_set by host_type
   - reconcileNetworking: dispatcher calls create_network_attachment
     per agent (host_id, host_class, fabric_interface, subnet_ref)
   - Triggers AAP workflow

7. CaaS template (simplified):
   - Creates HostedCluster + NodePools referencing pre-selected agents
   - MetalLB VIP provisioning (LoadBalancer Services for API + ingress)
   - Writes VIPs to ClusterOrder status
   - DNS records (inline)
   - No agent selection, no switch port config

#### Phase 3: VIP Feedback Loop

8. Feedback controller sees VIPs → signals fulfillment-service
9. fulfillment-service syncs api_endpoint/ingress_endpoint to Cluster
10. ExternalIPAttachment controller reads VIP → creates DNAT → Ready
11. Same for ingress

#### Deletion

12. Delete Cluster:
    - Auto-provisioned cleanup (ExternalIPs, NATGateway if auto-created)
    - Manually created resources NOT cleaned up
    - Default resources (VN, Subnet, SG) NOT cleaned up
    - AAP delete workflow: MetalLB Services, HostedCluster, NodePools, DNS
    - reconcileNetworking (delete): delete_network_attachment per BM node

### API Extensions

```protobuf
message ClusterNetworkAttachment {
  string subnet = 1;
  repeated string security_groups = 2;
  string node_set = 3;
  string fabric_interface = 4;  // system-populated from HostType
}

message ClusterSpec {
  // ... existing fields ...
  repeated ClusterNetworkAttachment network_attachments = N;
  ClusterExternalIPMode external_ip_mode = M;
  NATGatewayMode nat_gateway_mode = P;
}

message ClusterStatus {
  // ... existing fields ...
  string api_endpoint = X;
  string ingress_endpoint = Y;
}
```

ClusterOrder CRD adds NetworkAttachments to spec, APIEndpoint +
IngressEndpoint to status. DB migration adds network_attachments (JSONB),
api_endpoint, ingress_endpoint columns.

### Implementation Details

#### What Changes vs. Today

Removed: cluster_infra dispatch, external_access dispatch,
NETWORK_STEPS_COLLECTION, step collections.

Added: ClusterNetworkAttachment, api/ingress endpoint fields, operator
agent selection + reconcileNetworking, MetalLB VIP provisioning in
template, VIP feedback loop, ExternalIPAttachment Pending→Ready.

Kept: HostedCluster + NodePool creation, DNS inline, kubeconfig
retrieval, wait for nodes + operators, AAP workflow structure.

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, resolve fabric_interface, create ClusterOrder, sync VIPs |
| osac-operator ClusterOrder controller | Namespace/SA/RoleBindings, agent selection, network attachment (dispatcher), trigger AAP |
| osac-operator feedback controller | Signal fulfillment-service when VIPs appear |
| osac-operator ExternalIPAttachment controller | Read api/ingress endpoint, create DNAT |
| AAP template | HostedCluster + NodePools, MetalLB VIPs, DNS — no agent selection or networking |
| fabric_manager role | create/delete_network_attachment, DNAT, SNAT |
| k8s_manager role | create/delete_subnet (CUDN overlay) — at subnet creation only |

### Security Considerations

Network attachment configuration inherits the existing tenant isolation
model. All subnets must belong to the same VirtualNetwork, which is
tenant-scoped. The `osac.openshift.io/tenant` annotation is enforced on
all networking resources.

### Failure Handling and Recovery

- If agent selection fails (no suitable agents): ClusterOrder stays in
  Progressing with a condition describing the failure
- If network attachment fails: ClusterOrder stays in Progressing, does
  not proceed to provisioning
- If VIP discovery fails: ExternalIPAttachments stay Pending indefinitely
- Auto-provisioned resource cleanup on deletion: if cleanup fails
  permanently, finalizer is removed and parent deleted — orphans remain

### RBAC / Tenancy

All new resources include `osac.openshift.io/tenant` and
`osac.openshift.io/owner-reference` annotations. ClusterNetworkAttachment
validation enforces tenant-scoped subnet and security group references.

### Observability and Monitoring

No new metrics beyond existing controller reconciliation metrics.
K8s events emitted for: agent selection complete, network attachment
complete, VIP discovery complete, ExternalIPAttachment activated.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Agent selection logic complexity | Reuse existing step collection logic, move to Go |
| Step collection removal breaks existing deployments | Feature-gated; existing flow preserved until gate enabled |
| VIP discovery timing | ExternalIPAttachment Pending state handles async discovery |

### Drawbacks

Moving agent selection from Ansible to the operator requires reimplementing
selection logic in Go. This is justified by the cleaner separation of
concerns and consistency with the BMaaS flow.

## Alternatives (Not Implemented)

**Keep step collections.** Template continues to handle all networking.
Rejected: duplicates networking API, no tenant control, inconsistent
with VMaaS/BMaaS.

**Template handles network_attachment calls.** Template calls
create_network_attachment inline. Rejected: template can't call it before
agent selection (circular dependency), and the operator model is
consistent with BMaaS.

## Open Questions

1. How does the operator select agents? K8s API for Agent CRs, or AAP job?
2. NMState NNCP config — stays in template or moves to operator?
3. MetalLB IPAddressPool — created at subnet time or cluster time?
4. Fabric manager name resolution — NetworkClass CR or env var?

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
| Multi-job tracking (subnet) | OSAC-1459 | New |
| NATGateway full stack | OSAC-1443 | 1/10 In Progress |
| ExternalIPAttachment cluster target CRD | OSAC-2041 | New |
| Cluster DNAT flow | OSAC-1495 | New |
| ClusterNetworkAttachment proto | OSAC-1501 | New |
| api/ingress endpoint on Cluster | OSAC-2040 | New |
| ClusterOrder CRD: network_attachments | OSAC-1505 | New |
| ClusterOrder CRD: api/ingress status | OSAC-2080 | New |
| VIP discovery flow | OSAC-1506 | New |
| CaaS template changes | OSAC-1507 | New |
| MetalLB VIP provisioning | OSAC-2077 | New |
| Cluster provisioning flow | OSAC-2049 | New |
| HostType NetworkInterface list | Not tracked | **GAP** |
| Remove step collections | Not tracked | **GAP** |
| Agent selection in operator | Not tracked | **GAP** |
| fabric_interface resolution | Not tracked | **GAP** |
