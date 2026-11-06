---
title: multi-fabric-east-west-networking
authors:
  - vromanso@redhat.com
creation-date: 2026-07-14
last-updated: 2026-10-02
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1382
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking"
---

# Multi-Fabric East-West Networking

## Summary

This design keeps FabricDomain as the lifecycle and isolation boundary for a set
of devices on an east-west fabric. Phase 1 is an administrator-operated Netris
implementation; its Server Cluster template moves from NetworkClass to a private
BareMetalInstanceType binding, while Phases 2 and 3 add workload-driven
bare-metal membership, additional fabric managers, and VM device attachment.
See [PRD](prd.md) for the product requirements; this revision records the
implementation boundary and the proposed follow-on architecture.

## Motivation

North-south IP networking and east-west accelerator fabrics are separate
provisioning planes. VirtualNetwork and Subnet provide IP connectivity. A
FabricDomain asks a fabric manager to establish a membership/isolation boundary
for a particular group of machines. A Server Cluster template also describes
the Netris networks and physical NICs to program; that layout depends on the
machine hardware.

The original Phase 1 proposal stored one Netris template ID on NetworkClass.
That class is selected by a VirtualNetwork and is reused by different hardware
types. It therefore cannot reliably choose a template for a group of hosts with
different NIC layouts. The in-flight implementation also exposed FabricDomain
to tenants before it could safely derive host identity or allocation. Phase 1
now makes the admin boundary explicit and resolves each exact Netris hostname
through administrator-maintained hardware inventory.

This is a staged implementation plan, not a claim that the original tenant
self-service scope in the PRD has shipped. Before tenant-facing workload
membership is implemented, the PRD and Jira tasks must be reconciled with this
design.

### Goals

- Keep VirtualNetwork responsible for north-south/IP connectivity and keep
  FabricDomain responsible for an east-west isolation boundary.
- Deliver a bounded Phase 1 without adding `instance_type` to FabricDomain or
  asking tenants to provide Netris identifiers.
- Select Netris templates from the hardware type of every requested host and
  reject a FabricDomain whose servers require incompatible templates.
- Pin the resolved backend inputs before creating a Netris resource so retries,
  resize, and delete use stable identity.
- Keep the future model capable of multiple fabric managers and overlapping
  membership across different fabric planes.
- Put future tenant membership intent on a workload/allocation request and
  materialize the resulting device membership in FabricDomain reconciliation.

### Non-Goals

- Phase 1 tenant self-service, automatic bare-metal allocation, or
  selector-based membership.
- Phase 1 InfiniBand, NVLink, NICo, NMX-C, or VM fabric attachment.
- Inferring a BareMetalInstanceType from a hostname, HostType selector, or an
  unallocated BareMetalInstance.
- Generating a Netris Server Cluster template from NIC roles.
- Treating a successful AAP job as proof of data-plane reachability or
  per-server link health.
- Committing a final Phase 2 workload API schema in this document. The field
  names below are illustrative design shapes that require API review.

## Proposal

FabricDomain remains a distinct resource because a fabric isolation boundary
has its own identity, backend object, reconciliation status, retry behavior,
and cleanup lifecycle. NetworkClass describes supported network policy and
capability. BareMetalInstanceType describes hardware and its backend-specific
fabric binding. A workload request describes which allocated devices should
join which domain.

### Workflow Description

#### The Phase 1 flow before the correction

The original proposed flow was:

```text
NetworkClass (capability + Netris Server Cluster template ID)
        ↓
VirtualNetwork (north-south network and Netris VPC)
        ↓
FabricDomain (Ethernet EW + exact server hostnames)
        ↓
fulfillment-service → osac-operator → AAP
        ↓
Netris Server Cluster (template maps NICs and creates V-Nets)
```

An operator created the NetworkClass and pre-created a Netris Server Cluster
template. A tenant or onboarding workflow created a VirtualNetwork, which
provisioned the Netris VPC. An administrator created a FabricDomain with
Netris-known hostnames and that one VirtualNetwork. The operator submitted the
server list, template ID, and VPC ID to AAP. Netris created a Server Cluster
inside the VPC using the template.

The Server Cluster template, rather than FabricDomain, selected the NICs and
the Netris V-Nets. A template could define East-West, North-South/storage, and
OOB networks together. Therefore a FabricDomain request did not mean that only
an EW NIC would be changed. Administrators had to inspect the template and its
effect on existing Subnet/attachment configuration.

NetworkClass does not need the Server Cluster template to create a normal
VirtualNetwork. Its manager/profile and network policy drive VPC provisioning;
the template is a separate input to the Server Cluster membership operation.
The per-instance network-attachment path also selects an interface using the
workload template's HostType and fabric-role interface. That path configures an
individual attachment and does not itself create the multi-host Netris Server
Cluster used by Phase 1 FabricDomain.

