---
title: agentless-vlan-fabric-manager
authors:
  - yonibettan@gmail.com
creation-date: 2026-09-08
last-updated: 2026-10-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-3664
  - https://redhat.atlassian.net/browse/OSAC-4307
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking/design.md"
  - "/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/prd.md"
  - "/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md"
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
unique VLAN, provisions DHCP, BGP-backed external reachability, whole-address
DNAT, explicit-source SNAT, and required per-binding SecurityGroup policy
through Ansible roles. The current AgentlessNet packet path does not yet prove
that policy and remains a conformance blocker. Its manager registration follows
the shared
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).
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
VirtualNetwork and multiple VLAN-backed Subnets inside that namespace. The
selected Fabric Manager must enforce the shared SecurityGroup contract for
every assigned workload binding on same-Subnet, routed, and external paths.
The current permit-all forwarding and Layer 2 paths do not meet that contract;
per-binding enforcement is a release blocker until the AgentlessNet data path
and conformance tests prove it.
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
- Implement every Fabric Manager operation and target assigned to the
  Fabric-only IPv4 profile without adding public gRPC fields, REST resources,
  or CRDs. This includes contract-defined SecurityGroup operations.
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
- VM-to-fabric bridging and VM address assignment, which require a compatible
  K8s Manager in the Fabric-backed EVPN profile. AgentlessNet declares no
  `evpn-vxlan` capability.

## Proposal

The design adds the missing agentless implementation behind the existing
NetworkClass and dispatcher contracts. A provider registers an
'agentless_net' fabric-manager ConfigMap through Helm values and selects it in
the existing deployment configuration. The fulfillment-service owns API
validation, tenancy, ExternalIPPool capacity accounting, and exclusive
consumer reservations; the operator owns CRDs, finalizers, dependency checks,
and observed status. AgentlessNet owns provider-side pool registration and
selects and durably reserves each concrete ExternalIP address in its locked
state file, as well as
VirtualNetwork/Subnet realization, per-VirtualNetwork transit links, BGP `/32`
reachability, per-binding SecurityGroup policy, BMF port binding, DNAT, and
SNAT. It returns contract-defined `osac_result` artifacts after state-file
commits; OSAC owns API annotations and status. The
operator exposes a validated address as `ExternalIP.status.address`. [PRD:
FR-1, FR-2]

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

The provider installs a Cumulus-backed network node, AAP inventories, and
provider-scoped ExternalIPPool resources. Pool CIDRs remain API/controller
input and are not AgentlessNet state.

The target operator registration uses role Fabric, name agentless_net,
implementationRef osac.templates.agentless_net, contractVersion v1, and
capability ipv4. It does not advertise evpn-vxlan or list operations/targets,
so it is eligible only for the Fabric-only IPv4 profile. The collection must
be installed in the AAP execution environment. Do not publish this registration
as contract v1 or make it selectable until every assigned operation and target
passes contract conformance. The current SecurityGroup packet path is a known
blocker, so the current AgentlessNet implementation is not yet
contract-conformant.

The provider supplies Cumulus switches, network nodes, interfaces, external
interface, BGP peer, transit CIDR pool, VLAN-ID pool, and state-file location.
The deployment selects fabric_manager=agentless_net through its NetworkClass.
The generic Enclave installation flow discovers registered managers from OSAC
and displays them dynamically; it must not keep a product-specific list. This
feature adds no AgentlessNet-specific UI. Tenant users select the resulting
NetworkClass through the existing API.

A missing or invalid registration, unsupported profile, or NetworkClass naming
an undiscovered manager prevents dispatch and leaves a diagnostic condition.
OSAC never substitutes Netris or another default implementation.

#### Networking resource lifecycle

The Tenant Admin creates and deletes the tenant's Networking API resources:
VirtualNetwork, Subnet, ExternalIP, ExternalIPAttachment, and NATGateway. A
usable tenant network requires one VirtualNetwork with at least one Ready
Subnet before a machine can attach. SecurityGroup enforcement is a required
Fabric Manager operation, not deferred work. The selected manager applies the
contract policy to current bindings; the AgentlessNet packet path remains a
release blocker until it proves that behavior. Tenant Users consume these
resources through their workload workflows. [User]

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
   and contract-compliant SecurityGroup enforcement per VirtualNetwork, and one
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

BMaaS is the reference service path for physical workload attachment. CaaS
physical workers use the same operations through the BMaaS BaremetalInstance
path; a Cluster is not a target for physical port movement or DHCP lease
queries. ComputeInstance networking requires a Fabric-backed EVPN profile
with a compatible K8s Manager and is outside AgentlessNet's IPv4-only profile.

OSAC supplies the common `osac_job_vars` envelope and the normalized
BaremetalInstance resource. The AgentlessNet collection implements the
contract's fixed task entry points and consumes only the operation inputs in
`context`:

- `workload_attachment.move` uses `context.attachment`. OSAC provides the
  stable binding UID, `workloadKind: BaremetalInstance`, workload UID, host
  UID, interface, authoritative MAC, Subnet and VirtualNetwork UIDs and
  references, tenant ID, provider provisioning-network ID, and an exact
  `action` of `ATTACH` or `DETACH`. The role must not infer the action from
  `deletionTimestamp` or require an Agentless-specific field.
- On `ATTACH`, AgentlessNet moves the selected switch port from the configured
  provisioning VLAN to the VLAN for the referenced Subnet. It reports success
  only after the port and its stable binding record agree. BMaaS then reboots
  the host and waits for DHCP on the tenant network before marking handoff
  complete.
- On `DETACH`, AgentlessNet restores the provider provisioning network using
  the stable provider network ID even if the Subnet has already been removed.
  The operation is retry-safe and reports success only after restoration.
- A successful move returns `osac_result.data.attachment` with the input
  binding UID, state `ATTACHED` or `RESTORED`, and observed backend port
  identity. OSAC owns BaremetalInstance status and readiness.

