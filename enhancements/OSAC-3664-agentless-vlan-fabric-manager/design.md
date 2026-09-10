---
title: agentless-vlan-fabric-manager
authors:
  - yonibettan@gmail.com
creation-date: 2026-09-08
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3664
  - https://redhat.atlassian.net/browse/OSAC-4307
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking/design.md"
  - "/enhancements/OSAC-1435-vmaas-networking/design.md"
  - "/enhancements/OSAC-1436-caas-networking/design.md"
  - "/enhancements/OSAC-1437-bmaas-networking/design.md"
replaces:
  - N/A
superseded-by:
  - N/A
---


# Agentless VLAN Fabric Manager

## Summary

This design registers 'agentless_net' as a pluggable physical fabric manager and
implements the existing OSAC Networking API on managed-switch infrastructure.
The implementation reuses the NetworkClass/dispatcher lifecycle, maps each
VirtualNetwork to an isolated Linux routing namespace, maps each Subnet to a
unique VLAN, and provisions DHCP, iptables/netfilter rules, DNAT, and SNAT
through Ansible roles.
See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC currently has a Netris-backed physical fabric path. The repository also
contains agentless VLAN building blocks for CaaS-specific VLAN, router, SNAT,
DNAT, and external-access workflows, but those building blocks are not yet
registered as a unified fabric manager. They do not provide the full resource
lifecycle required by VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool,
ExternalIP, ExternalIPAttachment, and NATGateway. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

The current agentless path allocates VLANs and creates a router namespace per
cluster workflow. The unified networking model requires a namespace per
VirtualNetwork, multiple VLAN-backed Subnets inside that namespace, routing
between those Subnets subject to SecurityGroup policy, and no private routing
between different VirtualNetworks. [Locked: D12] [Research: VLANs and Linux network isolation]

Bare-metal nodes must obtain IPv4 addresses through fabric-side DHCP, and the
lease must reach the resource status path before external access can be enabled.
After network handoff, the bare-metal operator starts the generic DHCP-lease AAP
job. The agentless role queries the per-namespace lease store and publishes
structured lease data; the operator parses that data into per-attachment status,
and the existing feedback path publishes the status to fulfillment-service.
ExternalIPAttachment then waits for the target's primary address before
creating DNAT. [PRD: FR-4] [Codebase: osac-aap/playbook_osac_query_dhcp_lease.yml; bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery.go]

### Goals

- Reuse NetworkClass discovery, dispatcher selection, controller finalizers, and
  provisioning job tracking instead of adding an agentless-specific controller
  architecture. [Codebase: osac-operator/pkg/networkmanager]
- Implement all fabric-manager operations required by the existing Networking API
  without adding public gRPC fields, REST resources, or CRDs. [Locked: D3, D5]
- Use an explicit, idempotent mapping between VirtualNetworks, Subnets, VLANs,
  Linux routing namespaces, DHCP leases, and fabric policy.
- Keep the physical-switch support boundary to the validated Cumulus path for this
  milestone; do not claim support for other NetworkRunner platforms. [User]
- Preserve tenant isolation metadata, existing OPA authorization, and the
  ExternalIPAttachment/DNAT versus NATGateway/SNAT direction split. [Locked: D8, D14, D15]

### Non-Goals

- Adding or changing the public Networking API, resource model, or tenant-facing
  resource types.
- Implementing DNS, IPv6, dual-stack, inline CaaS networking deprecation, or the
  VM-to-fabric k8sManager bridge.
- Implementing VM IP assignment; VMs continue to receive addresses from the OVN
  overlay through the separate k8sManager path. [Locked: D8, D10, D11]
- Delivering per-service BMaaS, CaaS, or VMaaS end-to-end validation owned by
  OSAC-1562, OSAC-1611, and OSAC-3665. BMaaS remains the reference validation
  path for this backend. [Locked: D1, D2]
- Supporting switch platforms other than the validated Cumulus path or claiming
  multi-vendor concurrency guarantees.
- Creating tenant default networking resources; those are created by generic
  tenant onboarding and are consumed by the fabric manager like any other
  Networking API resource. [PRD: §2.2]

## Proposal

The design adds the missing agentless implementation behind the existing
NetworkClass and dispatcher contracts. A provider registers an
'agentless_net' fabric-manager ConfigMap through Helm values and selects it in
the existing deployment configuration. The fulfillment-service and operator
own API validation, tenancy, CRDs, status, finalizers, dependency checks, and
controller-owned ExternalIPPool/ExternalIP allocation. AgentlessNet owns only
data-plane operations: VirtualNetwork/Subnet/SecurityGroup realization, BMF
port binding, DNAT, and SNAT. It reads `ExternalIP.status.address` but does
not allocate or persist ExternalIP ranges or addresses. [PRD: FR-1, FR-2]

The flow below shows the ownership boundary. The operator selects the
implementation strategy and starts generic AAP jobs; the agentless template
performs the switch and net-node work; status returns through job results and
existing resource feedback. It does not introduce a second controller path.

The osac-operator dispatcher is the routing layer between a Networking CR and the selected implementation. It reads the NetworkClass fabric_manager and k8s_manager values, resolves the corresponding labeled manager ConfigMaps, stamps the implementation strategy used by the generic AAP playbook, and lets the existing provisioning lifecycle track retries, finalizers, job history, and status. It does not implement VLAN, DHCP, or NAT behavior itself.
~~~mermaid
flowchart LR
    Admin[Cloud Infrastructure Admin] --> Helm[Helm values and manager registration]
    Helm --> NC[NetworkClass fabricManager agentless_net]
    Tenant[Tenant Admin or User] --> API[Existing Networking API]
    API --> FS[fulfillment-service]
    FS --> CR[Networking CRs and tenant metadata]
    CR --> OP[osac-operator dispatcher]
    OP --> AAP[Generic AAP playbook]
    AAP --> Role[osac.templates.agentless_net]
    Role --> Switch[Cumulus switch VLAN and port]
    Role --> Node[Linux net node namespace DHCP iptables rule NAT]
    Node --> Lease[DHCP lease artifact]
    Lease --> OP
    OP --> Status[Resource status and conditions]
~~~

The diagram separates provider installation from tenant API use and shows
that lease feedback is part of the same provisioning lifecycle as fabric
configuration. The design relies on existing generic playbooks and status
feedback rather than exposing AAP or switch details to tenants.

### Workflow Description

#### Backend registration and installation

Starting state: the provider has a Cumulus switch fabric, an agentless network
node, the required AAP inventories, and provider-scoped ExternalIPPool
resources. Pool CIDRs remain API/controller input and are not AgentlessNet
state.

1. The unified Networking API selects the backend through
   NetworkClass.fabric_manager and the osac-operator dispatcher. It does not
   use NETWORK_STEPS_COLLECTION. That variable selects the AAP collection used
   by embedded CaaS workflows such as cluster_infra and external_access; the
   CaaS follow-up may set it to agentless_net.steps, but this BMaaS-focused
   design does not require changing it. [PRD: FR-1] [Codebase: osac-aap/group_vars/all/configuration.yaml]
2. The admin enables the operator's
   'networkManagers.fabricManagers.agentless_net' Helm entry with
   capabilities 'ipv4', description, and fabric role.
3. The installer creates a ConfigMap labeled
   'osac.openshift.io/network-fabric-manager' with 'data.name=agentless_net'.
   The operator discovers it and includes the manager in NetworkClass
   capability reconciliation. [Codebase: osac-operator/charts/operator/templates/network-managers.yaml]