#### Why the template belongs with hardware binding

A NetworkClass can be used by machine types with different NIC counts, names,
or cabling. A single template on the class can silently describe the wrong
layout for one of those types. A Netris template is backend-specific, so the
Phase 1 correction is a private binding on BareMetalInstanceType, scoped to the
NetworkClass. The NetworkClass retains capability and V-Net policy; it does not
own a Netris object ID.

Phase 1 deliberately does not add `instance_type` to FabricDomain. Exact Netris
hostnames are mapped to shared BareMetalInstanceType IDs in an administrator
owned inventory ConfigMap. This works before a host is allocated as a
BareMetalInstance and avoids guessing from labels. Different hardware types may
share a template; one FabricDomain may proceed only when every member resolves
to the same NetworkClass-scoped template.

#### Phase 1 create and reconcile

1. An infrastructure administrator configures a Netris NetworkClass. The class
   advertises Ethernet east-west support through its fabric-manager capability.
   Its public configuration contains no Server Cluster template ID.
2. The administrator creates or updates shared BareMetalInstanceType catalog
   entries through the private API. For each applicable type, the private
   `fabric_bindings.ethernet_ew.netris` value contains the NetworkClass ID and
   canonical positive decimal template ID.
3. The administrator maintains `operator.fabricDomainInventory` in Helm
   values. The map associates each exact Netris inventory hostname with a
   shared BareMetalInstanceType ID. Helm renders
   `ConfigMap/osac-fabric-domain-inventory` in the operator's networking
   namespace.
4. A tenant or administrator creates a VirtualNetwork. FabricDomain creation
   can be requested while the VN is still provisioning; the reconciler waits
   for a Ready VN with its Netris VPC ID before launching AAP.
5. An infrastructure administrator creates a FabricDomain for the same tenant,
   selecting `ethernet_ew`, one VirtualNetwork, and exact Netris hostnames.
   Public reads remain tenant-scoped; Phase 1 writes are administrator-only.
6. Fulfillment persists the domain, its VN-derived owner metadata, hub
   assignment, and finalizer before creating the hub CR. This ordering allows
   retries and cleanup to find the same hub object.
7. The operator resolves VN → NetworkClass and VPC. For each server it resolves
   hostname → BareMetalInstanceType → Ethernet/Netris binding. Missing or
   ambiguous identity, a cross-class binding, a deleting type, or differing
   template IDs fails closed. It queries distinct type IDs in filters of up to
   100 IDs. Since the List API does not guarantee result ordering, an incomplete
   page is retried by splitting the ID filter rather than advancing an offset;
   inconsistent responses fail closed.
8. Before the first AAP launch, the operator records the NetworkClass, template
   ID, VPC ID, and region in private status. These backend identifiers are not
   exposed through the tenant-facing API. AAP creates or updates the Netris
   Server Cluster with those pinned values and the requested servers. AAP
   verifies each hostname against Netris inventory and refuses unsafe
   name-only selection. While an AAP job is active, the operator reuses this
   persisted binding instead of repeating catalog lookups; it revalidates the
   binding after the job completes.
9. The public status reports job-level conditions and member status; private
   status retains the backend and VPC IDs for reconciliation and cleanup.
   Failure messages omit raw backend identifiers; detailed errors remain in
   operator logs. Member states follow the overall job; the controller does not
   read back physical link or independent server attachment health. A reported
   backend ID is fetched through the exact-ID Netris endpoint and checked
   against the pinned site and known VPC before AAP mutates it. An exact-ID
   miss never falls back to a name lookup.
10. Delete uses the persisted backend ID and pinned site/VPC context. If create
    intent was persisted but the backend ID was never observed, cleanup retains
    its finalizer until it can safely resolve or report the unresolved intent.
    VN deletion is blocked while a FabricDomain still depends on it.
11. If a successful AAP job returns a ServerCluster ID for another VPC, omits
    the VPC ID, or succeeds without a valid ServerCluster ID, the operator
    records a durable unverified artifact marker. It does not trust the
    returned ID, retry provisioning, or remove the deletion finalizer until an
    administrator resolves the possible Netris artifact and clears the marker.
    The returned ID is retained in private status only when it is valid and
    available.

The AAP template may program EW, NS/storage, and OOB networks together. Before
using a template, administrators must confirm that its port assignments do not
conflict with existing Subnet or per-instance attachments. Separate
FabricDomain objects in one VPC do not automatically create separate routed
isolation. The fabric manager's routing and isolation policy must provide the
required boundary.

#### Phase 1 command shape

The public API remains singular and does not expose instance type or template
ID:

```bash
osac --tenant tenant-a create fabricdomain \
  --name training-ew \
  --type ethernet_ew \
  --virtual-network <virtual-network-id> \
  --servers gpu-01.example.com,gpu-02.example.com
```

Conceptual private hardware binding:

```yaml
spec:
  fabric_bindings:
    ethernet_ew:
      netris:
        network_class: "<network-class-id>"
        template_id: "42"
```

Administrator onboarding inventory:

```yaml
operator:
  fabricDomainInventory:
    gpu-01.example.com: "<shared-baremetal-instance-type-id>"
    gpu-02.example.com: "<shared-baremetal-instance-type-id>"
```

Neither the private hardware binding nor the onboarding map is returned in
tenant-facing catalog responses. A BareMetalInstanceType is a hardware
description and backend binding, not a membership declaration.

#### Proposed Phase 2: tenant workload intent and multiple fabric managers

A workload/allocation request should express the set of devices to allocate and
the fabric boundaries those devices require. FabricDomain membership should be
materialized from allocated BareMetalInstance identities, not copied from an
administrator-maintained hostname list. The request is the source of intent;
FabricDomain is the observed/reconciled backend isolation object.

For example, a tenant requests four bare-metal workers. All four need an NVLink
domain managed by NICo, while two workers also need a separate Spectrum-X
Ethernet domain managed by Netris:

```yaml
# Illustrative only; not a current OSAC schema.
workload:
  allocations:
    - name: gpu-workers
      instanceType: hgx-8gpu
      count: 4
    - name: spectrumx-workers
      subsetOf: gpu-workers
      count: 2
  fabricRequests:
    - name: gpu-mesh
      type: nvlink
      members:
        workerGroup: gpu-workers
      backendProfileRef: nico-hgx
    - name: rdma-uplink
      type: ethernet_ew
      members:
        allocation: spectrumx-workers
      networkClassRef: spectrum-x
```

The scheduler allocates four BareMetalInstances. The NVLink controller request
contains all four allocated identities; the Ethernet request contains exactly
the two identities selected for the `spectrumx-workers` subset. The tenant can
choose the subset explicitly where supported, or ask placement to select any
two compatible workers. These become separate FabricDomain resources or separate
backend attachments managed under one workload, according to backend lifecycle
and API review. No hostname list is hand-maintained. Each hardware type must
advertise the required fabric capability and binding. Placement must reject a
request if no valid set of compatible devices can be allocated.

The ownership boundary is:

- **BareMetalInstanceType:** physical ports/roles, supported fabric types, and
  backend binding/profile references required to connect that SKU. It never
  decides tenant membership.
- **NetworkClass:** tenant-visible network capability and policy, such as
  Ethernet EW support and V-Net policy. It does not contain a Netris template
  identifier.
- **Workload/order request:** requested number and groups of devices, plus the
  desired fabric membership for each group.
- **FabricDomain:** durable identity and lifecycle of a specific fabric
  isolation boundary, with membership resolved to allocated device identities
  and observed backend status.
- **Infrastructure administrator:** configures hardware catalog, backend
  connectivity/credentials, policy, and available fabric profiles.
- **Tenant:** chooses from allowed fabric capabilities/profiles and asks for
  workload membership. The tenant does not provide Netris IDs, switch ports,
  HCA GUIDs, GPU UUIDs, or credentials.

For direct BMaaS requests, the workload intent belongs on the BareMetalInstance
allocation/request path, which already resolves the selected type and allocated
host. For CaaS worker pools, it belongs on the worker-group or order object and
must be propagated to the resulting BareMetalInstances. The implementation
must choose one canonical intent source and avoid requiring users to repeat the
same membership on both the order and every resulting instance.

A workload may ask for multiple domains with different member sets. For
example, all four machines can share a NICo NVLink partition while only two
join the Netris Ethernet domain, if the machine ports and both backends permit
that combination. Membership overlap is allowed across distinct fabric planes
when each backend supports it. It is not assumed to work for two Netris
dedicated Server Clusters: that backend's host exclusivity and shared endpoint
semantics must be checked and represented as capabilities. The API must reject
a topology that the selected manager cannot realize rather than silently
dropping or broadening membership.

Non-Netris domains need backend-specific, private configuration with explicit
ownership:

| Fabric | Hardware facts from BareMetalInstanceType | Admin/backend profile | Domain reconciliation |
|---|---|---|---|
| Ethernet EW | Ethernet ports and roles; Netris-compatible layout | Netris controller/site plus template binding scoped to the hardware type and NetworkClass | Server Cluster, VPC, members, and status |
| InfiniBand EW | HCA ports/GUID capabilities and supported link mode | UFM or supported Netris-IB profile, PKey allocation policy, credential reference | HCA membership, PKey assignment, observed state |
| NVLink | GPU/topology capabilities and supported peer layout | NICo or NMX-C endpoint/profile, partition policy, credential reference | GPU/device membership, partition lifecycle, observed state |

