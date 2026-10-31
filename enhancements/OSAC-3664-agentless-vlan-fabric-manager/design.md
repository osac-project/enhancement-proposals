---
title: agentless-vlan-fabric-manager
authors:
  - yonibettan@gmail.com
creation-date: 2026-09-08
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3664
  - https://redhat.atlassian.net/browse/OSAC-4307
  - https://redhat.atlassian.net/browse/OSAC-6202
  - https://redhat.atlassian.net/browse/OSAC-6693
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
unique VLAN, and provisions DHCP, permit-all forwarding, provider-managed
external route distribution, local FRR routes for ExternalIPAttachment,
NATGateway BGP routes, whole-address DNAT, and explicit-source SNAT through
Ansible roles.
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
the existing deployment configuration. The fulfillment-service owns API
validation, tenancy, durable ExternalIP allocation/consumer reservations, and
pool capacity accounting; the operator owns CRDs, finalizers, dependency
checks, and observed status. AgentlessNet owns provider-side pool and
ExternalIP address allocation in its locked state file, as well as
VirtualNetwork/Subnet realization, per-VirtualNetwork transit links, the local
ExternalIPAttachment route, NATGateway BGP `/32` reachability, the permit-all
forwarding baseline, BMF port binding, DNAT, and SNAT. For ExternalIP contract
v1, AAP returns the provider result in the same-job
`osac_result` artifact; the operator validates it against the submitted
ExternalIP and pool inputs before exposing the address as
`ExternalIP.status.address`. Managers that remain unversioned retain the legacy
annotation handoff. [Codebase: osac-operator/internal/controller/externalip_contract.go;
PRD: FR-1, FR-2]

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
   description, and fabric role. The chart entry does not yet render a
   registration that meets the network manager contract (immutable
   `osac.*` role registration, no version keys), so AgentlessNet is not
   deployable until it adopts the contract. The generic task contract has no
   per-task version keys.
3. The installer creates a ConfigMap labeled
   'osac.openshift.io/network-fabric-manager' with 'data.name=agentless_net'.
   The operator discovers it and includes the manager in NetworkClass
   capability reconciliation. All networking CR projections use the configured
   `OSAC_NETWORKING_NAMESPACE` hub namespace; tenant IDs remain annotations,
   not namespaces. [Codebase: osac-operator/charts/operator/templates/network-managers.yaml]
4. The post-install NetworkClass hook selects 'fabric_manager=agentless_net'.
   The Cloud Infrastructure Admin chooses the physical backend through
   deployment configuration, not through a new UI selector. Existing UI/API
   flows can list and select the resulting NetworkClass by name when creating
   a VirtualNetwork; they do not need to edit the deployment-only
   fabric_manager routing key. No new UI is delivered in this milestone.
   [Locked: D6, D7] [Codebase: osac-ux/libs/ui-components/src/api/v1/networking.ts]
5. The provider supplies the existing agentless inventory and credentials
   configuration. The inventory describes the Cumulus switches, network nodes,
   interfaces, provider-facing external interface, and connection data
   required by AAP. It supplies BGP peer/session configuration for NATGateway
   route distribution and a transit CIDR pool that
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

1. The bare-metal-fulfillment-operator resolves each attachment into a stable
   backend-neutral binding contract. The binding key is
   `<baremetal-instance-uid>/<interface>/<subnet-uid>`, not a display name. It
   contains the BareMetalInstance UID, BareMetalHost UID, logical interface,
   authoritative MAC from the `osac.openshift.io/interface-macs` annotation,
   Subnet UID, parent VirtualNetwork UID, server-side tenant attribution,
   operation direction, and the provider provisioning-network ID. The logical
   interface remains the status identity; the MAC is the DHCP lease identity.
   This default-permit milestone carries no policy-resource or
   SecurityGroup-association input. [User] [Codebase:
   bare-metal-fulfillment-operator/api/v1alpha1/baremetalinstance_types.go]
   The BMaaS attachment contract permits each `subnetRef` at most once within
   one BareMetalInstance; a Subnet may still be used by many BareMetalInstances.
   Multi-NIC BareMetalInstances therefore use distinct Subnets, and duplicate
   `subnetRef` values are rejected before network handoff or DHCP discovery.
2. After host provisioning, the BMF flow starts the generic
   `playbook_osac_move_network_attachment.yml` AAP job with this contract:
   `operation` (`attach` or `detach`), `binding_uid`, host/interface/MAC
   identity, `subnet_uid`, `virtual_network_uid`, tenant attribution, and
   `provisioning_network_id`. The playbook must not
   look up `netris_bm_provisioning_vnet` or reduce the binding to a V-Net name.
   Agentless resolves `subnet_uid` to the persisted tenant VLAN and resolves
   `provisioning_network_id` from provider configuration to its exact access
   VLAN. The role returns `binding_uid`, operation ID, resolved switch/port,
   tenant VLAN, provisioning VLAN, direction, and observed state.
3. For `attach`, Agentless records the desired binding before changing the
   switch. It verifies the host port identity, then performs reset-plus-set as
   one switch transaction or locked idempotent convergence: reset the access
   configuration and set the port to the resolved tenant VLAN. It reports
   success only after the switch port and `port_bindings` state agree. The BMF
   operator then reboots the host (or renews the link when the service supports
   it) and waits for the host's reboot/power condition and post-move DHCP lease.
   `NetworkHandoffComplete` is set only after port move, reboot completion, and
   OS DHCP on the tenant network; IP discovery and Ready are gated on it. A
   retry with the same binding UID and operation ID is a no-op after each phase
   is verified.
4. For `detach`, the BMF operator first powers the host off while it is still
   on the tenant network. Only after `PowerOff` is observed does the same
   contract restore the exact provider provisioning network recorded in
   `port_bindings`, not the deleted Subnet's display name. Agentless resets the
   tenant access configuration and sets the port to the saved provisioning VLAN,
   verifies the port, then marks the binding `restored` and removes it.
   `NetworkOffboardComplete` is set only after power-off and provisioning-VLAN
   restoration. If state is missing, the role may use only the stable provider
   provisioning-network ID; it must fail closed when that ID or its VLAN mapping
   is unavailable. The BMF deprovisioning finalizer waits for this
   acknowledgement before the host can leave the provisioning workflow.
5. The target obtains an IPv4 address through DHCP in the VN namespace. One
   DHCP service is bound to every Subnet VLAN interface in that namespace, so
   each Subnet's broadcast domain has a local DHCP presence. Central DHCP with
   relay is not supported in this milestone. [PRD: FR-4] [Locked: D13] [User]
   [Research: Local DHCP presence per broadcast domain]
6. The generic 'playbook_osac_query_dhcp_lease.yml' invokes the selected
   template's 'query_dhcp_lease' task for each network attachment. Because each
   `subnetRef` is unique within the BareMetalInstance, the agentless task uses
   the authoritative BMaaS port MAC resolved from the
   `osac.openshift.io/interface-macs` annotation together with `subnetRef` to
   match the lease store and publishes one lease entry per requested Subnet
   through 'set_stats'. Named fabric-server workflows may use their host
   identity, but BMaaS does not use an interface name as the lease key.
7. The operator validates the artifact's job status, attachment identity,
   authoritative MAC, Subnet reference, address family, and freshness before
   writing the observed address to the resource status. For BMaaS, each entry
   must contain a `mac_address` matching the interface-macs annotation, the
   expected `subnet_ref`, and the assigned IP. The artifact must contain exactly
   one entry for each requested SubnetRef; duplicate, unexpected, missing, or
   MAC-mismatched entries fail IP discovery.
8. The bare-metal operator retrieves the completed AAP job, parses
   DHCPLeaseResult.Leases, maps each lease by authoritative MAC plus the unique
   SubnetRef, validates the IP address, and writes
   Status.NetworkAttachmentStatuses. If a lease is missing, duplicated,
   unexpected, MAC-mismatched, or invalid, IP discovery remains failed and
   reconciliation retries.
9. The osac-operator BareMetalInstance feedback controller watches the CR status
   change and calls the fulfillment-service BareMetalInstances.Signal RPC.
   fulfillment-service persists the status, after which ExternalIPAttachment
   reconciliation can read the target's primary IP and create DNAT.
10. CaaS and VMaaS attachment and IP-address workflows can reuse the same
   direction, stable-subnet, host/interface, and provisioning-network contract;
   their service-specific identity resolution and IP-address workflows remain
   follow-up work.
   VM IP assignment and OVN bridging are not performed by this backend. [Locked: D8]

#### ExternalIP and inbound access

1. A Cloud Infrastructure Admin creates an ExternalIPPool containing IPv4
   ranges through the existing API. The fulfillment-service records the
   pool's capacity counters, and the agentless `create_external_ip_pool` AAP
   job registers the pool CIDRs in the locked AgentlessNet state file.
2. Creating the ExternalIPPool defines capacity; it does not allocate an
   address or create a traffic rule. When an ExternalIP is created, the
   fulfillment-service transaction locks the pool and creates the durable
   `external_ip_reservations` row keyed by the ExternalIP UUID. The row holds
   capacity in `HELD` state; it is not released merely because the provider job
   fails. The agentless `create_external_ip` AAP job reads the pool entry from
   the locked state file, reuses an existing allocation for the ExternalIP UID
   when retrying, or selects and persists the first available IPv4 address.
   For `externalIPContractVersion: v1`, AAP returns
   `osac_result.data.address` in the same job and does not patch the ExternalIP
   CR. The operator accepts only a successful current job whose ExternalIP UID,
   generation, operation, and submitted pool snapshot match the current
   ExternalIP and pool. It validates the address against the pool before
   recording the `COMMITTED` provider event in fulfillment-service and writing
   `ExternalIP.status.address`. Managers that remain on the unversioned
   contract retain the allocated-address and provider-result annotation
   handoff; annotation-only evidence is not accepted for v1. Allocation alone
   still has no data-plane route or NAT rule. [Codebase:
   osac-operator/internal/controller/externalip_contract.go;
   osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/tasks/_external_ip.yaml]
   `ExternalIP` readiness means that a concrete address is allocated; it does
   not mean that inbound traffic is usable. Inbound readiness is represented by
   the separate ExternalIPAttachment resource.