Lease discovery is a separate `dhcp_lease.query` operation targeting
BaremetalInstance. The role receives `context.attachments` with one request
per binding: binding UID, Subnet UID and canonical SubnetRef, interface, and
authoritative MAC. It matches by the exact SubnetRef/interface/MAC tuple,
normalizing MAC case, and returns exactly one matching entry per requested
binding in `osac_result.data.leases` with `subnetRef`, `interface`,
`ipAddress`, and `macAddress`. Missing, stale, or ambiguous leases fail with a
diagnostic. A server or workload name is never a fallback lease key.

After the manager returns the lease result, BMaaS validates the matching
contract entry and writes the address to BaremetalInstance attachment status.
The feedback controller publishes that status through the existing
fulfillment-service path; ExternalIPAttachment waits for the primary address
before creating DNAT. AgentlessNet does not write OSAC status, add provider
result annotations, or use a private callback as a second result channel.
#### ExternalIP and inbound access

1. A Cloud Infrastructure Admin creates an ExternalIPPool containing IPv4
   ranges through the existing API. The fulfillment-service records the
   pool's capacity counters, and the agentless `create_external_ip_pool` AAP
   job registers the pool CIDRs in the locked AgentlessNet state file.
2. Creating the ExternalIPPool defines capacity; it does not allocate an
   address or create a traffic rule. When an ExternalIP is created, the
   fulfillment-service transaction locks the pool and creates the durable
   `external_ip_reservations` row keyed by the ExternalIP UUID. The row holds
   capacity in `HELD` state; this OSAC capacity hold does not select or record
   the concrete address and is not released merely because the provider job
   fails. The agentless `create_external_ip` AAP job reads the pool entry from
   the locked state file, reuses an existing allocation for the ExternalIP UID
   when retrying, or selects and persists the first available IPv4 address
   under the state-file lock.
   The role returns `osac_result.data.externalIP.address`. OSAC validates the
   UID, generation, canonical address, and pool membership, then updates its
   own annotation and `ExternalIP.status.address`. The task does not patch the
   API resource or send a provider event. Allocation alone still has no
   data-plane route or NAT rule.
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
   address, and then announces the exact ExternalIP `/32` through BGP with the
   namespace-side transit address as the next hop. The route is announced only
   after the namespace and DNAT rule are present. The selected Fabric Manager
   enforces the contract SecurityGroup policy on this path; unmatched traffic
   remains denied when a SecurityGroup applies. AgentlessNet cannot be declared
   conformant until its packet path proves this behavior.
6. The attachment remains Pending or Progressing until both the parent
   ExternalIP address and the target address are current, the whole-address
   DNAT rule is present, and the BGP `/32` is observed as installed. It reaches
   Ready only after those checks and status feedback confirm the operation. If
   allocation succeeds but DNAT or route advertisement fails, the
   ExternalIPAttachment remains non-ready; `status.attached` remains true
   because the consumer reservation still prevents a second user. The address
   remains reserved for retry or ordered cleanup. For a Cluster target,
   `targetEndpoint` selects the current API-server or
   ingress VIP, and the same all-protocol address translation is used rather
   than a port-specific rule. The target becomes reachable only for traffic
   allowed by its effective SecurityGroup rules. [PRD: FR-5] [Contract]

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
   node/interface address instead of the allocated ExternalIP. The role then
   announces the exact ExternalIP `/32` through BGP using the saved namespace-
   side transit address as next hop.
4. A Subnet add/update enqueues every NATGateway for its VirtualNetwork. The
   NATGateway reconciler adds the new source CIDR and verifies the new SNAT rule
   before the Subnet is reported `NetworkReady` when a NATGateway already
   exists. A Subnet delete first marks the Subnet pending deletion and enqueues
   NATGateway reconciliation; the NATGateway removes and verifies that CIDR's
   SNAT rule, persists the reduced `source_cidrs` set, and only then allows the
   Subnet controller to delete its VLAN, gateway, and DHCP state. If the
   VirtualNetwork has no Subnets, the NATGateway keeps its consumer reservation
   and route but has an empty source rule set and reports no egress sources.
5. The selected Fabric Manager enforces the contract SecurityGroup policy on
   the SNAT path. Only permitted flows reach translation; established return
   traffic follows conntrack back through the namespace to the original source.
   AgentlessNet cannot be declared conformant until this behavior is proven on
   both routed and same-Subnet paths.
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

The provider underlay contract is explicit. The provider inventory must have a
working FRR/BGP session and upstream route policy before `agentless_net` is
Ready; those peer/session settings are provider configuration, not tenant
inputs. The existing `agentless_net.l3.bgp` primitive does not establish the
upstream BGP session. It adds or removes the consumer-owned local FRR static
route `<external-ip>/32 via <namespace-transit-next-hop>`, which FRR then
advertises over the provider-owned session. Agentless owns that local route and
the consumer UID; the provider owns the BGP peer and upstream policy.

An attachment or NATGateway is Ready only after the local FRR route is present,
the provider route check confirms the `/32` is advertised/reachable upstream,
and the namespace translation is installed. Cleanup withdraws the exact local
route, verifies that upstream reachability is gone, and only then removes the
translation and permits ExternalIP cleanup. A failed or unavailable upstream
check leaves the consumer non-ready and retains its finalizer and reservation.
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
2. For an ExternalIPAttachment, withdraw its ExternalIP /32 route and wait
   until it is absent from net-node routing/BGP state. Remove the owned
   whole-address DNAT rule and owner-specific conntrack state. The task returns
   success only after route, translation, and conntrack state are absent.
3. For a NATGateway, withdraw and verify its ExternalIP /32 route, remove the
   explicit-source SNAT rules, and remove owner-specific conntrack state. The
   task returns success only after all owned state is absent.
