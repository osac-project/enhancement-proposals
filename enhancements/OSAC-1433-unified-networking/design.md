---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-09-16
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - BareMetal Instance API: /enhancements/OSAC-1118-baremetal-instance-api
  - Three-Layer Networking Model: https://docs.google.com/document/d/1MwBjpmYoZoUN3PVjeIRZ2Y6mBuf0lu1uvTtN6XXPPTM
  - VMaaS Networking: /enhancements/OSAC-1435-vmaas-networking
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - BMaaS Networking: /enhancements/OSAC-1437-bmaas-networking
  - Default Networking: /enhancements/OSAC-1433-default-networking
replaces:
  - OSAC-356 Networking API (legacy)
superseded-by:
  - N/A
---

# Unified Networking API for VMaaS, CaaS, and BMaaS

## Summary

This document describes the technical design for the OSAC unified
networking architecture. For the problem statement and requirements,
see the companion [Requirements Document (PRD)](prd.md).

### Deployment Support Boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected networking deployments are outside the supported
boundary and must not be advertised as supported profiles. A connected
deployment has reachability among the provider-owned hub, selected network
managers, provider-controlled networking services, and provider-controlled
address infrastructure. The provider owns this configuration; connectivity is
not tenant selectable, and these reachability prerequisites must hold before
the deployment's NetworkClass is accepted. The boundary applies to
Fabric-only, K8s-only, and combined manager profiles.

### Networking Hub Support Boundary

OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

OSAC runs VMs on OpenShift using KubeVirt, which encapsulates each VM in a
pod. Pod networking is managed by OVN-Kubernetes, meaning VMs live inside an
OVN overlay that is not directly visible on the physical fabric. The core
premise of this design is that **VMs are part of the fabric**. Through a
[K8s manager](#how-vms-join-the-fabric) that bridges the OVN overlay to the
physical network, VMs become first-class participants in the fabric alongside
bare-metal servers and cluster nodes. Once on the fabric, all resource types
are treated uniformly — the fabric manager handles isolation, security, IP
allocation, DNAT, and SNAT for everything.

The design introduces:

- **NetworkClass** with two fields: `fabricManager` (handles all physical
  networking) and optional `k8sManager` (bridges VMs to the fabric)
- **Infrastructure-agnostic subnets** where the same subnet can host VMs,
  BM servers, and cluster nodes
- **ExternalIP** (renamed from PublicIP) to clarify that addresses are
  external to the VirtualNetwork, not necessarily internet-routable
- **Uniform API** where the same networking resources (VirtualNetwork,
  Subnet, SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway)
  serve VMaaS, CaaS, and BMaaS identically

The BMaaS integration is based on the `BaremetalInstance` resource defined in
the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api),
which provides a per-server resource aligned with ComputeInstance.

All networking resources and manager integrations in this design use IPv4.
IPv6 and dual-stack networking are not supported.

> **Implementation status:** This is the normative target contract. Current
> schemas and allocation paths still contain legacy IPv6/dual-stack
> support; implementation work must enforce this contract before rollout.

For user stories, goals, and non-goals, see the
[Requirements Document (PRD)](prd.md).

## API Contract

This section is the canonical API reference for unified networking. It covers
the networking fields on the resource itself and on the workload resources
that consume networking. Non-network workload fields remain governed by their
service-specific designs.

### Shared API conventions

#### API resource and persistence representations

The resource described in this section is the logical API resource, not a
database row. The `Field` column uses a logical field path such as
`spec.ipv4_cidr`; it describes the public API contract independently of the
transport used to carry it.

A logical `Create` operation accepts only fields marked request-writable. A
logical `Get` or `List` operation returns the complete resource representation,
including server-assigned identity, resolved defaults, output-only status, and
provider/controller fields where the caller is authorized to see them. The
request and response envelopes may differ by API transport, but they carry
this same logical resource contract.

The database or CRD representation is implementation-specific. It may split
metadata into columns, store spec/status as structured data, add version and
lifecycle data, or use a different schema entirely. Those storage details must
not be used as the API field contract.

#### Methods

| Method | Availability | Contract |
|---|---|---|
| `List` | User, provider, or private controller according to resource scope | Returns only resources visible in the caller's tenant/project or provider scope. Filters and ordering use the platform resource API. |
| `Get` | User, provider, or private controller according to resource scope | Resolves one resource by its stable `id` or supported metadata name and applies the same visibility rules as `List`. |
| `Create` | Resource owner or provider, depending on the resource | Validates the complete request before persistence, resolves documented defaults, and stores an immutable effective network configuration. |
| `Delete` | Resource owner or provider, depending on the resource | Enforces reverse-reference and dependency guards. Auto-created ExternalIP children are deleted by the documented parent finalizer flow. |
| `Update` | Not supported for networking configuration | The operation is not part of the networking contract. Metadata and network-owned fields are immutable; a replacement requires delete and create. An implementation that exposes a generic update operation must reject networking updates. |
| Private `Signal` / reconciliation writes | Controller only | Internal signals may trigger reconciliation. Controllers may update status, conditions, readiness, IP discovery, timestamps, and finalizers; these are not user API updates. |

Every networking resource has the common envelope `id`, `metadata`, `spec`,
and `status`.

#### Common resource envelope fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `id` | Stable resource identity | String | Present in responses; immutable | Unique within the resource type and deployment scope. |
| `metadata` | Resource name, ownership, labels, annotations, and lifecycle metadata | Metadata | Present where defined; immutable after creation for every caller | No metadata update operation is supported. Server-managed deletion/finalizer bookkeeping is lifecycle control, not a metadata update. |
| `spec` | Desired networking configuration | Resource-specific message | Required or optional as stated by the resource; immutable after creation | Input is validated before persistence and defaults are resolved into the effective configuration. |
| `status` | Controller-reported lifecycle and discovery results | Resource-specific message | Output-only | A resource starts in its resource-specific `UNSPECIFIED` or `PENDING` state, becomes `READY` only after required backend work succeeds, and reports terminal failures through `FAILED` and `status.message`. |

#### Shared formats, types, and presence

| Value | Type and format | Presence/default/validation |
|---|---|---|
| IPv4 CIDR | String `a.b.c.d/prefix`, prefix `0..32`, host bits zero | Required where the resource table says required. IPv6, dual-stack, malformed, non-canonical, and host-bit-set values are rejected. A Subnet must be contained by its parent VirtualNetwork and sibling Subnets must not overlap. |
| IPv4 address | String `a.b.c.d` without a CIDR suffix | Output-only for allocated/discovered addresses. Empty means not discovered; it is not a sentinel address. |
| Resource reference | Typed local or full reference message with the documented `id`/`name` fields | The referenced object must exist, be visible in the permitted scope, have the required type, and be `READY`/`ALLOCATED` when the field's table requires it. Arbitrary identifier strings are not valid typed references. |
| Enum | Named value from a resource-defined enumeration | User-set enum fields reject `UNSPECIFIED`, unknown, and future values unless the resource table explicitly allows `UNSPECIFIED`. |
| List | Ordered or unordered list of values or typed references | Cardinality, duplicate handling, and ordering are part of the field contract. Duplicate references are rejected; ordering is preserved where primary attachment order is meaningful. |
| Field path | Dot-separated logical path such as `spec.ipv4_cidr` | Field names are stable API concepts; a transport may apply its own naming or envelope rules. |
| Timestamp | Point in time | Controller/system timestamps use RFC 3339/UTC semantics when exposed by the API. |
| Integer counter | Whole-number count | Counters are non-negative unless a resource table explicitly states otherwise. |

### NetworkClass API

