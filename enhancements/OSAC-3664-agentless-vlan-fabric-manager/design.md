---
title: agentless-vlan-fabric-manager
authors:
  - yonibettan@gmail.com
creation-date: 2026-09-08
last-updated: 2026-09-22
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
unique VLAN, and provisions DHCP, permit-all forwarding, BGP-backed external
reachability, whole-address DNAT, and explicit-source SNAT through Ansible
roles.
See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC currently has a Netris-backed physical fabric path. The repository also
contains agentless VLAN building blocks for CaaS-specific VLAN, router, SNAT,
DNAT, and external-access workflows, but those building blocks are not yet
registered as a unified fabric manager. They do not provide the full resource
lifecycle required by VirtualNetwork, Subnet, ExternalIPPool, ExternalIP,
ExternalIPAttachment, and NATGateway. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

The current agentless path allocates VLANs and creates a router namespace per
cluster workflow. The unified networking model requires a namespace per
VirtualNetwork, multiple VLAN-backed Subnets inside that namespace, permitted
routing between those Subnets by default, permitted external ingress and egress
through supported paths, and no private routing between different
VirtualNetworks. SecurityGroup resources and policy enforcement are deferred;
the design must not introduce policy-dependent readiness gates.
[Locked: D12] [User] [Research: VLANs and Linux network isolation]

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
  Linux routing namespaces, DHCP leases, forwarding state, and external
  translation rules.
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
- Implementing SecurityGroup resources, policy semantics, policy enforcement, or
  provider-managed default-deny readiness checks. Until the future
  SecurityGroup-like policy effort, supported routed traffic is permitted by
  default; topology still prevents private routes between VirtualNetworks.

## Proposal

The design adds the missing agentless implementation behind the existing
NetworkClass and dispatcher contracts. A provider registers an
'agentless_net' fabric-manager ConfigMap through Helm values and selects it in
the existing deployment configuration. The fulfillment-service and operator
own API validation, tenancy, CRDs, status, finalizers, dependency checks, and
ExternalIPPool capacity accounting. AgentlessNet owns provider-side pool and
ExternalIP address allocation in its locked state file, as well as
VirtualNetwork/Subnet realization, per-VirtualNetwork transit links, BGP `/32`
reachability, the permit-all forwarding baseline, BMF port binding, DNAT, and
SNAT. It publishes the allocated address through the AAP job result and the
operator exposes it as `ExternalIP.status.address`. [PRD: FR-1, FR-2]

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
   interfaces, provider-facing external interface, BGP peer/session, and
   connection data required by AAP. It also supplies a transit CIDR pool that
   does not overlap tenant Subnets. VLAN allocation is internal state from the
   configured VLAN-ID pool; DHCP is created per Linux namespace; and the state
   file is managed on the network node. These are not tenant or Enclave Wizard
   controls in this milestone. [Codebase: osac-aap/group_vars/all/agentless_net.yaml]

A missing manager registration or a NetworkClass that names an undiscovered
manager prevents dispatch and leaves the affected resource in a diagnostic
failure condition; it does not silently fall back to Netris.

#### Networking resource lifecycle

The Tenant Admin creates and deletes the tenant's Networking API resources:
VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment, and NATGateway. A
usable tenant network requires one VirtualNetwork with at least one Ready
Subnet before a machine can attach. The agentless backend creates no
SecurityGroup resources and applies no policy rules; supported routed traffic
uses the permit-all forwarding baseline until the future policy effort. Tenant
Users consume these resources through their workload workflows. [User]

1. The Tenant Admin creates a VirtualNetwork and one or more Subnets through
   the existing gRPC/REST API or CLI.
2. fulfillment-service validates object shape, tenant attribution, parent
   references, CIDR containment, and sibling CIDR overlap. It writes the
   owner-reference annotation on Subnets and materializes the corresponding CR
   with tenant metadata. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]
3. The osac-operator controller adds its finalizer, resolves the NetworkClass,
   and dispatches resources with fabric side effects through the generic AAP
   playbook. The implementation strategy selects
   `osac.templates.agentless_net`.
4. AgentlessNet reconciles the desired fabric state idempotently: one namespace
   and permit-all forwarding baseline per VirtualNetwork, and one
   VLAN/interface/gateway/DHCP binding per Subnet. Subnet reconciliation never
   binds a host access port.
5. ExternalIPPool and ExternalIP remain controller-managed allocation
   resources. ExternalIPAttachment and NATGateway dispatch their owned
   translation and ExternalIP-route operations only after controller
   preconditions are satisfied.
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
   attachments, host interface names, and Subnet references. For BMaaS, it
   resolves the authoritative NIC MAC for each selected interface from the
   BareMetalHost `osac.openshift.io/interface-macs` annotation. The logical
   interface name selects the annotation entry and remains the port-move/status
   identity; the MAC is the DHCP lease identity. [User]
   The BMaaS attachment contract permits each `subnetRef` at most once within
   one BareMetalInstance; a Subnet may still be used by many BareMetalInstances.
   Multi-NIC BareMetalInstances therefore use distinct Subnets, and duplicate
   `subnetRef` values are rejected before network handoff or DHCP discovery.
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
   template's 'query_dhcp_lease' task for each network attachment. Because each
   `subnetRef` is unique within the BareMetalInstance, the agentless task uses
   the authoritative BMaaS port MAC resolved from the
   `osac.openshift.io/interface-macs` annotation together with `subnetRef` to
   match the lease store and publishes one lease entry per requested Subnet
   through 'set_stats'. Named fabric-server workflows may use their host
   identity, but BMaaS does not use an interface name as the lease key.
5. The operator validates the artifact's job status, attachment identity,
   authoritative MAC, Subnet reference, address family, and freshness before
   writing the observed address to the resource status. For BMaaS, each entry
   must contain a `mac_address` matching the interface-macs annotation, the
   expected `subnet_ref`, and the assigned IP. The artifact must contain exactly
   one entry for each requested SubnetRef; duplicate, unexpected, missing, or
   MAC-mismatched entries fail IP discovery.