4. OSAC enforces the ExternalIP consumer dependency: the parent cannot be
   released while either consumer exists. After consumer deletion succeeds,
   OSAC dispatches external_ip.release. AgentlessNet removes the UID-owned
   address and returns releaseState RELEASED only after confirming absence.
   OSAC validates the common result, updates capacity once, and removes the
   ExternalIP finalizer. If allocation never committed, release succeeds
   idempotently when no UID-owned address exists.
5. For a Subnet, remove its DHCP state, VLAN subinterface, gateway address,
   and Subnet-owned switch/VLAN state. Release its VLAN after dependent
   bindings and NATGateway source rules are gone.
6. For a VirtualNetwork, remove remaining child fabric state and its namespace
   after children are gone. Keep its transit /30 and veth pair until no
   ExternalIP consumer retains route or NAT state for that VirtualNetwork.
7. Remove a finalizer only after the manager task has reported cleanup through
   osac_result and OSAC has validated it.

The Cloud Infrastructure Admin owns provider-scoped manager and ExternalIPPool
resources. The Tenant Admin owns tenant VirtualNetwork, Subnet, ExternalIP,
ExternalIPAttachment, and NATGateway resources. AgentlessNet never creates or
deletes those API objects; it applies/removes provider state during
reconciliation. OSAC owns API reservations, capacity, finalizers, and observed
status. AgentlessNet owns its provider state. This feature creates no default
networking or policy resources.

### API Extensions

No new public gRPC service, REST resource, protobuf field, CRD kind, or webhook
is introduced. Existing fabric-facing resources use contract-v1 registration,
fixed AAP entry points, normalized job inputs, and osac_result. OSAC owns
resource status, annotations, and pool-capacity counters. The manager does not
patch API resources or add a provider-specific result channel.

| ID | Existing surface | Change | Requirements |
|---|---|---|---|
| IC-1 | Installer values, manager ConfigMap, NetworkClass selection | Register agentless_net with its implementation reference, contract v1, and IPv4 capability | FR-1, NFR-1 |
| IC-2 | VirtualNetwork and Subnet API/CR lifecycle | Route resources through the agentless dispatcher and realize VLAN, namespace, SecurityGroup policy, and cleanup state | FR-2, FR-3, FR-10, NFR-2, NFR-3 |
| IC-3 | Fabric network attachment and DHCP feedback | Implement workload_attachment.move and dhcp_lease.query for BaremetalInstance; CaaS physical workers use the same BMaaS path | FR-4, FR-8 |
| IC-4 | External access resource lifecycle | Preserve existing ExternalIP and consumer APIs; resolve tenant/cluster targets explicitly and configure DNAT/SNAT through the assigned contract tasks | FR-5, FR-6, FR-7, FR-10 |
| IC-5 | NATGateway lifecycle | Apply explicit outbound SNAT using ExternalIP.status.address and announce/withdraw its /32 route | FR-6, FR-10, NFR-2, NFR-3 |
| IC-6 | Resource status, conditions, events, and job history | Surface registration, provisioning, DHCP, switch, SecurityGroup, forwarding, BGP route, NAT, and cleanup failures | FR-9, NFR-2 |

#### Existing resource and metadata constraints

- Tenant-scoped resources retain 'osac.openshift.io/tenant' and
  'osac.openshift.io/owner-reference' annotations. No backend-created
  tenant object may omit them. [Codebase: fulfillment-service/internal/servers/private_subnets_server.go]
- NetworkClass, ExternalIPPool, and manager registration remain
  provider-scoped according to the existing API and OPA policy.
- No API-level field is added for VLAN ID, Linux namespace, DHCP server, switch
  platform, or AAP job ID. Those are implementation state and status metadata,
  not tenant API inputs.

#### ExternalIP reservation and manager results

The fulfillment-service remains authoritative for ExternalIPPool capacity,
tenant allocation status, and the exclusive consumer reservation shared by
ExternalIPAttachment and NATGateway. A durable reservation keyed by ExternalIP
UID may serialize allocation retries and update capacity counters exactly
once. It is OSAC-owned state; a manager does not write it or call a private
OSAC callback.

For `external_ip.allocate`, AgentlessNet reserves an address in its locked
provider state keyed by the ExternalIP UID and returns the common `osac_result`
with `data.externalIP.address`. OSAC validates the operation, resource UID,
observed generation, canonical IPv4 address, and membership in the selected
ExternalIPPool before it updates ExternalIP status and the OSAC-owned
allocated-address annotation. A retry for the same UID returns the same
reservation. A missing, malformed, stale, or out-of-pool result leaves the
resource non-ready and the capacity reservation held for retry or cleanup.

For `external_ip.release`, AgentlessNet removes the UID-owned address
reservation and returns `data.externalIP.releaseState: RELEASED` only after
that address is absent from provider state. OSAC validates the result before
releasing pool capacity once. Repeating release for an absent provider entry
succeeds idempotently.

