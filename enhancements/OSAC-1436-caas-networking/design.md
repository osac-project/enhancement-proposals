---
title: caas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1436
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "K8s-only Networking Manager: /enhancements/OSAC-1433-k8s-only-k8s-manager"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking — Cluster Networking via OSAC Networking API

CaaS networking provides tenant-controlled cluster node networking via VirtualNetwork + Subnet attachments, BM-based node sets with fabric interface resolution from BareMetalInstanceType, MetalLB VIP provisioning, and auto-provisioned external access (ExternalIP + ExternalIPAttachment) for cluster API and ingress endpoints.

CaaS is supported in connected single-hub Fabric-only, K8s-only, and
combined-manager deployments. The selected manager profile provides the
endpoint-VIP, BM-worker, and network reachability operations. A NATGateway is
required only when the tenant VirtualNetwork and management cluster have no
direct route; in that case the VirtualNetwork must have a Ready NATGateway.
In a combined-manager deployment, the
K8s manager creates the MetalLB IPAddressPool alongside the K8s overlay. In a
BM-only deployment, the Subnet controller creates and removes the pool using
the fabric-level networking path. A topology with neither a direct route nor
a Ready NATGateway is rejected for CaaS cluster creation. This is a
CaaS-specific readiness prerequisite and does not change the shared NATGateway
resource contract for other workloads.

The combined-manager path uses the configured k8s manager. The BM-worker flow
uses the shared CaaS contract for a Subnet whose NetworkClass uses
`cudn_evpn`; if the physical port move or EVPN transport integration is not yet
implemented, the normal provider AAP operation completes as a successful
no-op. CaaS does not reject the Cluster because of a manager/service support
combination.

CaaS uses the selected Subnet and any explicitly/default-resolved workload
SecurityGroups through every selected manager. The complete SecurityGroup and
NetworkACL contracts are required. The effective NetworkACL for a CaaS Subnet
is Ready only after every selected manager has reconciled it. Native
Kubernetes NetworkPolicy alone is not sufficient for either OSAC policy
contract.

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture (NetworkClass, dispatcher, infrastructure-agnostic subnets, resource hierarchy); this document defines how CaaS consumes that architecture.