4. The post-install NetworkClass hook selects 'fabric_manager=agentless_net'.
   The Cloud Infrastructure Admin chooses the physical backend through
   deployment configuration, not through a new UI selector. Existing UI/API
   flows can list and select the resulting NetworkClass by name when creating
   a VirtualNetwork; they do not need to edit the deployment-only
   fabric_manager routing key. No new UI is delivered in this milestone.
   [Locked: D6, D7] [Codebase: osac-ux/libs/ui-components/src/api/v1/networking.ts]
5. The provider supplies the existing agentless inventory and credentials
   configuration. The inventory describes the Cumulus switches, network nodes,
   interfaces, and connection data required by AAP. VLAN allocation is internal
   state from the configured VLAN-ID pool; DHCP is created per Linux namespace;
   and the state file is managed on the network node. These are not tenant or
   Enclave Wizard controls in this milestone. [Codebase: osac-aap/group_vars/all/agentless_net.yaml]

A missing manager registration or a NetworkClass that names an undiscovered
manager prevents dispatch and leaves the affected resource in a diagnostic
failure condition; it does not silently fall back to Netris.

#### Networking resource lifecycle

The Tenant Admin creates and deletes the tenant's Networking API resources:
VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, and
NATGateway. A usable tenant network requires one VirtualNetwork with at least
one Ready Subnet before a machine can attach. SecurityGroup is optional as an
object, but the backend's deny-by-default policy requires an applicable
SecurityGroup rule before traffic is permitted. Tenant Users consume these
resources through their workload workflows.

1. The Tenant Admin creates a VirtualNetwork, one or more Subnets, and any
   SecurityGroups through the existing gRPC/REST API or CLI.
2. fulfillment-service validates object shape, tenant attribution, parent
   references, CIDR containment, and sibling CIDR overlap. It writes the
   owner-reference annotation on Subnets and materializes the corresponding CR
   with tenant metadata. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]
3. The osac-operator controller adds its finalizer, resolves the NetworkClass,
   and dispatches resources with fabric side effects through the generic AAP
   playbook. The implementation strategy selects
   `osac.templates.agentless_net`.
4. AgentlessNet reconciles the desired fabric state idempotently: one namespace
   and default-deny baseline per VirtualNetwork, one VLAN/interface/gateway/
   DHCP binding per Subnet, and owned iptables/netfilter rules per
   SecurityGroup. Subnet reconciliation never binds a host access port.
5. ExternalIPPool and ExternalIP remain controller-managed allocation
   resources. ExternalIPAttachment and NATGateway dispatch only their DNAT/SNAT
   operations after controller preconditions are satisfied.
6. AAP job history and resource status are updated only after the desired
   operation completes. Retries reuse UID-keyed state and repair partial data
   plane configuration instead of allocating duplicate VLANs or namespaces.

The fulfillment-service remains authoritative for a client-supplied Subnet CIDR.
AgentlessNet validates that the requested CIDR is inside the VirtualNetwork
supernet and does not overlap a sibling before applying data-plane state; it
does not allocate a second CIDR or contradict the service object. Automatic
Subnet CIDR allocation, if required by a future API path, remains an open
question because the current API requires a CIDR and the current service
already performs this validation. [Codebase: fulfillment-service/proto/private/osac/private/v1/subnet_type.proto]

#### BMaaS attachment and DHCP feedback

This design specifies the BMaaS reference path. CaaS and VMaaS service-specific
attachment workflows follow in OSAC-1611 and OSAC-3665; their workflows and
service-specific input contracts are not expanded here. [Locked: D1, D2]

1. The bare-metal-fulfillment-operator resolves the BareMetalInstance network
   attachments, host interface names, and Subnet references. It resolves NIC
   MAC addresses from the management backend when available.
2. After host provisioning, the BMF flow starts the generic
   `playbook_osac_move_network_attachment.yml` AAP job. The playbook resolves
   each `subnetRef` and dispatches the backend-specific
   `move_network_attachment` entrypoint. For this design, a new
   `osac.templates.agentless_net` role must provide
   `tasks/move_network_attachment.yaml` to resolve the host interface and bind
   the corresponding switch port to the Subnet VLAN.
3. The target obtains an IPv4 address through DHCP in the VN namespace. One
   DHCP service is bound to every Subnet VLAN interface in that namespace, so
   each Subnet's broadcast domain has a local DHCP presence. Central DHCP with
   relay is not supported in this milestone. [PRD: FR-4] [Locked: D13] [User]
   [Research: Local DHCP presence per broadcast domain]
4. The generic 'playbook_osac_query_dhcp_lease.yml' invokes the selected
   template's 'query_dhcp_lease' task for each network attachment. The agentless
   task matches the attachment identity and Subnet to the lease store and
   publishes the existing 'leases' AAP artifact through 'set_stats'.
5. The operator validates the artifact's job status, attachment identity, MAC or
   interface identity, Subnet reference, address family, and freshness before
   writing the observed address to the resource status.
6. The bare-metal operator retrieves the completed AAP job, parses
   DHCPLeaseResult.Leases, maps each lease by SubnetRef, validates the IP
   address, and writes Status.NetworkAttachmentStatuses. If a lease is missing
   or invalid, IP discovery remains failed and reconciliation retries.
7. The osac-operator BareMetalInstance feedback controller watches the CR status
   change and calls the fulfillment-service BareMetalInstances.Signal RPC.
   fulfillment-service persists the status, after which ExternalIPAttachment
   reconciliation can read the target's primary IP and create DNAT.
8. CaaS and VMaaS attachment and IP-address workflows remain follow-up work.
   VM IP assignment and OVN bridging are not performed by this backend. [Locked: D8]

#### ExternalIP and inbound access

1. A Cloud Infrastructure Admin creates an ExternalIPPool containing IPv4
   ranges through the existing API.
2. Creating the ExternalIPPool defines capacity; it does not allocate an
   address or create a traffic rule. The fulfillment-service validates that a
   referenced pool is Ready and has capacity when an ExternalIP is created,
   reserves the address in the controller-owned API state, and exposes the
   assigned address through ExternalIP status. AgentlessNet does not receive or
   persist the pool range or the allocation. The ExternalIP becomes ALLOCATED
   but still carries no DNAT rule.
3. The Tenant Admin creates an ExternalIPAttachment that references the
   allocated ExternalIP and targets a supported resource. A Tenant User may
   request this through an authorized workload workflow, but the Networking
   API resource lifecycle remains Tenant Admin-owned.
4. The controller waits until the target's primary private address is present
   and current in status. Until then, the attachment remains pending and the
   controller does not dispatch an AAP attachment job.
5. Once the target address is available, the controller dispatches the
   agentless `create_external_ip_attachment` operation. The role creates only
   the owned DNAT mapping from the controller-assigned ExternalIP address to
   the target address. The VirtualNetwork default-deny baseline and
   SecurityGroup rules are reconciled independently by their own lifecycles;
   the attachment operation does not create or update SecurityGroup rules.
6. The attachment reaches Ready only after the AAP job and status feedback
   confirm the DNAT operation. Traffic not permitted by the already-applied
   default-deny/SecurityGroup policy is dropped. [PRD: FR-5]