The controller API should normalize lifecycle operations—resolve members, attach,
detach, observe, retry, and delete—while adapters implement Netris, UFM, NICo,
or NMX-C semantics. Do not model all fabrics as a Netris template ID. Profiles
and secrets stay infrastructure-owned. Tenant APIs reference an allowed profile
or policy, not a management endpoint or credential.

#### Proposed Phase 3: VM integration

VMs are not physical Server Cluster members. The current ComputeInstance
`network_attachments` select Subnets and SecurityGroups; they do not refer to
FabricDomain and do not allocate a fabric device. Phase 1 therefore makes no
claim that a VM can use the FabricDomain's EW path.

A future VM workload request can ask for a fabric attachment, but the request
must be realized through a host device path. For Ethernet, that may require an
SR-IOV Virtual Function (VF) or another supported virtual NIC carved from a
physical port that is already connected to the correct fabric. The VM placement
and device allocator must ensure that the host's BareMetalInstanceType has the
right port role and backend binding. The attachment controller must reserve and
release the device, connect it to the VM, and enforce tenant isolation. Netris
continues to see and manage the physical server/port; it does not see the VM as
a Server Cluster server.

A VM asking for NVLink additionally requires a supported GPU passthrough or
virtualization mode, peer-memory support, and a NICo/NMX-C allocation model.
It cannot be promised as an ordinary Subnet attachment. The platform must
validate those capabilities before scheduling the VM. If the VM cannot receive
the requested device semantics, admission must reject the request.

Phase 3 adds VM request fields and a reconciliation path that binds a logical
FabricDomain membership to concrete host devices and guest interfaces. The
domain records the fabric boundary; the VM instance records the allocated
interface/device attachment. VM detach/delete must release the VF/GPU resource
and update backend membership safely. The detailed ComputeInstance/BareMetal
device API and live SR-IOV/NVLink integration tests remain design work.

### API Extensions

Phase 1 adds or changes these API surfaces:

- Fulfillment public FabricDomain CRUD uses a singular `virtual_network`, an
  Ethernet EW type, and requested Netris hostnames. Type and VN are immutable;
  servers may be updated for resize. Public writes are administrator-only in
  this rollout; tenant-scoped reads retain tenant filtering.
- The private BareMetalInstanceType API adds
  `spec.fabric_bindings.ethernet_ew.netris.network_class` and
  `template_id`. CleanAPI marks this field private, and public catalog
  projection omits it.
- The NetworkClass public schema no longer accepts/reserves a template ID. EW
  capability is derived from the configured fabric-manager capability and
  remains disabled unless enabled for the deployment.
- The hub FabricDomain CRD contains the desired servers/VN, pinned provisioning
  identity, and private recovery status (`unverifiedBackendArtifact` plus an
  optional `unverifiedBackendId`). The operator watches FabricDomain, relevant
  VirtualNetwork changes, and its exact-host inventory ConfigMap. These
  recovery fields are private hub status, not tenant-facing API fields.
- Fulfillment-to-hub reconciliation persists hub placement and finalizer before
  CR creation, and feeds status back. VN deletion and FabricDomain create share
  dependency serialization.
- AAP Server Cluster create/delete validates server identities and scopes
  lookup by backend ID or site/VPC. It never deletes the first global name
  match.

Phase 2 requires a workload-facing membership request contract and a stable
allocated-device reference. Phase 3 requires VM device allocation and guest
attachment APIs. Those future fields are not implemented in Phase 1 and should
not be treated as finalized protobuf or CRD schemas.

## UX Alignment

No matching FabricDomain UI `@temp-api` contract is present in the design
inputs. Phase 1 uses the CLI/API for administrator operations. Before tenant
self-service UI work, define the supported workload and fabric-profile fields
in the API first, then align the UI type and generated types with that contract.

## Implementation Details/Notes/Constraints

### Ownership and data flow

```text
Admin config:
  NetworkClass capability/policy
  BareMetalInstanceType private Netris binding
  Helm exact-host → BareMetalInstanceType inventory
  pre-created Netris Server Cluster template

Tenant/IP setup:
  VirtualNetwork → NetworkClass → Netris VPC
  optional Subnet → IP segment/attachment

Phase 1 admin request:
  FabricDomain { ethernet_ew, one VN, exact Netris hostnames }
        ↓
  fulfillment API → assigned hub CR → operator
        ↓ resolve host types and pin config
  AAP create/update/delete Server Cluster → Netris
        ↓
  operator conditions/status → fulfillment API
```

The VirtualNetwork's NetworkClass selects the network backend and capability;
the VirtualNetwork reconciliation creates/records its VPC. A Server Cluster
create is a separate operation requiring the template ID, member servers, and
VPC context. A normal Subnet or north-south attachment does not need the
Server Cluster template. This is why moving the ID changes its owner, not the
provisioning operation.

### Hardware and Netris template