NetworkClass is provider-owned and deployment-scoped. Tenants may list or get
the effective class but cannot create, update, or delete it.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Provider or authorized tenant reader | Lists the deployment's visible NetworkClass objects; tenant callers receive the effective classes only. |
| `Get` | Provider or authorized tenant reader | Returns one visible NetworkClass and its resolved manager, capability, and default fields. |
| `Create` | Provider control plane | Creates a provider-owned class after connected reachability and manager-registration validation. |
| `Delete` | Provider control plane | Deletes a class only when no deployment default or tenant resource references it. |
| `Update` | Not supported | NetworkClass metadata, manager selection, capabilities, and defaults are immutable; replacement requires delete and create. |
| Private reconciliation | Networking controller | Updates only status, readiness, diagnostics, and hub placement. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `title` | Short provider-authored display name | String | Optional, provider-set, immutable | Presentation only; it does not select a backend. |
| `description` | Provider-authored long description and limitations | Markdown string | Optional, provider-set, immutable | Must follow platform Markdown rules. |
| `constraints` | Provider implementation constraints | `NetworkClassConstraints` | Optional provider output, immutable | No tenant-defined constraint fields are currently supported. |
| `capabilities` | Provider-computed supported address and feature capabilities | `NetworkClassCapabilities` | Output-only | `supports_ipv4` is true for a usable class; IPv6 and dual-stack are false in this contract. The manager combination must not advertise unsupported resources. |
| `capabilities.supports_ipv4` / `spec.disable_capabilities.supports_ipv4` | Whether IPv4 is supported or disabled by policy | Boolean | Capability is output-only; disable flag is provider-only; default `false` | Effective `capabilities.supports_ipv4` must be true for an accepted class. |
| `capabilities.supports_ipv6` / `spec.disable_capabilities.supports_ipv6` | Whether IPv6 is supported or disabled by policy | Boolean | Capability is output-only; disable flag is provider-only; default `false` | Must be false in this IPv4-only contract. |
| `capabilities.supports_dual_stack` / `spec.disable_capabilities.supports_dual_stack` | Whether dual-stack is supported or disabled by policy | Boolean | Capability is output-only; disable flag is provider-only; default `false` | Must be false in this IPv4-only contract. |
| `capabilities.dpu_support` / `spec.disable_capabilities.dpu_support` | Whether DPU offload is supported or disabled by policy | Boolean | Capability is output-only; disable flag is provider-only; default `false` | May be true only when the selected managers advertise DPU support. |
| `is_default` | Marks the provider-selected default class | Boolean | Provider-only; default `false`; immutable to tenants | At most one active default class exists per deployment. |
| `fabric_manager` | Selects the registered physical/fabric manager | String | Provider-only, immutable | If set, it must name an enabled provider registration. It handles physical segments, ACLs, IP allocation, DNAT, and SNAT. |
| `k8s_manager` | Selects the registered Kubernetes networking manager | String | Provider-only, immutable | If set, it must name an enabled provider registration. At least one of `fabric_manager` and `k8s_manager` is required. |
| `spec.defaults` | Default tenant onboarding network configuration | `NetworkDefaults` | Required by this contract; provider-only and immutable | Both IPv4 default CIDRs are required and must satisfy the nested field rules below. |
| `spec.disable_capabilities` | Provider policy for disabling supported capabilities | `NetworkClassCapabilities` | Optional provider-only, immutable | Not tenant input. Disabled values cannot appear in the effective capabilities. |
| `spec.vip_prefix_length` | Reserves the subnet suffix for CaaS API/ingress VIPs | Integer | Conditionally required, immutable | Required when CaaS/MetalLB VIP allocation is offered. It must be a valid IPv4 prefix more specific than the participating Subnet prefix and contained within that Subnet. |
| `spec.defaults.virtual_network_ipv4_cidr` | CIDR for the automatically created tenant VirtualNetwork | String | Required within `defaults`; immutable | Canonical IPv4 CIDR with host bits zero. There is no fallback if omitted. |
| `spec.defaults.subnet_ipv4_cidr` | CIDR for the automatically created tenant Subnet | String | Required within `defaults`; immutable | Canonical IPv4 CIDR, contained by the default VirtualNetwork CIDR, and non-overlapping with sibling Subnets. |
| `spec.defaults.virtual_network_ipv6_cidr` | Legacy IPv6 default field | String | Legacy optional field; rejected in new requests | Retained for compatibility only; it must not be supplied or silently dual-stacked. |
| `spec.defaults.subnet_ipv6_cidr` | Legacy IPv6 default field | String | Legacy optional field; rejected in new requests | Retained for compatibility only; it must not be supplied or silently dual-stacked. |
| `spec.defaults.ingress_rules` / `egress_rules` | Legacy default SecurityRule lists | List of `SecurityRule` | Legacy compatibility fields | New canonical requests use the SecurityGroup rule model. Legacy values are accepted only when they can be represented as supported IPv4 rules. |
| `spec.defaults.enable_nat_gateway` | Requests automatic default NATGateway onboarding | Boolean | Optional; default `false`; immutable | `true` is valid only when the selected manager combination supports NATGateway. |
| `status.state` | Current NetworkClass lifecycle state | `NetworkClassState` | Output-only; default `UNSPECIFIED` | Allowed values are `UNSPECIFIED`, `PENDING`, `READY`, and `FAILED`. |
| `status.message` | Human-readable lifecycle diagnostic | String | Output-only; empty when no diagnostic exists | Not a stable machine-readable error code. |
| `status.hub` | Hub placement for reconciliation | String | Private output-only; sticky for the resource lifetime | Must identify the deployment's single configured networking hub. |

NetworkClass is accepted only after the provider-owned connected
reachability prerequisites are satisfied.

### VirtualNetwork API

VirtualNetwork is tenant-owned and provides an infrastructure-agnostic IP
domain. It can be used by VMaaS, CaaS, and BMaaS when the selected manager
combination supports the workload.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists VirtualNetworks visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one VirtualNetwork and its resolved NetworkClass, CIDR, state, and hub. |
| `Create` | Tenant or provider | Validates the resolved class and IPv4 CIDR, then creates the resource in `PENDING` state. |
| `Delete` | Tenant or provider | Deletes the VirtualNetwork only after Subnet, SecurityGroup, NATGateway, and workload references are removed. |
| `Update` | Not supported | The class, CIDR, implementation strategy, metadata, and effective configuration are immutable. |
| Private reconciliation | Networking controller | Updates only state, diagnostics, hub placement, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.network_class` | Provider-resolved class implementing the network | `NetworkClassReference` | Provider/private; omitted input resolves the single deployment default; immutable | Tenants cannot select a different class. The resolved class must be `READY`. |
| `spec.ipv4_cidr` | Tenant VirtualNetwork address space | String | Required by this IPv4 contract; immutable | Canonical IPv4 CIDR with host bits zero. Cross-tenant overlap is allowed only because backend isolation is guaranteed. |
| `spec.implementation_strategy` | Provider-resolved backend strategy | String | Output-only/private; immutable | Derived from the deployment NetworkClass. It is never tenant input. Deployment placement is provider-owned and is not a tenant API field. |
| `status.state` | Lifecycle readiness | `VirtualNetworkState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, `DELETING`, or `DELETE_FAILED` as defined by the resource lifecycle. |
| `status.message` | Human-readable lifecycle diagnostic | String | Output-only; absent/empty when no diagnostic exists | Not a stable machine-readable error code. |
| `status.hub` | Hub placement for reconciliation | String | Output-only; sticky for the resource lifetime | The single configured networking hub owns the CR placement. |

Create rejects an absent or non-ready NetworkClass and persists the network in
`PENDING` until the selected manager reports the segment ready. Delete is
blocked while Subnets, SecurityGroups, NATGateways, or workload references
remain.

### Subnet API

Subnet is tenant-owned and is always a child of one VirtualNetwork.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists Subnets visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one Subnet with its parent reference, CIDR, state, and hub. |
| `Create` | Tenant or provider | Validates parent readiness, containment, and sibling non-overlap before persisting the Subnet. |
| `Delete` | Tenant or provider | Deletes the Subnet only when no attachment, workload, or other child reference remains. |
| `Update` | Not supported | Parent, CIDR, metadata, and effective networking configuration are immutable. |
| Private reconciliation | Networking controller | Updates only state, diagnostics, hub placement, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.virtual_network` | Parent VirtualNetwork | `VirtualNetworkLocalReference` | Required; immutable | Parent must exist, be `READY`, and be in the same tenant/project scope. |
| `spec.ipv4_cidr` | Subnet address range | String | Required by this IPv4 contract; immutable | Canonical IPv4 CIDR, contained entirely by the parent VN, and non-overlapping with every sibling Subnet. |
| `spec.ipv6_cidr` | Legacy IPv6 address range | String | Legacy compatibility field; rejected in new requests | IPv6 and dual-stack are outside this contract. |
| `status.state` | Lifecycle readiness | `SubnetState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, `DELETING`, or `DELETE_FAILED`. |
| `status.message` | Human-readable lifecycle diagnostic | String | Output-only | Explains failed validation or backend provisioning. |
| `status.hub` | Hub placement for reconciliation | String | Output-only; sticky | Uses the deployment's single networking hub. |

### SecurityGroup API

SecurityGroup is tenant-owned and scoped to one VirtualNetwork. Legacy
direction-specific fields remain readable for compatibility; the unified
canonical rule representation is described below.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists SecurityGroups visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one SecurityGroup, including its immutable effective rule representation. |
| `Create` | Tenant or provider | Validates the parent VirtualNetwork and canonical or legacy rules before persistence. |
| `Delete` | Tenant or provider | Deletes the group only when no workload attachment references it; the system fallback group is provider-managed. |
| `Update` | Not supported | Parent, rules, metadata, and effective policy are immutable; replacement requires delete and create. |
| Private reconciliation | Networking controller | Updates only state, diagnostics, hub placement, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.virtual_network` | VirtualNetwork whose workloads may use the group | `VirtualNetworkLocalReference` | Required; immutable | Parent must be `READY` and in the same scope. |
| `spec.ingress` | Legacy inbound rule list | List of `SecurityRule` | Legacy input/read compatibility; immutable after create | Cannot be combined with canonical `rules`; only representable IPv4 rules are accepted. |
| `spec.egress` | Legacy outbound rule list | List of `SecurityRule` | Legacy input/read compatibility; immutable after create | Same compatibility rules as `ingress`. |
| `spec.rules` | Canonical tenant firewall rules | List of `SecurityGroupRule` | Required for tenant-created groups; immutable | A tenant-created group has at least one rule. The system-created fallback group may be empty. Duplicates and conflicting equal-specificity rules are rejected. |
| `status.state` | Lifecycle readiness | `SecurityGroupState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, `DELETING`, or `DELETE_FAILED`. |
| `status.message` | Human-readable lifecycle diagnostic | String | Output-only | Reports invalid rule or parent readiness failures. |

#### SecurityGroupRule fields

| Field | Meaning | Type | Presence and validation |
|---|---|---|---|
| `action` | Allow or deny matching traffic | Enum | Required; `ALLOW` or `DENY`; unspecified/unknown rejected. |
| `direction` | Inbound or outbound direction | Enum | Required; `INGRESS` or `EGRESS`. |
| `protocol` | Protocol match | Enum | Required; `TCP`, `UDP`, `ICMP`, or `ANY`. |
| `port` | Single protocol port | Integer | Required for TCP/UDP, omitted for ICMP/ANY, range `1..65535`; port ranges are unsupported. |
| `source_cidr` / `destination_cidr` | Remote address match | Exactly one string | Exactly one canonical IPv4 CIDR. Ingress uses `source_cidr`; egress uses `destination_cidr`. |
| Rule evaluation | Effective behavior of multiple rules | Policy, not a field | Provider baseline is always present and is not exposed in the tenant group. Most-specific matching tenant rule wins; equal-specificity conflicts are rejected. |

### ExternalIPPool API