6. The bare-metal operator retrieves the completed AAP job, parses
   DHCPLeaseResult.Leases, maps each lease by authoritative MAC plus the unique
   SubnetRef, validates the IP address, and writes
   Status.NetworkAttachmentStatuses. If a lease is missing, duplicated,
   unexpected, MAC-mismatched, or invalid, IP discovery remains failed and
   reconciliation retries.
7. The osac-operator BareMetalInstance feedback controller watches the CR status
   change and calls the fulfillment-service BareMetalInstances.Signal RPC.
   fulfillment-service persists the status, after which ExternalIPAttachment
   reconciliation can read the target's primary IP and create DNAT.
8. CaaS and VMaaS attachment and IP-address workflows remain follow-up work.
   VM IP assignment and OVN bridging are not performed by this backend. [Locked: D8]

#### ExternalIP and inbound access

1. A Cloud Infrastructure Admin creates an ExternalIPPool containing IPv4
   ranges through the existing API. The fulfillment-service records the
   pool's capacity counters, and the agentless `create_external_ip_pool` AAP
   job registers the pool CIDRs in the locked AgentlessNet state file.
2. Creating the ExternalIPPool defines capacity; it does not allocate an
   address or create a traffic rule. When an ExternalIP is created, the
   fulfillment-service validates that the referenced pool is Ready and has
   capacity, then reserves one capacity slot in its API state. The agentless
   `create_external_ip` AAP job reads the pool entry from the locked state
   file, reuses an existing allocation for the ExternalIP UID when retrying,
   or selects and persists the first available IPv4 address. It publishes the
   selected address as an `external_ip_address` AAP job artifact through
   `ansible.builtin.set_stats`; the operator validates that artifact and writes
   the address to `ExternalIP.status.address`. The ExternalIP becomes ALLOCATED
   only after the AAP job succeeds and still has no data-plane route or NAT
   rule. External reachability is owned by the later ExternalIPAttachment or
   NATGateway consumer, not by the allocation alone.
   `ExternalIP` readiness means that a concrete address is allocated; it does
   not mean that inbound traffic is usable. Inbound readiness is represented by
   the separate ExternalIPAttachment resource.
3. The Tenant Admin creates an ExternalIPAttachment that references the
   allocated ExternalIP and targets a supported resource. A Tenant User may
   request this through an authorized workload workflow, but the Networking
   API resource lifecycle remains Tenant Admin-owned.
4. The controller waits until the target's primary private address is present
   and current in status. Until then, the attachment remains pending and the
   controller does not dispatch an AAP attachment job.
5. Once the target address is available, the controller dispatches the
   agentless `create_external_ip_attachment` operation. The role resolves the
   target VirtualNetwork and its persisted transit link, installs one owned
   whole-address DNAT rule from `ExternalIP.status.address` to the target
   address, and then announces the exact ExternalIP `/32` through BGP with the
   namespace-side transit address as the next hop. The route is announced only
   after the namespace, forwarding path, and DNAT rule are present. The
   VirtualNetwork permit-all baseline is reconciled by the VirtualNetwork
   lifecycle; the attachment operation does not create or update policy
   resources.
6. The attachment remains Pending or Progressing until both the parent
   ExternalIP address and the target address are current, the whole-address
   DNAT rule is present, and the BGP `/32` is observed as installed. It reaches
   Ready only after those checks and status feedback confirm the operation. If
   allocation succeeds but DNAT or route advertisement fails, the
   ExternalIPAttachment remains non-ready and the parent ExternalIP is not
   marked attached; the address remains reserved for retry or ordered cleanup.
   For a Cluster target, `targetEndpoint` selects the current API-server or
   ingress VIP, and the same all-protocol address translation is used rather
   than a port-specific rule. Once the supported external path exists, routed
   inbound traffic is permitted by the default forwarding baseline; no
   provider-managed default-deny capability is required. [PRD: FR-5] [User]

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
3. The agentless role resolves every current Subnet CIDR in the VirtualNetwork
   and its persisted transit link. It installs namespace-side `POSTROUTING`
   rules with explicit `SNAT --to-source <ExternalIP.status.address>` for
   those source CIDRs when traffic exits through the transit veth. It must not
   use `MASQUERADE` in the namespace or on the host for this path, because that
   would expose a node/interface address instead of the allocated ExternalIP.
   The role then announces the exact ExternalIP `/32` through BGP using the
   saved namespace-side transit address as next hop.
4. The independently reconciled `filter/FORWARD` permit-all baseline allows
   supported routed packets to reach the SNAT path. The NATGateway role does
   not evaluate or modify policy resources. The external endpoint observes the
   allocated ExternalIP as the source address, and established return traffic
   follows conntrack back through the namespace to the original source.
   NATGateway is Ready only after the explicit SNAT rules and BGP route are
   observed as installed. [PRD: FR-6] [Locked: D14]

NATGateway is outbound only. It does not create an inbound DNAT mapping.

The external packet paths are:

- Inbound: the upstream fabric receives the BGP advertisement for
  `<external-ip>/32` and sends the packet to the authoritative net node. The
  net-node route forwards it through the host side of the VirtualNetwork's
  transit veth to the namespace-side next hop. Namespace `PREROUTING` applies
  the attachment's whole-address DNAT to the target private address; the
  `FORWARD` baseline permits it and the Subnet interface delivers it to the
  target. The target's reply returns through its Subnet gateway, conntrack
  reverses the translation to the ExternalIP, and the namespace sends it over
  the transit link and external uplink.
- Outbound: the target sends to its Subnet gateway; the namespace routes the
  packet through the transit veth, and `POSTROUTING` changes its source to the
  NATGateway ExternalIP with explicit SNAT. The host forwards it without a
  second MASQUERADE rule. The reply arrives using the advertised ExternalIP
  `/32`, reaches the same namespace through the saved next hop, and conntrack
  reverses the SNAT to the target's private address.

