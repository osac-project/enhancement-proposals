# K8s Manager — K8s-Only

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | TBD |
| Date        | 2026-09-28 |

> This PRD covers the **k8s-only K8s manager** — the Kubernetes networking
> backend for OSAC. It builds on the [Unified Networking
> PRD](/enhancements/OSAC-1433-unified-networking/prd.md), which defines the
> shared networking model, resources, API, and connected-only deployment support
> boundary. This document defines the requirements for delivering VM-to-fabric
> bridging using only Kubernetes-native resources, without an external fabric
> controller.

This PRD inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
k8s-only networking supports connected deployments only; air-gapped and
disconnected networking deployments are not supported.

It also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.

## Terminology

- **K8s Manager**: The component that bridges the Kubernetes OVN overlay to the
  physical fabric, making VMs part of the fabric network. It manages
  Kubernetes-native networking resources (CUDNs, UDNs, NetworkAttachmentDefinitions)
  on the hub cluster.

- **K8sFallback**: The dispatcher mechanism that allows the K8s manager to fill
  the fabric manager role for supported resource kinds when no fabric manager is
  configured on the NetworkClass. This is how k8s-only deployments work — the
  K8s manager handles both K8s-layer and fabric-layer responsibilities for
  resources it supports.

- **CUDN (ClusterUserDefinedNetwork)**: An OVN-Kubernetes resource that defines
  a cluster-scoped user-defined network. CUDNs provide L2/L3 isolation between
  tenants using EVPN as the backend protocol.

- **NetworkClass**: A provider-configured resource that defines how networking is
  implemented. Specifies which fabric manager and K8s manager handle networking.
  For k8s-only deployments, `fabricManager` is empty and `k8sManager` is set to
  `k8s_only`.

## 1. Problem Statement

OSAC's networking architecture uses a two-manager model: a fabric manager for
physical networking and a K8s manager for bridging the Kubernetes OVN overlay to
the fabric. The K8s manager is responsible for creating the Kubernetes-level
networking resources that allow VMs running on the hub cluster to participate in
tenant networks.

The k8s-only K8s manager exists and is deployed, but has no formal requirements
document. Its behavior, supported operations, and limitations are inferred from
code, scattered feature docs, and the CUDN/EVPN phase 1 enhancement
(OSAC-4291). Without a consolidated PRD:

- Cloud Infrastructure Admins have no authoritative reference for what the
  k8s-only backend supports and what it does not, leading to misconfiguration
  and unsupported-operation attempts (e.g., creating NATGateways on a k8s-only
  NetworkClass)
- Developers implementing new networking features have no requirements baseline
  to validate against, risking drift between the k8s-only and fabric-backed
  paths
- Enforcement of unsupported operations is inconsistent — some are rejected by
  the dispatcher, others fail silently during provisioning

## 2. Goals and Non-Goals

### 2.1 Goals

- A Cloud Infrastructure Admin can deploy OSAC networking without an external
  fabric controller by selecting the k8s-only backend, and tenants get a working
  networking experience for the supported resource set
- The system must clearly reject unsupported operations (NATGateway creation)
  at the API level with an actionable error message, rather than failing during
  provisioning
- The k8s-only backend provides tenant network isolation using
  Kubernetes-native resources (CUDNs with OVN-Kubernetes EVPN backend),
  without requiring vendor-specific network controllers
- The capabilities advertised by a k8s-only NetworkClass accurately reflect
  what the backend supports, so that the fulfillment service and UI can
  surface limitations before a tenant attempts an unsupported action

### 2.2 Non-Goals

- No changes to the OSAC networking API or its resource model — the API is
  inherited from the unified networking work (OSAC-1433)
- IPv6 and dual-stack networking are not supported; the k8s-only backend
  supports IPv4 only
- NATGateway support — the k8s-only backend does not provide outbound NAT
  through the OSAC networking API. Resources may still have default outbound
  connectivity through the cluster's default gateway, but this is outside
  OSAC's networking model
- SecurityGroup policy enforcement — this is a separate concern shared across
  all backends and is not specific to the k8s-only manager
- Multi-hub networking — the k8s-only backend operates on a single hub cluster
- UI support for backend selection — backend selection is a provider
  configuration, not a tenant-facing action
- Support for bare-metal workloads — the k8s-only K8s manager provides
  VM-to-fabric bridging; bare-metal networking requires a fabric manager

## 3. User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to deploy OSAC networking using only
  Kubernetes-native resources by selecting the k8s-only backend, so that I can
  offer tenant networking on sites without an external fabric controller
- As a Cloud Infrastructure Admin, I want the k8s-only backend to register its
  capabilities accurately, so that the platform surfaces limitations (no
  NATGateway, IPv4 only) before tenants attempt unsupported actions
- As a Cloud Infrastructure Admin, I want a failed CUDN or network-attachment
  operation reflected on the affected resource's status, so that I can diagnose
  networking problems without inspecting Kubernetes resources directly
