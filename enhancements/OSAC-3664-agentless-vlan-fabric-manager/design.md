---
title: agentless-vlan-fabric-manager
authors:
  - yonibettan@gmail.com
creation-date: 2026-09-08
last-updated: 2026-11-03
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

> **Implementation baseline (OSAC-6752).** This revision was checked against
> [osac#2170](https://github.com/osac-project/osac/pull/2170), head
> [`54272aa80e6a56ff1d77b2ee8cf4749267f98cbe`](https://github.com/osac-project/osac/tree/54272aa80e6a56ff1d77b2ee8cf4749267f98cbe).
> That implementation is under review, not a release or deployment claim.
> The current AgentlessNet behavior below supersedes the older proposed mechanics
> where explicitly identified. Requirement and IC identifiers remain unchanged;
> unsupported requirements are not removed or claimed complete. The shared
> [network manager contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)
> remains provider-neutral.

### Current AgentlessNet behavior

Paths in this section refer to the pinned source tree above, not a moving branch.

| Area / traceability | Behavior in the reviewed implementation | Public source path |
|---|---|---|
| Registration / IC-1, FR-1, NFR-1 | The installer renders an immutable ConfigMap labeled `osac.openshift.io/network-fabric-manager: "true"`, with `data.name: agentless_net` and `data.ansible_role: osac.templates.agentless_net`. It does not register `role: fabric` or `capabilities: ipv4`. Role metadata describes IPv4-only support; this is not a capability field in the registration. No network type is advertised. | `osac-installer/charts/osac/templates/networking/agentless-net-registration.yaml`; `osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/meta/osac.yaml` |
| Dispatch and identity / IC-2, IC-3, FR-2, FR-8 | `playbook_osac_network_task.yml` runs the selected role's task file with `osac_job_vars`. Provider ownership uses `resource.id` (the API UUID), not `resource.metadata.uid`. Parent snapshots, `tenant`, and `ipam` come from the controller. Legacy state field names ending in `uid` do not mean Kubernetes UIDs. | `osac-aap/playbook_osac_network_task.yml`; role tasks `_validate_task_input.yaml`, `create_virtual_network.yaml`, `create_subnet.yaml` |
| Physical attachment / IC-3, FR-8 | `apply_network_attachment` and `delete_network_attachment` handle physical BareMetalInstance targets. Provider inventory resolves the host/interface to switch ports and the provisioning VLAN. SQLite stores `network_attachments` and exclusive `network_attachment_ports` claims, not the proposed `port_bindings` table. There is no generic move-playbook input or binding-result envelope in this path. | Role tasks `apply_network_attachment.yaml`, `delete_network_attachment.yaml`, `_resolve_attachment_configuration.yaml`; `plugins/module_utils/agentless_net_state.py` in the same collection |
| DHCP / IC-3, FR-4 | Attachment apply reserves an address from the saved `physical_ipv4_cidrs` before DHCP convergence. dnsmasq serves static MAC/address reservations and ignores unknown clients. Query requires the saved ready attachment, authoritative MAC, exact reserved address, and an active lease; merely finding that MAC elsewhere in the Subnet is insufficient. The typed result is `osac_result.dhcp_lease: {ip_address, mac_address}`, not a `leases` list. | Role task `query_dhcp_lease.yaml`; `plugins/module_utils/agentless_net_state.py` (`query_dhcp_lease`, `prepare_network_attachment`); `plugins/module_utils/agentless_net_subnet.py` (`find_active_dhcp_lease`, `_render_dhcp_config`) |
| ExternalIP / IC-4, FR-5 | The controller supplies `external_ip_pool`; allocation is API-ID-owned, with `osac_result.external_ip.address`. No `externalIPContractVersion`, `osac_result.data`, annotation fallback, or `RecordExternalIPProviderEvent` handshake belongs to this task contract. | Role task `_external_ip.yaml`; `osac-operator/internal/controller/externalip_controller.go`; `osac-operator/internal/networktask/result.go` |
| ExternalIPAttachment / IC-4, FR-5, FR-7 | `attach_external_ip` / `detach_external_ip` consume `external_ip` and `destination.address` plus `destination.routing_domain`. AgentlessNet requires `tenant_virtual_network` with API `virtual_network_id` and `subnet_id`; it does not require a BareMetalInstance target object. Hub-network destinations are unsupported. Successful attach/detach tasks emit no typed result. | Role task `_external_ip_attachment.yaml`; `osac-operator/internal/controller/externalipattachment_controller.go` |
| State and status / IC-2, IC-6, FR-9, FR-10 | Schema-v1 SQLite retains API-ID-owned provider allocations and cleanup state. VN transit is a `/31` within the VN CIDR, not the proposed separate `/30` pool. Provider-local phases are not CR status fields: networking CRs use `Ready` conditions, `status.jobs`, and the saved `status.taskInput`. | `plugins/module_utils/agentless_net_state.py`; `osac-operator/internal/networktask/engine.go`; `osac-operator/api/v1alpha1/networkattachment_types.go` |

The role task and plugin paths abbreviated above are under
`osac-aap/collections/ansible_collections/osac/templates/roles/agentless_net/`
and `osac-aap/collections/ansible_collections/osac/templates/`, respectively.

No per-task contract-version key is used; this does not remove the resource
snapshot's `apiVersion`, `metadata.uid` or `metadata.generation`. Those fields
describe the captured CR, while `resource.id` identifies provider ownership.

SecurityGroup tasks are a documented physical-policy no-op, not enforcement.
FabricDomain creation and cluster-ingress reservation fail as unsupported;
their cleanup tasks are no-ops. Physical NetworkAttachment apply/query is
BareMetalInstance-only, while ExternalIPAttachment accepts the tenant-network
destination abstraction. That abstraction alone does not prove VMaaS or CaaS
integration or packet delivery. These are AgentlessNet limits, not restrictions
on other Fabric Managers, and do not amend the future policy proposals in
[enhancement-proposals#324](https://github.com/osac-project/enhancement-proposals/pull/324)
or [#428](https://github.com/osac-project/enhancement-proposals/pull/428).

The later reservation/provider-event model, resource YAML examples, logical
state example, and associated recovery procedures retain the original design
intent for traceability. Their version keys, `port_bindings`, pool counters,
provider events, `/30` pool, and CR `phase` examples are **not current
implementation instructions**. Use the table above and the shared contract
for the reviewed task protocol. The [testplan](testplan.md) distinguishes
source test coverage from unexecuted acceptance scenarios.

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

The original motivation was a Netris-backed physical fabric path alongside
agentless VLAN building blocks for CaaS-specific VLAN, router, SNAT,
DNAT, and external-access workflows. Those building blocks did not provide
the unified API lifecycle. The reviewed baseline now registers a separate
`osac.templates.agentless_net` Fabric Manager; it does not turn the old CaaS
inline workflows into evidence of generic task conformance. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

The original inline agentless path allocates VLANs and creates a router namespace
per cluster workflow. The unified networking model requires a namespace per
VirtualNetwork, multiple VLAN-backed Subnets inside that namespace, permitted
routing between those Subnets by default, permitted external ingress and egress
through supported paths, and no private routing between different
VirtualNetworks. SecurityGroup resources and policy enforcement are deferred;
the design must not introduce policy-dependent readiness gates.
[Locked: D12] [User] [Research: VLANs and Linux network isolation]

Bare-metal nodes must obtain IPv4 addresses through fabric-side DHCP, and the
lease must reach the resource status path before external access can be enabled.
After network handoff, the NetworkAttachment controller starts the DHCP-lease AAP
task through `playbook_osac_network_task.yml`. The agentless role queries the
per-namespace lease store for the saved reservation and publishes a typed
`osac_result.dhcp_lease`; the operator accepts it into NetworkAttachment status.
That does not establish the workload feedback path: the baseline BMF IP-discovery
code still parses the legacy `leases` artifact, not this typed result.
Propagating the discovered address into BareMetalInstance status and then
fulfillment-service remains a service-integration acceptance goal, not a result
proved by these provider tasks. ExternalIPAttachment waits for the target's
primary workload address before creating DNAT. [PRD: FR-4] [Codebase:
osac-operator/internal/controller/networkattachment_controller.go;
bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery.go]

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

The reviewed implementation places AgentlessNet behind the existing
NetworkClass and generic network-task lifecycle. The installer registers
`osac.templates.agentless_net`; the operator supplies API-ID-owned snapshots,
orders tasks, validates typed results, and records observed status.
AgentlessNet owns its SQLite provider allocations and the physical data plane:
VirtualNetwork namespaces, Subnet VLANs, DHCP reservations, physical port claims,
local ExternalIPAttachment routes/DNAT, and NATGateway routes/SNAT.
The proposed fulfillment-service reservation/event model retained later in this
document is not part of this task adoption. No version key or legacy annotation
handoff is used for the reviewed AgentlessNet allocation result. [PRD: FR-1,
FR-2] [IC-1, IC-2, IC-4]

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
resources. Pool CIDRs arrive as API/controller snapshots and are persisted in
provider pool state; they are not independently selected by inventory.

1. The unified Networking API selects the backend through
   NetworkClass.fabric_manager and the osac-operator dispatcher. It does not
   use NETWORK_STEPS_COLLECTION. That variable selects the AAP collection used
   by embedded CaaS workflows such as cluster_infra and external_access; the
   CaaS follow-up may set it to agentless_net.steps, but this BMaaS-focused
   design does not require changing it. [PRD: FR-1] [Codebase: osac-aap/group_vars/all/configuration.yaml]
2. The admin sets installer `global.networking.fabricManager: agentless_net`.
   The installer renders the immutable manager registration with
   `name: agentless_net` and `ansible_role: osac.templates.agentless_net`.
   This registration now follows the generic task contract; that is not
   evidence of a released or validated deployment. There are no per-task
   version keys.
3. The installer creates a ConfigMap labeled
   'osac.openshift.io/network-fabric-manager' with 'data.name=agentless_net'.
   The operator discovers it and includes the manager in NetworkClass
   manager reconciliation. All networking CR projections use the configured
   `OSAC_NETWORKING_NAMESPACE` hub namespace; tenant IDs remain annotations,
   not namespaces. [Codebase: osac-installer/charts/osac/templates/networking/agentless-net-registration.yaml]
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
   route distribution. The reviewed provider selects a VN-owned transit `/31`
   inside the VN CIDR; it does not consume a separate transit-pool setting.
   VLAN allocation is internal state from the configured VLAN-ID pool;
   DHCP is created per Linux namespace; and the state
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
   operation completes. Retries reuse API-ID-keyed state and repair partial data
   plane configuration instead of allocating duplicate VLANs or namespaces.

The fulfillment-service remains authoritative for a client-supplied Subnet CIDR.
AgentlessNet validates that the requested CIDR is inside the VirtualNetwork
supernet and does not overlap a sibling before applying data-plane state; it
does not allocate a second CIDR or contradict the service object. Automatic
Subnet CIDR allocation, if required by a future API path, remains an open
question because the current API requires a CIDR and the current service
already performs this validation. [Codebase: fulfillment-service/proto/private/osac/private/v1/subnet_type.proto]

#### BMaaS attachment and DHCP feedback

The reviewed path uses NetworkAttachment tasks, not
`playbook_osac_move_network_attachment.yml`. The controller snapshots the
BareMetalInstance target, physical interface/MAC, Subnet, VirtualNetwork,
tenant, and IPAM plan in `osac_job_vars`. `resource.id` is the target API UUID;
Kubernetes UID and generation remain snapshot metadata, not provider ownership
keys. This describes the current BMaaS path, not completed CaaS/VMaaS service
integration. [PRD: FR-4, FR-8] [IC-3]

1. `apply_network_attachment` requires a physical BareMetalInstance target and
   matching parent snapshots. Provider inventory maps `target.host_name` and
   the interface to Cumulus ports; the task checks the saved Ready Subnet and
   exact IPAM plan before changing ports.
2. The provider saves the attachment, an address from its recorded physical
   ranges, and exclusive switch-port claims in SQLite. Retries reuse that
   allocation. It reconciles static DHCP reservations, applies the selected
   tenant VLAN and removes other mapped fabric interfaces from the tenant
   network, then marks the provider attachment ready.
3. The NetworkAttachment controller waits for the BareMetalInstance's
   `NetworkHandoffComplete` before starting `query_dhcp_lease`. The handoff and
   reboot remain workload-controller responsibilities, not a provider move
   result envelope.
4. Query reads the saved ready API-ID-owned attachment under the VN lock.
   It accepts only an unexpired (or non-expiring) lease for the reserved MAC
   **and exact reserved address**. Missing matches remain retryable; ambiguous
   matches and malformed lease files do not become successful discoveries.
5. The role returns `osac_result.dhcp_lease` with `ip_address` and `mac_address`.
   The controller's acceptance callback validates the MAC and physical address
   range before storing `NetworkAttachment.status.dhcpLease`. This is not the
   earlier per-BMI `leases` list with `subnet_ref` entries.
   NetworkAttachment Ready records successful apply before lease discovery;
   it is not proof of a lease or workload IP readiness. The baseline BMF
   discovery path still consumes the legacy artifact, so this controller's
   status write must not be presented as completed BMF/fulfillment feedback.
6. `delete_network_attachment` marks deletion, retains saved claims during
   cleanup, marks owned switches against late apply, restores saved fabric
   ports to the **currently validated provider-inventory provisioning VLAN**,
   then releases DHCP/address/port state. It does not restore a historical
   provisioning-network ID from a `port_bindings` row. Failed cleanup keeps
   ownership for retry.

Source: role tasks `apply_network_attachment.yaml`,
`delete_network_attachment.yaml`, `query_dhcp_lease.yaml`, and
`osac-operator/internal/controller/networkattachment_controller.go` at the
[reviewed baseline](#current-agentlessnet-behavior).

#### ExternalIP and inbound access

> **Baseline distinction.** The numbered sequence below retains the earlier reservation/event proposal, not the reviewed implementation. In #2170, `create_external_ip` returns `osac_result.external_ip.address`; `attach_external_ip` / `detach_external_ip` take `external_ip` and `destination` and return no typed output. The operator derives the destination from workload status. AgentlessNet accepts only a `tenant_virtual_network` routing domain, not a hub-network destination. No version key, annotation fallback, or provider-event RPC is used. See Current AgentlessNet behavior for the replacement protocol. [IC-4]

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
3. The agentless role installs one namespace-side `POSTROUTING` rule with
   explicit `SNAT --to-source <ExternalIP.status.address>` for the whole
   VirtualNetwork CIDR
   when traffic exits through the transit veth. It must not use `MASQUERADE`
   in the namespace or on the host for this path, because that would expose a
   node/interface address instead of the allocated ExternalIP. The host path
   installs a consumer-scoped NAT bypass before any generic POSTROUTING
   masquerade and scoped forwarding/return rules. The role then announces the
   exact ExternalIP `/32` through BGP using the saved namespace-side transit
   address as next hop.
4. Subnet create and delete do not reconcile NATGateways, because the rule
   covers the VirtualNetwork CIDR. A gateway deletion uses its saved identity
   and remains able to complete while Subnets are terminating. If the
   VirtualNetwork has no Subnets, the NATGateway keeps its consumer reservation
   and route.
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
the operator retries only a `retryable: true` failure; a failed delete is always retried. The operator accepts a
successful create only while the NATGateway and its dependencies still match the
stored input and are Ready and allocated; otherwise the result is rejected as
final and the provider state stays until the delete task. The delete removes the
saved route, translation, forwarding, and matching conntrack state and verifies
it, from the saved provider row, not from live dependency readiness. [OSAC-6693]

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
- If DHCP returns no matching lease, the query retries without a discovered
  address. NetworkAttachment Ready may already be true after apply; it is
  not a workload IP-readiness signal. The independent
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

> **Baseline distinction.** Historical proposed coordination model, not implemented by the reviewed baseline: the table and provider-event operation below are retained for traceability, not required AgentlessNet setup or task inputs. Do not implement a versioned result or service migration from this section as part of OSAC-6752. The shared task contract and typed results described above apply. [IC-4]

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

> **Baseline distinction.** The following YAML sketches are original design examples, not current CR manifests. In the reviewed code, Ready conditions, `status.jobs` and `status.taskInput` replace these `phase`/state examples; pool-counter examples and versioned-result annotations are not evidence of current fields. API IDs, not CR UIDs, identify provider state. [IC-2, IC-4, IC-6]

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

The installer selects AgentlessNet when
`global.networking.fabricManager: agentless_net` and renders
`osac-network-fabric-manager-agentless-net` in the release namespace. The
immutable ConfigMap uses the fabric-manager label and only the registration
fields `name` and `ansible_role`; the label supplies manager type. It has no
`role`, `capabilities`, or per-task version keys. The generic
`playbook_osac_network_task.yml` checks the fabric task allowlist and invokes
`osac.templates.agentless_net` with `tasks_from: osac_job_vars.task`.
An undiscovered manager must not silently fall back to Netris. [IC-1, IC-2]

#### NetworkClass capability boundary

AgentlessNet's `meta/osac.yaml` describes `supports_ipv4: true`,
`supports_ipv6: false`, and `supports_dual_stack: false`. Those informational
role fields are not registration capabilities. No Kubernetes network type
(such as `evpn`) is advertised. IPv4-only support remains NFR-1; do not infer
IPv6 rejection or end-to-end service conformance solely from this metadata.
See shared contract §4.2 for registration semantics. [PRD: FR-1, NFR-1]
[Locked: D10, D11]

#### VirtualNetwork and Subnet realization

The agentless role uses deterministic names derived from the resource API ID, not
tenant-provided display names, for Linux namespaces and state keys. The mapping
is:

1. VirtualNetwork API ID -> one Linux router namespace.
2. Subnet API ID -> a lookup key for one numeric VLAN allocation from the internal
   fabric VLAN-ID pool. The VLAN number is separate from the Subnet API ID, and
   the usable 802.1Q range is approximately 4094 IDs per physical fabric.
3. VLAN ID -> one VLAN subinterface moved into the VirtualNetwork namespace.
4. Subnet snapshot and recorded IPAM -> gateway address and static physical
   DHCP scope in that namespace. The backend validates and uses the supplied
   `ipam.gateway_ipv4`, assigns it to the Subnet VLAN interface, and advertises
   it as the DHCP default gateway; it does not choose a competing address plan.
   This address is backend data-plane state, not
   an ExternalIP or a separate Kubernetes object. Subnet deletion removes the
   DHCP scope and gateway address before deleting the VLAN interface and
   releasing the VLAN.
   The reviewed provider additionally rejects prefixes longer than `/28` for
   its recorded address plan (`agentless_net_state.py::_subnet_payload`). The
   older `/30` minimum and TC-NFR1-02's positive `/30` scenario remain desired
   acceptance behavior, not current AgentlessNet support. This provider limit
   does not change the shared address-plan contract or another manager's
   support for small Subnets. [PRD: FR-3, FR-4, NFR-1]
5. VirtualNetwork namespace -> one uplink boundary used for routing and external
   NAT.
6. VirtualNetwork API ID -> one saved transit `/31` selected inside the VN
   CIDR, used by the namespace-side route, host-side veth peer, and external
   next hop. There is no separate deployment transit-CIDR pool in this path.
   The provider checks host-route conflicts before realization. The router
   contract requires the namespace address, host peer
   address, and namespace default gateway to be persisted; they are not
   recomputed from a display name during cleanup.

The VLAN allocation is globally unique within the physical fabric. Reconciliation
looks up the Subnet API ID before allocating, so retries preserve the same VLAN.
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
API IDs (including legacy column names such as `uid` and `fulfillment_id`).
Kubernetes UIDs are snapshot metadata, not provider ownership keys. The database
tracks data-plane
resources, provider-side pool registration, and concrete ExternalIP allocations
owned by AgentlessNet; fulfillment-service remains authoritative for API objects
and service-side lifecycle state. The reviewed provider requires the exact
schema-v1 layout and the `network-manager-api-id-v1` contract marker. It does
not add missing consumer tables to an old database or adopt legacy UID-owned
state automatically. Incompatible layouts fail closed; operators must not
treat the historical logical sketch below as a migration procedure.

##### State structure

> **Baseline distinction.** Historical logical state sketch: do not use this example to construct or repair the current SQLite database. The reviewed schema uses API IDs in legacy `uid` columns, `network_attachments` and `network_attachment_ports` for physical reservations/claims, and a VN-owned `/31` transit selected inside the VN CIDR. It does not use the sketched `port_bindings` table or separate `/30` transit pool. [IC-2, IC-3]

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
    context: <validated ExternalIP and VirtualNetwork snapshot, including virtual_network.ipv4_cidr>
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
in the local FRR RIB. The saved `virtual_networks` payload's `transit` contains
a VN-owned `/31` selected inside that VirtualNetwork's CIDR, not from a
separate provider transit pool. Allocation starts at a deterministic slot
derived from the API ID and VN CIDR, probes for a free transit start, and
persists the selection for reuse on retry. The namespace and veth identities
are also derived from the API ID. `namespace_ip` is the upper `/31` address
and the saved next hop for both local ExternalIPAttachment and NATGateway
routes; `host_ip` is the lower address on the net node; `gateway` is that
host address without the prefix, used for the namespace's default route.
The provider-facing `external_interface` belongs to the consumer's provider
context, not the transit payload. Both consumer tasks use local FRR route
helpers; task success does not establish BGP sessions or upstream convergence.

> **Historical coordination/state protocol, not current instructions.** The
> service reservation/event, `port_bindings` and additive-migration mechanisms
> in the following discussion, including references in its numbered write
> protocol, are earlier proposals, not reviewed baseline support. This does not
> negate the existing provider pool/allocation tables or SQLite transaction and
> locking behavior described alongside them. Current API-ID schema validation
> rejects older layouts without migration; use the Version Skew Strategy and
> Support Procedures for current compatibility and recovery boundaries.

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
cluster API-versus-ingress choice. `context.virtual_network.ipv4_cidr` is the
source of the SNAT rule, so a change of the VirtualNetwork's Subnets does not touch it.
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

> **Baseline distinction.** The table below retains proposed transitions. Current physical attachment operations are `apply_network_attachment` / `delete_network_attachment`, DHCP is a typed `dhcp_lease` result, and ExternalIPAttachment uses `attach_external_ip` / `detach_external_ip`. The legacy move task, provider-event handshake and binding-result fields are not implemented. [IC-2, IC-3, IC-4]

| API action | State transition | AgentlessNet data-plane operation |
|---|---|---|
| VirtualNetwork create/update/delete | Add or reconcile one `virtual_networks` entry, including its transit `/30`, veth identities, and external-reachability mode; remove it only when the VirtualNetwork object is deleted and its child entries are gone | Allocate or reuse the transit link; create or repair the namespace, uplink, default route, and permit-all baseline; remove the link during ordered cleanup |
| Subnet create/update/delete | Add or reuse one `subnets` row with VLAN interface, gateway, DHCP range, exclusions, and state generation; remove it and release the VLAN only when the Subnet object is deleted and dependent bindings are gone | Create or repair the switch VLAN, namespace interface, gateway, dnsmasq range, and lease mapping; on delete, release DHCP, interface, and VLAN state; NATGateways are not touched |
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

Each Subnet uses the controller-supplied `ipam.gateway_ipv4` and recorded
`ipam.physical_ipv4_cidrs`; AgentlessNet does not recalculate the shared address
plan. Attachment apply reserves a usable physical address and renders a
static `dhcp-host` MAC/address mapping. dnsmasq uses static scopes and
`dhcp-ignore=tag:!known`; an empty physical range creates no physical DHCP
scope. It does not allocate an arbitrary dynamic address to an unknown MAC.
Reservations exclude the recorded gateway, VIP and other non-physical ranges.
[PRD: FR-4] [IC-3]
[Locked: D13]

The lease query is read-only: it neither creates a missing initialized lease
file nor converts a reservation alone into observed DHCP success. It checks
ready provider state, tenant ownership, MAC, expected reserved address and
expiry, returning only `osac_result.dhcp_lease: {ip_address, mac_address}`.
The controller validates the result through `networktask.ParseDHCPLease` and
stores it in the NetworkAttachment status. No top-level `leases` artifact or
per-entry `subnet_ref` is returned. The BMaaS workflow above states the handoff
gate; deployed DHCP and workload feedback still require end-to-end validation.

Source: `agentless_net_state.py::query_dhcp_lease`,
`agentless_net_subnet.py::find_active_dhcp_lease` and `_render_dhcp_config`,
role task `query_dhcp_lease.yaml`, and
`osac-operator/internal/networktask/result.go` at the reviewed baseline.

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
SecurityGroup deletion/reconciliation contract in this design (the
SecurityGroup AAP tasks are documented no-ops), and no policy-dependent readiness gate is added to
VirtualNetwork, ExternalIPAttachment, or NATGateway reconciliation. A future
policy design must choose an enforcement point that observes per-attachment
traffic (for example, Cumulus access-port ACLs or an explicitly forced
bridge/routing path), define multi-group combination semantics and
create/update/detach/rule-update ordering, and make deletion fail closed while
references remain. Those semantics are intentionally outside the current state
model and AAP action contract. [PRD: FR-3, FR-5, FR-6] [User]

#### ExternalIP, DNAT, and SNAT

> **Baseline distinction.** The service reservation state machine and
> versioned-result/annotation compatibility below retain the earlier proposal.
> They are not part of #2170's task protocol. Current AgentlessNet allocation
> returns `osac_result.external_ip.address`; attachment tasks use the saved
> `external_ip`/`destination` snapshots and emit no typed result. This does not
> replace the independent NATGateway lifecycle described here. [IC-4, IC-5]

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

NATGateway creates one source translation for its VirtualNetwork CIDR, using
explicit `SNAT --to-source <ExternalIP.status.address>`
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

> **Baseline distinction.** The role layout below is the earlier proposed layout, not an inventory of shipped task files. The reviewed implementation uses the generic network-task playbook and existing task names listed in Current AgentlessNet behavior. It adds no move task, per-task version keys, legacy annotation fallback, or versioned attach-result envelope. [IC-2, IC-3, IC-4]

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

> **Baseline distinction.** The migration/DAO/provider-event work below remains an unimplemented coordination proposal, not a prerequisite introduced by #2170. Provider allocation and consumer ownership in AgentlessNet SQLite must not be confused with this proposed fulfillment-service reservation table. [IC-4]

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

> **Baseline distinction.** The table below includes the historical service
> event, binding and transit-pool proposal. Current tasks publish sanitized
> `osac_error: {message, retryable}` through `_report_task_error.yaml` and retain
> API-ID-owned provider state for cleanup. Its provider events, `/30` pool and
> proposed diagnostic names must not be read as implemented recovery APIs.

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

**Question:** The shared task protocol now defines
`osac_result.dhcp_lease`, and the NetworkAttachment controller accepts it into
`status.dhcpLease`. The baseline BMF discovery path still parses its legacy
`leases` artifact and writes `Status.NetworkAttachmentStatuses`. What
service-integration evidence establishes the handoff between those paths and
fulfillment feedback? The shared typed schema is no longer an open choice;
completed BMaaS propagation and future CaaS/VMaaS integration remain unproven
by the provider fixtures.

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
- Verify Subnet add and delete leave the NATGateway row and SNAT rule unchanged.
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
- Exercise Subnet churn while NATGateway is Ready: verify the SNAT rule is
  unchanged.
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
(`PRAGMA user_version=1`). The reviewed application requires the exact table
layout and `network-manager-api-id-v1` marker; it does not add missing tables
or automatically migrate Kubernetes-UID-owned databases. Incompatible layouts
and corruption fail closed. Before deploying,
operators retain a backup of the SQLite database, network inventory, and BGP
configuration. There is no downgrade path or in-place OSAC rollback guarantee
across incompatible provider-state layouts.

The earlier proposed fulfillment-service migration below is not implemented
by this task adoption and is not an operator upgrade instruction. That
proposal creates one reservation row for every
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

> **Baseline distinction.** This checklist describes compatibility with
> osac#2170 at `54272aa80e6a56ff1d77b2ee8cf4749267f98cbe`, under review and
> not necessarily released. It does not establish a supported rolling-upgrade
> or migration path. Historical versioned artifacts, capabilities and events
> elsewhere in this proposal are not prerequisites supplied by this baseline.

For this AgentlessNet implementation, verify alignment on:

- immutable Fabric Manager registration with `name: agentless_net` and
  `ansible_role: osac.templates.agentless_net`, selected through the
  NetworkClass; there is no `ipv4` registration capability key;
- `playbook_osac_network_task.yml` dispatching the recorded manager role's
  task file with `osac_job_vars`, rather than provider-specific playbooks or
  extra launch variables;
- task input identity: manager name/type/role, task name, resource kind and
  API `resource.id`, Kubernetes `resource.metadata.uid` and `generation`
  context, tenant and task-specific parent/target snapshots. Provider ownership
  uses the API IDs, not the Kubernetes UID;
- SQLite `PRAGMA user_version=1`, the `network-manager-api-id-v1` state
  contract marker, and the exact validated table, index and foreign-key
  layout. Older v1 layouts are rejected, not additively migrated or adopted;
- database transactions and sidecar locks, resource operation locks,
  API-ID-owned reservations and delete tombstones; retries must not bypass
  retained claims or restore a deleted attachment;
- per-VirtualNetwork `/31` transit state and saved local FRR `/32` route/next-hop
  state for ExternalIPAttachment and NATGateway; these tasks do not configure
  BGP sessions;
- physical BareMetalInstance `apply_network_attachment` and
  `delete_network_attachment` inputs, inventory port mappings and provisioning
  VLAN, with `network_attachments` and `network_attachment_ports` claims;
- IPAM and dnsmasq configuration, saved MAC/address reservations and lease
  lookup against the reserved address. The DHCP result is
  `osac_result.dhcp_lease` with `ip_address` and `mac_address`; the operator
  validates the MAC and usable Subnet address before storing `status.dhcpLease`;
- ExternalIP create output `osac_result.external_ip.address`, validated
  against the pool CIDR; ExternalIPAttachment `destination.address` and
  `destination.routing_domain` for a tenant VirtualNetwork; whole-address
  DNAT and explicit-source NATGateway SNAT. Version keys, allocated-address
  annotations and private provider events are not this result contract.

Invalid generic job input fails with `osac_error.retryable: false`; a missing
role or task file is reported as retryable. Inspect those errors and the
recorded task input rather than assuming fallback to another manager or
compatibility with an older execution environment. These provider checks do
not redefine other managers' contracts or implement the proposed shared
reservation and capacity policies described elsewhere.

## Support Procedures

> **Baseline distinction.** These triage steps use evidence available in the
> same under-review baseline, not proof of deployed validation. Historical
> `leases` artifacts, provider events, annotations, `port_bindings` and `/30`
> layouts are not diagnostics supplied by this implementation.

Support personnel diagnose failures in this order:

1. Inspect the resource's conditions, `status.jobs` and `status.taskInput`.
   Correlate the task, recorded manager and API resource/parent/target IDs with
   the AAP job; keep Kubernetes UID/generation context distinct from provider
   ownership. Check the physical workload's handoff condition when DHCP query
   has not started; a successful apply alone does not establish a DHCP lease.
2. Confirm the NetworkClass selects the discovered immutable Fabric Manager
   ConfigMap with `name: agentless_net` and
   `ansible_role: osac.templates.agentless_net`. Check that the execution
   environment contains the requested role/task file and that the saved input
   passes its validation; do not look for an `ipv4` capability key.
3. Inspect AAP job status and sanitized `osac_error` message/retryability.
   For DHCP, compare `osac_result.dhcp_lease`, the requested MAC, saved
   reservation, dnsmasq lease file and `status.dhcpLease`. A missing or
   expired lease, or a lease at another address, does not satisfy the reserved
   MAC/address lookup. For ExternalIP creation, compare
   `osac_result.external_ip.address`, pool CIDR, `ExternalIP.status.address`
   and the provider allocation; no version key or annotation is required.
4. Check net-node reachability, provider inventory, namespace/interface state,
   and dnsmasq supervisor/configuration and lease paths. Inspect the validated
   API-ID-owned SQLite state: `virtual_networks`, `subnets`,
   `network_attachments`, `network_attachment_ports`, `external_ip_pools`,
   `external_ips`, `attachments` and `nat_gateways`, along with
   `deleted_resources` tombstones and the `state_metadata` contract marker.
   Compare Subnet VLAN/IPAM and attachment address/port claims with the saved
   task snapshots. For the VirtualNetwork transit, compare `cidr`,
   `namespace_ip`, `host_ip` and `gateway` in its saved `/31` payload, not a
   historical `/30` allocation.
5. Verify Cumulus VLAN/trunk/access-port state against the saved Subnet and
   physical attachment ports. During deletion, compare saved fabric ports
   with the validated inventory provisioning VLAN; inspect `deleting` state
   and retained address/port claims if cleanup failed. Do not manually release
   claims or infer detach behavior from a display name. Check the sibling
   Subnet VLAN independently of the attachment being removed.
6. For ExternalIPAttachment, inspect the saved tenant-network destination,
   local FRR `/32` route/next hop, whole-address DNAT and conntrack cleanup.
   For NATGateway, inspect its saved local FRR `/32` route/next hop, explicit
   `SNAT --to-source` and host bypass rules; host MASQUERADE must not overwrite
   that source. BGP session and advertisement verification requires separate
   deployment evidence: both consumer tasks install local routes, and task
   success alone does not establish upstream BGP reachability.
7. Preserve the database, inventory and job evidence before any recovery.
   Schema incompatibility or corruption fails closed; inspect the reported
   error and sidecar locks, not a presumed `StateCorrupt` provider event.
   There is no automatic repair or adoption of an older database layout.
   Do not rewrite tables or use the historical migration sketch as a repair
   procedure; stop reconciliation before any operator-led backup restoration.

To disable new use, remove or change the NetworkClass selection after draining
resources; do not delete the manager ConfigMap while resources still need
reconciliation. Existing workloads retain their applied fabric state until
explicit cleanup. Before re-enabling the manager, verify the exact API-ID
schema-v1 database contract and provider inventory against the selected code;
re-enabling is not a database migration or automatic repair mechanism.

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