The ExternalIP is not assigned as a floating address to an arbitrary host
interface. The BGP `/32`, the persisted transit next hop, and the namespace NAT
state together provide reachability and make repair/deletion deterministic.

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
2. For an ExternalIPAttachment, withdraw its ExternalIP `/32` BGP route and
   wait until the route is absent from the net-node routing/BGP state. Remove
   the whole-address DNAT rule, delete every namespace conntrack entry whose
   original or reply tuple contains that ExternalIP, and verify that the owned
   rule and conntrack state are absent before cleanup succeeds.
3. For a NATGateway, withdraw its ExternalIP `/32` BGP route and wait for
   confirmed withdrawal before removing its explicit SNAT rules. Delete every
   namespace conntrack entry whose original or reply tuple contains that
   ExternalIP and verify the route, rule, and conntrack state are absent. The
   referenced ExternalIP remains a separate resource and is not released
   implicitly.
4. For an ExternalIP, retain the fulfillment-service capacity reservation and
   deletion finalizer while an attachment or NATGateway owns a route, DNAT/SNAT
   rule, conntrack entry, provider allocation task, or UID-keyed `external_ips`
   entry. If an atomic provider-state commit never occurred, release the API
   reservation after the allocation reaches terminal failure. If a provider
   entry exists, remove it under the state-file lock and confirm that both
   external consumers and the `/32` route are absent before releasing the API
   reservation. [User]
5. For a Subnet, remove only DHCP, its VLAN subinterface, gateway IP, and
   Subnet-owned switch/VLAN state, then release the VLAN ID after confirmed
   cleanup.
6. For a VirtualNetwork, remove remaining child fabric state, external boundary,
   and namespace after children are gone. Do not release its transit `/30` or
   remove the veth pair until no ExternalIP consumer retains a route or NAT
   state for that VirtualNetwork.
7. Remove the finalizer only after the fabric manager reports the desired
   cleanup state. [PRD: FR-10] [Codebase: osac-operator/pkg/provisioning]

The Cloud Infrastructure Admin owns the provider-scoped manager and
ExternalIPPool resources. The Tenant Admin owns creation and deletion of the
tenant's VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment, and
NATGateway resources. Agentless_net never creates or deletes those API objects;
it applies and removes the fabric state during their existing reconciliation
lifecycles. This feature creates no default networking or policy resources.

### API Extensions

No new public gRPC service, REST resource, protobuf field, CRD kind, or webhook
is introduced. Existing fabric-facing resources receive the agentless backend;
fulfillment-service retains ExternalIPPool validation and capacity accounting,
the agentless AAP roles allocate provider-side pool addresses, and
ExternalIPAttachment and NATGateway use the resulting `ExternalIP.status.address`
for DNAT/SNAT. Existing status and condition fields carry observed readiness
and diagnostic failures. [Locked: D3, D5, D9]

The implementation changes the following existing surfaces:

| ID | Existing surface | Change | Requirements |
|---|---|---|---|
| IC-1 | Installer values, manager ConfigMap, NetworkClass selection | Register and select 'agentless_net' as a fabric manager with IPv4 capability | FR-1, NFR-1 |
| IC-2 | VirtualNetwork and Subnet API/CR lifecycle | Route existing fabric resources through the agentless dispatcher and realize VLAN, namespace, forwarding baseline, and cleanup state | FR-2, FR-3, FR-10, NFR-2, NFR-3 |
| IC-3 | Fabric network-attachment and DHCP feedback path | Attach BM/CaaS/VM targets through the existing generic contract and surface fabric-assigned IPs for BM/CaaS | FR-4, FR-8 |
| IC-4 | ExternalIPPool, ExternalIP, and ExternalIPAttachment lifecycle | Preserve service-owned pool capacity, allocate provider-side addresses through the locked AAP state file, install whole-address DNAT, and announce/withdraw the consumer-owned ExternalIP `/32` route | FR-5, FR-7, FR-10, NFR-2, NFR-3 |
| IC-5 | NATGateway lifecycle | Apply explicit outbound SNAT using the address in `ExternalIP.status.address`, announce/withdraw its `/32` route, and never replace it with host/interface MASQUERADE | FR-6, FR-10, NFR-2, NFR-3 |
| IC-6 | Resource status, conditions, events, and job history | Surface manager registration, provisioning, DHCP, switch, forwarding, BGP route, NAT, and cleanup failures with diagnostic reasons | FR-9, NFR-2 |

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
permit-all forwarding baseline on that namespace's `filter/FORWARD` path. The
baseline permits supported routed tenant flow and established/related return
traffic. Local DHCP traffic terminates in the namespace and is not routed
through this baseline. AgentlessNet records the mapping in the locked state
file; it does not create tenant child resources or install private routes to
another VirtualNetwork. [User]

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
does not own capacity accounting. AgentlessNet registers the pool CIDRs and
maintains concrete ExternalIP allocations in the locked state file; it does
not update the API capacity counters. Its ExternalIPAttachment and NATGateway
operations consume the current ExternalIP status address when programming
rules. Creating the pool does not allocate an address and does not create DNAT
or SNAT rules.

The status fields have disjoint owners: fulfillment-service owns
`status.total`, `status.allocated`, and `status.available`; the
ExternalIPPoolReconciler owns `status.phase`, `status.conditions`, and
provisioning-job fields. Fulfillment-service updates only its capacity fields
inside the pool-row lock. The reconciler uses a field-scoped status patch or
read-modify-write that preserves the capacity fields, retries on
`resourceVersion` conflict, and recomputes its owned fields from the latest
object. Neither writer replaces the full status with a stale snapshot. [NFR-2]

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

The fulfillment-service validates the pool and reserves capacity, but the
agentless AAP job selects the concrete address from the provider state file.
The job publishes the address as an `external_ip_address` artifact; the
operator validates the job result and publishes it in `status.address`.
Allocation alone creates no traffic rule; the address is consumed later by an
ExternalIPAttachment or a NATGateway, subject to the existing dependency and
exclusivity checks.