3. The Tenant Admin creates an ExternalIPAttachment that references the
   allocated ExternalIP and targets a supported resource. In the same
   fulfillment-service transaction that creates the child record, the service
   locks the ExternalIP reservation, verifies that no consumer is present, and
   records an Attachment consumer reservation. This sets
   `ExternalIP.status.attached=true` as an exclusivity reservation, not as a
   readiness signal. A Tenant User may request this through an authorized
   workload workflow, but the Networking API resource lifecycle remains Tenant
   Admin-owned. NATGateway creation uses the same transaction and consumer
   reservation, so an Attachment and NATGateway cannot acquire one ExternalIP
   concurrently.
4. The controller waits until the target's primary private address is present
   and current in status. Until then, the attachment remains pending and the
   controller does not dispatch an AAP attachment job.
5. Once the target address is available, the controller dispatches the
   agentless `create_external_ip_attachment` operation. The role resolves the
   target VirtualNetwork and its persisted transit link, installs one owned
   whole-address DNAT rule from `ExternalIP.status.address` to the target
   address, and installs the consumer-owned local FRR `/32` route using the
   saved namespace-side transit address as its next hop. For AgentlessNet
   contract v1, the controller supplies the ExternalIP, BareMetalInstance,
   primary Subnet, and parent VirtualNetwork identity/readiness/address
   snapshot with the attachment CR. AAP consumes this job input and saved
   provider state; it does not query Kubernetes or update OSAC CRs. It returns
   the v1 attach artifact only after its DNAT, forwarding, and local FRR route
   checks pass. The VirtualNetwork permit-all baseline is reconciled by the
   VirtualNetwork lifecycle; the attachment operation does not create or
   update policy resources.
6. The attachment remains Pending or Progressing until both the parent
   ExternalIP address and the target address are current, the whole-address
   DNAT rule and local FRR `/32` route are present, and the controller accepts
   the matching result artifact from the same AAP job. It reaches Ready only
   after those checks and status feedback confirm the operation. Upstream BGP
   peering and policy remain provider configuration outside the AAP job; the
   deployed external-client probe verifies the packet path. If allocation
   succeeds but DNAT or local-route setup fails, the
   ExternalIPAttachment remains non-ready; `status.attached` remains true
   because the consumer reservation still prevents a second user. The address
   remains reserved for retry or ordered cleanup. For a Cluster target,
   `targetEndpoint` selects the current API-server or
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
   explicit reference to an already allocated ExternalIP. The service transaction
   records the NATGateway consumer reservation under the same ExternalIP UUID
   lock used by Attachment creation.
2. The controller resolves that ExternalIP reference and verifies that the
   ExternalIP is allocated, belongs to the expected tenant scope, and is not
   already consumed by another NATGateway or ExternalIPAttachment.
3. The agentless role resolves every current Subnet CIDR in the VirtualNetwork
   and its persisted transit link. It persists that exact list as
   `nat_gateways.source_cidrs` and installs one namespace-side `POSTROUTING`
   rule with explicit `SNAT --to-source <ExternalIP.status.address>` per CIDR
   when traffic exits through the transit veth. It must not use `MASQUERADE`
   in the namespace or on the host for this path, because that would expose a
   node/interface address instead of the allocated ExternalIP. The host path
   installs a consumer-scoped NAT bypass before any generic POSTROUTING
   masquerade and scoped forwarding/return rules. The role then announces the
   exact ExternalIP `/32` through BGP using the saved namespace-side transit
   address as next hop.
4. The Subnet AAP create action realizes the VLAN, namespace interface,
   gateway, and DHCP state, then reconciles every active NATGateway in the same
   VirtualNetwork before the Subnet job succeeds. This installs and verifies
   the new source CIDR before the operator can report the Subnet `Ready`. The
   Subnet AAP delete action marks its saved Subnet state `deleting`, reconciles
   gateways using the remaining non-deleting Subnets, and verifies removal of
   the deleted CIDR's SNAT and matching conntrack state before DHCP, interface,
   or VLAN state is removed. Subnet and gateway operations use the existing
   per-VirtualNetwork state lock. A gateway deletion uses its saved identity and
   remains able to complete while Subnets are terminating. If the VirtualNetwork
   has no Subnets, the NATGateway keeps its consumer reservation and route with
   an empty source set and reports no egress sources.
5. The independently reconciled `filter/FORWARD` permit-all baseline allows
   supported routed packets to reach the SNAT path. The NATGateway role does
   not evaluate or modify policy resources. The external endpoint observes the
   allocated ExternalIP as the source address, and established return traffic
   follows conntrack back through the namespace to the original source.
   NATGateway is Ready only after explicit SNAT, host bypass/forwarding, and
   local route state is observed as installed. OSAC-6202 validates source
   translation and return traffic in the local VLAN lab through a test-only
   static peer route. Remote BGP advertisement and convergence are outside that
   local test's coverage.
   [PRD: FR-6] [Locked: D14]

##### AgentlessNet NATGateway task

AgentlessNet implements the generic Fabric `create_nat_gateway` and
`delete_nat_gateway` tasks of the [network manager contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#fabric-create_nat_gateway--delete_nat_gateway).
There is no version key and no typed output. The operator supplies the NATGateway
snapshot in `osac_job_vars.resource`, the VirtualNetwork and ExternalIP snapshots,
and `osac_job_vars.nat_gateway_context` with the current ExternalIP and
VirtualNetwork values (Kubernetes name/namespace/UID, Fulfillment UUID, tenant,
the allocated address or the canonical IPv4 CIDR, and `phase: Ready`). A manager
may ignore the context. The SNAT covers the whole VirtualNetwork CIDR, so
AgentlessNet's SQLite Subnet state does not decide the source CIDRs.

AAP reads and mutates only its provider state and Linux/FRR data plane. It does
not query the OSAC Kubernetes resources or patch their status/annotations. A
create succeeds, with no `osac_result`, only after SNAT, forwarding, and
route state are verified. A failure publishes `osac_error` with `retryable`, and
the operator retries only a `retryable: true` failure. The operator accepts a
successful create only while the NATGateway and its dependencies still match the
stored input and are Ready and allocated; otherwise the result is rejected as
final and the provider state stays until the delete task. The delete removes the
saved route, translation, forwarding, and matching conntrack state and verifies
it, from the stored input, not from live dependency readiness. [OSAC-6693]

NATGateway is outbound only. It does not create an inbound DNAT mapping.

The external packet paths are:

- Inbound: provider route policy delivers the external destination to the
  authoritative net node. Its local FRR static route for `<external-ip>/32`
  forwards through the host side of the VirtualNetwork's
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
interface. For ExternalIPAttachment, the local FRR `/32`, saved transit next
hop, and namespace DNAT state make repair/deletion deterministic. NATGateway
uses its separate provider BGP `/32` route for return traffic.

The provider underlay contract is explicit. Provider route policy must deliver
external traffic to the net node; BGP peer/session settings are provider
configuration, not tenant inputs. For ExternalIPAttachment, the AAP job
installs and verifies only the consumer-owned local FRR static route
`<external-ip>/32 via <namespace-transit-next-hop>`. Provider configuration
may distribute that local route to its peer. The job does not query the
upstream router or claim to verify remote BGP convergence. NATGateway keeps the
provider-owned BGP announce/withdraw operation. Agentless owns the local
attachment route and consumer UID; the provider owns route distribution and
the BGP peer/policy.

An ExternalIPAttachment is Ready only after its local route and namespace
translation are present and the controller accepts the matching v1 AAP result
artifact. The deployed external-client test verifies packet reachability.
Cleanup withdraws the exact local route and verifies it is absent before
removing the translation or permitting ExternalIP cleanup. A failed local
route or translation check leaves the consumer non-ready and retains its
finalizer and reservation. This attachment contract does not change NATGateway
readiness or result handling. [Codebase:
`osac-aap/collections/ansible_collections/osac/templates/plugins/module_utils/agentless_net_external_ip.py`]
[Codebase: osac-aap/collections/ansible_collections/agentless_net/l3/roles/bgp]

#### Failure and recovery workflow

For every operation, the controller records the AAP job target, attempt, and
failure message in the existing provisioning history and status condition.

- If the manager ConfigMap is absent, dispatch stops before an external side
  effect and the resource reports a configuration failure.
- If VLAN allocation or the state sidecar lock fails, the operation is retried
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
2. For an ExternalIPAttachment, withdraw its ExternalIP `/32` local FRR route
   and wait until it is absent from the net-node RIB. Remove
   the whole-address DNAT rule, delete every namespace conntrack entry whose
   original or reply tuple contains that ExternalIP, and verify that the owned
   rule and conntrack state are absent before cleanup succeeds.
3. For a NATGateway, withdraw its ExternalIP `/32` BGP route and wait for
   confirmed withdrawal before removing its explicit SNAT rules. Delete every
   namespace conntrack entry whose original or reply tuple contains that
   ExternalIP and verify the route, rule, and conntrack state are absent. The
   referenced ExternalIP remains a separate resource and is not released
   implicitly.
4. For an ExternalIP, the fulfillment-service records `release_requested` but
   does not decrement pool capacity. The ExternalIP controller retains its
   finalizer while an Attachment/NATGateway consumer reservation, provider
   allocation task, or UID-keyed `external_ips` entry exists. If no provider
   job was ever started, the operator still records a verified `NOT_COMMITTED`
   event for the UUID reservation before removing its finalizer. If the
   provider reports `NOT_COMMITTED`, the service can release a terminal failed
   or deleted allocation without an address. If the provider reports
   `CLEANUP_COMPLETE`, it must include the committed address/digest and prove
   that both external consumers, the `/32` route, DNAT/SNAT, and conntrack state
   are absent. The service then performs the single `RELEASED` capacity
   transaction; only its acknowledgement allows the operator to remove the
   finalizer. [User]
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
lifecycles. The fulfillment-service owns allocation/consumer reservation
state and pool counters; the operator owns CR finalizers and observed status;
AgentlessNet owns provider state and cleanup evidence. This feature creates no
default networking or policy resources.

### API Extensions

No new public gRPC service, REST resource, protobuf field, CRD kind, or webhook
is introduced. Existing fabric-facing resources receive the agentless backend.
The fulfillment-service adds an internal, non-tenant reservation record and a
private provider-result operation; neither is exposed through the public API or
REST surface. Agentless AAP roles allocate provider-side pool addresses. Under
ExternalIP contract v1 they return a same-job `osac_result`; the operator
validates it before writing `ExternalIP.status.address`. The legacy
`osac.openshift.io/allocated-address` and provider-result annotation handoff
remains for managers using the unversioned contract. ExternalIPAttachment and
NATGateway consume `ExternalIP.status.address` for DNAT/SNAT. Existing status
and condition fields carry observed readiness and diagnostic failures. [Locked:
D3, D5, D9; Codebase:
osac-operator/internal/controller/externalip_contract.go]

The implementation changes the following existing surfaces:

| ID | Existing surface | Change | Requirements |
|---|---|---|---|
| IC-1 | Installer values, manager ConfigMap, NetworkClass selection | Register and select 'agentless_net' as a fabric manager with IPv4 capability | FR-1, NFR-1 |
| IC-2 | VirtualNetwork and Subnet API/CR lifecycle | Route existing fabric resources through the agentless dispatcher and realize VLAN, namespace, forwarding baseline, and cleanup state | FR-2, FR-3, FR-10, NFR-2, NFR-3 |
| IC-3 | Fabric network-attachment and DHCP feedback path | Attach and detach BM/CaaS/VM targets through a backend-neutral stable binding contract, restore the provider provisioning network on offboarding, and surface fabric-assigned IPs for BM/CaaS | FR-4, FR-8 |
| IC-4 | ExternalIPPool, ExternalIP, and ExternalIPAttachment lifecycle | Persist an ExternalIP-UID reservation in fulfillment-service, allocate provider-side addresses through the locked AAP state file, transport and validate the provider result, install whole-address DNAT, and install/withdraw the saved local FRR `/32` route for ExternalIPAttachment without requiring upstream BGP convergence | FR-5, FR-7, FR-10, NFR-2, NFR-3 |
| IC-5 | NATGateway lifecycle | Apply explicit outbound SNAT using the address in `ExternalIP.status.address`, announce/withdraw its `/32` route, and never replace it with host/interface MASQUERADE | FR-6, FR-10, NFR-2, NFR-3 |
| IC-6 | Resource status, conditions, events, and job history | Surface manager registration, provisioning, DHCP, switch, forwarding, attachment local-route, NATGateway BGP-route, provider-result handshake, reservation, and cleanup failures with diagnostic reasons | FR-9, NFR-2 |

#### Existing resource and metadata constraints

- Tenant-scoped resources retain 'osac.openshift.io/tenant' and
  'osac.openshift.io/owner-reference' annotations. No backend-created
  tenant object may omit them. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]
