---
title: Unified Networking API for VMaaS, CaaS, and BMaaS
authors:
  - dmanor@redhat.com
creation-date: 2026-06-03
last-updated: 2026-09-23
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
  - K8s-only Networking Manager: /enhancements/OSAC-1433-k8s-only-k8s-manager
replaces:
  - OSAC-356 Networking API proposal (retired)
superseded-by:
  - N/A
---

# Unified Networking API for VMaaS, CaaS, and BMaaS

## Summary

This document describes the technical design for the OSAC unified
networking architecture. For the problem statement and requirements,
see the companion [Requirements Document (PRD)](prd.md).

OSAC runs VMs on OpenShift using KubeVirt, which encapsulates each VM in a
pod. Pod networking is managed by OVN-Kubernetes, meaning VMs live inside an
OVN overlay that is not directly visible on the physical fabric. The core
premise of this design is that **VMs are part of the fabric** when a deployment
includes a K8s manager. Every registered manager is a complete implementation
target for the full OSAC networking API and all three workload scopes: VMaaS,
BMaaS, and CaaS. A manager registration therefore declares only the manager
identity/type and the deployment-wide IPv4 contract; it does not advertise a
subset of resources, policy types, or services. A manager may temporarily use
a successful no-op AAP role for a resource or workflow still under development,
but that is an implementation stub and never a tenant-visible unsupported
capability or alternate API path. Native Kubernetes NetworkPolicy alone is not
a substitute for the OSAC policy contracts. The concrete manager profiles
define their backend mappings while inheriting this complete contract.

The design introduces:

- **NetworkClass** with optional `fabricManager` and `k8sManager` fields; at
  least one is required, and every selected manager receives the complete
  networking resource and workload contract
- **Infrastructure-agnostic subnets** where the same subnet can host VMs,
  BM servers, and cluster nodes, subject to the shared workload placement
  contract
- **ExternalIP** (renamed from PublicIP) to clarify that addresses are
  external to the VirtualNetwork, not necessarily internet-routable
- **Uniform API** where the same networking resources (VirtualNetwork,
  Subnet, SecurityGroup, NetworkACL, ExternalIP, ExternalIPAttachment,
  NATGateway) serve VMaaS, CaaS, and BMaaS identically

SecurityGroup and NetworkACL are complementary policy layers. A SecurityGroup
is a stateful, VirtualNetwork-scoped policy selected by a workload's network
attachment. A NetworkACL is a stateless, Subnet-associated policy inherited by
every workload on that Subnet. A packet must be permitted by both applicable
layers. SecurityGroup rules are allow-only and unmatched traffic is denied;
NetworkACL rules explicitly allow or deny traffic and are evaluated
independently in each direction.

NetworkACL is a subnet policy, not a workload attachment. It belongs to one
VirtualNetwork, can be associated with multiple explicit Subnets, and is the
effective policy for traffic entering or leaving those Subnets. Workload
attachments carry the Subnet (and, for BMaaS, the physical interface); they do
not carry NetworkACL references.

NetworkACL evaluation is stateless. Every packet is evaluated independently;
the dataplane does not remember a permitted connection and does not synthesize
the reverse rule. Tenant rules are evaluated first; if no tenant rule matches,
the provider-owned deployment default ACL policy (the deployment baseline)
applies. That baseline is currently hard-coded to `permit` all traffic and is
the least-specific policy. An
opposite-direction tenant rule is therefore required when the tenant needs to
impose a tenant-specific decision on return traffic; the baseline is not
serialized in or configurable through a tenant NetworkACL.

The BMaaS integration is based on the `BaremetalInstance` resource defined in
the [BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api),
which provides a per-server resource aligned with ComputeInstance.

BMaaS supports one tenant network attachment per `BaremetalInstance`: one
physical NIC is connected to one Subnet. A BareMetalInstanceType may describe multiple
physical interfaces for inventory and other service workflows, but BMaaS does
not support multi-NIC or multi-homed tenant attachments.

All networking resources and manager integrations in this design use IPv4.
IPv6 and dual-stack networking are not supported.

The optional `ipv6_cidr` fields in the public and private `VirtualNetwork`,
`Subnet`, and `SecurityRule` API messages are intentionally retained for wire
and generated-API compatibility. They are not removed or renumbered, leaving a
stable API shape for a future IPv6 implementation. The normative examples in
this document show only supported IPv4 inputs; they do not authorize removing
the legacy fields from the API or operator types. For the current IPv4-only
milestone, omitted or empty values are accepted, while non-empty IPv6 or
dual-stack values are rejected during API/CRD validation and are not
persisted, reconciled, or sent to networking providers.

For user stories, goals, and non-goals, see the
[Requirements Document (PRD)](prd.md).

> **Current implementation boundary:** OSAC supports connected deployments only.
> Air-gapped deployments are rejected before networking resources are provisioned.
> The contracts below describe the current supported behavior.

## Supported Operations and Immutability

This section defines the user/API operation contract for network-owned data.
Every network resource is create/read/delete-only: callers may create it, list
or get it, and delete it subject to dependency and finalizer checks. There is
no user/API update, patch, or replace operation for a network resource's
network-owned `spec` fields. A change to those fields requires deleting the
resource and creating a new one.

The contract is deliberately limited to network-owned data. Standard resource
metadata semantics, including Catalog Item definitions and metadata, are not
changed by this design. A Catalog Item may resolve a network value at parent
resource creation time, but that policy does not make the resulting network
value editable after creation.

East-west networking (`OSAC-1382`) is excluded from this shared contract because
it is not implemented. Its operation and field semantics remain governed by
its own design, which may support update and resize operations.

| Network-owned object or field | Allowed user/API operations | Immutability boundary |
|---|---|---|
| `NetworkClass` | Provider create, read, delete; tenant no access to create/update/delete | All provider-selected manager configuration in `spec` is fixed after creation. The provider may delete it only after the deployment has no networking resources or workload network attachments that depend on its manager resolution. |
| `VirtualNetwork` | Create, read, delete | CIDR/address-family and all other network `spec` fields are fixed after creation. Controller-owned dispatch annotations are not tenant fields and are not accepted as input. |
| `Subnet` | Create, read, delete | VirtualNetwork reference, CIDR/address-family, and all other network `spec` fields are fixed after creation. |
| `SecurityGroup` | Create, read, delete | VirtualNetwork reference and the complete allow-only rule set are fixed after creation. Tenant-created groups require at least one rule; the system-created tenant default group may have an empty rule set, which means default deny. |
| `NetworkACL` | Create, read, delete | VirtualNetwork reference, explicit Subnet associations, and the complete allow/deny rule set are fixed after creation. A NetworkACL may be associated with multiple Subnets; a Subnet may have only one effective ACL, including the system-created default ACL. |
| `ExternalIPPool` | Provider create, read, delete, and metadata-only update; tenant read/reference only | Address-family, CIDR ranges, and all other pool `spec` fields are fixed after creation. A provider may update only standard mutable metadata; no update may change the pool's network spec. Tenants cannot create, update, patch, replace, or delete deployment-scoped pools. |
| `ExternalIP` | Create, read, delete | Pool reference, address/allocation identity, and all other network `spec` fields are fixed after creation. |
| `ExternalIPAttachment` | Create, read, delete | ExternalIP, target, endpoint, and all other binding `spec` fields are fixed after creation; retargeting requires delete and create. |
| `NATGateway` | Create, read, delete | VirtualNetwork, ExternalIP, and all other gateway `spec` fields are fixed after creation; changing the ExternalIP requires delete and create. |
| `ComputeInstance.network_attachments` | Set on parent create, read with the parent, delete with the parent | The list-shaped field accepts zero or one entry only. The complete list and every entry field, including Subnet, SecurityGroups, and `primary`, are fixed after parent creation. The effective NetworkACL is resolved from the Subnet. |
| `Cluster.network_attachment` | Set on parent create, read with the parent, delete with the parent | The complete attachment and every entry field, including Subnet and SecurityGroups, are fixed after parent creation. The effective NetworkACL is resolved from the Subnet. |
| `BaremetalInstance.network_attachments` | Set on parent create, read with the parent, delete with the parent | The complete list and every entry field, including Subnet, SecurityGroups, interface, and primary designation, are fixed after parent creation; at most one entry is supported. The effective NetworkACL is resolved from the Subnet. |
| `auto_external_ip_attachment` on ComputeInstance, Cluster, and BaremetalInstance | Set on parent create, read with the parent, delete with the parent | This network-owned create-time switch is fixed after parent creation; changing automatic external access requires delete and recreate. |

Controllers may update `status`, conditions, readiness and IP-discovery
results, and may add or remove finalizers as part of reconciliation. Those
controller-owned transitions are not user/API updates to network-owned
`spec` fields. Non-network fields on ComputeInstance, Cluster, and
BaremetalInstance remain governed by their own designs.

## Field Types, Formats, and Validation

The protobuf wire type alone is not the complete API contract. Every
network-owned field must also have a defined format, presence/default rule,
allowed-value set, reference scope, and cross-field validation. The following
is the canonical contract for the currently supported north-south IPv4
networking surface.
Service-specific designs inherit these rules and add only their attachment
cardinality or placement constraints.

### Common formats

| Value | Contract |
|---|---|
| IPv4 CIDR | String in canonical dotted-decimal CIDR notation, `a.b.c.d/prefix`, with prefix `0..32` and host bits zero. IPv6 and dual-stack values are rejected. A Subnet CIDR must be contained by its parent VirtualNetwork CIDR and Subnet CIDRs must not overlap within that VirtualNetwork. |
| IPv4 address | String in dotted-decimal IPv4 notation without a CIDR suffix. Address fields are system/provider results, not alternate encodings of CIDRs. |
| Resource reference | A reference to an existing resource in the scope defined below; arbitrary strings are invalid. Use the typed local/full reference forms defined by [OSAC-1330](</enhancements/OSAC-1330-type-safe-resource-references/design.md>) for every reference-bearing network field, while preserving the documented resource scope. |
| Enum | Only the values listed in the relevant table are accepted. Unknown, future, and unspecified values are rejected for user-set fields unless explicitly marked as a status value. Protobuf enum symbols in the examples are uppercase identifiers; the public JSON and CLI representations are defined separately below and are not case-folded. |
| Repeated field | Cardinality, uniqueness, and ordering are part of the field contract. Duplicate references are rejected; ordering is meaningful only where explicitly stated. |
| Timestamp | If exposed in an API status or audit field, use `google.protobuf.Timestamp` / RFC 3339 semantics in UTC. Timestamps are controller/system fields and are not tenant network configuration. |
| Metadata name | Standard resource metadata rules apply; metadata is outside the network-owned field contract and is not changed by this design. |

### Enum wire and client representations

The protobuf snippets use conventional uppercase enum symbols, but clients must
use the following canonical representations:

| Field family | Protobuf symbols | REST/JSON value | CLI value | UI behavior |
|---|---|---|---|---|
| SecurityGroup and NetworkACL `direction` | `INGRESS`, `EGRESS` | `ingress`, `egress` | `ingress`, `egress` | Display `Ingress`/`Egress`; submit the lowercase JSON value |
| SecurityGroup and NetworkACL `protocol` | `TCP`, `UDP`, `ICMP`, `ANY` | `tcp`, `udp`, `icmp`, `any` | `tcp`, `udp`, `icmp`, `any` | Display labels may be title case; submit the lowercase JSON value |
| NetworkACL `action` | `ALLOW`, `DENY` | `allow`, `deny` | `allow`, `deny` | Display `Allow`/`Deny`; submit the lowercase JSON value |
| `ExternalIPPool.spec.ip_family` | `IPV4` | `IPV4` | `ipv4` | Display `IPv4`; submit `IPV4` |
| `ExternalIPAttachmentSpec.target_endpoint` | `UNSPECIFIED`, `API`, `INGRESS` | `UNSPECIFIED`, `API`, `INGRESS` | `api`, `ingress` for Cluster; omitted for VM/BM | Display `API`/`Ingress`; the CLI maps its lowercase values to the JSON enum |

The REST gateway performs only the documented protobuf-to-JSON mapping. It
does not accept alternative casing, aliases, or UI display labels. The server
and CLI reject a value that is not in the canonical representation for that
surface.

### Network resource fields

#### Attachment field names and message types

The API field name and the message type carried by that field are separate
parts of the contract. The resource-specific message types are the canonical
wire values; the field names below are the canonical API names:

| Resource | API field | Value type | Supported shape |
|---|---|---|---|
| `ComputeInstance` | `spec.network_attachments` | repeated `ComputeNetworkAttachment` | zero or one entry |
| `Cluster` | `spec.network_attachment` | `ClusterNetworkAttachment` | omitted or one structured message |
| `BaremetalInstance` | `spec.network_attachments` | repeated `BareMetalNetworkAttachment` | zero or one entry |

The generic-looking `network_attachment` and `network_attachments` names are
intentional API field names shared by the workload contracts. The plural field
is used by both ComputeInstance and BaremetalInstance, with a different
resource-specific element type in each contract. `cluster_network_attachment` and
`bare_metal_network_attachments` are not alternate field names and must not be
introduced as additional API fields. Internal CRDs may use their established
camelCase mappings (`networkAttachment` and `networkAttachments`), but their
values must still use the corresponding resource-specific message type.