ExternalIPPool is provider-managed and deployment-scoped. One pool may serve
all workload resource types.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Provider or authorized tenant reader | Lists pools visible in the provider scope; tenants do not select arbitrary pool ranges. |
| `Get` | Provider or authorized tenant reader | Returns one pool and its immutable ranges, family, strategy, and allocation counters. |
| `Create` | Provider control plane | Creates a pool only from provider-authorized IPv4 ranges and a supported implementation strategy. |
| `Delete` | Provider control plane | Deletes a pool only after all ExternalIP allocations are released. |
| `Update` | Not supported | Ranges, family, strategy, metadata, and allocation policy are immutable. |
| Private reconciliation | Networking controller | Updates only lifecycle state, diagnostics, hub placement, counters, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.cidrs` | Address ranges available for allocation | List of strings | Required; immutable | Current contract supports exactly one canonical IPv4 CIDR. The range must be provider-authorized and must not overlap another allocation pool. |
| `spec.ip_family` | Address family of all pool ranges | `IPFamily` | Required; immutable | Must be `IPV4`; unspecified, IPv6, and mixed-family requests are rejected. |
| `spec.implementation_strategy` | Provider-selected address advertisement strategy | String | Output-only; immutable | Derived by the provider; current supported strategy is the configured manager's supported implementation. |
| `status.state` | Pool lifecycle | `ExternalIPPoolState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, `DELETING`, or `DELETE_FAILED`. |
| `status.message` | Pool lifecycle diagnostic | String | Output-only | Explains allocation backend readiness or failure. |
| `status.hub` | Hub placement | String | Output-only; sticky | Uses the deployment's single networking hub. |
| `status.total` | Total usable addresses | Integer | Output-only | Computed from the supported CIDR, excluding unusable addresses. |
| `status.allocated` | Addresses allocated to ExternalIP resources | Integer | Output-only | Never exceeds `total`. |
| `status.available` | Addresses available for allocation | Integer | Output-only | `total - allocated`; zero means new ExternalIP creates fail for capacity. |

### ExternalIP API