- NetworkClass, ExternalIPPool, and manager registration remain
  provider-scoped according to the existing API and OPA policy.
- No API-level field is added for VLAN ID, Linux namespace, DHCP server, switch
  platform, or AAP job ID. Those are implementation state and status metadata,
  not tenant API inputs.

#### ExternalIP reservation and provider-result contract

The fulfillment-service stores one durable `external_ip_reservations` record
per ExternalIP UUID. The record is not a Kubernetes object and is not returned
by the tenant API. Its key fields are:

| Field | Meaning |
|---|---|
| `external_ip_id`, `pool_id` | Stable allocation identity and parent pool |
| `allocation_state` | `HELD`, `COMMITTED`, `RELEASE_REQUESTED`, or `RELEASED` |
| `provider_state` | `UNKNOWN`, `NOT_COMMITTED`, `COMMITTED`, or `CLEANUP_COMPLETE` |
| `address`, `provider_operation_id`, `provider_state_digest` | Provider evidence; address is required only for `COMMITTED` and cleanup evidence |
| `consumer_kind`, `consumer_id`, `consumer_state` | Exclusive Attachment/NATGateway reservation and `RESERVED` or `CLEANUP_PENDING` state |
| `release_requested_at`, `released_at`, `version` | Crash recovery, audit, and optimistic-locking fields |

Create locks the pool row and reservation key in one database transaction. A
new row increments `pool.status.allocated` and decrements
`pool.status.available`; a retry for the same ExternalIP UUID reuses the row
and never increments capacity twice. A release transaction locks the
reservation and pool, checks the provider and consumer gates, and changes the
row to `RELEASED` while decrementing `allocated` and incrementing `available`
exactly once. The row remains as an idempotency tombstone after release.

The private `RecordExternalIPProviderEvent` operation accepts
`external_ip_id`, `provider_operation_id`, `event`, `address`,
`provider_state_digest`, `consumer_kind`, `consumer_id`, and
`route_and_translation_absent`. Event values are `COMMITTED`,
`NOT_COMMITTED`, `CONSUMER_CLEANUP_COMPLETE`, and `CLEANUP_COMPLETE`.
`COMMITTED` is accepted only for a valid pool address and a provider entry
known to exist; `NOT_COMMITTED` is accepted only when the provider has verified
that no entry exists; `CONSUMER_CLEANUP_COMPLETE` is accepted only for the
currently reserved child; and `CLEANUP_COMPLETE` is accepted only when the
provider entry, ExternalIP route, DNAT, SNAT, and conntrack state are absent.
Replaying the same operation and digest is a no-op; a conflicting event or
digest is an aborted conflict. Only the operator calls this private operation
after validating the AAP result. [Codebase:
fulfillment-service/proto/private/osac/private/v1/external_ips_service.proto]

For unversioned ExternalIP managers, the
`osac.openshift.io/allocated-address` annotation is the legacy address
handoff. Under `externalIPContractVersion: v1`, AAP returns the allocation in
the same-job `osac_result`. The operator validates its schema, operation,
resource UID, generation, submitted job inputs, and current pool before writing
`ExternalIP.status.address`. V1 does not require or consult the allocated-
address annotation. [Codebase:
osac-operator/internal/controller/externalip_contract.go;
osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/tasks/_external_ip.yaml]

#### NetworkAPI resource CRs and implementation points

The following examples show the Kubernetes CR representation of each existing
Networking API resource handled by the agentless fabric manager. `status` is
controller-owned and is shown only to explain the important observed fields;
users submit the `spec` and do not write `status`. All networking CRs are
materialized in the single configured hub/networking namespace,
`$OSAC_NETWORKING_NAMESPACE`; the tenant annotations identify the logical
owner because Kubernetes namespace boundaries do not separate tenants here.
The examples use `tenant-a` only as an annotation value. `NetworkClass` is a
fulfillment-service API object rather than an operator CR, so its
`fabric_manager: agentless_net` selection is represented by the
`VirtualNetwork.spec.networkClass` field and the manager-registration section
above.

##### VirtualNetwork

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: VirtualNetwork
metadata:
  name: vnet-a
  namespace: $OSAC_NETWORKING_NAMESPACE
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
  namespace: $OSAC_NETWORKING_NAMESPACE
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
  namespace: $OSAC_NETWORKING_NAMESPACE
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
  namespace: $OSAC_NETWORKING_NAMESPACE
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
`status.state` reports allocation, and `status.attached` reports whether either
an ExternalIPAttachment or a NATGateway holds the exclusive consumer
reservation. It does not mean that the child data-plane operation is Ready.
The fulfillment-service owns `status.attached`; the operator owns
`status.address`, `status.state`, `status.phase`, `status.conditions`, and
provisioning fields. Each writer uses a field-scoped merge or read-modify-write
with conflict retries and never replaces a stale full status.

The fulfillment-service validates the pool and owns the durable capacity
reservation, but the agentless AAP job selects the concrete address from the
provider state file. For ExternalIP contract v1, the role commits provider
state and returns `osac_result.data.address` without patching the ExternalIP
CR. The operator validates that result against the successful job's submitted
ExternalIP and pool inputs, records the private provider event, and publishes
the address in `ExternalIP.status.address` only after the service acknowledges
`COMMITTED`. Only managers using the unversioned contract retain the
allocated-address/provider-result annotation handoff. Allocation alone
creates no traffic rule; the address is consumed later by an
ExternalIPAttachment or a NATGateway, subject to the durable consumer
reservation.

Provider-side address selection remains in AgentlessNet for this milestone.
The fulfillment-service does not advertise capacity as available until its
reservation reaches `RELEASED`, regardless of whether the provider selected the
address or only reported `NOT_COMMITTED`.

##### ExternalIPAttachment

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ExternalIPAttachment
metadata:
  name: public-ip-1-to-bm-1
  namespace: $OSAC_NETWORKING_NAMESPACE
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
than becoming a new ExternalIPAttachment API field. The parent ExternalIP
consumer reservation remains held through `DELETING` until the attachment
controller reports route, DNAT, and conntrack cleanup to fulfillment-service.

The ExternalIPAttachment controller waits for the target's primary IPv4 address
from the existing DHCP lease/status feedback path. If the address is missing
or stale, it keeps the attachment pending and does not dispatch the AAP job.
Once the target address is current, AgentlessNet creates an owned DNAT rule
from `ExternalIP.status.address` to that target, without a protocol or port
match, and installs and verifies the consumer-owned local FRR static route
`<ExternalIP>/32 via <saved VirtualNetwork transit next hop>`. The attachment
job verifies the local FRR RIB and does not query upstream BGP convergence;
route distribution beyond that local route is provider configuration. The
VirtualNetwork permit-all baseline is maintained by the VirtualNetwork
lifecycle, not by the attachment role. [Codebase:
osac-aap/collections/ansible_collections/osac/templates/plugins/module_utils/agentless_net_external_ip.py]

##### NATGateway

~~~yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NATGateway
metadata:
  name: vnet-a-egress
  namespace: $OSAC_NETWORKING_NAMESPACE
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
does not release the ExternalIP or clear its consumer reservation until cleanup
evidence is acknowledged by fulfillment-service; ExternalIP deletion remains a
separate Tenant Admin operation.

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

#### Net-node SQLite state and API action mapping