ExternalIP is an allocated address resource independent of any VirtualNetwork.
ExternalIPAttachment is the separate binding that gives that address an
inbound target. NATGateway is another separate consumer that references an
allocated ExternalIP for outbound SNAT. Creating a VirtualNetwork does not
create any of these resources. [Codebase: fulfillment-service/proto/private/osac/private/v1/external_ip_type.proto; fulfillment-service/proto/private/osac/private/v1/external_ip_attachment_type.proto; fulfillment-service/proto/private/osac/private/v1/nat_gateway_type.proto]

ExternalIPAttachment is inbound only. It does not create outbound SNAT and does
not alter the NATGateway configuration. [Locked: D14]

#### NATGateway and outbound access

1. A Tenant Admin creates a NATGateway for a VirtualNetwork and supplies an
   explicit reference to an already allocated ExternalIP.
2. The controller resolves that ExternalIP reference and verifies that the
   ExternalIP is allocated, belongs to the expected tenant scope, and is not
   already consumed by another NATGateway or ExternalIPAttachment.
3. The agentless role configures outbound SNAT on the VN namespace uplink.
   The source address observed by the external endpoint is the controller-
   approved address in the referenced ExternalIP status. AgentlessNet does not
   repeat the allocation, tenant-scope, or exclusivity checks and does not
   introduce a separate hidden net-node address.
4. The independently reconciled `filter/FORWARD` default-deny and
   SecurityGroup rules determine which packets reach the SNAT path. The
   NATGateway role does not evaluate or modify that policy; packets accepted by
   forwarding are translated in `POSTROUTING`, and established return traffic
   follows the stateful connection policy.
5. The NATGateway status reaches Ready after the AAP job completes. [PRD: FR-6]
   [Locked: D14]

NATGateway is outbound only. It does not create an inbound DNAT mapping.

#### Failure and recovery workflow

For every operation, the controller records the AAP job target, attempt, and
failure message in the existing provisioning history and status condition.

- If the manager ConfigMap is absent, dispatch stops before an external side
  effect and the resource reports a configuration failure.
- If VLAN allocation or the state-file lock fails, the operation is retried
  without changing existing allocations.
- If switch configuration succeeds but net-node configuration fails, the
  controller retries the missing desired state and cleanup logic removes the
  switch VLAN only when the resource is being deleted.
- If DHCP returns no matching lease, the BMaaS attachment remains non-ready
  with a diagnostic condition and the query is retried. The independent
  ExternalIP allocation is not changed, but an ExternalIPAttachment does not
  create DNAT until the target's primary private address is known. A
  NATGateway also remains an independent lifecycle once its referenced
  ExternalIP is allocated.
- If the AAP job reports failure but leaves a partial rule, the role's
  idempotent desired-state pass converges the rule before marking Ready.
- If a controller restarts, it reconstructs the desired operation from the CR,
  job history, and lock-protected state rather than treating the in-memory task
  as authoritative.

#### Deletion and cleanup

1. The resource controller observes deletion and retains its finalizer.
2. For an ExternalIPAttachment, remove DNAT and wait for confirmed removal.
3. Release the ExternalIP only after its attachment is removed.
4. For a NATGateway, remove its owned SNAT rules. The referenced ExternalIP
   remains a separate resource and is not released implicitly.
5. For a SecurityGroup, remove only the iptables chains and rules generated for
   that SecurityGroup after existing API dependency checks permit deletion.
6. For a Subnet, remove DHCP, its VLAN subinterface, gateway IP, and
   SecurityGroup-owned iptables rules, then release the VLAN ID.
7. For a VirtualNetwork, remove remaining child fabric state, external boundary,
   and namespace after children are gone.
8. Remove the finalizer only after the fabric manager reports the desired
   cleanup state. [PRD: FR-11] [Codebase: osac-operator/pkg/provisioning]

The Cloud Infrastructure Admin owns the provider-scoped manager and
ExternalIPPool resources. The Tenant Admin owns creation and deletion of the
tenant's VirtualNetwork, Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment,
and NATGateway resources. Agentless_net never creates or deletes those API
objects; it applies and removes the fabric state during their existing
reconciliation lifecycles. This feature creates no default networking resources.

### API Extensions

No new public gRPC service, REST resource, protobuf field, CRD kind, or webhook
is introduced. Existing fabric-facing resources receive the agentless backend;
ExternalIPPool and ExternalIP retain their controller-owned allocation
lifecycle, while ExternalIPAttachment and NATGateway use the assigned address
for DNAT/SNAT. Existing status and condition fields carry observed readiness
and diagnostic failures. [Locked: D3, D5, D9]

The implementation changes the following existing surfaces:

| ID | Existing surface | Change | Requirements |
|---|---|---|---|
| IC-1 | Installer values, manager ConfigMap, NetworkClass selection | Register and select 'agentless_net' as a fabric manager with IPv4 capability | FR-1, NFR-1 |
| IC-2 | VirtualNetwork, Subnet, SecurityGroup API/CR lifecycle | Route existing fabric resources through the agentless dispatcher and realize VLAN, namespace, iptables rule, and cleanup state | FR-2, FR-3, FR-11, NFR-2, NFR-3 |
| IC-3 | Fabric network-attachment and DHCP feedback path | Attach BM/CaaS/VM targets through the existing generic contract and surface fabric-assigned IPs for BM/CaaS | FR-4, FR-8 |
| IC-4 | ExternalIPPool, ExternalIP, and ExternalIPAttachment lifecycle | Preserve controller-owned pool/address allocation and apply inbound DNAT using the assigned address | FR-5, FR-7, FR-11, NFR-2, NFR-3 |
| IC-5 | NATGateway lifecycle | Apply outbound SNAT using the controller-approved ExternalIP; existing forwarding policy controls eligibility | FR-6, NFR-2, NFR-3 |
| IC-6 | Resource status, conditions, events, and job history | Surface manager registration, provisioning, DHCP, switch, iptables rule, NAT, and cleanup failures with diagnostic reasons | FR-10, NFR-2 |

#### Existing resource and metadata constraints

- Tenant-scoped resources retain 'osac.openshift.io/tenant' and
  'osac.openshift.io/owner-reference' annotations. No backend-created
  tenant object may omit them. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]
- NetworkClass, ExternalIPPool, and manager registration remain
  provider-scoped according to the existing API and OPA policy.
- No API-level field is added for VLAN ID, Linux namespace, DHCP server, switch
  platform, or AAP job ID. Those are implementation state and status metadata,
  not tenant API inputs.

#### NetworkAPI resource CRs and implementation points

The following examples show the Kubernetes CR representation of each existing
Networking API resource handled by the agentless fabric manager. `status` is
controller-owned and is shown only to explain the important observed fields;
users submit the `spec` and do not write `status`. The tenant-scoped examples
include the required tenant and owner-reference annotations. `NetworkClass` is
a fulfillment-service API object rather than an operator CR, so its
`fabric_manager: agentless_net` selection is represented by the
`VirtualNetwork.spec.networkClass` field and the manager-registration section
above.

##### VirtualNetwork

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: VirtualNetwork
metadata:
  name: vnet-a
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  region: region-a
  ipv4Cidr: 10.20.0.0/16
  networkClass: agentless-vlan