| Resource and field | Wire type / presence | Allowed values and validation |
|---|---|---|
| `NetworkClass.spec.fabric_manager` | String reference, optional | If present, must name a provider-registered fabric manager. The referenced manager is a complete implementation target for the networking API and all three workload services. |
| `NetworkClass.spec.k8s_manager` | String reference, optional | If present, must name a provider-registered K8s manager. The referenced manager is a complete implementation target for the networking API and all three workload services. At least one of `fabric_manager` or `k8s_manager` must be present. |
| `NetworkClass.spec.defaults` | `NetworkDefaults` message, required | There is no enable/disable knob. `virtual_network_cidr` and `ipv4_subnet_cidr` are both required canonical IPv4 CIDRs; the subnet must be contained by the VN. |
| `NetworkClass.spec.metallb_vip_prefix_length` | `int32`, required for the CaaS/MetalLB deployment path | No universal default exists. It must be a valid IPv4 prefix more specific than each participating Subnet prefix, and the reserved range must remain inside the Subnet. It is a deployment setting, not a manager capability advertisement. |
| Controller dispatch metadata | Operator-owned annotations, not tenant API fields | The operator derives the target manager names from the deployment NetworkClass and stores only the routing metadata required to reconcile and delete the selected targets. There is no tenant-selectable implementation strategy and no combined strategy value. |
| `VirtualNetwork.spec.ipv4_cidr` | IPv4 CIDR string, required | Must be a canonical IPv4 network CIDR. Cross-tenant CIDR overlap is allowed only because fabric isolation is explicitly relied upon; Subnet overlap within the VN is rejected. |
| `Subnet.spec.virtual_network` | Local VirtualNetwork reference, required | Must reference a `Ready` VirtualNetwork in the same tenant/project. |
| `Subnet.spec.ipv4_cidr` | IPv4 CIDR string, required | Must be a canonical IPv4 network CIDR contained by the parent VirtualNetwork and non-overlapping with sibling Subnets in that VN. |
| `SecurityGroup.spec.virtual_network` | Local VirtualNetwork reference, required | Must reference a `Ready` VirtualNetwork in the same tenant/project. |
| `SecurityGroup.spec.rules` | Repeated `SecurityGroupRule`, required for tenant-created groups | Tenant-created SecurityGroups must contain at least one rule. The tenant default SecurityGroup may have an empty list, which produces implicit default deny. Rules are create-time-only and duplicate rules are rejected. |
| `NetworkACL.spec.virtual_network` | Local VirtualNetwork reference, required | Must reference a `Ready` VirtualNetwork in the same tenant/project. |
| `NetworkACL.spec.subnets` | Repeated local Subnet references, required | Must contain one or more unique Ready Subnets from the parent VirtualNetwork. A Subnet may have at most one effective NetworkACL association; the system-created default ACL counts as that association, so an ordinary custom ACL cannot be associated with a Subnet that already has any effective ACL. |
| `NetworkACL.spec.rules` | Repeated `NetworkACLRule`, required for a user-created NetworkACL | Every user-created NetworkACL must contain at least one rule. Each tenant default ACL contains the explicit default ACL policy. Rules are create-time-only, duplicates are rejected, and conflicting equal-specificity rules are rejected. |
| `ExternalIPPool.spec.ip_family` | Enum, required | `IPV4` only. IPv6 and dual-stack values are rejected. |
| `ExternalIPPool.spec.cidrs` | Repeated IPv4 CIDR strings, required, exactly one supported | The list must contain exactly one canonical IPv4 CIDR. Multi-CIDR pools are not part of the supported contract; create separate pools instead. |
| `ExternalIP.spec.pool` | Provider/deployment-scoped ExternalIPPool reference, required | The pool must exist, be Ready, and have capacity. The allocated address is selected by the provider and all selected manager implementations; tenants do not supply an arbitrary address. |
| `ExternalIPAttachmentSpec.external_ip` | Local ExternalIP reference, required | The ExternalIP must exist, be `Allocated`, and cannot already be consumed by another ExternalIPAttachment or NATGateway. |
| `ExternalIPAttachmentSpec.target` | Required `oneof` | Exactly one of `compute_instance`, `cluster`, or `baremetal_instance` must be set. The target must be in the permitted tenant/project scope and `Ready`; the endpoint address must be populated before DNAT is dispatched. |
| `ExternalIPAttachmentSpec.target_endpoint` | `ExternalIPAttachmentEndpoint` enum | `API` or `INGRESS` is required for a Cluster target. `UNSPECIFIED` is required for ComputeInstance and BaremetalInstance targets. |
| `NATGateway.spec.virtual_network` | Local VirtualNetwork reference, required | Must reference a `Ready` VirtualNetwork in the same tenant/project; only one NATGateway is allowed per VN. |
| `NATGateway.spec.external_ip` | Local ExternalIP reference, required | Must reference an `Allocated`, unconsumed ExternalIP in the same tenant/project. |

For every reference above, create-time validation first checks existence, type,
scope, and uniqueness. A caller-created dependent resource is rejected with a
precondition error when the referenced resource is not yet in the required
state; the API does not silently create a Pending dependency. The only
exception is the allowlisted OSAC-owned automatic ExternalIP flow described
below. A resource may be Pending because its own selected manager is still
provisioning it, but it may not be admitted merely to wait for a referenced
resource to become ready.

There is one intentional scope exception for the current CaaS worker flow.
CaaS-managed BaremetalInstances are created in the builtin `system` tenant,
while their Subnet and effective NetworkACL belong to the tenant that owns the
Cluster. The trusted private CaaS-to-BMaaS create path resolves the local
Subnet reference and inherited ACL in the Cluster's effective tenant/project;
it must not require the destination BMI tenant to match the networking
resource tenant. This exception is limited to the authenticated CaaS worker
path. Standalone, Catalog-based, and tenant-facing BaremetalInstance creates
continue to require same-scope networking references.

### Strict dependency-ready creation

Creation admission is strict and ordered. The API resolves all explicit,
Catalog-provided, Template-provided, and defaulted references before it
persists the requested object. Every referenced object must already be in the
state required by the operation. If a dependency is `Pending`, `Failed`,
`Deleting`, or otherwise not usable, the request is rejected immediately; the
service does not create the dependent object and wait for the dependency to
recover. This rule applies equally to public tenant APIs, provider/default
onboarding APIs, private service-to-service APIs, and direct hub-CR admission.

The following readiness matrix is the minimum admission contract. A resource
can still be `Pending` after admission while its own selected manager performs
the resource's backend operation; that is different from creating it with a
non-Ready dependency.

| Create operation | Dependencies that must already be usable | Required state before persistence |
|---|---|---|
| `VirtualNetwork` | The deployment `NetworkClass` and every selected manager registration | NetworkClass and registrations are present, enabled, and usable; every selected manager implements the complete networking contract |
| `Subnet` | `VirtualNetwork` | `VirtualNetwork=Ready` |
| `SecurityGroup` | `VirtualNetwork` | `VirtualNetwork=Ready` |
| `NetworkACL` | `VirtualNetwork` and every referenced `Subnet` | `VirtualNetwork=Ready`; every Subnet is `Ready`; every association is available |
| `ExternalIP` | `ExternalIPPool` | `ExternalIPPool=Ready` with capacity |
| direct `ExternalIPAttachment` | `ExternalIP`, target workload, and target endpoint | `ExternalIP=Allocated`, target=`Ready`, endpoint present and valid |
| `NATGateway` | `VirtualNetwork` and `ExternalIP` | `VirtualNetwork=Ready`; `ExternalIP=Allocated` and unconsumed |
| `ComputeInstance` | Resolved `Subnet`, `SecurityGroup` values, effective Subnet `NetworkACL`, and any required instance profile | All resolved references and profiles are `Ready`; the selected manager combination implements the complete workload path |
| `Cluster` | Resolved `Subnet`, `SecurityGroup` values, effective Subnet `NetworkACL`, and the resolved cluster template/node-set inputs | All resolved references and profiles are `Ready`; any explicitly required reachability resource is `Ready` |
| `BaremetalInstance` | Resolved `Subnet`, `SecurityGroup` values, effective Subnet `NetworkACL`, `BareMetalInstanceType`, and the selected BM provisioning inputs | All resolved references and profiles are `Ready`; the selected manager combination implements the complete workload path |

The CaaS private worker exception changes only tenant scope resolution: the
BMI is materialized in the system tenant, but the trusted request resolves the
Cluster owner's Subnet, policy, and attachment values. It does not waive the
readiness requirements in the matrix. A pending or failed Cluster-owned
network dependency still rejects the private BMI create before a BMI or worker
CR is persisted.

#### Admission error and atomicity

For an existing dependency in the wrong state, the API returns
`FailedPrecondition`. The status must include one machine-readable detail for
each blocker with at least:

- `dependent_resource`: kind and requested name/ID;
- `field_path`: the request field that introduced the reference;
- `dependency_resource`: kind and name/ID;
- `dependency_state`: the observed state;
- `required_state`: the state required by the matrix; and
- `remediation`: wait for the dependency to reach the required state, then
  retry the create request.

The human-readable message uses this form:

```text
cannot create <DependentKind>/<dependent>: <field_path> references
<DependencyKind>/<dependency> in state <observed>; required state is
<required>. Wait for the dependency to become <required> and retry.
```

For example, a Subnet create against a Pending VirtualNetwork returns
`FailedPrecondition` identifying `spec.virtual_network` and the VN; a direct
attachment against a Pending ExternalIP identifies `spec.external_ip` and
requires `Allocated`. If several references are unusable, the response
identifies all blockers so the caller can correct the request in one cycle.
Missing or invisible references continue to use the platform's visibility-safe
`NotFound`/`InvalidArgument` behavior and must not reveal another tenant's
resource. No rejected request writes the dependent object, reserves capacity,
creates a child, creates a CR, or dispatches an AAP job.

#### The only Pending dependency exception

The only create path allowed to persist a child whose dependency is not yet in
its normal ready state is the OSAC-owned automatic external-access path:

1. The parent workload request must first resolve a `Ready` IPv4
   `ExternalIPPool` and pass capacity validation.
2. In the same transaction, OSAC may create the parent workload, an
   auto-created `ExternalIP` in `Pending`, and an auto-created
   `ExternalIPAttachment` in `Pending`. The attachment may reference the
   still-provisioning workload and the Pending ExternalIP.
3. Only the allowlisted immutable owner relationship and
   `osac.openshift.io/auto-created: "true"` marker authorize this exception.
   A tenant-created ExternalIP or attachment cannot use it.
4. The controllers wait for `ExternalIP=Allocated` and the workload endpoint
   to be ready before dispatching DNAT. If either becomes terminally Failed,
   the child reports that failure; it is not silently replaced or attached to
   another target.

An onboarding-created default NATGateway is not part of this exception. Its
auto-created ExternalIP may be Pending, but the NATGateway is created only
after the ExternalIPPool is Ready, the ExternalIP is Allocated, and the
default VirtualNetwork is Ready. Default VirtualNetwork, Subnet,
SecurityGroup, NetworkACL, and NATGateway resources therefore follow the same
strict dependency order as tenant-created resources.

The tenant default SecurityGroup belongs to the tenant default
VirtualNetwork. Defaulting never creates or selects a SecurityGroup from a
different VirtualNetwork. After field-level defaulting, the resolved Subnet
and every resolved SecurityGroup must belong to the same VirtualNetwork. If a
request supplies a Subnet from a non-default VirtualNetwork while omitting its
SecurityGroup, or supplies a SecurityGroup that is not compatible with the
defaulted Subnet, the request is rejected with `InvalidArgument` and a field
detail identifying both VirtualNetworks. The caller must provide a Ready
SecurityGroup in the selected VirtualNetwork; the server does not silently
create a per-VirtualNetwork default group.

### SecurityGroupRule fields

SecurityGroup rules describe traffic that is allowed to or from an attached
workload. They never contain an allow/deny action field: every rule is an
allow rule, and traffic that matches no rule is denied. Rules are stateful, so
return traffic for an accepted connection is allowed automatically. When
multiple SecurityGroups are attached, their allow rules are aggregated; an
allow in any attached group is sufficient at the SecurityGroup layer.

| Field | Contract |
|---|---|
| `direction` | Required enum: `ingress` or `egress`. Unknown values are rejected. |
| `protocol` | Required enum: `tcp`, `udp`, `icmp`, or `any`. Values are lowercase and case-sensitive. |
| `port` | Optional `int32`; for `tcp`/`udp`, omission matches all ports and a supplied value is `1..65535`; `icmp`/`any` omit it. Port ranges are not supported. |
| `source_cidr` / `destination_cidr` | Exactly one direction-specific field is required. It must be a canonical IPv4 CIDR; `source_cidr` is used for ingress and `destination_cidr` for egress. |
| Rule evaluation | All matching allow rules from all attached SecurityGroups are aggregated. There are no deny rules, no rule priority, and no most-specific-wins override. Unmatched traffic is denied. Connection state permits the reverse direction for an accepted flow. |

SecurityGroup rules are immutable after creation. A tenant-created group must
contain at least one rule. The tenant default SecurityGroup is an OSAC-created
fallback and may have an empty rule list to express default deny.

### NetworkACLRule fields

The following is the complete supported value contract. Rule fields are not
arbitrary strings:

| Field | Contract |
|---|---|---|
| `action` | Required enum: `allow` or `deny`. Unknown values are rejected. |
| `direction` | Required enum: `ingress` or `egress`. Unknown values are rejected. |
| `protocol` | Required enum: `tcp`, `udp`, `icmp`, or `any`. Protocol matching is case-sensitive; unknown values are rejected. |
| `port` | Optional `int32`; for `tcp`/`udp`, omission matches all ports and a supplied value is `1..65535`; `icmp`/`any` omit it. Port ranges are not supported. |
| `source_cidr` / `destination_cidr` | Exactly one direction-specific field is required. It must be a canonical IPv4 CIDR; `source_cidr` is used for ingress and `destination_cidr` for egress. |
| Rule evaluation | Evaluation is stateless and direction-specific. The provider-owned deployment baseline is always present as the least-specific fallback and currently permits all traffic. Tenant rules override it whenever they match. Within tenant rules, the most-specific matching rule wins: longest matching remote CIDR prefix, then exact protocol over `any`, then exact port over an omitted port. Conflicting equal-specificity rules are rejected. |

### Workload network fields

| Field | Wire type / presence | Allowed values and validation |
|---|---|---|
| `ComputeInstance.network_attachments` | Repeated `ComputeNetworkAttachment`, optional | Missing or empty uses the tenant default Subnet and, when the resolved Subnet is in the tenant default VirtualNetwork, the tenant default SecurityGroup. A supplied list contains zero or one entry only; more than one entry is rejected. The effective ACL for the resolved Subnet must be Ready. |
| `ComputeNetworkAttachment.subnet` | Local Subnet reference, optional at request and required after resolution | If omitted, resolve only the tenant default Subnet. If supplied, it must exist and be `Ready`. |
| `ComputeNetworkAttachment.security_groups` | Repeated local SecurityGroup references, optional | If omitted or empty, resolve the tenant default SecurityGroup only when the resolved Subnet is in the tenant default VirtualNetwork; otherwise reject with `InvalidArgument` unless a compatible explicit group is supplied. If supplied, use exactly the supplied groups; every group must be Ready, belong to the same tenant and VirtualNetwork, and be unique. |
| `ComputeNetworkAttachment.primary` | Optional boolean | With the supported single attachment, omission or `true` makes it primary; explicit `false` is rejected. Multi-interface primary selection is unsupported. |
| `Cluster.network_attachment` | `ClusterNetworkAttachment`, optional | Missing or an empty message uses the tenant default Subnet and, when that Subnet is in the tenant default VirtualNetwork, the tenant default SecurityGroup. When present, exactly one resolved attachment applies to every node set. The effective ACL for the resolved Subnet must be Ready. |
| `ClusterNetworkAttachment.security_groups` | Repeated local SecurityGroup references, optional | If omitted or empty, resolve the tenant default SecurityGroup only when the resolved Subnet is in the tenant default VirtualNetwork; otherwise reject with `InvalidArgument` unless a compatible explicit group is supplied. If supplied, use exactly the supplied groups; every group must be Ready, belong to the same tenant and VirtualNetwork, and be unique. |
| `BaremetalInstance.network_attachments` | Repeated `BareMetalNetworkAttachment`, optional | Missing or empty uses the tenant default Subnet and, when that Subnet is in the tenant default VirtualNetwork, the tenant default SecurityGroup. A non-empty list must contain exactly one entry. The effective ACL for the resolved Subnet must be Ready. |
| `BareMetalNetworkAttachment.security_groups` | Repeated local SecurityGroup references, optional | If omitted or empty, resolve the tenant default SecurityGroup only when the resolved Subnet is in the tenant default VirtualNetwork; otherwise reject with `InvalidArgument` unless a compatible explicit group is supplied. If supplied, use exactly the supplied groups; every group must be Ready, belong to the same tenant and VirtualNetwork, and be unique. |
| `BareMetalNetworkAttachment.interface` | String reference/name, optional | If set, it must identify a valid non-lifecycle port. If omitted, BMaaS selects the first valid `fabric` port from the effective BareMetalInstanceType. |
| `BareMetalNetworkAttachment.primary` | Optional boolean | The sole BM attachment is implicitly primary; omission or `true` is accepted and explicit `false` is rejected. |
| `auto_external_ip_attachment` | Boolean, optional | Defaults to `false`; when `true`, the system creates the automatic ExternalIP resources. It is create-time-only. |