The Phase 1 private binding is a per-type Netris reference scoped to one
NetworkClass. The Netris template itself remains provisioned out of band. It
contains server NIC names and the V-Net configuration used by Server Cluster
creation. This phase does not claim that OSAC can inspect the Netris template
to prove its ports, routing, or V-Net contents match the hardware.

A FabricDomain containing multiple BareMetalInstanceTypes is valid only if each
type resolves to the same template ID for the VN's NetworkClass. Different
types may share that template. A future inventory model should source host
identity from allocated BareMetalInstances and remove the Phase 1
hostname-to-type ConfigMap.

### Tenant metadata and lifecycle

Every hub FabricDomain carries `osac.openshift.io/tenant` and
`osac.openshift.io/owner-reference`. Tenant derives from the API resource;
owner-reference is forced to the associated VirtualNetwork API ID. It is an
OSAC hierarchy annotation, not a Kubernetes OwnerReference; finalizers and the
database dependency guard control lifecycle.

The API-to-hub reconciler stores the hub assignment and finalizer before
creating the CR. Create locks/validates the VN against deletion; deleting a VN
checks for active dependent domains. Cleanup uses the pinned region/VPC/backend
ID where available and retains the finalizer for unresolved create intent.
This prevents duplicate hub objects and accidental name-only backend deletion.

### Status meaning

`Ready=True` means the configured AAP Server Cluster operation completed and
returned a valid backend ID and the expected VPC ID. The backend and VPC
identifiers remain in private status; public readers receive the job conditions
and member summary, not raw Netris resource IDs. Per-server Active/Failed values are derived from
the job result and requested list. They do not mean that OSAC queried Netris
for independent port/link state, ran RoCE health checks, or validated
data-plane isolation. The status API must retain that distinction until
per-member observation exists.

### Component changes

| Component | Phase 1 responsibility |
|---|---|
| fulfillment-service | Private hardware bindings, NetworkClass capability semantics, FabricDomain validation/auth/CRUD, hub reconciler, status feedback, VN deletion dependency guard, CLI |
| osac-operator | Hardware lookup, pinned provisioning config, VN and ConfigMap watches, finalizer/reconcile, AAP launch, status, metrics/events |
| osac-aap | Fail-closed Netris host resolution and scoped Server Cluster create/delete |
| osac-installer | BMIT/inventory onboarding documentation, Helm inventory value and ConfigMap |
| tests/e2e | Deployed API authorization/tenant-visibility contract tests; no live Netris lifecycle suite is claimed |

## Security Considerations

Phase 1 FabricDomain writes are restricted to infrastructure administrators.
Tenants can inspect only domains visible to their tenant. Fulfillment validates
the referenced VN tenant and capability. The hub CR tenant annotation is
derived from the API object and owner-reference from its VN; caller values
cannot override them. The inventory ConfigMap and private BMIT bindings are
administrator-owned. Netris credentials remain in AAP's existing secret path.

Hostnames are security-sensitive infrastructure identifiers. The AAP role
resolves every requested host exactly and rejects absent, ambiguous, wrong-site,
or malformed identities before mutation. With an explicit backend ID, the role
uses the exact resource endpoint and verifies the returned site and known VPC
before mutation. A missing exact resource or scope mismatch fails closed. If
there is no backend ID, lookup requires a unique name match scoped to site and
VPC. There is no global first-by-name fallback.

If AAP reports success without a valid ServerCluster ID or without confirming
the expected VPC, the operator records a private recovery marker. It blocks
further provisioning and retains the FabricDomain finalizer. An administrator
must verify whether Netris contains an artifact, resolve it, and clear both
`status.unverifiedBackendArtifact` and `status.unverifiedBackendId` before
reconciliation resumes.

Phase 2 tenant membership must be authorized against allocation ownership.
Tenant requests may select only their own allocated devices and permitted
backend profiles. A tenant must never supply raw backend IDs, hostnames,
hardware inventory, HCA/GPU identifiers, or credentials as a way to bypass
placement policy.

## Failure Handling and Recovery