The preferred future architecture is for fulfillment-service/controller to
select the concrete address and pass it as an input to the backend, making the
backend a pure realization layer. That change is intentionally deferred; this
milestone follows the existing Netris provider-side allocation pattern.

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
from `ExternalIP.status.address` to that target, without a protocol or port
match, and announces the consumer-owned ExternalIP `/32` through BGP using the
VirtualNetwork transit next hop. The VirtualNetwork permit-all baseline is
maintained by the VirtualNetwork lifecycle, not by the attachment role.

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
AgentlessNet consumes the address in `ExternalIP.status.address` and installs
owned explicit-source SNAT rules and announces the consumer-owned ExternalIP
`/32`; it does not repeat those validation checks or evaluate a policy resource.
Deleting the NATGateway withdraws that route and removes its SNAT rules but
does not release the ExternalIP; ExternalIP deletion remains a separate Tenant
Admin operation.

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

No new policy fields are introduced by this design. The UI does not select the physical fabric
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
4. Subnet CIDR -> gateway address and DHCP scope in that namespace. For the
   IPv4-only milestone, the backend selects the first usable IPv4 address in
   the Subnet CIDR as `gateway_ipv4` (for example, `10.20.1.1` for
   `10.20.1.0/24`), assigns it to the Subnet VLAN interface, and advertises it
   as the DHCP default gateway. This address is backend data-plane state, not
   an ExternalIP or a separate Kubernetes object. Subnet deletion removes the
   DHCP scope and gateway address before deleting the VLAN interface and
   releasing the VLAN.
   AgentlessNet supports canonical IPv4 Subnet prefixes with a prefix length of
   at most `/30` (subject to parent containment and sibling-overlap validation).
   `/31` and `/32` are rejected before AAP or fabric provisioning because the
   L2 gateway/DHCP model requires a gateway address and at least one separate
   host address. `/30` is the smallest supported range: the first usable
   address is the gateway and the remaining usable address is available to
   DHCP. AgentlessNet does not implement Netris's separate `/31` L3VPN
   point-to-point mode, where DHCP and anycast gateway are disabled. [User]
5. VirtualNetwork namespace -> one uplink boundary used for routing and external
   NAT.
6. VirtualNetwork UID -> one provider-allocated transit `/30` used by the
   namespace-side route, host-side veth peer, and external next hop. The
   transit CIDR is deployment configuration and is disjoint from every tenant
   Subnet CIDR. The router contract requires the namespace address, host peer
   address, and namespace default gateway to be persisted; they are not
   recomputed from a display name during cleanup.

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
resource identifiers. The state file tracks data-plane resources, provider-side
pool registration, and concrete ExternalIP allocations owned by AgentlessNet;
fulfillment-service remains authoritative for API objects and capacity
counters.

##### State structure

~~~yaml
schema_version: 2
virtual_networks:
  - uid: <virtual-network-uid>
    namespace_name: <deterministic-name>
    uplink:
      namespace_interface: <namespace-veth-interface>
      host_interface: <host-veth-interface>
    transit:
      cidr: <provider-transit-cidr>
      namespace_ip: <namespace-transit-ip>/<prefix>
      host_ip: <host-transit-ip>/<prefix>
      next_hop: <namespace-transit-ip>
      gateway: <host-transit-ip>
      external_interface: <net-node-external-interface>
    external_reachability:
      mode: bgp
      route_prefix_length: 32
    default_forward_policy: permit_all
subnets:
  - uid: <subnet-uid>
    virtual_network_uid: <uid>
    vlan_id: <integer>
    gateway_ipv4: <address>
external_ip_pools:
  - uid: <external-ip-pool-uid>
    cidrs: [<ipv4-cidr>]
    ip_family: ipv4
external_ips:
  - uid: <external-ip-uid>
    pool_uid: <external-ip-pool-uid>
    address_ipv4: <address>
attachments:
  - uid: <external-ip-attachment-uid>
    external_ip_uid: <uid>
    virtual_network_uid: <virtual-network-uid>
    external_ip_address: <ipv4>
    target_address: <ipv4>
    target_endpoint: none | api | ingress
    route_prefix: <external-ip>/32
    route_next_hop: <namespace-transit-ip>
    route_protocol: bgp
    route_announced: true
    dnat:
      scope: address
      protocols: all
nat_gateways:
  - uid: <nat-gateway-uid>
    external_ip_uid: <uid>
    virtual_network_uid: <virtual-network-uid>
    external_ip_address: <ipv4>
    source_cidrs: [<subnet-cidr>]
    route_prefix: <external-ip>/32
    route_next_hop: <namespace-transit-ip>
    route_protocol: bgp
    route_announced: true
    snat:
      mode: explicit
      to_source: <external-ip>
port_bindings:
  - key: <baremetal-instance-uid>/<interface>/<subnet-uid>
    subnet_uid: <subnet-uid>
    vlan_id: <integer>
    host_name: <host-name>
    interface: <logical-interface>
~~~

The `virtual_networks.transit` entry is allocated from the provider-configured
transit pool once per VirtualNetwork. `namespace_ip` is the next hop passed to
the BGP route action; `host_ip` is the peer on the net node; `gateway` is the
default route used inside the namespace; and `external_interface` is the
provider-facing net-node interface used for egress. The
`external_reachability` mode is `bgp` for this milestone: each active
ExternalIP consumer owns one `<address>/32` announcement, and no L2/ARP
reachability alternative is claimed.