The service-specific documents must not introduce a different type, format,
default, or validation rule for these shared fields. Service-specific designs
may add only placement, cardinality, or lifecycle constraints for their own
attachment message. They must not add a workload-level NetworkACL reference.

### Validation and enforcement pipeline

The validation rules above are normative. A tenant must not be able to reach a
backend manager with a value that the API contract has already declared
unsupported. Validation is therefore performed in layers, with each layer
owning a different class of invariant:

| Layer | Enforcement point | Rules owned by the layer | Failure behavior |
|---|---|---|---|
| Request shape | Protobuf/protovalidate and REST gateway | Required fields, `oneof` selection, scalar types, enum membership, repeated-field cardinality that is expressible in the schema, and malformed values | Reject the request before a database write with `InvalidArgument`; do not normalize an invalid value into a valid one. |
| Tenant/provider authorization | API handler and OPA/RBAC policy | Provider-only NetworkClass access, tenant/project scope, visibility of references, and operation authorization | Return `PermissionDenied` or `NotFound` according to the platform's existing resource-visibility policy; do not leak another tenant's resource. |
| Semantic API validation | fulfillment-service private server | Canonical formatting, reference type and scope, readiness, uniqueness, cross-field rules, complete manager contract, and service-specific attachment rules | Return `InvalidArgument` for malformed/contradictory input and `FailedPrecondition` for an existing object that is not in the required state. Persist nothing from a rejected create. |
| Transactional validation | fulfillment-service database transaction | Uniqueness races, ExternalIP capacity reservation, one-consumer constraints, reverse-reference protection, and atomic parent/auto-created-resource creation | Abort the transaction. A failed capacity or uniqueness check leaves neither a partial parent resource nor an orphaned auto-created network resource. |
| Resource CRD validation | Operator CRD schema and CEL rules | The same cardinality and immutable-field rules at the hub-cluster boundary, including every network-owned nested field | Reject an invalid or mutated CR before reconciliation. CRD validation is defense in depth; it must not be weaker than the fulfillment-service contract. |
| Reconciliation preconditions | osac-operator and service-specific controllers | Readiness of an already-admitted resource's own manager operation, discovered target IPs, manager handoff ordering, and status-to-spec consistency | Do not dispatch a backend operation prematurely. Requeue an already-admitted resource while its own operation or an allowlisted auto-created ExternalIP/ExternalIPAttachment is Pending. A normal dependent create is rejected at admission and is never represented as a Pending child waiting for another resource. |
| Backend contract enforcement | Dispatcher and configured manager | Every selected manager receives the requested resource and operation, and returns only contract-valid allocation/status data | Treat a manager response with an invalid family, address, or state transition as a provisioning failure and do not mark the resource Ready. An unfinished operation may use an internal successful no-op AAP role. |

Validation is applied in the following order for every user create request:

1. Authenticate the caller and establish the effective tenant/project and
   provider scope.
2. Validate the request envelope, protobuf presence, oneofs, enums, repeated
   fields, and canonical formats.
3. Resolve Catalog/Template values without changing the meaning of an
   explicitly supplied value. Only the resource-specific attachment fields
   defined by the current API contract are accepted.
4. Resolve an omitted or empty workload Subnet and SecurityGroup membership
   using the documented tenant defaults. The tenant default SecurityGroup may
   be used only with the tenant default VirtualNetwork. NetworkACL association
   is not part of workload defaulting. The effective ACL is determined by the
   resolved Subnet and must be Ready.
5. Validate every resolved reference for existence, type, scope, readiness,
   and relationship to the other resolved references. A non-Ready existing
   dependency is a hard `FailedPrecondition` admission failure; it is not
   persisted as a Pending dependent and is not deferred to reconciliation. In
   particular, the
   resolved Subnet and SecurityGroups must belong to the same VirtualNetwork;
   a missing SecurityGroup is filled only when the tenant default group is in
   that same VirtualNetwork.
6. Validate cross-resource and complete-manager rules, including address
   family, CIDR containment/non-overlap, attachment cardinality, target
   endpoint rules, and one-consumer constraints. Every selected manager is an
   implementation target for every networking resource and workload service;
   there is no per-resource target lookup or zero-target success path.
7. Reserve any scarce capacity and persist the complete resolved spec in one
   transaction. If automatic ExternalIP resources are requested, persist the
   parent and its Pending children atomically; this is the only exception to
   the strict dependency-ready creation rule.
8. Reconcile only after persistence. Controllers re-check dependency
   readiness and the complete manager registration before every backend
   dispatch because state may change between API persistence and
   reconciliation. A newly referenced resource that was not Ready at
   admission is never created by this step. If an implementation is still
   being completed, its AAP role may finish successfully without changing the
   public API contract or inventing an unsupported-resource path.

The API distinguishes values that are absent, empty, and explicitly false:

- An omitted optional attachment field and an empty repeated attachment field
  invoke the documented defaulting behavior. They are not a request to bypass
  networking or to clear a default.
- An attachment message supplied without `subnet` receives the tenant default
  Subnet. There is no NetworkACL field in the attachment to default.
- An explicitly supplied reference, including a tenant-local reference that
  happens to equal the default, remains an explicit value and is validated as
  such.
- An explicitly supplied `primary: false` is not treated as omission and is
  rejected by the single-attachment contracts.
- An explicitly supplied unsupported enum, IPv6 value, second list entry, or
  unknown reference is rejected; clients and agents must not silently drop it.

#### Shared validation matrix

The following checks are required in addition to the field table. They are
shared by all service-specific designs and must be reused by direct creates,
Catalog-based creates, Template-default resolution, and private service-to-
service creates.

**NetworkClass.** The provider validation path must:

- enforce exactly one deployment NetworkClass and reject a second active
  NetworkClass for the same deployment;
- reject tenant create, update, patch, or delete attempts because
  NetworkClass is provider-owned;
- require at least one of `fabric_manager` and `k8s_manager`, reject an
  unknown manager name, and verify the referenced manager registration exists,
  is enabled, and is an IPv4 manager;
- verify before NetworkClass Ready that every selected manager profile provides
  the complete create/read/delete lifecycle, readiness, policy, allocation,
  translation, and workload integration for every canonical networking
  resource and for VMaaS, BMaaS, and CaaS. A profile that is incomplete is a
  provider configuration error, not a partial-manager registration;
- allow a development profile to route an incomplete implementation through a
  successful no-op AAP role while its code is being completed. The no-op is
  internal provider implementation behavior, is not represented as an
  unsupported resource or service, and cannot create a second public API path;
- treat a K8s-only manager as the direct implementation target, not as a
  fallback to a missing Fabric Manager. For every networking resource, select
  every configured manager: one selected manager means one job and two
  selected managers means two jobs. There is no zero-target resource case;
- validate that the persisted target metadata is complete and unambiguous:
  the generic implementation annotation names the Fabric target when one is
  selected, otherwise the K8s target; the K8s-specific annotation is present
  only for a dual-target resource. The annotations are controller-owned and
  cannot be supplied or changed by a tenant;
- require `spec.defaults`, require both default CIDRs, validate their IPv4
  canonical form and containment, and require a valid
  `metallb_vip_prefix_length` for the CaaS/MetalLB VIP path. There is no
  manager-defined CaaS service-selection key;
- reject IPv6 and dual-stack manager/deployment configuration; the complete
  manager contract is provider-resolved and not tenant input; and
- compute the per-resource dispatch targets from the manager combination and
  persist only the controller-owned routing metadata required for reconciliation
  and deletion. A caller-supplied implementation strategy or tenant-selected
  NetworkClass reference is rejected rather than honored; and
- publish only a manager-derived status: `addressFamily` must remain `ipv4`,
  and the NetworkClass must not expose a per-resource or per-service support
  matrix. All canonical resources and workload scopes are part of the selected
  manager contract. Status changes are provider/controller operations, not
  tenant updates;
- verify the deployment admission boundary before accepting the NetworkClass:
  exactly one hub cluster must be registered for the deployment and the
  deployment connectivity provider must report a connected topology. A zero-
  or multi-hub deployment, or an air-gapped deployment, is rejected with a
  provider configuration precondition; there is no tenant-settable override.
  All networking API and reconciliation paths must resolve through that one
  hub, and every persisted `status.hub` must identify it; and
- verify the complete workload integration before NetworkClass Ready: VMaaS
  placement, attachment resolution, and IPv4 discovery; BMaaS port movement
  and DHCP discovery; and CaaS worker placement, reachability, and VIP flow.
  A missing implementation is a provider configuration/development issue and
  is handled by the selected AAP implementation (including a temporary no-op
  stub), never by rejecting a tenant resource because an implementation is
  still being completed.

**VirtualNetwork.** The API and controller must:

- establish the tenant/project owner before validating the request and reject
  a cross-scope parent or duplicate name in the same scope according to the
  standard resource identity rules;
- accept only a canonical IPv4 `ipv4_cidr` with host bits zero and reject
  IPv6, dual-stack, malformed, or ambiguous CIDRs;
- reject caller-supplied implementation-strategy annotations or equivalent
  tenant fields. The controller derives routing metadata from the deployment
  NetworkClass and never honors a tenant-selected manager;
- reject a VirtualNetwork create if its deployment NetworkClass is absent or
  not Ready;
- prevent a tenant from using the VN as a parent for a Subnet outside the
  tenant/project scope; and
- keep the VN in Pending/Failed rather than Ready until the configured
  manager has successfully created and reported the network segment.

Cross-tenant CIDR overlap is allowed only because tenant isolation is supplied
by the configured networking backend. Within one VirtualNetwork, all child
Subnet CIDRs must be non-overlapping; the backend must not be asked to
provision an ambiguous address space.

**Subnet.** The API and controller must:

- require a local `virtual_network` reference and verify that the parent
  exists, is Ready, and belongs to the caller's effective tenant/project;
- accept only a canonical IPv4 network CIDR, with host bits zero, contained
  entirely in the parent VirtualNetwork CIDR, and not overlapping any sibling
  Subnet in that VirtualNetwork;
- reject a CIDR equal to, containing, or partially overlapping any sibling
  range; Subnet updates are not supported, so there is no user update path
  that can relax this check;
- reject an IPv6/dual-stack address family or a Subnet whose family differs
  from the parent VN and NetworkClass;
- validate any provider-reserved range such as a MetalLB VIP prefix only after
  containment and prefix ordering have been checked; and
- dispatch `create_subnet` only after the parent VN is Ready. The Subnet
  becomes Ready only after every selected manager reports success (or the
  development operation completes through its approved no-op AAP role).

A Subnet may be created before a tenant NetworkACL is associated with it. Such
a Subnet is Ready as a network resource but is not workload-ready: a
ComputeInstance, Cluster, or BaremetalInstance that resolves to it is rejected
with `FailedPrecondition` until the effective NetworkACL is Ready. The
deployment permit baseline is not a substitute for the tenant ACL.

**SecurityGroup and rules.** The API and controller must:

- require a Ready, same-scope VirtualNetwork;
- require at least one rule for a tenant-created SecurityGroup. The
  system-created tenant default SecurityGroup may be empty and means default
  deny;
- validate every rule independently: required direction and protocol,
  supported port presence/range, exactly one direction-appropriate CIDR,
  canonical IPv4 CIDR, and no unsupported extension fields;
- reject any `allow`/`deny` action field because SecurityGroup rules are
  allow-only;
- reject duplicate rules and duplicate SecurityGroup references on an
  attachment;
- require every attached group to be Ready, in the same tenant and
  VirtualNetwork as the workload's resolved Subnet; and
- keep the complete rule set and VirtualNetwork reference immutable after
  create. SecurityGroup evaluation is stateful and aggregates allow rules
  across all attached groups; it does not use deny rules or a most-specific
  override.

**NetworkACL and rules.** The API and controller must:

  - require a Ready, same-scope VirtualNetwork;
- require one or more explicit Ready Subnet associations, each belonging to
  the same VirtualNetwork, with no duplicate references;
- enforce at most one effective NetworkACL association per Subnet, counting
  the system-created default ACL; an ordinary custom ACL create is rejected if
  the Subnet already has any effective ACL. Replacing a default ACL is a
  default-resource replacement workflow, not a second association;
- require at least one rule for a user-created NetworkACL. Each tenant default
  ACL is populated with the explicit default ACL policy;
- validate every rule independently before evaluating the rule set: required
  action, direction, and protocol; supported enum value; correct port
  presence/range for the protocol; exactly one direction-appropriate CIDR;
  canonical IPv4 CIDR; and no unsupported extension fields;
- normalize canonical CIDR text and omitted-vs-explicit fields before duplicate
  detection. Enum values must already use their canonical lower-case spelling;
  enum case is not folded. Two normalized identical rules are duplicates even
  if their input text used different equivalent CIDR formatting;
- reject conflicting equal-specificity rules after normalization;
- reject a rule whose source/destination field does not match its direction,
  including ingress with only `destination_cidr` or egress with only
  `source_cidr`; and
- keep the Subnet association list and complete rule list immutable after
  create. The runtime evaluator applies the effective ACL at the Subnet
  boundary and evaluates every packet independently.

**ExternalIPPool.** The provider-scoped pool validation must:

- require `ip_family == IPV4` and reject unspecified, IPv6, and dual-stack
  values;
- require exactly one CIDR in the list, validate canonical IPv4 network form,
  and reject an empty list, multiple CIDRs, host bits, or a CIDR outside the
  provider's permitted address space;
- reject overlapping allocation ranges between pools in the same deployment
  unless the manager explicitly provides disjoint allocation ownership; the
  provider must not expose two pools that can allocate the same address;
- ensure the manager can allocate, release, and report addresses for the pool
  before the pool is marked Ready; and
- keep the pool address family and range immutable. A pool with allocated
  ExternalIPs cannot be replaced in place.

**ExternalIP.** The API and controller must:

- require a Ready pool in the permitted deployment/provider scope;
- atomically reserve capacity before persisting an allocation and reject the
  request when no capacity is available;
- never accept a tenant-selected arbitrary address as an alternative to pool
  allocation. Any manager-reported address must be IPv4, belong to the pool
  CIDR, not be a network/broadcast/reserved address, and not already be
  allocated;
- allow only the manager to transition the allocation from Pending to
  Allocated or Failed; and
- prevent deleting or releasing an ExternalIP while an ExternalIPAttachment
  or NATGateway consumes it.

**ExternalIPAttachment.** The API and controller must:

- require exactly one target oneof arm and reject an empty or multiply set
  target;
- require a local ExternalIP reference, verify that it is Allocated for a
  direct user create, and reject an ExternalIP already consumed by another
  attachment or NATGateway;
- verify that the target exists, is in the permitted tenant/project scope,
  and is Ready enough to expose the endpoint used for DNAT;
- require `API` or `INGRESS` only for Cluster targets, require
  `UNSPECIFIED` for ComputeInstance and BaremetalInstance targets, and reject
  endpoint values that do not match the target type;
- reject a duplicate attachment for the same ExternalIP/target/endpoint
  combination;
- validate the discovered target endpoint as canonical IPv4 before dispatch;
  the tenant cannot supply or override the discovered endpoint address; and
- allow the internal auto-provisioning transaction to create a Pending
  attachment together with its Pending ExternalIP, while requiring the
  asynchronous controller to wait for both `ExternalIP == Allocated` and the
  target endpoint before creating DNAT.

**NATGateway.** The API and controller must:

- accept NATGateway creation as part of the complete manager contract. If the
  backend operation is not yet implemented, the selected AAP role may complete
  as a temporary no-op; the API must not reject the tenant resource because a
  provider implementation is unfinished;
- require a Ready same-scope VirtualNetwork and an Allocated, unconsumed
  same-scope ExternalIP;
- enforce one NATGateway per VirtualNetwork and one consumer per ExternalIP;
- reject an ExternalIPAttachment or second NATGateway that would consume the
  same ExternalIP;
- dispatch SNAT only after both referenced objects are Ready/Allocated and
  the VN segment exists; and
- validate manager-reported SNAT state before marking the NATGateway Ready.

**Workload attachments and status.** Every ComputeInstance, Cluster, and
BaremetalInstance create path must:

- apply the same omitted/empty/partial defaulting matrix, including Catalog
  and Template resolution precedence;
- validate the complete resolved attachment set against the shared Subnet,
  NetworkACL, VirtualNetwork, readiness, and IPv4 rules;
- reject network-owned updates and patches after persistence, including
  nested references, list order/cardinality, primary designation,
  `auto_external_ip_attachment`, and BM interface selection;
- permit controllers to write only status, conditions, and finalizers; and
- validate every discovered status value before exposing it: canonical IPv4,
  matching resolved subnet/interface, no duplicate status entry, and a
  cardinality consistent with the service-specific design.

#### Operation and lifecycle validation

Validation applies to operations as well as field values. The supported
tenant surface is intentionally narrow:

- **Create:** the caller may provide only network fields documented in the
  resource-specific contract. The server validates the complete request
  before persistence, resolves defaults, and stores the complete effective
  network spec. A caller cannot create an object with an unresolved
  dependency merely because a manager might become Ready later. An existing
  dependency in `Pending`, `Failed`, or `Deleting` state returns the shared
  field-specific `FailedPrecondition` detail; only the allowlisted automatic
  ExternalIP/ExternalIPAttachment transaction may persist Pending children.
- **Provider-owned resources:** NetworkClass and ExternalIPPool operations
  are provider/deployment operations. A tenant create, update, patch, replace,
  or delete request for either resource is rejected by authorization before
  semantic validation. A tenant may read or reference only the pool made
  visible by the provider's scope policy; it cannot supply a deployment pool
  definition or mutate its CIDRs, family, capacity, or lifecycle. A provider
  may perform a metadata-only update on an ExternalIPPool using the standard
  metadata contract; the update must not contain any pool network field.
- **Read and list:** the API applies the existing tenant/project/provider
  scope before returning network resources, attachments, or references. A
  caller cannot use a list filter, typed reference, Catalog Item, or status
  field to discover or mutate another tenant's network objects.
- **Update, patch, and replace:** requests that change any network-owned
  field are rejected, including changes hidden inside a field mask or nested
  message. This includes resource references, CIDRs, rule lists, attachment
  list length/order, `primary`, interface, target oneof, endpoint enum,
  `auto_external_ip_attachment`, and provider-resolved implementation data.
  The server must compare the complete immutable network portion, not only
  top-level protobuf fields.
- **Delete:** a delete request is admitted only after the service validates
  every direct reverse reference and child relationship defined in the shared
  dependency graph. Tenant-managed dependents always block deletion; parent
  deletion never deletes, detaches, retargets, or changes a tenant-managed
  child to Pending. A dependent that has a deletion timestamp but has not yet
  been archived or otherwise confirmed absent is still a blocker, because it
  may still hold a backend relationship.
- **Auto-created delete exception:** the only cascades permitted by this
  contract are allowlisted OSAC-owned resources with an exact immutable owner
  relationship:
  - For a workload's automatic external access, the order is
    `ExternalIPAttachment -> ExternalIP`.
  - For an onboarding-created default `NATGateway`, OSAC deletes its owned
    automatic `ExternalIP` only after the NATGateway's own backend cleanup has
    completed. VirtualNetwork deletion never directly cascades to the
    NATGateway or its ExternalIP.
  Neither exception cascades to the `ExternalIPPool` or to tenant-created
  resources. If any tenant-managed blocker exists, no auto-created child is
  deleted as a partial side effect and the parent delete is rejected.
- **Delete failure:** a rejected delete returns `FAILED_PRECONDITION`, leaves
  the target and every dependency unchanged, and identifies each direct
  blocker by resource kind, ID/name, relationship field, and the action needed
  to remove it. The same information is exposed in machine-readable status
  details for CLI and UI clients.
- **Delete completion:** after admission, a resource may remain in
  `Deleting` while its own backend finalizers run. A finalizer may clean
  external infrastructure, but it must not bypass a dependency guard or delete
  tenant-managed API resources. A networking finalizer remains until its
  cleanup succeeds; it must not be removed merely to leave an orphan.
- **Soft-deletion lifecycle:** successful delete admission marks the target
  `Deleting`; archival/removal happens only after the target's own finalizers
  complete. A deletion timestamp is not absence for reverse-reference checks,
  and cleanup failure keeps the target and finalizer present for retry.
- **Retry and idempotency:** retrying the same create or reconciliation input
  must not create a second default resource, a second NATGateway for a VN,
  duplicate NetworkACL rule, duplicate ExternalIP allocation, or second
  backend segment. A retry may adopt only an existing object whose immutable
  identity, owner, parent, and network spec exactly match the request.
- **Status and finalizers:** controller status, conditions, timestamps, IP
  discovery, and finalizers are the only mutable controller-owned outputs.
  Status is never accepted as an alternate input path for network spec, and a
  finalizer cannot be used to bypass an API immutability or dependency guard.
- **Direct CR/API bypass:** operator admission/CEL and controller checks must
  reject the same unsupported values if a CR is submitted without going
  through fulfillment-service. The hub CR is not a weaker API surface.
- **Backend failure:** a manager may report Pending, Ready, or Failed only
  through the defined reconciliation state machine. A caller cannot force
  Ready by setting status, and a controller cannot report Ready when any
  required manager or dependency is still Pending/Failed.

## Proposal

### NetworkClass

NetworkClass is the provider-level CRD that defines which managers handle
networking for the deployment. Tenants never interact with it. One
NetworkClass per deployment.

#### Manager combinations

OSAC networking is handled by two managers:

- **Fabric Manager** (optional) — a single provider-configured implementation
  that manages the complete physical networking contract: tenant isolation,
  SecurityGroup and NetworkACL policy, IP allocation, DNAT, SNAT, and
  inter-subnet L3 routing within a VirtualNetwork. When a VN has multiple
  subnets, the fabric manager provides the L3 gateway for each subnet and
  routes between them automatically.

- **K8s Manager** (optional) — provides the complete K8s implementation for
  every canonical resource and workload scope, and may bridge an OVN overlay
  to a fabric when paired with a Fabric Manager. In K8s-only mode it is the
  direct target for every resource and workload operation. Manager-specific
  profiles define concrete entrypoints and may use temporary successful no-op
  AAP roles while implementation work is in progress. MetalLB IPAddressPool
  CRs for CaaS VIP allocation are created at subnet creation time when the
  selected K8s manager implements the common CaaS path, gated on
  `NetworkClass.spec.metallb_vip_prefix_length`.

#### Why Two Managers?

When a Fabric Manager is present, it is one implementation. The deployment
does not split isolation, ACL, IP allocation, or translation across unrelated
per-action drivers on the same fabric. The single `fabricManager` field
captures this provider-owned implementation choice.