ExternalIP is tenant-owned when explicitly created and is also created by the
provider transaction for automatic external access.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists ExternalIPs visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one ExternalIP with allocation state, address, pool, attachment, and attribution status. |
| `Create` | Tenant or provider, or parent controller | Allocates from the selected provider pool; automatic parent creation may create it atomically in `PENDING` state. |
| `Delete` | Tenant or provider, subject to ownership | Deletes only an unattached ExternalIP; an attached address must be detached first, including during parent finalization. |
| `Update` | Not supported | Pool, metadata, address ownership, and allocation identity are immutable. |
| Private reconciliation | Networking controller | Updates only allocation state, address, attachment attribution, timestamps, diagnostics, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.pool` | Pool from which the address is allocated | `ExternalIPPoolReference` | Required; immutable | Pool must be `READY`, visible in the permitted scope, IPv4, and have capacity. Tenants cannot provide an arbitrary address. |
| `status.state` | Allocation lifecycle | `ExternalIPState` | Output-only | `UNSPECIFIED`, `PENDING`, `ALLOCATED`, `FAILED`, or `DELETING`. |
| `status.message` | Allocation diagnostic | String | Output-only | Explains allocation failure or pending state. |
| `status.address` | Allocated IPv4 address | String | Output-only; empty until `ALLOCATED`, stable thereafter | Must be canonical IPv4 and belong to the pool CIDR. |
| `status.pool` | Resolved pool identifier | String | Output-only | Mirrors `spec.pool`; cannot change. |
| `status.attached` | Whether a ready attachment consumes the address | Boolean | Output-only; default `false` | An attached ExternalIP cannot be deleted. |
| `status.hub` | Hub placement | String | Output-only; sticky | Uses the deployment's single networking hub. |
| `status.attribution` | Settled target attribution | ExternalIPAttribution | Output-only | Controller-populated only. |
| `status.attachment_transition_time` | Time attachment attribution changed | Timestamp | Output-only | RFC 3339/UTC timestamp. |
| `status.state_transition_time` | Time allocation state changed | Timestamp | Output-only | RFC 3339/UTC timestamp. |

### ExternalIPAttachment API

ExternalIPAttachment binds one allocated ExternalIP to one target. A Cluster
attachment may be created before the Cluster is ready; it remains `PENDING`
until the target VIP is available. Automatic parent-resource provisioning may
also create the ExternalIP and attachment atomically in `PENDING` state.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists attachments visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one immutable target binding and its resolved address and lifecycle state. |
| `Create` | Tenant or provider, or parent controller | Validates exactly one target and creates a binding; a Cluster target may remain pending until its VIP exists. |
| `Delete` | Tenant or provider, or parent controller | Removes DNAT attribution before releasing the ExternalIP; parent finalizers use this ordering automatically. |
| `Update` | Not supported | ExternalIP, target, endpoint, metadata, and effective DNAT configuration are immutable. |
| Private reconciliation | Networking controller | Updates only binding state, resolved address, diagnostics, timestamps, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.external_ip` | Address being attached | `ExternalIPLocalReference` | Required; immutable | Must reference an `ALLOCATED`, unconsumed ExternalIP, except the documented internal auto-provisioning transaction. |
| `spec.compute_instance` | ComputeInstance DNAT target | Typed reference | Exactly one target arm; immutable | Target must exist in scope and expose its resolved attachment address before DNAT. |
| `spec.cluster` | Cluster DNAT target | Typed reference | Exactly one target arm; immutable | Target may be pending; controller waits for the selected VIP. |
| `spec.baremetal_instance` | BaremetalInstance DNAT target | Typed reference | Exactly one target arm; immutable | Target must exist in scope and expose its discovered IPv4 address before DNAT. |
| `spec.target_endpoint` | Cluster endpoint receiving DNAT | `ExternalIPAttachmentEndpoint` | Immutable; required for Cluster, `UNSPECIFIED` otherwise | Only `API` or `INGRESS` is valid for Cluster. |
| `status.state` | Binding lifecycle | `ExternalIPAttachmentState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, or `DELETING`. |
| `status.external_ip_address` | Address mirrored from ExternalIP | IPv4 address | Output-only; empty until ready | Must match the referenced ExternalIP status. |
| `status.message` | Binding diagnostic | String | Output-only | Explains pending target discovery or failure. |
| `status.hub` | Hub placement | String | Output-only; sticky | Uses the deployment's single networking hub. |
| `status.state_transition_time` | Time binding state changed | Timestamp | Output-only | RFC 3339/UTC timestamp. |

### NATGateway API

NATGateway provides outbound SNAT for every Subnet in one VirtualNetwork. Only
one gateway is allowed per VN, and an ExternalIP cannot be shared with an
ExternalIPAttachment.

#### Methods

| Method | Caller | Contract |
|---|---|---|
| `List` | Tenant or provider | Lists NATGateways visible in the caller's tenant/project or provider scope. |
| `Get` | Tenant or provider | Returns one gateway with its immutable VirtualNetwork and ExternalIP references and lifecycle state. |
| `Create` | Tenant or provider | Validates one-ready-gateway-per-VN, ExternalIP exclusivity, and manager capability before persistence. |
| `Delete` | Tenant or provider | Removes SNAT only after dependent egress operations have drained and the gateway reference is released. |
| `Update` | Not supported | VirtualNetwork, ExternalIP, metadata, and effective SNAT configuration are immutable. |
| Private reconciliation | Networking controller | Updates only lifecycle state, diagnostics, hub placement, timestamps, and finalizers. |

#### Fields

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `spec.virtual_network` | VirtualNetwork whose egress is translated | `VirtualNetworkLocalReference` | Required; immutable | Parent must be `READY`; one NATGateway per VN. |
| `spec.external_ip` | SNAT source address | `ExternalIPLocalReference` | Required; immutable | ExternalIP must be `ALLOCATED`, same scope, and unconsumed. K8s-only deployments reject NATGateway creation when unsupported. |
| `status.state` | SNAT lifecycle | `NATGatewayState` | Output-only | `UNSPECIFIED`, `PENDING`, `READY`, `FAILED`, or `DELETING`. |
| `status.message` | SNAT diagnostic | String | Output-only | Explains dependency or backend failure. |
| `status.hub` | Hub placement | String | Output-only; sticky | Uses the deployment's single networking hub. |
| `status.state_transition_time` | Time gateway state changed | Timestamp | Output-only | RFC 3339/UTC timestamp. |

### ComputeInstance networking API

This subsection covers only the networking fields on ComputeInstance. The
current unified field is the list-shaped `network_attachments` field; the
field remains repeated for compatibility but accepts at most one virtual NIC
attachment.

#### Methods

ComputeInstance itself follows its service-specific create/read/update/delete
contract for non-network fields. The networking fields below are
create-time-only under this design: a network change requires replacing the
ComputeInstance. Automatic ExternalIP children are cleaned up in attachment-
then-IP order when the parent finalizer performs that documented cleanup.

| Method | Caller | Networking contract |
|---|---|---|
| `List` | Tenant or provider | Returns the visible ComputeInstance resources with their resolved networking fields and discovered addresses. |
| `Get` | Tenant or provider | Returns one ComputeInstance with its resolved attachment, status, and any auto-created ExternalIP children visible to the caller. |
| `Create` | Tenant or provider | Resolves the documented default attachment, validates the single-NIC constraint, and creates any requested ExternalIP children in the parent transaction. |
| `Delete` | Tenant or provider | Removes auto-created ExternalIPAttachment and ExternalIP children in dependency order before completing parent deletion. |
| `Update` | Not supported for networking fields | A network change requires replacing the ComputeInstance; non-network fields remain governed by the service-specific API. |

#### Fields

| Field | Meaning | Type | Presence/default/mutability | Validation |
|---|---|---|---|---|
| `spec.network_attachments` | VM virtual NIC attachment | List of `ComputeNetworkAttachment` | Optional; omitted/empty resolves tenant defaults; immutable after create | Zero or one entry is accepted. The entry must reference a `READY` Subnet; its resolved attachment belongs to one VN. More than one entry is rejected. |
| `ComputeNetworkAttachment.subnet` | Subnet for one virtual NIC | `SubnetLocalReference` | Required after resolution; immutable | Must be visible, `READY`, and in the effective tenant scope. |
| `ComputeNetworkAttachment.security_groups` | Groups applied to one virtual NIC | List of `SecurityGroupLocalReference` | Optional; empty resolves the tenant default group; immutable | Every group must be `READY`, same-VN, and unique. |
| `spec.auto_external_ip_attachment` | Requests automatic ExternalIP and attachment creation | Boolean | Default `false`; immutable | When true, the parent transaction creates the Pending children atomically and the controller waits for allocation and discovered VM IP. |
| `status.compute_network_attachment_statuses` | Runtime IP for the resolved VM attachment | List of `ComputeNetworkAttachmentStatus` | Output-only; empty until discovery; cardinality matches the resolved attachment | The status entry maps to the sole attachment and reports canonical IPv4. |
| `ComputeNetworkAttachmentStatus.subnet_ref` | Resolved Subnet identifier | String | Output-only | Must match the resolved attachment. |
| `ComputeNetworkAttachmentStatus.ip_address` | DHCP/overlay-discovered VM address | IPv4 address | Output-only; empty until discovery | Must be canonical IPv4. |

### Cluster networking API

Cluster networking has two separate concepts: `spec.network` configures the
cluster-internal pod/service ranges, while `spec.network_attachment` connects
all node sets to one tenant Subnet.

#### Methods

Cluster create resolves omitted networking defaults. The networking fields are
immutable after creation; changing them requires replacing the Cluster. Read
and list expose the resolved attachment and output-only endpoint status.

| Method | Caller | Networking contract |
|---|---|---|
| `List` | Tenant or provider | Returns visible Clusters with their resolved networking fields and endpoint status. |
| `Get` | Tenant or provider | Returns one Cluster with its resolved attachment and discovered API/ingress endpoints. |
| `Create` | Tenant or provider | Resolves cluster-network defaults, validates the single attachment, and creates any requested ExternalIP children in the parent transaction. |
| `Delete` | Tenant or provider | Removes auto-created ExternalIPAttachment and ExternalIP children in dependency order before completing parent deletion. |
| `Update` | Not supported for networking fields | A network change requires replacing the Cluster; non-network fields remain governed by the CaaS API. |

#### Fields

| Field | Meaning | Type | Presence/default/mutability | Validation |
|---|---|---|---|---|
| `spec.network` | Cluster-internal CNI ranges | `ClusterNetwork` | Optional; immutable; omitted child fields use platform defaults | Pod/service CIDRs are canonical IPv4 and are not tenant fabric Subnets. |
| `ClusterNetwork.pod_cidr` | Pod network range | IPv4 CIDR | Default `10.128.0.0/14`; immutable after resolution | Must be valid and non-overlapping with the service range and provider-reserved ranges. |
| `ClusterNetwork.service_cidr` | Service network range | IPv4 CIDR | Default `172.30.0.0/16`; immutable after resolution | Must be valid and non-overlapping with the pod range and provider-reserved ranges. |
| `spec.network_attachment` | Single tenant attachment shared by all node sets | `ClusterNetworkAttachment` | Optional parent; omitted resolves tenant defaults; immutable | A present message must contain `subnet`; only an empty `security_groups` list may default inside it. |
| `ClusterNetworkAttachment.subnet` | Shared tenant Subnet | `SubnetLocalReference` | Required when message is present; immutable | Must reference a `READY` Subnet in the effective tenant scope. |
| `ClusterNetworkAttachment.security_groups` | Groups applied to all node-set fabric interfaces | List of `SecurityGroupLocalReference` | Optional; empty selects tenant default; immutable in networking contract | Groups must be `READY`, same-VN, and unique. |
| `spec.auto_external_ip_attachment` | Requests API and ingress ExternalIP children | Boolean | Default `false`; immutable | When true, creates two Pending ExternalIPs and attachments atomically. |
| `status.api_endpoint` | Internal API VIP used as DNAT target | IPv4 address | Empty until MetalLB/CaaS discovery | Not the external `api_url`; controller-populated only. |
| `status.ingress_endpoint` | Internal ingress VIP used as DNAT target | IPv4 address | Empty until MetalLB/CaaS discovery | Not the external console URL; controller-populated only. |

### BaremetalInstance networking API

BaremetalInstance networking uses one physical interface attachment. The
repeated field is retained for compatibility, but the current BMaaS contract
accepts at most one attachment and treats it as the primary attachment.

#### Methods

BaremetalInstance create resolves omitted networking defaults. Network
attachment fields and `auto_external_ip_attachment` are immutable after
creation; a change requires replacing the BaremetalInstance. Non-network
provisioning fields remain governed by the BMaaS design.

| Method | Caller | Networking contract |
|---|---|---|
| `List` | Tenant or provider | Returns visible BaremetalInstances with their resolved attachment and discovered address status. |
| `Get` | Tenant or provider | Returns one BaremetalInstance with its resolved attachment, interface, and address status. |
| `Create` | Tenant or provider | Resolves the default fabric port, validates the single-NIC constraint, and creates any requested ExternalIP children in the parent transaction. |
| `Delete` | Tenant or provider | Removes auto-created ExternalIPAttachment and ExternalIP children in dependency order before completing parent deletion. |
| `Update` | Not supported for networking fields | A network change requires replacing the BaremetalInstance; non-network fields remain governed by the BMaaS API. |

#### Fields

| Field | Meaning | Type | Presence/default/mutability | Validation |
|---|---|---|---|---|
| `spec.network_attachments` | Physical NIC-to-Subnet attachment | List of `BareMetalNetworkAttachment` | Optional; omitted/empty resolves tenant defaults; immutable in this contract | Zero or one entry is accepted. The entry uses one VN and is the primary attachment. More than one entry is rejected. |
| `BareMetalNetworkAttachment.subnet` | Subnet connected to one physical NIC | `SubnetLocalReference` | Required after resolution; immutable | Must be `READY` and in the effective tenant scope. |
| `BareMetalNetworkAttachment.security_groups` | Groups applied to one physical NIC | List of `SecurityGroupLocalReference` | Optional; empty resolves tenant default; immutable in this contract | Groups must be `READY`, same-VN, and unique. |
| `BareMetalNetworkAttachment.interface` | Physical port selected for the attachment | String | Omitted selects the first valid fabric-role port; immutable | Must identify a valid non-lifecycle port from the effective hardware profile. |
| `BareMetalNetworkAttachment.primary` | Compatibility marker for the default-route and external-access attachment | Boolean | Optional; omitted or `true` means primary; immutable | `false` is rejected because only one attachment is supported. |
| `spec.auto_external_ip_attachment` | Requests automatic ExternalIP and attachment creation | Boolean | Default `false`; immutable | Parent transaction creates Pending children; controller waits for allocation and DHCP discovery. |
| `status.network_attachment_statuses` | Runtime state per physical attachment | List of `BareMetalNetworkAttachmentStatus` | Output-only; empty until DHCP lease discovery; cardinality matches resolved attachments | Entries must correspond to resolved interfaces and report canonical IPv4. |
| `BareMetalNetworkAttachmentStatus.interface` | Resolved physical interface | String | Output-only | Must match the selected hardware port. |
| `BareMetalNetworkAttachmentStatus.subnet_ref` | Resolved Subnet identifier | String | Output-only | Legacy status representation; must match the resolved attachment. |
| `BareMetalNetworkAttachmentStatus.ip_address` | DHCP-discovered tenant address | IPv4 address | Output-only; empty until lease discovery | Canonical IPv4 only. |
| `BareMetalNetworkAttachmentStatus.primary` | Resolved primary designation | Boolean | Output-only | Mirrors the resolved attachment. |

The `interface` selector is resolved against the effective
`BareMetalInstanceType` port catalog. `fabric` ports are tenant-network
eligible; `lifecycle` ports are reserved for provisioning and are rejected.
When the selector is omitted, BMaaS chooses the first valid fabric port. CaaS
resolves its worker fabric interface from each node set's
`BareMetalInstanceType` rather than exposing that selector to the tenant.

### HostType API

HostType is a provider/system hardware catalog retained for inventory and
legacy consumers. Current BMaaS and CaaS attachment resolution uses the
tenant-facing `BareMetalInstanceType` and its `network_ports`; HostType is not
a second source of truth for workload networking. This subsection defines
only the fields that remain relevant to provider-side networking. Virtual-
machine HostTypes have no physical interfaces. Bare-metal HostTypes have an
ordered interface list.

#### Methods

| Method | Caller | Networking contract |
|---|---|---|
| `List` | Provider or private controller | Lists HostTypes available for provider-side inventory and legacy consumers. |
| `Get` | Provider or private controller | Returns the immutable interface catalog for provider-side inventory; it does not override `BareMetalInstanceType.network_ports`. |
| `Create` / `Delete` | Provider control plane | Catalog lifecycle is owned by the HostType API; deletion is blocked while a provider workflow requires the profile. |
| `Update` | Not a networking operation | Catalog mutation cannot mutate existing Cluster or BaremetalInstance attachments; this design exposes no networking update path. |

#### Fields used by networking

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `id` | Stable HostType identifier | String | Server-assigned, immutable | Must be unique. |
| `metadata` | Resource metadata | `Metadata` | Established by the owning catalog API; not a networking input | Networking controllers treat it as opaque. |
| `title` | Short hardware-profile name | String | Provider-set | Human-readable single-line text. |
| `description` | Long hardware-profile description | Markdown string | Provider-set | Must follow platform Markdown rules. |
| `interfaces` | Physical ports available on the profile | List of `NetworkInterface` | Provider-set; ordered | Empty for VM profiles; non-empty for BM profiles. The first interface for a role is the legacy provider-side default. |
| `NetworkInterface.name` | Stable interface identifier | String | Required; unique within the HostType; immutable for provider-side resolution | Names such as `data-0` and `mgmt-0` are opaque identifiers. |
| `NetworkInterface.role` | Intended traffic role | String | Required; provider-set | `fabric`, `management`, `storage`, and `lifecycle` are conventions, not an enforced enum. `lifecycle` is not tenant-attachable. |
| `NetworkInterface.description` | Human-readable interface description | String | Optional provider-set | Informational only. |

### BareMetalInstanceType API

BareMetalInstanceType is the tenant-visible catalog of bare-metal hardware.
Networking consumes its ordered `network_ports` list; CPU, memory, disk, and
accelerator fields remain defined by the BareMetalInstanceType API.

#### Methods

| Method | Caller | Networking contract |
|---|---|---|
| `List` | Tenant or provider | Lists hardware profiles and their discoverable network ports. |
| `Get` | Tenant or provider | Returns the profile and the network-port catalog used to validate `BareMetalNetworkAttachment.interface`. |
| `Create` / `Delete` | Provider control plane | Catalog lifecycle is owned by the BareMetalInstanceType API; deletion is blocked while a provisioning workflow requires the profile. |
| `Update` | Not a networking operation | Catalog mutation cannot mutate existing BaremetalInstance attachments; this design exposes no networking update path. |

#### Fields used by networking

| Field | Meaning | Type | Presence and mutability | Validation |
|---|---|---|---|---|
| `id` | Stable hardware-profile identifier | String | Server-assigned, immutable | Must be unique. |
| `metadata` | Resource metadata | `Metadata` | Established by the owning catalog API; not a networking input | Networking controllers treat it as opaque. |
| `spec.hardware.network_ports` | Physical network ports available on the hardware profile | List of `BareMetalNetworkPortSpec` | Optional at the generic catalog layer; immutable for a resolved BaremetalInstance | Port names must be unique. A usable networking profile must expose at least one `fabric` port. |
| `BareMetalNetworkPortSpec.name` | Port identifier selected by an attachment | String | Required; unique within the profile | Must be non-empty and stable across inventory, fabric-manager, and DHCP-lease lookup. |
| `BareMetalNetworkPortSpec.role` | Port traffic role | String | Required; provider-set | `fabric`, `management`, `storage`, and `lifecycle` are conventions. `lifecycle` is not tenant-attachable. |
| `BareMetalNetworkPortSpec.type` | Physical link type | String | Required; provider-set | Examples include `Ethernet` and `InfiniBand`; non-empty. |
| `BareMetalNetworkPortSpec.speed` | Link speed | String | Required; provider-set | Examples include `1Gbps`, `10Gbps`, and `100Gbps`; non-empty. |

#### Reference and lifecycle rules

For every resource above, validation proceeds before backend dispatch: resolve
typed references, apply only the documented defaults, validate scope and
readiness, validate IPv4 and cardinality, then persist the complete effective
spec. A rejected create persists nothing. Controllers requeue while an
allowed dependency is `PENDING`; they never mark a resource `READY` before
all required backend operations and discovered addresses are valid.

The provider-owned baseline connectivity, single-hub placement, IPv4-only
boundary, and create/read/delete immutability rules in the surrounding design
are normative parts of every subsection above.

## Proposal

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for the deployment. Tenants never interact with it. One
NetworkClass per deployment.

#### Two Managers

OSAC networking is handled by two managers:

- **Fabric Manager** — a single product (e.g., Netris, Neutron) that manages
  all physical networking: tenant isolation, ACLs, IP allocation, DNAT, SNAT,
  and inter-subnet L3 routing within a VirtualNetwork. The physical fabric is
  one infrastructure — one controller manages it all. When a VN has multiple
  subnets, the fabric manager provides the L3 gateway for each subnet and
  routes between them automatically.

- **K8s Manager** (optional) — handles everything needed to make VMs part of
  the fabric: creates the K8s overlay (e.g., CUDN with LocalNet) and bridges
  it to the fabric segment. Needed for deployments that host VMs — once VMs
  are on the fabric, the fabric manager handles them identically to
  bare-metal servers. MetalLB IPAddressPool CRs for CaaS VIP allocation are
  created by the Subnet controller at subnet creation time (gated on
  `NetworkClass.spec.vip_prefix_length`), independent of the k8sManager.

#### Why Two Managers?

The fabric is one product. You cannot have Netris handling isolation and
Neutron handling ACLs on the same switches — splitting into per-action
drivers does not reflect how physical networking works. A single
`fabricManager` field captures this reality.

The K8s side is a separate concern: it bridges the OVN overlay to the
physical fabric. The mechanism depends on the deployment — see
[How VMs Join the Fabric](#how-vms-join-the-fabric) for the available
options. The goal is always the same: make VMs part of the fabric. A single
`k8sManager` field captures this.

Once VMs are on the fabric, the fabric manager handles everything for all
resource types uniformly. There is no VM-vs-BM distinction for security,
ExternalIP, DNAT, or SNAT.

#### NetworkClass Examples

**Netris + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: moc-site-1
spec:
  fabricManager: netris
  k8sManager: cudn_localnet
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

**Neutron + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: bos-site-1
spec:
  fabricManager: neutron
  k8sManager: cudn_localnet
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

**BM-only deployment (no VMs):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: gpu-site-1
spec:
  fabricManager: netris
capabilities:
  supportsIpv4: true
  supportsIpv6: false
  supportsDualStack: false
```