| Failure | Behavior and recovery | User-visible result |
|---|---|---|
| VN is not Ready or has no Netris VPC ID | Reconcile requeues and watches VN changes; no AAP job is launched | FabricDomain remains Progressing |
| Inventory hostname is missing or maps to no shared BMIT | Fail closed; administrator corrects ConfigMap/catalog and reconcile retries | Failed condition identifies unresolved host/type |
| Type lacks an Ethernet/Netris binding for this NetworkClass | No AAP mutation; fix private catalog binding | Failed condition names type/class mismatch |
| Domain members resolve to different template IDs | Refuse provisioning; split the membership or align hardware bindings | Failed condition reports incompatible layouts |
| Netris hostname is absent or ambiguous | AAP role stops before create/update/delete | AAP failure condition; no unsafe host mutation |
| Exact backend ID is missing or resolves outside the pinned site/VPC | AAP uses the exact-ID endpoint, validates scope, and stops without name fallback or mutation | AAP job fails; operator retains the existing trusted ID and finalizer |
| Netris create succeeds but status/job record is lost | Retry uses idempotent scoped lookup; persisted intent and finalizer prevent false cleanup success | Progressing or explicit unresolved-intent failure |
| AAP succeeds without a valid ServerCluster ID | Set `status.unverifiedBackendArtifact`; block retries and finalizer removal because an unidentifiable artifact may exist. Administrator verifies/removes any Netris artifact, then clears the marker | Failed condition instructs an administrator to resolve the artifact; deletion remains pending |
| AAP returns a valid ServerCluster ID but omits the VPC ID or reports another VPC | Keep the ID out of trusted `backendId`; persist the unverified marker and ID, then block retries and deletion until administrator resolution | Failed condition; finalizer remains until the marker is cleared after Netris verification |
| Delete has intent but no observed backend ID and no unverified-artifact marker | Do not remove finalizer on a no-op; retry safe resolution and surface unresolved identity | Deletion remains pending/failed for admin action |
| NetworkClass/type binding changes after pinning | Operator refuses silent live rebinding; restore binding or delete/recreate for migration | Failed condition explains pinned-config mismatch |
| AAP, Netris, or operator is unavailable | Reconcile/job retry is idempotent with pinned identity | Progressing/Failed with retryable reason |
| VM lacks a supported VF/GPU path in Phase 3 | Admission/placement rejects before backend mutation | Request reports unsupported device capability |

## RBAC / Tenancy

| Actor | Phase 1 access |
|---|---|
| Infrastructure administrator | Configure NetworkClass, private BMIT binding, inventory; create/update/delete FabricDomain |
| Tenant administrator/user | Read only tenant-visible FabricDomains; create VirtualNetworks and Subnets under existing policy |
| Workload controller | No new Phase 1 privilege; receives the domain status through existing service contracts |

The tenant annotation scopes visibility. The owner-reference annotation records
the VN relationship for every hub object. Phase 1 does not grant a tenant the
ability to enroll arbitrary servers. Phase 2 must let a tenant request membership
only for devices allocated to that tenant through a workload/order.

## Observability and Monitoring

The operator exports:

| Metric/event | Meaning |
|---|---|
| `osac_fabric_domains_total{type,tenant}` | Non-deleting domains in the configured networking namespace |
| `osac_fabric_domain_provisioning_duration_seconds{type}` | Time to first persisted Ready state |
| `osac_fabric_domain_provisioning_failures_total{type,reason}` | Persisted transitions into failure or a new failure reason |
| `FabricDomainProvisioned` (Normal) | First successful Ready transition |
| `FabricDomainProvisioningFailed` (Warning) | Persisted failure reason changes |
| `FabricDomainDeleted` (Normal) | Backend cleanup succeeds |

These report control-plane/job state. They do not measure per-server attachment,
physical link health, collective performance, or tenant data-plane reachability.
Repeated reconciles do not emit duplicate failure counts/events for an unchanged
persisted reason.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Phase 1 inventory map can become stale | Exact host identity, explicit BMIT ID, ConfigMap watch, admin-owned changes, and fail-closed resolution |
| Netris template may not match physical wiring | Binding is per hardware type; template remains admin-managed; require deployment validation and do not claim automatic template inspection |
| Tenant-facing PRD scope is not delivered in Phase 1 | State the boundary explicitly; revise PRD/Jira before implementing workload self-service |
| AAP job success may overstate member readiness | Document job-level status semantics and plan independent member observation |
| Same host may be requested by competing domains | Phase 1 is admin-operated; add conflict/lease enforcement before tenant automatic membership |
| Backends have different membership constraints | Define capabilities and validation per adapter; do not flatten all backends into Netris Server Cluster semantics |
| VM networking cannot attach physical fabric semantics by Subnet alone | Require explicit VF/GPU allocation and guest attachment support before advertising VM capability |

Security review must cover administrator-only binding/inventory writes, tenant
filtering, stale/conflicting allocations, and backend cleanup identity.

## Drawbacks

Moving the template to a private BareMetalInstanceType binding adds catalog
configuration and an administrator-maintained Phase 1 hostname map. The map is a
temporary bridge; it duplicates identity already available after allocation.
The private field is Netris-specific for Phase 1 and must evolve into
backend-scoped bindings before additional fabrics are implemented.

An explicit FabricDomain resource adds API and controller surface even when a
workload request could theoretically carry a backend payload directly. It is
retained because the isolation boundary has independent identity, status,
backend correlation, and cleanup. The future design must keep request intent
and materialized domain membership from becoming competing sources of truth.

## Alternatives (Not Implemented)

### Keep the template on NetworkClass

This is the smallest change and works only when every machine type using the
class has an identical Netris NIC layout. It cannot safely model per-SKU layouts
or reject mixed templates. Rejected because backend hardware configuration
belongs with the hardware selection used for each member.