status:
  phase: Ready
  backendNetworkId: <agentless-virtual-network-id>
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.region` identifies the deployment region, `spec.ipv4Cidr` is the
VirtualNetwork supernet, and `spec.networkClass` selects the existing
NetworkClass whose fabric manager is `agentless_net`. `status.phase` and
`status.conditions` expose reconciliation and failure state; the
provider-specific `status.backendNetworkId` identifies the realized network
without exposing a Linux namespace name.

AgentlessNet maps the VirtualNetwork UID to one deterministic Linux routing
namespace, creates its uplink/external boundary, and initializes an owned
default-deny iptables/netfilter policy on that namespace's `filter/FORWARD`
path. The baseline permits established/related return traffic but no new
routed tenant flow until an explicit policy allows it. Local DHCP traffic
terminates in the namespace and is not routed through this baseline. AgentlessNet
records the mapping in the locked state file; it does not create tenant child
resources or install private routes to another VirtualNetwork.

##### Subnet

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: Subnet
metadata:
  name: subnet-a
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  virtualNetwork: vnet-a
  ipv4Cidr: 10.20.1.0/24
status:
  phase: Ready
  backendNetworkId: <agentless-subnet-id>
  conditions:
  - type: NetworkReady
    status: "True"
~~~

`spec.virtualNetwork` references the parent routing domain and
`spec.ipv4Cidr` supplies the client-selected, non-overlapping subnet CIDR.
`status.phase`, `status.conditions`, and `status.backendNetworkId` report
observed provisioning; the VLAN ID is deliberately not a tenant API field.

AgentlessNet allocates one globally unique VLAN ID for the Subnet UID, creates
the VLAN on the Cumulus switch through the validated NetworkRunner path, moves
the VLAN interface into the parent namespace, assigns the gateway, and binds
the per-namespace DHCP service to the interface. It does not assign physical
access ports during Subnet provisioning. Reconciliation reuses the recorded
VLAN on retry and supports multiple Subnets in one VirtualNetwork.

Physical port assignment is deferred to the BMF attachment flow. The BMF
controller associates a machine interface with a `subnetRef` and invokes the
generic `playbook_osac_move_network_attachment.yml`, which must dispatch to the
new `osac.templates.agentless_net/tasks/move_network_attachment.yaml` role for
the AgentlessNet-specific switch-port operation.

This direct BMF-to-AAP attachment boundary is not an ideal design because it
couples the BMF flow to a backend job contract instead of representing the
binding as a declarative Networking API object. The design is currently
investigating a future `SubnetAttachment` CRD in the Network API; BMF would
create that object and the networking operator would reconcile the port binding.
That CRD is not introduced by this milestone, so the generic AAP flow remains
the implementation path described here.

##### SecurityGroup

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: SecurityGroup
metadata:
  name: web-access
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  virtualNetwork: vnet-a
  ingressRules:
  - protocol: tcp
    portFrom: 443
    portTo: 443
    sourceCidr: 0.0.0.0/0
  egressRules:
  - protocol: all
    destinationCidr: 0.0.0.0/0
status:
  phase: Ready
  backendSecurityGroupId: <agentless-rule-set-id>
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.virtualNetwork` scopes the policy. `spec.ingressRules` and
`spec.egressRules` are the existing allow-rule model; an empty or missing
allow rule does not create an allow-by-default path. `status.phase`,
`status.conditions`, and `status.backendSecurityGroupId` report whether the
policy was accepted and realized.

AgentlessNet compiles the rules into owned iptables/netfilter chains at the
VirtualNetwork routing boundary, including the required default-deny and
established-connection behavior. It applies only the chains owned by this
SecurityGroup and leaves other tenants' rules unchanged. Attachment workflows
determine which SecurityGroups apply to a workload interface.

##### ExternalIPPool

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ExternalIPPool
metadata:
  name: public-ipv4
  namespace: osac-networking
spec:
  cidrs:
  - 198.51.100.0/29
  ipFamily: IPv4
status:
  phase: Ready
  total: 6
  allocated: 1
  available: 5
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.cidrs` and `spec.ipFamily` are provider-defined pool capacity. The
provider-scoped `status.total`, `status.allocated`, and `status.available`
fields expose capacity and consumption; `status.conditions` carries pool
validation or provisioning failures.

The fulfillment-service calculates `status.total` and the initial
`status.available` when the pool is created. When an ExternalIP is created or
deleted, fulfillment-service locks the pool record and adjusts
`status.allocated` and `status.available` atomically. The
ExternalIPPoolReconciler separately reports the controller-level pool phase; it
does not own capacity accounting. AgentlessNet does
not receive or persist the pool range, and it does not update these counters.
Its ExternalIPAttachment and NATGateway operations consume the current
ExternalIP status address when programming rules. Creating the pool does not
allocate an address and does not create DNAT or SNAT rules.

##### ExternalIP

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ExternalIP
metadata:
  name: public-ip-1
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  pool: public-ipv4
status:
  phase: Ready
  state: Allocated
  address: 198.51.100.2
  attached: false
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.pool` requests an address from the named provider pool. The
Tenant Admin creates this resource; it is not implicitly created by a tenant
or by AgentlessNet. `status.address` is the allocated IPv4 address,
`status.state` reports allocation, and `status.attached` reports whether an
ExternalIPAttachment is currently using it.

The fulfillment-service/controller allocates the address, publishes it in
`status.address`, and maintains the allocation across reconciliation.
AgentlessNet does not mirror the pool or allocation in its state file.
Allocation alone creates no traffic rule; the controller-assigned address is
consumed later by an ExternalIPAttachment or a NATGateway, subject to the
existing dependency and exclusivity checks.

##### ExternalIPAttachment

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ExternalIPAttachment
metadata:
  name: public-ip-1-to-bm-1
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  externalIP: public-ip-1
  baremetalInstance: bm-1
status:
  phase: Ready
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.externalIP` selects the allocated address and exactly one target field
selects the ComputeInstance, Cluster, or BareMetalInstance. `targetEndpoint`
is additionally required for a cluster target. `status.phase` and
`status.conditions` report whether the attachment is active; the target's
private address remains in the existing attachment/network status path rather
than becoming a new ExternalIPAttachment API field.

The ExternalIPAttachment controller waits for the target's primary IPv4 address
from the existing DHCP lease/status feedback path. If the address is missing
or stale, it keeps the attachment pending and does not dispatch the AAP job.
Once the target address is current, AgentlessNet creates an owned DNAT rule
from the controller-assigned ExternalIP address to that target. The
VirtualNetwork default-deny baseline and SecurityGroup rules are maintained by
the VirtualNetwork and SecurityGroup lifecycles, not by the attachment role.

##### NATGateway

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NATGateway
metadata:
  name: vnet-a-egress
  namespace: tenant-a
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: <tenant-owner-reference>
spec:
  virtualNetwork: vnet-a
  externalIP: egress-ip-1
status:
  phase: Ready
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.virtualNetwork` selects the private routing domain and `spec.externalIP`
explicitly references an already allocated ExternalIP. `status.phase` and
`status.conditions` report whether the SNAT path is active; the CR does not
duplicate the referenced address.

The NATGateway controller validates the referenced ExternalIP allocation,
tenant scope, and exclusivity before dispatching the backend operation.
AgentlessNet consumes the controller-approved address in
`ExternalIP.status.address` and installs owned SNAT rules; it does not repeat
those validation checks or evaluate SecurityGroup egress policy. Deleting the
NATGateway removes its SNAT rules but does not release the ExternalIP;
ExternalIP deletion remains a separate Tenant Admin operation.

The CR examples show the API boundary. VLAN IDs, namespace names, DHCP lease
records, iptables chains, conntrack/NAT state, and AAP job identifiers remain
implementation state and are reconciled through the existing status,
conditions, job history, and feedback paths.

## UX Alignment

The active osac-ux checkout contains the networking @temp-api contract in
'osac-ux/libs/ui-components/src/api/v1/networking.ts'. This design adds no new
tenant API fields, so the agentless backend must preserve the existing mappings:

| UI field | Proto field | Notes / deviation |
|---|---|---|
| 'VirtualNetwork.spec.networkClass' | 'VirtualNetwork.spec.network_class' | Existing direct mapping; backend selection remains provider-side |
| 'VirtualNetwork.spec.ipv4Cidr' | 'VirtualNetwork.spec.ipv4_cidr' | Existing direct mapping |
| 'Subnet.spec.virtualNetwork' | 'Subnet.spec.virtual_network' | Existing parent reference |
| 'Subnet.spec.ipv4Cidr' | 'Subnet.spec.ipv4_cidr' | Existing CIDR field |
| 'SecurityGroup.spec.virtualNetwork' | 'SecurityGroup.spec.virtual_network' | Existing parent reference |
| 'SecurityGroup.spec.ingress' | 'SecurityGroup.spec.ingress' | Existing rule list |
| 'SecurityGroup.spec.egress' | 'SecurityGroup.spec.egress' | Existing rule list |

The Kubernetes CR represents the same public rules as `spec.ingressRules` and
`spec.egressRules`; the service/operator mapping preserves the public
`ingress`/`egress` API names. No deviation is introduced. The UI does not
select the physical fabric
manager and no UI code is required for this milestone. Future UI work is
tracked separately in OSAC-4308 and OSAC-4309. [PRD: §2.2] [Codebase: osac-ux/libs/ui-components/src/api/v1/networking.ts]
### Implementation Details/Notes/Constraints

#### Manager registration and dispatch

The osac-operator discovers ConfigMaps labeled
'osac.openshift.io/network-fabric-manager'. The ConfigMap data includes the
manager name, description, and comma-separated capabilities. The Helm chart
entry must render:

- name: 'agentless_net'
- role: 'fabric'
- capabilities: 'ipv4'
- description identifying the Cumulus-supported agentless VLAN backend

The manager name must match the NetworkClass 'fabric_manager' value and the
AAP implementation-strategy annotation. Unknown or disabled manager names must
produce a status failure rather than selecting another manager. [Codebase: osac-operator/pkg/networkmanager; osac-operator/charts/operator/templates/network-managers.yaml]

#### NetworkClass capability boundary

The agentless registration declares IPv4 support and does not declare IPv6 or
dual-stack. The fulfillment-service's existing capability validation rejects
unsupported address-family requests before the provisioning job is launched.
This keeps the dual-stack-ready API intact while enforcing the milestone
boundary through NetworkClass capabilities. [Locked: D10, D11]

#### VirtualNetwork and Subnet realization

The agentless role uses deterministic names derived from the resource UID, not
tenant-provided display names, for Linux namespaces and state keys. The mapping
is:

1. VirtualNetwork UID -> one Linux router namespace.
2. Subnet UID -> a lookup key for one numeric VLAN allocation from the internal
   fabric VLAN-ID pool. The VLAN number is separate from the Subnet UID, and
   the usable 802.1Q range is approximately 4094 IDs per physical fabric.
3. VLAN ID -> one VLAN subinterface moved into the VirtualNetwork namespace.
4. Subnet CIDR -> gateway address and DHCP scope in that namespace.
5. VirtualNetwork namespace -> one uplink boundary used for routing and external
   NAT.

The VLAN allocation is globally unique within the physical fabric. Reconciliation
looks up the Subnet UID before allocating, so retries preserve the same VLAN.
VLAN state is protected by an exclusive file lock and persisted before the
switch or namespace operation is reported complete. [PRD: FR-3] [PRD: Risk 8.5]
[Research: VLAN-backed L2 with a separate L3 boundary]
The current service validates Subnet CIDR containment and sibling overlap. The
backend must not create a second CIDR allocation that contradicts the service
object. Whether automatic CIDR allocation is required beyond the current
client-supplied Subnet API remains an open question. [Codebase: fulfillment-service/proto/private/osac/private/v1/subnet_type.proto]

#### Net-node state file and API action mapping

The JSON state file used by the agentless net node becomes versioned and
resource-oriented. Its logical sections are lists of entries keyed by stable
resource identifiers. The state file tracks only data-plane resources and
rules owned by AgentlessNet; ExternalIPPool and ExternalIP allocation remain
fulfillment-service/controller state.

##### State structure

~~~yaml
schema_version: 1
virtual_networks:
  - uid: <virtual-network-uid>
    namespace_name: <deterministic-name>
    uplink: <interface-or-veth-identity>
    default_deny: true
subnets:
  - uid: <subnet-uid>
    virtual_network_uid: <uid>
    vlan_id: <integer>
    gateway_ipv4: <address>
security_groups:
  - uid: <security-group-uid>
    virtual_network_uid: <uid>
    rule_generation: <generation>
    ingress_chain: <owned-chain-name>
    egress_chain: <owned-chain-name>
attachments:
  - uid: <external-ip-attachment-uid>
    external_ip_uid: <uid>
    target_address: <ipv4>
    mode: dnat
nat_gateways:
  - uid: <nat-gateway-uid>
    external_ip_uid: <uid>
    mode: snat
port_bindings:
  - key: <baremetal-instance-uid>/<interface>/<subnet-uid>
    subnet_uid: <subnet-uid>
    vlan_id: <integer>
    host_name: <host-name>
    interface: <logical-interface>
~~~

The `attachments` and `nat_gateways` entries identify the API resource whose
DNAT or SNAT rules are owned by the backend; the role reads the current
ExternalIP status when it reconciles those rules. `port_bindings` tracks the
temporary BMF-to-Subnet attachment operation because the current milestone
invokes the generic attachment playbook directly; a future SubnetAttachment
CRD could replace this integration boundary. The existing low-level IPAM
`public_ips` map is not retained in the unified backend state. The exact
serialized names may follow the current collection conventions, but the state
must be keyed by stable OSAC resource identifiers rather than arbitrary
cluster-purpose strings. State writes are atomic, locked, and idempotent. A
state schema version permits an additive migration if the backend state format
changes. [Codebase: osac-aap/collections/ansible_collections/agentless_net/ipam]

##### API action state transitions

| API action | State transition | AgentlessNet data-plane operation |
|---|---|---|
| VirtualNetwork create/update/delete | Add or reconcile one `virtual_networks` entry; remove it after child entries are gone | Create or repair the namespace, uplink, and default-deny baseline; remove them during ordered cleanup |
| Subnet create/update/delete | Add or reuse one `subnets` entry and its `vlan_id`; remove it and release the VLAN after dependent bindings are gone | Create or repair the switch VLAN, namespace interface, gateway, and DHCP scope; no host access-port binding during Subnet provisioning |
| SecurityGroup create/update/delete | Add or replace the `security_groups` entry and rule generation; remove its owned chains on delete | Compile or remove only that SecurityGroup's iptables/netfilter rules; preserve the VN default-deny baseline |
| ExternalIPPool create/delete | No AgentlessNet state entry | Controller/API capacity and readiness only; no backend address allocation |
| ExternalIP create/delete | No AgentlessNet state entry | Controller/API allocation and release only; no data-plane rule |
| ExternalIPAttachment create/delete | Add, replace, or remove one `attachments` entry | Read the controller-assigned ExternalIP address and target status, then create or remove the owned DNAT rule |
| NATGateway create/delete | Add or remove one `nat_gateways` entry | Read the controller-approved ExternalIP address and create or remove the owned SNAT rule |
| BMF attachment bind/unbind | Add or remove one `port_bindings` entry keyed by machine, interface, and Subnet | Move the Cumulus access port to or from the Subnet VLAN through the generic attachment playbook |