#### Capabilities

Capabilities are **inferred from the assigned managers** and published in
the NetworkClass `capabilities` field — the provider does not set them
manually. The operator computes the intersection of capabilities declared by
the assigned manager ConfigMaps and populates `capabilities` automatically. For
a BM-only NetworkClass without a `k8sManager`, the absent manager is excluded
from this intersection; only the configured `fabricManager` contributes
capabilities.

The supported deployment boundary is IPv4-only. Managers must advertise the
`ipv4` capability. IPv6 and dual-stack manager registrations are rejected,
and NetworkClass capability output must be `supportsIpv4: true` with
`supportsIpv6: false` and `supportsDualStack: false`.

| Capability | Type | Meaning |
|-----------|------|---------|
| `supportsIpv4` | bool | IPv4 addressing is available; `true` for OSAC networking |
| `supportsIpv6` | bool | IPv6 addressing; always `false` |
| `supportsDualStack` | bool | IPv4 + IPv6 addressing; always `false` |
| `dpuSupport` | bool | DPU-accelerated networking available |

The set of capabilities is defined by the operator and is fixed — adding a
new capability requires an operator update. Managers declare which
capabilities they support; they cannot define custom capabilities.

#### Manager Registration (ConfigMap)

Each manager ships a ConfigMap declaring its type and capabilities. These
ConfigMaps are deployed as part of the OSAC installation alongside the
manager's Ansible roles.

**Fabric managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fabric-manager-netris
  namespace: osac
  labels:
    osac.openshift.io/network-fabric-manager: "true"
data:
  name: netris
  description: "Netris SDN — tenant isolation, ACL, IPAM, DNAT, SNAT"
  capabilities: "ipv4"
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fabric-manager-neutron
  namespace: osac
  labels:
    osac.openshift.io/network-fabric-manager: "true"
data:
  name: neutron
  description: "OpenStack Neutron — tenant isolation, IPAM, floating IPs"
  capabilities: "ipv4"
```

**K8s managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-cudn-localnet
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: cudn_localnet
  description: "CUDN with LocalNet — bridges OVN overlay to physical fabric"
  capabilities: "ipv4"
```

The operator discovers managers by listing ConfigMaps with the appropriate
labels. When a NetworkClass is created, the operator validates each manager
assignment against the corresponding ConfigMap. Adding a new manager means
deploying a new ConfigMap and Ansible role — no API or operator changes
needed.

### How VMs Join the Fabric

OSAC runs VMs on OpenShift using KubeVirt. Each VM is encapsulated in a pod
whose networking is managed by OVN-Kubernetes. By default, VM IP addresses
exist only within the OVN overlay and are not visible on the physical
fabric. The k8sManager bridges this overlay to the fabric so that VMs
become first-class fabric participants — reachable at their subnet IP from
any other resource on the same fabric segment.

Several mechanisms can achieve this bridging. The k8sManager is pluggable —
different deployments use different mechanisms depending on their
infrastructure and requirements:

**CUDN with LocalNet.** The k8sManager creates a ClusterUserDefinedNetwork
(CUDN) with LocalNet topology, mapping the OVN network directly to a
physical VLAN on the hosting cluster's trunk interface. VMs in this network
are bridged to the fabric at L2 — they share a broadcast domain with
bare-metal servers on the same VLAN. This is the simplest mechanism and
provides full L2 adjacency.

**OVN EVPN.** OVN advertises VM routes to the fabric via BGP EVPN. The
fabric learns VM MAC/IP bindings and can route to them. VMs remain in the
OVN overlay but are reachable from the fabric at L3. This preserves OVN's
per-VM isolation on the same hypervisor while still making VMs fabric
participants. Note: OVN EVPN is not yet GA in OpenShift.

**CUDN with VRF-lite.** The hosting cluster uses VRF (Virtual Routing and
Forwarding) instances to route between the OVN overlay and the fabric. Each
tenant VN maps to a VRF on the host, which peers with the fabric via BGP.
VMs are reachable from the fabric via L3 routing through the VRF. See the
[CUDN with VRF-lite setup guide](/docs/networking/setup-bpg-vrf-lite) for
a working example.

**DPU-based bridging.** SmartNICs (DPUs) offload the OVN-to-fabric bridging
to hardware. The DPU handles packet encapsulation/decapsulation between OVN
and the physical network, providing line-rate bridging without host CPU
overhead.

The choice of mechanism is transparent to tenants — it is configured by the
provider as part of the k8sManager installation. The networking API and
resource model are identical regardless of which mechanism is used. All that
matters is the contract: once the k8sManager has bridged a subnet, VMs on
that subnet are reachable from the fabric at their subnet IP.

### Infrastructure-Agnostic Subnets

VirtualNetwork and Subnet do not carry a scope or service field. Subnets are
infrastructure-agnostic — the dispatcher provisions both the fabric segment
and (if the NetworkClass has a k8sManager) the K8s overlay for every subnet.
Any resource type can be placed on any subnet.

At subnet creation, the dispatcher runs:

1. **Fabric manager** — creates fabric segment (e.g., VLAN, VPC)
2. **K8s manager** (if present) — creates K8s overlay on each hosting
   cluster in the deployment and bridges it to the fabric segment

VMs are placed in the K8s overlay (which is bridged to the fabric), BM
servers and cluster nodes are placed directly on the fabric segment. The
fabric is the single source of truth for multi-tenancy and routing — all
resources, regardless of type, are on the fabric.

### Dispatcher (Operator Composition Logic)

The osac-operator acts as a **dispatcher**: when reconciling any networking
resource, it resolves the NetworkClass and calls the
appropriate managers. Each manager corresponds to an Ansible role — the
dispatcher triggers the appropriate AAP playbook, passing the resource and
context as the event payload.