The `external_ip_pools` entries register provider-side pool CIDRs and the
`external_ips` entries record concrete addresses allocated from those pools.
The AAP roles allocate under the state-file lock and reuse an existing
ExternalIP UID entry on retry. The `attachments` and `nat_gateways` entries
identify the API resource whose route and DNAT/SNAT rules are owned by the
backend. Their saved route prefix, next hop, protocol, and address are the
inputs for idempotent repair and deletion; cleanup must not derive them from a
current name or a newly allocated transit link. `target_endpoint` records the
cluster API-versus-ingress choice, while `source_cidrs` is reconciled whenever
the VirtualNetwork's Subnet set changes.

The current `agentless_net.l3.dnat` role is single-port and TCP/UDP-specific,
and the current `agentless_net.l3.snat` role uses `MASQUERADE`; neither role is
reused unchanged for these entries. The generic AgentlessNet implementation
must extend or wrap them with an all-protocol, whole-address DNAT action and an
explicit-source SNAT action. `port_bindings` tracks the
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
| VirtualNetwork create/update/delete | Add or reconcile one `virtual_networks` entry, including its transit `/30`, veth identities, and external-reachability mode; remove it only when the VirtualNetwork object is deleted and its child entries are gone | Allocate or reuse the transit link; create or repair the namespace, uplink, default route, and permit-all baseline; remove the link during ordered cleanup |
| Subnet create/update/delete | Add or reuse one `subnets` entry; remove it and release the VLAN only when the Subnet object is deleted and dependent bindings are gone | Create or repair the switch VLAN, namespace interface, gateway, and DHCP scope; reconcile any active NATGateway `source_cidrs`; no host access-port binding during Subnet provisioning |
| ExternalIPPool create/delete | Add or reconcile one `external_ip_pools` entry; remove it only when the ExternalIPPool object is deleted | Register or remove provider-side pool CIDRs under the state-file lock; fulfillment-service remains authoritative for capacity counters |
| ExternalIP create/delete | Create one idempotent fulfillment-service capacity reservation keyed by ExternalIP UID; add or reuse one complete `external_ips` entry keyed by the same UID; remove the provider entry before releasing the API reservation | Select and persist a complete IPv4 allocation atomically under the state-file lock, publish it as the AAP result, and release provider state before API capacity during ordered cleanup |
| ExternalIPAttachment create/delete | Add, replace, or remove one `attachments` entry containing the target, whole-address DNAT, `/32` route, saved next hop, and route-announced state | Read the address from `ExternalIP.status.address` and target status, create the all-protocol DNAT rule, announce or withdraw the owned BGP `/32`, then remove the rule during ordered cleanup |
| NATGateway create/delete | Add or remove one `nat_gateways` entry containing all current source CIDRs, explicit SNAT address, `/32` route, saved next hop, and route-announced state | Read the address from `ExternalIP.status.address`, create explicit `SNAT --to-source` rules, announce or withdraw the owned BGP `/32`, then remove the rules during ordered cleanup |
| BMF attachment bind/unbind | Add or remove one `port_bindings` entry keyed by machine, interface, and Subnet | Move the Cumulus access port to or from the Subnet VLAN through the generic attachment playbook |

Every transition is applied under the state-file lock and is persisted before
the corresponding operation is reported successful. The fulfillment-service
capacity reservation and provider `external_ips` entry use the ExternalIP UID
as their idempotency key. The provider writes the complete entry atomically—an
allocation either commits the full entry or commits nothing. A retry reuses a
committed entry by UID instead of allocating a second address. A failed
allocation with no committed entry keeps the same API reservation while it is
retryable and releases it exactly once on terminal failure or deletion. [User]

For an ExternalIP consumer, the desired route and translation state is recorded
with the consumer UID before the AAP action starts. The role applies the
namespace translation first, announces the saved `/32` with the saved next hop,
and sets `route_announced: true` only after both the data-plane rule and route
are observed. A retry uses those same values. Cleanup reverses that order from
the outside in: withdraw and verify the route, remove and verify the owned NAT
rule, clear the consumer state, and only then permit ExternalIP release.

#### DHCP and lease feedback

The implementation runs one DHCP service in each VN namespace and binds it to
every Subnet VLAN interface. This gives DHCPDISCOVER broadcasts a local
interface in each L2 domain and allows one lease store to serve all Subnets in
the VN. Central DHCP with relay is not a supported deployment option for this
milestone. [Locked: D13] [User] [Research: Local DHCP presence per broadcast domain]

The agentless 'query_dhcp_lease' role accepts the generic attachment inputs:

- host identity for named fabric-server workflows;
- authoritative port MAC for BMaaS, resolved from the
  `osac.openshift.io/interface-macs` annotation; the logical interface name is
  only the annotation lookup key;
- Subnet reference;
- requested address family, fixed to IPv4 for this milestone.

It looks up a BMaaS lease by port MAC and Subnet, rejects an ambiguous, stale,
or mismatched match, and publishes a list under the AAP 'leases' artifact.
Named fabric-server workflows may use their host identity. The
operator consumes only a successful job artifact whose identity matches the
current resource generation. A missing lease causes a requeue and diagnostic
condition; it does not create a DNAT rule with an empty target. [PRD: FR-4,
FR-9] [Codebase: osac-aap/playbook_osac_query_dhcp_lease.yml]

#### Forwarding baseline

VirtualNetwork creation establishes a permit-all forwarding baseline in the
namespace's `filter/FORWARD` path. The baseline permits supported routed
traffic, including inter-Subnet traffic within the VirtualNetwork and traffic
through supported external DNAT/SNAT paths. Established and related return
traffic follows the existing connection-tracking behavior; local DHCP traffic
terminates in the namespace rather than traversing this path.

Traffic between hosts in the same Subnet is switched at Layer 2 on the access
VLAN and does not traverse the namespace's `filter/FORWARD` chain. That traffic
is intentionally permitted by FR-3; the chain cannot be described as an
attachment-scoped enforcement point for same-Subnet packets. The baseline
therefore governs routed packets only, while VLAN uniqueness and separate
VirtualNetwork namespaces provide the internal isolation boundary.

