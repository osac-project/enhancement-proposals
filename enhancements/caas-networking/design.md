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
  - "Default Networking: /enhancements/default-networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking — Cluster Networking via OSAC Networking API

This enhancement extends the unified networking API to support CaaS-specific requirements: tenant-controlled cluster node networking via VirtualNetwork + Subnet attachments, BM-based node sets with fabric interface resolution, MetalLB VIP provisioning, and auto-provisioned external access (ExternalIP + NATGateway) for cluster API and ingress endpoints.

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/unified-networking/design.md), providing the detailed per-service flow for this service type. The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how this specific service consumes that architecture.

Cluster provisioning currently uses inline networking logic in the CaaS template — all VLAN creation, SNAT, DNAT, IP allocation, DNS, and MetalLB configuration happens in step collections with zero tenant control. This enhancement moves networking lifecycle to the OSAC Networking API, enables tenants to place clusters on shared or isolated VirtualNetworks, and introduces a VIP feedback loop for cluster API/ingress endpoints to enable auto-provisioned external access. See [PRD](prd.md) for detailed requirements.

## Motivation

Cluster provisioning today follows this flow:

1. Tenant creates Cluster with template + node_sets + pull_secret (no networking parameters)
2. fulfillment-service creates ClusterOrder CR
3. osac-operator ClusterOrder controller triggers AAP workflow
4. AAP workflow calls the CaaS template which dispatches to `{{ network_steps_collection }}.cluster_infra` and `{{ network_steps_collection }}.external_access`:
   - **Netris**: selects agents, creates server cluster, allocates NAT IP, creates SNAT/DNAT, DNS, MetalLB
   - **agentless_net**: allocates VLAN, configures switch ports, creates L3 router namespace, SNAT, DNAT, DNS, MetalLB

### What Already Works

- HyperShift HostedCluster + NodePool creation works
- ClusterOrder CR exists with spec/status fields
- AAP workflow integration (`osac-create-hosted-cluster-workflow`) works
- Step collections (`netris.steps`, `agentless_net.steps`) provision working networking

### What's Missing

- CaaS template does ALL networking — none goes through the OSAC Networking API
- Tenants have no control over which VirtualNetwork or Subnet their cluster nodes use
- Tenants cannot place two clusters in the same VN or isolate them in separate VNs
- `network_steps_collection` env var selects the ENTIRE networking backend deployment-wide
- Step collections duplicate functionality that should be in the networking API
- No VIP feedback loop (cluster VIPs are provisioned in the template but not synced to fulfillment-service)
- No auto external access (tenant must manually create ExternalIP + ExternalIPAttachment for API/ingress)

### Goals

- Move cluster networking lifecycle to the OSAC Networking API (VirtualNetwork, Subnet, SecurityGroup)
- Tenant-controlled cluster node subnet placement via `network_attachment` field on ClusterSpec
- BM-based node sets with fabric interface resolution from HostType
- VIP feedback loop: template provisions MetalLB VIPs → ClusterOrder status → fulfillment-service → Cluster → ExternalIPAttachment controller
- Auto ExternalIP mode (`external_ip_mode: AUTO_ALL`) for single-call API/ingress external access
- Auto NATGateway mode (`nat_gateway_mode: AUTO`) for single-call outbound connectivity
- Remove step collections (`netris.steps`, `agentless_net.steps`) from CaaS networking

### Agent Pool Model

The current assumption is that **pre-booted Assisted Installer agents** are ready in a pool, waiting to be assigned to clusters. These agents sit on a **parking network** — a fabric-manager-managed V-Net that provides basic connectivity (DHCP, PXE, management access) while agents are idle.

When an agent is selected for a cluster:
1. The agent's port is **moved from the parking network to the tenant's subnet V-Net** (via `create_network_attachment`)
2. The agent receives a new IP from the tenant subnet's DHCP server
3. After cluster deletion, the agent's port is **returned to the parking network** (via `delete_network_attachment`)

This differs from BMaaS, where servers start with no network attachment and are placed directly on the tenant V-Net. For CaaS, the `create_network_attachment` role must handle the transition: check if the port is already on a network (parking V-Net), remove it, then add to the target V-Net. The `delete_network_attachment` role reverses this: remove from tenant V-Net, return to parking V-Net.

**Generic role behavior:** The `create_network_attachment` role works identically for both CaaS and BMaaS by always checking if the given port is already part of a V-Net. If yes, remove it first. Then add to the target V-Net. This means:
- **CaaS:** agent on parking V-Net → remove from parking → add to tenant V-Net
- **BMaaS:** server not on any V-Net → nothing to remove → add to tenant V-Net

**Future consideration:** The agent pool model may evolve toward on-demand agent booting during cluster provisioning (no pre-booted pool). The design should accommodate this by not assuming agents are pre-existing — the `reconcileAgentSelection` step abstracts agent discovery, and the networking flow works regardless of whether the agent was pre-booted or just provisioned.