Every transition is applied under the state-file lock and is persisted before
the corresponding operation is reported successful. A retry reads the entry
by stable UID or binding key and converges the desired data-plane state instead
of allocating a second VLAN or creating duplicate owned rules. [User]

#### DHCP and lease feedback

The implementation runs one DHCP service in each VN namespace and binds it to
every Subnet VLAN interface. This gives DHCPDISCOVER broadcasts a local
interface in each L2 domain and allows one lease store to serve all Subnets in
the VN. Central DHCP with relay is not a supported deployment option for this
milestone. [Locked: D13] [User] [Research: Local DHCP presence per broadcast domain]

The agentless 'query_dhcp_lease' role accepts the generic attachment inputs:

- host identity;
- logical interface name or MAC identity;
- Subnet reference;
- requested address family, fixed to IPv4 for this milestone.

It looks up the lease by attachment identity and Subnet, rejects an ambiguous
or stale match, and publishes a list under the AAP 'leases' artifact. The
operator consumes only a successful job artifact whose identity matches the
current resource generation. A missing lease causes a requeue and diagnostic
condition; it does not create a DNAT rule with an empty target. [PRD: FR-4,
FR-10] [Codebase: osac-aap/playbook_osac_query_dhcp_lease.yml]

#### SecurityGroup policy

VirtualNetwork creation establishes the default-deny iptables/netfilter
baseline in the namespace's `filter/FORWARD` path. SecurityGroup create,
update, and delete operations only add, replace, or remove the rules owned by
that SecurityGroup; they do not create or remove the baseline policy.

SecurityGroup rules are translated into owned iptables/netfilter rules at the
VN routing boundary. The implementation uses the existing Netris behavior as
the parity reference and must document the exact protocol, port, CIDR,
direction, default, and established-connection semantics in the role contract.
The PRD requires unpermitted inbound, cross-Subnet, and outbound traffic to be
blocked; therefore an absent allow rule cannot produce an allow-by-default path.
[PRD: FR-3, FR-5, FR-6] [Research: OpenStack Neutron routing and security model]

The iptables rule compiler is idempotent. It replaces only rules owned by the target
SecurityGroup/VN and does not modify another tenant's rules. A failed compile
leaves the previous applied policy in place where possible and reports the
failed desired generation in status.

#### ExternalIP, DNAT, and SNAT

ExternalIPPool CIDRs and ExternalIP allocation are controller-owned API state.
AgentlessNet consumes the allocated address from ExternalIP status and does
not maintain a second pool or allocation database. ExternalIP release remains
blocked while an ExternalIPAttachment still owns the inbound mapping.

ExternalIPAttachment creates a destination translation from the controller-
assigned ExternalIP to the target's primary private address. It never changes
the NATGateway SNAT rule. NATGateway creates a source translation for packets
that pass the independently reconciled forwarding policy, using its associated
ExternalIP. These operations use separate state sections, role entrypoints,
and deletion paths. [Locked: D14]

Cross-VirtualNetwork private routing is not installed. If two VNs use
overlapping CIDRs, their separate namespaces prevent direct private routing.
Access between them requires the explicit external path through ExternalIP and
NATGateway. [Locked: D15] [Research: Address-realm boundaries]

#### AAP role layout

The agentless implementation must provide:

- 'osac.templates.agentless_net' registration metadata with
  'template_type: network', 'fabric_manager: agentless_net', and IPv4-only
  capabilities.
- Generic network resource entrypoints for VirtualNetwork, Subnet,
  SecurityGroup, ExternalIPAttachment, and NATGateway. ExternalIPPool and
  ExternalIP capacity/allocation remain fulfillment-service/controller
  responsibilities; the backend only consumes their status when programming
  DNAT or SNAT.
- Generic network attachment entrypoints for create/delete or equivalent
  attach/detach operations. The AgentlessNet implementation must add
  `osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/tasks/move_network_attachment.yaml`
  for the BMF attachment flow.
- 'query_dhcp_lease' compatible with the generic query playbook.
- Shared step roles for VLAN/IPAM, router namespace, DHCP, SecurityGroup
  iptables rules, DNAT, SNAT, and Cumulus port configuration.
- Role argument validation and idempotent create/delete behavior.

The existing 'agentless_net.steps' collection remains reusable where its
inputs and lifecycle match the unified resource contract. Cluster-specific
static NMStateConfig and BGP endpoint code is not treated as the generic
Networking API implementation. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

#### Fulfillment-service coordination

No new proto or REST field is required. The service-side work is limited to
confirming that all active validation and reconciliation paths allow the
multiple-Subnet behavior required by D12, updating stale 1:1 documentation,
and preserving existing tenant/owner metadata. The current Subnet server already
checks CIDR subset and sibling overlap and has tests for multiple Subnets.
[Codebase: fulfillment-service/internal/servers/private_subnets_server.go]

If a downstream one-Subnet guard is found, it must be changed in the same
implementation plan because a backend that can configure multiple VLANs is not
user-complete while the service rejects the second Subnet. [PRD: C1]

#### Installer and Enclave Wizard

The installer already accepts 'agentless_net' and 'agentless_net.steps' in the
schema. The implementation adds the manager registration and only adds new
Helm values for inputs that cannot be derived from existing inventory or
configuration. Any new value must have:

- a typed entry in 'charts/osac/values.yaml';
- a matching schema entry in 'charts/osac/values.schema.json';
- a description, default, and validation constraint;
- documentation for the Cloud Infrastructure Admin.

The Enclave Wizard renders standard schema controls automatically. A custom
wizard workflow is not part of this design. [Codebase: osac-installer/charts/osac/values.schema.json; .design/context/enclave-wizard-pipeline.md]

### Security Considerations

No new authentication mechanism or tenant authorization policy is introduced.
The existing fulfillment-service OPA/authentication path remains the authority for
API access, and the operator continues to process tenant-scoped CRs in their
existing namespace/annotation boundaries. [Codebase: fulfillment-service/internal/auth]

The implementation must preserve 'osac.openshift.io/tenant' and
'osac.openshift.io/owner-reference' on tenant-scoped resources. Provider-scoped
NetworkClass and ExternalIPPool operations remain restricted to provider
personas. The fabric role must reject a tenant's identifier when it does not
match the resource's server-side attribution; it must not rely on user-supplied
display names for isolation. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]

AAP network jobs require privileged access to network nodes and switches.
Credentials are supplied through existing Kubernetes Secrets/inventory
configuration and are not placed in CR status, events, or normal logs. Shell
commands and role inputs must be parameterized from validated resource data;
no tenant-controlled value may become an unquoted command fragment.

The two critical isolation controls are unique VLAN allocation per physical
fabric and separate routing namespaces per VirtualNetwork. Reusing a VLAN ID
across VNs or installing a shared route between overlapping VNs violates NFR-3.
[PRD: NFR-3] [Locked: D12, D15]

### Failure Handling and Recovery