The agentless net node stores provider state in SQLite with
`PRAGMA user_version=1`. The logical collections below map to SQLite tables;
they are not a serialized JSON document. Each resource row is keyed by stable
Kubernetes and Fulfillment identifiers. The database tracks data-plane
resources, provider-side pool registration, and concrete ExternalIP allocations
owned by AgentlessNet; fulfillment-service remains authoritative for API objects
and capacity counters. Schema changes are made directly in the canonical v1
schema; `PRAGMA user_version` remains 1. The application recognizes only the
known prior v1 table layouts and adds missing consumer tables transactionally
after validating the existing tables. It has no downgrade path and rejects
unknown or malformed layouts without changing them.

##### State structure

~~~yaml
# Logical row fields; the on-disk representation is SQLite schema v1.
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
    dhcp:
      daemon: dnsmasq
      service_unit: agentless-dhcp@<virtual-network-uid>.service
      config_path: /etc/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.conf
      lease_path: /var/lib/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.leases
      lease_duration_seconds: <integer>
    default_forward_policy: permit_all
subnets:
  - uid: <subnet-uid>
    virtual_network_uid: <uid>
    vlan_id: <integer>
    vlan_interface: <namespace-vlan-interface>
    gateway_ipv4: <address>
    dhcp_range_start: <address>
    dhcp_range_end: <address>
    dhcp_reserved_addresses: [<address>]
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
    fulfillment_id: <external-ip-attachment-uuid>
    tenant_id: <tenant-id>
    external_ip_uid: <external-ip-kubernetes-uid>
    virtual_network_uid: <virtual-network-uid>
    subnet_uid: <subnet-uid>
    external_address: <ipv4>
    phase: provisioning | ready | deleting
    context: <validated ExternalIP, target, Subnet, VirtualNetwork snapshot>
    provider:
      namespace_name: <VirtualNetwork namespace>
      namespace_interface: <namespace veth>
      host_interface: <host veth>
      external_interface: <provider uplink>
      next_hop: <saved namespace transit address>
nat_gateways:
  - uid: <nat-gateway-uid>
    fulfillment_id: <nat-gateway-fulfillment-uuid>
    tenant_id: <tenant-id>
    external_ip_uid: <uid>
    virtual_network_uid: <virtual-network-uid>
    external_address: <ipv4>
    phase: provisioning | ready | deleting
    context: <validated ExternalIP and VirtualNetwork snapshot>
    provider:
      namespace_name: <VirtualNetwork namespace>
      namespace_interface: <namespace veth>
      host_interface: <host veth>
      external_interface: <provider uplink>
      next_hop: <saved namespace transit address>
    source_cidrs: [{subnet_uid: <uid>, cidr: <ipv4-cidr>}]
    source_revision: <sha256 of sorted Subnet UID/CIDR pairs>
    applied_source_cidrs: [{subnet_uid: <uid>, cidr: <ipv4-cidr>}]
    applied_revision: <verified-source-revision>
    cleanup_source_cidrs: [{subnet_uid: <uid>, cidr: <ipv4-cidr>}]
    route_prefix: <derived external_address>/32
    route_next_hop: <derived provider.next_hop>
port_bindings:
  - binding_uid: <baremetal-instance-uid>/<interface>/<subnet-uid>
    baremetal_instance_uid: <baremetal-instance-uid>
    host_uid: <baremetal-host-uid>
    subnet_uid: <subnet-uid>
    virtual_network_uid: <virtual-network-uid>
    tenant: <server-attributed-tenant>
    interface: <logical-interface>
    mac_address: <authoritative-mac>
    switch: <switch-identity>
    switch_port: <switch-port-identity>
    tenant_vlan_id: <integer>
    provisioning_network_id: <provider-stable-id>
    provisioning_vlan_id: <integer>
    direction: attach | detach
    state: desired | attached | restoring | restored
    handoff_phase: port_moved | rebooting | dhcp_pending | attached | poweroff_pending | restoring | restored
    operation_id: <idempotency-key>
~~~

The `attachments` row stores its validated context and provider interfaces,
including the saved next hop. Its local FRR route is derived from
`external_address` and `provider.next_hop`; the entry has no BGP
`route_announced` state. AAP installs/removes the static route and verifies it
in the local FRR RIB. The `virtual_networks.transit` row is allocated from
the provider-configured transit pool once per VirtualNetwork. `namespace_ip`
is the next hop for the local attachment route and the NATGateway BGP action;
`host_ip` is the peer on the net node; `gateway` is the default route used
inside the namespace; and `external_interface` is the provider-facing net-node
interface used for egress. NATGateway retains the provider-configured BGP
`/32` behavior. The attachment job does not verify upstream route convergence.

The fulfillment-service `external_ip_reservations` record is separate from
this provider database. The service row owns API capacity, allocation and
consumer reservation state; the `external_ips` provider entry owns only the
concrete provider allocation. The two records are correlated by ExternalIP
UUID, address, provider operation ID, and state digest. A provider event is not
treated as capacity release until the service transaction accepts it.

The `external_ip_pools` rows register provider-side pool CIDRs and the
`external_ips` rows record concrete addresses allocated from those pools.
The AAP roles allocate under the SQLite transaction lock and reuse an existing
ExternalIP UID entry on retry. The `attachments` and `nat_gateways` entries
identify the API resource whose route and DNAT/SNAT rules are owned by the
backend. Their saved route prefix, next hop, protocol, and address are the
inputs for idempotent repair and deletion; cleanup must not derive them from a
current name or a newly allocated transit link. `target_endpoint` records the
cluster API-versus-ingress choice, while `source_cidrs` is reconciled by the
Subnet AAP create/delete actions whenever the VirtualNetwork's Subnet set
changes. `source_cidrs_revision` records the verified Subnet UID/CIDR snapshot
covered by the SNAT rules. Pending desired inputs and the union of possibly
installed CIDRs remain saved until provider operations are verified, so an
interrupted retry can remove stale rules without forgetting them.
`port_bindings` records both sides of the access-port transition: the resolved
tenant VLAN and the stable provider
provisioning-network/VLAN used for detach. Its `binding_uid`, host UID, MAC,
interface, switch port, direction, and operation ID are the idempotency and
cleanup inputs; a host display name or Netris V-Net name is not sufficient.

The current `agentless_net.l3.dnat` role is single-port and TCP/UDP-specific,
and the current `agentless_net.l3.snat` role uses `MASQUERADE`; neither role is
reused unchanged for these entries. The generic AgentlessNet implementation
must extend or wrap them with an all-protocol, whole-address DNAT action and an
explicit-source SNAT action. `port_bindings` tracks the BMF-to-Subnet binding
through both attach and detach because the current milestone invokes the
generic attachment playbook directly; a future SubnetAttachment CRD could
replace this integration boundary. The existing low-level IPAM
`public_ips` map is not retained in the unified backend state. The exact
serialized names may follow the current collection conventions, but the state
must be keyed by stable OSAC resource identifiers rather than arbitrary
cluster-purpose strings. SQLite transactions and the existing per-resource
locks make state transitions durable and idempotent. This work adds the
`nat_gateways` table to the canonical schema v1 without bumping
`PRAGMA user_version`. The schema opener recognizes two exact prior v1
layouts: the original layout without consumer tables, and the attachment
layout without `nat_gateways`. Under the sidecar lock and a SQLite transaction,
it validates existing tables, adds only missing consumer tables with their
indexes and foreign keys, and verifies the resulting canonical schema. Read-only
actions encountering one of those exact layouts perform the same additive
migration under the write lock before continuing. An unknown table set,
malformed table, corrupt database, or unexpected `user_version` fails closed
without mutation. There is no JSON backup or downgrade path. The write protocol
is:

1. Acquire the per-VirtualNetwork lock for provider operations and the sidecar
   database lock for SQLite access. Validate file ownership/mode, the expected
   `PRAGMA user_version=1`, table definitions, indexes, and foreign keys.
2. Use `BEGIN IMMEDIATE` to reserve or update the UID-owned row and persist
   pending desired inputs before issuing external commands. Do not hold a
   database transaction open while waiting for a provider command.
3. Reconcile and verify the provider state. In a new transaction, compare the
   current row with the saved pending operation and commit the applied
   revision or cleanup result.
4. A process failure rolls back an incomplete SQLite transaction. A completed
   pending row remains available for idempotent provider reconciliation after
   restart. Only the two known earlier v1 layouts are migrated. Invalid or
   noncanonical databases fail closed; the application does not downgrade or
   restore them from a JSON backup.

The existing low-level IPAM allocation tasks do not participate in this
SQLite database. [Codebase:
`osac-aap/collections/ansible_collections/osac/templates/plugins/module_utils/agentless_net_state.py`]

##### API action state transitions

| API action | State transition | AgentlessNet data-plane operation |
|---|---|---|
| VirtualNetwork create/update/delete | Add or reconcile one `virtual_networks` entry, including its transit `/30`, veth identities, and external-reachability mode; remove it only when the VirtualNetwork object is deleted and its child entries are gone | Allocate or reuse the transit link; create or repair the namespace, uplink, default route, and permit-all baseline; remove the link during ordered cleanup |
| Subnet create/update/delete | Add or reuse one `subnets` row with VLAN interface, gateway, DHCP range, exclusions, and state generation; remove it and release the VLAN only when the Subnet object is deleted and dependent bindings are gone | Create or repair the switch VLAN, namespace interface, gateway, dnsmasq range, and lease mapping; before the create job succeeds, reconcile active NATGateway rules for the new non-deleting Subnet set; on delete, exclude the Subnet and verify its SNAT/conntrack cleanup before releasing DHCP, interface, or VLAN state |
| ExternalIPPool create/delete | Add or reconcile one `external_ip_pools` entry; remove it only when the ExternalIPPool object is deleted | Register or remove provider-side pool CIDRs under the state-file lock; fulfillment-service remains authoritative for capacity counters |
| ExternalIP create/delete | Create or reuse one fulfillment-service reservation keyed by ExternalIP UUID; add or reuse one complete `external_ips` provider entry keyed by the same UUID; accept provider and consumer cleanup events; release capacity only in the service's idempotent `RELEASED` transaction | Select and persist a complete IPv4 allocation atomically under the state-file lock; for v1, return `osac_result.data.address` without patching the CR; keep the annotation handoff only for unversioned managers; remove provider state before the service acknowledges capacity release |
| ExternalIPAttachment create/delete | Atomically reserve the ExternalIP consumer in fulfillment-service; add, replace, or remove one `attachments` entry containing validated context and saved provider identity/next hop; retain the reservation through cleanup | Read the address from `ExternalIP.status.address` and target status, create the all-protocol DNAT rule, install/verify or withdraw/verify the saved local FRR `/32`, then report consumer cleanup to the service |
| NATGateway create/delete | Atomically reserve the ExternalIP consumer in fulfillment-service; add or remove one `nat_gateways` row containing provider identity, the VirtualNetwork CIDR, explicit SNAT address, `/32` route, saved next hop, and pending cleanup state; retain the reservation through verified cleanup | Consume the controller-supplied `nat_gateway_context`; create explicit `SNAT --to-source` rules, scoped host forwarding and NAT bypass, then announce/verify or withdraw/verify the owned BGP `/32`; no typed output |
| BMF attachment bind/unbind | Add or reconcile one `port_bindings` entry keyed by binding UID, host/interface/MAC, Subnet, tenant VLAN, and provisioning-network identity | For attach, reset-plus-set the access port to the resolved Subnet VLAN; for detach, reset-plus-set it back to the saved provisioning VLAN and remove state only after verification |