| Operation | Managers called |
|-----------|----------------|
| VN create/delete | `fabricManager` |
| Subnet create/delete | `fabricManager` + `k8sManager` (per hosting cluster) |
| SecurityGroup create/delete | `fabricManager` |
| ExternalIP alloc/release | `fabricManager` |
| ExternalIPAttachment create/delete | `fabricManager` |
| NATGateway create/delete | `fabricManager` |

Everything except subnet creation is handled by the fabric manager alone.
The k8sManager is only involved at subnet creation (to bridge the overlay)
— after that, VMs are on the fabric and the fabric manager handles them
like any other resource.

The dispatch table above covers **networking resources only**. Compute
resources (ComputeInstance, BaremetalInstance, Cluster) handle per-instance
network attachment through their provisioning operators — see per-service
designs at [VMaaS](/enhancements/OSAC-1435-vmaas-networking),
[CaaS](/enhancements/OSAC-1436-caas-networking),
[BMaaS](/enhancements/OSAC-1437-bmaas-networking).

### Resource Hierarchy

```text
NetworkClass (per deployment, provider-only)

VirtualNetwork (tenant-managed, infrastructure-agnostic)
  ├── Subnet              → fabricManager + k8sManager
  ├── SecurityGroup       → fabricManager
  └── NATGateway          → fabricManager

ExternalIPPool (deployment-scoped, provider-managed)
  └── ExternalIP (tenant-managed) → fabricManager

ExternalIPAttachment (tenant-managed)
                          → fabricManager
                            references an ExternalIP and a target resource
```

### ExternalIPPool

"External" in ExternalIPPool/ExternalIP means **external to the
VirtualNetwork**. In the supported connected deployment boundary, the
provider creates pools with addresses routable in the provider's connected
network. The API does not require Internet reachability, but air-gapped and
disconnected networking deployments are not supported.

ExternalIPPools are provider-managed and deployment-scoped. The fabric
manager handles ExternalIP allocation — one pool serves all resource types.
Each pool uses exactly one canonical IPv4 CIDR. The API's repeated `cidrs`
field is retained for compatibility, but validation rejects an empty list or
more than one entry; IPv6 and dual-stack pools are not supported.
Pool creation requires `spec.ipFamily` to be `IP_FAMILY_IPV4`;
`IP_FAMILY_UNSPECIFIED`, IPv6, and dual-stack values are rejected before
persistence.

#### Address-Family and CIDR Contract

All user-supplied network CIDRs use canonical dotted-decimal IPv4 notation
(`a.b.c.d/prefix`) with host bits zero. A Subnet CIDR must be contained by its
parent VirtualNetwork and sibling Subnet CIDRs must not overlap. Provider and
controller-produced addresses are canonical IPv4 addresses without a CIDR
suffix. Any IPv6, dual-stack, malformed, or non-canonical value is rejected
before persistence or backend dispatch.
All explicit and automatic ExternalIP allocation paths, including per-service
auto-provisioning, must request `IP_FAMILY_IPV4`; `IP_FAMILY_UNSPECIFIED` is
not a valid default for this contract.

### End-to-End Flows

This section shows how the unified networking API works from the tenant's
perspective. The flows are the same regardless of which fabric manager or
K8s manager the provider has deployed.

#### Provider Setup

1. Provider deploys hosting cluster(s) and fabric controller
2. Provider creates NetworkClass for the deployment (provider-only,
   tenants never see it)
3. Provider creates ExternalIPPool:

```bash
osac admin create externalippool \
  --network-class moc-site-1 \
  --cidrs 203.0.113.0/24 \
  --ip-family ipv4 \
  --name external-pool-1
```

The fabric manager registers the IP range in its IPAM for allocation.

#### Networking Setup (Same for All Resource Types)

The tenant creates networking resources. This workflow is identical
regardless of whether the tenant plans to run VMs, clusters, or bare-metal
servers.

**Create VirtualNetwork:**

```bash
osac create virtualnetwork --network-class moc-site-1 --cidr 10.0.0.0/16 \
  --name my-net
```

The fabric manager creates an isolated tenant segment on the fabric.

**Create Subnet:**

```bash
osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 \
  --name my-subnet
```

The fabric manager creates a fabric segment (e.g., VLAN) for the subnet.
If the NetworkClass has a K8s manager, it also creates a K8s overlay on each
hosting cluster and bridges it to the fabric segment. After this step, VMs placed in the
overlay and BM servers with switch ports on the fabric segment are in the
same L2 domain.

**Create SecurityGroup:**

```bash
osac create security-group --virtual-network my-net --name my-sg \
  --ingress "protocol:tcp,port:443,source:0.0.0.0/0"
```

The fabric manager creates ACL rules on the fabric.

#### Resource Creation (Differs by Type)

The networking setup above is shared. Only the resource creation step
differs internally — the tenant CLI experience is the same for all types.

**ComputeInstance (VM):**

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --name my-vm
```

VM is placed in the K8s overlay namespace on a hosting cluster. Because the
overlay is bridged to the fabric, the VM is directly on the fabric segment
and gets an IP from the subnet CIDR.

**BaremetalInstance:**

Bare-metal servers have multiple physical interfaces. The tenant discovers
available network ports via the BareMetalInstanceType API — each
BareMetalInstanceType lists its network ports with name, role, type, speed,
and description (see
[HostType API](#hosttype-api) and
[BareMetalInstanceType API](#baremetalinstancetype-api)). Given the port
identifiers, the tenant specifies which interface to attach to the subnet.
The current BMaaS contract accepts one entry in the repeated
`network_attachments` field, mapping one physical interface to one subnet. If
`interface` is omitted, fulfillment defaults to the first `fabric` port from
`BareMetalInstanceType.network_ports`.

Single interface (simple case):

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=my-subnet,security-groups=my-sg \
  --name my-server
```

The API retains the repeated field for compatibility, but only one attachment
is supported. The fabric manager configures the selected host switch port on
the corresponding fabric segment and the interface gets an IP from the
subnet's CIDR.

Validation rules:
- At most one attachment is accepted
- All referenced subnets must belong to the same VirtualNetwork
- The `interface` must reference a valid port name from the BareMetalInstanceType's
  network ports list

**Cluster:**

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet,security-groups=my-sg \
  --node-set workers=large,size=3 --name my-cluster
```

For v0.2, **CaaS supports BM node sets only**. VM-based cluster node sets
are architecturally possible but deferred. The fulfillment-service resolves
the interface from the BareMetalInstanceType (`fabric_interface` — first port
with role `fabric`) and stores it on the node set. The worker controller passes
that stored value to BMaaS; BMaaS handles the host's network attachment as part
of its provisioning lifecycle.
See [CaaS Networking](/enhancements/OSAC-1436-caas-networking) for the detailed flow.

Cluster nodes have multiple physical interfaces. Unlike BaremetalInstance
(where the tenant specifies interfaces directly), for clusters the
**system** resolves the interface from each node set's BareMetalInstanceType
`network_ports` list.
The tenant specifies which subnet to use (one per cluster); the system maps it to the
correct physical interfaces based on each node set's BareMetalInstanceType.

In all cases, the resource ends up on the fabric. The fabric manager sees
all resources equally — there is no VM-vs-BM distinction.

#### External Access (Same for All Resource Types)

Since all resources are on the fabric, external access operations are
uniform. There is no VM-vs-BM distinction — the fabric manager handles
DNAT and SNAT identically for all resource types.

**Allocate ExternalIP:**

```bash
osac create externalip --pool external-pool-1 --name my-ip
```

The fabric manager allocates an IP from its IPAM (e.g., 203.0.113.45).

**Attach for inbound access (DNAT):**

```bash
# Attach to a VM
osac create externalipattachment --externalip my-ip \
  --compute-instance my-vm --name vm-att

# Attach to a BM server (new target type)
osac create externalipattachment --externalip my-ip \
  --baremetal-instance my-server --name bm-att

# Attach to a cluster API server (new target type + endpoint)
osac create externalipattachment --externalip my-ip \
  --cluster my-cluster --target-endpoint api --name api-att