SecurityGroup resources, policy rules, and default-deny authorization are not
implemented by this milestone. There is no attachment-to-SecurityGroup state,
SecurityGroup AAP action, or SecurityGroup deletion/reconciliation contract in
this design, and no policy-dependent readiness gate is added to
VirtualNetwork, ExternalIPAttachment, or NATGateway reconciliation. A future
policy design must choose an enforcement point that observes per-attachment
traffic (for example, Cumulus access-port ACLs or an explicitly forced
bridge/routing path), define multi-group combination semantics and
create/update/detach/rule-update ordering, and make deletion fail closed while
references remain. Those semantics are intentionally outside the current state
model and AAP action contract. [PRD: FR-3, FR-5, FR-6] [User]

#### ExternalIP, DNAT, and SNAT

ExternalIPPool API objects, aggregate capacity counters, and UID-keyed capacity
reservations remain fulfillment-service state. AgentlessNet maintains
provider-side pool and concrete ExternalIP allocation entries in its locked
state file. The AAP allocation job publishes the selected address only after
the complete `external_ips` entry is atomically committed, and the operator
copies it to `ExternalIP.status.address`. ExternalIP release remains blocked
while an ExternalIPAttachment or NATGateway still owns a route or NAT mapping,
while allocation is in progress, or while the provider entry has not been
confirmed removed. The route owner retains the exact `/32` and next hop needed
for withdrawal; it is not reconstructed from the current VirtualNetwork
object.
If provider allocation fails before the atomic commit, no provider address
exists and the retry uses the existing UID reservation; terminal failure or
deletion compensates that reservation. If the provider entry is committed,
cleanup removes it before the API reservation and pool capacity are released.

ExternalIPAttachment creates one destination translation from the address in
`ExternalIP.status.address` to the target's primary private address, without a
protocol or port match. In iptables terms, the desired rule is equivalent to
`-t nat -A PREROUTING -d <external-ip> -j DNAT --to-destination <target-ip>`;
the role must not silently reduce this to the current single-port TCP/UDP
contract. For a Cluster, the controller resolves the selected API or ingress
VIP and persists that endpoint choice with the rule state. The attachment never
changes the NATGateway SNAT rule.

NATGateway creates source translations for every current Subnet CIDR in its
VirtualNetwork, using explicit `SNAT --to-source <ExternalIP.status.address>`
on the namespace transit egress. The host-side external path must not apply a
second MASQUERADE. Both consumers use the shared BGP `/32` announce/withdraw
action with their own saved next hop, but retain separate state sections, role
entrypoints, and deletion paths. [Locked: D14]

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
  ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway.
  fulfillment-service owns ExternalIPPool/API validation and
  capacity counters; the ExternalIPPool and ExternalIP roles register CIDRs,
  allocate concrete addresses in the locked state file, and publish the
  `external_ip_address` AAP result. Attachment and NAT roles consume the
  resulting `ExternalIP.status.address` when programming whole-address DNAT or
  explicit-source SNAT. The VirtualNetwork entrypoint allocates and repairs
  the per-VirtualNetwork transit `/30` and veth pair.
- Generic network attachment entrypoints for create/delete or equivalent
  attach/detach operations. The AgentlessNet implementation must add
  `osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/tasks/move_network_attachment.yaml`
  for the BMF attachment flow.
- 'query_dhcp_lease' compatible with the generic query playbook.
- Shared step roles for VLAN/IPAM, router namespace, DHCP, forwarding baseline,
  BGP `/32` announce/withdraw, whole-address DNAT, explicit-source SNAT, and
  Cumulus port configuration. The BGP action receives the saved `route_prefix`
  and `route_next_hop`; it must verify withdrawal before cleanup proceeds.
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

This milestone intentionally permits supported routed traffic after the
topology establishes a route, including external ingress through DNAT and
external egress through SNAT. That default-permit behavior is not a substitute
for SecurityGroup policy; same-Subnet traffic is likewise intentionally
permitted at Layer 2. SecurityGroup resources, attachment bindings, and policy
enforcement are deferred to a future effort. The design therefore preserves
topology isolation and existing API authorization but does not add a
default-deny readiness gate or claim an in-use SecurityGroup deletion protocol.

### Failure Handling and Recovery