Every provider transition is serialized with the per-VirtualNetwork lock and
persisted through SQLite transactions before the operation is reported
successful. The
fulfillment-service reservation and provider `external_ips` entry use the
ExternalIP UUID as their idempotency key. The provider writes the complete
entry atomically—an allocation either commits the full entry or commits
nothing. A retry reuses a committed entry by UID instead of allocating a second
address. A failed allocation with no committed entry keeps the same service
reservation while retryable; terminal failure or deletion requires a validated
`NOT_COMMITTED` event before the service can release it. [User]

For an ExternalIPAttachment, the controller persists the consumer reservation
and AAP saves the attachment context and provider next hop before changing the
data plane. The role applies forwarding and DNAT, then installs and verifies
the local FRR `/32` route in the net-node RIB. It does not announce the route
through a job-managed BGP action or wait for an upstream peer. Cleanup withdraws
and verifies that saved local route before removing the owned DNAT/forwarding
rules and conntrack state, then reports `CONSUMER_CLEANUP_COMPLETE` to
fulfillment-service. NATGateway keeps its separate BGP announce/withdraw flow
around explicit SNAT. The service clears `status.attached` after consumer
cleanup; provider `CLEANUP_COMPLETE` then permits allocation capacity release.

#### DHCP and lease feedback

The implementation uses `dnsmasq` as one supervised DHCP daemon per
VirtualNetwork Linux namespace. The AgentlessNet role renders
`/etc/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.conf`, stores leases in
`/var/lib/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.leases`, and runs the
daemon through `agentless-dhcp@<virtual-network-uid>.service` with automatic
restart. The service starts only after the namespace and all declared VLAN
interfaces exist; Subnet changes render a complete configuration and reload or
restart the same daemon while preserving the lease file. Central DHCP with
relay is not a supported deployment option for this milestone. [Locked: D13]
[User] [Research: Local DHCP presence per broadcast domain]

Each Subnet entry supplies one DHCP range bound to its VLAN interface. The
range excludes the network and broadcast addresses, the first usable gateway
address stored as `gateway_ipv4`, and any provider-reserved addresses. The
daemon advertises that gateway as DHCP option 3 and uses the configured lease
duration. A `/30` therefore leaves only its non-gateway usable address for
DHCP; `/31` and `/32` remain rejected because this gateway/DHCP model cannot
provide the required separate host address.

The lease database is the dnsmasq lease-file format at the path above. The
`query_dhcp_lease` role reads it after validating the current state generation,
filters for an unexpired authoritative MAC, and confirms that the leased IP is
inside the requested Subnet CIDR and not reserved. It rejects zero, duplicate,
expired, MAC-mismatched, or cross-Subnet matches. A daemon restart reloads the
same lease file; a missing or malformed lease file causes a diagnostic and
requeue rather than assigning a replacement address. The operator publishes a
lease artifact containing the attachment identity, MAC, SubnetRef, IP, and
state generation. [Codebase: osac-aap/playbook_osac_query_dhcp_lease.yml]

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
therefore governs routed packets only, while VLAN uniqueness and separate Linux
VirtualNetwork routing namespaces provide the internal isolation boundary.

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

ExternalIPPool API objects, aggregate capacity counters, and the durable
ExternalIP-UID reservation remain fulfillment-service state. AgentlessNet
maintains provider-side pool and concrete ExternalIP allocation entries in its
locked state file. For ExternalIP contract v1, the AAP allocation role commits
the complete `external_ips` entry and returns `osac_result.data.address`
without patching the ExternalIP CR. The operator validates the successful
job result against the submitted ExternalIP and pool snapshots, then records
`COMMITTED` in fulfillment-service and copies the address to
`ExternalIP.status.address`. Only unversioned managers retain the legacy
allocated-address annotation handoff.

The reservation state machine is:

| State | Entry condition | Capacity rule |
|---|---|---|
| `HELD` | API create transaction reserved one pool slot | Counted as allocated; retryable provider work may reuse it |
| `COMMITTED` | Provider entry and address were acknowledged by the service | Remains allocated; consumer may be reserved separately |
| `RELEASE_REQUESTED` | Delete or terminal failure requested release | Remains allocated until provider and consumer gates pass |
| `RELEASED` | Service transaction accepted `NOT_COMMITTED` or `CLEANUP_COMPLETE` | Capacity returned exactly once; later duplicate events are no-ops |

`NOT_COMMITTED` is authoritative only when the provider inspected its UID-keyed
state and found no entry. A failed AAP job without that result cannot release
capacity; the operator retries an inspect/compensation action. For a committed
entry, ExternalIPAttachment and NATGateway must first report consumer cleanup.
Attachment cleanup removes and verifies its saved local FRR route, DNAT,
forwarding rules, and conntrack state. NATGateway cleanup withdraws its BGP
route and removes its SNAT and conntrack state. The provider then removes the
`external_ips` entry and reports `CLEANUP_COMPLETE`. The fulfillment-service
locks the reservation and pool and performs the one-time capacity release. No
controller, AAP role, or stale status update may decrement pool capacity
directly.

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
second MASQUERADE. NATGateway uses the BGP `/32` announce/withdraw action with
its saved next hop. ExternalIPAttachment instead installs and withdraws its
saved local FRR static route. They retain separate state sections, role
entrypoints, and deletion paths. [Locked: D14; Codebase:
osac-aap/collections/ansible_collections/osac/templates/plugins/module_utils/agentless_net_external_ip.py]

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
  capacity and consumer reservations; the ExternalIPPool and ExternalIP roles
  register CIDRs and allocate concrete addresses in the locked state file.
  ExternalIP v1 returns a same-job artifact and does not patch the CR; the
  legacy allocated-address annotation handoff is limited to unversioned
  managers. Attachment and NAT roles consume `ExternalIP.status.address` when
  programming whole-address DNAT or explicit-source SNAT. The VirtualNetwork entrypoint
  allocates and repairs the per-VirtualNetwork transit `/30` and veth pair.
- Generic network attachment entrypoints for create/delete or equivalent
  attach/detach operations. The generic playbook passes a stable binding UID,
  host UID, interface, authoritative MAC, Subnet/VN UID, tenant attribution,
  direction, and provider provisioning-network ID. The AgentlessNet implementation must add
  `osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/tasks/move_network_attachment.yaml`
  for the BMF attachment flow. The role returns the resolved tenant and
  provisioning VLANs, switch port, operation ID, and observed binding state.
- 'query_dhcp_lease' compatible with the generic query playbook.
- Shared step roles for VLAN/IPAM, router namespace, dnsmasq DHCP service and
  lease-store management, forwarding baseline, local FRR `/32` route handling
  for ExternalIPAttachment, BGP `/32` announce/withdraw for NATGateway,
  whole-address DNAT, explicit-source SNAT, and Cumulus port configuration.
  The NATGateway BGP action receives the saved `route_prefix` and
  `route_next_hop`; it must verify withdrawal before cleanup proceeds. All
  state-changing roles use the shared sidecar-lock/temp-file/rename transaction
  and do not call the old in-place IPAM writer.
- Role argument validation and idempotent create/delete behavior.

The generic attachment playbook must not derive a detach target from the
current Subnet name or a Netris variable. It passes the stable provisioning
network ID on both directions, and AgentlessNet resolves that ID to a VLAN from
provider configuration before performing reset-plus-set and verification.

The ExternalIP operator must validate the v1 `osac_result` against the current
successful job and submitted pool input before treating AAP success as a
successful reconciliation. The legacy allocated-address annotation is
consumed only for unversioned managers. The shared provisioning lifecycle
therefore needs a pre-success validation callback (or equivalent
ExternalIP-specific gate) that runs before recording the successful config
version. A malformed or missing result remains retryable; it must not be
converted into `ALLOCATED` with an empty address.

The existing 'agentless_net.steps' collection remains reusable where its
inputs and lifecycle match the unified resource contract. Cluster-specific
static NMStateConfig and BGP endpoint code is not treated as the generic
Networking API implementation. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

#### Fulfillment-service coordination

In addition to the multi-Subnet validation and tenant metadata work, the
fulfillment-service adds a migration and DAO for
`external_ip_reservations`. ExternalIP create locks the pool and reservation
key, inserts or reuses the `HELD` row, and updates pool counters in one
transaction. ExternalIP delete accepts `PENDING`, `FAILED`, `ALLOCATED`, and
`DELETING` reservations, records `release_requested`, and does not change
capacity until the provider-result handshake succeeds.

ExternalIPAttachment and NATGateway create operations use the same reservation
row lock to claim the single consumer slot. Their delete operations mark the
consumer `CLEANUP_PENDING`; the operator sends a private
`CONSUMER_CLEANUP_COMPLETE` event only after route, DNAT/SNAT, and conntrack
cleanup is observed. The service then clears `status.attached` and the consumer
slot with a field-scoped update. A second consumer receives
`FailedPrecondition` while the slot is reserved, including during cleanup.