```

The fabric manager creates a DNAT rule: external IP → resource's subnet IP.
Each resource (ComputeInstance, BaremetalInstance) is associated with one
tenant subnet and has one fabric IP — the DNAT targets that IP directly. The
ExternalIP is attached to the resource, not to a specific interface; the
fabric manager routes to the resource's sole/primary subnet IP.

**Cluster ExternalIPAttachment flow:**

For VMs and BM, the DNAT target is the resource's fabric IP —
straightforward. For clusters, the DNAT target is a service-level VIP
(API server or ingress) that is discovered during cluster provisioning.
The VIP allocation is decoupled from the networking layer:

1. CaaS template creates MetalLB LoadBalancer Services for API server
   and ingress. MetalLB allocates VIPs from its IPAddressPool (created
   by k8s_manager at subnet creation).
2. Template discovers the allocated VIPs and writes them to ClusterOrder
   CR status (`apiEndpoint`, `ingressEndpoint`)
3. Feedback controller syncs VIPs to the Cluster object in the
   fulfillment service as `api_endpoint` and `ingress_endpoint` fields
4. ExternalIPAttachment controller reads the VIP from ClusterOrder
   status → calls fabric manager to create DNAT: external IP →
   internal VIP
5. ExternalIPAttachment transitions to Ready

The tenant can inspect the allocated VIPs:

```bash
osac get cluster my-cluster -o yaml
# api_endpoint: 10.0.5.20
# ingress_endpoint: 10.0.1.50
```

ExternalIPAttachments can be created before or after the cluster. If
created before (Pending state), the controller activates them once the
cluster's endpoint VIPs are available. If created after, the DNAT rule
is configured immediately.

**Auto-provisioning lifecycle (auto_external_ip_attachment):**

Auto ExternalIP attachment provisioning (described in per-service
EPs and [Default Networking](/enhancements/OSAC-1433-default-networking)) is a
two-phase process:

*Phase 1 — synchronous (during the create API call):*

The fulfillment-service validates pool capacity, creates ExternalIP and
ExternalIPAttachment records in PostgreSQL, and decrements pool capacity
— all within the same API transaction. If the pool is exhausted, the
call fails and no resources are persisted (including the parent
resource). Both the ExternalIP and ExternalIPAttachment start in
**Pending** state. The ExternalIPAttachment's target reference is set at
creation time, but the DNAT target IP may not yet be known (the target
resource may still be provisioning).

The fulfillment-service creates the ExternalIPAttachment with the
ExternalIP in Pending state (not yet Allocated). This bypasses the
normal ExternalIPAttachment server validation that requires the
ExternalIP to be Allocated — the auto-provisioning codepath in the
fulfillment-service creates both resources atomically within the same
transaction, so the Allocated check is not needed (the ExternalIP is
guaranteed to exist and will be reconciled by the operator).

*Phase 2 — asynchronous (controller reconciliation):*

Each resource type has an independent fulfillment-service reconciler.
The ExternalIP and ExternalIPAttachment CRs are pushed to the hub
cluster independently — there is no cross-resource ordering in the
reconcilers. The operator-side controllers handle ordering via
precondition checks and requeue:

- fulfillment-service reconcilers push ExternalIP and
  ExternalIPAttachment CRs to the hub cluster (independently, around
  the same time)
- osac-operator ExternalIP controller dispatches to AAP → fabric
  manager allocates an IP address → ExternalIP transitions to
  **Allocated**
- osac-operator ExternalIPAttachment controller checks two
  preconditions before dispatching:
  - **ExternalIP must be Allocated** (have an allocated address). If
    not, the controller requeues.
  - **Target resource must have a known IP.** The required IP depends
    on the target type (see below). If not yet available, the
    controller requeues.
- Once both preconditions are met, the controller dispatches to AAP →
  fabric manager creates the DNAT rule → ExternalIPAttachment
  transitions to **Ready**

*ExternalIPAttachment controller preconditions per target type:*

| Target type | Required precondition | Source of target IP |
|-------------|----------------------|---------------------|
| ComputeInstance | `compute_network_attachment_statuses` populated with primary attachment's `ip_address` | Feedback controller reads KubeVirt VMI network status, writes `ComputeNetworkAttachmentStatus` per attachment |
| Cluster | `status.apiEndpoint` or `status.ingressEndpoint` populated on ClusterOrder CR | MetalLB allocates VIP from IPAddressPool, template discovers and writes to ClusterOrder status |
| BaremetalInstance | `status.networkAttachmentStatuses[].ipAddress` populated for the primary interface | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches port MAC (from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to assigned IP; operator writes to CR status |

The controller uses the existing requeue pattern: if the precondition
is not met, it returns `ctrl.Result{RequeueAfter: interval}` and
retries until the target IP appears. This is the same pattern used
today for the `VirtualMachineReference` check on ComputeInstance
targets.

*IP discovery — DHCP-based host networking:*

All host-side IP assignment uses DHCP. The fabric's DHCP server (managed
by the fabric manager as part of the network segment infrastructure) assigns IPs
to hosts when they boot on the subnet. OSAC does not pre-allocate IPs
or configure host-side networking — DHCP handles IP address, gateway,
prefix, and DNS automatically.

After the host receives its IP via DHCP, the IP is discovered and
written to the resource's CR status for two purposes:
- ExternalIPAttachment controller reads the primary IP for DNAT target
- Tenant visibility (API response includes the allocated IP)

IP discovery mechanism per service type:

| Service | Discovery source | Who writes status | Status field |
|---------|-----------------|-------------------|-------------|
| VMaaS | KubeVirt VMI `status.interfaces[].ipAddress` | osac-operator feedback controller → Signal RPC → fulfillment-service | `ComputeInstanceStatus.compute_network_attachment_statuses[].ip_address` |
| CaaS | Agent CR network status | osac-operator feedback controller → Signal RPC → fulfillment-service | `ClusterOrderStatus.nodeSets[].agents[].ipAddress` (operator-internal) |
| BMaaS | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches port MAC — from the BareMetalHost `osac.openshift.io/interface-macs` annotation — to the DHCP-assigned IP, falling back to server name for named fabric servers (see [BMaaS OQ#4 — Resolved](/enhancements/OSAC-1437-bmaas-networking/design.md#4-how-is-the-hosts-runtime-ip-discovered-after-network-reconfiguration)) | bare-metal-fulfillment-operator dispatches `query_dhcp_lease` → writes to CR status → feedback controller → Signal RPC → fulfillment-service | `BareMetalInstanceStatus.network_attachment_statuses[].ip_address` |

The fabric manager's `move_network_attachment` role is switch-side
only — it moves a host's fabric port from one network segment to another
(`from_vnet_name` → `to_vnet_name`, either side optional). Attach and
detach are the **same primitive**: on provision the port moves from a
**provisioning network** to the tenant subnet's network segment; on deletion it
moves back to the provisioning network. The role operates purely against the
fabric (no Subnet CR lookup) and is keyed on plain segment names, so the caller
resolves a `subnetRef` → tenant segment name and supplies the provisioning
network name from configuration. Detach is a no-op if the port is not on the
named segment, so re-runs and unexpected states are safe.

One role handles both BMaaS (fabric NIC on the provisioning network while the
server is idle so it has internet during metal3 inspection) and CaaS (agent
moving from a provisioning network to the tenant network). The **timing** of the
move differs per service:

- **BMaaS:** Move happens **POST-provisioning** (provision on the provisioning
  network → move to tenant network → reboot so the OS re-DHCPs on the tenant
  network). This achieves isolation-until-ready: the tenant cannot reach the
  server during imaging/first-boot.
- **CaaS:** BMaaS moves the port **POST-OS-provisioning** (the host is provisioned
  on the provisioning network, then the port moves to the tenant network and the
  host reboots before it joins the cluster installation flow).

Once on the tenant network, the host receives an IP from the fabric's DHCP server
automatically. A single AAP job template serves both directions, deriving onboard
(provisioning network → tenant) vs. offboard (tenant → provisioning network) from
the resource's `deletionTimestamp`. See [BMaaS — Provisioning Network and Port
Moves](/enhancements/OSAC-1437-bmaas-networking/design.md#provisioning-network-and-port-moves).

IP discovery for BMaaS is a separate dispatcher call. After
`reconcileProvisioning` completes and the host has received a DHCP
lease, the operator dispatches `query_dhcp_lease` — this role queries
the fabric manager's DHCP lease API for the subnet and matches the
server's port MAC address to find the corresponding DHCP-assigned IP.
Bare-metal hosts are not named fabric servers, so the lease is matched
by NIC MAC, which the operator supplies from the host's
`osac.openshift.io/interface-macs` BareMetalHost annotation; named
fabric servers such as CaaS agents fall back to matching by server name.

*NATGateway controller preconditions:*

The NATGateway controller has two preconditions before dispatching the
SNAT rule creation:

| Precondition | Source |
|-------------|--------|
| Referenced VirtualNetwork must be Ready (fabric segment provisioned) | VirtualNetwork CR status |
| Referenced ExternalIP must be Allocated (have an allocated address) | ExternalIP CR status |

If either precondition is not met, the NATGateway controller requeues.
This prevents dispatching to AAP before the VN's fabric segment exists
(no segment to attach the SNAT rule to) or without a valid SNAT source
address.

*Auto-provisioned resource labeling:*

All auto-created resources receive the label
`osac.openshift.io/auto-created: "true"`. Auto-provisioned
ExternalIPs also receive a parent-resource label
`osac.openshift.io/auto-created-for: <resource-id>` so that the
cleanup logic can find orphaned ExternalIPs directly, even if the
intermediate ExternalIPAttachment has already been deleted.

*Auto-provisioned resource cleanup on parent deletion:*

The parent resource's finalizer uses a phased requeue approach to
ensure correct ordering:

1. Query ExternalIPAttachments labeled `auto-created` targeting
   this resource. Issue delete for each. Requeue.
2. On next reconcile: check if all ExternalIPAttachments are fully
   deleted (including their own finalizers completing the DNAT rule
   removal). If not, requeue.
3. Once all ExternalIPAttachments are gone: query ExternalIPs labeled
   `auto-created-for: <this-resource>`. Issue delete for each.
   Requeue.
4. On next reconcile: check if all ExternalIPs are fully deleted. If
   not, requeue.
5. Once all ExternalIPs are gone: proceed with parent resource
   deletion.

If cleanup fails permanently after a configured retry limit: finalizer is removed,
parent resource deleted, orphaned resources left in cluster. Orphaned
resources are identifiable by the `auto-created-for` label.

**Enable outbound NAT (SNAT):**

```bash
osac create externalip --pool external-pool-1 --name nat-ip
osac create natgateway --virtual-network my-net --externalip nat-ip \
  --name my-nat
```

The fabric manager creates a SNAT rule for the VN: all egress traffic from
the VN's CIDR is source-NATted to the ExternalIP. Applies to all resources
in the VN — VMs, BM servers, cluster nodes — since all are on the fabric.

### Implementation Details

#### Deletion Dependency Guards

When the API layer (fulfillment-service) soft-deletes networking resources,
it accepts the delete as soon as child resources are themselves soft-deleted.
On the operator side, each controller triggers its AAP deprovision job when
it sees a `deletionTimestamp`. If a parent and its children are deleted
near-simultaneously, the parent's deprovision job fires before children
have been fully removed from the infrastructure backend, causing the backend
to reject the parent deletion.

To prevent unnecessary failed jobs and backoff delays, each parent
controller gates its deprovision on the complete removal of child CRs.
The controller lists child CRs referencing the parent before triggering the
AAP deprovision job. If any children still exist on the cluster (regardless
of their own deletion state), the controller requeues with a short interval
(10 seconds) instead of dispatching a doomed job.

| Controller | Gate deprovision on |
|---|---|
| VirtualNetwork | No Subnet, SecurityGroup, or NATGateway CRs with `spec.virtualNetwork` referencing this VNet |
| Subnet | No ComputeInstance CRs with `spec.networkAttachments[].subnetRef` referencing this Subnet; no BareMetalInstance CRs with `spec.networkAttachments[].subnetRef` referencing this Subnet (see [BMaaS Networking](/enhancements/OSAC-1437-bmaas-networking/design.md)) |
| ExternalIP | No ExternalIPAttachment or NATGateway CRs with `spec.externalIP` referencing this EIP |
| ExternalIPPool | No ExternalIP CRs with `spec.pool` referencing this pool |

The full dependency chain (delete order, leaf first):

```text
ComputeInstance / BareMetalInstance (leaf)
  must be gone before --> Subnet
  must be gone before --> ExternalIPAttachment (via auto-cleanup)

