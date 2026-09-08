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
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking — Cluster Networking via OSAC Networking API

CaaS networking provides tenant-controlled cluster node networking via VirtualNetwork + Subnet attachments, BM-based node sets with fabric interface resolution from BareMetalInstanceType, MetalLB VIP provisioning, and auto-provisioned external access (ExternalIP + ExternalIPAttachment) for cluster API and ingress endpoints.

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how CaaS consumes that architecture.

Cluster provisioning uses the OSAC Networking API for all networking lifecycle — tenants place clusters on their VirtualNetworks via `network_attachment`, the `BareMetalWorkerReconciler` creates on-demand `BareMetalInstance` objects via the BMaaS private gRPC API (BMaaS owns the fabric port move and IP assignment as part of BMI provisioning), and a VIP feedback loop enables auto-provisioned external access for cluster API and ingress endpoints. See [PRD](prd.md) for detailed requirements and [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md) for the full provisioning design.

## Motivation

Clusters require tenant-controlled networking to enable:
- Placing clusters on shared or isolated VirtualNetworks
- Automatic agent port configuration (provisioning network → tenant network) during cluster creation
- VIP feedback loop for cluster API/ingress endpoints to enable DNAT via ExternalIPAttachment
- Auto external access (ExternalIP + ExternalIPAttachment) for single-call cluster provisioning with inbound connectivity

### Goals

- Move cluster networking lifecycle to the OSAC Networking API (VirtualNetwork, Subnet, SecurityGroup)
- Tenant-controlled cluster node subnet placement via `network_attachment` field on ClusterSpec
- BM-based node sets with fabric interface resolution from BareMetalInstanceType (OSAC-1201)
- On-demand BareMetalInstance creation via BMaaS private gRPC API; BMaaS owns the fabric port move and IP assignment as part of BMI provisioning (OSAC-2135)
- VIP feedback loop: template provisions MetalLB VIPs → ClusterOrder status → fulfillment-service → Cluster → ExternalIPAttachment controller
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call API/ingress external access
- Remove step collections (`netris.steps`, `agentless_net.steps`) from CaaS networking

### On-Demand BMI Provisioning Model (OSAC-2135)

Per [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), CaaS provisions bare-metal worker nodes **on demand** via the BMaaS private gRPC API — the static pre-boot agent pool is removed. A dedicated `BareMetalWorkerReconciler` in osac-operator creates `BareMetalInstance` objects for each requested worker. Each BMI references a RHCOS DiskImage and carries discovery ignition inline from a cluster-specific InfraEnv.

**BMaaS owns the full provisioning lifecycle** including networking:
1. BMaaS provisions the host on the **provisioning network** (inventory → OS provisioning via DiskImage + ignition)
2. BMaaS moves the host's fabric port **provisioning network → tenant network** (`reconcileNetworking` dispatches `move_network_attachment` after provisioning completes)
3. BMaaS reboots the host so the OS re-DHCPs on the tenant network (`reconcileReboot`)
4. BMaaS discovers the tenant-network IP via DHCP lease query (`reconcileIPDiscovery`)
5. The full assisted-installer cluster installation begins on the tenant network: the host registers as an Agent with assisted-service, performs hardware discovery, runs the OpenShift installation, and reports progress — all from scratch on the tenant network

The `BareMetalWorkerReconciler` reads `ClusterOrder.spec.network_attachment` (a `ClusterNetworkAttachment` carrying `subnetRef` + `securityGroupRefs`) and enriches it into a per-BMI `BareMetalNetworkAttachment` by resolving the fabric interface from the immutable `fabric_interface` stored on the node set by the fulfillment-service. CaaS never dispatches `move_network_attachment` directly — that is BMaaS's responsibility as part of BMI provisioning. On cluster deletion, the controller calls `BareMetalInstances.Delete`; BMaaS handles full host cleanup including returning the fabric port to the provisioning network.

### Non-Goals

- VMaaS or BMaaS networking (this EP covers CaaS only)
- VM-based cluster node sets (v0.2 supports BM node sets only; VM worker nodes require HyperShift ↔ CUDN integration not in scope)
- DNS API (DNS record creation stays inline in the template until DNS API is implemented)
- Multi-NIC cluster nodes (v0.2: one attachment per cluster → one subnet; each node set resolves its own fabric interface from its BareMetalInstanceType)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)