The private provider-event operation is idempotent by ExternalIP UUID,
provider-operation ID, and state digest. It performs compare-and-set
transitions under the reservation and pool locks and returns an explicit
acknowledgement or conflict. The service, not the operator or AAP role, is the
only component that changes pool `allocated`/`available` counters. These are
fulfillment-service implementation changes even though no tenant-facing proto
or REST field is added. The current Subnet server still checks CIDR subset and
sibling overlap and retains its multiple-Subnet tests. [Codebase:
fulfillment-service/internal/servers/private_subnets_server.go]

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
API access. The operator processes all networking CRs in the configured hub
namespace and relies on the server-set tenant/owner annotations plus stable
UUIDs for attribution; co-location is not treated as tenant isolation.
[Codebase: fulfillment-service/internal/auth]

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
| Networking CR lookup uses a tenant namespace, name-only selector, or mismatched tenant/owner attribution | Stop before mutation; reselect `$OSAC_NETWORKING_NAMESPACE` and retry by stable UUID with server-set attribution | Resource condition identifies namespace/attribution mismatch |
| Invalid NetworkClass, unsupported IPv6 request, or Subnet prefix `/31`/`/32` | API/controller validation rejects before provisioning | Invalid argument or failed condition names the unsupported address family or prefix; no AAP job or fabric state is created |
| VLAN state sidecar lock unavailable | Retry with backoff; preserve existing allocation and do not use the data-file inode as a lock | Provisioning remains pending with lock diagnostic |
| SQLite schema is corrupt, noncanonical, has an unknown table layout, or an unexpected `user_version` | Fail closed; do not allocate, release, change routes, or report a successful AAP result. Keep schema version 1 and require operator-led repair of the database | Resource condition identifies `StateCorrupt`; only the two documented earlier v1 layouts receive additive table migration, and no unknown layout is overwritten |
| Net node is unreachable or state/dnsmasq validation fails | Block fabric mutations, provider commits, cleanup releases, and finalizer removal; requeue after local health recovers | `NetNodeUnavailable` condition is visible; existing resources remain degraded |
| Net-node restore cannot rehydrate namespaces, DHCP, local attachment routes, or translations | Keep mutations and releases blocked; have the operator restore a verified SQLite backup or surface the exact failed phase | `NetNodeRestoreFailed` condition identifies the phase; attachments remain non-ready and NATGateway route changes are not reported successful |
| VLAN allocation exhausted or already owned | Do not reuse an allocated ID; fail the requested generation | Failed condition identifies VLAN allocation exhaustion/conflict |
| ExternalIP state sidecar lock unavailable or pool has no free address | Retry without changing an existing `HELD` reservation; do not publish an address or bypass the shared lock | ExternalIP remains non-ready with an allocation diagnostic and capacity remains held once |
| ExternalIP v1 result artifact is missing, stale, malformed, mismatched, or out of pool; or an unversioned annotation handoff is invalid | Reject the result before `ALLOCATED`; retain the same reservation and retry the current generation; do not record a successful config version | ExternalIP remains Pending/Progressing with a provider-result condition |
| ExternalIP allocation fails before atomic provider-state commit | Require a provider `NOT_COMMITTED` result or an inspect job before compensation; retain capacity while retryable and release it exactly once only after terminal failure/deletion | ExternalIP remains non-ready during retry; capacity is restored only after authoritative compensation |
| ExternalIP deletion races allocation or provider cleanup | Serialize by ExternalIP UUID; keep `release_requested` and the finalizer until `NOT_COMMITTED` or `CLEANUP_COMPLETE` is acknowledged by fulfillment-service | No address becomes reusable until provider state, consumer state, and API reservation agree |
| Switch VLAN or access-port operation fails | Retry the same binding UID with the saved host/MAC, switch port, tenant VLAN, and provisioning VLAN; do not release or forget the binding on partial failure | AAP failure and resource status contain switch error; the port remains in the last verified state |
| BMaaS reboot, power-off, or post-move DHCP gate fails | Keep the binding phase and BMF finalizer, retry the host lifecycle operation, and do not start or complete IP discovery until the matching handoff condition is true | `NetworkHandoffComplete` or `NetworkOffboardComplete` remains false with a diagnostic condition |
| BMaaS detach cannot resolve the provisioning network | Fail closed and retain the binding/finalizer; do not leave the host on a tenant VLAN or guess from a display name | Resource remains terminating with provisioning-network diagnostic |
| Transit-pool allocation or veth/router setup partially fails | Reuse the UID-keyed transit `/30` and saved interface/IP values on retry; do not install an attachment local route or announce a NATGateway BGP route until the namespace and default route are verified | VirtualNetwork or dependent consumer remains non-ready with a transit-link diagnostic |
| Namespace/VLAN interface creation partially fails | Reconcile desired namespace and interfaces; remove only orphaned state on delete | Resource remains non-ready with net-node error |
| NATGateway source CIDR set is stale during Subnet add/delete | Reconcile gateway rules from the Subnet AAP create/delete action under the per-VirtualNetwork lock; persist the new `source_cidrs_revision` only after verification, and block Subnet job success/release until complete | Subnet remains non-ready or terminating while its required SNAT rule is missing or stale; AAP job diagnostics identify the failing rule revision |
| dnsmasq configuration, service, or lease file is missing/malformed | Re-render the complete per-VN configuration, preserve a valid lease file, restart the supervised daemon, and requeue; never invent a lease | DHCP condition identifies daemon/config/lease failure and IP discovery remains pending |
| DHCP lease absent or ambiguous | Requery; do not update status or create DNAT until identity/freshness checks pass | Condition identifies lease-unavailable/ambiguous |
| AAP lease artifact is stale or job failed | Ignore artifact, retain current status, retry current generation | Job failure and resource condition remain visible |
| Forwarding baseline or owned NAT rule application fails | Retry the desired generation without reporting Ready; preserve the saved route/NAT inputs | The affected resource condition and job history identify the forwarding or NAT operation failure |
| DNAT/SNAT or local FRR route setup partially fails | Compare desired state with the saved owner state and repair; do not report Ready until the exact translation and local `/32` route are observed | Attachment/NAT condition identifies the translation or route failure |
| ExternalIP allocation succeeds but DNAT or local route setup does not | Keep ExternalIP allocated, keep ExternalIPAttachment non-ready, retain its consumer reservation and `status.attached=true`, and retry using the same address/next hop | Attachment condition identifies the DNAT or local-route failure |
| External endpoint observes a node address instead of the NATGateway ExternalIP | Remove any MASQUERADE rule from this path, install explicit `SNAT --to-source`, and verify the observed source before Ready | NATGateway remains non-ready with a source-address diagnostic |
| ExternalIPAttachment local-route withdrawal or DNAT cleanup fails | Retain the consumer and ExternalIP finalizers, keep capacity reserved, and retry from the saved address and next hop; do not release while the local `/32`, DNAT/forwarding rules, or conntrack state remains | Attachment remains terminating with an external-cleanup condition |
| NATGateway BGP withdrawal or SNAT cleanup fails | Retain the consumer and ExternalIP finalizers, keep capacity reserved, and retry from the persisted BGP route and SNAT state; do not release while the route or translation remains | NATGateway remains terminating with an external-cleanup condition |
| Consumer cleanup completes but service acknowledgement is lost | Replay `CONSUMER_CLEANUP_COMPLETE` by UUID and digest; service clears the consumer reservation exactly once | `status.attached` remains true until the acknowledgement is durable |
| Provider cleanup completes but capacity-release acknowledgement is lost | Replay `CLEANUP_COMPLETE`; the service's `RELEASED` transition is idempotent and the operator retries finalizer removal | Pool capacity changes once and the ExternalIP finalizer eventually clears |
| Status writers race or return stale snapshots | Patch only owned fields after a fresh read and retry conflicts; never replace full ExternalIP status | Address, attached flag, conditions, and provisioning history are not lost |
| Delete is interrupted | Finalizer re-enters the ordered cleanup phases after restart | Resource remains terminating with cleanup reason |
| Net node restarts | Rehydrate transit links, `/32` route ownership, DNAT/SNAT rules, and conntrack prerequisites from the versioned state file; reconcile actual interfaces/rules before reporting Ready | Existing resource statuses remain non-ready until observed state converges |

All create/delete/attach/detach operations are keyed by stable resource or
binding UID and desired generation. AAP retries must be safe after a controller
restart or lost job response. [Codebase: osac-operator/pkg/provisioning/provision_lifecycle.go]

#### Net-node availability and restore contract

This milestone has one authoritative net node and no automatic standby. A
net-node preflight checks reachability, state-file validation, namespace
inventory, and dnsmasq services before a fabric mutation is accepted. BGP
peer/session availability concerns NATGateway route distribution; an
ExternalIPAttachment is checked against its local FRR route. When the node is unavailable, the operator reports
`NetNodeUnavailable`, blocks new or modifying VirtualNetwork/Subnet,
attachment, NAT, and ExternalIP provider operations, and retains all relevant
finalizers and capacity reservations. It does not mark an unobserved provider
operation committed or release an address during the outage.

If the node process and kernel state remain alive, existing L2/routed flows may
continue while new control-plane changes are blocked. A node reboot or network
namespace loss breaks active connections and may withdraw upstream `/32`
routes; the design does not promise connection or conntrack continuity across
that failure. Existing resources remain represented but degraded until the
restore sequence completes.

Recovery acquires the SQLite sidecar lock and validates the schema-v1
database. If the database is corrupt, recovery is an operator-led restore of a
verified database backup; the application does not select a last-known-good
generation or repair an unrecognized schema. Reconciliation then recreates
namespaces,
veths, VLAN interfaces, gateways, forwarding, dnsmasq from preserved lease
files, and owned DNAT/SNAT rules. It restores local ExternalIPAttachment
routes and NATGateway BGP `/32` routes only after the corresponding namespace
path and translations are verified. Conntrack state is not persisted; old
connections must reconnect, while new connections are
allowed only after the restored rules and routes pass health checks. A malformed
state or failed restore keeps mutations blocked and surfaces `StateCorrupt` or
`NetNodeRestoreFailed` rather than guessing or releasing resources.

### RBAC / Tenancy

No new RBAC or authentication policy is required. Existing OPA and attribution
logic controls who can create or modify tenant resources; provider personas
control NetworkClass, manager registration, and ExternalIPPool configuration.