The K8s side is a separate concern: it bridges the OVN overlay to the
physical fabric. The mechanism depends on the deployment — see
[How VMs Join the Fabric](#how-vms-join-the-fabric) for the available
options. The goal is always the same: make VMs part of the fabric. A single
`k8sManager` field captures this.

When both managers are present, every networking resource and workload
operation is dispatched to both configured managers. There is no per-resource,
per-scope, or per-service target selection. There is no VM-vs-BM distinction
for shared resource operations; workload-specific placement and attachment
mechanics remain in the service designs, while every manager owns the complete
contract.

At least one manager is required. A K8s-only manager is a supported deployment
mode and is authoritative for the complete contract. Every configured manager
receives every canonical networking resource operation and every workload
scope operation. One configured manager produces one internal target; two
configured managers produce two targets, and both must complete before the
resource or workload is Ready. There is no unsupported-resource or
unsupported-scope branch in the public API. During development, a selected
manager's AAP job may be a successful no-op, but the dispatcher still sends the
operation to that manager and records its normal result.

The operator resolves the manager combination into an internal dispatch plan.
There is no tenant-settable or persisted `VirtualNetwork.spec.implementation_strategy`
field. The operator-owned implementation-strategy annotations described in
[Dispatcher and AAP job routing](#dispatcher-and-aap-job-routing) are routing
metadata only; tenants never select a manager or implementation strategy per
VirtualNetwork.

#### NetworkClass Examples

**Fabric Manager + CUDN (VMs and BM):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: moc-site-1
spec:
  fabricManager: <configured-fabric-manager>
  k8sManager: cudn_localnet
  defaults:
    virtualNetworkCIDR: 10.0.0.0/16
    ipv4SubnetCIDR: 10.0.1.0/24
status:
  capabilities:
    addressFamily: ipv4
```

**BM-only deployment (no VMs):**

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: gpu-site-1
spec:
  fabricManager: <configured-fabric-manager>
  defaults:
    virtualNetworkCIDR: 10.2.0.0/16
    ipv4SubnetCIDR: 10.2.0.0/24
status:
  capabilities:
    addressFamily: ipv4
```

**K8s-only deployment (no Fabric Manager):**

The topology is shared here; the current manager registration and complete
manager contract are defined in the [K8s-only Networking Manager design](/enhancements/OSAC-1433-k8s-only-k8s-manager/design.md).

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: NetworkClass
metadata:
  name: ovn-only-1
spec:
  k8sManager: <configured-k8s-only-manager>
  defaults:
    virtualNetworkCIDR: 10.0.0.0/16
    ipv4SubnetCIDR: 10.0.1.0/24
  metallbVipPrefixLength: 28 # required by the shared CaaS VIP contract
status:
  capabilities:
    addressFamily: ipv4
    # All canonical resources and VMaaS, BMaaS, and CaaS workload scopes are
    # part of the selected manager contract. No per-resource support matrix is
    # exposed.
```

#### Manager contract

All networking managers and NetworkClasses expose IPv4-only behavior. IPv6 and
dual-stack networking are not supported. The manager registration has no
per-resource, per-policy, per-scope, or per-service subset declaration. Selecting a
manager means selecting the complete OSAC networking contract: VirtualNetwork,
Subnet, SecurityGroup, NetworkACL, ExternalIPPool, ExternalIP,
ExternalIPAttachment, NATGateway, and the VMaaS, BMaaS, and CaaS workload
flows.

The provider validates the complete manager profile before the NetworkClass is
Ready. A development profile may route a not-yet-implemented operation to a
successful no-op AAP role; this keeps the API and dispatcher contract uniform
while the backend is being completed. It is not reported as an unsupported
resource, workload scope, or manager-specific contract and must not be used to claim
production dataplane readiness.

The only deployment-wide value exposed in NetworkClass status is the fixed
`addressFamily: ipv4` contract, alongside ordinary readiness and job status.

#### Manager Registration (ConfigMap)

Each manager ships a ConfigMap declaring its type and capabilities. These
ConfigMaps are deployed as part of the OSAC installation alongside the
manager's Ansible roles.

The ConfigMap identifies the manager and its type. It does not contain a
resource, policy, workload-scope, or service subset declaration. Provider
installation validation verifies that the selected profile contains the
complete OSAC operation set before NetworkClass Ready. A temporary development
profile may use successful no-op AAP roles for unfinished operations; the
dispatcher still invokes those jobs using the normal resource and workload
contracts.

**Fabric managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fabric-manager
  namespace: osac
  labels:
    osac.openshift.io/network-fabric-manager: "true"
data:
  name: <configured-fabric-manager>
  description: "Provider fabric implementation — tenant isolation, ACL, IPAM, DNAT, SNAT"
  capabilities: "addressFamily:ipv4"
```

**K8s managers:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-<profile>
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: <configured-k8s-manager>
  description: "Provider K8s networking implementation"
  capabilities: "addressFamily:ipv4"
```

Every manager profile must implement every canonical resource and all three
workload scopes. Native Kubernetes NetworkPolicy alone does not satisfy the
OSAC policy contracts; a development-only no-op role may temporarily stand in
for unfinished policy behavior without changing the public API or registration
shape. Concrete profiles document backend mappings, not advertised subsets.

The `cudn_evpn` K8s manager is defined by the [OSAC-4291 Phase 1 design](/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking/design.md).
It is a separate manager profile and inherits the complete manager contract;
this shared contract does not expand CUDN-EVPN feature behavior.

The operator discovers managers by listing ConfigMaps with the appropriate
labels. When a NetworkClass is created, the operator validates each manager
assignment against the corresponding ConfigMap and verifies the complete
manager profile. Adding a new manager means deploying a new ConfigMap and
Ansible role — no tenant API changes are needed.

See the [K8s-only Networking Manager design](/enhancements/OSAC-1433-k8s-only-k8s-manager/design.md)
for the concrete current K8s-only manager profile. Its backend mappings are
implementation details of the complete contract; they do not define optional
resource or workload support.

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

In a K8s-only deployment there is no physical Fabric Manager. The configured
K8s manager provides the complete networking API and all three workload service
integrations in the OVN/Kubernetes networking domain. The concrete backend
mechanics are defined in the [K8s-only Networking Manager
design](/enhancements/OSAC-1433-k8s-only-k8s-manager/design.md), but they do not
change the public resource or service contract.

The same complete contract applies in K8s-only, Fabric-only, and combined
deployments. In a combined deployment both selected managers receive every
resource and workload operation. If an implementation is temporarily
unfinished, its AAP role may complete successfully as a provider-internal
no-op; the API still admits the operation and does not expose a partial
capability or service-selection branch.

### Infrastructure-Agnostic Subnets

VirtualNetwork and Subnet do not carry a scope or service field. Subnets are
infrastructure-agnostic — the dispatcher provisions the configured network
backend(s) for every subnet. Any resource type can be placed on any subnet
permitted by the shared placement contract.

At subnet creation, the dispatcher sends the operation to every configured
manager:

1. **Fabric manager** — creates the fabric segment (for example VLAN or VPC).
2. **K8s manager** — creates the K8s overlay on each hosting cluster; in a
   combined deployment it also performs the configured bridge/integration work.

Every configured manager receives the Subnet operation. The same complete
manager rule applies to VirtualNetwork, SecurityGroup, NetworkACL,
ExternalIPPool, ExternalIP, ExternalIPAttachment, and NATGateway; manager
presence always means that the manager is an implementation target.

With both managers, VMs are placed in the K8s overlay and BM servers and
cluster nodes are placed directly on the fabric segment. In K8s-only mode,
all three workload services use the selected K8s manager's networking domain;
service-specific designs define the mechanics, not manager eligibility.

Manager-specific placement constraints remain implementation validation inside
the complete service contract. For example, the Phase 1 cudn_evpn manager may
limit where its current VM placement implementation can run; that does not
create a public manager capability or a resource/service rejection branch.
Development-only AAP stubs may complete the operation while the placement
implementation is being delivered.

### Dispatcher and AAP job routing

The osac-operator acts as a dispatcher: it resolves the single deployment
NetworkClass, validates the referenced complete manager registrations, and
builds an internal dispatch plan. The plan contains one target per configured
manager, never zero targets, and never a combined implementation-strategy
string. Targets are ordered deterministically as `fabric`, then `k8s`:

| Effective targets | Result |
|---|---|
| Fabric only | One Fabric target and one Fabric AAP job |
| K8s only | One K8s target and one K8s AAP job |
| Fabric and K8s | Two targets and two AAP jobs; both must succeed |

The K8s-only case is not a physical-network fallback. It is direct dispatch to
the K8s manager's implementation for that resource. The concrete entrypoint
and current supported-resource table are maintained in the [K8s-only
Networking Manager design](/enhancements/OSAC-1433-k8s-only-k8s-manager/design.md).

The same rule applies in a combined deployment: both managers receive every
resource and workload operation. The operator does not infer partial support
from manager type, workload type, or a resource-specific registration field.

#### Manager resolution and implementation annotations

`NetworkClass.spec.fabric_manager` and `NetworkClass.spec.k8s_manager` are
manager-registration references, not tenant-selectable implementation values.
The resolver fetches each referenced ConfigMap by its manager label and
`data.name`, rejects missing or wrong-type registrations, and returns the
validated manager names to the dispatcher.

The operator retains two internal annotations for AAP routing:

| Annotation | Meaning |
|---|---|
| `osac.openshift.io/implementation-strategy` | The primary/legacy target. It contains the Fabric manager name when a Fabric target exists; otherwise it contains the K8s manager name. This is why the key has no `fabric` prefix. |
| `osac.openshift.io/k8s-implementation-strategy` | The second K8s target's manager name, present only when the same resource is dispatched to both Fabric and K8s targets. It is absent for K8s-only resources. |

These annotations are controller-owned, are not accepted from tenant input,
and are not combined into values such as `netris+<k8s-manager>`. They are persisted
so deletion can select the same targets even when a parent resource used for
resolution has already been deleted.

#### AAP translation

The operator uses the standard action template for the resource, for example:

```text
VirtualNetwork create       -> osac-create-virtual-network
Subnet delete               -> osac-delete-subnet
ExternalIPAttachment create -> osac-attach-external-ip
```

The AAP event contains the complete resource as `osac_job_vars.resource`.
The playbook reads the generic implementation-strategy annotation and includes
the manager role:

```text
osac.templates.<manager-name>
```

For a two-target plan, the operator launches the same action once per target.
For each launch it passes a resource copy whose generic annotation is
temporarily set to that target's manager name. The persisted resource is not
mutated by this per-job override. Job status records carry the target role
(`fabric` or `k8s`), and the resource becomes Ready only after every selected
target's latest job succeeds. A failure or Pending result on any selected
target prevents Ready and is retried independently.

Read and list operations are fulfillment-service operations over the persisted
OSAC resource and controller status; they do not launch an AAP job or require
the manager to be resolvable at read time. Backend health and readiness are
reported asynchronously through reconciliation. Create and delete are the
operations that dispatch to the selected manager targets.

Deletion uses the persisted target metadata and launches the corresponding
delete action for every target that provisioned the resource. A target is not
invented during deletion, and a manager outside the persisted dispatch plan is
never called.

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
  ├── Subnet              → every configured manager
  ├── SecurityGroup       → every configured manager
  ├── NetworkACL          → every configured manager
  └── NATGateway          → every configured manager

ExternalIPPool (deployment-scoped, provider-managed)
  └── ExternalIP (tenant-managed) → every configured manager

ExternalIPAttachment (tenant-managed)
                          → every configured manager; references an ExternalIP
                            and a target resource
```

### ExternalIPPool

"External" in ExternalIPPool/ExternalIP means **external to the
VirtualNetwork**. In the supported connected deployment boundary, the
  provider supplies the routable addresses and every selected manager
allocates or reserves its implementation of them. Air-gapped deployment
behavior is outside the supported contract.

ExternalIPPools are provider-managed and deployment-scoped. Every selected
manager handles its ExternalIP allocation — one pool serves all
resource types.

### Normative CLI contract

The CLI is a client of the public API; the server remains authoritative for
all validation. The CLI may reject malformed syntax locally, but it must not
silently repair, drop, replace, or default an explicitly supplied value.
Server validation errors are displayed with their API field path and backend
status: `InvalidArgument` for malformed or contradictory input,
`FailedPrecondition` for an existing dependency that is not Ready/Allocated,
and `PermissionDenied` or visibility-safe `NotFound` for unauthorized scope.
For a strict dependency failure, the CLI also displays each dependency
blocker's kind/name, observed state, required state, and the remediation to
wait and retry. It must not turn this failure into a local Pending operation or
silently retry the create while the dependency is unready.

#### Common command and reference rules

- Network-owned resources expose `create`, `get/list`, and `delete` through
  the CLI. They do not expose update, patch, or replace operations for
  network-owned `spec` fields. Workload update commands may update
  non-network fields only; attempts to change a network-owned field or
  `auto_external_ip_attachment` are rejected and require delete/recreate.
- Resource names use `--name`. Network references use the target's name in
  the field-specific flag. Where the generic typed-reference client supports
  an ID form, `--<field>-id` is accepted only as a consistency check alongside
  `--<field>` and must resolve to the same object; ID-only input is rejected
  because every reference requires `name`. Project/shared scope modifiers are
  allowed only for full references whose API field permits that scope; local
  Subnet, NetworkACL, and VirtualNetwork references remain in the caller's
  tenant/project.
- The CLI serializes every reference as the typed reference object required by
  the API, for example `{ "name": "app-subnet" }`; it never sends a raw ID or
  string in a reference-bearing field. Names, IDs, project scope, and shared
  scope follow [OSAC-1330](../OSAC-1330-type-safe-resource-references/design.md).
- `--cidr` and `--cidrs` values must be canonical IPv4 CIDRs in
  `a.b.c.d/prefix` form, with host bits zero. IPv6, dual-stack values, bare
  addresses, host bits, and invalid prefixes are rejected. There is no
  `--ipv6`, `--dual-stack`, `--hub`, or `--air-gapped` networking mode.
- Each tenant's default NetworkACL contains the explicit default ACL policy:
  deny all ingress and allow all egress. There is no CLI flag for changing
  that tenant policy. Separately, the
  provider-owned deployment baseline is hard-coded to `permit` all traffic,
  is the least-specific fallback, and is not tenant data or a tenant CLI
  input. Controller-owned dispatch annotations, manager selection on a tenant
  VirtualNetwork, and provider capabilities are not tenant CLI inputs.

#### Provider networking commands

NetworkClass is provider-owned. Tenants have no NetworkClass create, update,
patch, or delete command. If the provider CLI manages NetworkClass, its
canonical create shape is:

```bash
osac admin create networkclass \
  --name <networkclass-name> \
  --fabric-manager <name> \
  --k8s-manager <name> \
  --virtual-network-cidr <ipv4-cidr> \
  --ipv4-subnet-cidr <ipv4-cidr> \
  [--metallb-vip-prefix-length <prefix>]
```

`--name` is required and identifies the provider-owned NetworkClass in the
deployment. `--fabric-manager` and `--k8s-manager` are independently
optional, but at least one must be present. The two default CIDRs are required
and canonical;
the subnet CIDR must be contained by the VirtualNetwork CIDR. The MetalLB
prefix is supplied for the CaaS VIP allocation path and must satisfy the shared
prefix and containment validation. The dispatch plan is derived from
the managers and is never accepted as a flag. Each tenant's
  default NetworkACL policy is fixed to deny-all ingress and allow-all egress
  and is provisioned through tenant default-resource handling, not this
  deployment command. Separately, the provider-owned deployment default ACL
policy is hard-coded to `permit` all traffic and is not a tenant or
CLI-configurable field.

ExternalIPPool is provider-managed and deployment-scoped:

```bash
osac admin create externalippool \
  --cidrs <one-canonical-ipv4-cidr> \
  --ip-family ipv4 \
  --name <pool-name>
```

`--cidrs` retains its plural API-compatible spelling but accepts exactly one
value and may occur only once. A second value, IPv6 value, omitted
`--ip-family`, or an unsupported family is rejected. Separate pools are used
instead of multiple CIDRs in one pool.

#### Tenant network resource commands

```bash
osac create virtualnetwork --cidr <ipv4-cidr> --name <vn-name>
osac create subnet --virtual-network <vn-name> \
  --cidr <contained-ipv4-cidr> --name <subnet-name>
osac create security-group --virtual-network <vn-name> --name <sg-name> \
  --rule 'direction=ingress,protocol=tcp,port=22,source-cidr=192.0.2.0/24'
osac create network-acl --virtual-network <vn-name> \
  --subnet <subnet-name> \
  --rule 'action=allow,direction=ingress,protocol=tcp,port=443,source-cidr=0.0.0.0/0' \
  --name <network-acl-name>
```

`--virtual-network` and `--pool`/target reference flags identify existing
resources by name (or by the corresponding typed-reference ID form where the
field supports it). The referenced VirtualNetwork must be Ready and in the
same tenant/project for Subnet, SecurityGroup, and NetworkACL creation.
SecurityGroup creation requires at least one allow-only rule. NetworkACL
creation requires one or more explicit `--subnet` references. Every referenced Subnet
must be Ready, belong to the VirtualNetwork, and have no existing effective
NetworkACL association. The system-created default ACL counts as an effective
association. A single NetworkACL may be associated with multiple Subnets. The
Subnet CIDR must be contained by its parent and must not overlap a sibling
Subnet. Replacing a default ACL uses the documented default-resource
replacement workflow after the old default and its blockers have been removed.

For SecurityGroup, `--rule` is repeatable, one SecurityGroupRule per occurrence.
Each rule contains `direction`, `protocol`, an optional single `port`, and
exactly one direction-appropriate `source-cidr` or `destination-cidr`. It must
not contain an `action` key; SecurityGroup rules are allow-only and unmatched
traffic is denied. Multiple SecurityGroups on a workload aggregate their
allow rules.

For NetworkACL, `--rule` is repeatable, one NetworkACLRule per occurrence. Each rule uses
the key/value grammar shown above and must contain:

- `action`: `allow` or `deny`;
- `direction`: `ingress` or `egress`;
- `protocol`: `tcp`, `udp`, `icmp`, or `any`;
- `port`: optional for `tcp`/`udp` (omission matches all ports), omitted for
  `icmp`/`any`, and within `1..65535` when supplied; and
- exactly one of `source-cidr` for ingress or `destination-cidr` for egress,
  using a canonical IPv4 CIDR.

Port ranges, unknown keys, duplicate rules, conflicting equal-specificity
rules, IPv6 CIDRs, and an empty rule list for a user-created NetworkACL are
rejected. Each tenant's default NetworkACL contains explicit deny-all ingress
and allow-all egress rules. A separate provider-owned deployment baseline is
always present as the least-specific fallback and is currently hard-coded to
`permit` all traffic; it is not serialized in the tenant ACL. Every selected
manager receives the NetworkACL operation. Native Kubernetes NetworkPolicy
alone does not change the OSAC NetworkACL contract; while an implementation is
being completed, its AAP role may execute as an internal successful no-op.

#### Workload attachment grammar

All three workload commands use one CLI option even though VM and BM API
fields are repeated. The option selects a Subnet; the effective NetworkACL is
inherited from that Subnet:

```text
--network-attachment subnet=<subnet-name>[,security-groups=<sg-name>...]\
[,interface=<port-name>]
```

The option may occur zero or one time. Repeating the option, using an unknown
key, or providing an empty key/value is rejected. `security-groups` is a
repeatable comma-separated typed local reference list; duplicates are rejected.
Omitting the entire option
means the API receives an omitted/empty attachment field and resolves the
tenant default Subnet and the default SecurityGroup only when that Subnet is in
the tenant default VirtualNetwork and the group is available. There is no
workload-level NetworkACL key; ACL
associations are managed through the NetworkACL resource.

The CLI does not emit `primary`; the sole attachment is implicitly primary.
If a raw structured CLI input exposes the compatibility field, only omitted
or `primary=true` is accepted and `primary=false` is rejected. The CLI does
not expose `--network-attachments`, a multi-NIC mode, or a way to bypass
defaulting.

The canonical resource mappings are:

| Resource | API field and value type | CLI form | Additional allowed keys |
|---|---|---|---|
| ComputeInstance | repeated `network_attachments` of `ComputeNetworkAttachment`, zero or one | one optional `--network-attachment` | `subnet`, `security-groups`; `interface` is forbidden |
| BaremetalInstance | repeated `network_attachments` of `BareMetalNetworkAttachment`, zero or one | one optional `--network-attachment` | `subnet`, `security-groups`, optional `interface` |
| Cluster | singular `network_attachment` of `ClusterNetworkAttachment` | one optional `--network-attachment` | `subnet`, `security-groups`; `interface` and `primary` are forbidden |

For BaremetalInstance, `interface=<port-name>` must identify a valid
non-lifecycle port from the effective BareMetalInstanceType. When omitted,
BMaaS selects the first valid `fabric` port. For ComputeInstance and Cluster,
an interface key is invalid rather than ignored. Cluster has one attachment
for all node sets; the system resolves each node set's physical fabric
interface and the tenant cannot provide per-node-set network values.

#### External access and attachment commands

The create-time flag `--external-ip-attachment` maps to
`auto_external_ip_attachment: true` for ComputeInstance, BaremetalInstance,
and Cluster. If omitted, the value is false. The flag cannot be used on an
update command because the field is immutable after create.

Explicit ExternalIP creation and attachment use:

```bash
osac create externalip --pool <ready-pool-name> --name <ip-name>
osac create externalipattachment --externalip <allocated-ip-name> \
  --compute-instance <ready-vm-name> --name <attachment-name>
osac create externalipattachment --externalip <allocated-ip-name> \
  --baremetal-instance <ready-bm-name> --name <attachment-name>
osac create externalipattachment --externalip <allocated-ip-name> \
  --cluster <ready-cluster-name> --target-endpoint api \
  --name <attachment-name>
```

Exactly one target flag is required: `--compute-instance`,
`--baremetal-instance`, or `--cluster`. `--target-endpoint` is required for
Cluster and accepts only `api` or `ingress`; it is forbidden for VM and BM.
The ExternalIP must be Allocated and unused, the target must be Ready, and a
Cluster endpoint must already be discovered. A caller cannot create a
Pending forward reference; only internal auto-provisioning can do that.

NATGateway uses:

```bash
osac create natgateway --virtual-network <ready-vn-name> \
  --externalip <allocated-unused-ip-name> --name <gateway-name>
```

Only one NATGateway may exist per VirtualNetwork. NATGateway has no
update/replace command. Every selected manager receives the operation; an
unfinished implementation may use a successful internal no-op AAP role.

### End-to-End Flows

This section shows how the unified networking API works from the tenant's
perspective. The flows are the same regardless of which fabric manager or
K8s manager the provider has deployed.

#### Provider Setup

1. Provider deploys the configured networking manager(s) and hosting cluster(s)
2. Provider creates NetworkClass for the deployment (provider-only,
   tenants never see it)
3. Provider creates ExternalIPPool:

```bash
osac admin create externalippool \
  --cidrs 203.0.113.0/24 \
  --ip-family ipv4 \
  --name external-pool-1
```

The ExternalIPPool controller registers the range with every selected manager.
The concrete
implementation is defined by the selected manager profile; a Fabric Manager
uses its own IPAM, while the current K8s-only profile is documented in the
[K8s-only Networking Manager design](/enhancements/OSAC-1433-k8s-only-k8s-manager/design.md).
The pool is Ready only after the selected implementation(s) confirm the range.

#### Networking Setup (Same for All Resource Types)

The tenant creates networking resources. This workflow is identical
regardless of whether the tenant plans to run VMs, clusters, or bare-metal
servers.

**Create VirtualNetwork:**

```bash
osac create virtualnetwork --cidr 10.0.0.0/16 \
  --name my-net
```

Every configured manager creates its implementation of the isolated tenant
segment.

**Create Subnet:**

```bash
osac create subnet --virtual-network my-net --cidr 10.0.1.0/24 \
  --name my-subnet
```

Every configured manager creates its subnet backend. If both managers are
configured, the Fabric Manager creates a fabric segment and the K8s Manager
creates an overlay on each eligible hosting cluster and bridges it to that
segment, subject to the selected manager's hosting-cluster limits.

**Create SecurityGroup:**

```bash
osac create security-group --virtual-network my-net --name my-sg \
  --rule "direction=ingress,protocol=tcp,port=443,source-cidr=0.0.0.0/0"
```

The SecurityGroup is implemented by every configured manager. If both managers
are configured, both must report successful enforcement before the group is
Ready. The rules are
allow-only and stateful; unmatched traffic remains denied.

**Create NetworkACL:**

```bash
osac create network-acl --virtual-network my-net --name my-nacl \
  --subnet my-subnet \
  --rule "action=allow,direction=ingress,protocol=tcp,port=443,source-cidr=0.0.0.0/0"
```

Every configured manager creates the stateless ACL rules at the associated
Subnet boundary. If an implementation is not yet complete, its AAP role may
execute as a temporary successful no-op while the API and resource lifecycle
remain available.

#### SecurityGroup Rule Semantics

SecurityGroup rules are stateful allow rules attached to a workload through
its network attachment. There is no `allow`/`deny` action field. The default
SecurityGroup may contain no rules, which means that unmatched traffic is
denied. Tenant-created groups require at least one rule.

When multiple SecurityGroups are attached, their allow rules are aggregated;
an allowed match in any attached group permits the SecurityGroup layer. There
is no deny rule and no most-specific override at this layer. Once a flow is
accepted, its return traffic is allowed by connection state. The final packet
decision still requires the effective Subnet NetworkACL to allow the packet.

#### NetworkACL Rule Semantics

NetworkACL behavior is uniform across VMaaS, CaaS, and BMaaS. It is enforced
at the Subnet boundary, independently for ingress and egress, and without
connection tracking.

Each tenant's default NetworkACL is associated with its default Subnet and
contains the default ACL policy:

```text
ingress: deny  any  0.0.0.0/0
egress:  allow any  0.0.0.0/0
```

Every selected manager receives the default NetworkACL operation. The
deployment `permit` baseline is separate from the tenant default ACL and does
not replace it during development.

Each packet is evaluated independently. Tenant rules take precedence whenever
they match; when no tenant rule matches, the provider-owned deployment baseline
applies, currently permitting all traffic. If an inbound TCP connection is
allowed on port 443, the return packets are still evaluated independently. The
ACL does not infer or add an opposite-direction tenant rule; such a rule is
required when the tenant needs to control the return path with tenant policy.

When rules overlap, the most-specific matching rule wins. Specificity is
ordered by longest matching remote CIDR prefix, exact protocol over `any`, and
exact port over an omitted port. Conflicting equal-specificity rules are
rejected. These semantics apply separately to ingress and egress.

#### Resource Creation (Differs by Type)

The networking setup above is shared. Only the resource creation step
differs internally — the tenant CLI experience is the same for all types.

**ComputeInstance (VM):**

```bash
osac create computeinstance --template ocp_virt_vm \
  --network-attachment subnet=my-subnet \
  --name my-vm
```

VM is placed in the K8s overlay namespace on a hosting cluster. Because the
overlay is bridged to the fabric, the VM is directly on the fabric segment
and gets an IP from the subnet CIDR.

**BaremetalInstance:**

BareMetalInstanceTypes may describe multiple physical network ports. The tenant
discovers available network ports via the BareMetalInstanceType API — each
BareMetalInstanceType lists its network ports with name, role, type, and speed
(see [BareMetalInstanceType and Interface Resolution](#baremetalinstancetype-and-interface-resolution)).
BMaaS selects exactly one of those interfaces for the tenant network. The
tenant specifies the single interface-to-subnet mapping, or omits `interface`
and lets the fabric manager select the default.

Single interface:

```bash
osac create baremetalinstance --template bcm_h100 \
  --network-attachment interface=data-0,subnet=my-subnet \
  --name my-server
```

The fabric manager configures the selected host switch port on the
corresponding fabric segment. The interface gets an IP from the subnet's CIDR.

Validation rules:
- All referenced subnets must belong to the same VirtualNetwork
- BMaaS accepts at most one network attachment per BaremetalInstance
- If an attachment is provided, its `interface` must reference a valid port
  name from the BareMetalInstanceType's network ports list

**Cluster:**

```bash
osac create cluster --template ocp_4_17_small \
  --network-attachment subnet=my-subnet \
  --node-set-size workers=3 --name my-cluster
```

The resolved ClusterTemplate owns the node-set names and
`baremetal_instance_type`; the request may provide only permitted sizes for
those existing node sets.

For the current supported release, **CaaS supports BM node sets only**.
VM-based cluster node sets are not supported. The fulfillment-service resolves
the interface from the BareMetalInstanceType (`fabric_interface` — first port
with role `fabric`). The BareMetalWorkerReconciler passes that resolved
interface to BMaaS, which owns the network attachment and switch-port
configuration during BMI provisioning.
See [CaaS Networking](/enhancements/OSAC-1436-caas-networking) for the detailed flow.

Cluster hardware profiles may expose multiple physical interfaces. Unlike
BaremetalInstance (where the tenant may specify the interface name), for
clusters the **system** resolves exactly one tenant-facing fabric interface
from each BareMetalInstanceType's `network_ports` list. The current CaaS
contract rejects multi-NIC node requests; additional inventory interfaces are
not additional tenant network attachments.
The tenant specifies which subnet to use (one per cluster); the system maps it to the
correct physical interfaces based on each node set's BareMetalInstanceType.

With a Fabric Manager, the resource ends up on the fabric and the manager sees
all resources equally. In K8s-only mode, the configured K8s Manager provides
the equivalent supported networking domain; there is still no VM-vs-BM API
distinction.

#### Catalog Item integration

Catalog Items are an optional, create-time governance layer over the resource
API. They govern the tenant-facing network field on a resource; they do not
create or select the provider's NetworkClass, VirtualNetwork, provisioning
network, fabric manager, or k8s manager.

The resource-specific Catalog fields are:

| Resource | Catalog-governed network field | System-resolved networking |
|---|---|---|
| ComputeInstance | `network_attachments` (the canonical per-resource field) | CUDN/NAD placement and the hosting namespace |
| Cluster | `network_attachment` (one attachment for the cluster) | `fabric_interface` for each node set |
| BaremetalInstance | `network_attachments` (at most one attachment) | Provisioning-network handoff and switch-side port operations |

At Create, Catalog policy and tenant input are resolved first, followed by
Template defaults. Default networking then resolves the workload Subnet and
SecurityGroup membership: an omitted or empty attachment receives the tenant
default Subnet and default SecurityGroup when those resources exist, while a
supplied attachment receives defaults only for missing fields. The effective
NetworkACL is inherited from the resolved Subnet; ACL references are never
workload fields. Supplied fields are never replaced. The final value is then
checked with the ordinary Subnet, SecurityGroup, NetworkACL, VirtualNetwork,
cardinality, primary, and interface rules for that resource type.

A shared Catalog Item cannot lock or default a tenant-local Subnet or
SecurityGroup. It must leave such values editable or ungoverned so the tenant
can supply them or receive the tenant's defaults. NetworkACL association is
never a Catalog or workload field. A tenant-owned item may reference resources
in its own tenant and project scope.

The Catalog `auto_external_ip_attachment` policy governs only whether the
resource-specific automatic external-access behavior is enabled. It does not
select an ExternalIP, ExternalIPPool, NATGateway, or allocation strategy. The
resulting side effect remains resource-specific: one automatically attached
ExternalIP for Compute and Bare Metal, and the API and ingress ExternalIPs for
Cluster.

Catalog governance ends after the resource is created. The resolved network
value is immutable after creation, including SecurityGroup membership and the
effective NetworkACL inherited from the Subnet.
Later changes require deleting and recreating the parent resource. Catalog
Item definitions and metadata remain governed by the Catalog Items design and
are outside this networking change.

See [Catalog Items v2](/enhancements/OSAC-3538-catalog-items-v2/design.md)
for the typed policy representation and reference lifecycle.

#### External Access (Same for All Resource Types)

External access operations are uniform across resource types. Every configured
manager handles the corresponding ExternalIP, ExternalIPAttachment, and
NATGateway operation. Manager type and K8s-only versus combined topology do
not change the public contract.

**Allocate ExternalIP:**

```bash
osac create externalip --pool external-pool-1 --name my-ip
```

Every selected manager allocates or reserves its implementation of the
ExternalIP (for example, `203.0.113.45`). The ExternalIP becomes Allocated
only after all selected implementations report success.

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

Every selected manager creates its DNAT rule: external IP → resource's
subnet IP. The ExternalIPAttachment becomes Ready only after all selected
implementations report success.
Each resource (ComputeInstance, BaremetalInstance) is associated with one
subnet and has one fabric IP — the DNAT targets that IP directly. For BMaaS,
that is the IP of the single tenant network attachment.

**Cluster ExternalIPAttachment flow:**

For VMs and BM, the DNAT target is the resource's fabric IP —
straightforward. For clusters, the DNAT target is a service-level VIP
(API server or ingress) that is discovered during cluster provisioning.
The VIP allocation is decoupled from the networking layer:

1. CaaS template creates MetalLB LoadBalancer Services for API server
   and ingress. MetalLB allocates VIPs from its IPAddressPool, created by the
   selected K8s manager at Subnet creation, or by the CaaS BM-only
   fabric-level path in a Fabric-only deployment.
2. Template discovers the allocated VIPs and writes them to ClusterOrder
   CR status (`apiEndpoint`, `ingressEndpoint`)
3. Feedback controller syncs VIPs to the Cluster object in the
   fulfillment service as `api_endpoint` and `ingress_endpoint` fields
4. ExternalIPAttachment controller reads the VIP from ClusterOrder
   status → dispatches DNAT creation to every selected manager for
   the attachment
5. ExternalIPAttachment transitions to Ready

The tenant can inspect the allocated VIPs:

```bash
osac get cluster my-cluster -o yaml
# api_endpoint: 10.0.5.20
# ingress_endpoint: 10.0.1.50
```

A caller-created ExternalIPAttachment may be created only after its
ExternalIP is Allocated and its target is Ready with the required endpoint.
The sole forward-reference exception is the internal auto-provisioning
transaction described below: it creates the Pending ExternalIP and Pending
attachment atomically with the parent workload. The asynchronous controller
then waits for both dependencies before programming DNAT and marking the
attachment Ready.

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
- osac-operator ExternalIP controller dispatches to AAP for every selected
  manager → all selected implementations allocate or confirm the IP
  address → ExternalIP transitions to **Allocated**
- osac-operator ExternalIPAttachment controller checks two
  preconditions before dispatching:
  - **ExternalIP must be Allocated** (have an allocated address). If
    not, the controller requeues.
  - **Target resource must have a known IP.** The required IP depends
    on the target type (see below). If not yet available, the
    controller requeues.
- Once both preconditions are met, the controller dispatches to AAP for every
  selected manager → all selected implementations create the DNAT
  rule → ExternalIPAttachment transitions to **Ready**

*ExternalIPAttachment controller preconditions per target type:*

| Target type | Required precondition | Source of target IP |
|-------------|----------------------|---------------------|
| ComputeInstance | `compute_network_attachment_statuses` populated with the single attachment's `ip_address` | Feedback controller reads the sole KubeVirt VMI interface status and writes at most one `ComputeNetworkAttachmentStatus` |
| Cluster | `status.apiEndpoint` or `status.ingressEndpoint` populated on ClusterOrder CR | MetalLB allocates VIP from IPAddressPool, template discovers and writes to ClusterOrder status |
| BaremetalInstance | the single `status.networkAttachmentStatuses[].ipAddress` populated for the selected interface | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches the selected port MAC (from the BareMetalHost `osac.openshift.io/interface-macs` annotation) to the assigned IP; operator writes to CR status |

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
- ExternalIPAttachment controller reads the single BMaaS tenant IP for DNAT target
- Tenant visibility (API response includes the allocated IP)

IP discovery mechanism per service type:

| Service | Discovery source | Who writes status | Status field |
|---------|-----------------|-------------------|-------------|
| VMaaS | KubeVirt VMI `status.interfaces[].ipAddress` | osac-operator feedback controller → Signal RPC → fulfillment-service | `ComputeInstanceStatus.compute_network_attachment_statuses[].ip_address` |
| CaaS | Cluster API/Ingress VIPs from ClusterOrder status; worker host IPs are not an ExternalIP target | Template writes VIPs to ClusterOrder status; the feedback controller syncs service endpoints. Agent watching is limited to MAC correlation and worker binding | `Cluster.status.api_endpoint` / `ingress_endpoint`; per-agent IP is not used for the shared ExternalIP flow |
| BMaaS | Operator queries fabric manager's DHCP lease API via dispatcher (`query_dhcp_lease` role) after provisioning completes; matches port MAC — from the BareMetalHost `osac.openshift.io/interface-macs` annotation — to the DHCP-assigned IP, falling back to server name for named fabric servers (see [BMaaS OQ#4 — Resolved](/enhancements/OSAC-1437-bmaas-networking/design.md#4-how-is-the-hosts-runtime-ip-discovered-after-network-reconfiguration)) | bare-metal-fulfillment-operator dispatches `query_dhcp_lease` → writes to CR status → feedback controller → Signal RPC → fulfillment-service | `BareMetalInstanceStatus.network_attachment_statuses[].ip_address` |

The fabric manager's `move_network_attachment` role is switch-side
only — it moves a host's fabric port from one network segment to another
(`from_vnet_name` → `to_vnet_name`, either side optional). Attach and
detach are the **same primitive**: on provision the port moves from a
**provisioning network** to the tenant subnet's network segment; on deletion it
moves back to the provisioning network. The role operates purely against the
fabric (no Subnet CR lookup) and is keyed on plain segment names, so the caller
resolves the typed Subnet reference to a tenant segment name and supplies the provisioning
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
- **CaaS:** BMaaS creates each worker on demand and provisions it on the
  provisioning network. After OS provisioning, BMaaS moves the selected port
  to the tenant network, reboots the host so it requests DHCP there, and
  discovers the tenant IP through the fabric DHCP lease API. CaaS watches
  Agent objects only to correlate the booted worker to its BMI and bind it to
  the NodePool; it does not use Agent status as the network-IP discovery
  source.

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

The API and direct hub-CR admission path must evaluate these preconditions
before persisting a new NATGateway. If either is not met, a new create is
rejected with the shared field-specific `FailedPrecondition`; it is not
persisted as a Pending NATGateway merely to wait for the dependency.

After a NATGateway has been admitted successfully, its controller rechecks
both preconditions before every backend dispatch. If a dependency is
temporarily unavailable or its own SNAT operation is still in progress, the
controller requeues that already-admitted NATGateway. If a dependency becomes
terminally Failed or is being deleted, the NATGateway reports the documented
failure and does not dispatch SNAT. Requeueing is therefore a reconciliation
retry for an existing object, never an admission path for an invalid create.

*Auto-provisioned resource labeling:*

All auto-created resources receive the canonical marker
`osac.openshift.io/auto-created: "true"` and an immutable exact owner
relationship containing the owner kind and owner ID. Auto-provisioned
ExternalIPs and ExternalIPAttachments are eligible for the workload-delete
cleanup, and the ExternalIP created for an onboarding default NATGateway is
eligible for cleanup by that exact NATGateway owner after NAT backend cleanup.
An owner label may support indexed lookup, but a label alone is not proof of
ownership and must not authorize deletion of a resource.

*Auto-provisioned resource cleanup on parent deletion:*

The parent resource's cleanup finalizer uses a phased requeue approach to
ensure correct ordering without touching tenant-managed resources:

1. Query only allowlisted ExternalIPAttachments whose immutable owner is
   exactly this resource. If ownership is missing or inconsistent, fail
   safely rather than guessing. Issue delete for each. Requeue.
2. On next reconcile: check if all ExternalIPAttachments are fully
   deleted (including their own finalizers completing the DNAT rule
   removal). If not, requeue.
3. Once all ExternalIPAttachments are gone: query only allowlisted
   ExternalIPs whose immutable owner is exactly this resource. Issue delete
   for each. Requeue.
   Requeue.
4. On next reconcile: check if all ExternalIPs are fully deleted. If
   not, requeue.
5. Once all ExternalIPs are gone: proceed with parent resource deletion.
   The ExternalIPPool is never deleted by this workflow.

This five-phase sequence is the workload path. A default NATGateway uses a
separate finalizer path: first validate that the NATGateway delete has been
admitted and that the exact immutable owner relationship identifies its
automatic ExternalIP; then remove the NAT backend binding, wait for that
cleanup to complete, delete only the owned ExternalIP, and remove the
NATGateway finalizer after the ExternalIP is fully absent. VirtualNetwork
deletion never invokes this path, and the ExternalIPPool and all
tenant-managed resources remain outside it.

If cleanup fails, the parent remains in `Deleting` and the finalizer retries.
The workload finalizer is not removed merely to unblock parent deletion, and
the workload workflow never deletes a tenant-managed attachment, ExternalIP,
pool, Subnet, NetworkACL, NATGateway, or VirtualNetwork. The default-NAT
finalizer likewise fails closed if ownership is missing or inconsistent.

**Enable outbound NAT (SNAT):**

```bash
osac create externalip --pool external-pool-1 --name nat-ip
osac create natgateway --virtual-network my-net --externalip nat-ip \
  --name my-nat
```

Every selected manager creates a SNAT rule for the VN: all egress traffic from
the VN's CIDR is source-NATted to the ExternalIP. An unfinished implementation
may complete through a temporary successful no-op AAP role.

### API Extensions

#### VirtualNetwork

```protobuf
message VirtualNetworkSpec {
  string ipv4_cidr = 2;               // required, immutable
}
```

No scope or service field — subnets are infrastructure-agnostic.

The implementation target is not a tenant-visible `VirtualNetwork` field.
The operator persists only its controller-owned dispatch annotations (when
needed for reconciliation and deletion), as defined in the dispatcher section.

#### SecurityGroup

```protobuf
message SecurityGroupRule {
  SecurityGroupRuleDirection direction = 1; // required: INGRESS or EGRESS
  SecurityGroupRuleProtocol protocol = 2;   // required: TCP, UDP, ICMP, or ANY
  optional int32 port = 3; // TCP/UDP: omitted means all ports; otherwise 1..65535; no ranges
  oneof remote_cidr {
    string source_cidr = 4;      // required for ingress
    string destination_cidr = 5; // required for egress
  }
}

message SecurityGroupSpec {
  VirtualNetworkLocalReference virtual_network = 1; // required, immutable
  repeated SecurityGroupRule rules = 2;              // immutable
}
```

SecurityGroup rules are allow-only; there is no action field and no deny rule.
An attached workload is denied when none of its SecurityGroup rules match.
The tenant default SecurityGroup is system-created and may have an empty rule
list to represent default deny. Tenant-created SecurityGroups require at
least one rule. A SecurityGroup is implemented by every configured manager; one
internal target is used for each selected manager.

#### NetworkACL

```protobuf
message NetworkACLRule {
  NetworkACLRuleAction action = 1; // required: ALLOW or DENY
  NetworkACLRuleDirection direction = 2; // required: INGRESS or EGRESS
  NetworkACLRuleProtocol protocol = 3; // required: TCP, UDP, ICMP, or ANY
  optional int32 port = 4; // TCP/UDP: omitted means all ports; otherwise 1..65535; no ranges
  oneof remote_cidr {
    string source_cidr = 5;      // required for ingress
    string destination_cidr = 6; // required for egress
  }
}

message NetworkACLSpec {
  VirtualNetworkLocalReference virtual_network = 1; // required, immutable
  repeated SubnetLocalReference subnets = 2;         // one or more, immutable
  repeated NetworkACLRule rules = 3;                 // immutable
}
```

Each tenant's default NetworkACL is associated with its default Subnet and
contains explicit deny-all ingress and allow-all egress rules. Every
user-created NetworkACL requires at least one rule and one or more explicit
Subnet associations. A Subnet cannot be associated with more than one custom
NetworkACL. Every selected manager receives the operation; unfinished policy
implementation may use a temporary successful no-op AAP role.

#### BareMetalInstanceType and Interface Resolution

**BareMetalInstanceType** is the authoritative bare-metal catalog resource
defined in
the [BareMetalInstanceType EP](/enhancements/OSAC-1201-baremetal-instance-types).
It provides hardware discovery and structured network ports for both CaaS and
BMaaS interface resolution:

```protobuf
message BareMetalNetworkPortSpec {
  string name = 1;        // e.g., "data-0", "data-1", "mgmt-0" — unique within the type
  string role = 2;        // e.g., "fabric", "management", "storage", "lifecycle"
  string type = 3;        // e.g., Ethernet, InfiniBand
  string speed = 4;       // e.g., 1Gbps, 100Gbps
}
```

Every BareMetalInstanceType used for networking must expose at least one
`fabric` port. Ports are ordered; when multiple ports share a role, the first
one is the default for that role. `host_label_selector` is used for inventory
matching; CaaS and BMaaS resolve network attachments directly from
BareMetalInstanceType, with no separate interface catalog.

| Role | Meaning |
|------|---------|
| `fabric` | Primary fabric traffic (east-west, tenant workloads) |
| `management` | In-band management/control plane traffic |
| `storage` | Storage fabric traffic |
| `lifecycle` | Out-of-band lifecycle management (PXE boot, Redfish/BMC) — not tenant-attachable |

Roles are conventions, not enforced enums. Ports/interfaces with role
`lifecycle` are used by the provisioning system (Ironic, Metal3) and
should not appear in `network_attachments`.

**CaaS** uses BareMetalInstanceType: the fulfillment-service resolves the
interface automatically (first `fabric`-role port → stored as
`fabric_interface` on the node set definition).

**BMaaS** uses BareMetalInstanceType: the tenant discovers interfaces
from BareMetalInstanceType and specifies one port name on
`BareMetalNetworkAttachment.interface`, validated against the
BareMetalInstanceType's network ports list. The `interface` field references
a port name in the BareMetalInstanceType network port list. A hardware profile
may list additional physical interfaces, but BMaaS does not attach them to the
tenant network.

#### Network Attachment Types

Each resource type has its own network attachment message. The core fields
(`subnet` and optional `security_groups`) are shared, but each type adds
resource-specific fields. Resource
references use the typed local-reference messages defined by
[OSAC-1330](/enhancements/OSAC-1330-type-safe-resource-references/design.md).
In a create request, a local reference is an object such as
`{ "name": "app-subnet" }`; a raw identifier string or an identifier-only
object is not a valid wire value. The server may populate `id` in the
resolved stored reference, and a caller may provide `id` only alongside
`name` for consistency checking. The effective NetworkACL is discovered from
the referenced Subnet; it is not part of the attachment.
The attachment list or singular attachment and every field in every entry are
immutable after resource creation.

**ComputeNetworkAttachment** (for ComputeInstance):

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  optional bool primary = 2;            // one-entry attachment is implicitly primary
  repeated SecurityGroupLocalReference security_groups = 3; // omitted/empty -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}
```

The API remains list-shaped, but the current contract supports zero or one
entry only. A single entry maps one virtual NIC to one subnet and is implicitly
primary when `primary` is omitted. More than one entry is rejected; multi-
interface VM requests are not supported by this contract.
See the [VMaaS networking design](/enhancements/OSAC-1435-vmaas-networking/design.md)
for the service-specific validation.

**BareMetalNetworkAttachment** (for BaremetalInstance):

```protobuf
message BareMetalNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  string interface = 2;                 // omitted -> first fabric interface
  optional bool primary = 3;            // the sole attachment is implicitly primary
  repeated SecurityGroupLocalReference security_groups = 4; // omitted/empty -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}
```

BMaaS accepts at most one entry. That entry maps one physical interface to
one subnet; if `interface` is omitted, the fabric manager picks a default.
The single attachment is implicitly primary and supplies the instance's
default route and ExternalIP DNAT target. The BareMetalInstanceType port
catalog does not imply support for multiple tenant network attachments.

**ClusterNetworkAttachment** (for Cluster):

```protobuf
message ClusterNetworkAttachment {
  SubnetLocalReference subnet = 1;                 // omitted -> tenant default Subnet
  repeated SecurityGroupLocalReference security_groups = 2; // omitted/empty -> tenant default SecurityGroup only for the tenant default VirtualNetwork
}
```

A single attachment applies to the whole cluster — all node sets share the same subnet.
The `fabric_interface` is resolved by the fulfillment-service at creation time for each
node set from its BareMetalInstanceType (first port with role `fabric` — see [BareMetalInstanceType and Interface Resolution](#baremetalinstancetype-and-interface-resolution))
and stored on the node set definition. The tenant does not set this field.

#### Resource Specs

**ComputeInstance** (resource-specific attachment field):

```protobuf
message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 18; // list-shaped, zero or one supported
}
```

`network_attachments` is the only supported ComputeInstance attachment
field. The former shared `NetworkAttachment` field is replaced before this API
is released and is not accepted. No dual-field compatibility or migration
period is part of this design.

**BaremetalInstance** (new — defined in the
[BareMetal Instance API enhancement](/enhancements/OSAC-1118-baremetal-instance-api)):

```protobuf
message BareMetalInstanceSpec {
  BareMetalInstanceCatalogItemReference catalog_item = 1;
  optional string ssh_public_key = 2;
  optional string user_data = 3;
  optional BareMetalInstanceRunStrategy run_strategy = 4;
  int64 restart_trigger = 5;
  map<string, google.protobuf.Any> template_parameters = 6;
  optional BareMetalInstanceImage image = 7;

  // NEW: OSAC networking
  repeated BareMetalNetworkAttachment network_attachments = 8;
  BareMetalInstanceTemplateReference template = 10;
  BareMetalInstanceTypeReference instance_type = 20;
}
```

**Cluster** (new):

```protobuf
message ClusterSpec {
  ClusterTemplateReference template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  map<string, ClusterNodeSet> node_sets = 3;

  // NEW: networking
  ClusterNetworkAttachment network_attachment = 9;  // singular, one per cluster
}
```

- Cluster-internal CNI (pod/service CIDRs) uses platform defaults.
- The cluster's template determines the node sets, but the current CaaS
  networking contract accepts BM node sets only; VM-based node sets are
  rejected by the service-specific placement validation. CaaS node sets share
  one tenant subnet and use the system-resolved fabric interface. VMaaS
  ComputeInstances use the separate ComputeNetworkAttachment contract and,
  using the selected manager's K8s overlay where the workload is hosted.

The Cluster resource also gains two fields populated by the system
during provisioning:

```protobuf
message ClusterStatus {
  string api_endpoint = X;      // set by CaaS template, internal API server VIP
  string ingress_endpoint = Y;  // set by CaaS template, internal ingress VIP
}
```

These are used by the ExternalIPAttachment controller as the DNAT backend
IP when the target is a cluster (see
[Cluster ExternalIPAttachment flow](#cluster-externalipattachment-flow)).

#### Resource Status — Discovered IPs

After provisioning, resources receive IPs via DHCP. Feedback controllers
discover these IPs and write them to status for two purposes: tenant
visibility and ExternalIPAttachment DNAT target resolution.

**ComputeInstanceStatus:**

```protobuf
message ComputeNetworkAttachmentStatus {
  SubnetLocalReference subnet = 1;     // Controller-owned resolved reference
  string ip_address = 2;               // Discovered from KubeVirt VMI network status
  bool primary = 3;                     // Echoed from spec
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = N;
  // VMaaS populates zero or one status entry under the current contract.
}
```

Feedback controller watches the sole KubeVirt VMI interface in
`status.interfaces[].ipAddress`, maps it to the single attachment by CUDN NAD
reference, and fires Signal RPC to fulfillment-service.

**BaremetalInstanceStatus:**

```protobuf
message BareMetalNetworkAttachmentStatus {
  string interface = 1;                 // Physical interface name (echoed from spec)
  SubnetLocalReference subnet = 2;      // Controller-owned resolved reference
  string ip_address = 3;               // Discovered via query_dhcp_lease role after provisioning (matches port MAC to DHCP lease)
  bool primary = 4;                     // Echoed from spec
}

message BareMetalInstanceStatus {
  // ... existing fields ...
  repeated BareMetalNetworkAttachmentStatus network_attachment_statuses = N; // at most one for BMaaS
}
```

IP discovered after DHCP assignment on the tenant network. After
`reconcileProvisioning` completes, the operator dispatches
`query_dhcp_lease` to the fabric manager's DHCP lease API, matching
the server's port MAC address to find the assigned IP (see
[BMaaS OQ#4 — Resolved](/enhancements/OSAC-1437-bmaas-networking/design.md#4-how-is-the-hosts-runtime-ip-discovered-after-network-reconfiguration)).
The operator writes the discovered IP to CR status, and the feedback
controller syncs to fulfillment-service.

**ClusterStatus** does not have per-attachment IP status — CaaS uses
service-level VIPs (`api_endpoint`, `ingress_endpoint`) rather than
per-node IPs. Per-agent IPs are tracked on the ClusterOrder CR's
`NodeSetStatus.AgentStatus.IPAddress` (operator-internal, not surfaced
to tenant).

#### ExternalIPAttachment — Inbound Traffic (DNAT)

Handles **inbound traffic only**. Does not affect egress (that is
NATGateway's job).

```protobuf
enum ExternalIPAttachmentEndpoint {
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_UNSPECIFIED = 0;
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_API         = 1;  // Cluster API server
  EXTERNAL_IP_ATTACHMENT_ENDPOINT_INGRESS     = 2;  // Cluster ingress wildcard
}

message ExternalIPAttachmentSpec {
  ExternalIPLocalReference external_ip = 1;  // required, immutable

  oneof target {
    ComputeInstanceLocalReference compute_instance = 2;
    ClusterLocalReference cluster = 3;
    BareMetalInstanceLocalReference baremetal_instance = 4;
  }
  ExternalIPAttachmentEndpoint target_endpoint = 5;
  // Required when target=cluster; must be UNSPECIFIED otherwise.
}
```

All fields are immutable after creation.

#### NATGateway — Outbound Traffic (SNAT)

Handles **outbound traffic only**.

```protobuf
message NATGatewaySpec {
  VirtualNetworkLocalReference virtual_network = 1;  // required, immutable
  ExternalIPLocalReference external_ip = 2;          // required, immutable
}
```

An ExternalIP can only be used by one consumer (either an
ExternalIPAttachment or a NATGateway, not both). One NATGateway per
VirtualNetwork. NATGateway is optional — it provides a dedicated egress
identity. Without it, resources may still have default egress but without a
controlled source IP.

All fields are immutable after creation.

**Direction summary:**

| Resource | Direction | Mechanism |
|----------|-----------|-----------|
| ExternalIPAttachment | Inbound (DNAT) | External IP → resource |
| NATGateway | Outbound (SNAT) | Resource → external IP |

### Implementation Details

#### Deletion Dependency Guards

Deletion uses direct reverse-reference validation, not a recursive graph walk.
For each resource type, the API checks only the tables or relationship indexes
that can directly point to that resource. An existence-only check may stop at
the first match; a rejected request performs indexed lookups that return the
blocking resource kind, ID/name, relationship field, and lifecycle state. The
cost is proportional to the direct blockers returned, not to the total number
of resources or to unrelated descendants.

The check and the deletion admission are one transaction. The service locks
the target, reads its direct blockers, and marks it for deletion only when no
tenant-managed blockers remain. Reference creation takes a compatible lock on
the target and verifies that it is still Ready/active. This prevents a
concurrent create from racing a successful delete. Database constraints or
triggers remain the final guard even when the API has already performed the
same preflight query.

For a rejected request, the service returns `FAILED_PRECONDITION` with
machine-readable blocker details and a human-readable equivalent such as:

```text
cannot delete VirtualNetwork "vn-1"; blockers:
- Subnet "subnet-a" via spec.virtual_network (delete the Subnet first)
- SecurityGroup "sg-a" via spec.virtual_network (delete the SecurityGroup first)
- NetworkACL "acl-a" via spec.virtual_network (delete the NetworkACL first)
- NATGateway "nat-a" via spec.virtual_network (delete the NATGateway first)
```

The service returns all direct blockers under the configured response limit and
includes the total count when the limit is exceeded. A blocker whose
`deletion_timestamp` is set but whose row has not yet been archived is still
reported: a tenant must wait for that child to disappear before deleting its
parent. This makes the user-visible order deterministic and prevents backend
cleanup races.

The shared direct dependency graph is:

| Resource being deleted | Direct tenant-managed blockers |
|---|---|
| Workload (`ComputeInstance`, `BaremetalInstance`, or `Cluster`) | Tenant-created `ExternalIPAttachment` resources targeting the workload; valid OSAC-owned auto-created attachments are the documented exception |
| `VirtualNetwork` | `Subnet`, `SecurityGroup`, `NetworkACL`, and `NATGateway` resources referencing the VN |
| `SecurityGroup` | ComputeInstance, BaremetalInstance, and Cluster network attachments, or Catalog Item/Template network policies, referencing the SecurityGroup |
| `Subnet` | ComputeInstance, BaremetalInstance, and Cluster attachments, or Catalog Item/Template network policies, referencing the Subnet; NetworkACLs whose explicit association list contains the Subnet |
| `NetworkACL` | No child is implied by the ACL's own `virtual_network` or `subnets[]` references; the ACL must be deleted before those referenced resources, and its deletion never deletes or detaches them |
| `NATGateway` | No child is implied by the gateway's own VirtualNetwork or ExternalIP references; the gateway must be deleted before those referenced resources |
| `ExternalIP` | ExternalIPAttachments and NATGateways consuming the IP |
| `ExternalIPPool` | ExternalIPs allocated from the pool |
| `ExternalIPAttachment` | No child is implied by its target or ExternalIP references; the attachment must be deleted before the target workload and ExternalIP |
| `NetworkClass` | All deployment resources and manager integrations that depend on its resolved manager targets; this is provider-only |

The workload attachment fields are reverse references to their resolved
Subnet. They do not become independent child resources and are removed only
when the workload itself is deleted. A manually created
`ExternalIPAttachment` targeting a workload is a separate reverse reference
and blocks workload deletion until the tenant deletes the attachment.

The dependency edges and leaf-first order are therefore:

```text
Tenant-managed ExternalIPAttachment -> target workload and ExternalIP
NATGateway -> ExternalIP and VirtualNetwork
SecurityGroup -> workload network attachments and VirtualNetwork
NetworkACL -> associated Subnets and VirtualNetwork
Workload network attachment -> Subnet
Subnet -> VirtualNetwork
ExternalIP -> ExternalIPPool
VirtualNetwork -> deployment NetworkClass resolution

Delete leaves first, respecting the edges above:
  tenant-managed ExternalIPAttachments before their target workloads and
  ExternalIPs; workload resources, SecurityGroups, NetworkACLs, and NATGateways
  before the resources they reference
  then ExternalIPs and Subnets
  then ExternalIPPools and VirtualNetworks
```

The only exceptions are OSAC-owned automatic resources with explicit,
immutable ownership: the resource must carry the canonical auto-created marker,
the exact owner kind and owner ID, and an allowlisted resource type. A target
reference or tenant match alone does not qualify. When a workload with valid
auto-created resources is deleted, the parent cleanup finalizer deletes the
auto-created ExternalIPAttachment first, waits for it to disappear, then
deletes the auto-created ExternalIP and waits for it to disappear. When an
onboarding default NATGateway is deleted, its finalizer may delete only its
owned automatic ExternalIP after the NAT backend binding is gone. The
ExternalIPPool and every tenant-managed resource are outside these cascades;
VirtualNetwork deletion never directly cascades to NATGateway resources. If
ownership metadata is missing or inconsistent, the service fails safely
instead of guessing.

If the workload has both valid auto-created resources and a tenant-managed
blocker, the entire delete request is rejected and no auto-created resource is
partially deleted. If auto-resource cleanup fails, the parent remains in
`Deleting` and the finalizer retries; it is not removed to create an orphan.

Relationship checks use indexed reference columns or expression indexes. For
repeated references such as `NetworkACL.spec.subnets[]`, the implementation
must use a normalized relationship index or an equivalent GIN/indexed JSON
representation. Auto-resource lookup must use an indexed immutable owner
relationship rather than an unbounded label scan. The API may preflight for
rich error details, but the transactional database guard is authoritative.

Catalog Item and Template policies do not introduce a second deletion model.
While a Catalog Item policy contains a governed network reference, that policy
is a blocker according to the Catalog Items contract. After materialization,
the workload or network resource's direct reference remains authoritative.

#### NATGateway Scope

One NATGateway per VirtualNetwork. All subnets in the VN use the gateway.
Per-subnet NAT association is unsupported.

#### Attachment cardinality and primary behavior

ComputeInstance exposes repeated `network_attachments` to preserve a
list-shaped API, but accepts zero or one entry only. A supplied entry is
implicitly primary when `primary` is omitted; explicit `primary: false` and a
list with more than one entry are rejected. Multi-interface VM support is not
part of the current contract.

BaremetalInstance retains the repeated `network_attachments` API field for
compatibility, but accepts at most one entry. When present, that entry is
implicitly primary and supplies the default gateway, ExternalIP DNAT target,
and NATGateway source address. There is no secondary BMaaS attachment or
tenant-facing multi-homing behavior.

Cluster supports a single `network_attachment` — one subnet for all node
sets. Per-node-set subnet placement is not supported in v0.2. All subnets
must belong to the same VN across all resource types.

**IP assignment:** All resource types receive IPs via DHCP. For VMs, OVN
provides DHCP on the CUDN overlay. For BM servers and CaaS agents, the
fabric's DHCP server assigns an IP on the network segment. The provisioning
template does NOT configure host-side networking (no static IP, gateway, or
DNS configuration) — DHCP handles it automatically.

**ExternalIPAttachment:** For BMaaS, every selected manager creates a
DNAT rule to the single attachment's subnet IP. The tenant does not select an
interface for the DNAT target because BMaaS has only one tenant attachment.

**Cluster networking:** `ClusterNetworkAttachment` is a single attachment
(one subnet for the whole cluster). Each bare-metal node uses exactly one
tenant-facing fabric interface, resolved from its BareMetalInstanceType;
multi-NIC node requests are rejected. The `primary` field does not apply to
`ClusterNetworkAttachment`.

#### Multiple Hosting Clusters Per Deployment

Multiple hosting clusters are a provider placement concern. At subnet
creation, the k8sManager creates a K8s overlay on each eligible hosting
cluster and bridges it to the fabric segment. VMs on different hosting
clusters share the same subnet via the fabric. A manager-specific design may
impose a stricter implementation limit; for example, CUDN-EVPN Phase 1
currently uses one hosting cluster.

#### Deployment Topology

Each OSAC deployment has exactly one hub cluster. Multi-hub deployments are
not supported. All networking resources (VirtualNetwork, Subnet,
NetworkACL, ExternalIPPool, ExternalIP, ExternalIPAttachment, and
NATGateway) are reconciled through that hub, and their `status.hub` fields
identify the deployment's hub.

Provider deployment inventory is the source of truth for this admission check;
the tenant-facing networking API does not accept a hub or connectivity-mode
field. Before the provider creates or marks the deployment NetworkClass Ready,
the inventory must identify exactly one active hub and report
`connectivity_mode=connected`. Missing, duplicate, or non-connected inventory
state is a provider configuration error and prevents NetworkClass acceptance.

##### Deployment Support Boundary

The current OSAC networking contract supports connected deployments only.
Air-gapped and disconnected deployments are outside the supported boundary and
must not be advertised as a supported networking topology. A connected
deployment is one whose active hub, selected networking managers, and required
provider-controlled network services can reach one another and the deployment's
configured external address infrastructure. Connectivity is provider-owned
deployment configuration; it is not a tenant-selectable NetworkClass,
VirtualNetwork, or workload option.

The provider must establish and validate this boundary before the deployment
NetworkClass is accepted. Tenant networking resources and workload attachments
must not be admitted through a deployment that does not satisfy it. The
connected-only rule applies equally to Fabric-only, K8s-only, and combined
manager profiles; manager choice does not create an air-gapped exception.

All shared networking resources and manager integrations use IPv4; IPv6 and
dual-stack networking are not supported.

Hosting clusters are distinct from the hub. Where a `k8sManager` is
configured, subnet creation provisions the K8s overlay on each eligible
hosting cluster and bridges it to the fabric segment. VMs on different
hosting clusters share the same subnet via the fabric; those hosting clusters
do not create additional hubs.
Manager-specific placement and hosting-cluster limits remain authoritative.

#### Cross-VN Communication

VirtualNetworks are isolated. Cross-VN communication (VN Peering) is a
separate enhancement.

#### DNS

DNS is a service-integration concern, not part of the networking API. CaaS
template roles create DNS records. A DNS API is a separate enhancement.

#### BM-Only Deployments

Fabric-only deployments use the Fabric Manager's complete VM, BMaaS, and CaaS
integration. K8s-only deployments use the K8s Manager's complete integration.
Combined deployments run both implementations. The CaaS path creates the
MetalLB IPAddressPool where a K8s overlay is used and uses the fabric-level
VIP path where the deployment is Fabric-only; the deployment-level
`metallb_vip_prefix_length` remains the single source of that reservation.

#### CIDR Overlap

The operator validates that Subnet CIDRs do not overlap within a
VirtualNetwork at creation time.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fabric manager complexity | One Ansible role handles all networking concerns | Clear interface contract per operation; tested independently per manager |
| K8s-to-fabric bridge failure | VMs unreachable from fabric | k8sManager validates bridge connectivity at subnet creation; subnet stays Pending until bridge is confirmed |
| CaaS prerequisite ordering | Internal auto-provisioning reserves ExternalIP capacity before the cluster endpoint exists | The internal path creates Pending records atomically; the controller waits for allocation and endpoint readiness before DNAT |
| ExternalIPAttachment target validation | A caller-created attachment may reference a target that is not Ready or may be deleted | Direct create rejects non-Ready references; only the internal auto-provisioning path may create a Pending forward reference, and deletion is handled by the parent cleanup flow |
| CIDR overlap | Overlapping subnets cause routing ambiguity | Operator validates at creation time; rejected with clear error |

### Drawbacks

This design requires K8s-to-fabric connectivity in every deployment that
hosts VMs on a fabric-bridged K8s overlay. The k8sManager must provide that
bridge for the selected VM-capable topology. In deployments without VMs
(BM-only, with or without CaaS), the k8sManager is not needed for BM port
movement, while a combined CaaS topology may still use it for the overlay
and MetalLB IPAddressPool. The CaaS design defines whether the pool is
created by the selected K8s manager or by the BM-only fabric-level path.

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
   NAT association is unsupported.

5. **ExternalIPPool shared.** Every selected manager handles its
   ExternalIP allocation for all resource types. Multiple deployment-scoped pools are
   supported; each pool has exactly one CIDR and pools must not overlap unless
   the provider explicitly declares disjoint allocation ownership. Automatic
   allocation selects a Ready pool with the most available capacity.

6. **Multiple hosting clusters.** Subnet creation provisions the K8s overlay
   on each eligible hosting cluster. VMs on different clusters share the
   subnet via the fabric. Manager-specific implementation limits, such as
   CUDN-EVPN Phase 1 being single-cluster, remain authoritative.

7. **Internal IP pools.** Managed by managers with sensible defaults. Not
   part of the tenant API or NetworkClass spec.

8. **ExternalIP naming.** "External" means external to the VirtualNetwork.
   The supported deployment boundary is connected only; air-gapped behavior is
   rejected and is not part of this design.

9. **Attachment immutability.** Attachment cardinality, Subnet, interface,
   primary designation, NetworkACL membership, and every other
   network-attachment field are immutable after resource creation. Changing
   any of them requires deleting and recreating the resource.

10. **Security enforcement.** Each configured manager is an implementation
    target for both SecurityGroup and NetworkACL. A K8s manager may implement
    either policy directly only when it satisfies the complete OSAC contract.
    Native Kubernetes NetworkPolicy alone does not satisfy either OSAC policy
    contract; a K8s SecurityGroup adapter must implement the complete stateful
    SecurityGroup semantics, and a NetworkACL adapter must implement the
    complete stateless rule semantics. The current K8s-only profile's concrete
    adapter is defined in the [K8s-only Networking Manager
    design](../OSAC-1433-k8s-only-k8s-manager/design.md). Both selected
    managers reconcile the same OSAC resource in a combined deployment.

11. **Per-resource NetworkAttachment types.** Separate proto messages
    (`ComputeNetworkAttachment`, `BareMetalNetworkAttachment`,
    `ClusterNetworkAttachment`) instead of one shared type. Each resource
    type has a different selector concept (virtual NIC, physical interface,
    node set) — a shared type with optional fields would accumulate
    dead weight per resource type.

## Test Plan

The executable, reviewable plan for the shared networking contract is
maintained in [testplan.md](testplan.md). It is the source of truth for unit,
integration, and end-to-end coverage, including supported workflows,
explicitly unsupported behavior, dependency readiness, immutability, and
recovery. Service-specific test plans inherit these shared cases and may add
service-specific cases without weakening them.
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