Shared field types, formats, presence rules, allowed values, and validation
are defined by the [Unified Networking field contract](/enhancements/OSAC-1433-unified-networking/design.md#field-types-formats-and-validation).

The shared networking resource model and IPv4-only scope are defined by the
[Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).
The connected-only deployment boundary, including the exclusion of air-gapped
deployments, is defined by the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary).
The shared operation contract is defined by [Supported Operations and
Immutability](/enhancements/OSAC-1433-unified-networking/design.md#supported-operations-and-immutability).

CaaS inherits the Unified Networking [strict dependency-ready creation
contract](/enhancements/OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation): the resolved Subnet, SecurityGroups,
effective NetworkACL, template/node-set inputs, and any required NATGateway
must already be Ready before Cluster or private worker admission. The
OSAC-owned automatic ExternalIP/ExternalIPAttachment pair is the only
allowlisted Pending-child exception; CaaS does not create a Cluster, worker,
or NATGateway merely to wait for a Pending network dependency.

Cluster provisioning uses the OSAC Networking API for all networking lifecycle — tenants place clusters on their VirtualNetworks via `network_attachment` (`ClusterNetworkAttachment`), the `BareMetalWorkerReconciler` creates on-demand `BareMetalInstance` objects via the BMaaS private gRPC API (BMaaS owns the fabric port move and IP assignment as part of BMI provisioning), and a VIP feedback loop enables auto-provisioned external access for cluster API and ingress endpoints. See [PRD](prd.md) for detailed requirements and [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md) for the full provisioning design.

## Motivation

Clusters require tenant-controlled networking to enable:
- Placing clusters on shared or isolated VirtualNetworks
- Automatic agent port configuration (provisioning network → tenant network) during cluster creation
- VIP feedback loop for cluster API/ingress endpoints to enable DNAT via ExternalIPAttachment
- Auto external access (ExternalIP + ExternalIPAttachment) for single-call cluster provisioning with inbound connectivity

### Goals

- Move cluster networking lifecycle to the OSAC Networking API (VirtualNetwork, Subnet, SecurityGroup, NetworkACL)
- Tenant-controlled cluster node subnet placement via the singular
  `ClusterSpec.network_attachment` field, whose value is a
  `ClusterNetworkAttachment`
- BM-based node sets with fabric interface resolution from BareMetalInstanceType (OSAC-1201)
- On-demand BareMetalInstance creation via BMaaS private gRPC API; BMaaS owns the fabric port move and IP assignment as part of BMI provisioning (OSAC-2135)
- VIP feedback loop: template provisions MetalLB VIPs → ClusterOrder status → fulfillment-service → Cluster → ExternalIPAttachment controller
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call API/ingress external access
- Remove the legacy fabric and agent step collections from CaaS networking

### On-Demand BMI Provisioning Model (OSAC-2135)

Per [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), CaaS provisions bare-metal worker nodes **on demand** via the BMaaS private gRPC API — the static pre-boot agent pool is removed. A dedicated `BareMetalWorkerReconciler` in osac-operator creates `BareMetalInstance` objects for each requested worker. Each BMI references a RHCOS DiskImage and carries discovery ignition inline from a cluster-specific InfraEnv.

**BMaaS owns the full provisioning lifecycle** including networking:
1. BMaaS provisions the host on the **provisioning network** (inventory → OS provisioning via DiskImage + ignition)
2. BMaaS moves the host's fabric port **provisioning network → tenant network** (`reconcileNetworking` dispatches `move_network_attachment` after provisioning completes)
3. BMaaS reboots the host so the OS re-DHCPs on the tenant network (`reconcileReboot`)
4. BMaaS discovers the tenant-network IP via DHCP lease query (`reconcileIPDiscovery`)
5. The full assisted-installer cluster installation begins on the tenant network: the host registers as an Agent with assisted-service, performs hardware discovery, runs the OpenShift installation, and reports progress — all from scratch on the tenant network

The `BareMetalWorkerReconciler` reads the singular typed
`ClusterNetworkAttachment` from `ClusterOrder.spec.networkAttachment` and
converts it into one `BareMetalNetworkAttachment` in the private BMaaS
`network_attachments` list, using the immutable `fabric_interface` stored on
the node set by the fulfillment-service. CaaS never dispatches
`move_network_attachment` directly — that is BMaaS's responsibility as part of
BMI provisioning. On cluster deletion, the controller calls
`BareMetalInstances.Delete`; BMaaS handles full host cleanup including
returning the fabric port to the provisioning network.

### Non-Goals

- VMaaS or BMaaS networking (this EP covers CaaS only)
- VM-based cluster node sets (v0.2 supports BM node sets only; VM worker nodes require HyperShift ↔ CUDN integration not in scope)
- DNS API (DNS record creation stays inline in the template until DNS API is implemented)
- Provider-side physical interface resolution (one tenant attachment per cluster → one subnet; each node set resolves its fabric interface from its BareMetalInstanceType)
- Dispatcher infrastructure implementation (deferred to Unified Networking EP implementation)

## Proposal

### Workflow Description

#### Phase 1: Tenant Creates Networking Resources

These steps are identical to VMaaS/BMaaS — the networking API is uniform.

1. **Create VirtualNetwork:**
   ```bash
   osac create virtualnetwork --cidr 10.0.0.0/16 --name my-net
   ```
   Dispatcher → one `create_virtual_network` job for each configured manager

2. **Create Subnet:**
   ```bash
   osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 --name my-subnet
   ```
   Dispatcher → one job for each configured manager; a Fabric target creates the fabric
   segment and a K8s target creates the overlay. The Subnet becomes Ready only
   after every selected target succeeds.

3. **Create policy resources:**
   ```bash
   osac create network-acl --virtual-network my-net --subnet my-subnet --name my-nacl \
     --rule "action=allow,direction=ingress,protocol=tcp,port=443,source-cidr=0.0.0.0/0"
   ```
   The NetworkACL is associated with the Subnet and is inherited by workloads
   placed on that Subnet; it is not part of the Cluster attachment. A
   SecurityGroup is selected by the Cluster attachment and is propagated to
   each BMaaS worker attachment.
   Dispatcher → every configured manager. If both are configured, both internal
   targets must reconcile. A temporary unfinished operation may use a
   successful no-op AAP role.

#### Phase 2: Tenant Creates Cluster

4. **Create Cluster:**
    ```bash
    # Explicit networking:
    osac create cluster --template ocp_4_17_small \
      --network-attachment subnet=my-subnet \
      --node-set-size compute=3 --name my-cluster

    # Or with defaults + auto external access:
    osac create cluster --template ocp_4_17_small \
      --external-ip-attachment \
      --node-set-size compute=3 --name my-cluster
    ```

    The template owns the node-set names and
    `baremetal_instance_type`; the request may provide only the permitted
    size values for those existing node sets.

5. **fulfillment-service:**
    - If `ClusterSpec.network_attachment` (a `ClusterNetworkAttachment`) is omitted or an empty message: populates the tenant default Subnet and the default SecurityGroup only when that Subnet is in the tenant default VirtualNetwork. If present without a subnet or SecurityGroup list, defaults only the missing fields (see Default Networking PRD)
    - Validates the `ClusterNetworkAttachment`:
      - Subnet exists, is Ready
      - The Subnet has an effective, Ready NetworkACL after every selected manager has reconciled it
      - Every referenced/default SecurityGroup is Ready, unique, same-tenant, and in the Subnet's VirtualNetwork
      - If the supplied Subnet is outside the tenant default VirtualNetwork and
        no compatible SecurityGroup is supplied, reject with `InvalidArgument`;
        never apply the default-VN SecurityGroup. A Subnet without a Ready
        effective ACL is rejected for Cluster placement with `FailedPrecondition`.
    - For each node_set: resolves `baremetal_instance_type` → BareMetalInstanceType → picks first port with `role=fabric` from `network_ports[]` and stores as `fabric_interface` on the node set definition in the ClusterOrder spec
    - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool, creates two ExternalIPs (API + ingress) and two ExternalIPAttachments with the canonical `osac.openshift.io/auto-created: "true"` marker and an exact immutable Cluster owner relationship — all in the same DB transaction, all starting in **Pending** state. The ExternalIPs may also expose `osac.openshift.io/auto-created-for: <cluster-id>` for indexed discovery, but that label is not ownership proof. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. The ExternalIPAttachments transition to Ready once VIPs are populated (see Phase 3). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the shared two-phase flow and phased requeue cleanup pattern.
    - Creates Cluster record with empty `api_endpoint` / `ingress_endpoint`
    - Creates ClusterOrder CR with the resolved singular `ClusterNetworkAttachment` in `spec.networkAttachment`

6. **osac-operator ClusterOrder controller:**
    - Creates namespace, ServiceAccount, RoleBindings (same as today)

    **a. Triggers AAP workflow** to create the HostedCluster and NodePool CRs.

    **b. `BareMetalWorkerReconciler`** (runs after the ClusterDeployment exists, per OSAC-2135):
    - Creates a cluster-specific `InfraEnv` CR for discovery ignition
    - For each bare-metal worker requested, creates a `BareMetalInstance` via the BMaaS private gRPC API, passing a one-entry `network_attachments` list of `BareMetalNetworkAttachment` values enriched from `ClusterOrder.spec.networkAttachment` with its typed SecurityGroup references and the immutable `fabric_interface` already stored on the node set by the fulfillment-service (step 5) — the controller does not re-resolve from BareMetalInstanceType to avoid divergence if the profile changes after cluster creation
    - BMaaS provisions each host (DiskImage + ignition), moves its fabric port from provisioning network → tenant network, reboots, and discovers the tenant-network IP via DHCP lease query — all as part of BMI provisioning (inventory → provisioning → networking → reboot → IP discovery)
    - The controller correlates registered Agents to BMIs via MAC address and labels them for NodePool selection
    - If an Agent does not register within a configurable timeout (default: 30 minutes), the controller sets the worker phase to `Failed` with reason `AgentRegistrationTimeout` and retries with escalating backoff (see OSAC-2135 for full retry logic)

    > **Tenant-network reachability prerequisites.** After the port move, cluster installation runs entirely on the tenant network. Where the tenant V-Net and the management cluster are in separate VPCs with no direct network path, all communication between them traverses the external network: outbound via a Ready NATGateway/SNAT path, inbound to the management cluster's external ingress. This applies to assisted-service registration, container image pulls, and post-installation kubelet-to-kube-apiserver heartbeats. All dependencies (container images, RHCOS, OCP release payload) must be pullable from the tenant network via the same egress path. NetworkACL egress rules must allow outbound `:443`. `AgentRegistrationTimeout` catches tenant-to-assisted-service egress failures (the agent cannot register if it cannot reach assisted-service). A topology without both a direct route and a Ready NATGateway is rejected before Cluster persistence.

7. **CaaS template creates the HostedCluster + NodePool; BareMetalWorkerReconciler provisions workers.**

    The template's `install.yaml` changes:

    **a. Create HostedCluster + NodePools:**
    - AAP creates HyperShift HostedCluster + NodePool CRs
    - No agent selection or switch port configuration — the `BareMetalWorkerReconciler` handles worker provisioning on-demand via BMaaS (step 6b)
    - Host-side networking handled by DHCP — no NMState or static config needed

    **b. MetalLB VIP provisioning (REPLACES `external_access` step):**

    The VN and Subnet already exist (tenant created them in steps 1-3). External access (ExternalIP, ExternalIPAttachment) is auto-provisioned or managed separately by the tenant. When the VN has no direct route to the management cluster, a Ready NATGateway must already exist on the VN; CaaS does not create one per cluster. If a direct route exists, no NATGateway is required. The template:
    - Creates MetalLB LoadBalancer Services for API server + ingress VIPs
    - MetalLB allocates VIPs from the IPAddressPool created at subnet creation: by the k8s_manager alongside the overlay in a combined-manager deployment, or by the Subnet controller through the fabric-level path in a BM-only deployment
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
      1. ExternalIP must be Allocated by every selected manager for that
         ExternalIP
      2. ClusterOrder must have `status.apiEndpoint` populated (VIP allocated by MetalLB, discovered by template in step 7b)
    - Once both are met: reads ClusterOrder's `apiEndpoint` → 10.0.1.200
    - Calls the external-IP attachment operation on every selected manager for
      that ExternalIPAttachment
    - The selected manager implementation(s) create DNAT: api-ip
      (203.0.113.10) → 10.0.1.200
    - ExternalIPAttachment transitions from **Pending** to **Ready**

11. Same for ingress ExternalIPAttachment:
    - Requeues until ExternalIP is Allocated AND ClusterOrder's `status.ingressEndpoint` is populated
    - Reads ClusterOrder's `ingressEndpoint` → 10.0.1.201
    - Creates DNAT: ingress-ip (203.0.113.11) → 10.0.1.201
    - Transitions to **Ready**

#### Deletion (reverse order)

12. **Delete Cluster:**
    - **Auto-provisioned cleanup (osac-operator ClusterOrder controller):** Phased requeue deletes only ExternalIPAttachments and ExternalIPs with the canonical auto-created marker and an exact immutable Cluster owner. It deletes attachments first, waits for full removal, then deletes ExternalIPs, waits, and proceeds only after cleanup succeeds. A target reference or label alone is not sufficient ownership proof. See [Unified Networking — auto-provisioned resource cleanup](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types).
    - **Manually created resources are NOT cleaned up** — tenant manages their lifecycle. A manually created ExternalIPAttachment that targets the Cluster remains a reverse reference and blocks Cluster deletion until the tenant deletes the attachment; it is not detached or changed to Pending implicitly.
    - **Default networking resources (VN, Subnet, SecurityGroup, NetworkACL, NATGateway) are NOT cleaned up** — tenant-scoped and shared. Subnet deletion reports Cluster and NetworkACL blockers; VirtualNetwork deletion reports Subnet, SecurityGroup, NetworkACL, and NATGateway blockers.
    - ClusterOrder controller triggers AAP delete workflow
    - CaaS delete template:
      - Deletes MetalLB LoadBalancer Services
      - Deletes HyperShift HostedCluster + NodePools
      - DNS cleanup
    - ClusterOrder finalizer actively deletes every BMI listed in `status.workers[]` via `BareMetalInstances.Delete` on the BMaaS private API (30 s context deadline per call). The call returns once the delete is accepted; BMaaS handles full host cleanup asynchronously (deprovision, fabric port return to provisioning network). The controller retains each worker entry in `status.workers[]` in `Deleting` phase and polls BMI state on subsequent reconciliation cycles until the BMI is confirmed gone — only then is the entry removed. If the deadline is exceeded or the call fails, the controller retries on the next requeue (controller-runtime exponential backoff); `BareMetalInstances.Delete` is idempotent, so retries are safe. The finalizer holds until all `status.workers[]` entries are confirmed deleted. The InfraEnv CR is garbage collected via its ownerReference to the ClusterOrder (see OSAC-2135).
    - Removes ClusterOrder finalizer

13. **Tenant deletes networking resources** (independently and leaf-first):
    - Delete tenant-managed ExternalIPAttachments, SecurityGroups, NetworkACLs, and NATGateways first; each delete reports direct blockers and never cascades to its referenced resources.
    - Delete ExternalIPs only after all consuming ExternalIPAttachments and NATGateways are fully gone; every selected manager then releases its allocation.
    - Delete Subnets only after all Cluster, BMI, VM, and NetworkACL association blockers are fully gone.
    - Delete VirtualNetworks only after all Subnets, SecurityGroups, NetworkACLs, and NATGateways are fully gone.
    - A child that is deleting but not yet archived still blocks its parent. All accepted deletes use the shared transactional blocker and locking contract.

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

The tenant provides a single `ClusterNetworkAttachment` with an optional
`subnet` and `security_groups` list — no NetworkACL, node-set, or interface
field. The effective NetworkACL is inherited
from the selected Subnet. The
`BareMetalWorkerReconciler` resolves the interface from the
BareMetalInstanceType for each node set:

1. For each node set in the cluster spec (e.g., "gpu"), read `ClusterSpec.node_sets["gpu"].baremetal_instance_type` = "bm-standard"
2. BareMetalInstanceType "bm-standard" has network_ports:
   ```
   [{name: "data-0", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "data-1", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "mgmt-0", role: "management", type: "Ethernet", speed: "1Gbps"}]
   ```
3. The controller picks the first port with `role=fabric` → `data-0`, uses it as the `interface` field on the per-BMI `BareMetalNetworkAttachment`
4. BMaaS receives the `BareMetalNetworkAttachment` (subnet + interface + primary) on the BMI Create call and handles the fabric port move as part of provisioning (see [On-Demand BMI Provisioning Model](#on-demand-bmi-provisioning-model-osac-2135))

For the current CaaS contract, **BM node sets only are supported**. VM-based
cluster node sets are rejected by validation.

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
- Legacy step collections and their networking functionality are replaced by
  the OSAC Networking API and generic fabric-manager roles.

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

### CLI networking contract

CaaS inherits the shared [Unified Networking CLI contract](../OSAC-1433-unified-networking/design.md#normative-cli-contract).
The Cluster-specific mapping is:

| API field | CLI form | Allowed values |
|---|---|---|
| `spec.network_attachment` | One optional `--network-attachment` | Omitted or one structured attachment; a second option is rejected |
| `ClusterNetworkAttachment.subnet` | `subnet=<name>` inside the attachment value | Optional; omission receives the tenant default Subnet; an attachment with no explicit Subnet is completed without replacing any explicit SecurityGroup list |
| `ClusterNetworkAttachment.security_groups` | `security-groups=<name>[,...]` inside the attachment value | Optional; omission receives the tenant default SecurityGroup only when the resolved Subnet is in the tenant default VirtualNetwork; explicit list is typed, unique, same-tenant, same-VN, and Ready |
| `auto_external_ip_attachment` | `--external-ip-attachment` | Presence means `true`; omission means `false`; create-time only |

The canonical explicit command is:

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet \
  --node-set-size workers=3 --name my-cluster
```

The CLI must not expose `--network-attachments`, `network-acls=...`,
`interface=...`, `primary=...`, per-node-set network values, or a VM-style
multi-NIC mode.
The one attachment applies to the entire Cluster; the system resolves one
fabric interface per node set from the template-owned BareMetalInstanceType.
Omitting the option invokes the tenant default Subnet and default
  SecurityGroup. The CLI constructs typed local Subnet and
SecurityGroup references and sends the singular resource-specific
`ClusterNetworkAttachment` message. NetworkACL association is managed through
the NetworkACL resource. Network fields and
`auto_external_ip_attachment` cannot be changed through update or patch
commands; delete and recreate is required.

### API Extensions

#### Proto (fulfillment-service)

```protobuf
message ClusterNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  repeated SecurityGroupLocalReference security_groups = 2; // omitted -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}
// Note: fabric_interface is system-populated ONCE on each node set definition
// by the fulfillment-service at cluster creation (resolved from the node set's
// BareMetalInstanceType, immutable after creation). The BareMetalWorkerReconciler
// reads this stored value — it does not re-resolve from BareMetalInstanceType.

message ClusterSpec {
  ClusterTemplateReference template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;
  // ... existing fields ...
  ClusterNetworkAttachment network_attachment = 9;   // NEW, optional, singular; API field name is network_attachment
  optional bool auto_external_ip_attachment = 10;     // NEW, create-time only; omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment for API and ingress
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
    NetworkAttachment *ClusterNetworkAttachment `json:"networkAttachment,omitempty"` // private CRD mapping of ClusterSpec.network_attachment; empty message -> tenant default Subnet and SecurityGroup
}

type ClusterNetworkAttachment struct {
    Subnet         *SubnetLocalReference `json:"subnet,omitempty"` // resolved before provisioning
    SecurityGroups []SecurityGroupLocalReference `json:"securityGroups,omitempty"` // omitted/empty -> tenant default SecurityGroup only for the tenant default VirtualNetwork
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

CaaS applies the shared [Unified Networking validation
pipeline](/enhancements/OSAC-1433-unified-networking/design.md#validation-and-enforcement-pipeline)
and adds cluster-wide and
node-set-specific checks. Validation runs before creating the Cluster and
again before creating any private BMaaS worker request.

**Cluster attachment shape and defaulting:**

- `network_attachment` is singular. The API accepts an omitted field or an
  empty message for default resolution. Any repeated or additional tenant
  attachment representation is invalid.
- A supplied attachment may contain only the shared `subnet` and
  `security_groups` fields. NetworkACLs, `fabric_interface`, physical port names, and
  per-node-set attachment selectors are not tenant input and are rejected if
  they appear in the public Cluster request.
- Omitted/empty input resolves the tenant default Subnet and default
  SecurityGroup. The effective NetworkACL is the ACL associated
  with that Subnet; it must be Ready, be IPv4, be in
  the effective tenant/project, and belong to one VirtualNetwork. Every
  SecurityGroup reference must be Ready, same-tenant, same-VN, and unique.
- The resolved attachment is stored once in `ClusterOrder.spec.networkAttachment`.
  The worker controller must not append a second tenant attachment while
  enriching worker requests.

**Cluster and node-set validation:**

- The selected Cluster Template must be compatible with the supported CaaS
  node model. v0.2 accepts BM node sets only; VM-based node sets and a
  multi-NIC node request are rejected before networking resources are
  created.
- The resolved `ClusterSpec.node_sets` map must have exactly the same keys as
  the selected ClusterTemplate's authoritative `spec.node_sets` map. Missing
  template node sets, extra caller-supplied node sets, and renamed node-set
  keys are rejected before persistence. For every key, the submitted
  `baremetal_instance_type` must equal the Template's typed reference;
  Catalog policy and tenant input may change only the permitted `size` value.
  The server must not accept a caller-provided hardware reference merely
  because it independently names a Ready BareMetalInstanceType.
- Every node set must identify a valid `baremetal_instance_type` in the
  permitted scope. The referenced BareMetalInstanceType must be Ready/usable,
  contain at least one ordered port with role `fabric`, and contain no
  malformed port definitions.
- For each node set, fulfillment-service selects the first ordered `fabric`
  port and persists it as the immutable `fabric_interface`. It must reject a
  missing fabric port, a lifecycle-only profile, or a node set whose
  interface cannot be represented in the BMaaS attachment contract.
- The tenant cannot select or override `fabric_interface`. Catalog policy,
  Template defaults, and tenant network input may govern only the tenant
  Subnet and SecurityGroup list; the effective NetworkACL is inherited from
  the Subnet association.
- The same resolved Subnet and SecurityGroup list apply to every node set.
  Per-node-set Subnet, ACL, SecurityGroup, or tenant-interface overrides are
  rejected. The node set's
  stored `fabric_interface` may differ by BareMetalInstanceType, but it does
  not create another tenant network attachment.
- The resolved attachment and every network-owned nested field are immutable
  after Cluster creation. Changing them requires deleting and recreating the
  Cluster; changing a BareMetalInstanceType later does not re-resolve an
  existing Cluster's stored interface.

**Private BMaaS worker validation:**

- Every worker create request contains exactly one
  `BareMetalNetworkAttachment` with the Cluster Subnet, the Cluster's typed
  SecurityGroup list, the immutable node-set `fabric_interface`, and implicit
  `primary: true`.
- The private CaaS request carries the Cluster's effective tenant/project as
  trusted reference-resolution context. BMaaS resolves the local Subnet and
  SecurityGroup references in that source scope and the worker receives the
  effective NetworkACL through the Subnet association; it does not compare the source tenant with the
  destination BMI's builtin `system` tenant. This exception is limited to
  CaaS-created BMIs and does not weaken tenant-facing BMaaS validation.
- BMaaS remains authoritative for the final physical-interface validation:
  the port must still exist in the referenced BareMetalInstanceType, be
  tenant-attachable, and not have role `lifecycle`. A private caller cannot
  bypass BMaaS validation by using the ClusterOrder CR directly.
- The worker controller does not re-resolve the interface after ClusterOrder
  creation. If the stored interface becomes unavailable, worker provisioning
  fails/retries with a clear condition; it does not silently choose another
  port.
- Worker deletion waits for BMaaS to remove the worker and return the selected
  port to the provisioning network. The ClusterOrder finalizer must not
  release the Subnet or related network resources while worker BMIs remain.

**External access and VIP validation:**

- Before persisting a Cluster, validation must confirm that the deployment has
  a valid CaaS endpoint-VIP path: the NetworkClass must provide the CaaS/MetalLB
  VIP path through the shared `metallb_vip_prefix_length` contract, and the
  selected topology must provide the required worker and network reachability
  prerequisites. When the tenant and management networks have no direct route,
  the resolved VirtualNetwork must have a Ready NATGateway. A deployment
  without that path is rejected; the request is not persisted. These are
  service/topology prerequisites, not tenant-defined manager capability names.
- The reachability check is provider-owned and evaluates the resolved tenant
  VirtualNetwork against the management cluster's connected routing state.
  `direct_route_available == true` is accepted without NAT; when it is false,
  validation requires a Ready NATGateway on that VirtualNetwork. If the
  provider cannot establish either result, or reports no direct route and no
  Ready NATGateway, validation returns `FailedPrecondition` before any
  Cluster, worker, VIP, or ExternalIP records are persisted. There is no
  tenant-settable route override and no fallback to an unready NATGateway.
- `auto_external_ip_attachment` is create-time-only. When true, the request
  must reserve two IPv4 ExternalIPs atomically: one for `API` and one for
  `INGRESS`. Pool exhaustion or inability to reserve two addresses rejects
  the entire Cluster create and leaves no parent or child records.
- The two ExternalIPs must be distinct, and each ExternalIPAttachment must
  reference the same Cluster with the matching endpoint enum. A Cluster
  target with `UNSPECIFIED`, a Compute/BM target with `API`/`INGRESS`, or
  duplicate API/Ingress attachments is rejected.
- ExternalIPAttachment dispatch waits independently for the corresponding
  ExternalIP to be `Allocated` and the matching ClusterOrder endpoint to be
  populated. API DNAT uses only `status.apiEndpoint`; ingress DNAT uses only
  `status.ingressEndpoint`.
- Each discovered endpoint must be canonical IPv4, belong to the resolved
  Subnet/MetalLB address pool, be distinct from the other endpoint, and be
  stable for the lifetime of the Cluster. Empty, IPv6, duplicate, or
  out-of-subnet endpoint status is rejected and does not activate DNAT.
- The template must not report the Cluster Ready before the required VIP
  resources and endpoint statuses are available. The ExternalIPAttachment
  controller requeues rather than dispatching DNAT with an empty endpoint.

**Validation errors:**

- Field paths identify the failure: `spec.network_attachment.subnet`,
  `spec.node_sets[<name>].baremetal_instance_type`, or the corresponding
  `target_endpoint` field. No invalid input is persisted.

#### Catalog Item interaction

Catalog Item v2 may govern the singular `network_attachment` field as a whole
structured `ClusterNetworkAttachment` value. It may lock the attachment or make it editable with an
optional default. Catalog resolution occurs before tenant default networking:
tenant input wins for an editable policy, then the Catalog default and Template
defaults are applied. Finally, missing attachment Subnet and SecurityGroup
fields receive the tenant's defaults. The tenant default
SecurityGroup is used only when the resolved Subnet belongs to the tenant
default VirtualNetwork; a non-default-VirtualNetwork Subnet without a
compatible explicit group is rejected. The effective NetworkACL is inherited
from the selected Subnet and supplied fields are preserved.

The Catalog Item governs only the tenant-facing Subnet and SecurityGroup
references.
`fabric_interface` is derived separately for each node set from
BareMetalInstanceType and is never a Catalog field. A shared Catalog Item therefore cannot
lock or default tenant-local network references; it must leave the attachment
editable or ungoverned. The normal CaaS rules still apply: one attachment per
Cluster, all node sets share its Subnet, and all referenced objects belong to
the same VirtualNetwork.

The editable policy applies only during Cluster creation. After creation, the
resolved attachment and every network-owned field are read-only. Catalog Item
definitions and metadata remain governed by Catalog Items v2 and are not
changed here.

#### Template Changes

**osac.templates.ocp_4_17_small/install.yaml:**
- Remove: `osac.service.cluster_infra` call
- Remove: `osac.service.external_access` call
- Remove: agent selection logic (moved to operator)
- Add: create HostedCluster + NodePools; the worker reconciler binds Agents after on-demand BMaaS provisioning
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
| osac-operator BareMetalWorkerReconciler | Create on-demand BareMetalInstances via BMaaS private gRPC API with an enriched `network_attachments` list of `BareMetalNetworkAttachment` values (typed subnet reference from ClusterOrder `networkAttachment` + immutable `fabric_interface` from the node set, resolved once by fulfillment-service; the effective NetworkACL is inherited from the Subnet); correlate Agents to BMIs via MAC; delete BMIs on scale-down/cluster deletion. BMaaS owns the fabric port move and IP discovery as part of BMI provisioning (OSAC-2135) |
| osac-operator ClusterOrder controller | Create namespace/SA/RoleBindings, trigger AAP workflow, aggregate worker status; the AAP template does not receive pre-selected agents |
| osac-operator ClusterOrder feedback controller | Watch ClusterOrder status, Signal fulfillment-service when VIPs appear |
| osac-operator ExternalIPAttachment controller | Read ClusterOrder `apiEndpoint`/`ingressEndpoint` (MetalLB-allocated, template-discovered) from status, dispatch DNAT to every selected manager |
| AAP template (ocp_4_17_small) | Create HostedCluster+NodePools; the worker reconciler provisions and binds on-demand BMIs/Agents, while the template provisions MetalLB VIPs and writes VIPs to ClusterOrder status |
| BMaaS (bare-metal-fulfillment-operator) | Owns full BMI provisioning lifecycle including inventory → OS provisioning → fabric port move (provisioning network → tenant) → reboot → DHCP lease query IP discovery; returns fabric port to provisioning network on BMI deletion |
| selected manager(s) | Move network attachments, create/delete external-IP attachments (DNAT), and create/delete NATGateway |
| k8s_manager (Ansible role, combined-manager deployments) | create/delete_subnet (the configured k8s overlay) and create/delete the MetalLB IPAddressPool — called at subnet creation/deletion, NOT at cluster creation |
| Subnet controller (BM-only deployments) | create/delete the MetalLB IPAddressPool through the fabric-level path — called at subnet creation/deletion, NOT at cluster creation |

#### Auto-Provisioned Resource Lifecycle

- Resources carry the canonical `osac.openshift.io/auto-created: "true"`
  marker and an exact immutable Cluster owner relationship.
- The parent cleanup finalizer deletes in order: ExternalIPAttachment →
  ExternalIP, waiting for each resource to disappear.
- The ExternalIPPool and tenant-created resources are never cascaded.
- On cleanup failure, the finalizer remains and the parent stays `Deleting`; it
  is not removed to create an orphan.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent Cluster
- No new authentication or authorization changes
- SecurityGroup enforcement follows the [Unified Networking SecurityGroup rule
  semantics](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup-rule-semantics),
  and NetworkACL enforcement follows the shared stateless semantics for the
  effective Subnet ACL. The deployment `permit` baseline is separate from the
  tenant default ACL; native Kubernetes NetworkPolicy alone is not a substitute
  for either OSAC policy contract.

### Failure Handling and Recovery

#### ClusterOrder Controller Reconciliation Failures

- A Cluster create request with a missing Subnet uses the normal
  visibility-safe `NotFound`/`InvalidArgument` response; a request that
  references an existing Subnet that is not Ready is rejected before Cluster
  or ClusterOrder persistence with `FailedPrecondition`. In a topology without
  a direct route, a missing or non-Ready required NATGateway, or an unavailable
  required MetalLB endpoint-VIP path, is rejected the same way. No Cluster is
  left in Failed or Pending to wait for these dependencies. After valid
  admission, failures in the Cluster's own worker, manager, or endpoint
  provisioning may enter Failed and retry according to that workflow.
- BMI creation failure (BMaaS private API error or no available hosts): worker phase set to `Failed`, controller retries with escalating backoff (see OSAC-2135 retry logic)
- Agent registration timeout (host booted but Agent did not register within 30 min): worker phase set to `Failed` with reason `AgentRegistrationTimeout`, controller deletes the timed-out BMI and retries
- AAP job failure (template execution error): ClusterOrder enters Failed state with AAP job ID in status

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, resource not persisted
- ExternalIP provisioning failure: ExternalIP enters Failed state, Cluster remains in Pending (external access unavailable, cluster may still function without inbound connectivity)
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach cluster (cluster functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- Auto-provisioned resource cleanup permanent failure: the parent remains in
  `Deleting`, the finalizer is retained, and retry/status reporting continues;
  no orphan is intentionally created by removing the finalizer.

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (Cluster with new fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from Cluster to auto-created resources
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected
- Tenant User can view auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via the standard API; their network-owned fields are not editable

### Observability and Monitoring

New structured log events:
- ClusterOrder controller: `WorkerProvisioningStarted` (info),
  `AgentBindingCompleted` (info), `AgentBindingFailed` (error),
  `NetworkAttachmentsConfigured` (info), `VIPsDiscovered` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error), `VIPFeedbackProcessed` (info)

New Kubernetes events on ClusterOrder:
- `AgentsBound`: an on-demand worker Agent was correlated to its BMI and bound
  to the cluster NodePool
- `AgentBindingFailed`: an Agent could not be correlated or bound to its
  on-demand worker
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

**Impact:** MetalLB needs an IPAddressPool CR covering the subnet CIDR to allocate VIPs from. If the selected topology fails to create it at subnet creation, cluster API/ingress endpoints are unreachable.

**Mitigation:** The selected topology creates the IPAddressPool at Subnet creation (the k8s_manager alongside the configured k8s overlay in combined-manager deployments, or the Subnet controller through the fabric-level path in BM-only deployments). Subnet remains Pending until the required overlay/fabric resources and IPAddressPool are confirmed on all hosting clusters.

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

### ~~1. How does the operator correlate and bind worker agents?~~ — Resolved

Resolved: Per OSAC-2135, the `BareMetalWorkerReconciler` creates on-demand `BareMetalInstance` objects via the BMaaS private gRPC API. Agents register automatically after BMI provisioning and are correlated to BMIs via MAC address. The static pre-boot agent pool is removed.

### ~~2. NMState NNCP configuration~~ — Resolved

Resolved: DHCP handles host-side networking for CaaS agents. NMState NNCP
configuration is no longer needed — BMaaS provisions the host on the
provisioning network, moves the selected port to the tenant segment, reboots
the host, and the host receives its tenant IP, gateway, and DNS from the
fabric's DHCP server. The template does not configure static networking.

### ~~3. MetalLB IP pools~~ — Resolved

Resolved: the MetalLB IPAddressPool is created at subnet creation time and is a shared prerequisite for all hosted cluster control planes on that hosting cluster, not a per-cluster resource. In combined-manager deployments, the **k8s_manager creates the pool alongside the configured k8s overlay**. In BM-only deployments, the **Subnet controller creates the pool through the fabric-level path**. The CaaS template creates LoadBalancer Services; MetalLB dynamically allocates VIPs from the pool and announces them. The template discovers the allocated VIPs and writes them to ClusterOrder status.

### ~~4. How does the operator know the fabric_manager name?~~ — Resolved

Resolved: The operator reads the fabric_manager name from the NetworkClass CR. One NetworkClass per deployment, read on first reconcile and cached. The NetworkClass is a K8s CR (not just a fulfillment-service DB object).

### ~~5. Should auto NATGateway treat a Deleting NATGateway as 'does not exist'?~~ — Resolved

Resolved: NATGateway reuse limited to Ready only. Failed/Deleting NATGateways cause the create request to fail with an error. NATGateway auto-provisioning per resource was removed — NATGateway is now a VN default created at tenant onboarding.

### ~~6. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity is checked synchronously during the API call. If exhausted, the call fails atomically. No Failed resource created.

### ~~7. How is the subnet CIDR partitioned between MetalLB VIP allocation and fabric DHCP assignment?~~ — Resolved

Resolved: The MetalLB IPAddressPool uses a reserved sub-range of the subnet CIDR (e.g., the last /28), created at Subnet creation time. In combined-manager deployments the k8s_manager creates the pool alongside the overlay; in BM-only deployments the Subnet controller creates it through the fabric-level path. The fabric manager's DHCP server excludes this range. The sub-range size is configurable on the NetworkClass. This ensures MetalLB VIPs and DHCP-assigned agent IPs never overlap.

### ~~8. What IP addresses do DNS records point to — MetalLB VIPs or ExternalIPs?~~ — Resolved

Resolved: Kubeconfig API address uses the MetalLB VIP directly — workers are on the same subnet and reach it without DNS. External DNS records (api.<cluster>.<domain>, *.apps.<cluster>.<domain>) point to the ExternalIP and are only created when the tenant uses --external-ip-attachment. No bootstrap sequencing issue — workers use VIPs from kubeconfig, not DNS.

## Test Plan

The executable, reviewable plan for CaaS Networking is maintained in
[testplan.md](testplan.md). It covers the singular Cluster attachment, BM
node-set interface resolution, private BMaaS handoff, VIP and ExternalIP
behavior, cleanup, Catalog parity, and unsupported behavior. Shared
networking contracts are covered by the [Unified Networking test
plan](../OSAC-1433-unified-networking/testplan.md).
## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachment`, `auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`) implemented in fulfillment-service
- [ ] Operator CRD updated with `ClusterNetworkAttachment`, `APIEndpoint`,
  `IngressEndpoint` fields
- [ ] BareMetalWorkerReconciler (OSAC-2135) implemented — on-demand BMI creation with an enriched `network_attachments` list of `BareMetalNetworkAttachment` values
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
- Auto-provisioned ExternalIP resources remain protected by their owner
  relationship and parent finalizer until a compatible controller resumes the
  ordered cleanup.

Acceptable downgrade steps:
- Delete Clusters using new field
- Re-create using old flow (no network_attachment field)
- Restore a compatible controller and allow the retained parent finalizer to
  resume `ExternalIPAttachment -> ExternalIP` cleanup. Do not authorize
  deletion from the auto-created label alone; verify the immutable Cluster
  owner relationship and shared dependency guards.

## Version Skew Strategy

### Control Plane Skew

fulfillment-service, osac-operator, and osac-aap are deployed together in the same namespace and upgraded atomically (all controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not send `--network-attachment` flag → server populates the default Subnet; the effective NetworkACL is inherited from that Subnet
- New CLI uses new `--network-attachment` flag → server accepts

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses new `--network-attachment` flag → old server rejects unknown field
- Workaround: omit `--network-attachment` until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: Cluster creation is rejected for networking readiness

**Detection:**
```bash
# Inspect the create response for FailedPrecondition and its dependency details
```

**Cause:** The requested Subnet is missing/not visible or is not Ready, the
required MetalLB endpoint-VIP path is unavailable, or the deployment has no
Ready NATGateway when the selected topology has no direct route.

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure, wait for
   `Ready`, and retry the create request.
3. Verify that the Subnet controller created the MetalLB pool. If the tenant
   and management networks have no direct route, also verify that a Ready
   NATGateway exists on the VirtualNetwork; a direct route does not require a
   NATGateway. For a combined-manager deployment, verify the registered
   `k8s_manager` and its pool-creation status before retrying.

### Symptom: Cluster remains Deleting during auto-provisioned ExternalIP cleanup

**Detection:** `kubectl get cluster` shows the parent in `Deleting`, and
controller logs show a retry for its owned ExternalIPAttachment or ExternalIP.

**Cause:** Cleanup is waiting for a transient backend/API dependency or failed
after deletion was admitted.

**Resolution:**
1. Check Cluster deletion logs (controller logs) for cleanup errors
2. Verify the canonical auto-created marker and exact immutable Cluster owner
   relationship
3. Resolve the backend/API failure and allow reconciliation to delete the
   attachment first and the ExternalIP second; do not remove the finalizer

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
- k8s_manager Ansible role for configured overlay provisioning
- fabric_manager Ansible role with the generic `move_network_attachment` primitive (OSAC-2081); a provisioned provisioning network segment for BMaaS BMI provisioning
- Integration test environment with a supported k8s overlay/fabric combination
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
| ClusterOrder CRD: singular networkAttachment | OSAC-1505 | New |
| ClusterOrder CRD: api/ingress endpoint status | OSAC-2080 | New |
| VIP discovery flow (feedback) | OSAC-1506 | New |
| CaaS template: accept network_attachment + system-resolved per-node interface config | OSAC-1507 | New |
| CaaS template: MetalLB VIP provisioning + write to status | OSAC-2077 | New |
| BareMetalWorkerReconciler (on-demand BMI provisioning + networking) | OSAC-2135 | New |
| BM provisioning flow — reconcileNetworking dispatcher logic | OSAC-2047 | Closed |
| CLI --network-attachment for Cluster | OSAC-2076 | New |
| Integration test | OSAC-2078 | New |
| Fabric manager `move_network_attachment` role (generic port move) | OSAC-2081 (BM networking role) | Closed |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed | OSAC-1201 | New |
| Remove cluster_infra / external_access step collection dispatch | Not tracked | **GAP** |
| Remove NETWORK_STEPS_COLLECTION dependency | Not tracked | **GAP** |
| fulfillment-service: resolve interface from BareMetalInstanceType (fabric_interface) | Not tracked | **GAP** |