### Add `instance_type` to FabricDomain

This removes hostname lookup only if every server in the domain is already
known to use that type. It misstates membership as hardware configuration and
still does not identify individual allocated machines. Rejected for Phase 1;
allocated device identities should supply type in Phase 2.

### Infer type from HostType selectors or hostname patterns

A selector can match multiple catalog entries and hostname conventions are not
a stable identity contract. Rejected in favor of an explicit exact-host
onboarding map during Phase 1 and allocated BareMetalInstance identity later.

### Create FabricDomains only from per-instance network attachments

The current attachment model selects an interface and attaches one instance to
an IP network. It does not express one multi-host EW isolation boundary or
drive Netris Server Cluster creation. A common attach/detach reconciler may
become a reusable Phase 2 backend path, but the resource lifecycle and domain
identity remain explicit.

### Put all fabric configuration on NetworkClass

This conflates tenant network policy, hardware wiring, backend endpoint
configuration, and membership. It also cannot describe two independent
FabricDomains with different device subsets. Keep policy, hardware binding,
backend profile, and membership intent at their respective ownership layers.

### Make FabricDomain contain a tenant-supplied hostname list permanently

This cannot safely serve tenant BMaaS or allocation-driven CaaS. Rejected as
the long-term source of membership; Phase 1 keeps it only as an admin bridge.

### Do not introduce a FabricDomain resource

Putting backend status directly on an order or instance duplicates lifecycle
state across workloads and gives cleanup no stable fabric-boundary identity.
Rejected for workloads that require an independently reconciled isolation
boundary. A short-lived implementation detail may be nested in a workload CR,
but the domain identity and backend lifecycle must remain addressable.

## Open Questions

1. Should Phase 2 intent live on a shared workload/order fabric-request field,
   on BareMetalInstance allocation requests, or in a common request object that
   both CaaS and BMaaS materialize? The API must have one source of truth and
   preserve per-domain member subsets. **Owner:** OSAC API and workload
   architecture. **Impact:** Phase 2 request schema and allocation lifecycle.
2. Should a FabricDomain be tenant-created as a reusable named boundary, or
   created by the workload controller from each workload's fabric request?
   Decide reuse, ownership, and deletion semantics before defining the public
   API. **Owner:** OSAC product and API architecture. **Impact:** Phase 2
   FabricDomain ownership and deletion semantics.
3. Which backend adapters are required first: Netris Ethernet, UFM/Netris
   InfiniBand, NICo NVLink, or NMX-C? For each, define member identity,
   isolation primitive, allowed overlap, and observed Ready criteria. **Owner:**
   Fabric backend integration team. **Impact:** Phase 2/3 adapter scope and
   backend profile schema.
4. Which VM device model and supported hardware provide a safe Ethernet VF and
   NVLink path? Define allocation, guest attach/detach, and cleanup contracts
   before adding VM API fields. **Owner:** VMaaS and BMaaS architecture.
   **Impact:** Phase 3 VM request and device lifecycle APIs.
5. Does the Phase 1 NetworkClass capability source and Phase 2 fabric-profile
   selection remain adequate when deployments support more than one manager or
   NetworkClass? **Owner:** OSAC API architecture. **Impact:** NetworkClass
   capabilities and tenant-visible fabric profile selection.

## Test Plan

### Unit Tests

- Validate the private template ID is a positive canonical decimal value and is
  not exposed in the public BareMetalInstanceType projection.
- Reject stale/missing host inventory, missing/deleting BMITs, wrong
  NetworkClass bindings, and mixed template IDs.
- Verify template/VPC/region configuration is pinned before launch and catalog
  changes do not silently mutate an existing domain.
- Verify owner/tenant annotations are overwritten from authoritative API
  relationships; create and VN delete serialize correctly.
- Verify AAP refuses missing, duplicate, ambiguous, wrong-site, and unsafe
  name-only host/Server Cluster lookups before mutation.
- Verify missing/invalid AAP backend IDs and wrong-VPC artifacts persist the
  unverified-artifact marker, block retries and deletion, and retain the
  finalizer until administrator resolution; successful delete uses the
  recorded backend identity, and public responses omit private Netris/VPC IDs.
- Verify exact-ID AAP lookups use the resource endpoint, validate site/VPC
  scope, and never fall back to global name matching after a miss.
- Verify a successful AAP job that omits the ServerCluster VPC ID leaves the
  returned backend ID untrusted and retains the recovery marker.
- Verify a VirtualNetwork becoming Ready or its inventory map changing wakes
  only the relevant FabricDomain reconciliations.
- Verify metric/event transitions are emitted once and represent job-level
  readiness.

### Integration Tests

- Run fulfillment database/API/authorization tests for create, read, update,
  delete, tenant isolation, admin write policy, owner metadata, and VN deletion
  dependencies.