Tenant-scoped Kubernetes resources retain both
'osac.openshift.io/tenant' and 'osac.openshift.io/owner-reference'. The
owner-reference points to the parent resource where the existing service path
sets it. The operator and service use these annotations for filtering and
feedback attribution. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]

VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment, and NATGateway CRs
are co-located in the configured `$OSAC_NETWORKING_NAMESPACE`/hub namespace.
That namespace is an operator placement boundary, not a tenant-isolation
boundary. Fulfillment-service OPA and attribution checks remain the user-access
boundary. Every AAP lookup or mutation must select the configured namespace,
stable resource UUID, and server-set tenant/owner attribution together; a
resource name alone is never an isolation key. Names may be used only for
diagnostic labels after the UUID and attribution checks pass.

The agentless role receives validated private resource data through AAP. It
must not use a tenant-provided name as an isolation key; the resource UID and
server-side tenant attribution are the isolation inputs. For port moves, the
host UID, authoritative MAC, binding UID, Subnet UID, and provider provisioning
network ID are mandatory; a display host name or V-Net name cannot select a
switch port or detach target.

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
| NetNodeUnavailable | Warning | Net-node reachability, state, or dnsmasq checks fail |
| NetNodeRestoreFailed | Warning | Namespace, DHCP, route, or translation rehydration fails |
| VLANAllocationFailed | Warning | VLAN allocation cannot complete |
| TransitLinkFailed | Warning | A per-VirtualNetwork transit `/30`, veth, or namespace route cannot be created or repaired |
| ExternalIPReservationBlocked | Warning | A durable allocation or consumer reservation cannot advance |
| ExternalIPProviderResultRejected | Warning | Provider result annotations fail UUID, generation, address, or digest validation |
| ExternalIPCapacityReleaseBlocked | Warning | Provider or consumer cleanup has not been acknowledged by fulfillment-service |
| DHCPLeaseUnavailable | Warning | No current lease matches the attachment |
| ExternalRouteApplyFailed | Warning | The ExternalIPAttachment local FRR `/32` cannot be installed/verified or the NATGateway BGP `/32` cannot be announced/verified with its saved next hop |
| ExternalRouteWithdrawBlocked | Warning | The ExternalIPAttachment local route or NATGateway BGP route cannot be withdrawn during consumer or ExternalIP cleanup |
| NATSourceAddressMismatch | Warning | Egress validation does not observe the associated ExternalIP as the source address |
| FabricCleanupBlocked | Warning | Ordered deletion cannot proceed |
| FabricResourceReady | Normal | Desired fabric state and required feedback are ready |

Logs include resource UID, tenant attribution hash or ID permitted by the
existing logging policy, manager name, desired generation, job ID, route prefix
and next hop, interface identity, reservation state, provider operation ID, and
operation result. NAT validation may log the selected address and observed
source address, but not credentials or full secret contents. Provider digests
are logged as identifiers, not as state-file contents.

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

#### BMaaS port restoration

An interrupted handoff can leave a host on a tenant VLAN and prevent the next
PXE/provisioning attempt from reaching the provisioning network. The binding
state persists host/MAC, switch port, tenant VLAN, provisioning-network ID/VLAN,
and direction; attach and detach use the same idempotent reset-plus-set
operation, retain the finalizer on uncertainty, and verify provisioning VLAN
restoration before deleting state.

#### DHCP and lease-store dependency

A missing or unhealthy per-VN dnsmasq service prevents IP status and therefore
prevents reliable inbound DNAT. The role validates the namespace interfaces,
dnsmasq unit/configuration, lease-file format, gateway exclusions, and lease
freshness before attachment; it restarts the daemon from the preserved lease
file and records the failure in status instead of assigning a replacement IP.

#### Stateful net-node failure

A restart or failover can lose namespace, DHCP, conntrack, NAT, veth, local
FRR route, or NATGateway BGP route state. Rehydration first acquires the stable
sidecar lock and validates the SQLite schema-v1 database; corrupt state blocks
every mutation and release until an operator restores a verified backup. It
then reconciles the saved transit link, `/32` route ownership, and translation
rules before reporting a consumer Ready. This
milestone supports one authoritative net node and does not claim multi-node
state replication or automatic failover. Recovery requires the database backup,
network inventory, NATGateway BGP peer configuration where applicable, and an explicit restore action when
the current generation is corrupt.

#### External route and source-address correctness

For ExternalIPAttachment, the role installs the saved local FRR static
`<address>/32 via <next-hop>` route and verifies it in the net-node RIB. Cleanup
withdraws and verifies that local route before removing DNAT, forwarding, and
conntrack state. The job does not query an upstream BGP peer or treat remote
convergence as attachment readiness; provider configuration controls any
distribution beyond the local FRR route. For NATGateway, the provider BGP
action continues to announce and withdraw its `/32` around explicit SNAT.
In both paths, the saved next hop scopes the route to the correct VirtualNetwork,
and the host path must not use MASQUERADE for NATGateway traffic.

#### ExternalIP reservation and handshake correctness

The service database, operator CR, AAP job, and provider state file can observe
the same ExternalIP at different times. Releasing pool capacity from any one
of those observations could oversubscribe an address or release it while a
route is still usable. The UUID-keyed reservation, provider operation ID,
state digest, consumer reservation, compare-and-set events, and one-time
`RELEASED` transaction make the fulfillment-service the sole capacity owner.
Unknown provider outcomes fail closed and require an inspect/cleanup retry.

#### Backend parity

Differences from Netris can change tenant-observable behavior even when API
responses match. A capability-by-capability parity matrix and BMaaS reference
validation compare the in-scope L2, routing, DHCP, DNAT, SNAT, status, and
cleanup behavior. SecurityGroup provisioning and policy enforcement are outside
this milestone and are excluded from the parity claim for both backend paths.
[Locked: C2] [PRD: FR-2, NFR-2]

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

#### Provide external route distribution without tenant-managed L2/ARP

The v1 ExternalIPAttachment role installs and verifies only a local FRR static
`/32` route; provider configuration may distribute that route to external
networks, but the AAP job does not establish the BGP peer or verify remote
convergence. NATGateway retains the provider's BGP `/32` announce/withdraw
action. A tenant-managed L2/ARP design would require floating-address
ownership, gratuitous-ARP/neighbour handling, and a different failover and
cleanup model, so this milestone does not claim that alternative.

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

**Question:** Which exact switch transaction and lock scope implement the
supported Cumulus reset-plus-set operation for attach and detach, including
access-port rollback after a partial failure?

This milestone claims BMaaS attach and detach through the stable binding
contract defined above, but does not claim broader NetworkRunner-provider
behavior. Each operation must be idempotent, preserve the saved provisioning
VLAN, and leave the switch in a known state after a failed retry.

**Impact:** Limits the role argument schema, concurrency tests, support procedures,
and documented switch compatibility.

#### 3. Service-specific attachment inputs

**Owner:** Connectivity & Fabric team with BMaaS and CaaS owners

**Question:** What canonical host, interface, MAC, and primary-attachment data
does each BMaaS, CaaS, and VMaaS integration provide to the generic attachment
and DHCP roles?

**Impact:** The BMaaS binding, provisioning-network identity, and MAC-to-lease
mapping are defined here; CaaS and VMaaS may extend the generic contract with
their own stable host identity without changing the BMaaS identity rule.

## Test Plan

The detailed requirement-anchored testplan will be drafted after the design is
approved. The following scenarios summarize the expected coverage; they are
not a substitute for that testplan.

### Unit Tests

- Parse and validate agentless manager ConfigMap capabilities.
- Allocate and release VLAN IDs with idempotence, collision rejection, pool
  exhaustion, SQLite transaction contention, and restart recovery cases.
- Verify the exact SQLite table definitions and `PRAGMA user_version=1`.
  Exercise both recognized prior-v1 table layouts, interrupted transactions,
  sidecar/resource-lock serialization, foreign-key enforcement, and fail-closed
  handling of corrupt, noncanonical, or unknown layouts. No JSON backup or
  downgrade migration is used.
- Verify net-node preflight blocks mutations and capacity release while the
  node is unavailable, then rehydrates namespaces, dnsmasq, routes, and NAT
  from the validated state; confirm old conntrack flows are not promised.
- Allocate one transit `/30` per VirtualNetwork and preserve its namespace/host
  addresses, next hop, and route identity across retries.
- Map resource UID, tenant, VirtualNetwork, Subnet, and attachment identity to
  deterministic namespace/state keys.
- Compile and validate the permit-all forwarding baseline without introducing
  policy-resource inputs or default-deny gates.
- Validate DHCP lease artifact identity, address family, Subnet reference, and
  desired-generation freshness.
- Validate dnsmasq range generation, gateway/reserved-address exclusions,
  lease-file parsing, daemon restart, and lease preservation across reload.
- Verify ExternalIPAttachment whole-address DNAT and local FRR route
  install/verify/withdraw ordering; verify NATGateway SNAT-before-BGP announce
  and BGP-withdraw-before-release ordering.
- Verify NATGateway source-CIDR reconciliation when a Subnet is added, updated,
  or deleted, including rule-set revision and ordering before VLAN release.
- Inject an ExternalIP SQLite transaction failure and verify that no partial
  `external_ips` row is visible, retries reuse the same UUID reservation, and
  terminal failure compensates capacity only after `NOT_COMMITTED`.
- Verify v1 `osac_result` validation and unversioned annotation compatibility,
  idempotent private provider events, consumer exclusivity for Attachment versus
  NATGateway, field-scoped status updates, and exactly-once `RELEASED` capacity
  accounting.
- Validate attachment binding keys, host/MAC identity, direction transitions,
  provisioning-network resolution, and idempotent attach/detach state changes,
  including reboot, power-off, and
  DHCP-gated handoff phases.
- Verify status condition reason/message mapping for AAP and controller-owned
  allocation errors.

### Integration Tests

- Render manager ConfigMap and NetworkClass selection with Helm values.
- Reconcile VirtualNetwork and multiple Subnets through envtest/fake AAP
  providers; verify provider-side ExternalIP allocation
  annotations populate status only after a committed reservation event,
  consumers persist the transit/route state, and DNAT/SNAT actions use that
  address.
