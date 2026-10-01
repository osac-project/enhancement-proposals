# K8s Manager — K8s-Only

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | [OSAC-2069](https://redhat.atlassian.net/browse/OSAC-2069) |
| Date        | 2026-09-29 |

> This PRD covers the k8s_only Kubernetes networking manager. It builds on
> the [Unified Networking PRD](/enhancements/OSAC-1433-unified-networking/prd.md),
> which defines the shared networking API and deployment boundaries. This
> document defines the Kubernetes-native behavior and supported workload scope
> of the k8s_only manager.

The k8s_only manager provisions VM networking on the provider-owned hub
cluster. It uses OVN-Kubernetes primary CUDNs, Kubernetes NetworkPolicy, and
MetalLB. It does not connect to an external network control plane.

## Terminology

- **K8s-only manager**: The k8s_only NetworkClass manager that provisions
  supported networking resources on the hub cluster using Kubernetes APIs.
- **CUDN (ClusterUserDefinedNetwork)**: An OVN-Kubernetes cluster-scoped
  resource that defines a user network. This manager creates a primary Layer2
  CUDN for each Subnet.
- **NetworkClass**: Provider configuration that selects the k8s_only manager.
  Shared registration and dispatch behavior is defined in the Unified
  Networking design.

## 1. Problem Statement

The k8s_only manager has no consolidated requirements document describing
its resource mapping, VM attachment behavior, supported targets, and
limitations. These details are currently inferred from the Ansible roles and
scattered feature documentation. Without a requirements baseline, operators
can attempt unsupported operations, and implementation or test changes can
silently diverge from the behavior the manager is intended to provide.

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cloud Infrastructure Admin can select the k8s_only manager and provide
  IPv4 VM networking on the hub cluster using Kubernetes-native resources.
- A tenant can create Subnets and attach VMs through the shared networking API.
- A VM's primary pod network is the Subnet CUDN; VMs on the same Subnet can
  communicate at Layer 2.
- ExternalIP resources provide inbound VM access through MetalLB.
- Unsupported operations and targets are reported clearly before or during
  provisioning, at the earliest layer supported by the shared API and current
  implementation.
- Resource create, update, retry, and delete requests converge on the requested
  supported state without duplicate Kubernetes resources.

### 2.2 Non-Goals

- No changes to the shared OSAC networking API or resource model.
- IPv6 and dual-stack support.
- NATGateway or managed outbound SNAT.
- Routed connectivity between different Subnet CUDNs, including Subnets under
  the same VirtualNetwork.
- Bare-metal networking or cluster endpoint ExternalIP attachments.
- Multi-hub networking.
- Installing or configuring OVN-Kubernetes or MetalLB.
- Tenant selection of the backend.

## 3. User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select the Kubernetes-native
  manager and configure the supported IPv4 network behavior, so that VM
  networking can run on the hub cluster without another networking control
  plane.
- As a Cloud Infrastructure Admin, I want the manager's IPv4 capability
  reflected on its NetworkClass, so that provider configuration describes the
  network it can provide.
- As a Cloud Infrastructure Admin, I want unsupported resource operations and
  provisioning failures surfaced on resource status, so that I can diagnose
  them without inspecting every Kubernetes object.
- As a Cloud Infrastructure Admin, I want to configure the default Subnet
  CIDR used during tenant onboarding, so that I can manage the address space
  used on the hub cluster.

### Tenant Admin

- As a Tenant Admin, I want to create VirtualNetworks and Subnets through the
  shared API, so that tenant workflows remain consistent across deployments.
- As a Tenant Admin, I want to attach an ExternalIP to a VM for inbound access.
- As a Tenant Admin, I want an unsupported NATGateway or workload target to
  report a clear failure rather than remain pending.

### Tenant User

- As a Tenant User, I want a VM attached to a Subnet to receive its address
  from the Subnet CUDN automatically.
- As a Tenant User, I want VMs on the same Subnet to communicate over their
  shared Layer2 network.

## 4. Requirements

### 4.1 Functional Requirements

#### Registration and Capabilities

- **FR-1:** The manager registration must use the
  osac.openshift.io/network-k8s-manager: "true" label, set data.name to
  k8s_only, and declare IPv4 capability.
- **FR-2:** A NetworkClass with the k8s_only manager and no fabric manager
  must resolve to the k8s-only provisioning role for supported resource kinds.
  The shared dispatcher behavior and per-resource role selection are defined
  in the Unified Networking design.
- **FR-3:** Effective NetworkClass capabilities must advertise the K8s
  manager's IPv4 support when it is the sole manager. The current capabilities
  reconciler skips synchronization when no fabric manager is configured, so
  this target behavior is not currently implemented and requires a focused
  unit test.

#### Kubernetes-Native Network Resources

- **FR-4:** VirtualNetwork is a logical grouping in this manager and does not
  create a separate Kubernetes network object. Subnet creation must create a
  namespace and a primary Layer2 CUDN whose namespace selector matches that
  Subnet.
- **FR-5:** The CUDN must use the Subnet's supplied canonical IPv4 CIDR and
  persistent OVN IPAM. The k8s-only manager must not create a per-VM
  NetworkAttachmentDefinition or move a physical port.
- **FR-6:** Subnet CIDRs are supplied by the caller and passed to the CUDN
  unchanged after API validation. The manager does not allocate or release
  Subnet CIDRs from a provider pool. The installer's subnetIPv4CIDR value is a
  default used during tenant onboarding, not an allocation pool.

#### VM Network Behavior

- **FR-7:** A VM attached to a k8s-only Subnet must use the primary CUDN in
  that Subnet's namespace. The role creates the namespace and CUDN; it does
  not create a per-VM NAD or UDN.
- **FR-8:** VMs on the same Subnet must communicate at Layer 2. Separate
  Subnet CUDNs do not gain routed connectivity from sharing a VirtualNetwork.
  Different VirtualNetworks remain isolated, including where their CIDRs
  overlap.

#### Unsupported Operations and External Access

- **FR-9:** NATGateway is unsupported in a k8s-only NetworkClass. Reconciliation
  must set a Failed condition on the NATGateway that identifies the unsupported
  operation and manager, without creating an AAP job. The current
  NATGatewayReconciler receives a dispatch resolver but does not validate the
  NATGateway dispatch plan before provisioning; wire it through the shared
  dispatch validation and status path. This is asynchronous resource failure,
  not API admission rejection.
- **FR-10:** ExternalIPPool must create a MetalLB IPAddressPool and
  L2Advertisement. ExternalIP allocation must reserve an address through a
  parking LoadBalancer Service. ExternalIPAttachment supports ComputeInstance
  (VM) targets by moving the address to a LoadBalancer Service in the VM
  namespace. Cluster and BaremetalInstance targets are unsupported; current
  role input validation reports the unsupported target during provisioning,
  not at admission.
- **FR-11:** When an ExternalIP is attached to a VM using a primary CUDN, the
  manager must make the MetalLB ingress Service discoverable through the
  OVN-Kubernetes mirrored EndpointSlice and the standard Service label
  expected by MetalLB. The current role waits for the mirrored EndpointSlice
  and adds kubernetes.io/service-name.
- **FR-12:** Address migration between parking and VM Services must preserve the
  exact address throughout attach and detach. Use an atomic transfer or a
  pool-scoped lock shared by independent AAP jobs; all OSAC operations that can
  claim an address from the pool must participate. Hold the lock from before
  deleting the current Service until its replacement is confirmed to own the
  same address. On failure, restore the previous Service pinned to that address
  before releasing the lock. The current delete-then-create sequence has a
  reservation gap and no shared lock.

#### Failure Handling and Lifecycle

- **FR-13:** CUDN, namespace, NetworkPolicy, MetalLB, and Service failures must
  be reported on the affected OSAC resource with an actionable diagnostic.
  Parking Service allocation timeout must be distinguishable from successful
  allocation.
- **FR-14:** Deleting a Subnet must delete its CUDN and namespace. Deleting an
  ExternalIPAttachment must restore the parking Service before the address is
  released. Cleanup and repeated create/delete requests must be idempotent.
- **FR-15:** Subnet CIDR and VirtualNetwork NetworkClass are immutable after
  creation and rejected by CRD validation. NetworkClass manager type is
  immutable after assignment; current enforcement is Fulfillment Service
  validation, not CRD validation.

- **FR-16:** SecurityGroup ingress and egress rules must be translated into
  NetworkPolicy rules in every namespace labeled for its VirtualNetwork.
  Updating the SecurityGroup must update the corresponding NetworkPolicies and
  remove obsolete policy rules.

### 4.2 Non-Functional Requirements

- **NFR-1:** The manager supports IPv4 only.
- **NFR-2:** VM networking resources and their associated Kubernetes objects
  must be scoped to the provider-owned hub cluster.
- **NFR-3:** CUDN provisioning and VM attachment must complete within the
  existing reconciliation timeout.
- **NFR-4:** Create, retry, supported update, and delete requests must be
  idempotent and converge to desired state. ExternalIP address migration must
  also protect against concurrent allocation during handoff.

## 5. Acceptance Criteria

- [ ] With a NetworkClass selecting k8s_only and no fabric manager, a
  VirtualNetwork and Subnet reach Ready and the Subnet has a namespace and
  primary Layer2 CUDN.
- [ ] The CUDN selects only the namespace labeled for its Subnet, uses the
  supplied canonical IPv4 CIDR, and enables persistent OVN IPAM.
- [ ] A VM attached to a Subnet uses that Subnet's primary CUDN without a
  per-VM NAD or physical-port operation.
- [ ] VMs on the same Subnet communicate at Layer2; VMs on different Subnets
  do not gain routing through their shared VirtualNetwork; different
  VirtualNetworks remain isolated even if CIDRs overlap.
- [ ] The NetworkClass advertises IPv4 capability from the K8s manager. The
  current reconciler gap is covered by a unit test and fixed before claiming
  this acceptance criterion is met.
- [ ] The CUDN uses the caller-supplied Subnet CIDR. The installer default
  only supplies a default value and does not allocate or reserve CIDRs.
- [ ] Creating a NATGateway under a k8s-only NetworkClass sets a Failed
  condition with an unsupported-operation diagnostic and creates no AAP job.
- [ ] ExternalIPPool creates an IPAddressPool and correctly named
  L2Advertisement in metallb-system. ExternalIP reserves a MetalLB address
  through a parking Service.
- [ ] Attaching an ExternalIP to a VM creates the ingress Service in the VM
  namespace, pins it to the reserved address, and uses the CUDN EndpointSlice
  workaround. Detach restores the parking Service.
- [ ] Attach and detach preserve the same address under concurrent allocation.
  A failure test verifies that the previous Service is restored with the exact
  address before the shared pool lock is released.
- [ ] ExternalIPAttachment to a Cluster or BaremetalInstance is reported as
  unsupported. Current code reports this from role validation during
  provisioning.
- [ ] A provisioning error appears on the affected resource status with a
  diagnostic naming the failed Kubernetes resource and reason.
- [ ] Deleting a Subnet removes its CUDN and namespace. Repeating create,
  attach, detach, and delete does not create duplicates or leave orphaned
  resources.
- [ ] Changes to immutable Subnet CIDR and VirtualNetwork NetworkClass are
  rejected by CRD validation. NetworkClass manager-type changes are rejected
  by Fulfillment Service validation.

## 6. Assumptions

- OVN-Kubernetes and its CUDN CRD are installed on the hub cluster.
- MetalLB and its IPAddressPool and L2Advertisement CRDs are installed and
  configured on the hub cluster.
- The manager operates on the single provider-owned networking hub.
- Tenants attach ComputeInstances to Subnets through the shared OSAC networking
  API; the k8s-only implementation supports only VM targets for ExternalIP.

## 7. Dependencies

- **Unified Networking EP (OSAC-1433)** — defines the shared networking API,
  NetworkClass, dispatch behavior, and lifecycle contract.
- **OVN-Kubernetes CUDN** — provides the primary Layer2 network and IPAM for
  VM launcher pods in the Subnet namespace.
- **MetalLB** — allocates and announces ExternalIP addresses on the configured
  Layer2 network.
- **Fulfillment Service validation** — enforces NetworkClass manager
  immutability.

## 8. Risks

### 8.1 CUDN API and cluster prerequisites

- **Owner:** OSAC networking maintainers
- **Mitigation:** Check CUDN API availability before rollout and validate the
  supported OVN-Kubernetes version in the service deployment environment.

### 8.2 Subnet CIDR validity

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Subnet CIDRs are caller-supplied and must be valid IPv4,
  contained within the parent VirtualNetwork, and non-overlapping with sibling
  Subnets. Validation should reject invalid ranges before CUDN provisioning.

### 8.3 ExternalIP reservation race

- **Owner:** OSAC networking maintainers
- **Mitigation:** Replace the delete-then-create Service migration with a
  serialized or atomic reservation handoff. Until then, concurrent allocations
  can claim an address during attach or detach.

### 8.4 MetalLB Service address discovery

- **Owner:** OSAC networking maintainers
- **Mitigation:** The role waits for the OVN-Kubernetes mirrored EndpointSlice
  and adds the Service label MetalLB expects. Keep this path covered by a
  fixture in the AAP Kind component tests and by a deployed VM service flow.

## Test Plan

The plan separates operator/API behavior, Ansible resource operations, and
deployed service behavior. CUDN dataplane behavior and external reachability
are verified in the existing VMaaS/as-a-service flows.

| Case | Requirement | Tier / owner | Scenario and test environment |
|---|---|---|---|
| K8S-UT-1 | FR-1, FR-2, FR-9 | Operator unit/envtest — [DEV] | Verify k8s_only registration and dispatch selection, then reconcile a NATGateway under a K8s-only NetworkClass; assert Failed status identifies the unsupported manager and no provisioning provider/AAP job is invoked. |
| K8S-UT-2 | FR-3 | Operator unit test — [DEV] | Verify K8s-only NetworkClass capabilities are sourced from the K8s manager when no fabric manager is configured. |
| K8S-UT-3 | FR-15 | Fulfillment Service unit test — [DEV] | Verify NetworkClass manager type can be set initially but cannot be changed after assignment. |
| K8S-UT-4 | FR-15 | Operator envtest — [DEV] | Verify served CRD validation rejects changes to Subnet CIDR and VirtualNetwork NetworkClass. |
| K8S-UT-5 | FR-6 | Fulfillment Service/operator unit tests — [DEV] | Verify supplied Subnet CIDRs are canonical IPv4, contained within the parent VirtualNetwork, do not overlap sibling Subnets, and reject IPv6 or dual-stack input. |
| K8S-UT-6 | FR-13 | Operator unit/envtest — [DEV] | Simulate a failed Kubernetes provisioning result; assert the affected resource enters Failed with a diagnostic naming the failed resource and reason. |
| K8S-CI-1 | FR-4, FR-7 | AAP component integration — [DEV] | Run the k8s_only role against Kind; verify VirtualNetwork no-op behavior and delegation to cudn_net, network_policy, and metallb_l2 role entrypoints. |
| K8S-CI-2 | FR-4, FR-5, FR-6, FR-14 | AAP component integration — [DEV] | Install CUDN CRDs in Kind. Verify namespace labels, primary CUDN fields, supplied CIDR, deletion order, and repeated create/delete behavior. This checks API objects, not OVN dataplane connectivity. |
| K8S-CI-3 | FR-16 | AAP component integration — [DEV] | Create, update, and delete a SecurityGroup against Kind namespaces; verify NetworkPolicy is created or updated with the expected selector and rules, and is absent from unrelated namespaces. This checks resource translation, not policy enforcement. |
| K8S-CI-4 | FR-10, FR-11, FR-12, FR-14 | AAP component integration — [DEV] | Install MetalLB CRDs and simulate Service ingress status. Create the mirrored EndpointSlice fixture with endpointslice.kubernetes.io/managed-by=endpointslice-mirror-controller.k8s.ovn.org and k8s.ovn.org/service-name=osac-eip-<external-ip-name>-ingress; verify Service labels and pool selection, pin the VM Service to the allocated IP, and restore the parking Service on detach/failure. Run independent same-pool allocation and attach/detach jobs concurrently; verify the shared lock prevents reassignment and rollback restores the exact address before lock release. |
| K8S-QE-1 | FR-5, FR-6, FR-7, FR-8, FR-10, FR-11, FR-12, FR-14 | Existing VMaaS/as-a-service flows — [QE] | In a deployed environment with OVN-Kubernetes and MetalLB, provision VMs using caller-supplied Subnet CIDRs; verify same-Subnet connectivity, lack of routing between separate Subnets, isolation between VirtualNetworks including overlapping CIDRs, ExternalIP inbound access, and cleanup after detach. Concurrently allocate ExternalIPs from one pool while another address is attached and detached; verify distinct allocations and that the attached address remains unchanged throughout the handoff. |
| K8S-QE-2 | FR-9 | Existing VMaaS/as-a-service E2E — [QE] | Create the prerequisites for a NATGateway under a k8s-only NetworkClass; verify the resource reaches Failed with an unsupported-operation diagnostic. K8S-UT-1 verifies that no provisioning provider/AAP job is invoked. |

The current osac-aap/tests/integration Kind setup does not install CUDN or
MetalLB CRDs/controllers and has no k8s_only role target. The AAP component
suite must add CRD fixtures, role targets, and MetalLB status simulation as
described above. A CRD-only Kind test cannot verify actual CUDN dataplane
behavior or allocate a MetalLB IP. Those behaviors belong in deployed
VMaaS/as-a-service flows.

---

## Provenance

Authored: revise @ prd 0.11.3 - 2bd6607, workspace main @ d165396

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"d165396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