- As a Cloud Infrastructure Admin, I want to configure the subnet CIDR pool
  from which the k8s-only backend allocates tenant subnets, so that I can
  control the address space used on the hub cluster

### Tenant Admin

- As a Tenant Admin, I want to create VirtualNetworks and Subnets through the
  same API regardless of whether the deployment uses a fabric controller or
  k8s-only, so that my workflow is consistent across environments
- As a Tenant Admin, I want to receive a clear error when I attempt an
  unsupported operation (e.g., creating a NATGateway on a k8s-only
  NetworkClass), so that I know to use an alternative approach rather than
  waiting for a provisioning failure
- As a Tenant Admin, I want to attach ExternalIPs to my resources for inbound
  access, so that my VMs are reachable from outside the VirtualNetwork

### Tenant User

- As a Tenant User, I want VMs attached to a subnet to automatically receive
  IP addresses and connectivity on that subnet's network, so that I do not
  configure addressing manually
- As a Tenant User, I want VMs on the same subnet to communicate at L2, and
  VMs on different subnets of the same VirtualNetwork to communicate at L3,
  so that network segmentation works as expected

## 4. Requirements

### 4.1 Functional Requirements

#### Backend Registration and Capabilities

- **FR-1:** The k8s-only K8s manager must register as a ConfigMap with label
  `osac.openshift.io/network-k8s-manager: "true"`, name `k8s_only`, and
  capabilities reflecting IPv4 support only. The NetworkClass capabilities
  controller must compute the intersection of fabric and K8s manager
  capabilities and update the fulfillment service.

- **FR-2:** When a NetworkClass has `fabricManager` empty and `k8sManager` set
  to `k8s_only`, the dispatcher must route supported resource kinds through the
  K8sFallback path. The k8s-only backend must handle VirtualNetwork, Subnet,
  SecurityGroup, ExternalIP, ExternalIPPool, and ExternalIPAttachment
  operations through this path.

#### Unsupported Operation Rejection

- **FR-3:** NATGateway creation on a NetworkClass using the k8s-only backend
  must be rejected at the API level with a clear error indicating that
  NATGateways are not supported by the k8s-only backend. The error must name
  the unsupported resource kind and the backend that does not support it.

- **FR-4:** The dispatcher must not route NATGateway operations through
  K8sFallback. The rejection must occur before any provisioning work begins.

#### Tenant Network Isolation

- **FR-5:** The k8s-only backend must create CUDNs on the hub cluster for
  tenant network isolation. Each Subnet must map to a CUDN with a dedicated
  L2/L3 segment using OVN-Kubernetes with EVPN as the backend protocol.
  Different VirtualNetworks must have no direct connectivity — a VM in one
  VirtualNetwork must not reach another VirtualNetwork's private subnet
  addresses, even when their address ranges overlap.

- **FR-6:** The k8s-only backend must allocate subnet CIDRs from a
  provider-configurable CIDR pool. Allocated CIDRs must not overlap with
  each other or with existing allocations.

#### VM Network Attachment

- **FR-7:** When a VM (ComputeInstance) is attached to a Subnet managed by the
  k8s-only backend, the backend must create the Kubernetes-level network
  attachment (NetworkAttachmentDefinition / UDN) that bridges the VM's OVN
  interface to the CUDN, so the VM receives an IP address on the subnet and
  participates in the tenant network.

- **FR-8:** VMs on the same Subnet must communicate at L2. VMs on different
  Subnets of the same VirtualNetwork must communicate at L3 through the
  VirtualNetwork routing path. VMs on different VirtualNetworks must have no
  direct internal connectivity.

#### Cluster Network Attachment

- **FR-9:** When a Cluster is attached to a Subnet managed by the k8s-only
  backend, the backend must configure the CUDN namespace selector to include
  the cluster's hosted control plane namespace, so that the cluster's nodes
  can participate in the tenant network.

#### External Access

- **FR-10:** The k8s-only backend must support ExternalIP and
  ExternalIPAttachment resources for inbound access to VMs and clusters.
  ExternalIPPools are provider-defined; ExternalIPs are allocated from them.

#### Failure Visibility

- **FR-11:** When a CUDN creation, network attachment, or subnet allocation
  fails, the failure must be reflected on the affected OSAC networking
  resource's status with a diagnostic message. The error must be actionable —
  naming the Kubernetes resource that failed and the reason.

#### Lifecycle and Cleanup

- **FR-12:** Deleting a Subnet must delete its associated CUDN and release the
  allocated CIDR back to the pool. Deleting a VirtualNetwork must be blocked
  while child Subnets exist. Deleting an ExternalIPAttachment must remove the
  inbound path before the ExternalIP can be released.

- **FR-13:** The k8s-only backend must handle CUDN and network-attachment
  cleanup idempotently — repeated delete attempts must not fail or leave
  orphaned Kubernetes resources.