| Failure | Recovery | Observable result |
|---|---|---|
| Manager ConfigMap missing or capability mismatch | Stop before AAP side effects; requeue after manager discovery changes | Resource condition identifies missing manager/capability |
| Invalid NetworkClass, unsupported IPv6 request, or Subnet prefix `/31`/`/32` | API/controller validation rejects before provisioning | Invalid argument or failed condition names the unsupported address family or prefix; no AAP job or fabric state is created |
| VLAN state lock unavailable | Retry with backoff; preserve existing allocation | Provisioning remains pending with lock diagnostic |
| VLAN allocation exhausted or already owned | Do not reuse an allocated ID; fail the requested generation | Failed condition identifies VLAN allocation exhaustion/conflict |
| ExternalIP state lock unavailable or pool has no free address | Retry without changing an existing UID allocation; do not publish an address | ExternalIP remains non-ready with an allocation diagnostic |
| ExternalIP allocation artifact is missing, stale, or mismatched | Ignore the artifact and retry the current generation; do not set `status.address` | ExternalIP remains Pending/Progressing with an allocation condition |
| ExternalIP allocation fails before atomic provider-state commit | Retry using the existing UID-keyed API reservation; if failure becomes terminal or the resource is deleted, release that reservation exactly once because no provider entry exists | ExternalIP remains non-ready during retry and reports the allocation failure; capacity is restored after compensation |
| ExternalIP deletion races allocation or provider cleanup | Serialize operations by ExternalIP UID; remove a committed provider entry before releasing API capacity, or release the reservation directly when no entry was committed | No address becomes reusable until the provider state and API reservation agree |
| Switch VLAN or access-port operation fails | Retry idempotently; leave existing applied state untouched when possible | AAP failure and resource status contain switch error |
| Transit-pool allocation or veth/router setup partially fails | Reuse the UID-keyed transit `/30` and saved interface/IP values on retry; do not announce any ExternalIP route until the namespace and default route are verified | VirtualNetwork or dependent consumer remains non-ready with a transit-link diagnostic |
| Namespace/VLAN interface creation partially fails | Reconcile desired namespace and interfaces; remove only orphaned state on delete | Resource remains non-ready with net-node error |
| DHCP lease absent or ambiguous | Requery; do not update status or create DNAT until identity/freshness checks pass | Condition identifies lease-unavailable/ambiguous |
| AAP lease artifact is stale or job failed | Ignore artifact, retain current status, retry current generation | Job failure and resource condition remain visible |
| Forwarding baseline or owned NAT rule application fails | Retry the desired generation without reporting Ready; preserve the saved route/NAT inputs | The affected resource condition and job history identify the forwarding or NAT operation failure |
| DNAT/SNAT or BGP announcement partially fails | Compare desired state with the saved owner state and repair; do not report Ready until both the exact rule and `/32` route are observed | Attachment/NAT condition identifies the translation or route failure |
| ExternalIP allocation succeeds but DNAT or route advertisement does not | Keep ExternalIP allocated, keep ExternalIPAttachment non-ready and `status.attached` false, and retry using the same address/next hop; do not release capacity | Attachment condition identifies the DNAT or external-route failure |
| External endpoint observes a node address instead of the NATGateway ExternalIP | Remove any MASQUERADE rule from this path, install explicit `SNAT --to-source`, and verify the observed source before Ready | NATGateway remains non-ready with a source-address diagnostic |
| BGP withdrawal or owned NAT cleanup fails | Retain the consumer and ExternalIP finalizers, keep capacity reserved, and retry from the persisted route/rule state; never release an address while its `/32` or translation remains | Resource remains terminating with external-cleanup condition |
| Delete is interrupted | Finalizer re-enters the ordered cleanup phases after restart | Resource remains terminating with cleanup reason |
| Net node restarts | Rehydrate transit links, `/32` route ownership, DNAT/SNAT rules, and conntrack prerequisites from the versioned state file; reconcile actual interfaces/rules before reporting Ready | Existing resource statuses remain non-ready until observed state converges |

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
| TransitLinkFailed | Warning | A per-VirtualNetwork transit `/30`, veth, or namespace route cannot be created or repaired |
| DHCPLeaseUnavailable | Warning | No current lease matches the attachment |
| ExternalRouteApplyFailed | Warning | The consumer-owned ExternalIP `/32` cannot be announced or verified with its saved next hop |
| ExternalRouteWithdrawBlocked | Warning | A route cannot be withdrawn during consumer or ExternalIP cleanup |
| NATSourceAddressMismatch | Warning | Egress validation does not observe the associated ExternalIP as the source address |
| FabricCleanupBlocked | Warning | Ordered deletion cannot proceed |
| FabricResourceReady | Normal | Desired fabric state and required feedback are ready |

Logs include resource UID, tenant attribution hash or ID permitted by the
existing logging policy, manager name, desired generation, job ID, route prefix
and next hop, interface identity, and operation result. NAT validation may log
the selected address and observed source address, but not credentials or full
secret contents.

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

A restart or failover can lose namespace, DHCP, conntrack, NAT, veth, or BGP
route state. The state file is versioned and locked; rehydration reconciles the
saved transit link, `/32` route ownership, and translation rules before
reporting a consumer Ready. This milestone supports one authoritative net node
and does not claim multi-node state replication or automatic failover. Recovery
requires the state-file backup, network inventory, and BGP peer configuration.

#### External route and source-address correctness

An announced `/32` with the wrong next hop can blackhole inbound traffic, and a
leftover MASQUERADE rule can make outbound traffic expose the node address
instead of the tenant's ExternalIP. The design allocates one transit `/30` per
VirtualNetwork, persists the namespace/host addresses and consumer-owned route
identity, applies DNAT or explicit SNAT before announcing the route, verifies
the installed route and observed source address, and withdraws the route before
removing translation state or releasing the ExternalIP.

#### Backend parity

Differences from Netris can change tenant-observable behavior even when API
responses match. A capability-by-capability parity matrix and BMaaS reference
validation compare the in-scope L2, routing, DHCP, DNAT, SNAT, status, and
cleanup behavior. SecurityGroup provisioning and policy enforcement are excluded
from this parity claim because they remain a Netris requirement but are deferred
for agentless VLAN. [Locked: C2] [PRD: FR-2, NFR-2]

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

#### Advertise ExternalIPs with L2/ARP instead of BGP

An L2 design could place each ExternalIP on a provider-facing interface and
answer ARP directly, but it would require floating-address ownership,
gratuitous-ARP/neighbour handling, and a different failover and cleanup model.
This design selects BGP `/32` announcements because the existing AgentlessNet
external-access path already has announce/withdraw primitives and the route can
identify the per-VirtualNetwork namespace through its saved transit next hop.
The provider must therefore supply a BGP session and route verification in the
agentless inventory; this milestone does not claim an L2/ARP alternative.

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

**Question:** The BMaaS implementation consumes a 'leases' artifact whose
entries require 'subnet_ref', 'interface', authoritative 'mac_address', and
'ip_address', then writes the accepted values into
'Status.NetworkAttachmentStatuses'. Should this artifact shape and its
generation/freshness validation become the shared contract for future CaaS and
VMaaS consumers, or remain BMaaS-specific until those integrations are
designed?

**Impact:** Changes the AAP role contract, operator feedback controller, stale
artifact handling, and the service-specific FR-4/FR-9 tests.

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
- Allocate one transit `/30` per VirtualNetwork and preserve its namespace/host
  addresses, next hop, and route identity across retries.
- Map resource UID, tenant, VirtualNetwork, Subnet, and attachment identity to
  deterministic namespace/state keys.
- Compile and validate the permit-all forwarding baseline without introducing
  policy-resource inputs or default-deny gates.