### Non-Goals

- VMaaS or BMaaS networking (this EP covers CaaS only)
- VM-based cluster node sets (v0.2 supports BM node sets only; VM worker nodes require HyperShift ↔ CUDN integration not in scope)
- DNS API (DNS record creation stays inline in the template until DNS API is implemented)
- Multi-NIC cluster nodes (v0.2: one attachment per cluster → one subnet; each node set resolves its own fabric interface from its HostType)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)
- On-demand agent booting (v0.2 assumes pre-booted agent pool; may change in future)

## Proposal

### Workflow Description

#### Phase 1: Tenant Creates Networking Resources

These steps are identical to VMaaS/BMaaS — the networking API is uniform.

1. **Create VirtualNetwork:**
   ```bash
   osac create virtualnetwork --region moc-region-1 --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_virtual_network`

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → TWO jobs: fabric_manager creates VLAN/fabric segment + k8s_manager creates CUDN overlay (if region hosts VMs)

3. **Create SecurityGroup:**
   ```bash
   osac create security-group --virtual-network my-net --name my-sg \
     --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_security_group`

#### Phase 2: Tenant Creates Cluster

4. **Create Cluster:**
    ```bash
    # Explicit networking:
    osac create cluster --template ocp_4_17_small \
      --network-attachment subnet=my-subnet,security-groups=my-sg \
      --node-set compute=large,size=3 --name my-cluster

    # Or with defaults + auto external access:
    osac create cluster --template ocp_4_17_small \
      --external-ip=auto-all --nat-gateway=auto \
      --node-set compute=large,size=3 --name my-cluster
    ```

5. **fulfillment-service:**
    - If `network_attachment` omitted: populates with tenant's default Subnet + default SecurityGroup (see Default Networking PRD)
    - Validates network_attachment:
      - Subnet exists, is Ready
      - SecurityGroups exist, are Ready, belong to same VN
    - For each node_set: resolves `host_type` → HostType → picks first interface with role `fabric` and stores as `fabric_interface` on the node set definition in the ClusterOrder spec
    - If `external_ip_mode == AUTO_ALL`: auto-selects ExternalIPPool, creates two ExternalIPs (API + ingress, each labeled `osac.openshift.io/auto-provisioned: "true"` and `osac.openshift.io/auto-provisioned-for: <cluster-id>`) and two ExternalIPAttachments (labeled `osac.openshift.io/auto-provisioned: "true"`) — all in the same DB transaction, all starting in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. The ExternalIPAttachments transition to Ready once VIPs are populated (see Phase 3). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow and phased requeue cleanup pattern.
    - If `nat_gateway_mode == AUTO`: checks if NATGateway already exists on the VN. If exists: reuse (regardless of state or whether it was manually or auto-created). No new resources created. If not exists: creates a **separate** ExternalIP for the NATGateway's SNAT source (ExternalIP exclusivity means one consumer each) and creates NATGateway in a **separate DB transaction** after the parent resource is persisted, both labeled `osac.openshift.io/auto-provisioned: "true"`. Pool capacity is decremented for this additional ExternalIP; if the pool is exhausted, the NATGateway is not created but the Cluster creation still succeeds (outbound NAT is best-effort).
    - Creates Cluster record with empty `api_endpoint` / `ingress_endpoint`
    - Creates ClusterOrder CR with enriched `network_attachment` in spec

