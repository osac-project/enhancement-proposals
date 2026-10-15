---
title: caas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-12
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1436
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md"
  - "CaaS BM Worker Provisioning: /enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Networking — Cluster Networking via OSAC Networking API

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
- [Proposal](#proposal)
  - [Working with provider-supplied managers](#working-with-provider-supplied-managers)
  - [Management publication handoff](#management-publication-handoff)
  - [Workflow Description](#workflow-description)
  - [BareMetalInstanceType and Interface Resolution](#baremetalinstancetype-and-interface-resolution)
  - [API contract](#api-contract)
  - [Component behavior and constraints](#component-behavior-and-constraints)
- [Security Considerations](#security-considerations)
- [Failure Handling and Recovery](#failure-handling-and-recovery)
- [RBAC and Tenancy](#rbac-and-tenancy)
- [Observability and Monitoring](#observability-and-monitoring)
- [Risks and Mitigations](#risks-and-mitigations)
- [Drawbacks](#drawbacks)
- [Provider Networking Disabled](#provider-networking-disabled)
- [Alternatives Considered](#alternatives-considered)
- [Open Questions](#open-questions)
- [Test Plan](#test-plan)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)
- [Dependencies](#dependencies)

CaaS networking provides tenant-controlled cluster node networking via one `network_attachment` per Cluster, BM-based node sets with fabric interface resolution from BareMetalInstanceType, MetalLB VIP provisioning, and auto-provisioned external access (ExternalIP + ExternalIPAttachment) for cluster API and ingress endpoints.

## Summary

This document is a service-specific extension of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md). The unified EP defines the shared architecture and [deployment support boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary); CaaS networking supports connected deployments only and does not add air-gapped or disconnected networking support. This document defines how CaaS consumes that architecture.
Networking resources support only Create, List/Get, and Delete, and the
`Cluster` network attachment is immutable after creation; changes require
delete and recreate.

CaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

Cluster provisioning uses the OSAC Networking API for all networking lifecycle — tenants place clusters on their VirtualNetworks via `network_attachment`, the `BareMetalWorkerReconciler` creates on-demand `BareMetalInstance` objects via the BMaaS private gRPC API (BMaaS owns the fabric port move and IP assignment as part of BMI provisioning), and a VIP feedback loop enables auto-provisioned external access for cluster API and ingress endpoints. See [PRD](prd.md) for detailed requirements and [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md) for the full provisioning design.

The manager-backed resource flows and provider IP-discovery/readiness behavior
in this document describe the enabled mode. The feature-gated disabled behavior
is specified at the end of the Proposal section. API-level SecurityGroup rule
validation and reference checks remain active in disabled mode. OSAC submits no
provider operation to apply or remove SecurityGroup rules; rules already
programmed in the backend may continue to affect traffic until provider-side
cleanup. [User]

The [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)
owns registration, task/input/result schemas, no-op requirements, overlapping
address spaces, stable API ownership, NetworkData, retries and shared cleanup.
The [internal request protocol](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#workload-attachment-policy-lifecycle)
defines attachment status and projection recovery. This design specifies the
service's handoffs and readiness gates, not another copy of those rules.

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
- VIP feedback loop: separate CaaS phase provisions management API publication and reserved guest ingress → ClusterOrder status → fulfillment-service → Cluster → ExternalIPAttachment controller
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call API/ingress external access
- Remove step collections (`netris.steps`, `agentless_net.steps`) from CaaS networking

### On-Demand BMI Provisioning Model (OSAC-2135)

Per [OSAC-2135](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md), CaaS provisions bare-metal worker nodes **on demand** via the BMaaS private gRPC API using per-worker provisioning. A dedicated `BareMetalWorkerReconciler` in osac-operator creates `BareMetalInstance` objects for each requested worker. Each BMI references a RHCOS DiskImage and carries discovery ignition inline from a cluster-specific InfraEnv.

**BMaaS owns the full provisioning lifecycle** including networking:
1. BMaaS provisions the host on the **provisioning network** (inventory → OS provisioning via DiskImage + ignition).
2. After provisioning, BMF creates the worker BMI's target-only SubnetAttachment. OSAC networking dispatches Fabric `apply_subnet_attachment`, which maps the selected physical port to the fabric segment backing the chosen Subnet and installs stateful policy. BMF waits until the request reports `NetworkAttachmentsReady=True` before advancing.
3. Only after attachment readiness does BMaaS perform the single handoff reboot so the OS requests tenant DHCP configuration (`reconcileReboot`). It then reports `NetworkHandoffComplete=True`.
4. The SubnetAttachment controller queries the tenant DHCP lease only after handoff, using the required selected-port MAC. It records `IPDiscoveryComplete=True`; BMF mirrors the discovered IP and readiness to BMI status.
5. The full assisted-installer cluster installation begins only after the exact BMI is Running with attachment, handoff and valid tenant IP discovery complete. An Agent that registers early may be correlated but cannot be approved, cluster-bound or selected by a NodePool until the [worker binding gate](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#mac-address-correlation) and current management publication gate pass. The admitted Agent performs the installation and reports progress on the tenant network.

The `BareMetalWorkerReconciler` reads the private `ClusterOrder.spec.networkAttachment` (a `ClusterNetworkAttachment` carrying typed subnet and security-group references) and enriches it into a per-BMI `BareMetalNetworkAttachment` by resolving the fabric interface from the immutable `fabric_interface` stored on the node set by the fulfillment-service. CaaS never dispatches physical attachment operations directly. BMF owns the worker lifecycle gates and networking reconciliation owns each worker's attachment jobs and lease lookup. On cluster deletion, the controller calls `BareMetalInstances.Delete`; BMaaS follows the same serialized offboarding flow as standalone BMIs: power off on the tenant network, wait for SubnetAttachment cleanup and port restoration, then deprovision and release the host. See the [BMaaS networking design](/enhancements/OSAC-1437-bmaas-networking/design.md#deletion-reverse-order) for the exact condition and finalizer sequence.

### CaaS worker network authorization

The binding uses the Cluster API ID and node-set, so recreating ClusterOrder
does not change the worker's parent or require metadata mutation. Its current
UID still fences ClusterOrder reads/writes through unified projection recovery.

Ordinary ComputeInstances and tenant-owned BaremetalInstances may reference
only their own tenant's Subnet and SecurityGroups. CaaS worker BMIs remain
hidden infrastructure owned by the builtin `system` tenant, as required by
OSAC-2135; their network tenant is the owning Cluster's tenant. This is a
specific controller-authorized parent binding, not a general system-tenant
exception. [User]

The authenticated CaaS worker controller supplies these reserved annotations
on the private `BareMetalInstances.Create` object's metadata:

| Annotation | Value |
|---|---|
| `osac.openshift.io/cluster-api-id` | Owning Cluster's fulfillment API UUID. |
| `osac.openshift.io/cluster-node-set` | Owning node-set name in that Cluster. |

Fulfillment permits these fields only for its explicitly authorized CaaS
worker service identity (the existing `service-account-osac-controller`
principal, explicitly authorized for this operation; a separate credential is
not required). In the Create transaction it resolves the live,
non-deleting Cluster API record, locks against parent
deletion, and verifies the named bare-metal node set. It derives the effective
network tenant from Cluster metadata, the Subnet/SecurityGroups from the
Cluster's immutable attachment, and the physical interface/instance type
from the stored node set. The submitted BMI attachment and instance type
must match those resolved values; omission cannot fall back to system-tenant
network defaults. All referenced network resources must be Ready and belong
to that Cluster tenant/VirtualNetwork.

The same transaction stores the BMI as `metadata.tenant=system`, the validated
parent annotations, and the system-derived
`osac.openshift.io/network-tenant` annotation, and records reverse references
to the Cluster and its network resources. These reserved fields and the BMI
attachment are immutable. Public/ordinary tenant requests cannot supply them;
generic metadata updates cannot add, remove, or alter them, and cannot turn
an existing BMI into a delegated worker. The existing name-based
`cluster-order` label and `owner-reference` annotation remain diagnostic
correlation only; a label or system tenant value alone grants no delegation.
This uses the existing metadata storage, not a new reservation resource or
tenant-facing API. [User]

BMF creates the worker's SubnetAttachment with infrastructure tenant `system`,
the durable BMI API ID binding and a targetRef to its exact current CR UID. Before create/apply/lease dispatch, OSAC verifies
the projected reserved fields against the authoritative BMI and bound parent,
resolves the effective network tenant, and captures that context in the
operation journal. `osac_job_vars.tenant` is the verified network tenant;
`target_identity.tenant` and the BMI metadata remain `system`. Managers use
the resolved `tenant`, Subnet and policy context; they never infer network
authorization from target metadata or perform cross-tenant lookups.
For normal tenant workloads both tenant identities are equal.

Cluster deletion cancels/drains worker creates, deletes all recorded worker
BMIs and waits for their confirmed cleanup before parent finalization.
Deleting BMIs continue to hold network reverse references. Cleanup uses the
validated original binding and snapshot even if the parent projection is
missing; no new apply/lease operation may use an absent, changed or deleting
parent. Missing/mismatched ownership leaves creation non-ready and never
adopts another tenant's worker. Cleanup is not skipped because live parent
lookup fails. Parent records/bindings remain available until children finish.
The current worker code instead checks BMI tenancy against the Cluster tenant;
implementation must replace that assumption consistently in creation,
observation, adoption, networking and teardown while preserving the target's
system-tenant visibility requirement. [User]

### Non-Goals

- VMaaS or BMaaS networking (this EP covers CaaS only)
- VM-based cluster node sets (v0.2 supports BM node sets only; VM worker nodes require HyperShift ↔ CUDN integration not in scope)
- DNS API (enabled-mode tenant/public endpoint records stay in the CaaS network phase until the DNS API is implemented; disabled mode uses baseline DNS)
- Multi-NIC cluster nodes (not supported; v0.2 has one attachment per cluster → one subnet, while each node set resolves its own fabric interface from its BareMetalInstanceType)
- Implementation of the shared manager dispatch contract, which is defined by the Network Manager Integration Contract.

## Proposal

### Working with provider-supplied managers

CaaS selects networking through the same deployment NetworkClass. Physical
workers consume [BMaaS's provider handoff](/enhancements/OSAC-1437-bmaas-networking/design.md#working-with-provider-supplied-managers);
CaaS creates authorized worker BMIs and observes their progress instead of
calling switch or DHCP integrations itself. A CaaS-only deployment needs no
Kubernetes Manager for worker attachment.

| Phase | CaaS responsibility | Provider integration boundary |
|---|---|---|
| Bootstrap | Establish control-plane publication and required worker reachability before install. | Provider environment supplies the management path described below; optional external DNAT cannot bootstrap it. |
| Workers | Create hidden BMIs bound to the owning Cluster's tenant network; observe BMaaS completion and Agent registration. | Selected Fabric handles each BMI through the BMaaS attachment/lease contract. |
| Guest ingress | Ask for a reservation owned by Cluster API ID; persist accepted address before configuring guest MetalLB. | Fabric reserves/reuses one real address from the Subnet VIP range. |
| Endpoint feedback | Verify the guest Service uses that address; publish confirmed API/ingress endpoints. | Optional external mappings use Fabric tasks with the endpoint's explicit routing domain. |
| Delete | Remove external mappings and guest ingress consumers, release reservation, clean worker BMIs, then management/control-plane resources. | Fabric confirms release and physical cleanup; CaaS waits at each dependency gate. |

The endpoint topology, Cluster-owned ingress reservation lifecycle, and worker
authorization below are CaaS-specific. The Network Manager Integration Contract
defines the common AAP task/result envelope, attempt correlation, and retry and
recovery behavior; this extension defines its ingress task result and ownership. [User]

### Management publication handoff

The ClusterOrder controller produces `ClusterOrder.status.conditions[type=ManagementPublicationReady]` from core management-publication observations; the worker reconciler reads it before creating BMIs or permitting Agent binding. It records `observedGeneration` for the current ClusterOrder and recomputes the condition against current referenced resources on restart/reprojection; a stale true condition alone cannot authorize work. This core lifecycle gate remains active in disabled mode using actual baseline publication; it launches no skipped provider operation. It is a private controller condition, not a new public endpoint API. [User]

| Producer/resource | Authoritative publication fields | Consumer and gate |
|---|---|---|
| Ordinary CaaS AAP role creates HostedCluster | `spec.services[service=APIServer].servicePublishingStrategy.loadBalancer.hostname`; OAuthServer, OIDC, Konnectivity and Ignition use `Route` publication | HyperShift realizes management Services/Routes. The workload role already writes these publishing strategies. |
| HyperShift reconciles HostedCluster | `status.controlPlaneEndpoint.host` and `.port`; `status.ignitionEndpoint` | CaaS reads the actual bootstrap hostname/port and ignition endpoint, never derives the API port from an assumed 6443 default. |
| Management MetalLB / Kubernetes Service | The HostedControlPlane-owned API LoadBalancer Service's `status.loadBalancer.ingress[].ip` and API `spec.ports[].port`, found through the exact HostedCluster/HostedControlPlane ownership chain | CaaS records the real IPv4 VIP in `ClusterOrder.status.apiEndpoint`. The Service frontend port is the API DNAT target port; the pod `targetPort` is not a VIP port. Ambiguous Service ownership, VIPs or API ports leave publication non-ready. |
| HyperShift / OpenShift routers / provider DNS and TLS | Owned Routes' `spec.host`, matching `status.ingress[].conditions[type=Admitted]`, and provider DNS/TLS serving those hosts | CaaS checks admission, DNS resolution, TLS hostname/trust, and published listeners from the management/controller path for API, ignition, Konnectivity, authentication and assisted-service. API VIP assignment alone is insufficient; these observations do not prove tenant egress reachability. The assisted-service endpoint is the one used by discovery ignition; the worker later reads `InfraEnv.status.bootArtifacts.discoveryIgnitionURL`. |
| HyperShift-generated installation configuration | `HostedCluster.status.kubeconfig.name` references the Secret containing kubeconfig `clusters[].cluster.server` | The generated server URL must agree with `status.controlPlaneEndpoint`; CaaS validates it when available before using it for guest configuration. HyperShift/assisted-service own the worker bootstrap configuration; CaaS does not replace its server with an optional ExternalIP. |

`ManagementPublicationReady=True` requires the current API publication, required admitted Routes and management-side DNS/TLS/listener checks to pass. Otherwise it is false with reason `ManagementPublicationPending` or `ManagementPublicationFailed` and a diagnostic naming the endpoint/check. Before creating BMIs, CaaS also requires its referenced tenant networking resources to meet ordinary enabled readiness. The provider qualifies and supplies the tenant-to-management route, DNS access and required egress as a deployment prerequisite; a controller-side probe does not establish that path. No temporary tenant probe placement or new provider probe task is required. [User]

The first real worker exercises the tenant path after BMaaS completes attachment, handoff and tenant IP discovery. The [worker binding gate](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#mac-address-correlation) checks the exact BMI phases and the existing Agent `status.conditions[type=Connected].status=True`; ordinary assisted-service eligibility and installation then exercise the published API, ignition, authentication and image paths. Connected is not a post-handoff timestamp, and this design does not invent an unavailable freshness interface. If no connected, authorized Agent is observed within the registration timeout measured from BMI network readiness, report `AgentRegistrationTimeout` with the affected worker and assisted-service path for investigation. Later communication failures retain the installation failure and keep the worker/Cluster non-ready, including when an old Connected condition remains true. Successful management-side checks do not prove tenant reachability. Cleanup and retry use the existing worker lifecycle. [User]

The publication gate does not wait for that future worker communication, guest node readiness, healthy guest cluster operators, ingress setup or a usable guest kubeconfig before admitting BMI creation. These are subsequent binding/installation gates. Cleanup continues if publication readiness regresses; new worker creation/binding waits for recovery. [User]

For optional API DNAT, resolve `destination.address` from the management Service VIP, `destination.endpoint=api`, and exactly one `destination.port_mappings` entry: `protocol=TCP`, `external_port=HostedCluster.status.controlPlaneEndpoint.port`, and `target_port` equal to that Service's API frontend port. Preserve the published client port even when it differs from the VIP Service port. For ingress use the Fabric-reserved guest address, `destination.endpoint=ingress`, and TCP 80→80 and 443→443 mappings. The API uses `routing_domain.type=provider_management`; ingress uses `tenant_virtual_network`. Before dispatch, re-read the existing resources and capture resolved identity, address and ports in the shared durable operation record. Retries and deletion use that accepted operation context. No second publication snapshot or tenant-selected port API is introduced. [User]

The existing publication field sources are in
`osac-aap/collections/ansible_collections/osac/service/roles/hosted_cluster/tasks/create_hosted_cluster.yaml`
and the pinned HyperShift API `HostedClusterStatus`. The publication condition,
management-side publication checks, explicit BMI/Agent binding gate and DNAT resolution above are required implementation
work; current endpoint/status code is not evidence that they already exist.

### Workflow Description

#### Phase 1: Networking prerequisites

Use the shared [creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates) and [deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards), together with [tenant defaults](/enhancements/OSAC-1433-default-networking/design.md).
Require the resolved tenant Subnet and SecurityGroups ready before creating
the workload. Shared network creation, data persistence and optional external
address resources follow unified rules; this service adds no backend-specific
selection or allocation path.

A deployment that offers tenant-subnet cluster ingress configures
`NetworkClass.spec.vip_prefix_length` before creating Subnets for CaaS. The
field is optional in the shared API. CaaS resolves the profile bound to the
Cluster's Subnet and rejects Cluster creation with a configuration diagnostic
if the field is absent, before persisting the Cluster or starting worker
provisioning. When configured, the Fabric Manager receives the captured value
in the canonical `network_class` task context and reserves a matching prefix
inside each Subnet. A prefix that cannot fit a Subnet prevents that Subnet
from becoming Ready; the reserved range is excluded from dynamic allocation.

#### Phase 2: Tenant Creates Cluster

1. **Create Cluster:**
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

2. **fulfillment-service:**
    - If `network_attachment` is omitted or empty: populates it with the tenant's default Subnet and default SecurityGroup (see Default Networking PRD).
    - If one attachment is supplied, defaults only missing fields: a missing Subnet receives the tenant default Subnet, and a missing or empty SecurityGroup list receives the tenant default SecurityGroup only when the resolved Subnet belongs to the tenant's default VirtualNetwork; supplied values are preserved. CaaS does not accept a tenant interface field; fulfillment resolves the first `fabric` port from each node set's BareMetalInstanceType and stores it as immutable `fabric_interface` on the node set for the worker handoff.
    - Validates network_attachment (the singular Cluster field):
      - Subnet exists, is Ready
      - SecurityGroups exist, are Ready, belong to same VN
      - For tenant-subnet ingress, the Subnet's bound NetworkClass has `vip_prefix_length` configured; otherwise reject Cluster creation before any Cluster or ClusterOrder is persisted.
    - For each node_set: resolves `baremetal_instance_type` → BareMetalInstanceType → picks first port with `role=fabric` from `network_ports[]` and stores as `fabric_interface` on the node set definition in the ClusterOrder spec
    - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity), creates two ExternalIPs (API + ingress, each labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <cluster-id>`) in the same DB transaction as the Cluster. Both start in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. ExternalIPAttachments are **not** created at this point — their dependencies (ExternalIP Allocated + Cluster Ready) are not yet met. The fulfillment-service internal reconciler creates them later once both prerequisites are satisfied (see Phase 3). See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access) for the full stepped flow.
    - Creates Cluster record with empty `api_endpoint` / `ingress_endpoint`
    - Creates ClusterOrder CR with the resolved singular `networkAttachment` in spec

3. **osac-operator ClusterOrder controller and network phase:**
    - Create namespace, ServiceAccount, RoleBindings, HostedCluster and NodePool definitions using the ordinary workload provisioning path.
    - The API server runs in the provider management cluster. Its LoadBalancer Service obtains a VIP from the provider's management-network MetalLB allocator, unique within that management address space. It does not consume a tenant Subnet VIP pool.
    - Before worker creation/binding, satisfy the [management publication handoff](#management-publication-handoff) and set the current `ManagementPublicationReady` condition. The provider installs the management publication mechanism as a deployment prerequisite; optional tenant ExternalIPAttachments cannot satisfy this gate.
    - Record the real management API VIP as `status.apiEndpoint`; HyperShift owns the bootstrap endpoint in `status.controlPlaneEndpoint` and the generated installation configuration described above. Keep this path for worker installation and ongoing kubelet/API traffic. Workers do not treat a management VIP as if it belonged to their tenant Subnet.
    - When creating a Subnet, the Fabric task receives the captured `NetworkClass.spec.vip_prefix_length` as `network_class.vip_prefix_length` through the [manager contract's canonical task inputs](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#canonical-serialized-task-inputs). It reserves the configured prefix within the Subnet and excludes it from dynamic address allocation. For ingress, dispatch Fabric `reserve_cluster_ingress_ip` with ClusterOrder as `resource`, the owning Cluster API ID as reservation owner (the ClusterOrder UID only correlates/fences the attempt), and resolved tenant VirtualNetwork/Subnet context. The Fabric Manager is the sole allocator for this reserved slice across concurrent guest clusters and hosting clusters.
    - The successful result contains `osac_result.data.cluster_ingress.address`. OSAC validates request UID/generation, canonical IPv4 form, usable-host containment in the Subnet and consistency with any accepted allocation. After accepting the result, the operator persists the address in the ClusterOrder annotation `osac.openshift.io/ingress-allocated-address` before guest configuration. Fabric owns IPAM: it atomically reserves a real address in its pre-excluded VIP slice, returns the same address for the same owner on retry, and gives independent clusters sharing a Subnet distinct addresses. OSAC does not maintain a second reservation registry. Reserving an address does not change immutable NetworkData.
    - Reservation failure/exhaustion leaves the ingress network phase non-ready with a diagnostic. No guest MetalLB pool or fabricated ingress endpoint is created from a missing reservation. [User]

    **BareMetalWorkerReconciler** admits new workers only after the HostedCluster/ClusterDeployment exists and the current `ManagementPublicationReady` gate passes:
    - Creates cluster-specific InfraEnv discovery ignition.
    - Creates each BMI through the BMaaS private API, passing the reserved parent binding, one-entry network attachment copied from `ClusterOrder.spec.networkAttachment`, and the immutable node-set `fabric_interface` stored by fulfillment at Cluster creation. Fulfillment verifies them against the authoritative Cluster before creating a system-tenant worker; it must not default from the system tenant.
    - BMF provisions OS on provisioning connectivity, waits for `NetworkAttachmentsReady=True` from its target-only SubnetAttachment before performing one handoff reboot, then reports `NetworkHandoffComplete`. Networking reconciliation waits for that handoff before discovering the worker lease using the selected-port MAC; BMF mirrors `IPDiscoveryComplete` and the address before the BMI can be Running.
    - Agents register and installation proceeds over tenant NATGateway/SNAT to the provider-published management endpoints. Tenant SecurityGroup egress must allow the required endpoints/ports, including HTTPS/image dependencies and the published API port. Custom VirtualNetworks require their own usable egress; the default NATGateway belongs only to the default VirtualNetwork.
    - Correlates Agents to BMIs by MAC, waits for the explicit BMI/Agent [binding gate](/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning/design.md#mac-address-correlation), then labels for NodePool selection. Retains existing registration timeout/retry behavior; an early cached Agent cannot prove the tenant path. CaaS does not dispatch its own port moves or create Cluster-target SubnetAttachment requests.

4. **Enabled-mode ingress VIP phase and cluster installation completion:**
    - Once the guest cluster API is usable, use its admin kubeconfig to create its MetalLB ingress configuration and LoadBalancer Service in that guest cluster.
    - Create a single-address IPAddressPool containing only the Fabric-reserved ingress address, with allocation constrained to that cluster's ingress Service; create the corresponding advertisement on the tenant network. The guest MetalLB instance advertises/assigns an already reserved address and does not allocate another tenant VIP independently.
    - Validate the actual Service endpoint matches the reservation and publish it as `status.ingressEndpoint`. API and ingress endpoints live in different routing domains: API uses `routing_domain.type=provider_management`, ingress uses `routing_domain.type=tenant_virtual_network` with the resolved VirtualNetwork/Subnet API IDs and projection UID fences.
    - No tenant-subnet IPAddressPool is created in a shared management/hosting MetalLB instance. Distinct tenants may use overlapping tenant CIDRs because their guest allocators and routing domains are separate; unique reservations within one Subnet come from the Fabric Manager.
    - The core workflow waits for workers, cluster operators, real management API endpoint and real guest ingress endpoint before Cluster Ready. Optional auto ExternalIP allocation/attachment does not gate worker bootstrap or installation Ready.
    - Tenant/public DNS for optional ExternalIPs is published only after that endpoint's attachment is Ready; bootstrap DNS/routes already exist through the provider management publication path. The DNS API itself remains a separate EP.
    - This provider-network phase is tracked/cancellable separately from the core install AAP job. Disabled mode creates no provider reservation or OSAC guest VIP pool and consumes only actual baseline endpoints. [User]

#### Phase 3: VIP Feedback Loop

5. **osac-operator feedback controller** watches ClusterOrder status:
    - Sees `apiEndpoint` and `ingressEndpoint` populated
    - Fires Signal RPC to fulfillment-service

6. **fulfillment-service** re-reads ClusterOrder CR:
    - Syncs `api_endpoint` and `ingress_endpoint` from ClusterOrder status to the Cluster object

7. **fulfillment-service internal reconciler** creates ExternalIPAttachments once both prerequisites are met:
    - Each ExternalIP must be **Allocated** with a validated real address; its corresponding endpoint must exist
    - Cluster must be **Ready** (VIPs populated in Cluster status)
    - Creates each endpoint's ExternalIPAttachment once its gates pass (API + ingress), each labeled `osac.openshift.io/auto-created: "true"`. Both start in **Pending** state. Creation readiness gate is satisfied because both ExternalIP (Allocated) and target Cluster (Ready) are in their terminal ready state.

8. **ExternalIPAttachment controller** reconciles each attachment (defense in depth — the fulfillment-service already validated prerequisites):
    - API attachment: uses `destination.endpoint=api`, the actual management VIP and published-to-Service port mapping from the [management publication handoff](#management-publication-handoff), with `routing_domain.type=provider_management`. The adapter resolves its backend management-domain identifier from its configured environment; Fabric `attach_external_ip` creates the optional inbound translation there.
    - Ingress attachment: resolves `ingressEndpoint` in `routing_domain.type=tenant_virtual_network`, with the tenant VirtualNetwork/Subnet API IDs, projection UID fences and the reserved guest ingress address; Fabric `attach_external_ip` creates inbound translation in that tenant domain.
    - A Cluster target remains supported for both API and INGRESS. Target resolution never assumes both endpoints belong to the Cluster's tenant attachment. Required logical routing domain and target address/context are resolved before dispatch; missing context leaves the attachment waiting/failing with a diagnostic.
    - These optional attachments are separate from the provider management bootstrap publication. Their failures do not invalidate the already usable installation endpoint. [User]

#### Deletion (reverse order)

9. **Delete Cluster:**
    - Register/retain the ClusterOrder finalizer. Manually created ExternalIPAttachments block the delete request until their owner removes them; shared tenant defaults remain. See [Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards).
    - Automatic child cleanup deletes ExternalIPAttachments and waits for confirmed DNAT removal, then deletes ExternalIPs and waits for confirmed address release. Remove their optional public DNS with confirmed attachment cleanup.
    - Resolve the guest network phase through its durable operation record before releasing the ingress reservation. Persist phase intent before its first guest API mutation, so a lost response/restart counts as possibly started. Apply the shared never-started/possibly-started cleanup rule:
      - **Proven never started:** installation failed before any guest network mutation could launch, with no unresolved attempt. Skip deletion of nonexistent guest objects and release any accepted/maybe-started Fabric reservation by its Cluster API owner. A guest API is not required for this branch.
      - **Possibly started:** cancel/drain guest configuration, then remove the guest ingress Service, advertisement and single-address pool while the guest API/workers remain usable; await confirmed removal before release. An inaccessible guest API, missing annotation or timeout is not proof of absence. Retain allocation/finalizers and report `GuestIngressCleanupBlocked` until the administrator repairs management/bootstrap reachability or the guest API and normal guest-object cleanup succeeds. The CaaS phase records confirmed cleanup in the same durable operation record. If access cannot be restored, ownership and reservations remain retained; there is no timeout, administrator status override or force-finalizer shortcut that declares backend absence.
    - After guest-consumer cleanup or proven non-start, dispatch Fabric `release_cluster_ingress_ip` under the original Cluster API ID/context. Retain the allocation annotation and finalizers on failure; Fabric must not reassign the address before confirmed release. After confirmed release, OSAC removes the annotation. Missing annotation still requires cleanup by captured owner identity when reservation may have started.
    - After guest cleanup or the proven-never-started branch and reservation release, delete NodePools/workers through their ordinary lifecycle. The ClusterOrder finalizer calls `BareMetalInstances.Delete` for every authoritatively parent-bound BMI, reconciling those records with `status.workers[]` to recover children whose Create response or status write was lost (30 s context deadline per call), retains its Deleting worker entry and polls on later reconciliations until BMI is confirmed gone. Accepted deletion is not completed deletion. Calls are idempotent and retries use backoff. BMF confirms host shutdown before its request restores provisioning connectivity and releases host ownership.
    - Keep the provider-published management bootstrap path through worker teardown. Once all workers are gone, remove the HostedCluster-owned management Service/publication, release its management VIP through provider management MetalLB, and delete the HostedCluster/core resources. The shared provider publication mechanism remains provider-owned. InfraEnv is garbage collected through its ClusterOrder ownerReference.
    - Remove the ClusterOrder finalizer only after all required enabled-mode cleanup completes. Disabled mode cancels and awaits active networking jobs, then follows logical cleanup without provider operations; skipped backend routes/reservations may require provider/manual cleanup. [User]

10. **Tenant deletes networking resources** (independently, if desired):
    - Delete ExternalIPAttachments → fabric manager removes DNAT rules
    - Delete NATGateway → fabric manager removes SNAT rule
    - Delete ExternalIPs → fabric manager releases IPs
    - Delete SecurityGroup → remove the immutable OSAC rule object after no attachments reference it
    - Delete Subnet → require no workload/cluster reservation references; delete VM overlay through Kubernetes Manager when configured, then Fabric segment and reserved slice. CaaS does not depend on a VM manager or shared hosting tenant pools.
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

The tenant provides a single `ClusterNetworkAttachment` with optional `subnet`
and `security_groups` fields — no node_set or interface field. Fulfillment
resolves and stores the interface from the BareMetalInstanceType for each node
set:

1. For each node set in the cluster spec (e.g., "gpu"), read `ClusterSpec.node_sets["gpu"].baremetal_instance_type` = "bm-standard"
2. BareMetalInstanceType "bm-standard" has network_ports:
   ```
   [{name: "data-0", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "data-1", role: "fabric", type: "Ethernet", speed: "100Gbps"},
    {name: "mgmt-0", role: "management", type: "Ethernet", speed: "1Gbps"}]
   ```
3. Fulfillment picks the first port with `role=fabric` → `data-0`, stores it as the immutable `fabric_interface` on the node set in the ClusterOrder
4. The worker controller copies the stored `fabric_interface` into the per-BMI `BareMetalNetworkAttachment`; BMaaS receives the attachment (subnet + interface + primary) on the BMI Create call and handles the fabric port move as part of provisioning (see [On-Demand BMI Provisioning Model](#on-demand-bmi-provisioning-model-osac-2135))

For v0.2: **CaaS supports BM node sets only.** VM-based cluster node sets are architecturally possible but are deferred — the HyperShift ↔ CUDN integration for VM worker nodes is not in scope.

For v0.2: **one attachment per cluster → one subnet; each node set uses its own immutable fabric interface resolved from its BareMetalInstanceType at cluster creation.**

#### Interface Role Convention

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) |

Roles are conventions, not enforced enums. The CaaS template defaults to role `fabric` for the tenant's subnet. The `lifecycle` interface is used by the provisioning system (Ironic, Metal3) for PXE boot and BMC operations — it is NOT tenant-attachable and the template skips it during interface resolution.

<a id="api-extensions"></a>

### API contract

#### Proto (fulfillment-service)

```protobuf
message ClusterNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
}
// Private ClusterNodeSet fields; public API omits fabric_interface.
message ClusterNodeSet {
  reserved 1;
  reserved "host_type";
  optional int32 size = 2;
  string fabric_interface = 3; // Server-derived, private, immutable snapshot
  BareMetalInstanceTypeReference baremetal_instance_type = 4;
}

message ClusterSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;
  // ... existing fields ...
  ClusterNetworkAttachment network_attachment = 9;   // Optional, singular
  optional bool auto_external_ip_attachment = 10;              // Auto-provision ExternalIP + ExternalIPAttachment for API and ingress
}

message ClusterStatus {
  // ... existing fields ...
  string api_endpoint = 6;      // Real hosted API VIP in provider management routing domain
  string ingress_endpoint = 7;  // Real guest ingress VIP in tenant VirtualNetwork routing domain
}
```

The authoritative snapshot is the private database-backed
`Cluster.spec.node_sets[<node-set>].fabric_interface`. Fulfillment resolves it
once at Cluster creation from the first `fabric` port of that node set's
BareMetalInstanceType, rejecting a missing port. Public callers cannot supply
it; private callers cannot override it. Later worker creation and scale-out
reuse the snapshot rather than re-reading a changed instance type.
Fulfillment projects it to the matching
`ClusterOrder.spec.nodeRequests[].fabricInterface`, keyed by `nodeSet`.
Projection recovery restores this value from the database. A status mirror is
observational only and cannot authorize a different port.

#### Operator CRD (ClusterOrder)

```go
type ClusterOrderSpec struct {
    // ... existing fields ...
    NetworkAttachment *ClusterNetworkAttachment `json:"networkAttachment,omitempty"`
    NodeRequests []NodeRequest `json:"nodeRequests,omitempty"`
}

type NodeRequest struct {
    // ... node count and BareMetalInstanceType reference ...
    NodeSet         string `json:"nodeSet"`
    FabricInterface string `json:"fabricInterface"` // Immutable server-derived spec snapshot
}

type ClusterNetworkAttachment struct {
    SubnetRef         string   `json:"subnetRef,omitempty"`
    SecurityGroupRefs []string `json:"securityGroupRefs,omitempty"`
}

type ClusterOrderStatus struct {
    // ... existing fields, including Conditions []metav1.Condition ...
    // ManagementPublicationReady gates new worker creation and Agent binding.
    APIEndpoint     string          `json:"apiEndpoint,omitempty"`     // Provider management MetalLB API VIP
    IngressEndpoint string          `json:"ingressEndpoint,omitempty"` // Fabric-reserved address advertised by guest MetalLB
}

// Per-worker lifecycle state is tracked in ClusterOrder.status.workers[]
// (see OSAC-2135 WorkerStatus). The BareMetalWorkerReconciler manages
// worker phases (Provisioning → WaitingForAgent → Binding → Ready),
// BMI resource IDs, and failure/retry state. IP addresses are discovered
// by BMaaS as part of BMI provisioning (reconcileIPDiscovery) and do not
// require operator-side Agent CR IP watching.
```

The operator stores the validated ingress allocation on ClusterOrder:

```yaml
metadata:
  annotations:
    osac.openshift.io/ingress-allocated-address: "192.0.2.20"
```

This system-managed annotation records Fabric's allocation before guest
publication; `status.ingressEndpoint` remains empty until the guest Service
confirms the same address. Fabric returns `data.cluster_ingress.address` and
does not patch ClusterOrder. Projection reconciliation preserves the
annotation; tenant input cannot supply or replace it. OSAC adds it using the
exact ClusterOrder UID and resourceVersion, accepts an identical retry, and
fails a conflicting value rather than replacing an allocation. A write failure
blocks guest configuration; restart replays the durably accepted job result.
The existing captured operation context retains the owning Cluster API ID, Subnet API ID and provider binding for recovery and cleanup. The ClusterOrder UID fences only writes to that projection. When the same Cluster is reprojected, restore the accepted annotation from the durable operation result under the new UID/resourceVersion before guest provisioning; do not reserve a second address.
There is no additional reservation table, CRD or NetworkData value. Normal
deletion retains the annotation until consumers are removed and Fabric
confirms release; the shared contract defines lost-result recovery and the
disabled-mode exception. [User]

Public endpoint strings remain addresses. The private `ManagementPublicationReady` condition and existing HostedCluster/Service fields define the bootstrap/port handoff above; no public port fields are added. ExternalIPAttachment's resolved `destination` includes endpoint-specific `port_mappings`, while its dispatch input includes the `routing_domain`
object: `.type=provider_management` for the actual API VIP, or
`.type=tenant_virtual_network` with tenant VirtualNetwork/Subnet API IDs and projection UID fences for
ingress. The provider adapter obtains backend management-domain identifiers
from its configured environment.
The shared manager contract defines the result and dispatch schemas. [User]

#### Database

Migration adds to clusters table:
- `network_attachment JSONB` — stores the singular ClusterNetworkAttachment
- `api_endpoint TEXT` — provider management API VIP
- `ingress_endpoint TEXT` — Fabric-reserved guest ingress VIP

#### Server Validation

- network_attachment: resolved subnet exists, is Ready; missing fields have been defaulted without replacing supplied values
- Each node set's `baremetal_instance_type` must have at least one `network_ports` entry with `role=fabric` for fabric_interface resolution
- Immutability: network_attachment is immutable after creation
- target_endpoint validation on ExternalIPAttachment: required when target is cluster, must be `API` or `INGRESS`

<a id="template-and-network-phase-changes"></a>

#### Template and network-phase responsibilities

**`osac.templates.ocp_4_17_small/install.yaml` core ClusterOrder job:**
- Create HostedCluster + NodePools with the configured Agent selectors. The worker reconciler later correlates and labels registered Agents for those selectors; initial creation cannot require workers that depend on the HostedCluster bootstrap path.
- Do not run tenant-pool-backed MetalLB VIP provisioning inline in this core job

**Separate enabled-mode CaaS network phase:**
- Confirm provider management API publication before worker bootstrap; reserve guest ingress address through Fabric fixed tasks; configure its guest single-address MetalLB pool/Service after reservation
- Record real endpoint addresses and resolved routing domains, synchronize status, and release the guest reservation only after confirmed Service/advertisement cleanup
- Run as separately tracked/cancellable network work; the disabled mode skips it and consumes only baseline-provided endpoints

**`osac.templates.ocp_4_17_small/delete.yaml` core ClusterOrder job:**
- BMaaS owns worker port restoration through BMI deletion.
- Perform core cluster teardown in the [deletion order](#deletion-reverse-order). NodePool/worker removal follows guest-network cleanup; HostedCluster and its management publication remain until worker deletion is confirmed.
- Run MetalLB Service and other provider-network cleanup only in the separately tracked enabled-mode network phase; disabled deletion skips provider cleanup

<a id="implementation-detailsnotesconstraints"></a>

### Component behavior and constraints

#### Component Responsibility Summary

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate `network_attachment` (singular), resolve fabric_interface per node set from BareMetalInstanceType, create ClusterOrder CR, sync VIPs from feedback, auto-provision ExternalIP |
| osac-operator BareMetalWorkerReconciler | Create on-demand BareMetalInstances via BMaaS private gRPC API with a one-entry `network_attachments` list (subnet from ClusterOrder `networkAttachment` + immutable `fabric_interface` from the node set, resolved once by fulfillment-service); correlate Agents to BMIs via MAC; delete BMIs on scale-down/cluster deletion. BMaaS owns the fabric port move and IP discovery as part of BMI provisioning (OSAC-2135) |
| osac-operator ClusterOrder controller | Create namespace/SA/RoleBindings, trigger AAP workflow, aggregate worker status |
| osac-operator ClusterOrder feedback controller | Watch ClusterOrder status, Signal fulfillment-service when VIPs appear |
| osac-operator ExternalIPAttachment controller | Resolve real API/ingress address plus provider_management/tenant_virtual_network context and dispatch endpoint-specific DNAT |
| AAP template and separate CaaS network phase | Create HostedCluster/NodePools; wait for published management bootstrap endpoints; configure guest ingress with its Fabric-reserved address; publish real endpoint status |
| BMaaS (bare-metal-fulfillment-operator) | Owns worker inventory/OS/power lifecycle, request gates, one handoff reboot and discovered-IP mirror; confirms shutdown before networking request restores provisioning port on deletion |
| fabric_manager (Ansible role) | Per-worker apply/delete policy/physical attachment and selected-MAC DHCP lookup; Cluster-API-ID-owned ingress reservation/release; endpoint-domain-aware ExternalIP DNAT and VN SNAT |
| k8s_manager (Ansible role) | VM-only overlay/attachment work when VM workloads are enabled; CaaS works without this manager |

#### Auto-Provisioned Resource Lifecycle

- Labeled `osac.openshift.io/auto-created: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent Cluster
- Existing authentication remains. Private worker creation adds the [parent-binding authorization](#caas-worker-network-authorization): only the authorized controller may create system-tenant workers with verified access to the parent Cluster network.
- Complete stateful SecurityGroup rules apply to each worker BMI interface before tenant traffic. The hosted API uses the provider management publication and infrastructure policy; its optional DNAT target domain is not inferred from worker Subnet policy.

### Failure Handling and Recovery

#### ClusterOrder Controller Reconciliation Failures

- Missing/non-Ready Subnet at admission: reject Cluster creation with `FailedPrecondition`. Loss of a dependency after admission holds the relevant network phase non-ready with a diagnostic; it does not select another Subnet.
- BMI creation failure (BMaaS private API error or no available hosts): worker phase set to `Failed`, controller retries with escalating backoff (see OSAC-2135 retry logic)
- Agent registration timeout (BMI network-ready but no connected, authorized Agent observed within 30 min): worker phase set to `Failed` with reason `AgentRegistrationTimeout` and a diagnostic naming the worker and tenant-to-assisted-service path to investigate; controller deletes the timed-out BMI through normal cleanup and retries. Management-side publication success does not suppress this failure.
- AAP job failure (template execution error): ClusterOrder enters Failed state with AAP job ID in status

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, resource not persisted
- ExternalIP provisioning failure: ExternalIP reports failure; core cluster provisioning continues through the provider-published management bootstrap endpoint, and optional external access remains unavailable
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach cluster (cluster functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]

### RBAC and Tenancy

Tenant visibility and ordinary tenant networking permissions remain unchanged. The [worker authorization contract](#caas-worker-network-authorization) adds explicit controller authorization and immutable parent/network-tenant validation for hidden system-tenant BMIs. Cluster-owned ExternalIPs and ExternalIPAttachments inherit tenant isolation from their parent:
- `osac.openshift.io/tenant` annotation propagated from Cluster to auto-created resources
- OPA policies enforce tenant-scoped operations according to each resource API;
  networking resources use create/list/get/delete and do not expose
  update/patch, while supported non-network workload updates remain available
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

#### Risk: Bootstrap publication or guest ingress reservation unavailable

**Impact:** Workers cannot install if the published management API/control-plane
routes are unavailable from tenant egress. Ingress cannot become ready if its
Fabric reservation is absent, exhausted or mismatched with the guest Service.

**Mitigation:** Provider management MetalLB/publication is a deployment
prerequisite. Gate worker bootstrap on real published endpoints. Reserve the
ingress address under stable Cluster API ID before guest pool creation,
the Fabric adapter provides atomic reservation, uniqueness within the
shared Subnet and VIP-slice membership. OSAC validates usable Subnet
containment and owner identity, persists the allocation annotation, and
requires an exact guest Service match.
Retain reservation ownership through cleanup failures. This supports CaaS-only
profiles and overlapping tenant CIDRs without shared hosting tenant pools. [User]

**Reviewed by:** osac-operator and provider networking teams

### Drawbacks

#### VIP feedback loop adds complexity

VIP discovery flow (separate endpoint phase → ClusterOrder status → Signal RPC → fulfillment-service → Cluster → ExternalIPAttachment controller) adds cross-component coordination complexity. Failure in any step breaks the flow.

**Trade-off:** Complexity vs. auto external access. Chosen approach: implement VIP feedback loop to enable auto ExternalIP for clusters. Alternative: manual external access only (simpler, less usable).

### Provider Networking Disabled

Apply the [unified disabled-mode contract](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control)
for API validation, external-address state, existing-job resolution and logical
cleanup. Workers follow [BMaaS disabled behavior](/enhancements/OSAC-1437-bmaas-networking/design.md#provider-networking-disabled),
including skipped port movement/reboot/lease phases and their conditions.

CaaS still provisions on available baseline connectivity to assisted-service,
control-plane endpoints, DNS and installation dependencies. That environment
must supply real API/ingress publication; skipped tenant networking creates
neither a tenant VIP pool nor a route. Baseline endpoint feedback may be
reported. Cluster Ready means installation completed on that baseline, without
claiming tenant routing. Two requested automatic ExternalIPs reserve logical
capacity under unified rules but cannot unblock attachment without real
allocation and endpoint readiness. [PRD: FR-12] [User]

Worker/cluster teardown remains available after active jobs are accounted for.
Previously moved host ports may require provider restoration before host
cleaning; keep management/bootstrap connectivity until workers finish teardown.

Re-enabling provider networking follows the [shared activation preflight](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control). For this extension, drain and delete each Cluster through its normal teardown path and wait for its worker BaremetalInstances to complete the BMaaS cleanup handoff. The shared gate also waits for workloads owned by other extensions and blocks new workload Creates while activation is pending. Reads and deletes remain available. After the deployment profile and configured pools regain real provider readiness, each Cluster still waits for its own ready networking references. A disabled-mode ProvisioningDisabled state does not satisfy enabled readiness. An ordinary restart of an already enabled deployment does not require a new drain. [User]

## Alternatives Considered

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

The hosted API uses provider management MetalLB and a published management
endpoint available before worker bootstrap. Guest ingress uses a single-address
pool in its own cluster containing a Fabric-reserved address from the tenant
Subnet's VIP slice. CaaS requires no VM-overlay Kubernetes Manager. [User]

### ~~4. How does the operator know the fabric_manager name?~~ — Resolved

Resolved: Fulfillment binds each resource and operation to the authoritative NetworkClass and exact manager registration identities. The operator verifies the projected CR identities against that binding; a cached logical manager name cannot redirect retries or cleanup after replacement. One deployment profile remains selected, and its bound resources must drain before replacement.

### ~~5. Should auto NATGateway treat a Deleting NATGateway as 'does not exist'?~~ — Resolved

Resolved: NATGateway reuse limited to Ready only. Failed/Deleting NATGateways cause the create request to fail with an error. NATGateway auto-provisioning per resource was removed — NATGateway is now a VN default created at tenant onboarding.

### ~~6. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity is checked synchronously during the API call. If exhausted, the call fails atomically. No Failed resource created.

### ~~7. How is the subnet CIDR partitioned between MetalLB VIP allocation and fabric DHCP assignment?~~ — Resolved

The shared API leaves `vip_prefix_length` optional. A CaaS Cluster create
request is rejected before persistence when tenant-subnet ingress is required
but the Subnet's bound NetworkClass omits it. When configured, Subnet creation
passes the captured value to the Fabric Manager, which reserves a contained
prefix and excludes it from dynamic allocation. A prefix that cannot fit the
Subnet prevents Subnet readiness. The Fabric Manager is the sole allocator
for that range; `reserve_cluster_ingress_ip` returns a stable
Cluster-API-ID-owned address. Guest MetalLB advertises only that reservation.
Concurrent clusters sharing a Subnet cannot independently allocate the same
address, and reservations do not modify immutable NetworkData. [User]

### ~~8. What IP addresses do DNS records point to — MetalLB VIPs or ExternalIPs?~~ — Resolved

Worker installation uses provider-published management API/control-plane DNS,
TLS and route/DNAT endpoints reachable through tenant egress before Cluster
Ready. Optional tenant API/ingress ExternalIP DNS is published after its
ExternalIPAttachment is Ready. API DNAT resolves `provider_management`;
ingress DNAT resolves `tenant_virtual_network`. Workers never require a later
optional tenant ExternalIPAttachment to complete installation. [User]

## Test Plan

- **[DEV/QE] Worker authorization:** verify hidden system-tenant workers use only the validated parent Cluster network context. Reject forged parent metadata, wrong node sets/UIDs and foreign attachments; exercise parent-delete/create races and cleanup after projection loss. The extension owns these parent-authorization cases; generic owner/context rejection is covered by [TC-FR6-01](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md#tc-fr6-01-reject-invalid-json-schemas-declarations-and-manager-results).

### Endpoint Topology and Attachment Contract

- **[DEV] Contract:** verify CaaS rejects Cluster creation before persistence or worker provisioning when the bound NetworkClass omits the required `vip_prefix_length`. With the field configured, verify `create_subnet` receives the captured `network_class.vip_prefix_length`, reserves a CIDR contained in the Subnet, and fails Subnet creation/readiness when the prefix cannot fit. Verify the reserved range is excluded from dynamic address allocation. Also verify fixed Fabric ingress reserve/release entry points, Cluster API ID idempotency, unique addresses within the Subnet VIP slice, exact `cluster_ingress.address` result shape, missing/invalid allocation rejection, and DNAT routing_domain/context for both Cluster target endpoints. A provider no-change success still requires real allocation/results for allocating tasks.
- **[DEV] Envtest:** provide the management VIP first, delay management-side DNS, TLS and Route admission separately, and assert `ManagementPublicationReady=False` blocks BMI creation/Agent binding. Make the API publish on TCP 7443 with Service port 6443; verify bootstrap uses 7443 and API DNAT maps external 7443 to VIP 6443, including restart before feedback. Do not gate workers on guest readiness or kubeconfig availability; delay optional ExternalIP allocation and prove core install continues; guest Service waits for the operator-written allocation annotation; failed annotation writes block provisioning; restart replays accepted results without reallocating; stale-UID writes and conflicting annotations fail; lost-result retry retains API-ID-owned allocation; projection reconciliation preserves the annotation; cleanup failures retain it and finalizers until confirmed release.
- **[DEV] Envtest / [QE] E2E:** with zero workers, satisfy management-side publication and ready tenant references; BMI creation proceeds without a tenant probe resource/task. Break tenant egress while management checks remain healthy. An early Agent cannot bypass BMI handoff/IP gates, and Connected=False/Unknown blocks binding until timeout. If a stale Connected=True persists, subsequent assisted installation still fails and the Cluster remains non-ready; do not assert that a condition transition timestamp proves post-handoff traffic. Restore egress and retry through ordinary cleanup, then verify actual registration and installation through API/ignition/image paths before Cluster Ready.
- **[QE] E2E:** CaaS-only deployment without K8s manager; two tenants with identical Subnet CIDRs; concurrent clusters on one Subnet across hosting clusters get distinct ingress reservations; guest single-address pools match reservations; worker/API DNS/TLS and kubelet traffic work before optional attachment creation; ingress HTTP/HTTPS reaches the guest router.
- **[DEV] Envtest / Contract:** fail installation before the guest phase can start and delete without a guest API; reservation release completes after prior external cleanup. Separately lose access after a guest mutation might have succeeded: retain reservation/finalizers, reject reuse, and resume only after API recovery and confirmed guest-object cleanup; an inaccessible guest never authorizes release.
- **[QE] E2E:** API ExternalIP routes in management domain and ingress ExternalIP in tenant domain; remove DNAT, guest Service/advertisement, then release reservation; ensure management bootstrap path remains through worker teardown; disabled mode fabricates neither address nor routing success. [User]


### Provider Networking Control (FR-12)

- **[DEV] Envtest / [QE] E2E:** request re-enablement with a baseline workload or a workload whose networking was suspended by disablement still present. Assert activation and new workload creates are blocked, existing Read/Delete remain available, and no apply/lease/reservation or tenant attachment mutation runs. Drain workloads and jobs, repair backend leftovers, then activate; stale skipped readiness cannot admit new workloads until genuine network prerequisites are ready. Repeated enabled restarts do not invoke a fresh drain.

- Verify normal cluster provision/delete jobs still run with the shared setting
  disabled and sufficient baseline connectivity; no tenant VIP allocation,
  IPAM, public DNS/routing, or provider cleanup runs while disabled; core
  ClusterOrder jobs remain active.
- Verify the disabled contract takes effect after coordinated rollout and
  active provider-network operations reach terminal state.
- Verify in-progress provider-network operations reach terminal state before
  skipped status or deletion completion, including retryable status errors.
- Verify non-allocating Networking API resources report `Ready=True`, reason
  `ProvisioningDisabled`, with a skipped-work message only after logical
  preconditions pass. Verify ExternalIP pending and previously allocated
  statuses match the shared contract. Verify incomplete worker BMI phases
  skipped after disablement report `Status=Unknown`, reason
  `ProvisioningDisabled`, confirmed earlier phases retain `True`, and legacy
  `True`/`Skipped` conditions are normalized; ClusterOrder Ready and those
  skipped conditions do not claim tenant routing or ExternalIP attachment.
  Enabled mode retains normal provider behavior.
- Verify invalid API/defaulting/dependency requests remain rejected,
  SecurityGroup defaulting/immutability remains unchanged, and automatic
  attachments still wait for Allocated + workload Ready.

### Unit Tests

- fulfillment-service: network_attachment validation (subnet exists, Ready, same VN)
- fulfillment-service: omitted and partial attachment defaulting (empty `security_groups` is missing; supplied values are preserved; a missing group list defaults only for the tenant default VirtualNetwork and is rejected for a non-default subnet without caller-supplied groups)
- fulfillment-service: fabric_interface resolution per node set (BareMetalInstanceType must have fabric-role port)
- fulfillment-service: interface resolution from BareMetalInstanceType (pick first fabric-role port from network_ports[] and store it on the node set)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator BareMetalWorkerReconciler: BMI creation with enriched network_attachment using the stored node-set interface
- osac-operator BareMetalWorkerReconciler: Agent-to-BMI MAC correlation
- osac-operator feedback controller: VIP sync to fulfillment-service

### Integration Tests

- E2E: create Cluster with explicit network_attachment, verify cluster provisioned on correct subnet
- E2E: create Cluster with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created for API and ingress, DNAT rules functional
- E2E: create Cluster with `--external-ip-attachment`, verify full connectivity (ExternalIP + ExternalIPAttachment for API and ingress)
- E2E: delete Cluster with auto-provisioned resources, verify ExternalIPAttachments and ExternalIPs cleaned up
- E2E: create Cluster with omitted network_attachment, verify default Subnet + SecurityGroup populated
- E2E: VIP feedback loop — verify the separate endpoint phase writes confirmed VIPs to ClusterOrder status, fulfillment-service syncs to Cluster, ExternalIPAttachment controller creates DNAT

### Tricky Test Cases

- Multiple node sets sharing the same subnet (verify correct fabric interface resolution per node set from BareMetalInstanceType)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify retained finalizer/ownership on persistent failure, successful cleanup after repair)
- VIP feedback loop failure (Signal RPC fails, fulfillment-service does not sync VIPs)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachment`, `auto_external_ip_attachment`, `api_endpoint`, `ingress_endpoint`) implemented in fulfillment-service
- [ ] Operator CRD updated with `ClusterNetworkAttachment`, `APIEndpoint`, `IngressEndpoint` fields
- [ ] BareMetalWorkerReconciler (OSAC-2135) implemented — on-demand BMI creation with enriched network_attachment
- [ ] Agent-to-BMI MAC correlation and NodePool labeling implemented
- [ ] VIP feedback loop (endpoint phase → ClusterOrder → fulfillment-service → Cluster) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] With networking disabled, ClusterOrder install/delete remains available while tenant VIP allocation, IPAM, public DNS/routing, and provider cleanup are absent
- [ ] Integration tests pass (E2E coverage for network_attachment, auto ExternalIP attachment, VIP feedback)
- [ ] Documentation: API reference, user guide for simplified cluster creation

GA criteria:
- [ ] Fabric-only CaaS profile validated; Kubernetes Manager required only when the deployment also enables VM overlay workloads
- [ ] Network Manager Integration Contract registration, generic dispatch, result validation, and durable recovery implemented; the selected Fabric Manager and any required Kubernetes Manager pass provider qualification
- [ ] BareMetalInstanceType with `network_ports` (BareMetalNetworkPortSpec) implemented and tested
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade and Downgrade Strategy

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
- Separate CaaS phase reports the management API VIP and Fabric-reserved guest ingress VIP
- VIP feedback loop: ClusterOrder → fulfillment-service → Cluster → ExternalIPAttachment controller
- Deferred ExternalIPAttachment creation: fulfillment-service internal reconciler creates ExternalIPAttachments after ExternalIP is Allocated and Cluster is Ready

#### Kept

- HyperShift HostedCluster + NodePool creation (same)
- Agent correlation and labeling (BareMetalWorkerReconciler correlates Agents to BMIs via MAC address)
- Enabled-mode tenant/public endpoint DNS updates (in the separately gated
  network phase until the DNS API is implemented)
- Kubeconfig retrieval (same)
- Wait for nodes + cluster operators (same)
- AAP workflow structure (create → post-install → report-status)

### Upgrade and downgrade gates

Follow the [shared coordinated rollout and rollback requirements](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy).
Preserve existing resource/provider bindings, accepted results and cleanup
context. Wire compatibility does not establish backend migration safety.
Drain or verifiably adopt legacy state before using new ownership keys; finish
cleanup with compatible components before downgrading to a version that cannot
interpret the retained state. Disabled-mode provider leftovers still require
confirmed provider/manual cleanup before their addresses or hosts are reused.

### Service compatibility

Cluster attachment and endpoint fields retain their defined wire shapes.
The target replaces step-collection networking with tracked provider operations,
parent-authorized system-tenant workers and Fabric-owned ingress reservations.
Existing clusters cannot be assumed to switch ownership safely because an
API field is additive. Preserve their original cleanup path until verified
migration or ordered drain/recreation completes; do not run both networking
paths against one cluster. New workers require server-side parent validation
before the controller can enable their creation.

## Version Skew Strategy

### Control Plane Skew

Use the [shared version-skew rules](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy).
Fulfillment, the workload/networking controllers and AAP content must agree on
the handoff and cleanup protocol. A coordinated installer release still has a
rolling transition; incompatible components must not dispatch new work.

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

**Cause:** The Subnet is missing/not Ready, provider management publication is unusable from tenant egress, or Fabric ingress reservation is unavailable.

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. Inspect the management bootstrap publication and ingress reservation diagnostics; repair the provider route/DNS/TLS, egress policy, or address capacity. CaaS-only deployments require no VM Kubernetes Manager. [User]

### Symptom: Deletion waits for automatic external cleanup

**Detection:** The parent remains Deleting with its finalizer and child references; an auto-created ExternalIPAttachment or ExternalIP reports a failed cleanup operation.

**Cause:** The provider has not confirmed DNAT removal or address release.

**Resolution:**
1. Inspect parent, child and AAP operation diagnostics to identify the failed task.
2. Repair provider connectivity/configuration or the backend operation; let reconciliation retry with the same durable operation identity.
3. Confirm attachment deletion before address release and parent deletion. Preserve finalizers and address ownership until successful cleanup; do not force-remove finalizers. [User]

### Symptom: ClusterOrder VIPs not synced to Cluster

**Detection:** `kubectl get clusterorder <name> -o yaml` shows `apiEndpoint` and `ingressEndpoint` populated, but `kubectl get cluster <name> -o yaml` shows empty fields

**Cause:** VIP feedback loop failure (Signal RPC failed, or fulfillment-service did not process)

**Resolution:**
1. Check osac-operator feedback controller logs for Signal RPC errors
2. Check fulfillment-service logs for VIP sync errors
3. Manually trigger reconciliation: `kubectl annotate clusterorder <name> osac.openshift.io/reconcile=true`

### Disabling automatic ExternalIP requests

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running clusters

### Provider networking intentionally skipped

Set `global.networking.provisioningEnabled=false` through the Helm setting or Enclave Wizard checkbox
installation/upgrade value map and complete both operator rollouts. Inspect
`Ready=True`/`ProvisioningDisabled` conditions on non-allocating Networking API
resources, `Unknown`/`ProvisioningDisabled` conditions on worker BMI network
phases, and tracked network job states. Ordinary workload provisioning remains
active with the baseline connectivity described
above. Networking APIs remain available; no provider allocation, routing,
port movement, DHCP discovery, or cleanup is supplied by the skipped path.
Existing provider resources may require manual/provider-side cleanup. [User]

## Infrastructure Needed

- AAP execution environment with `osac.templates.ocp_4_17_small` core role updated; a separately tracked CaaS network phase manages enabled-mode MetalLB VIP provisioning
- A Kubernetes Manager that meets the shared manager contract and passes provider qualification, only for deployments also serving VM overlay workloads; it is not a CaaS prerequisite
- Fabric fixed attachment/lease and `reserve_cluster_ingress_ip`/`release_cluster_ingress_ip` entry points; management MetalLB/publication plus the BMaaS provisioning network are deployment prerequisites
- Integration test environment with the deployment-selected Fabric Manager. Add a compatible Kubernetes Manager only when the tested deployment also supports VM overlay networking.
- BareMetalInstanceType test data with `network_ports` (BareMetalNetworkPortSpec)

## Dependencies

Jira states below were checked on 2026-10-12. This is an implementation-tracking snapshot: closed legacy or service issues do not satisfy the target Network Manager Integration Contract, which remains required before provider networking is enabled.

| Dependency | Jira | Status (2026-10-12) |
|-----------|------|---------------------|
| Legacy dispatcher groundwork (not the new NetworkManager/NetworkData contract) | OSAC-1457, OSAC-1458, OSAC-1460 | Closed |
| Legacy two-job lifecycle tracking (does not implement the target durable manager-attempt journal) | OSAC-1459 | Closed |
| Network Manager Integration Contract registration, generic dispatch, result validation, and durable recovery | N/A — defined by the linked contract design; platform implementation remains required | Required before provider networking is enabled |
| NATGateway full stack | OSAC-1443 (10 tasks) | Closed |
| ExternalIPAttachment cluster target in CRD | OSAC-2041 | Closed |
| Cluster DNAT flow in controller | OSAC-1495 | Closed |
| ClusterNetworkAttachment proto | OSAC-1501 | Closed |
| api_endpoint/ingress_endpoint on Cluster status | OSAC-2040 | Closed |
| Immutability validation | OSAC-1503 | Closed |
| DB migration for Cluster networking fields | OSAC-2079 | Closed |
| Server validation | OSAC-1504 | Closed |
| ClusterOrder CRD: singular `networkAttachment` | OSAC-1505 | Closed |
| ClusterOrder CRD: api/ingress endpoint status | OSAC-2080 | Closed |
| VIP discovery flow (feedback) | OSAC-1506 | Closed |
| CaaS template dispatch migration | OSAC-1507 (duplicate; see OSAC-2243) | OSAC-1507: New; OSAC-2243: Closed |
| CaaS endpoint phase: management publication, Fabric ingress reservation, guest single-address MetalLB Service and confirmed status | OSAC-2077 | Closed |
| BareMetalWorkerReconciler (on-demand BMI provisioning + networking) | OSAC-2135 | Closed |
| Historical BMI direct-dispatch groundwork; target SubnetAttachment request lifecycle is shared implementation work | OSAC-2047 | Closed (historical groundwork) |
| CLI --network-attachment for Cluster | OSAC-2076 | Closed |
| Integration test | OSAC-2078 | Review |
| Historical Fabric port-move backend groundwork; fixed attachment/lease adapters and ingress reservation tasks remain shared target implementation work | OSAC-2081 (Netris BM) | Closed (historical groundwork) |
| BareMetalInstanceType: network ports (BareMetalNetworkPortSpec) with name, role, type, speed | OSAC-1201 | Closed |
| Remove cluster_infra / external_access step collection dispatch | Not tracked | **GAP** |
| Remove NETWORK_STEPS_COLLECTION dependency | Not tracked | **GAP** |
| fulfillment-service: resolve interface from BareMetalInstanceType (fabric_interface) | Not tracked | **GAP** |

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: revise @ design 0.11.5 - 1c6e8de, workspace main @ 04cc50101

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"04cc50101","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","respond","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","revise","revise","revise","revise","manual-edit","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