## Proposal

### Workflow Description

#### Phase 1: Tenant Creates Networking Resources

These steps are identical to VMaaS/BMaaS — the networking API is uniform.

1. **Create VirtualNetwork:**
   ```bash
   osac create virtualnetwork --network-class moc-bm-1 --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → `osac.templates.{{ fabric_manager }}.create_virtual_network`

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → TWO jobs: fabric_manager creates VLAN/fabric segment + k8s_manager creates CUDN overlay (if deployment hosts VMs)

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
      --external-ip-attachment \
      --node-set compute=large,size=3 --name my-cluster
    ```

5. **fulfillment-service:**
    - If `network_attachment` omitted: populates with tenant's default Subnet + default SecurityGroup (see Default Networking PRD)
    - Validates network_attachment:
      - Subnet exists, is Ready
      - SecurityGroups exist, are Ready, belong to same VN
    - For each node_set: resolves `baremetal_instance_type` → BareMetalInstanceType → picks first port with `role=fabric` from `network_ports[]` and stores as `fabric_interface` on the node set definition in the ClusterOrder spec
    - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool, creates two ExternalIPs (API + ingress, each labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <cluster-id>`) and two ExternalIPAttachments (labeled `osac.openshift.io/auto-created: "true"`) — all in the same DB transaction, all starting in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. The ExternalIPAttachments transition to Ready once VIPs are populated (see Phase 3). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow and phased requeue cleanup pattern.
    - Creates Cluster record with empty `api_endpoint` / `ingress_endpoint`
    - Creates ClusterOrder CR with enriched `network_attachment` in spec

6. **osac-operator ClusterOrder controller:**
    - Creates namespace, ServiceAccount, RoleBindings (same as today)

    **a. Triggers AAP workflow** to create the HostedCluster and NodePool CRs.

    **b. `BareMetalWorkerReconciler`** (runs after the ClusterDeployment exists, per OSAC-2135):
    - Creates a cluster-specific `InfraEnv` CR for discovery ignition
    - For each bare-metal worker requested, creates a `BareMetalInstance` via the BMaaS private gRPC API, passing `network_attachments` enriched from `ClusterOrder.spec.network_attachment` with the immutable `fabric_interface` already stored on the node set by the fulfillment-service (step 5) — the controller does not re-resolve from BareMetalInstanceType to avoid divergence if the profile changes after cluster creation
    - BMaaS provisions each host (DiskImage + ignition), moves its fabric port from provisioning network → tenant network, reboots, and discovers the tenant-network IP via DHCP lease query — all as part of BMI provisioning (inventory → provisioning → networking → reboot → IP discovery)
    - The controller correlates registered Agents to BMIs via MAC address and labels them for NodePool selection
    - If an Agent does not register within a configurable timeout (default: 30 minutes), the controller sets the worker phase to `Failed` with reason `AgentRegistrationTimeout` and retries with escalating backoff (see OSAC-2135 for full retry logic)

    > **Tenant-network reachability prerequisites.** After the port move, cluster installation runs entirely on the tenant network. The tenant V-Net and the management cluster are in separate VPCs with no direct network path — all communication between them traverses the external network: outbound via NATGateway/SNAT from the tenant V-Net, inbound to the management cluster's external ingress. This applies to assisted-service registration, container image pulls, and post-installation kubelet-to-kube-apiserver heartbeats. All dependencies (container images, RHCOS, OCP release payload) must be pullable from the tenant network via the same egress path. SecurityGroup egress rules must allow outbound `:443`. `AgentRegistrationTimeout` catches tenant-to-assisted-service egress failures (the agent cannot register if it cannot reach assisted-service). A future disconnected installation flow would pre-stage dependencies locally, removing the egress requirement.

7. **CaaS template creates the HostedCluster + NodePool; BareMetalWorkerReconciler provisions workers.**

    The template's `install.yaml` changes:

    **a. Create HostedCluster + NodePools:**
    - AAP creates HyperShift HostedCluster + NodePool CRs
    - No agent selection or switch port configuration — the `BareMetalWorkerReconciler` handles worker provisioning on-demand via BMaaS (step 6b)
    - Host-side networking handled by DHCP — no NMState or static config needed

    **b. MetalLB VIP provisioning (REPLACES `external_access` step):**

    The VN and Subnet already exist (tenant created them in steps 1-3). External access (ExternalIP, ExternalIPAttachment) is auto-provisioned or managed separately by the tenant. NATGateway is expected to exist on the VN as a default from tenant onboarding, not auto-created per cluster. The template:
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
    - **Auto-provisioned cleanup (osac-operator ClusterOrder controller):** Phased requeue: deletes ExternalIPAttachments first (by target reference), waits, then deletes ExternalIPs (by `auto-created-for` label), waits, then proceeds. See [Unified Networking — Auto-provisioned resource cleanup](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types).
    - **Manually created resources are NOT cleaned up** — tenant manages their lifecycle. Manually created ExternalIPAttachments transition back to detached / Pending.
    - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — tenant-scoped and shared.
    - ClusterOrder controller triggers AAP delete workflow
    - CaaS delete template:
      - Deletes MetalLB LoadBalancer Services
      - Deletes HyperShift HostedCluster + NodePools
      - DNS cleanup
    - ClusterOrder finalizer actively deletes every BMI listed in `status.workers[]` via `BareMetalInstances.Delete` on the BMaaS private API (30 s context deadline per call). The call returns once the delete is accepted; BMaaS handles full host cleanup asynchronously (deprovision, fabric port return to provisioning network). The controller retains each worker entry in `status.workers[]` in `Deleting` phase and polls BMI state on subsequent reconciliation cycles until the BMI is confirmed gone — only then is the entry removed. If the deadline is exceeded or the call fails, the controller retries on the next requeue (controller-runtime exponential backoff); `BareMetalInstances.Delete` is idempotent, so retries are safe. The finalizer holds until all `status.workers[]` entries are confirmed deleted. The InfraEnv CR is garbage collected via its ownerReference to the ClusterOrder (see OSAC-2135).
    - Removes ClusterOrder finalizer

13. **Tenant deletes networking resources** (independently, if desired):
    - Delete ExternalIPAttachments → fabric manager removes DNAT rules
    - Delete NATGateway → fabric manager removes SNAT rule
    - Delete ExternalIPs → fabric manager releases IPs
    - Delete SecurityGroup → fabric manager removes ACL rules
    - Delete Subnet → dispatcher calls both managers: fabric manager removes network segment, k8s_manager removes CUDN overlay + MetalLB IPAddressPool from hosting clusters
    - Delete VirtualNetwork → fabric manager removes tenant segment

### BareMetalInstanceType and Interface Resolution

#### BareMetalInstanceType Network Ports

Per [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), `HostType` is deprecated and decommissioned — `BareMetalInstanceType` (OSAC-1201) is the sole source of truth for hardware profiles and interface resolution. CaaS `ClusterNodeSet.baremetal_instance_type` references this resource.

```protobuf
message BareMetalNetworkPortSpec {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0" — unique within the type
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string type = 3;        // e.g., "Ethernet"
  string speed = 4;       // e.g., "100Gbps", "1Gbps"
}
```

`BareMetalInstanceType` is a bare-metal-only resource (OSAC-1201) — BM vs VM is classified by resource type (`BareMetalInstance` vs `ComputeInstance`), not by the contents of `network_ports`. Every `BareMetalInstanceType` must declare at least one `network_ports` entry with `role=fabric`; a bare-metal profile with no fabric port is rejected at creation time because both the operator (provisioning-network port move) and the default-interface resolution (first `role=fabric` port) depend on it.

Interfaces are ordered. When multiple interfaces share the same role (e.g., two `fabric` interfaces), the first one in the list is the default for that role.

#### How CaaS Uses BareMetalInstanceType

The tenant provides a single `ClusterNetworkAttachment` with `subnet` only — no node_set or interface field. The `BareMetalWorkerReconciler` resolves the interface from the BareMetalInstanceType for each node set:

1. For each node set in the cluster spec (e.g., "gpu"), read `ClusterSpec.node_sets["gpu"].baremetal_instance_type` = "bm-standard"
2. BareMetalInstanceType "bm-standard" has network_ports:
   ```
   [{name: "data-0", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "data-1", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "mgmt-0", role: "management", type: "Ethernet", speed: "1Gbps"}]
   ```
3. The controller picks the first port with `role=fabric` → `data-0`, uses it as the `interface` field on the per-BMI `BareMetalNetworkAttachment`
4. BMaaS receives the `BareMetalNetworkAttachment` (subnet + interface + primary) on the BMI Create call and handles the fabric port move as part of provisioning (see [On-Demand BMI Provisioning Model](#on-demand-bmi-provisioning-model-osac-2135))

For v0.2: **CaaS supports BM node sets only.** VM-based cluster node sets are architecturally possible but are deferred — the HyperShift ↔ CUDN integration for VM worker nodes is not in scope.

For v0.2: **one attachment per cluster → one subnet; each node set resolves its own fabric interface from its BareMetalInstanceType.**

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
- `BareMetalWorkerReconciler` creates on-demand BareMetalInstances via BMaaS private gRPC API; BMaaS owns the fabric port move and IP assignment as part of BMI provisioning (OSAC-2135)
- Template provisions MetalLB VIPs and writes them to ClusterOrder status
- VIP feedback loop: ClusterOrder → fulfillment-service → Cluster → ExternalIPAttachment controller
- ExternalIPAttachment Pending → Ready lifecycle for cluster targets

#### Kept

- HyperShift HostedCluster + NodePool creation (same)
- Agent correlation and labeling (BareMetalWorkerReconciler correlates Agents to BMIs via MAC address)
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
// Note: fabric_interface is system-populated ONCE on each node set definition
// by the fulfillment-service at cluster creation (resolved from the node set's
// BareMetalInstanceType, immutable after creation). The BareMetalWorkerReconciler
// reads this stored value — it does not re-resolve from BareMetalInstanceType.

message ClusterSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;
  // ... existing fields ...
  ClusterNetworkAttachment network_attachment = 9;   // NEW, optional, singular
  bool auto_external_ip_attachment = 10;              // NEW, auto-provision ExternalIP + ExternalIPAttachment for API and ingress
}

message ClusterStatus {
  // ... existing fields ...
  string api_endpoint = X;      // NEW: set by template via feedback
  string ingress_endpoint = Y;  // NEW: set by template via feedback
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
    Name            string `json:"name"`
    FabricInterface string `json:"fabricInterface,omitempty"` // System-populated from BareMetalInstanceType
}

// Per-worker lifecycle state is tracked in ClusterOrder.status.workers[]
// (see OSAC-2135 WorkerStatus). The BareMetalWorkerReconciler manages
// worker phases (Provisioning → WaitingForAgent → Binding → Ready),
// BMI resource IDs, and failure/retry state. IP addresses are discovered
// by BMaaS as part of BMI provisioning (reconcileIPDiscovery) and do not
// require operator-side Agent CR IP watching.
```

#### Database

Migration adds to clusters table:
- `network_attachment JSONB` — stores the singular ClusterNetworkAttachment
- `api_endpoint TEXT` — discovered API server VIP
- `ingress_endpoint TEXT` — discovered ingress VIP

#### Server Validation

- network_attachment: subnet exists, is Ready
- Each node set's `baremetal_instance_type` must have at least one `network_ports` entry with `role=fabric` for fabric_interface resolution
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
- Remove: switch port cleanup (handled by BMaaS via BMI deletion)
- Keep: delete HostedCluster + NodePools, MetalLB Services, DNS cleanup

### Implementation Details/Notes/Constraints

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate `network_attachment` (singular), resolve fabric_interface per node set from BareMetalInstanceType, create ClusterOrder CR, sync VIPs from feedback, auto-provision ExternalIP |
| osac-operator BareMetalWorkerReconciler | Create on-demand BareMetalInstances via BMaaS private gRPC API with enriched `network_attachments` (subnet from ClusterOrder `network_attachment` + immutable `fabric_interface` from the node set, resolved once by fulfillment-service); correlate Agents to BMIs via MAC; delete BMIs on scale-down/cluster deletion. BMaaS owns the fabric port move and IP discovery as part of BMI provisioning (OSAC-2135) |
| osac-operator ClusterOrder controller | Create namespace/SA/RoleBindings, trigger AAP workflow, aggregate worker status |
| osac-operator ClusterOrder feedback controller | Watch ClusterOrder status, Signal fulfillment-service when VIPs appear |
| osac-operator ExternalIPAttachment controller | Read ClusterOrder `apiEndpoint`/`ingressEndpoint` (MetalLB-allocated, template-discovered) from status, create DNAT via fabric_manager |
| AAP template (ocp_4_17_small) | Create HostedCluster+NodePools, provision MetalLB VIPs, write VIPs to ClusterOrder status, host-side networking handled by DHCP |
| BMaaS (bare-metal-fulfillment-operator) | Owns full BMI provisioning lifecycle including inventory → OS provisioning → fabric port move (provisioning network → tenant) → reboot → DHCP lease query IP discovery; returns fabric port to provisioning network on BMI deletion |
| fabric_manager (Ansible role) | move_network_attachment (generic port move, dispatched by BMaaS during BMI provisioning), create/delete_external_ip_attachment (DNAT), create/delete_nat_gateway (SNAT) |
| k8s_manager (Ansible role) | create/delete_subnet (CUDN overlay) — called at subnet creation, NOT at cluster creation |

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-created: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- On permanent cleanup failure: finalizer removed, parent deleted, orphaned resources left for manual cleanup

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent Cluster
- No new authentication or authorization changes
- SecurityGroup rules control cluster node inbound traffic (tenant-configurable via explicit SG or default SG)

### Failure Handling and Recovery

#### ClusterOrder Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): ClusterOrder enters Failed state with condition, retries on Subnet status change
- BMI creation failure (BMaaS private API error or no available hosts): worker phase set to `Failed`, controller retries with escalating backoff (see OSAC-2135 retry logic)
- Agent registration timeout (host booted but Agent did not register within 30 min): worker phase set to `Failed` with reason `AgentRegistrationTimeout`, controller deletes the timed-out BMI and retries
- AAP job failure (template execution error): ClusterOrder enters Failed state with AAP job ID in status

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, resource not persisted
- ExternalIP provisioning failure: ExternalIP enters Failed state, Cluster remains in Pending (external access unavailable, cluster may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach cluster (cluster functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: after N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (Cluster with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from Cluster to auto-created resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- ClusterOrder controller: `AgentSelectionCompleted` (info), `AgentSelectionFailed` (error), `NetworkAttachmentsConfigured` (info), `VIPsDiscovered` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error), `VIPFeedbackProcessed` (info)

New Kubernetes events on ClusterOrder:
- `AgentsSelected`: agent selection succeeded
- `AgentSelectionFailed`: agent selection failed (no suitable agents)
- `NetworkingConfigured`: network attachments (switch ports) configured
- `NetworkingFailed`: network attachment configuration failed
- `VIPsDiscovered`: API and ingress VIPs written to status
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: BMaaS private API dependency for worker provisioning

**Impact:** The `BareMetalWorkerReconciler` depends on the BMaaS private gRPC API (`BareMetalInstances.Create`/`Delete`) for all worker lifecycle operations. If the fulfillment-service is unavailable, worker provisioning and deprovisioning stall.

**Mitigation:** Controller uses context deadlines (30s) and sets `FulfillmentServiceUnavailable` condition after 3 consecutive errors, backing off to 5-minute requeue intervals. Existing workers continue running independently of the controller (see OSAC-2135).

**Reviewed by:** osac-operator team

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create cluster with `auto_external_ip_attachment=true`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: MetalLB IPAddressPool missing on hosting cluster

**Impact:** MetalLB needs an IPAddressPool CR covering the subnet CIDR to allocate VIPs from. If the k8s_manager fails to create it at subnet creation, cluster API/ingress endpoints are unreachable.

**Mitigation:** k8s_manager creates IPAddressPool alongside the CUDN overlay at subnet creation (resolved in OQ#3). Subnet remains Pending until both CUDN overlay and IPAddressPool are confirmed on all hosting clusters.

**Reviewed by:** osac-operator team

### Drawbacks

#### VIP feedback loop adds complexity

VIP discovery flow (template → ClusterOrder status → Signal RPC → fulfillment-service → Cluster → ExternalIPAttachment controller) adds cross-component coordination complexity. Failure in any step breaks the flow.

**Trade-off:** Complexity vs. auto external access. Chosen approach: implement VIP feedback loop to enable auto ExternalIP for clusters. Alternative: manual external access only (simpler, less usable).

## Alternatives (Not Implemented)

### Alternative 1: Keep networking in step collections

Instead of moving networking to the OSAC Networking API, keep step collections and extend them with tenant-scoped VirtualNetwork/Subnet creation.

**Rejected because:** Step collections are deployment-wide (NETWORK_STEPS_COLLECTION env var), not tenant-scoped. Tenants cannot share VirtualNetworks across resources or isolate clusters in separate VNs. The unified networking API provides a cleaner multi-tenant model.

### Alternative 2: No VIP feedback loop, manual external access only

Instead of implementing VIP feedback loop, require tenants to manually create ExternalIP and ExternalIPAttachment after cluster is Ready.

**Rejected because:** Poor user experience. Tenants must poll cluster status, discover VIPs, then manually create external access. Auto external access (single-call API) is a key usability improvement.

## Open Questions

### ~~1. How does the operator select agents?~~ — Resolved

Resolved: Per OSAC-2135, the `BareMetalWorkerReconciler` creates on-demand `BareMetalInstance` objects via the BMaaS private gRPC API. Agents register automatically after BMI provisioning and are correlated to BMIs via MAC address. The static pre-boot agent pool is removed.

### ~~2. NMState NNCP configuration~~ — Resolved

Resolved: DHCP handles host-side networking for CaaS agents. NMState NNCP configuration is no longer needed — agents receive their IP, gateway, and DNS from the fabric's DHCP server when they boot on the network segment. The template does not configure static networking.

### ~~3. MetalLB IP pools~~ — Resolved

Resolved: the **k8s_manager creates the MetalLB IPAddressPool CR at subnet creation time**, alongside the CUDN overlay on each hosting cluster. The IPAddressPool covers the subnet CIDR and is a shared prerequisite for all hosted cluster control planes on that hosting cluster — not a per-cluster resource. The CaaS template creates LoadBalancer Services; MetalLB dynamically allocates VIPs from the pool and announces them. The template discovers the allocated VIPs and writes them to ClusterOrder status.

### ~~4. How does the operator know the fabric_manager name?~~ — Resolved

Resolved: The operator reads the fabric_manager name from the NetworkClass CR. One NetworkClass per deployment, read on first reconcile and cached. The NetworkClass is a K8s CR (not just a fulfillment-service DB object).

### ~~5. Should auto NATGateway treat a Deleting NATGateway as 'does not exist'?~~ — Resolved

Resolved: NATGateway reuse limited to Ready only. Failed/Deleting NATGateways cause the create request to fail with an error. NATGateway auto-provisioning per resource was removed — NATGateway is now a VN default created at tenant onboarding.

### ~~6. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity is checked synchronously during the API call. If exhausted, the call fails atomically. No Failed resource created.

### ~~7. How is the subnet CIDR partitioned between MetalLB VIP allocation and fabric DHCP assignment?~~ — Resolved

Resolved: The k8s_manager creates the MetalLB IPAddressPool with a reserved sub-range of the subnet CIDR (e.g., last /28). The fabric manager's DHCP server is configured to exclude this range. The sub-range size is configurable on the NetworkClass. This ensures MetalLB VIPs and DHCP-assigned agent IPs never overlap.

### ~~8. What IP addresses do DNS records point to — MetalLB VIPs or ExternalIPs?~~ — Resolved

Resolved: Kubeconfig API address uses the MetalLB VIP directly — workers are on the same subnet and reach it without DNS. External DNS records (api.<cluster>.<domain>, *.apps.<cluster>.<domain>) point to the ExternalIP and are only created when the tenant uses --external-ip-attachment. No bootstrap sequencing issue — workers use VIPs from kubeconfig, not DNS.

## Test Plan

### Unit Tests

- fulfillment-service: network_attachment validation (subnet exists, Ready, same VN)
- fulfillment-service: fabric_interface resolution per node set (BareMetalInstanceType must have fabric-role port)
- fulfillment-service: interface resolution from BareMetalInstanceType (pick first fabric-role port from network_ports[])
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator BareMetalWorkerReconciler: BMI creation with enriched network_attachment
- osac-operator BareMetalWorkerReconciler: Agent-to-BMI MAC correlation
- osac-operator feedback controller: VIP sync to fulfillment-service

### Integration Tests

- E2E: create Cluster with explicit network_attachment, verify cluster provisioned on correct subnet
- E2E: create Cluster with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created for API and ingress, DNAT rules functional
- E2E: create Cluster with `--external-ip-attachment`, verify full connectivity (ExternalIP + ExternalIPAttachment for API and ingress)
- E2E: delete Cluster with auto-provisioned resources, verify ExternalIPAttachments and ExternalIPs cleaned up
- E2E: create Cluster with omitted network_attachment, verify default Subnet + SecurityGroup populated
- E2E: VIP feedback loop — verify template writes VIPs to ClusterOrder status, fulfillment-service syncs to Cluster, ExternalIPAttachment controller creates DNAT

### Tricky Test Cases

- Multiple node sets sharing the same subnet (verify correct fabric interface resolution per node set from BareMetalInstanceType)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify finalizer retry, eventual orphan cleanup)
- VIP feedback loop failure (Signal RPC fails, fulfillment-service does not sync VIPs)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachment`, `auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`) implemented in fulfillment-service
- [ ] Operator CRD updated with `NetworkAttachment`, `APIEndpoint`, `IngressEndpoint` fields
- [ ] BareMetalWorkerReconciler (OSAC-2135) implemented — on-demand BMI creation with enriched network_attachment
- [ ] Agent-to-BMI MAC correlation and NodePool labeling implemented
- [ ] VIP feedback loop (template → ClusterOrder → fulfillment-service → Cluster) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] Template changes (remove cluster_infra/external_access, add MetalLB VIP provisioning) completed
- [ ] Integration tests pass (E2E coverage for network_attachment, auto ExternalIP attachment, VIP feedback)
- [ ] Documentation: API reference, user guide for simplified cluster creation

GA criteria:
- [ ] k8s_manager implementation (OSAC-1511 or OSAC-1717) delivered and production-tested
- [ ] Multi-job tracking (OSAC-1459) implemented and stable
- [ ] Dispatcher infrastructure (OSAC-1457, OSAC-1458, OSAC-1460) delivered
- [ ] BareMetalInstanceType with `network_ports` (BareMetalNetworkPortSpec) implemented and tested
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (`network_attachment`, `auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`) are additive
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
- Auto-provisioned ExternalIP resources remain (manual cleanup required if not needed)

Acceptable downgrade steps:
- Delete Clusters using new field
- Re-create using old flow (no network_attachment field)
- Manually delete orphaned auto-provisioned resources (ExternalIP, ExternalIPAttachment labeled `osac.openshift.io/auto-created: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service, osac-operator, and osac-aap are deployed together in the same namespace and upgraded atomically (all controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not send `--network-attachment` flag → server populates default Subnet + SecurityGroup
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

**Cause:** Subnet not found, not Ready, or BM-only deployment (no k8s_manager)

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. If BM-only deployment, tenant must create Cluster in a deployment with k8s_manager configured

### Symptom: Auto-provisioned ExternalIP not cleaned up after Cluster deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-created: "true"` with no parent

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

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running clusters

## Infrastructure Needed

- AAP execution environment with `osac.templates.ocp_4_17_small` role updated (remove cluster_infra/external_access, add MetalLB VIP provisioning)
- k8s_manager Ansible role (OSAC-1511 or OSAC-1717) for CUDN overlay provisioning
- fabric_manager Ansible role with the generic `move_network_attachment` primitive (OSAC-2081); a provisioned provisioning network segment for BMaaS BMI provisioning
- Integration test environment with CUDN or EVPN fabric
- BareMetalInstanceType test data with `network_ports` (BareMetalNetworkPortSpec)

## Dependencies

| Dependency | Jira | Status |
|-----------|------|--------|
| Dispatcher core | OSAC-1457, OSAC-1458, OSAC-1460 | Closed |
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
| BareMetalWorkerReconciler (on-demand BMI provisioning + networking) | OSAC-2135 | New |
| BM provisioning flow — reconcileNetworking dispatcher logic | OSAC-2047 | Closed |
| CLI --network-attachment for Cluster | OSAC-2076 | New |
| Integration test | OSAC-2078 | New |
| Fabric manager `move_network_attachment` role (generic port move) | OSAC-2081 (Netris BM) | Closed |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed | OSAC-1201 | New |
| Remove cluster_infra / external_access step collection dispatch | Not tracked | **GAP** |
| Remove NETWORK_STEPS_COLLECTION dependency | Not tracked | **GAP** |
| fulfillment-service: resolve interface from BareMetalInstanceType (fabric_interface) | Not tracked | **GAP** |
