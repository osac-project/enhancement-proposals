---
title: k8s-only-k8s-manager
authors:
  - Dan Manor
creation-date: 2026-09-28
last-updated: 2026-09-29
tracking-link:
  - "https://redhat.atlassian.net/browse/OSAC-2069"
prd:
  - "prd.md"
---

# K8s Manager — K8s-Only

## Summary

This design documents how the `k8s_only` manager implements its supported
networking operations with Kubernetes-native resources: CUDNs, NetworkPolicies,
and MetalLB. The shared manager contract is defined in the
[Unified Networking design](../OSAC-1433-unified-networking/design.md#manager-contract).
See [PRD](prd.md) for full requirements.

## Motivation

The `k8s_only` manager provides tenant networking for KubeVirt workloads using
OVN-Kubernetes and MetalLB. Its resource mapping, role behavior, and limitations
have not been formally documented. This design records the existing role
behavior and the target requirements where implementation changes are needed.
The Unified Networking design describes manager selection and dispatch behavior.

### Goals

- Describe how the k8s-only backend implements supported operations using
  Kubernetes-native resources (CUDNs, NetworkPolicies, MetalLB)
- Establish the supported and unsupported operation set with concrete rejection
  behavior

### Non-Goals

- NATGateway support — the k8s-only backend does not and will not provide SNAT
- Bare-metal networking
- Multi-hub CUDN coordination
- IPv6 or dual-stack

## Proposal

### K8s-Only Behavior

The `k8s_only` composite Ansible role delegates VirtualNetwork and Subnet
operations to `cudn_net`, SecurityGroup operations to `network_policy`, and
ExternalIP operations to `metallb_l2`. VirtualNetwork create and delete are
no-ops; Subnet provisioning creates a Namespace and CUDN. The Unified Networking
design defines how a NetworkClass selects this manager and how the dispatcher
handles unsupported operations. NATGateway has no k8s-only implementation. The
target behavior is to set a Failed condition on the resource before creating an
AAP job. The current NATGateway reconciler does not validate its dispatch plan
before provisioning, so this target still requires controller wiring.

CUDN-based VM attachment does not move a physical port, so this
manager does not implement `move_network_attachment`. The current k8s-only flow does
not request lease discovery and its roles do not implement
`query_dhcp_lease`; add a K8s task if a service later routes lease-discovery
requests to this manager.

### API Extensions

The k8s-only backend introduces no new CRDs or API changes. It operates within
the existing OSAC networking API (VirtualNetwork, Subnet, SecurityGroup,
ExternalIP, ExternalIPPool, ExternalIPAttachment, NATGateway) defined by the
unified networking work (OSAC-1433).

The backend registers itself via ConfigMap:

# Default rendered registration (the namespace follows the operator chart's
# release namespace; `osac` is the standard installation namespace).
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: osac-network-k8s-manager-k8s-only
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: k8s_only
  description: "Hub-cluster VM networking with CUDN, Kubernetes NetworkPolicy, and MetalLB L2."
  capabilities: "ipv4"
```

The registration declares IPv4. For a K8s-only NetworkClass, effective
capabilities must come from this K8s manager when it is the only
manager configured. The current capability reconciler skips synchronization when
`fabricManager` is empty, so this declaration is not currently copied to the
NetworkClass. The central design and K8S-UT-2 treat K8s-only capability
synchronization as required behavior.

The composite role runs against the cluster targeted by the AAP execution
environment. The roles use `OSAC_REMOTE_CLUSTER_KUBECONFIG` when set;
otherwise they use the execution environment's default Kubernetes context.

| OSAC Resource | K8s Resources Created |
|---|---|
| VirtualNetwork | (none — logical grouping) |
| Subnet | Namespace, ClusterUserDefinedNetwork |
| SecurityGroup | NetworkPolicy |
| ExternalIPPool | MetalLB IPAddressPool, L2Advertisement |
| ExternalIP | Service (type: LoadBalancer) in metallb-system |
| ExternalIPAttachment | Service (type: LoadBalancer) in VM namespace |

## Implementation Details/Notes/Constraints

### Ansible Role Architecture

The k8s-only backend uses the `osac.templates.k8s_only` composite Ansible role.
It provides the resource entrypoints selected by the dispatcher and delegates
to independent Kubernetes-native roles by resource kind:

```
osac.templates.k8s_only
├── osac.templates.cudn_net       # VirtualNetwork (no-op), Subnet (Namespace + CUDN)
├── osac.templates.network_policy # SecurityGroup (NetworkPolicy)
└── osac.templates.metallb_l2     # ExternalIPPool, ExternalIP, ExternalIPAttachment
```

### VirtualNetwork — No-Op

The k8s-only backend treats VirtualNetwork as a logical grouping and
creates no Kubernetes network object. The Ansible role
logs success and returns immediately. L3 routing isolation between
VirtualNetworks is provided by keeping their Subnet CUDNs isolated. Sharing a
VirtualNetwork does not connect its Subnets in this phase.

### Subnet — Primary Layer2 CUDN

Subnet provisioning creates two Kubernetes resources:

**1. Namespace** with the label
`k8s.ovn.org/primary-user-defined-network: ""` and a label matching the
subnet's ID for CUDN namespace selection:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: <subnet-metadata-name>
  labels:
    k8s.ovn.org/primary-user-defined-network: ""
    osac.openshift.io/subnet-id: "<subnet-uuid>"
```

The namespace name is the Subnet resource's `metadata.name`; the Ansible role
also adds the tenant and VirtualNetwork labels when those values are present.
The primary-network namespace label attaches pods, including VM launcher pods,
in that namespace to the CUDN. The role does not create a per-VM
NetworkAttachmentDefinition or invoke `move_network_attachment`.

**2. ClusterUserDefinedNetwork (CUDN)** with a primary Layer2 network:

```yaml
apiVersion: k8s.ovn.org/v1
kind: ClusterUserDefinedNetwork
metadata:
  name: <subnet-metadata-name>
spec:
  namespaceSelector:
    matchLabels:
      osac.openshift.io/subnet-id: "<subnet-uuid>"
  network:
    topology: Layer2
    layer2:
      role: Primary
      ipamLifecycle: Persistent
      subnets: # includes the required spec.ipv4Cidr
        - "<subnet-ipv4-cidr>"
```

The role uses the primary Layer2 CUDN pattern implemented by `cudn_net`: it
sets `topology: Layer2`, `role: Primary`, `ipamLifecycle: Persistent`, and the
supplied subnet CIDR. OVN-Kubernetes assigns the primary UDN to pods in the
selected namespaces. Separate CUDNs remain isolated by default; this manager
does not create a `ClusterNetworkConnect` or provide routed connectivity
between Subnets. See [ClusterNetworkConnect
behavior](https://ovn-kubernetes.io/master/features/user-defined-networks/cluster-network-connect/).

Subnet deletion reverses the process: delete the CUDN, then delete the namespace.

### SecurityGroup — NetworkPolicy

SecurityGroup rules are translated into Kubernetes NetworkPolicy resources in
each Namespace labeled for the SecurityGroup's VirtualNetwork. The
`osac.templates.network_policy` role maps OSAC's ingress/egress rule model
(`sourceCidr`, `destinationCidr`, protocol, and port range) to NetworkPolicy
`ingress` and `egress` rules. The policy selects pods carrying the label
`osac.openshift.io/<security-group-name>`.

This is a semantic difference from the Netris backend, which uses Netris ACL
rules. NetworkPolicy enforcement depends on the CNI (OVN-Kubernetes in this case)
and may differ in rule evaluation order, stateful tracking, and default behavior.

### ExternalIPPool — MetalLB IPAddressPool

ExternalIPPool creates a MetalLB IPAddressPool and L2Advertisement:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: <external-ip-pool-metadata-name>
  namespace: metallb-system
spec:
  addresses:
    - "<cidr-from-spec>"
  autoAssign: false
  avoidBuggyIPs: true
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: <external-ip-pool-metadata-name>-l2adv
  namespace: metallb-system
spec:
  ipAddressPools:
    - <external-ip-pool-metadata-name>
```

`autoAssign: false` prevents this pool from being selected for Services without
an explicit pool request. OSAC's parking and ingress Services request the pool
by annotation. `avoidBuggyIPs: true` skips .0 and .255 addresses.

### ExternalIP — Parking Service Pattern

ExternalIP allocation uses a "parking" Service pattern:

The role creates a `Service` named `osac-eip-<external-ip-name>` in
`metallb-system`, with type `LoadBalancer`, an empty selector, the pool
annotation, and an unused placeholder port (65535). It waits for MetalLB to
populate `status.loadBalancer.ingress` and stores the IP in an Ansible fact.
The role does not write `osac.openshift.io/allocated-address` to the ExternalIP
resource. After the AAP job succeeds, the operator reads the address from the
Service status as a fallback and populates ExternalIP status.

The parking Service reserves the IP in MetalLB's allocation table without routing
any traffic. This IP is later migrated to a target namespace when an
ExternalIPAttachment is created.

### ExternalIPAttachment — IP Migration to VM Namespace

The role reads the IP from the parking Service, deletes that Service, and then
creates `osac-eip-<external-ip-name>-ingress` in the ComputeInstance namespace.
The new Service uses the pool annotation, the
`metallb.universe.tf/loadBalancerIPs` annotation with the assigned IP, a
selector for the VM launcher pod, and a TCP port 22 mapping. This delete-then-
create sequence has a window in which the IP is not reserved. If Service
creation fails, the role attempts to restore the parking Service. The operation
is not an atomic IP handoff; another allocation can claim the address during
this gap because there is no shared reservation or serialization mechanism.

For a namespace using a primary UDN, the role waits for the OVN-Kubernetes
mirrored EndpointSlice and adds the standard `kubernetes.io/service-name` label
that MetalLB expects. It then annotates the ComputeInstance with the external
IP address.

Detachment deletes the VM Service first, recreates the parking Service pinned
to the same IP with MetalLB's `metallb.universe.tf/loadBalancerIPs` annotation,
and removes the ComputeInstance address annotation. If parking Service creation
fails, the role attempts to restore the VM Service. This sequence also has a
reservation gap and is not atomic. Concurrent allocation during that gap can
claim the address before the parking Service is restored.

**Required handoff behavior:** Use an atomic MetalLB address transfer or a
pool-scoped lock shared by all AAP jobs that can allocate or move addresses from
that pool. Acquire it before deleting the current Service, keep it until the
replacement Service reports the same address, and recreate the previous Service
pinned to that address before releasing the lock if the transfer fails. A
Kubernetes Lease or equivalent may provide the cross-job lock; lock loss must
stop further Service mutations. Cover both attach and detach, including a new
ExternalIP allocation racing with either transition.

**Limitation**: The role requires `spec.computeInstance` and fails its input
assertion when that field is absent. It does not implement Cluster or
BaremetalInstance targets, and this role-level check is not an admission-time
rejection.

### NATGateway — Unsupported

The k8s-only manager has no NATGateway implementation. The shared dispatch table
marks NATGateway as having no K8s fallback. The K8s-only implementation must
surface that dispatch error as a Failed condition on the NATGateway without
creating an AAP job. Today, `NATGatewayReconciler` inherits the implementation
strategy from its parent VirtualNetwork and does not validate the dispatch plan;
wire it through shared dispatch validation and status handling before claiming
this behavior. The shared API may accept the request and report its unsupported
manager asynchronously through the resource status; this is not an admission
rejection.

### Subnet CIDR Input

The Subnet API supplies `spec.ipv4Cidr`; `cudn_net` passes that value to the
CUDN. The target and current behavior both use caller-supplied canonical IPv4
CIDRs. The CRD validates the format and immutability, while the operator
validates containment within the parent VirtualNetwork and non-overlap with
sibling Subnets. The installer's `subnetIPv4CIDR` NetworkClass value supplies
a default during tenant onboarding; it is not an allocation pool. The manager
does not allocate or release Subnet CIDRs.

### Security Considerations

The k8s-only backend inherits the existing OSAC security model:

- **Credentials and authorization**: No Netris controller credentials are
  required. AAP still needs Kubernetes credentials for the target cluster;
  these come from its execution environment and optional remote kubeconfig.
- **Tenant isolation**: Primary Layer2 CUDNs provide separate subnet networks.
  VMs in different CUDNs cannot communicate unless a network connection is
  explicitly configured; this manager does not configure cross-Subnet
  connections. OVN-Kubernetes enforces the isolation at the OVS datapath level.
- **Input validation**: CRD CEL validation rejects invalid CIDRs, non-canonical
  formats, and IPv6 addresses. The operator validates parent-child relationships
  (Subnet within VirtualNetwork CIDR range).

### Failure Handling and Recovery

| Failure Mode | Behavior | Recovery |
|---|---|---|
| CUDN or Namespace task fails | AAP job fails; the operator reports the provisioning failure on the Subnet | Retry uses the role's `present`/`absent` resource operations |
| MetalLB pool or advertisement task fails | AAP job fails; the operator reports the provisioning failure on the ExternalIPPool | Retry the provisioning job after the MetalLB API is available |
| Parking Service receives no IP | The AAP task times out waiting for Service ingress status and fails; no dedicated “pool exhausted” condition is set | Investigate MetalLB pool configuration/capacity, then retry |
| EndpointSlice workaround times out | AAP job fails while waiting for the OVN-K mirrored EndpointSlice | Check namespace UDN and Service endpoints, then retry |
| NATGateway on k8s-only | Current controller does not validate the dispatch plan. Target: set a Failed condition with an unsupported-operation diagnostic before creating an AAP job. | Wire the controller to the shared dispatch validation/status path; no K8s implementation exists |
| AAP or target-cluster API unavailable | Provisioning job fails or remains pending according to the AAP/dispatcher lifecycle | Restore the service and let reconciliation retry |

The Kubernetes resource tasks use `state: present`/`absent`; ExternalIP
attachment and detachment also check existing Services for job redelivery and
attempt compensating cleanup on failure. These sequences are idempotent on
redelivery but are not atomic across the parking and VM Services. Target
convergence therefore includes the shared pool lock or atomic handoff above,
not only repeated execution of individual Service tasks.

### RBAC / Tenancy

No RBAC or tenancy changes from the unified networking model. Tenant isolation
is enforced by:

- CUDN namespace selectors — each CUDN targets only its own namespace
- OVN-Kubernetes CUDN namespace selection — limits each primary network to
  namespaces carrying its Subnet ID label
- `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` annotations
  on networking resources
- AAP execution credentials require permissions to create and delete the
  Namespace, CUDN, NetworkPolicy, MetalLB, and Service resources described
  above. The operator uses its target-cluster client to read the parking
  Service status when populating ExternalIP status; these are separate
  identities and permissions.

### Observability and Monitoring

No new observability changes beyond the standard OSAC networking monitoring. The
k8s-only backend surfaces operational state through:

- Resource status phases and conditions (standard across all backends)
- Provisioning job tracking via the `ProvisioningJobs` array
- AAP job logs for Ansible role execution details
- Kubernetes resource status, including MetalLB's LoadBalancer Service ingress
  address

## Risks and Mitigations

### CUDN API stability

The CUDN API (`k8s.ovn.org/v1 ClusterUserDefinedNetwork`) is an OVN-Kubernetes
feature. If the API changes in a future OVN-K release, the Ansible roles must be
updated. Mitigated by tracking upstream OVN-K releases and testing against each
new version.

### NetworkPolicy vs ACL semantic differences

SecurityGroup translation to NetworkPolicy may produce different enforcement
behavior than Netris ACL translation. Tenants moving workloads between
k8s-only and Netris-backed deployments may observe behavioral differences in
firewall rule evaluation. Mitigated by documenting the difference and
standardizing the SecurityGroup enforcement model in a separate enhancement.

### MetalLB L2 scalability

MetalLB L2 mode uses ARP/NDP to announce IPs. Large numbers of ExternalIPs may
cause ARP table pressure on the L2 segment. Mitigated by the fact that
ExternalIPPools have bounded CIDR ranges and `avoidBuggyIPs: true` reduces the
usable IP count slightly.

### ExternalIPAttachment target limitations

The k8s-only backend only supports `spec.computeInstance` targets for
ExternalIPAttachment. Cluster and bare-metal targets are not implemented.
Tenants attempting these will see a provisioning failure rather than an
upfront API rejection. Mitigated by documenting the limitation and potentially
adding admission validation in a future enhancement.

## Drawbacks

The k8s-only backend supports this feature set:

- No NATGateway — tenants lose managed outbound NAT with stable source IPs
- No bare-metal networking — physical switch configuration is outside this
  manager's scope
- ExternalIPAttachment limited to VMs — no cluster-level external access
- NetworkPolicy enforcement may differ from Netris ACL enforcement

These limitations follow from the manager's Kubernetes-only resource model.
The trade-off is reduced dependency on external networking services at the
cost of a smaller supported workload and operation set.

## Alternatives (Not Implemented)

### Direct OVN-K integration (no AAP)

The operator could create CUDNs and MetalLB resources directly via Kubernetes
API calls, bypassing AAP and Ansible roles. This would reduce latency and
eliminate the AAP dependency. Rejected because the OSAC provisioning framework
is built around AAP as the execution engine, and all other managers use the same
pattern. Bypassing AAP for one manager would create a second provisioning path
with different failure modes, monitoring, and debugging characteristics.

### Calico/Cilium-based isolation

Instead of OVN-Kubernetes CUDNs, tenant isolation could be implemented
using Calico or Cilium network policies and VXLAN overlays. Rejected because OSAC
deploys on OpenShift, which uses OVN-Kubernetes as the default CNI. CUDNs are the
existing Kubernetes-native mechanism used by the current role, reducing the
dependency surface.

### NATGateway via OVN logical router SNAT

OVN supports SNAT on logical routers. The k8s-only backend could configure OVN
SNAT rules directly to provide NATGateway support. Rejected because this would
require direct OVN northbound DB access, bypassing the OVN-Kubernetes abstraction
layer. This is fragile, unsupported by OVN-K, and could conflict with OVN-K's own
NAT management.

## Test Plan

The test plan separates operator dispatch/validation, AAP resource operations,
and deployed service behavior. Operator unit/envtest and AAP component-integration
cases belong to the owning `[DEV]` work; deployed VMaaS/as-a-service journeys
belong to `[QE]` work.

| Case | Requirement | Tier / owner | Scenario and test environment |
|---|---|---|---|
| K8S-UT-1 | FR-1, FR-2, FR-9 | Operator unit/envtest — `[DEV]` | Verify k8s_only registration and dispatch selection; reconcile a NATGateway with a K8s-only NetworkClass and assert Failed status with an unsupported-operation diagnostic and no provisioning provider/AAP job call. |
| K8S-UT-2 | FR-3 | Operator unit test — `[DEV]` | Verify K8s-only NetworkClass capabilities are sourced from this manager when no fabric manager is configured. |
| K8S-UT-3 | FR-15 | Fulfillment Service unit tests — `[DEV]` | Verify `k8sManager` can be set initially but cannot be changed after it has been set. This is enforced by Fulfillment Service validation, not CRD validation. |
| K8S-UT-4 | FR-15 | Operator envtest — `[DEV]` | Verify the served CRD schemas reject changes to a Subnet's IPv4 CIDR and a VirtualNetwork's NetworkClass. |
| K8S-UT-5 | FR-6 | Fulfillment Service/operator unit tests — `[DEV]` | Verify supplied Subnet CIDRs are canonical IPv4, contained within the parent VirtualNetwork, do not overlap sibling Subnets, and reject IPv6 or dual-stack input. |
| K8S-UT-6 | FR-13 | Operator unit/envtest — `[DEV]` | Simulate a failed Kubernetes provisioning result; assert the affected resource enters Failed with a diagnostic naming the failed resource and reason. |
| K8S-CI-1 | FR-4, FR-7 | AAP component integration — `[DEV]` | Add a `k8s_only` composite-role target to the Kind suite; verify VirtualNetwork is a no-op and each supported resource operation reaches its delegated role entrypoint. Dispatcher selection is covered by K8S-UT-1. |
| K8S-CI-2 | FR-4, FR-5, FR-6, FR-14 | AAP component integration — `[DEV]` | Install CUDN CRDs in Kind and verify Namespace labels, primary CUDN fields, supplied CIDR, deletion order, and repeated create/delete. Immutable-field validation is covered by K8S-UT-4. These checks validate Kubernetes objects, not OVN dataplane connectivity. |
| K8S-CI-3 | FR-16 | AAP component integration — `[DEV]` | Create, update, and delete a SecurityGroup with namespaces labeled for its VirtualNetwork; verify the NetworkPolicy is rendered or updated in each matching namespace with the expected selector and rules, and is absent from unrelated namespaces. This checks resource translation, not policy enforcement. |
| K8S-CI-4 | FR-10, FR-11, FR-12, FR-14 | AAP component integration — `[DEV]` | Install MetalLB CRDs and use a fixture that assigns Service status. For the primary-UDN path, create the mirrored EndpointSlice fixture and verify MetalLB labels, pool/L2Advertisement names, and that the active Service stays pinned to the allocated IP across attach/detach. Run two independent role executions concurrently against the same Kind cluster to represent separate AAP jobs; verify the shared lock prevents reassignment and failure restores the exact address before lock release. A CRD-only Kind cluster does not allocate an IP. |
| K8S-QE-1 | FR-5, FR-6, FR-7, FR-8, FR-10, FR-11, FR-12, FR-14 | Existing VMaaS/as-a-service flows — `[QE]` | In a deployed environment with OVN-Kubernetes and MetalLB, provision VMs using caller-supplied Subnet CIDRs; verify same-Subnet connectivity, no routing between separate Subnets, isolation between VirtualNetworks including overlapping ranges, ExternalIP inbound access, and cleanup after detach. Concurrently allocate ExternalIPs from one pool while another address is attached and detached; verify distinct allocations and that the attached address remains unchanged throughout the handoff. |
| K8S-QE-2 | FR-9 | Existing VMaaS/as-a-service E2E — `[QE]` | Create NATGateway prerequisites under the k8s-only NetworkClass; verify Failed status with an unsupported-operation diagnostic. K8S-UT-1 verifies that no provisioning provider/AAP job is invoked. |

The current `osac-aap/tests/integration` Kind setup does not install CUDN or
MetalLB CRDs/controllers and has no `k8s_only` role target. The AAP component
suite must add the CRD fixtures and MetalLB status simulation described above.
Real CUDN dataplane behavior and external reachability are covered by the
existing VMaaS/as-a-service flows, not by the Kind resource tests. SecurityGroup
policy enforcement is outside this enhancement's scope; K8S-CI-3 only verifies
NetworkPolicy resource translation.

---

## Provenance

Authored: revise @ design 0.11.3 - 2bd6607, workspace main @ d165396

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"d165396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