- Exercise ExternalIPAttachment local FRR static `/32` install, verification,
  and withdrawal with its saved next hop; check the local RIB and packet path
  without requiring upstream BGP convergence.
- Exercise NATGateway BGP `/32` announce/withdraw with its saved next hop and
  verify the provider-owned peer sees the route. Exercise whole-address DNAT
  for API/ingress endpoints and explicit-source SNAT without host-side
  MASQUERADE.
- Exercise Subnet churn while NATGateway is Ready: verify a new SNAT rule is
  installed before Subnet readiness and an old rule is removed before Subnet
  VLAN/DHCP cleanup.
- Exercise ExternalIP deletion during allocation and verify UUID serialization,
  Pending/Failed compensation, provider cleanup, consumer cleanup, and delayed
  exactly-once API capacity release.
- Verify tenant and owner annotations survive the service-to-CR path.
- Verify per-VN dnsmasq configuration and service lifecycle for multiple VLAN
  interfaces, including malformed configuration and lease-file recovery.
- Exercise generic DHCP job artifact consumption for multi-NIC instances using
  distinct Subnets, and reject duplicate SubnetRefs before lease discovery.
- Exercise Cumulus attach and detach with a fake switch: verify tenant VLAN
  placement, provisioning-VLAN restoration, partial-failure retry, and
  controller/AAP restart recovery from `port_bindings`. Verify the BMF power
  and reboot gates before DHCP discovery and before tenant-to-provisioning
  restoration.
- Stop and restart the net node during Ready traffic and cleanup; verify
  existing resources become degraded, new operations are blocked, local
  attachment routes and NATGateway BGP routes are restored after the data path,
  and capacity is not released early.
- Exercise AAP role argument validation and idempotent create/delete for the
  Cumulus support contract.
- Verify all VLAN/IPAM writers use the shared sidecar-lock transaction and that
  the legacy in-place IPAM writer cannot mutate the unified state file.
- Verify controller restart/requeue behavior and ordered finalizer cleanup.

### E2E Tests

- Configure the Cumulus-backed agentless manager and create a VirtualNetwork
  and multiple Subnets through the existing API.
- Verify same-Subnet L2, permitted same-VN cross-Subnet traffic, and
  private-address isolation between overlapping VirtualNetworks.
- Provision a BMaaS reference attachment, obtain a DHCP address, and observe it in
  status.
- Verify the BMaaS lifecycle moves a host from provisioning to its tenant VLAN
  then reboots and observes tenant DHCP before Ready, and powers it off before
  returning to the exact provisioning VLAN on offboarding, without relying on a
  Netris variable or display name.
- Verify an external-client probe reaches a BareMetalInstance through the
  saved local FRR route and whole-address DNAT, then receives its response;
  upstream BGP convergence is not an AAP attachment-readiness check.
- For NATGateway, verify the upstream BGP peer learns its `/32`, outbound
  traffic is explicitly SNATed, and the external endpoint observes the
  NATGateway ExternalIP as the source address.
- Verify ExternalIPAttachment and Subnet/VirtualNetwork deletion order and
  non-interference with other tenants, including local FRR route withdrawal,
  DNAT/conntrack removal, and NATGateway BGP/SNAT cleanup before ExternalIP
  reuse.
- Verify an ExternalIP cannot be acquired by both an ExternalIPAttachment and a
  NATGateway, and that `status.attached` remains true until consumer cleanup is
  acknowledged even when child data-plane readiness fails.
- Keep full CaaS/VMaaS service validation in the downstream follow-up features
  named by the PRD.

## Graduation Criteria

The target milestone is the IPv4-only agentless VLAN milestone described by the
PRD. Graduation to a broader support stage requires:

- all PRD acceptance criteria pass for the Cumulus reference environment;
- no critical tenant-isolation, DNAT/SNAT-direction, or deletion-order defects;
- BMaaS reference provisioning and DHCP status feedback pass repeatedly;
- inbound ExternalIP traffic follows the saved local FRR route and DNAT to the
  intended VirtualNetwork, outbound traffic observes the NATGateway ExternalIP,
  and cleanup removes the relevant local or BGP route before address reuse;
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

AgentlessNet provider state remains SQLite schema v1
(`PRAGMA user_version=1`). The application additively migrates only the two
known earlier v1 table layouts into the canonical schema after validating all
existing tables. Unknown layouts and corruption fail closed. Before deploying,
operators retain a backup of the SQLite database, network inventory, and BGP
configuration. There is no downgrade path or in-place OSAC rollback guarantee
after a new consumer table has been added.

The fulfillment-service migration creates one reservation row for every
existing ExternalIP before enabling the new create/delete path. Existing
allocated objects start in `COMMITTED` only when their provider address can be
verified; otherwise they start in `HELD` with `provider_state=UNKNOWN` and
remain unavailable for release until an inspect action establishes
`COMMITTED` or `NOT_COMMITTED`. Existing Attachment/NATGateway references are
backfilled as consumer reservations under the ExternalIP UUID lock.

To disable the backend, the provider selects another NetworkClass only after
agentless-managed resources are drained or intentionally retained. Disabling a
manager does not delete tenant resources or silently release its allocations.
There is no in-application SQLite downgrade path. Reverting code requires the
operator to stop reconciliation and restore a backup whose table shape matches
that code version; the application never silently drops or rewrites tables.

## Version Skew Strategy

The operator, fulfillment-service, installer, and AAP collections must agree on:

- manager name 'agentless_net';
- configured `OSAC_NETWORKING_NAMESPACE` hub namespace for every networking CR;
- capability string 'ipv4';
- implementation-strategy value;
- generic job names and input shapes;
- status/lease artifact schema;
- SQLite `PRAGMA user_version=1`, canonical table/index/foreign-key shape, and
  the exact additive migration from recognized earlier v1 table sets;
- state transaction protocol: SQLite `BEGIN IMMEDIATE` and commit, a stable
  sidecar lock for database access, and per-VirtualNetwork operation locking;
- per-VirtualNetwork transit-link fields, the saved local FRR next hop for
  ExternalIPAttachment, and the BGP `/32` prefix/next-hop contract for
  NATGateway;
- network-attachment binding fields, `attach`/`detach` direction semantics,
  stable provisioning-network identity, and the `port_bindings` state shape;
- DHCP daemon (`dnsmasq`) lifecycle, per-VN config/lease paths, range and
  exclusion rules, and lease-artifact identity validation;
- whole-address DNAT inputs and explicit-source SNAT inputs. A component that
  still sends the old single-port DNAT or MASQUERADE-only SNAT arguments must
  not report the consumer Ready.
- ExternalIP v1 `osac_result` fields and unversioned allocated-address
  annotation compatibility, private provider-event values, consumer cleanup
  events, and the rule that only
  fulfillment-service releases pool capacity;
- ExternalIP status field ownership: fulfillment-service owns `attached`, while
  the operator owns `address`, `state`, `phase`, `conditions`, and provisioning
  fields through field-scoped conflict-safe updates.

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
3. Check net-node reachability, state validation, namespace inventory, and
   dnsmasq services. Check BGP session health for NATGateway route operations;
   inspect the local FRR RIB for ExternalIPAttachment route state.
4. Inspect AAP job status, 'leases' and v1 `osac_result` artifacts, the
   allocated-address annotation only for unversioned managers, reservation
   events, dnsmasq unit/configuration and lease paths, and the agentless logs.
5. Check the lock-protected SQLite database for the resource UID, VLAN,
   gateway/DHCP, namespace, transit `/30`, veth peer addresses, provider-side
   ExternalIP allocation, attachment local-route next hop, NATGateway BGP
   `/32` prefix/next hop, and owned NAT/DNAT rule mapping. Compare any
   ExternalIP address with
   `ExternalIP.status.address` and provider state. Inspect the allocated-address
   annotation only when the selected ExternalIP manager is unversioned. Confirm
   the fulfillment-service reservation
   state and pool counters before diagnosing capacity. Also inspect the stable
   sidecar lock, schema validation result, and any `StateCorrupt` event before
   attempting an operator-led database repair.
6. Verify Cumulus VLAN/trunk/access-port state and the net-node namespace,
   interfaces, local attachment-route and NATGateway BGP installation or
   withdrawal, exact whole-address DNAT, explicit `SNAT --to-source` rules,
   and conntrack state. Confirm that no
   host-side MASQUERADE rule can overwrite the NATGateway source address. For
   BMaaS, compare the binding UID, host/MAC, switch port, tenant VLAN,
   provisioning-network ID/VLAN, direction, and observed state with
   `port_bindings`; never infer detach behavior from a display name.

To disable new use, remove or change the NetworkClass selection after draining
resources; do not delete the manager ConfigMap while resources still need
reconciliation. Existing workloads retain their applied fabric state until
explicit cleanup. Re-enabling the manager resumes reconciliation if the
SQLite schema-v1 database and network inventory validate.

## Infrastructure Needed

A repeatable validation environment needs:

- a Cumulus switch or equivalent validated Cumulus test target;
- one or more network-node hosts with privileged namespace/VLAN/firewall access;
- a provider transit-CIDR pool and local FRR access for ExternalIPAttachment
  route install/withdraw checks;
- a configured BGP peer and `/32` route verification for NATGateway tests;
- AAP inventory and job templates for the generic networking playbooks;
- dnsmasq and a service supervisor on the net node, with per-VN configuration
  and IPv4 lease storage accessible to the agentless role;
- an ExternalIPPool and an external traffic endpoint for DNAT/SNAT assertions;
- existing OSAC kind/integration fixtures for service and controller tests.

No new repository is required. Test infrastructure changes should extend the
existing mono-repo and tests/e2e patterns.

---

## Provenance

Authored: revise @ design 0.11.5 - e2b0d87, workspace osac-6202-natgateway-snat @ 9eac9f81a
Final: revise [manual] @ design 0.11.5 - e2b0d87, workspace osac-6202-natgateway-snat @ b6007aac2

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"b6007aac2","source_repo_branch":"osac-6202-natgateway-snat","commits_behind_main":0,"commits_ahead_main":17,"main_ref":"main","phases":["revise","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