ExternalIPAttachment
  must be gone before --> ExternalIP

NATGateway
  must be gone before --> ExternalIP
  must be gone before --> VirtualNetwork

SecurityGroup
  must be gone before --> VirtualNetwork

Subnet
  must be gone before --> VirtualNetwork

ExternalIP
  must be gone before --> ExternalIPPool

VirtualNetwork (delete last)
```

This is the same pattern used during provisioning (e.g., the NATGateway
controller gates provisioning on ExternalIP readiness and VirtualNetwork
readiness) -- applied symmetrically to the deprovision path.

#### NATGateway Scope

One NATGateway per VirtualNetwork. All subnets in the VN use the gateway.
Per-subnet NAT association is a future enhancement.

#### Single-NIC Workload Attachment Constraint

VMaaS, BMaaS, and CaaS currently support at most one tenant network
attachment per workload. VMaaS and BMaaS retain repeated attachment fields
for API compatibility, while CaaS retains its singular field. Requests
with more than one VM or BM attachment are rejected by API validation and by
the corresponding operator CRD. Multi-NIC workload networking is future
scope.

With exactly one attachment, the attachment is the **primary** attachment by
default and determines:

- Which subnet provides the **default gateway** for the resource
- Which subnet IP is used as the **DNAT target** for ExternalIPAttachment
- Which subnet IP is used as the **source** for NATGateway SNAT

**Validation and compatibility:**
- Zero or one attachment is valid
- If one BMaaS attachment exists, its existing `primary` field may be omitted
  or set to `true`; both mean the same default-route behavior. `primary: false`
  is rejected. VMaaS has no primary field, and CaaS has no primary concept.
- Omitted or empty attachment lists receive the resource-specific defaults
  described in [Attachment Presence and Defaulting](#attachment-presence-and-defaulting);
  a supplied attachment receives defaults only for missing fields.
- The complete resolved attachment list and every network-owned field are
  immutable after creation; changing them requires deleting and recreating the
  workload.

**IP assignment:** All resource types receive IPs via DHCP. For VMs,
OVN provides DHCP on the CUDN overlay. For BM servers and CaaS agents,
the fabric's DHCP server assigns IPs on the network segment. The provisioning
template does NOT configure host-side networking (no static IP, gateway,
or DNS configuration) — DHCP handles it automatically.

| Subnet role | IP assignment provides (via DHCP) |
|-------------|---------------------------------------------|
| Sole/primary attachment | IP address + default gateway + DNS |

This ensures the resource has exactly one default route. Additional workload
attachments are not supported in the current API contract.

**ExternalIPAttachment:** The fabric manager creates a DNAT rule to the
resource's sole/primary subnet IP. The tenant does not need to specify an
interface; the single-attachment contract determines the target.

**Cluster networking:** `ClusterNetworkAttachment` is a single attachment
(one subnet for the whole cluster). Multi-NIC for individual cluster nodes is
not supported by the current CaaS contract. The `primary` field does not
apply to `ClusterNetworkAttachment`.

#### Multiple Hosting Clusters Per Deployment

Multiple hosting clusters are supported per deployment. At subnet creation, the
k8sManager creates a K8s overlay on each hosting cluster and bridges it to
the fabric segment. VMs on different hosting clusters share the same subnet
via the fabric.

#### Hub Selection (CR Placement)

The fulfillment-controller creates K8s CRs on the single registered hub
cluster in a supported networking deployment. All networking resources
(VirtualNetwork, Subnet, SecurityGroup, ExternalIPPool, ExternalIP,
ExternalIPAttachment, NATGateway) use that hub. Multi-hub networking
placement, cross-hub resource coordination, and cross-hub network connectivity
are unsupported. The hub assignment remains sticky through `status.hub` for
resource lifecycle and reconciliation.

This boundary applies only to the networking area and does not define hub
behavior for other OSAC areas. The fabric can still span multiple hosting
clusters where the relevant networking feature supports that topology.

#### Cross-VN Communication

VirtualNetworks are isolated. Cross-VN communication (VN Peering) is a
separate enhancement.

#### DNS

DNS is a service-integration concern, not part of the networking API. CaaS
template roles create DNS records. A DNS API is a separate enhancement.

#### BM-Only Deployments

If a NetworkClass has no k8sManager, the deployment does not support VMs.
ComputeInstance creation is rejected if the target NetworkClass has no
k8sManager — there is no K8s overlay to place the VM on.

CaaS clusters work without a k8sManager. MetalLB IPAddressPool creation
is handled by the Subnet controller (gated on
`NetworkClass.spec.vip_prefix_length`), not by the k8sManager. BM-only
CaaS deployments provision clusters with fabric-level networking and
MetalLB VIP allocation without requiring a K8s overlay.

#### CIDR Overlap

The operator validates that Subnet CIDRs do not overlap within a
VirtualNetwork at creation time.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fabric manager complexity | One Ansible role handles all networking concerns | Clear interface contract per operation; tested independently per manager |
| K8s-to-fabric bridge failure | VMs unreachable from fabric | k8sManager validates bridge connectivity at subnet creation; subnet stays Pending until bridge is confirmed |
| CaaS prerequisite ordering | ExternalIPs may be needed before cluster | Pending state for attachments; template validates its own prerequisites |
| ExternalIPAttachment target validation | Target may not exist yet (CaaS) or may be deleted | Pending state for forward references; attachment tracks target lifecycle |
| CIDR overlap | Overlapping subnets cause routing ambiguity | Operator validates at creation time; rejected with clear error |

### Drawbacks

This design requires K8s-to-fabric connectivity in every deployment that
hosts VMs. The k8sManager must bridge the OVN overlay to the physical
fabric for VMs to participate. In deployments without VMs (BM-only, with
or without CaaS), the k8sManager is not needed and the design reduces to
fabric-manager-only. MetalLB IPAddressPool creation for CaaS VIP
allocation is handled by the Subnet controller, not the k8sManager.

The trade-off is justified by infrastructure-agnostic subnets: any resource
type on any subnet, uniform security enforcement via the fabric, and no
per-resource-type dispatcher logic for ExternalIP or NATGateway.

## Alternatives (Not Implemented)

**Original NetworkClass model.** Tenants select a NetworkClass per VN.
Exposes implementation details. Not viable for multi-service support.

**Per-action driver composition.** Separate drivers for each networking
concern (network, acl, ingress, egress, publicIP) with independent
registration and composition. Over-engineered — the fabric is one product,
and splitting it into per-action drivers does not reflect how physical
networking works. Also creates complexity in the dispatcher and validation.

**Separate k8s ACL driver.** A dedicated k8s.acl driver (e.g.,
NetworkPolicy) alongside fabric ACLs. Redundant — when VMs are on the
fabric, the fabric enforces security for all traffic including VM traffic.
Adding a k8s ACL layer creates dual enforcement with no clear benefit.

**VN scope field (vm/bm).** Require tenants to declare what a network is
for at creation time. Makes subnets service-specific, prevents mixed
workloads, and leaks infrastructure details.

**Lazy subnet provisioning.** Defer manager selection to resource placement
time. Creates ambiguous subnet state and complicates the tenant experience.

## Resolved Questions

1. **Infrastructure-agnostic subnets.** VMs participate in the fabric via
   k8sManager. No scope/service field on VN. Any resource on any subnet.

2. **Cluster endpoint types:** `api` and `ingress` — enum
   `ExternalIPAttachmentEndpoint`.

3. **ExternalIP ownership:** An ExternalIP can only be consumed by one
   resource (either ExternalIPAttachment or NATGateway, not both).

4. **One NATGateway per VN.** Multiple gateways are ambiguous. Per-subnet
   NAT is a future enhancement.

5. **ExternalIPPool shared.** The fabric manager handles ExternalIP allocation
   for all resource types. One pool per deployment.

6. **Multiple hosting clusters.** Subnet creation provisions K8s overlay
   on each hosting cluster. VMs on different clusters share the subnet
   via the fabric.

7. **Internal IP pools.** Managed by managers with sensible defaults. Not
   part of the tenant API or NetworkClass spec.

8. **ExternalIP naming.** "External" means external to the VirtualNetwork —
   not necessarily Internet-routable. This applies within the supported
   connected deployment boundary.

9. **network_attachments immutability and cardinality.** Network attachments
   are immutable after resource creation, and VMaaS/BMaaS accept at most one
   entry even though the fields remain repeated for compatibility. Changing
   network attachment requires recreating the resource.

10. **Security enforcement.** The fabric is the single enforcement point
    for SecurityGroups. No separate K8s-level ACL needed — VMs are on the
    fabric.

11. **Per-resource NetworkAttachment types.** Separate proto messages
    (`ComputeNetworkAttachment`, `BareMetalNetworkAttachment`,
    `ClusterNetworkAttachment`) instead of one shared type. Each resource
    type has a different selector concept (virtual NIC, physical interface,
    node set) — a shared type with optional fields would accumulate
    dead weight per resource type.

12. **Create/read/delete networking API.** Networking resource specifications,
    metadata, and workload network attachment fields are immutable after
    creation. The supported change path is delete and recreate; controller
    status reconciliation is internal and does not expose an update operation.

## Test Plan

*Section to be completed when targeted at a release.*

## Graduation Criteria

*Section to be completed when targeted at a release.*

## Upgrade / Downgrade Strategy

*Section to be completed when targeted at a release.*

## Version Skew Strategy

*Section to be completed when targeted at a release.*

## Support Procedures

*Section to be completed when targeted at a release.*

## Infrastructure Needed

No additional infrastructure beyond existing OSAC components and managers.