- Run operator envtest reconciliation with fake Fulfillment/AAP clients,
  including Ready delay, resize, delete, restart/retry, pinned config, and
  watches.
- Run AAP role tests against the local Netris HTTP stub for create, resize,
  deletion, and identity ambiguity.
- Render installer/operator Helm charts with empty and populated
  `fabricDomainInventory`; validate the ConfigMap namespace, exact data, schema,
  and CRD copies.
- Exercise API-to-hub status feedback and finalizer ordering with both hub
  clients and the private API reconciler.

### E2E Tests

- Deploy OSAC with an Ethernet EW-capable Netris NetworkClass and verify
  tenant-scoped reads and administrator-only FabricDomain writes through the
  API. This API contract test does not provision a live Netris Server Cluster.
- A live Netris/AAP scenario should create a VN, wait for its VPC, create an
  admin FabricDomain, observe the AAP job and Server Cluster, resize, then
  delete and verify backend cleanup and VN deletion unblocking.
- Test true same-tenant and cross-tenant packet isolation only on a deployment
  with representative Netris hardware and network templates; API status alone
  is insufficient evidence.
- Phase 2 tests must request four devices with an NVLink domain covering all
  four and an Ethernet EW domain covering two, then verify allocated identity,
  membership and failure recovery against each backend.
- Phase 3 tests must allocate and release an Ethernet VF to a VM, test tenant
  isolation, and verify that unsupported NVLink virtualization requests fail
  before placement or backend mutation.

Phase 1 unit, envtest, role, and chart checks are implementation validation.
The live fabric lifecycle and packet-level E2E scenarios remain deployment
coverage and are not claimed as run by this design update.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages:
Dev Preview → Tech Preview → GA based on production deployment feedback. Phase 1
must at minimum pass API/operator/AAP unit and integration validation, publish
the administrator onboarding guide, and clearly document the absence of live
Netris/data-plane E2E validation.

## Upgrade / Downgrade Strategy

The Phase 1 fields are additive except NetworkClass's prior template field is
removed/reserved. Before upgrade, remove the template ID from NetworkClass and
write equivalent per-type private BMIT bindings plus exact-host inventory.
Existing FabricDomains must have their selected NetworkClass/template/VPC/region
pinned before controller rollout can safely continue reconciliation. Do not
silently switch backend configuration for an already-created Server Cluster.

Downgrade requires removing FabricDomains and their backend Server Clusters
before reverting the controller and private BMIT schema. Keep the catalog and
NetworkClass migration steps documented with the release.

## Version Skew Strategy

Deploy fulfillment API, operator CRD/controller, and AAP role changes as one
compatible OSAC release. The operator requires the private BareMetalInstanceType
fields, new CRD status shape, inventory ConfigMap, and AAP variables. If the
private API or CRD is ahead/behind, reconciliation must report an explicit
configuration or compatibility failure and retain finalizers where cleanup is
incomplete. NetworkClass capability remains disabled by default until the
operator and AAP dependencies are ready.

## Support Procedures

Use API conditions and the hub FabricDomain CR to identify the failed stage.
Check VN readiness/VPC ID, exact-host ConfigMap entries, shared BMIT state and
NetworkClass-scoped binding, then the AAP job and Netris Server Cluster by
pinned backend ID/site/VPC. Correct the catalog or inventory and allow the
controller to retry. If `unverifiedBackendArtifact` is true, search Netris by
the recorded unverified ID when present and by the domain name plus pinned site
and VPC. Verify and remove or correct any artifact before clearing both
`status.unverifiedBackendArtifact` and `status.unverifiedBackendId`; do not clear
the marker just to force reconciliation. Do not delete the VN while a domain is
deleting. If create intent has no observed job or backend ID and no artifact
marker, keep the finalizer and investigate the AAP job rather than clearing it
manually.

Disabling network provisioning prevents new backend work and must not mark a
domain Ready. Existing domains still require cleanup through the normal
finalizer path before uninstalling the controller or removing API fields.

## Infrastructure Needed

No new infrastructure is required for Phase 1. Validation uses existing
fulfillment/operator test harnesses, an AAP local HTTP stub, and installer
chart rendering. Live Netris/AAP and packet-level coverage requires a
representative deployment and remains an environment prerequisite.

## References

- [OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382)
- [FabricDomain Phase 1 API and controller PR #1270](https://github.com/osac-project/osac/pull/1270)
- [Netris Server Cluster API](https://www.netris.ai/docs/en/latest/server-cluster.html)
- [Netris V-Net documentation](https://www.netris.ai/docs/en/latest/vnet.html)
- [Enhancement proposal #179](https://github.com/osac-project/enhancement-proposals/pull/179)

---

## Provenance

Authored: revise @ design 0.8.0 - 7efcedb, workspace main @ d165396

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"d165396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