| Failure | Recovery | Observable result |
|---|---|---|
| Manager ConfigMap missing or capability mismatch | Stop before AAP side effects; requeue after manager discovery changes | Resource condition identifies missing manager/capability |
| Invalid NetworkClass or unsupported IPv6 request | API/controller validation rejects before provisioning | Invalid argument or failed condition names address family |
| VLAN state lock unavailable | Retry with backoff; preserve existing allocation | Provisioning remains pending with lock diagnostic |
| VLAN allocation exhausted or already owned | Do not reuse an allocated ID; fail the requested generation | Failed condition identifies VLAN allocation exhaustion/conflict |
| Switch VLAN or access-port operation fails | Retry idempotently; leave existing applied state untouched when possible | AAP failure and resource status contain switch error |
| Namespace/VLAN interface creation partially fails | Reconcile desired namespace and interfaces; remove only orphaned state on delete | Resource remains non-ready with net-node error |
| DHCP lease absent or ambiguous | Requery; do not update status or create DNAT until identity/freshness checks pass | Condition identifies lease-unavailable/ambiguous |
| AAP lease artifact is stale or job failed | Ignore artifact, retain current status, retry current generation | Job failure and resource condition remain visible |
| iptables rule compilation fails | Keep last known policy where safe; retry desired generation | SecurityGroup/VN condition identifies policy error |
| DNAT/SNAT operation partially fails | Compare desired state with owned rules and repair; never release an IP before DNAT removal | Attachment/NAT condition and job history identify failure |
| Delete is interrupted | Finalizer re-enters the ordered cleanup phases after restart | Resource remains terminating with cleanup reason |
| Net node restarts | Rehydrate state from the versioned state file and reconcile actual interfaces/rules | Existing resource statuses remain non-ready until observed state converges |

All create/delete operations are keyed by stable resource UID and desired
generation. AAP retries must be safe after a controller restart or lost job
response. [Codebase: osac-operator/pkg/provisioning/provision_lifecycle.go]
### RBAC / Tenancy

No new RBAC or authentication policy is required. Existing OPA and attribution
logic controls who can create or modify tenant resources; provider personas
control NetworkClass, manager registration, and ExternalIPPool configuration.

Tenant-scoped Kubernetes resources retain both
'osac.openshift.io/tenant' and 'osac.openshift.io/owner-reference'. The
owner-reference points to the parent resource where the existing service path
sets it. The operator and service use these annotations for filtering and
feedback attribution. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]

The agentless role receives validated private resource data through AAP. It
must not use a tenant-provided name as an isolation key; the resource UID and
server-side tenant attribution are the isolation inputs.

### Observability and Monitoring

No new Prometheus metric family is required for the initial implementation.
Existing controller reconciliation, AAP job, and resource condition metrics
remain the primary health signals.

The implementation adds structured Kubernetes events and log reasons at the
existing controller/AAP boundaries:

| Reason | Type | Emitted when |
|---|---|---|
| NetworkManagerUnavailable | Warning | Manager registration or capability lookup fails |
| FabricOperationFailed | Warning | AAP create/update/delete job fails |
| VLANAllocationFailed | Warning | VLAN allocation cannot complete |
| DHCPLeaseUnavailable | Warning | No current lease matches the attachment |
| SecurityGroupRulesApplyFailed | Warning | SecurityGroup translation or application fails |
| FabricCleanupBlocked | Warning | Ordered deletion cannot proceed |
| FabricResourceReady | Normal | Desired fabric state and required feedback are ready |

Logs include resource UID, tenant attribution hash or ID permitted by the
existing logging policy, manager name, desired generation, job ID, and operation
result. They do not include credentials or full secret contents.

### Risks and Mitigations

#### VLAN exhaustion

Each Subnet consumes one unique VLAN ID per physical fabric, creating an
approximately 4094-ID ceiling. The installer exposes the pool range, validates
that it is non-empty, and reports exhaustion without reusing IDs. QinQ or VXLAN
are explicit architectural alternatives, not part of this milestone. [PRD: Risk 8.5]

#### Cumulus-only coverage

Cumulus is the only validated switch platform. Other NetworkRunner providers may
have different command, commit, locking, or rollback semantics. The design
documents the Cumulus support boundary and fails configuration validation for
unvalidated provider profiles. [User] [Research: NetworkRunner and Cumulus]

#### DHCP and lease-store dependency

A missing per-namespace DHCP service prevents IP status and therefore prevents
reliable inbound DNAT. The role validates the namespace DHCP configuration
before attachment, retries lease queries, and records the missing lease in
status.

#### Stateful net-node failure

A restart or failover can lose namespace, DHCP, conntrack, or NAT state. The
state file is versioned and locked; rehydration reconciles desired state. This
milestone supports one authoritative net node and does not claim multi-node
state replication or automatic failover. Recovery requires the state-file
backup and network inventory.

#### Backend parity

Differences from Netris can change tenant-observable behavior even when API
responses match. A capability-by-capability parity matrix and BMaaS reference
validation compare L2, routing, iptables rule, DHCP, DNAT, SNAT, status, and cleanup
behavior. [Locked: C2]

#### Privileged integration surface

AAP roles can alter physical switch and routing state. Role argument specs,
least-privilege inventories, idempotent operations, and Cumulus-only support
reduce blast radius. No tenant-provided shell fragments are accepted.

### Drawbacks

This approach adds a privileged network-node control plane and a persistent
fabric state file in front of ordinary Kubernetes reconciliation. It requires
the team to maintain Linux routing, DHCP, firewall, and switch automation in
addition to the OSAC controllers. The design also accepts a lower initial
platform-support breadth than a generic NetworkRunner claim and may require
manual operational recovery if a net node loses state.

Those costs are accepted because the PRD's value is an API-equivalent physical
fabric path without Netris. The dispatcher and NetworkClass abstractions keep
the backend-specific complexity behind an existing contract.

### Alternatives (Not Implemented)

#### Keep Netris as the only physical fabric manager

This has the smallest implementation cost but does not support managed-switch
deployments without Netris. It fails the feature's primary goal. [PRD: §1]

#### Run one namespace per Subnet

This makes local DHCP and VLAN operations simple, but it removes the
VirtualNetwork-level routing boundary and makes inter-Subnet policy and
cross-Subnet gateway behavior harder to manage consistently. It conflicts with
D12's VirtualNetwork-as-routing-domain model. [Locked: D12]

#### Use switch SVIs and switch DHCP relay as the primary L3 boundary

This could reduce net-node routing work, but it splits routing and policy between
the switch and the agentless backend, conflicts with the pure-L2 switch model
captured in the design inputs, and makes tenant isolation/provider portability
dependent on switch-specific L3 behavior.

#### Make centralized DHCP with relay the primary design

Central DHCP centralizes lease storage and may simplify multi-node visibility,
but every Subnet still needs a relay foothold, the 'giaddr' mapping must be
maintained, and lease acquisition depends on a central service. The per-VN
namespace server avoids those additional dependencies. Central DHCP with relay
is not supported in this milestone. [User] [Research: DHCP (RFC 2131)]

#### Use VXLAN or QinQ instead of a flat VLAN allocation

These approaches increase segmentation scale, but they require additional
underlay/overlay capabilities and are outside the IPv4 agentless VLAN milestone.
Cumulus documents them as scale alternatives. [Research: NetworkRunner and Cumulus]

#### Add an agentless-specific operator controller

A separate controller could hard-code the backend flow, but it would duplicate
manager discovery, finalizers, retries, job target tracking, and status logic.
The existing dispatcher is the intended pluggability boundary. [Codebase: osac-operator/pkg/networkmanager]

### Open Questions

#### 1. Lease artifact schema and freshness

**Owner:** osac-operator and fulfillment-service maintainers