- Validate DHCP lease artifact identity, address family, Subnet reference, and
  desired-generation freshness.
- Verify whole-address/all-protocol DNAT, explicit `SNAT --to-source`, BGP
  announce-after-rule ordering, and route-withdraw-before-release cleanup.
- Inject an ExternalIP state-file write failure and verify that no partial
  `external_ips` entry is visible, retries reuse the same UID reservation, and
  terminal failure compensates the API reservation.
- Verify status condition reason/message mapping for AAP and controller-owned
  allocation errors.

### Integration Tests

- Render manager ConfigMap and NetworkClass selection with Helm values.
- Reconcile VirtualNetwork and multiple Subnets through envtest/fake AAP
  providers; verify provider-side ExternalIP allocation
  artifacts populate status, consumers persist the transit/route state, and
  DNAT/SNAT actions use that address.
- Exercise BGP `/32` announce/withdraw with a saved namespace-side next hop,
  whole-address DNAT for API/ingress cluster endpoints, and explicit-source
  SNAT without host-side MASQUERADE.
- Exercise ExternalIP deletion during allocation and verify UID serialization,
  provider cleanup, and delayed API capacity release.
- Verify tenant and owner annotations survive the service-to-CR path.
- Exercise generic DHCP job artifact consumption for multi-NIC instances using
  distinct Subnets, and reject duplicate SubnetRefs before lease discovery.
- Exercise AAP role argument validation and idempotent create/delete for the
  Cumulus support contract.
- Verify controller restart/requeue behavior and ordered finalizer cleanup.

### E2E Tests

- Configure the Cumulus-backed agentless manager and create a VirtualNetwork
  and multiple Subnets through the existing API.
- Verify same-Subnet L2, permitted same-VN cross-Subnet traffic, and
  private-address isolation between overlapping VirtualNetworks.
- Provision a BMaaS reference attachment, obtain a DHCP address, and observe it in
  status.
- Verify inbound ExternalIP traffic follows the BGP `/32` to the VN namespace,
  reaches the target through whole-address DNAT, and returns through conntrack.
- Verify outbound traffic is explicitly SNATed and the external endpoint
  observes the NATGateway ExternalIP as the source address.
- Verify ExternalIPAttachment and Subnet/VirtualNetwork deletion order and
  non-interference with other tenants, including route withdrawal and NAT-rule
  removal before ExternalIP reuse.
- Keep full CaaS/VMaaS service validation in the downstream follow-up features
  named by the PRD.

## Graduation Criteria

The target milestone is the IPv4-only agentless VLAN milestone described by the
PRD. Graduation to a broader support stage requires:

- all PRD acceptance criteria pass for the Cumulus reference environment;
- no critical tenant-isolation, DNAT/SNAT-direction, or deletion-order defects;
- BMaaS reference provisioning and DHCP status feedback pass repeatedly;
- inbound ExternalIP traffic follows the consumer-owned BGP `/32` to the
  intended VirtualNetwork, outbound traffic observes the NATGateway ExternalIP,
  and deletion withdraws the route before the address can be reused;
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

The agentless state file uses a schema version. The design's schema 2 adds the
per-VirtualNetwork transit link and consumer-owned external-route fields. An
upgrade must migrate state additively before new reconciliation begins,
preserve existing VLAN, namespace, transit, firewall, provider-side ExternalIP,
BGP route, DNAT, and SNAT mappings, and refuse to start a destructive migration
when the state cannot be parsed or a required route next hop is missing. There
is no in-place OSAC upgrade guarantee; deployment operators must retain a
backup of the state file, network inventory, and BGP configuration.

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
- state-file schema version;
- per-VirtualNetwork transit-link fields and the BGP `/32` route prefix/next-hop
  contract;
- whole-address DNAT inputs and explicit-source SNAT inputs. A component that
  still sends the old single-port DNAT or MASQUERADE-only SNAT arguments must
  not report the consumer Ready.

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
   gateway/DHCP, namespace, transit `/30`, veth peer addresses, provider-side
   ExternalIP allocation, saved BGP `/32` prefix/next hop, and owned NAT/DNAT
   rule mapping. Compare any ExternalIP address with
   `ExternalIP.status.address` and the AAP allocation artifact.
5. Verify Cumulus VLAN/trunk/access-port state and the net-node namespace,
   interfaces, route/BGP installation or withdrawal, exact whole-address DNAT,
   explicit `SNAT --to-source` rules, and conntrack state. Confirm that no
   host-side MASQUERADE rule can overwrite the NATGateway source address.

To disable new use, remove or change the NetworkClass selection after draining
resources; do not delete the manager ConfigMap while resources still need
reconciliation. Existing workloads retain their applied fabric state until
explicit cleanup. Re-enabling the manager resumes reconciliation if the
state-file schema and network inventory are available.

## Infrastructure Needed

A repeatable validation environment needs:

- a Cumulus switch or equivalent validated Cumulus test target;
- one or more network-node hosts with privileged namespace/VLAN/firewall access;
- a provider transit-CIDR pool, a configured BGP peer, and a way to verify
  `/32` route installation and withdrawal;
- AAP inventory and job templates for the generic networking playbooks;
- IPv4 DHCP lease storage accessible to the agentless role;
- an ExternalIPPool and an external traffic endpoint for DNAT/SNAT assertions;
- existing OSAC kind/integration fixtures for service and controller tests.

No new repository is required. Test infrastructure changes should extend the
existing mono-repo and tests/e2e patterns.

---

## Provenance

Authored: revise @ design 0.9.0 - 562b610, workspace main @ 0ae795e37
Final: respond @ design 0.11.1 - f1d6a4b, workspace main @ b9575896d (dirty)

> Context changed between revise and respond.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.1","ai_workflows":"f1d6a4b","source_repo":"b9575896d (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","revise","draft","respond","respond","respond","respond","manual-edit","respond","revise","respond","respond","respond"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