#### Immutability

- **FR-14:** A Subnet's CIDR, a VirtualNetwork's NetworkClass, and a
  NetworkClass's K8s manager type must be immutable after creation. Attempts
  to change these fields must be rejected by CRD validation.

### 4.2 Non-Functional Requirements

- **NFR-1:** The k8s-only backend supports IPv4 only. IPv6 and dual-stack
  are not supported.

- **NFR-2:** Tenant-observable networking behavior — VM connectivity, subnet
  isolation, external access — must be equivalent between the k8s-only
  backend (for its supported resource set) and fabric-backed backends. The
  absence of NATGateway is a documented limitation, not a behavior difference
  in shared resources.

- **NFR-3:** CUDN creation and network attachment must complete within the
  existing reconciliation timeout. The k8s-only backend must not introduce
  additional latency beyond what OVN-Kubernetes CUDN creation requires.

## 5. Acceptance Criteria

- [ ] With the k8s-only backend configured (no fabric manager), a tenant
  creates a VirtualNetwork and Subnet through the API and they reach a ready
  state
- [ ] A CUDN is created on the hub cluster for each Subnet, providing L2/L3
  isolation via OVN-Kubernetes EVPN
- [ ] A VM attached to a k8s-only Subnet receives an IP address on that subnet
  and can communicate with other VMs on the same subnet at L2
- [ ] VMs on different Subnets of the same VirtualNetwork can communicate at L3
- [ ] VMs on different VirtualNetworks cannot reach each other's private
  addresses, even with overlapping CIDRs
- [ ] Creating a NATGateway on a k8s-only NetworkClass returns an API error
  naming the unsupported resource and backend — no provisioning work begins
- [ ] A tenant attaches an ExternalIP to a VM and inbound traffic reaches the
  VM through the external access path
- [ ] A Cluster attached to a k8s-only Subnet has its hosted control plane
  namespace included in the CUDN's namespace selector
- [ ] A CUDN creation failure is reflected on the Subnet's status with a
  diagnostic message naming the failed Kubernetes resource
- [ ] Deleting a Subnet deletes its CUDN and releases the allocated CIDR
- [ ] Deleting a VirtualNetwork is blocked while child Subnets exist
- [ ] Subnet CIDR, VirtualNetwork NetworkClass, and NetworkClass k8sManager
  type are immutable after creation — modification attempts are rejected
- [ ] The k8s-only backend's registered capabilities accurately reflect IPv4
  support only and no NATGateway support

## 6. Assumptions

- OVN-Kubernetes with EVPN support is installed and configured on the hub
  cluster. The k8s-only backend does not install or configure OVN-Kubernetes.
- The CUDN API (`ClusterUserDefinedNetwork`) is available on the hub cluster
  as a stable or beta Kubernetes resource.
- The k8s-only backend operates on a single hub cluster. Cross-hub CUDN
  coordination is not supported.
- Bare-metal workloads require a fabric manager for physical switch
  configuration; the k8s-only backend's K8sFallback handles API-level resource
  management but does not configure physical switches.

## 7. Dependencies

- **Unified Networking EP (OSAC-1433)** — defines the networking model and API
  this backend implements
  ([Unified Networking EP](/enhancements/OSAC-1433-unified-networking))
- **OVN-Kubernetes CUDN/EVPN support** — the underlying Kubernetes networking
  feature that provides tenant isolation
- **NetworkClass capabilities controller** — computes and advertises the
  intersection of manager capabilities to the fulfillment service
- **Dispatcher K8sFallback** — routes operations to the K8s manager when no
  fabric manager is configured

## 8. Risks

### 8.1 OVN-Kubernetes CUDN API stability

- **Owner:** Connectivity & Fabric team
- **Mitigation:** Track upstream OVN-Kubernetes CUDN API maturity. If the CUDN
  API changes, the k8s-only backend must adapt without breaking existing tenant
  networks.

### 8.2 CIDR pool exhaustion

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** The default pool (10.0.0.0/8) provides a large address space.
  Pool utilization should be visible in status. When the pool is exhausted,
  Subnet creation returns a clear error.

### 8.3 Inconsistent tenant experience without NATGateway

- **Owner:** Connectivity & Fabric team
- **Mitigation:** Document that k8s-only deployments do not support managed
  outbound NAT. VMs may still have default outbound connectivity through the
  cluster's default gateway, but this is outside OSAC's networking model and
  not guaranteed. Surface this limitation in the NetworkClass capabilities so
  tenants are aware before creating resources.

### 8.4 K8sFallback masking fabric-only failures

- **Owner:** Connectivity & Fabric team
- **Mitigation:** K8sFallback silently handles resources that would normally go
  to a fabric manager. If a resource kind requires fabric-specific behavior
  that the K8s manager cannot provide, the failure must be surfaced clearly
  rather than silently producing a degraded resource.