6. **osac-operator ClusterOrder controller:**
    - Creates namespace, ServiceAccount, RoleBindings (same as today)

    **a. `reconcileAgentSelection` (NEW — replaces template-side agent selection):**
    - For each node_set: selects suitable agents from inventory based on `host_type`, availability, and labels
    - Labels and reserves selected agents for this cluster
    - Stores selected agent references on ClusterOrder status

    **b. `reconcileNetworking` (NEW — runs after agent selection, before provisioning):**
    - **Operator dispatches switch-side config:** For each agent across all node sets, dispatcher calls `osac.templates.{{ fabric_manager }}.create_network_attachment` passing `host_name` (agent's Netris server name), `logical_interface_name` (fabric_interface from the agent's node set definition), `subnet_ref`. The role checks if the port is already on a V-Net (parking network) — if so, removes it first — then adds the port to the tenant's subnet V-Net. Agents receive new IPs from the tenant subnet's DHCP server. See [Agent Pool Model](#agent-pool-model).
    - Network attachments must be Ready before provisioning proceeds

    **c. Triggers AAP workflow** (same as today, but template is simpler):
    - The ClusterOrder CR is serialized and passed to AAP

7. **CaaS template receives ClusterOrder (agents already selected, switch ports already configured).**

    The template's `install.yaml` changes:

    **a. Create HostedCluster + NodePools:**
    - `osac.service.hosted_cluster` creates HyperShift HostedCluster + NodePool CRs referencing the pre-selected agents from `status.nodeSets[].agents[].agentName`
    - No agent selection logic — already done by operator in step 6a
    - No switch port configuration — already done by operator in step 6b
    - Host-side networking handled by DHCP — no NMState or static config needed

    **b. MetalLB VIP provisioning (REPLACES `external_access` step):**

    The VN and Subnet already exist (tenant created them in steps 1-3). External access (ExternalIP, NATGateway, ExternalIPAttachment) is managed separately by the tenant. The template:
    - Creates MetalLB LoadBalancer Services for API server + ingress VIPs
    - MetalLB allocates VIPs from its IPAddressPool (created by k8s_manager at subnet creation)
    - Discovers the allocated VIPs and writes them to ClusterOrder CR status:
      ```yaml
      status:
        apiEndpoint: 10.0.1.200     # MetalLB-allocated API VIP
        ingressEndpoint: 10.0.1.201 # MetalLB-allocated ingress VIP
      ```
    - DNS record creation (stays inline — DNS API is a separate EP)

    **c. Retrieve kubeconfig, wait for nodes + operators (same as today)**

#### Phase 3: VIP Feedback Loop

8. **osac-operator feedback controller** watches ClusterOrder status:
    - Sees `apiEndpoint` and `ingressEndpoint` populated
    - Fires Signal RPC to fulfillment-service

9. **fulfillment-service** re-reads ClusterOrder CR:
    - Syncs `api_endpoint` and `ingress_endpoint` from ClusterOrder status to the Cluster object

10. **ExternalIPAttachment controller** reconciles the API attachment:
    - Checks two preconditions before dispatching (requeues if either is not met):
      1. ExternalIP must be Allocated (have an allocated address from the fabric manager)
      2. ClusterOrder must have `status.apiEndpoint` populated (VIP allocated by MetalLB, discovered by template in step 7b)
    - Once both are met: reads ClusterOrder's `apiEndpoint` → 10.0.1.200
    - Calls `osac.templates.{{ fabric_manager }}.create_external_ip_attachment`
    - Fabric manager creates DNAT: api-ip (203.0.113.10) → 10.0.1.200
    - ExternalIPAttachment transitions from **Pending** to **Ready**

11. Same for ingress ExternalIPAttachment:
    - Requeues until ExternalIP is Allocated AND ClusterOrder's `status.ingressEndpoint` is populated
    - Reads ClusterOrder's `ingressEndpoint` → 10.0.1.201
    - Creates DNAT: ingress-ip (203.0.113.11) → 10.0.1.201
    - Transitions to **Ready**

#### Deletion (reverse order)

12. **Delete Cluster:**
    - **Auto-provisioned cleanup (osac-operator ClusterOrder controller):** Phased requeue: deletes ExternalIPAttachments first (by target reference), waits, then deletes ExternalIPs (by `auto-provisioned-for` label), waits, then proceeds. See [Unified Networking — Auto-provisioned resource cleanup](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types).
    - **Auto-provisioned NATGateway is NOT cleaned up** — shared per-VN resource.
    - **Manually created resources are NOT cleaned up** — tenant manages their lifecycle. Manually created ExternalIPAttachments transition back to detached / Pending.
    - **Default networking resources (VN, Subnet, SG) are NOT cleaned up** — tenant-scoped and shared.
    - ClusterOrder controller triggers AAP delete workflow
    - CaaS delete template:
      - Deletes MetalLB LoadBalancer Services
      - Deletes HyperShift HostedCluster + NodePools
      - DNS cleanup
      - No switch port cleanup — template doesn't handle networking
    - ClusterOrder controller `reconcileNetworking` (delete): dispatcher calls `delete_network_attachment` per BM node (passing host_name, logical_interface_name from the agent's node set definition, subnet_ref). The role removes the port from the tenant's subnet V-Net and **returns it to the parking network** — the agent is back in the idle pool. See [Agent Pool Model](#agent-pool-model).
    - ClusterOrder controller `reconcileAgentCleanup` (delete): removes operator-set reservation labels from agents, making them available for future clusters.
    - Removes ClusterOrder finalizer

13. **Tenant deletes networking resources** (independently, if desired):
    - Delete ExternalIPAttachments → fabric manager removes DNAT rules
    - Delete NATGateway → fabric manager removes SNAT rule
    - Delete ExternalIPs → fabric manager releases IPs
    - Delete SecurityGroup → fabric manager removes ACL rules
    - Delete Subnet → dispatcher calls both managers: fabric manager removes V-Net segment, k8s_manager removes CUDN overlay + MetalLB IPAddressPool from hosting clusters
    - Delete VirtualNetwork → fabric manager removes tenant segment

### HostType and Interface Resolution

#### HostType Resource (shared with BMaaS)

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

Interfaces are ordered. When multiple interfaces share the same role (e.g., two `fabric` interfaces), the first one in the list is the default for that role.

#### How CaaS Uses HostType

The tenant provides a single `ClusterNetworkAttachment` with `subnet` only — no node_set or interface field. The fulfillment-service resolves the interface from the HostType for each node set:

1. For each node set in the cluster spec (e.g., "gpu"), read `ClusterSpec.node_sets["gpu"].host_type` = "acme_1tb_h100"
2. HostType "acme_1tb_h100" has interfaces:
   ```
   [{name: "data-0", role: "fabric"},
    {name: "data-1", role: "fabric"},
    {name: "mgmt-0", role: "management"}]
   ```
3. fulfillment-service picks the first interface with role `fabric` → `data-0`, stores as `fabric_interface` on the node set definition
4. Operator calls `create_network_attachment` with `interface=data-0` per node

For v0.2: **CaaS supports BM node sets only.** VM-based cluster node sets are architecturally possible (the HostType BM-vs-VM discriminator and CUDN overlay support it) but are deferred — the HyperShift ↔ CUDN integration for VM worker nodes is not in scope.

For v0.2: **one attachment per cluster → one subnet; each node set uses its own fabric interface from its HostType.**

#### Interface Role Convention

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) |

Roles are conventions, not enforced enums. The CaaS template defaults to role `fabric` for the tenant's subnet. The `lifecycle` interface is used by the provisioning system (Ironic, Metal3) for PXE boot and BMC operations — it is NOT tenant-attachable and the template skips it during interface resolution.

### What Changes vs. Today

#### Removed

- `osac.service.cluster_infra` dispatch to `{{ network_steps_collection }}.cluster_infra`
- `osac.service.external_access` dispatch to `{{ network_steps_collection }}.external_access`
- The entire concept of `NETWORK_STEPS_COLLECTION` for CaaS networking
- Step collections: `netris.steps`, `agentless_net.steps`, `osac.steps` etc. — their networking functionality is replaced by the OSAC Networking API + fabric manager roles

#### Added

- `ClusterNetworkAttachment` proto message on ClusterSpec
- `api_endpoint` / `ingress_endpoint` status fields on Cluster and ClusterOrder
- Operator handles agent selection and network attachment (dispatcher calls `create_network_attachment` / `delete_network_attachment` for BM nodes before/after provisioning)
- Template provisions MetalLB VIPs and writes them to ClusterOrder status
- VIP feedback loop: ClusterOrder → fulfillment-service → Cluster → ExternalIPAttachment controller
- ExternalIPAttachment Pending → Ready lifecycle for cluster targets

#### Kept

- HyperShift HostedCluster + NodePool creation (same)
- Agent selection and labeling (moved from template to operator)
- DNS record creation (inline, until DNS API is implemented)
- Kubeconfig retrieval (same)
- Wait for nodes + cluster operators (same)
- AAP workflow structure (create → post-install → report-status)

### API Extensions

#### Proto (fulfillment-service)

```protobuf
message ClusterNetworkAttachment {
  string subnet = 1;                    // Subnet ID, required, immutable
  repeated string security_groups = 2;  // SecurityGroup IDs, mutable
}
// Note: fabric_interface is system-populated on each node set definition
// by the fulfillment-service (resolved from the node set's HostType).

message ClusterSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;
  // ... existing fields ...
  ClusterNetworkAttachment network_attachment = 4;   // NEW, optional, singular
  ClusterExternalIPMode external_ip_mode = 20;       // NONE, AUTO_API, AUTO_INGRESS, AUTO_ALL
  NATGatewayMode nat_gateway_mode = 21;              // NONE or AUTO
}

message ClusterStatus {
  // ... existing fields ...
  string api_endpoint = X;      // NEW: set by template via feedback
  string ingress_endpoint = Y;  // NEW: set by template via feedback
}

enum ClusterExternalIPMode {
  CLUSTER_EXTERNAL_IP_MODE_UNSPECIFIED = 0;
  CLUSTER_EXTERNAL_IP_MODE_NONE = 1;          // default
  CLUSTER_EXTERNAL_IP_MODE_AUTO_API = 2;      // auto-provision API endpoint only
  CLUSTER_EXTERNAL_IP_MODE_AUTO_INGRESS = 3;  // auto-provision ingress endpoint only
  CLUSTER_EXTERNAL_IP_MODE_AUTO_ALL = 4;      // auto-provision both
}

enum NATGatewayMode {
  NAT_GATEWAY_MODE_UNSPECIFIED = 0;
  NAT_GATEWAY_MODE_NONE = 1;   // default
  NAT_GATEWAY_MODE_AUTO = 2;
}
```

#### Operator CRD (ClusterOrder)

```go
type ClusterOrderSpec struct {
    // ... existing fields ...
    NetworkAttachment *ClusterNetworkAttachment `json:"networkAttachment,omitempty"`
}

type ClusterNetworkAttachment struct {
    SubnetRef         string   `json:"subnetRef"`
    SecurityGroupRefs []string `json:"securityGroupRefs,omitempty"`
}

type ClusterOrderStatus struct {
    // ... existing fields ...
    APIEndpoint     string          `json:"apiEndpoint,omitempty"`     // MetalLB-allocated API VIP, discovered by template
    IngressEndpoint string          `json:"ingressEndpoint,omitempty"` // MetalLB-allocated ingress VIP, discovered by template
    NodeSets        []NodeSetStatus `json:"nodeSets,omitempty"`        // Per-agent data
}

type NodeSetStatus struct {
    Name            string        `json:"name"`
    FabricInterface string        `json:"fabricInterface,omitempty"` // System-populated from HostType
    Agents          []AgentStatus `json:"agents"`
}

type AgentStatus struct {
    AgentName string `json:"agentName"`           // Agent CR name (for NodePool targeting)
    HostName  string `json:"hostName"`            // Netris server name (for dispatcher)
    SubnetRef string `json:"subnetRef,omitempty"`
    IPAddress string `json:"ipAddress,omitempty"` // Discovered from Agent CR after DHCP assignment
}
```

#### Database

Migration adds to clusters table:
- `network_attachment JSONB` — stores the singular ClusterNetworkAttachment
- `api_endpoint TEXT` — discovered API server VIP
- `ingress_endpoint TEXT` — discovered ingress VIP

#### Server Validation

- network_attachment: subnet exists, is Ready
- Each node set's host_type must have at least one interface with role `fabric` for fabric_interface resolution
- Immutability: network_attachment is immutable after creation
- target_endpoint validation on ExternalIPAttachment: required when target is cluster, must be `API` or `INGRESS`

#### Template Changes

**osac.templates.ocp_4_17_small/install.yaml:**
- Remove: `osac.service.cluster_infra` call
- Remove: `osac.service.external_access` call
- Remove: agent selection logic (moved to operator)
- Add: create HostedCluster + NodePools referencing pre-selected agents from ClusterOrder status
- Add: MetalLB VIP provisioning (create LoadBalancer Services, discover VIPs, write to ClusterOrder status)

**osac.templates.ocp_4_17_small/delete.yaml:**
- Remove: step collection delete dispatch
- Remove: switch port cleanup (moved to operator)
- Keep: delete HostedCluster + NodePools, MetalLB Services, DNS cleanup

### Implementation Details/Notes/Constraints

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachment (singular), resolve fabric_interface per node set, create ClusterOrder CR, sync VIPs from feedback, auto-provision ExternalIP/NATGateway |
| osac-operator ClusterOrder controller | Create namespace/SA/RoleBindings, select agents, configure network attachments (dispatcher), trigger AAP workflow |
| osac-operator ClusterOrder feedback controller | Watch ClusterOrder status, Signal fulfillment-service when VIPs/IPs appear |
| osac-operator ExternalIPAttachment controller | Read ClusterOrder `apiEndpoint`/`ingressEndpoint` (MetalLB-allocated, template-discovered) from status, create DNAT via fabric_manager |
| AAP template (ocp_4_17_small) | Create HostedCluster+NodePools (with pre-selected agents), provision MetalLB VIPs, write VIPs to ClusterOrder status, host-side networking handled by DHCP — no agent selection logic |
| fabric_manager (Ansible role) | Switch-side only: create/delete_network_attachment (V-Net port attachment), create/delete_external_ip_attachment (DNAT), create/delete_nat_gateway (SNAT) |
| k8s_manager (Ansible role) | create/delete_subnet (CUDN overlay) — called at subnet creation, NOT at cluster creation |

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-provisioned: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway) inherit tenant annotation from parent Cluster
- No new authentication or authorization changes
- SecurityGroup rules control cluster node inbound traffic (tenant-configurable via explicit SG or default SG)

### Failure Handling and Recovery

#### ClusterOrder Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): ClusterOrder enters Failed state with condition, retries on Subnet status change
- Agent selection failure (no suitable agents): ClusterOrder enters Failed state, manual investigation required
- Network attachment failure (switch port config failed): ClusterOrder enters Failed state with AAP job ID in status
- AAP job failure (template execution error): ClusterOrder enters Failed state with AAP job ID in status

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, resource not persisted
- ExternalIP provisioning failure: ExternalIP enters Failed state, Cluster remains in Pending (external access unavailable, cluster may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach cluster (cluster functional, external access unavailable)

#### Auto NATGateway Provisioning Failures

- Pool exhaustion: NATGateway creation fails, Cluster proceeds without outbound NAT
- Reusing failed NATGateway: if existing NATGateway on VN is Failed or Deleting, system reuses it (no new NATGateway created), outbound connectivity unavailable until tenant manually deletes failed NATGateway and retries
- NATGateway provisioning failure: NATGateway enters Failed state, outbound SNAT rule not created, cluster has no outbound connectivity

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (Cluster with new fields, auto-provisioned ExternalIP/ExternalIPAttachment/NATGateway) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from Cluster to auto-created resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-provisioned: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- ClusterOrder controller: `AgentSelectionCompleted` (info), `AgentSelectionFailed` (error), `NetworkAttachmentsConfigured` (info), `VIPsDiscovered` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `AutoProvisionedNATGateway` (info), `ExternalIPPoolExhausted` (error), `VIPFeedbackProcessed` (info)

New Kubernetes events on ClusterOrder:
- `AgentsSelected`: agent selection succeeded
- `AgentSelectionFailed`: agent selection failed (no suitable agents)
- `NetworkingConfigured`: network attachments (switch ports) configured
- `NetworkingFailed`: network attachment configuration failed
- `VIPsDiscovered`: API and ingress VIPs written to status
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned
- `AutoNATGatewayCreated`: NATGateway auto-provisioned or reused

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: Agent selection logic moved from template to operator

**Impact:** Operator must implement agent selection logic currently in step collections (query agents by host_type, check availability, reserve, label). If implementation is incomplete or buggy, cluster provisioning fails.

**Mitigation:** Port existing agent selection logic from netris.steps/agentless_net.steps to operator. Test with integration tests.

**Reviewed by:** osac-operator team

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create cluster with `external_ip_mode=AUTO_*`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Auto NATGateway reuses failed or deleting NATGateway

**Impact:** If existing NATGateway on VN is Failed or Deleting, system reuses it, cluster's outbound connectivity will not work.

**Mitigation:** Document expected behavior: tenants must manually delete failed NATGateway and retry cluster creation. Alternative: change design to check NATGateway state before reusing (deferred to implementation phase).

**Reviewed by:** API design team

#### Risk: MetalLB IPAddressPool missing on hosting cluster

**Impact:** MetalLB needs an IPAddressPool CR covering the subnet CIDR to allocate VIPs from. If the k8s_manager fails to create it at subnet creation, cluster API/ingress endpoints are unreachable.

**Mitigation:** k8s_manager creates IPAddressPool alongside the CUDN overlay at subnet creation (resolved in OQ#3). Subnet remains Pending until both CUDN overlay and IPAddressPool are confirmed on all hosting clusters.

**Reviewed by:** osac-operator team

### Drawbacks

#### VIP feedback loop adds complexity

VIP discovery flow (template → ClusterOrder status → Signal RPC → fulfillment-service → Cluster → ExternalIPAttachment controller) adds cross-component coordination complexity. Failure in any step breaks the flow.

**Trade-off:** Complexity vs. auto external access. Chosen approach: implement VIP feedback loop to enable auto ExternalIP for clusters. Alternative: manual external access only (simpler, less usable).

#### Auto NATGateway reuse regardless of state

Design specifies that auto NATGateway reuses existing NATGateway "regardless of state or whether it was manually or auto-created." This simplifies conflict avoidance but means tenants can end up with clusters referencing failed NATGateways.

**Trade-off:** Simplicity vs. robustness. Chosen approach: reuse any existing NATGateway, document workaround (delete and retry). Alternative: state-aware reuse (more complex, could create duplicate NATGateways during transient failures).

## Alternatives (Not Implemented)

### Alternative 1: Keep networking in step collections

Instead of moving networking to the OSAC Networking API, keep step collections and extend them with tenant-scoped VirtualNetwork/Subnet creation.

**Rejected because:** Step collections are deployment-wide (NETWORK_STEPS_COLLECTION env var), not tenant-scoped. Tenants cannot share VirtualNetworks across resources or isolate clusters in separate VNs. The unified networking API provides a cleaner multi-tenant model.

### Alternative 2: No VIP feedback loop, manual external access only

Instead of implementing VIP feedback loop, require tenants to manually create ExternalIP and ExternalIPAttachment after cluster is Ready.

**Rejected because:** Poor user experience. Tenants must poll cluster status, discover VIPs, then manually create external access. Auto external access (single-call API) is a key usability improvement.

### Alternative 3: Always create auto NATGateway, even if one exists

Instead of reusing existing NATGateway, always create a new one when `nat_gateway_mode=AUTO`.

**Rejected because:** Multiple NATGateways on the same VN would conflict at the fabric level (SNAT rules for the same CIDR would overlap). Reusing existing NATGateway avoids conflict.

## Open Questions

### 1. How does the operator select agents?

The operator needs agent selection logic (currently in the step collection's cluster_infra role). This includes: querying available agents by host_type and labels, reserving them for this cluster, and labeling them. Does the operator call an AAP job for this, or does it interact with the agent inventory directly (K8s API for Agent CRs)?

**Owner:** osac-operator team

**Impact:** Affects implementation of `reconcileAgentSelection`.

### ~~2. NMState NNCP configuration~~ — Resolved

Resolved: DHCP handles host-side networking for CaaS agents. NMState NNCP configuration is no longer needed — agents receive their IP, gateway, and DNS from the fabric's DHCP server when they boot on the V-Net. The template does not configure static networking.

### ~~3. MetalLB IP pools~~ — Resolved

Resolved: the **k8s_manager creates the MetalLB IPAddressPool CR at subnet creation time**, alongside the CUDN overlay on each hosting cluster. The IPAddressPool covers the subnet CIDR and is a shared prerequisite for all hosted cluster control planes on that hosting cluster — not a per-cluster resource. The CaaS template creates LoadBalancer Services; MetalLB dynamically allocates VIPs from the pool and announces them. The template discovers the allocated VIPs and writes them to ClusterOrder status.

### 4. How does the operator know the fabric_manager name?

With one NetworkClass per deployment, the operator reads it once. But for the dispatcher call, the operator needs the name to select the right AAP template. Options: read NetworkClass CR, or env var.

**Owner:** osac-operator team

**Impact:** Affects dispatcher implementation in ClusterOrder controller.

### 5. Should auto NATGateway treat a Deleting NATGateway as "does not exist"?

Design decision: reuse existing NATGateway in Ready or Failed state (avoids duplicate SNAT conflicts). Open question: should a NATGateway in **Deleting** state be treated as "does not exist" (create a new one), since the SNAT rule is being removed and the NATGateway will soon be fully deleted? Current behavior would silently attach to a disappearing resource.

**Owner:** API design team

**Impact:** Affects NATGateway reuse logic and user experience when NATGateway is being deleted concurrently.

### 6. Should capacity exhaustion return an API error or create a Failed resource?

Current proposal: return error, no resources persisted. Alternative: create Failed resource for audit trail.

**Owner:** API design team

**Impact:** Affects auto ExternalIP allocation behavior and acceptance criteria.

## Test Plan

### Unit Tests

- fulfillment-service: network_attachment validation (subnet exists, Ready, same VN)
- fulfillment-service: fabric_interface resolution per node set (host_type must have fabric-role interface)
- fulfillment-service: interface resolution from HostType (pick first fabric-role interface)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- fulfillment-service: auto NATGateway reuse (reuse existing, create new if none exists)
- osac-operator ClusterOrder controller: agent selection logic
- osac-operator ClusterOrder controller: network attachment resolution
- osac-operator feedback controller: VIP sync to fulfillment-service

### Integration Tests

- E2E: create Cluster with explicit network_attachment, verify cluster provisioned on correct subnet
- E2E: create Cluster with `--external-ip=auto-all`, verify auto ExternalIP + ExternalIPAttachment created for API and ingress, DNAT rules functional
- E2E: create Cluster with `--nat-gateway=auto`, verify auto NATGateway created or reused, SNAT rule functional
- E2E: create Cluster with `--external-ip=auto-all --nat-gateway=auto`, verify full connectivity (inbound + outbound)
- E2E: delete Cluster with auto-provisioned resources, verify ExternalIPAttachments and ExternalIPs cleaned up
- E2E: create Cluster with omitted network_attachment, verify default Subnet + SecurityGroup populated
- E2E: VIP feedback loop — verify template writes VIPs to ClusterOrder status, fulfillment-service syncs to Cluster, ExternalIPAttachment controller creates DNAT

### Tricky Test Cases

- Multiple node sets sharing the same subnet (verify correct fabric interface resolution per node set from HostType)
- Auto NATGateway when existing NATGateway is Failed (verify reuse, document expected behavior)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)
- VIP feedback loop failure (Signal RPC fails, fulfillment-service does not sync VIPs)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachment`, `external_ip_mode`, `nat_gateway_mode`, `api_endpoint`, `ingress_endpoint`) implemented in fulfillment-service
- [ ] Operator CRD updated with `NetworkAttachment`, `APIEndpoint`, `IngressEndpoint` fields
- [ ] Agent selection logic (`reconcileAgentSelection`) implemented in osac-operator
- [ ] Network attachment logic (`reconcileNetworking`) implemented in osac-operator
- [ ] VIP feedback loop (template → ClusterOrder → fulfillment-service → Cluster) implemented
- [ ] Auto ExternalIP and auto NATGateway provisioning functional
- [ ] Template changes (remove cluster_infra/external_access, add MetalLB VIP provisioning) completed
- [ ] Integration tests pass (E2E coverage for network_attachment, auto ExternalIP, auto NATGateway, VIP feedback)
- [ ] Documentation: API reference, user guide for simplified cluster creation

GA criteria:
- [ ] k8s_manager implementation (OSAC-1511 or OSAC-1717) delivered and production-tested
- [ ] Multi-job tracking (OSAC-1459) implemented and stable
- [ ] Dispatcher infrastructure (OSAC-1457, OSAC-1458, OSAC-1460) delivered
- [ ] HostType NetworkInterface list implemented and tested
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`network_attachment`, `external_ip_mode`, `nat_gateway_mode`, `api_endpoint`, `ingress_endpoint`) are additive
- Existing Cluster resources continue to work (networking managed by step collections)
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Template changes deployed (cluster_infra/external_access removed, MetalLB VIP provisioning added)
- Existing clusters (created before upgrade) continue to work with old flow
- New clusters (created after upgrade) use new flow (OSAC Networking API)
- No breaking changes

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service, osac-operator, and osac-aap images to `N`
- Existing Cluster resources with new `network_attachment` field will be unrecognized by `N` server
- Manual cleanup required: delete Cluster resources created with new field, re-create with old flow
- Auto-provisioned ExternalIP/NATGateway resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Delete Clusters using new field
- Re-create using old flow (no network_attachment field)
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway labeled `osac.openshift.io/auto-provisioned: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service, osac-operator, and osac-aap are deployed together in the same namespace and upgraded atomically (all controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not send `--network-attachment` flag → server uses default Subnet + SecurityGroup
- New CLI uses new `--network-attachment` flag → server accepts

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses new `--network-attachment` flag → old server rejects unknown field
- Workaround: omit `--network-attachment` until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: Cluster stuck in Pending, condition "NetworkingResolutionFailed"

**Detection:**
```bash
kubectl describe cluster <name> -n <namespace>
# Check status.conditions for NetworkingResolutionFailed
```

**Cause:** Subnet not found, not Ready, or BM-only region (no k8s_manager)

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. If BM-only region, tenant must create Cluster in a region with k8s_manager configured

### Symptom: Auto-provisioned ExternalIP not cleaned up after Cluster deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check Cluster deletion logs (controller logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Symptom: ClusterOrder VIPs not synced to Cluster

**Detection:** `kubectl get clusterorder <name> -o yaml` shows `apiEndpoint` and `ingressEndpoint` populated, but `kubectl get cluster <name> -o yaml` shows empty fields

**Cause:** VIP feedback loop failure (Signal RPC failed, or fulfillment-service did not process)

**Resolution:**
1. Check osac-operator feedback controller logs for Signal RPC errors
2. Check fulfillment-service logs for VIP sync errors
3. Manually trigger reconciliation: `kubectl annotate clusterorder <name> osac.openshift.io/reconcile=true`

### Disabling the feature

To disable auto ExternalIP and auto NATGateway:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP/NATGateway workflows remain functional
- No impact on existing running clusters

## Infrastructure Needed

- AAP execution environment with `osac.templates.ocp_4_17_small` role updated (remove cluster_infra/external_access, add MetalLB VIP provisioning)
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- fabric_manager Ansible role with `create_network_attachment` / `delete_network_attachment` (OSAC-2081)
- Integration test environment with CUDN or EVPN fabric
- HostType test data with structured NetworkInterface list

## Dependencies

| Dependency | Jira | Status |
|-----------|------|--------|
| Dispatcher core | OSAC-1457, OSAC-1458, OSAC-1460 | In Progress |
| Multi-job tracking (subnet) | OSAC-1459 | New |
| NATGateway full stack | OSAC-1443 (10 tasks) | 1/10 In Progress |
| ExternalIPAttachment cluster target in CRD | OSAC-2041 | New |
| Cluster DNAT flow in controller | OSAC-1495 | New |
| ClusterNetworkAttachment proto | OSAC-1501 | New |
| api_endpoint/ingress_endpoint on Cluster status | OSAC-2040 | New |
| Immutability validation | OSAC-1503 | New |
| DB migration for Cluster networking fields | OSAC-2079 | New |
| Server validation | OSAC-1504 | New |
| ClusterOrder CRD: network_attachment | OSAC-1505 | New |
| ClusterOrder CRD: api/ingress endpoint status | OSAC-2080 | New |
| VIP discovery flow (feedback) | OSAC-1506 | New |
| CaaS template: accept network_attachment + per-node config | OSAC-1507 | New |
| CaaS template: MetalLB VIP provisioning + write to status | OSAC-2077 | New |
| Cluster provisioning flow (operator side) | OSAC-2049 | New |
| CLI --network-attachment for Cluster | OSAC-2076 | New |
| Integration test | OSAC-2078 | New |
| Fabric manager create/delete_network_attachment role | OSAC-2081 (Netris BM) | New |
| HostType: add structured NetworkInterface list | Not tracked | **GAP** |
| Remove cluster_infra / external_access step collection dispatch | Not tracked | **GAP** |
| Remove NETWORK_STEPS_COLLECTION dependency | Not tracked | **GAP** |
| Agent selection logic in operator (reconcileAgentSelection) | Not tracked | **GAP** |
| fulfillment-service: resolve interface from HostType (fabric_interface) | Not tracked | **GAP** |