**Question:** The BMaaS implementation currently consumes a 'leases' artifact
whose entries contain 'subnet_ref', 'interface', 'ip_address', and
'mac_address', then writes the accepted values into
'Status.NetworkAttachmentStatuses'. Should this artifact shape and its
generation/freshness validation become the shared contract for future CaaS and
VMaaS consumers, or remain BMaaS-specific until those integrations are
designed?

**Impact:** Changes the AAP role contract, operator feedback controller, stale
artifact handling, and the service-specific FR-4/FR-10 tests.

#### 2. Cumulus NetworkRunner contract

**Owner:** Connectivity & Fabric team

**Question:** Which exact inputs and lock scope comprise the supported Cumulus
create/delete task contract for VLANs and access ports?

The milestone does not claim move, update, rollback, or broader
NetworkRunner-provider behavior. Create/delete tasks must be idempotent and
must leave the switch in a known state after a failed retry.

**Impact:** Limits the role argument schema, concurrency tests, support procedures,
and documented switch compatibility.

#### 3. Service-specific attachment inputs

**Owner:** Connectivity & Fabric team with BMaaS and CaaS owners

**Question:** What canonical host, interface, MAC, and primary-attachment data
does each BMaaS, CaaS, and VMaaS integration provide to the generic attachment
and DHCP roles?

**Impact:** The BMaaS role input and MAC-to-lease mapping are defined here;
future service integrations may extend the generic contract without changing
the BMaaS identity rule.

## Test Plan

The detailed requirement-anchored testplan will be drafted after the design is
approved. The following scenarios summarize the expected coverage; they are
not a substitute for that testplan.

### Unit Tests

- Parse and validate agentless manager ConfigMap capabilities.
- Allocate and release VLAN IDs with idempotence, collision rejection, pool
  exhaustion, lock contention, and state-file recovery cases.
- Map resource UID, tenant, VirtualNetwork, Subnet, and attachment identity to
  deterministic namespace/state keys.
- Compile SecurityGroup ingress/egress rules and reject unsupported address
  families or malformed rules.
- Validate DHCP lease artifact identity, address family, Subnet reference, and
  desired-generation freshness.
- Verify DNAT/SNAT direction separation and deletion ordering.
- Verify status condition reason/message mapping for AAP and controller-owned
  allocation errors.

### Integration Tests

- Render manager ConfigMap and NetworkClass selection with Helm values.
- Reconcile VirtualNetwork, multiple Subnets, and SecurityGroup through
  envtest/fake AAP providers; verify controller-owned ExternalIP allocation and
  DNAT/SNAT consumers use the assigned status address without backend allocation
  state.
- Verify tenant and owner annotations survive the service-to-CR path.
- Exercise generic DHCP job artifact consumption and multi-NIC lease mapping.
- Exercise AAP role argument validation and idempotent create/delete for the
  Cumulus support contract.
- Verify controller restart/requeue behavior and ordered finalizer cleanup.

### E2E Tests

- Configure the Cumulus-backed agentless manager and create a VirtualNetwork,
  multiple Subnets, and SecurityGroup through the existing API.
- Verify same-Subnet L2, permitted and denied same-VN cross-Subnet traffic, and
  private-address isolation between overlapping VirtualNetworks.
- Provision a BMaaS reference attachment, obtain a DHCP address, and observe it in
  status.
- Verify permitted and denied inbound ExternalIP traffic.
- Verify permitted outbound traffic observes the NATGateway ExternalIP and denied
  traffic is blocked.
- Verify ExternalIPAttachment and Subnet/VirtualNetwork deletion order and
  non-interference with other tenants.
- Keep full CaaS/VMaaS service validation in the downstream follow-up features
  named by the PRD.

## Graduation Criteria

The target milestone is the IPv4-only agentless VLAN milestone described by the
PRD. Graduation to a broader support stage requires:

- all PRD acceptance criteria pass for the Cumulus reference environment;
- no critical tenant-isolation, DNAT/SNAT-direction, or deletion-order defects;
- BMaaS reference provisioning and DHCP status feedback pass repeatedly;
- resource failure conditions identify switch, DHCP, iptables rule, allocation, and cleanup
  failures;
- the documented Cumulus support boundary is validated in CI or a repeatable
  integration environment.

Broader switch support and higher-density QinQ/VXLAN operation require separate
validation and support criteria.

## Upgrade / Downgrade Strategy

This enhancement adds a backend implementation but no public API fields or CRD
versions. Existing Netris deployments remain selected by their existing
NetworkClass and are not migrated automatically.

The agentless state file uses a schema version. An upgrade must migrate state
additively before new reconciliation begins, preserve existing VLAN,
namespace, firewall, DNAT, and SNAT mappings, and refuse to start a destructive
migration when the state cannot be parsed. ExternalIP allocation remains
controller-owned and is not migrated through the AgentlessNet state file. There
is no in-place OSAC upgrade guarantee; deployment operators must retain a
backup of the state file and network inventory.

To disable the backend, the provider selects another NetworkClass only after
agentless-managed resources are drained or intentionally retained. Disabling a
manager does not delete tenant resources or silently release its allocations.
Downgrade requires the deployed role and state schema to understand the previous
state version; otherwise manual state export/restore is required.

## Version Skew Strategy

The operator, fulfillment-service, installer, and AAP collections must agree on:

- manager name 'agentless_net';
- capability string 'ipv4';
- implementation-strategy value;
- generic job names and input shapes;
- status/lease artifact schema;
- state-file schema version.

If the operator cannot discover the configured manager or the AAP role cannot
accept the job's inputs, the resource remains non-ready with a diagnostic
condition. It must not silently dispatch to Netris. During a rolling deployment,
old components that do not know 'agentless_net' cannot provision new resources;
existing resources remain represented by their CR/status but may require the
provider to complete the rollout before creating or modifying them.

## Support Procedures

Support personnel diagnose failures in this order:

1. Inspect the resource's status conditions and provisioning job history.
2. Confirm the NetworkClass points to a discovered IPv4-capable
   'agentless_net' ConfigMap.
3. Inspect AAP job status, 'leases' artifacts, and the agentless role logs.
4. Check the lock-protected state file for the resource UID, VLAN,
   gateway/DHCP, namespace, and owned NAT/DNAT rule mapping. Read the current
   ExternalIP status for any external address; it is not mirrored in the
   AgentlessNet state file.
5. Verify Cumulus VLAN/trunk/access-port state and the net-node namespace,
   interfaces, routes, iptables rules, and conntrack state.

To disable new use, remove or change the NetworkClass selection after draining
resources; do not delete the manager ConfigMap while resources still need
reconciliation. Existing workloads retain their applied fabric state until
explicit cleanup. Re-enabling the manager resumes reconciliation if the
state-file schema and network inventory are available.

## Infrastructure Needed

A repeatable validation environment needs:

- a Cumulus switch or equivalent validated Cumulus test target;
- one or more network-node hosts with privileged namespace/VLAN/firewall access;
- AAP inventory and job templates for the generic networking playbooks;
- IPv4 DHCP lease storage accessible to the agentless role;
- an ExternalIPPool and an external traffic endpoint for DNAT/SNAT assertions;
- existing OSAC kind/integration fixtures for service and controller tests.

No new repository is required. Test infrastructure changes should extend the
existing mono-repo and tests/e2e patterns.

---

## Provenance

Authored: revise @ design 0.9.0 - 562b610, workspace main @ 0ae795e37
Final: draft @ design 0.9.1 - f121df6, workspace main @ 0ae795e37

> Context changed between revise and draft.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.9.1","ai_workflows":"f121df6","source_repo":"0ae795e37","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","draft"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