ExternalIPAttachment and NATGateway use the existing exclusive consumer
reservation. Their create operations return success only after the owned DNAT
or SNAT state and required BGP route are observed. Their delete operations
return success only after the owned translation and route are absent. OSAC
releases the consumer reservation after validated task success; the parent
ExternalIP cannot be released while either consumer remains. Successful tasks
use the common `osac_result` envelope and do not patch provider-result
annotations, send provider events, or invoke private callbacks. The exact task
inputs, results, cleanup gates, and retry requirements are defined by the
[Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

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
  conditions:
  - type: Ready
    status: "True"
~~~

`spec.region` identifies the deployment region, `spec.ipv4Cidr` is the
VirtualNetwork supernet, and `spec.networkClass` selects the existing
NetworkClass whose fabric manager is `agentless_net`. `status.phase` and
`status.conditions` expose reconciliation and failure state. Provider identifiers remain in manager-owned state; managers do not write OSAC status.

AgentlessNet maps the VirtualNetwork UID to one deterministic Linux routing
namespace and creates its uplink/external boundary. The desired state includes
contract-compliant SecurityGroup enforcement for attached bindings. The current
`filter/FORWARD` forwarding path and same-Subnet Layer 2 switching do not prove
per-binding policy and must not be treated as the target. Local DHCP traffic
terminates in the namespace and is not routed through this baseline.
AgentlessNet records the mapping in the locked state file; it does not create
tenant child resources or install private routes to another VirtualNetwork.
[User]

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
  conditions:
  - type: NetworkReady
    status: "True"
~~~

`spec.virtualNetwork` references the parent routing domain and
`spec.ipv4Cidr` supplies the client-selected, non-overlapping subnet CIDR.
OSAC-owned status.phase and status.conditions report observed provisioning; the VLAN ID is deliberately not a tenant API field. Provider IDs remain in the manager's UID-keyed state.

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
reservation. AgentlessNet selects and persists the concrete address in its
provider state file, then returns `osac_result.data.externalIP.address`.
OSAC validates that result and writes `status.address` and the
`osac.openshift.io/allocated-address` annotation. Allocation alone creates no
traffic rule; the address is consumed later by an ExternalIPAttachment or a
NATGateway, subject to the OSAC-owned consumer reservation.

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
match, and announces the consumer-owned ExternalIP `/32` through BGP using the
VirtualNetwork transit next hop. SecurityGroup policy is enforced per workload binding according to the shared
contract; a permissive forwarding rule is not sufficient.

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

The AgentlessNet ConfigMap uses the Fabric Manager role label, data.name
agentless_net, implementationRef osac.templates.agentless_net, contractVersion
v1, and the `ipv4` capability. Manager registration does not list operations.
The Fabric-only IPv4 profile assigns AgentlessNet the complete Fabric
operation and target set, including SecurityGroup policy and workload
attachment/DHCP operations for BaremetalInstance. CaaS physical workers use
the same BaremetalInstance path through BMaaS; Cluster is not a port-move or
lease-query target. AgentlessNet declares no `evpn-vxlan` capability and
cannot be paired with a K8s Manager for that profile.

The current permit-all and Layer 2 paths do not implement SecurityGroup
policy. AgentlessNet is not contract-v1 conformant and cannot be selected as a
conforming Fabric Manager until every assigned task and target passes the
contract conformance suite. OSAC rejects profile-incompatible work before AAP
and never substitutes another manager. [Contract]

The shared contract defines the ConfigMap schema, complete role operation and
target matrix, task inputs and outputs, SecurityGroup behavior, and
registration validation. This design defines AgentlessNet's backend mapping
and records any implementation gap; it does not redefine the manager
interface. [Codebase: osac-operator/pkg/networkmanager; osac-operator/charts/operator/templates/network-managers.yaml]

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
    dhcp:
      daemon: dnsmasq
      service_unit: agentless-dhcp@<virtual-network-uid>.service
      config_path: /etc/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.conf
      lease_path: /var/lib/agentless-net/dhcp/<virtual-network-uid>/dnsmasq.leases
      lease_duration_seconds: <integer>
    default_forward_policy: deny
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
    source_cidrs_revision: <subnet-state-generation>
    route_prefix: <external-ip>/32
    route_next_hop: <namespace-transit-ip>
    route_protocol: bgp
    route_announced: true
    snat:
      mode: explicit
      to_source: <external-ip>
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

The `virtual_networks.transit` entry is allocated from the provider-configured
transit pool once per VirtualNetwork. `namespace_ip` is the next hop passed to
the BGP route action; `host_ip` is the peer on the net node; `gateway` is the
default route used inside the namespace; and `external_interface` is the
provider-facing net-node interface used for egress. The
`external_reachability` mode is `bgp` for this milestone: each active
ExternalIP consumer owns one `<address>/32` announcement, and no L2/ARP
reachability alternative is claimed.

The fulfillment-service allocation and consumer state is separate from this
provider state file. OSAC owns API capacity and the exclusive consumer
reservation; the external_ips provider entry owns only the concrete address
reservation. They are correlated by ExternalIP UID and, after allocation, the
canonical address. The manager does not write OSAC state or send a callback.

The `external_ip_pools` entries register provider-side pool CIDRs and the
`external_ips` entries record concrete addresses allocated from those pools.
The AAP roles allocate under the state-file lock and reuse an existing
ExternalIP UID entry on retry. The `attachments` and `nat_gateways` entries
identify the API resource whose route and DNAT/SNAT rules are owned by the
backend. Their saved route prefix, next hop, protocol, and address are the
inputs for idempotent repair and deletion; cleanup must not derive them from a
current name or a newly allocated transit link. `target_endpoint` records the
cluster API-versus-ingress choice, while `source_cidrs` is reconciled whenever
the VirtualNetwork's Subnet set changes. `source_cidrs_revision` records the
Subnet snapshot that the SNAT rule set covers. `port_bindings` records both sides of
the access-port transition: the resolved tenant VLAN and the stable provider
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
cluster-purpose strings. State writes are atomic, locked, and idempotent. A
state schema version permits an additive migration if the backend state format
changes. The write protocol is:

1. Derive a stable sidecar lock path, for example
   `<state-path>.lock`, and open it with `O_CREAT` before every read or write.
   Acquire an exclusive `flock` on this sidecar; never lock the data-file inode,
   because atomic rename replaces that inode and would allow concurrent writers.
2. Under the sidecar lock, read and strictly validate the current JSON schema,
   including duplicate UID/VLAN/address checks and all cross-references. A
   missing file is initialized only during first installation when no backup
   exists; a missing file after a generation was committed is corruption. A
   malformed or unknown-version state fails closed: no allocation, release,
   route change, or successful AAP result is allowed.
3. Serialize the complete next state to a uniquely named temporary file in the
   same directory and filesystem, set its restrictive mode, flush it, and call
   `fsync` on the temporary file.
4. Before replacing the current state, write the validated current bytes to a
   same-filesystem `<state-path>.bak` temporary file, `fsync` it, atomically
   rename it to the backup path, and `fsync` the parent directory.
5. Atomically rename the new temporary state over the data path and `fsync` the
   parent directory before releasing the sidecar lock. Stale temporary files
   are never treated as state.

This ordering guarantees that a crash at any byte of a write leaves either the
previous complete state or the next complete state; it cannot expose partial
JSON. The backup is the last-known-good generation. If the current file is
malformed or missing, the role reports `StateCorrupt` and stops. An operator
recovery action validates the backup and restores it through the same locked
temporary-file/rename protocol; recovery never silently overwrites malformed
state. The existing low-level IPAM allocation tasks that use `r+`, `seek`,
`write`, `truncate`, and `fsync` on the data file are not reusable unchanged;
they must be converted to this shared transaction helper before participating
in the unified state file. [Codebase: osac-aap/collections/ansible_collections/agentless_net/ipam]

##### Contract operations and AgentlessNet state transitions

AgentlessNet targets the Fabric-only IPv4 profile. It implements every Fabric
operation and target assigned by contract v1; registrations cannot advertise an
operation subset. Its fixed entry points are virtual_network.create/delete,
subnet.create/delete, security_group.apply/delete,
external_ip_pool.create/delete, external_ip.allocate/release,
external_ip_attachment.create/delete, nat_gateway.create/delete,
workload_attachment.move, and dhcp_lease.query. SecurityGroup and
ExternalIPAttachment include the contract's cluster and baremetal_instance
targets. Workload movement and DHCP lease lookup target baremetal_instance
only. CaaS physical workers use that same BaremetalInstance path through BMaaS.
AgentlessNet does not claim the Fabric-backed EVPN profile.

The state file is an implementation detail for idempotency and recovery. Its
UID-keyed records do not extend the manager contract, and ordinary operations
do not return provider identifiers. Every successful task returns the common
osac_result; only contract-defined operations return data:

| Contract operation | AgentlessNet action | Successful result |
|---|---|---|
| virtual_network.create/delete | Create/remove one namespace and transit link after child resources are ready/gone | Empty data object |
| subnet.create/delete | Create/remove VLAN interface, gateway, DHCP range, and lease mapping | Empty data object |
| security_group.apply/delete | Reconcile a complete binding snapshot; remove only policy owned by the deleted group | Empty data object |
| external_ip_pool.create/delete | Register/remove pool CIDRs; OSAC owns API capacity | Empty data object |
| external_ip.allocate | Persist/reuse one canonical IPv4 address keyed by ExternalIP UID | data.externalIP.address |
| external_ip.release | Remove the UID entry; absent entries succeed idempotently | data.externalIP.releaseState RELEASED after absence |
| external_ip_attachment.create/delete | Install/remove owner-keyed DNAT and /32 route after target resolution | Empty data object |
| nat_gateway.create/delete | Install/remove explicit-source SNAT rules and owner-keyed /32 route | Empty data object |
| workload_attachment.move | Move to Subnet on attach or restore saved provisioning VLAN on detach | data.attachment with binding UID, ATTACHED/RESTORED, and observed port identity |
| dhcp_lease.query | Resolve one lease for every requested attachment | data.leases, exactly one entry per request |

Create/apply tasks persist enough UID-keyed backend state to make retries
idempotent. Delete tasks confirm owned state is absent before returning success.
OSAC validates operation, resource UID, generation, and result shape; it owns API
status, annotations, job history, and capacity accounting. The complete
envelope, field schemas, target matrix, and readiness/deletion ordering are
normative in the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

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
AgentlessNet dhcp_lease.query task reads it after validating the current state
generation, then returns a lease only when exactly one unexpired entry matches
the requested Subnet reference, logical interface, and authoritative MAC.
MAC comparison is case-insensitive after normalization. It confirms the IP is
inside the requested Subnet CIDR and is not reserved. Zero, duplicate, expired,
stale, MAC-mismatched, and cross-Subnet matches fail with a diagnostic; the
manager does not guess from a host or server name.

For each request in context.attachments, return one osac_result.data.leases
entry with exactly subnetRef, interface, ipAddress, and macAddress. The Subnet
reference is canonical namespace/name. No partial or extra results are
returned. OSAC correlates the tuple to the binding and writes accepted
addresses to workload status. A missing lease causes retry and a diagnostic;
it does not create DNAT with an empty target. The normalized inputs and exact
result schema are defined in the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

#### SecurityGroup policy

AgentlessNet implements `security_group.apply` and `security_group.delete`
as assigned by contract v1. On each apply, it consumes the complete current
`context.securityGroup.attachments` snapshot, applies policy only to those
bindings, removes policy for bindings omitted by a later snapshot, and
converges updates without leaving stale rules. It must implement the shared
default-deny and stateful-return behavior, preserve rule input order, union
allow rules across groups attached to the same binding, and keep different
bindings' groups isolated.

The policy must cover same-Subnet Layer 2 traffic, routed traffic, and flows
through DNAT and SNAT. The current Linux `filter/FORWARD` forwarding path
does not observe same-Subnet packets, and the current design has no proven
per-binding Cumulus mechanism. Selecting an access-port ACL or forcing traffic
through a routing path are candidate mechanisms only; neither is a conformance
claim until tests prove all assigned targets and packet paths. This remains a
release blocker. On attach, policy must succeed before the attachment becomes
Ready; on detach, the workload leaves the network before the next binding
snapshot removes its policy. The exact semantics and ordering are normative in
the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

#### ExternalIP, DNAT, and SNAT

AgentlessNet maps the contract operations to its provider state file and
network namespace:

- `external_ip_pool.create/delete` registers or removes the provider pool
  CIDRs under the state-file lock. Fulfillment-service owns pool capacity and
  allocation counters.
- `external_ip.allocate` reserves one IPv4 address by ExternalIP UID and
  returns it in `osac_result.data.externalIP.address`. A retry for the same UID
  returns the existing address.
- `external_ip.release` removes the UID-owned provider reservation and returns
  `osac_result.data.externalIP.releaseState: RELEASED` only after it is absent.
- `external_ip_attachment.create/delete` installs or removes the owned
  whole-address DNAT rule and the consumer-owned BGP `/32` route for the
  resolved target in `context.target`. It reports success only after the
  requested provider state is observed.
- `nat_gateway.create/delete` installs or removes explicit-source SNAT rules
  for the current Subnet CIDRs and the ExternalIP route. It reports success
  only after the requested provider state is observed. The host must not apply
  a second MASQUERADE on this path.

OSAC validates the common `osac_result` envelope, owns resource status and
annotations, and releases ExternalIP consumer/capacity reservations only after
the corresponding contract task succeeds. No provider event, private callback,
or provider-result annotation is part of the manager interface. The selected
Fabric Manager also enforces SecurityGroup policy on these ingress and egress
paths; translation does not bypass the shared policy. Conformance remains
blocked until AgentlessNet proves per-binding policy behavior for DNAT, SNAT,
routed traffic, and same-Subnet traffic.

#### AAP role layout

The manager registration is a ConfigMap labeled
osac.openshift.io/network-fabric-manager: "true". It declares logical name
agentless_net, implementationRef osac.templates.agentless_net, contractVersion
v1, and technical capability ipv4. It does not declare operations or targets.
The reference resolves to a collection role installed in the AAP execution
environment.

The collection supplies the fixed contract-v1 Fabric task entry points listed
above. Each task consumes the common osac_job_vars envelope and normalized
operation inputs. The move role uses context.attachment.action exactly as
ATTACH or DETACH; it restores the provider provisioning VLAN on detach even if
the tenant Subnet was deleted. The DHCP role matches every requested binding by
SubnetRef, interface, and authoritative MAC. Successful output uses
osac_result. Allocation, release, attachment movement, and DHCP lease lookup
return only operation-specific data defined by the contract. Other operations
return an empty data object.

The collection includes shared step roles for VLAN/IPAM, routing namespaces,
dnsmasq, per-binding SecurityGroup policy, BGP /32 announce/withdraw,
whole-address DNAT, explicit-source SNAT, and Cumulus port configuration. All
state-changing roles use the sidecar-lock/temp-file/rename transaction above.
Existing low-level IPAM tasks that write shared state in place cannot be reused.

Do not advertise the registration as conformant until every assigned operation
and target works, including SecurityGroup enforcement for same-Subnet, routed,
DNAT, and SNAT paths. Current permissive forwarding and Layer 2 behavior do
not meet that requirement. No manager-specific status annotation, callback,
or result channel is added.

The existing agentless_net.steps collection remains reusable where its inputs
and lifecycle match the unified resource contract. Cluster-specific static
NMStateConfig and BGP endpoint code is not the generic Networking API
implementation. [Codebase: osac-aap/collections/ansible_collections/agentless_net]

#### Fulfillment-service coordination

The fulfillment-service remains the OSAC API and capacity authority. It
validates tenant resources, records the ExternalIP consumer reservation, and
owns pool counters. The selected manager only implements assigned AAP tasks
and owns provider state.

For ExternalIP creation, OSAC holds capacity while it dispatches
external_ip.allocate. After validating osac_result.data.externalIP.address,
OSAC writes its allocated-address annotation and status. For deletion, OSAC
enforces consumer cleanup dependencies, dispatches external_ip.release,
validates releaseState RELEASED, then updates capacity once. ExternalIPAttachment
and NATGateway use the existing exclusive consumer reservation; OSAC clears it
only after their validated delete task succeeds. The manager does not call
fulfillment-service directly and does not exchange private events, operation
digests, or annotations.

Subnet validation remains authoritative in fulfillment-service. It must accept
multiple non-overlapping Subnets inside one VirtualNetwork so the backend's
multi-VLAN behavior is usable. Remove any one-Subnet guard as part of that API
implementation; it is not delegated to the manager. [PRD: C1]

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

The target permits routed and same-Subnet traffic only as allowed by the
effective SecurityGroup policy for each binding, including flows through DNAT
and SNAT. The current AgentlessNet forwarding and switching paths permit
traffic without that policy and therefore fail the contract. This is a
release-blocking implementation gap; topology isolation and API authorization
do not replace workload-level SecurityGroup enforcement.

### Failure Handling and Recovery

| Failure | Recovery | Observable result |
|---|---|---|
| Manager registration is missing, invalid, or incompatible with the selected profile | Stop before AAP side effects and retry after correction | OSAC condition identifies the manager, profile, or invalid field |
| Resource lookup has the wrong namespace or tenant attribution | Stop before mutation; retry by stable UID with server-set attribution | Diagnostic condition names the mismatch |
| NetworkClass, address family, or Subnet prefix is invalid | Reject before AAP dispatch | API error or failed condition; no fabric state is created |
| State lock is unavailable or state JSON is malformed | Retry lock contention; fail closed on corrupt state and require explicit recovery | Resource remains non-ready with lock or StateCorrupt diagnostic |
| VLAN or transit allocation fails | Keep UID-owned state and retry without reusing another resource's allocation | Allocation condition and AAP job identify conflict or exhaustion |
| ExternalIP allocation result is missing, stale, malformed, or outside its pool | Reject osac_result and retain capacity while retrying | ExternalIP remains non-ready with a result diagnostic |
| ExternalIP allocation or release is interrupted | Retry the same UID task; release succeeds only when its UID entry is absent | Capacity stays held until OSAC validates the result |
| Consumer cleanup task fails or its result is not recorded | Retry UID-keyed deletion and retain the consumer reservation | Consumer remains deleting/non-ready until OSAC validates success |
| Cumulus port move or restoration fails | Retry with the same binding UID and saved provisioning VLAN; retain the finalizer | Attachment condition identifies switch failure; port state is not forgotten |
| DHCP lease is missing, stale, or ambiguous | Requery exact SubnetRef/interface/MAC; do not invent an address | Lease condition identifies the failed match |
| SecurityGroup or NAT rule application fails | Retry without reporting Ready; preserve binding, route, and translation inputs | Policy or NAT condition and job history identify the failure |
| Route/translation cleanup is incomplete | Retain consumer and parent finalizers; retry until owned state is absent | Cleanup condition remains visible; capacity is not released |
| Delete is interrupted or the net node restarts | Re-enter ordered cleanup or restore validated state before reporting Ready | Resource remains non-ready/deleting with the failed phase |

All create/delete/attach/detach operations use stable resource or binding UIDs
and desired generations. Retries are safe after controller restart or a lost
job response. [Codebase: osac-operator/pkg/provisioning/provision_lifecycle.go]

#### Net-node availability and restore contract

This milestone has one authoritative net node and no automatic standby. A
net-node preflight checks reachability, state-file validation, namespace
inventory, dnsmasq services, and the provider BGP session before a fabric
mutation is accepted. When the node is unavailable, the operator reports
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

Recovery acquires the sidecar state lock, validates the current generation or
explicitly restores the last-known-good backup, then recreates namespaces,
veths, VLAN interfaces, gateways, forwarding, dnsmasq from preserved lease
files, and owned DNAT/SNAT rules. It restores BGP `/32` routes only after the
corresponding namespace path and translations are verified. Conntrack state is
not persisted; old connections must reconnect, while new connections are
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

Existing controller reconciliation, AAP job history, and resource conditions
remain the primary health signals. Diagnostics identify the operation, manager,
resource UID, generation, and failed contract field without exposing
credentials or tenant secrets.

Relevant conditions include NetworkManagerUnavailable,
FabricOperationFailed, NetNodeUnavailable, NetNodeRestoreFailed,
ExternalIPReservationBlocked, ExternalIPResultRejected,
ExternalIPCapacityReleaseBlocked, DHCPLeaseUnavailable,
SecurityGroupPolicyFailed, ExternalRouteApplyFailed,
ExternalRouteWithdrawBlocked, NATSourceAddressMismatch, and
FabricCleanupBlocked. ExternalIPResultRejected means OSAC rejected a missing,
malformed, stale, or out-of-pool osac_result; it does not refer to a
provider-specific annotation or callback.

The current AgentlessNet packet path remains non-conformant until SecurityGroup
policy is proven for every assigned target and packet path. Logs may include
resource UID, tenant attribution permitted by existing logging policy, manager,
desired generation, AAP job ID, route prefix/next hop, interface identity,
reservation state, and operation result. Logs must not contain credentials or
full secret contents.

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

A restart or failover can lose namespace, DHCP, conntrack, NAT, veth, or BGP
route state. Rehydration first acquires the stable sidecar lock and validates
the current state or last-known-good `.bak`; malformed state blocks every
mutation and release. It then reconciles the saved transit link, `/32` route
ownership, and translation rules before reporting a consumer Ready. This
milestone supports one authoritative net node and does not claim multi-node
state replication or automatic failover. Recovery requires the state backup,
network inventory, BGP peer configuration, and an explicit restore action when
the current generation is corrupt.

#### External route and source-address correctness

An announced `/32` with the wrong next hop can blackhole inbound traffic, and a
leftover MASQUERADE rule can make outbound traffic expose the node address
instead of the tenant's ExternalIP. The design allocates one transit `/30` per
VirtualNetwork, persists the namespace/host addresses and consumer-owned route
identity, applies DNAT or explicit SNAT before announcing the route, verifies
the installed route and observed source address, and withdraws the route before
removing translation state or releasing the ExternalIP.

#### ExternalIP reservation and release correctness

OSAC and the manager state file can observe the same ExternalIP at different
times. Releasing capacity before the manager confirms removal could allow an
address to be reused while a route is active. OSAC holds capacity until all
consumer delete tasks succeed and external_ip.release confirms that the
UID-owned address is absent. UID-keyed state and idempotent tasks make retries
safe; OSAC alone updates API status and pool counters.

#### Backend parity

Differences from Netris can change tenant-observable behavior even when API
responses match. A capability-by-capability parity matrix and BMaaS reference
validation compare L2, routing, DHCP, SecurityGroup, DNAT, SNAT, status, and
cleanup behavior. AgentlessNet is not contract-conformant until SecurityGroup
behavior passes the per-binding conformance checks. [Locked: C2]
[PRD: FR-2, FR-11, NFR-2]

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

#### 1. Cumulus per-binding SecurityGroup enforcement

**Owner:** Connectivity & Fabric team

**Question:** Which Cumulus and Linux enforcement points can apply SecurityGroup
policy per workload binding across same-Subnet, routed, DNAT, and SNAT paths
while preserving stateful return traffic?

This implementation choice blocks conformance and manager registration until a
candidate passes the [Agentless VLAN testplan](testplan.md).

#### 2. Cumulus NetworkRunner transaction

**Owner:** Connectivity & Fabric team

**Question:** Which switch transaction and lock scope implement the supported
Cumulus reset-plus-set operation for attach and detach, including rollback
after partial failure?

Each operation must be idempotent, preserve the saved provisioning VLAN, and
leave the switch in a known state after a failed retry. Contract v1 already
defines the operation, inputs, and result schema.

## Test Plan

The requirement-anchored procedures live in the [Agentless VLAN testplan](testplan.md).
They validate the Fabric-only operation/target matrix, normalized attach and
DHCP inputs, exact osac_result outputs, ordered cleanup, and retry behavior.

The release-blocking conformance cases prove SecurityGroup behavior per binding
for same-Subnet, routed, DNAT, and SNAT traffic. They include different groups
on endpoints sharing a Subnet, multiple groups on one binding, complete binding
snapshots, binding add/remove, rule updates, default deny, permitted flows, and
stateful return. Current permissive forwarding and Layer 2 paths are expected
to fail until a conforming packet path is implemented.

## Graduation Criteria

The target milestone is the IPv4-only agentless VLAN milestone described by the
PRD. Graduation to a broader support stage requires:

- all PRD acceptance criteria pass for the Cumulus reference environment;
- every assigned contract-v1 operation and target passes, including per-binding
  SecurityGroup enforcement on same-Subnet, routed, DNAT, and SNAT traffic;
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

This enhancement adds a backend implementation and contract-v1 registration;
it does not change tenant-facing APIs or CRD versions. Existing Netris
deployments remain selected by their NetworkClass and are not migrated
automatically.

The AgentlessNet state file is versioned. The new schema adds the
per-VirtualNetwork transit link and consumer-owned external-route fields.
Upgrade migrates state additively before reconciliation, preserving VLAN,
namespace, transit, DHCP, UID-keyed ExternalIP, BGP route, DNAT, and SNAT
mappings. It refuses destructive migration if the file cannot be parsed or a
required route next hop is missing. Operators retain backups of state,
inventory, and BGP configuration.

Before contract-v1 ExternalIP dispatch is enabled, OSAC allocations and consumer
ownership must be matched to UID-owned manager state. Unresolved allocations
remain non-ready and unavailable for reuse until an operator resolves the
mismatch. Existing consumer dependencies must be represented in OSAC before
address release is enabled.

To disable the backend, select another NetworkClass only after AgentlessNet
resources are drained or intentionally retained. Disabling a manager does not
delete tenant resources or silently release allocations. Downgrade requires
the deployed role and state schema to understand the previous version;
otherwise manual state export and restore is required.

## Version Skew Strategy

The operator, fulfillment-service, installer, and AAP collections must agree on:

- manager role, logical name agentless_net, implementationRef, contractVersion
  v1, and technical capability ipv4;
- configured OSAC_NETWORKING_NAMESPACE hub namespace;
- the fixed Fabric-only IPv4 operation and target matrix, with no per-manager
  operation subset;
- common osac_job_vars envelope, fixed task entry points, and normalized inputs;
- osac_result envelope and exact operation-specific result schemas;
- state-file schema and locked atomic-write/recovery protocol;
- per-VirtualNetwork transit-link fields and BGP /32 prefix/next-hop behavior;
- BaremetalInstance binding fields, ATTACH/DETACH semantics, and saved
  provisioning-network identity;
- dnsmasq lifecycle and exact SubnetRef/interface/MAC lease matching;
- whole-address DNAT, explicit-source SNAT, and per-binding SecurityGroup
  enforcement on all packet paths;
- ExternalIP release ordering: consumers are deleted first, manager confirms
  address removal, and OSAC alone updates API status and capacity.

If the operator cannot discover or validate registration, or the AAP role
cannot accept contract inputs, resources remain non-ready with diagnostics.
Dispatch never silently falls back to Netris. Components that do not understand
contract v1 cannot provision new resources during a rolling deployment.

## Support Procedures

1. Inspect OSAC resource conditions and provisioning job history.
2. Confirm the NetworkClass selects the discovered agentless_net Fabric Manager
   and its contract-v1 registration declares ipv4.
3. Check net-node reachability, state validation, namespace inventory, dnsmasq,
   SecurityGroup policy, and BGP session health before inspecting AAP jobs.
4. Inspect AAP job status and validated osac_result artifacts, lease results,
   OSAC ExternalIP status, dnsmasq configuration/lease paths, and role logs.
5. Check the lock-protected state file for resource UID, VLAN, gateway/DHCP,
   namespace, transit /30, veth addresses, UID-owned ExternalIP allocation,
   saved BGP /32 prefix/next hop, SecurityGroup binding policy, and owned
   NAT/DNAT rules. Compare ExternalIP.status.address with the OSAC-owned
   allocated-address annotation. Confirm OSAC consumer reservation and pool
   state before diagnosing capacity.
6. Verify Cumulus VLAN/trunk/access-port state and net-node namespace,
   interfaces, route installation/withdrawal, DNAT/SNAT rules, and conntrack.
   Confirm no host-side MASQUERADE rule overwrites the NATGateway source.
   For BMaaS, compare binding UID, host/MAC, switch port, tenant VLAN,
   provisioning-network ID/VLAN, direction, and observed state. Never infer
   detach behavior from a display name.

To disable new use, change NetworkClass selection after draining resources;
do not delete the manager ConfigMap while resources need reconciliation.
Existing workloads retain applied state until explicit cleanup.

## Infrastructure Needed

A repeatable validation environment needs:

- a Cumulus switch or equivalent validated Cumulus test target;
- one or more network-node hosts with privileged namespace/VLAN/firewall access;
- a provider transit-CIDR pool, a configured BGP peer, and a way to verify
  `/32` route installation and withdrawal;
- AAP inventory and job templates for the generic networking playbooks;
- dnsmasq and a service supervisor on the net node, with per-VN configuration
  and IPv4 lease storage accessible to the agentless role;
- an ExternalIPPool and an external traffic endpoint for DNAT/SNAT assertions;
- existing OSAC kind/integration fixtures for service and controller tests.

No new repository is required. Test infrastructure changes should extend the
existing mono-repo and tests/e2e patterns.

---

## Provenance

Authored: revise @ design 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ e97b06357

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"e97b06357","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
