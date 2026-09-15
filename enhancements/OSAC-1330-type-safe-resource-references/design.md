---
title: type-safe-resource-references
authors:
  - Haim Tayrie
creation-date: 2026-07-15
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1330
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking"
  - "/enhancements/bare-metal-fulfillment"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Type-Safe Resource References

## Summary

This enhancement replaces all opaque `string` reference fields in the OSAC
fulfillment API with per-type structured protobuf messages (`<Type>Reference`
and `<Type>LocalReference`), introduces a gRPC interceptor using protoreflect
for centralized reference validation, and updates the CLI, UI, database
triggers, and CEL filter paths accordingly. See [PRD](prd.md) for detailed
requirements.

The networking schemas covered by this design use IPv4 CIDRs only; IPv6 and
dual-stack networking are not supported.

## Motivation

Every OSAC resource that points to another resource does so through a bare
`string` field. A `SubnetSpec.virtual_network` is indistinguishable at the
schema level from `SubnetSpec.ipv4_cidr` -- both are strings. This creates
three classes of problems:

1. **No compile-time safety.** Nothing prevents a developer from passing a
   Subnet ID where a VirtualNetwork ID is expected. The proto compiler,
   Go type system, and REST/JSON schema all treat these identically.

2. **No cross-tenant addressability.** References carry only an identifier (or
   name) with no tenant or project context. Referencing a shared resource in a
   different tenant (a global ClusterTemplate, a deployment-scoped NetworkClass)
   requires out-of-band knowledge of the target's identifier.

3. **Scattered, inconsistent validation.** Each server validates references
   inline in its Create/Update methods using ad-hoc DAO lookups. Error codes
   are inconsistent -- some servers return `InvalidArgument`, others return
   `NotFound` for the same "referenced resource doesn't exist" condition.
   Business logic validation (CIDR containment, same-VirtualNetwork checks) is
   entangled with existence checks.

The current codebase contains 34 spec-level reference fields across 15 public
API resources (see the complete inventory in the architectural context
document). Each field has its own inline validation logic in the corresponding
server implementation. The UI resolves IDs to names client-side for display,
requiring extra API calls. The CLI passes raw strings with no structural
validation.

This proposal replaces every reference field with a typed message that carries
the referenced resource's name (and optionally tenant and project for
cross-scope references), centralizes existence validation in an interceptor,
and standardizes error reporting across all services. [Locked: D2]

### Goals

- Provide compile-time type safety for all inter-resource references through
  per-type protobuf messages, making it impossible to assign a Subnet
  reference to a VirtualNetwork field.
- Centralize reference existence validation in a single gRPC interceptor so
  that new resources automatically inherit validation without per-server code.
- Standardize error reporting for invalid references on `InvalidArgument` with
  structured field paths across all services.
- Maintain incremental deliverability so that each resource group can be
  migrated independently while the system remains functional. [Locked: D6]
- Prepare the proto schema for the future (tenant, project, name) migration
  by including the `id` field in reference messages, even though id-based
  resolution is deferred. [Locked: D5]

### Non-Goals

- The (tenant, project, name) migration itself -- reference types provide the
  foundation, but the migration of resource identification from UUIDs to
  (tenant, project, name) tuples is a separate initiative. [Locked: D5]
- Backward compatibility with the current string-based reference format.
  [Locked: D1]
- Changes to internal resource identification (primary keys, database schema
  beyond trigger updates).
- Quota enforcement or RBAC changes -- existing authorization model applies
  unchanged.

## Proposal

The design introduces three coordinated changes:

1. **Per-type reference messages in proto.** For each referenceable resource
   type, two new messages are added to its `_type.proto` file:
   `<Type>Reference` (full: id, tenant, project, name) for cross-tenant/project
   references, and `<Type>LocalReference` (name only) for same-tenant/project
   references. All 34 spec-level string reference fields are replaced with the
   appropriate message type. Field numbers are reused since backward
   compatibility is not required. [Locked: D1]

2. **gRPC reference validation interceptor.** A new unary server interceptor
   uses protoreflect to walk incoming request messages, identify fields whose
   type is a reference message (detected by naming convention and message
   structure), validate that the referenced resource exists via DAO lookups, and
   return standardized `InvalidArgument` errors with field paths. Business logic
   validation (CIDR containment, same-VirtualNetwork membership) remains in
   per-server code.

3. **Consumer updates.** The CLI constructs reference messages from flag values.
   The UI sends nested JSON objects instead of flat strings. Database triggers
   update their JSON path expressions. CEL filter paths change from
   `this.spec.virtual_network` to `this.spec.virtual_network.name`.

### Workflow Description

#### Creating a compute instance with network attachments (Tenant User)

Starting state: A Tenant User has a Subnet named `app-subnet` in READY state
within the tenant and project. The Subnet has its effective NetworkACL ready;
the ACL is associated with the Subnet and is not referenced by the workload
attachment.

1. The user submits a CreateComputeInstance request. In the REST/JSON body,
   network attachments use nested reference objects:
   ```json
   {
     "metadata": { "name": "my-vm" },
     "spec": {
       "catalog_item": { "name": "standard-vm" },
       "network_attachments": [
         {
           "subnet": { "name": "app-subnet" }
         }
       ]
     }
   }
   ```

2. The gRPC gateway deserializes the JSON into the proto message. The
   `catalog_item` field is a `ComputeInstanceCatalogItemReference` (full
   reference, since catalog items may be cross-tenant). The `subnet` field is
   a `SubnetLocalReference` (local, since subnets are always same-tenant). The
   The attachment contains only a `SubnetLocalReference`; its effective
   NetworkACL is resolved from the referenced Subnet.

3. The reference validation interceptor fires before the server handler. It
   walks the `CreateComputeInstanceRequest` message using protoreflect,
   discovers the reference-typed fields, and for each:
   - Extracts the `name` field from the reference message.
   - Looks up the resource via the corresponding DAO using the caller's tenant
     context.
   - If the resource does not exist, collects an error with the field path
     (e.g., `spec.network_attachments[0].subnet.name`).

4. If any reference is invalid, the interceptor returns `InvalidArgument` with
   all invalid references listed in the error details. The user sees:
   ```
   InvalidArgument: invalid references:
     spec.network_attachments[0].subnet.name: Subnet "app-subnet" not found
   ```

5. If all references are valid, the request proceeds to the
   ComputeInstancesServer handler, which performs business logic validation
   (e.g., the Subnet and its effective NetworkACL must be Ready and belong to
   the same tenant and VirtualNetwork).

6. On success, the created ComputeInstance is returned with the submitted
   names preserved and the resolved identifier/scope fields populated according
   to the reference contract.

#### Creating a virtual network in the single deployment NetworkClass (Tenant Admin)

Starting state: The provider has configured the single deployment NetworkClass.
Tenants do not select a NetworkClass for individual VirtualNetworks.

1. The Tenant Admin submits a CreateVirtualNetwork request:
   ```json
   {
     "metadata": { "name": "prod-net" },
     "spec": {
       "ipv4_cidr": "10.0.0.0/16"
     }
   }
   ```

2. The server resolves the single deployment NetworkClass and derives the
   provider/private `implementation_strategy`.

3. The server validates the CIDR format and the resolved manager capabilities.

#### Creating a catalog item referencing a template in another tenant (Cloud Provider Admin)

Starting state: A Cloud Provider Admin has created a ClusterTemplate named
`ocp-4.18` in tenant `infra-templates`.

1. The admin creates a ClusterCatalogItem in the `shared` tenant, referencing
   the template by tenant and name:

   ```json
   {
     "metadata": { "name": "ocp-standard" },
     "spec": {
       "template": {
         "name": "ocp-4.18",
         "tenant": "infra-templates"
       }
     }
   }
   ```

2. The `template` field is a `ClusterTemplateReference` (full reference). The
   interceptor reads the explicit `tenant` value from the reference message
   and looks up the ClusterTemplate in tenant `infra-templates`, not the
   caller's current tenant.

3. If the template exists, the request proceeds to the server handler. If
   not, the interceptor returns `InvalidArgument` with
   `spec.template.name: ClusterTemplate "ocp-4.18" not found in tenant "infra-templates"`.

#### Error handling: invalid reference

When a user references a nonexistent resource:

```json
{
  "metadata": { "name": "my-subnet" },
  "spec": {
    "virtual_network": { "name": "nonexistent-vnet" }
  }
}
```

The interceptor returns:
```
Code: InvalidArgument
Message: invalid resource references
Details: [
  {
    field: "spec.virtual_network.name",
    description: "VirtualNetwork \"nonexistent-vnet\" not found in tenant \"tenant-a\", project \"default\""
  }
]
```

The response uses `google.rpc.BadRequest` with `FieldViolation` entries for
each invalid reference, providing a machine-parseable and human-readable error.

```mermaid
sequenceDiagram
    participant U as User (REST/gRPC)
    participant GW as gRPC Gateway
    participant INT as Reference Interceptor
    participant SRV as Resource Server
    participant DAO as Database (DAO)

    U->>GW: POST /v1/subnets {spec: {virtual_network: {name: "prod-net"}}}
    GW->>INT: CreateSubnet(request)
    INT->>INT: Walk message, find SubnetSpec.virtual_network (VirtualNetworkLocalReference)
    INT->>DAO: Get VirtualNetwork by name="prod-net" in tenant context
    alt Reference valid
        DAO-->>INT: VirtualNetwork found
        INT->>SRV: Forward request
        SRV->>SRV: Business logic validation (CIDR containment)
        SRV->>DAO: Insert Subnet
        SRV-->>U: Subnet created
    else Reference invalid
        DAO-->>INT: Not found
        INT-->>U: InvalidArgument with field path
    end
```

The diagram above shows the request flow for a Subnet creation. The reference
validation interceptor sits between the gRPC gateway and the resource server.
It validates reference existence before the server handler runs. If any
reference is invalid, the interceptor short-circuits the request with a
structured error. If all references are valid, the request proceeds to the
server for business logic validation and persistence.

### API Extensions

This enhancement modifies existing protobuf message definitions. It does not
add new gRPC services, CRDs, webhooks, or finalizers.

**Modified proto files (public API):**

| File | Change |
|------|--------|
| `compute_instance_type.proto` | Add `ComputeInstanceTemplateReference`, `ComputeInstanceCatalogItemReference`, and `SubnetLocalReference`. Replace string fields in `ComputeInstanceSpec` and `ComputeNetworkAttachment`. Import `InstanceTypeLocalReference` from `instance_type_type.proto`. |
| `subnet_type.proto` | Add `VirtualNetworkLocalReference`. Replace `SubnetSpec.virtual_network`. |
| `virtual_network_type.proto` | Remove the tenant-settable `NetworkClassReference`; retain provider/private `implementation_strategy` and validate `VirtualNetworkSpec.ipv4_cidr`. |
| `network_acl_type.proto` | Reuse `VirtualNetworkLocalReference` and add repeated `SubnetLocalReference` fields for `NetworkACLSpec.virtual_network` and `NetworkACLSpec.subnets`. NetworkACL rules contain no workload attachment references. |
| `external_ip_attachment_type.proto` | Add `ExternalIPLocalReference`, `ComputeInstanceLocalReference`, `ClusterLocalReference`, `BareMetalInstanceLocalReference`. Replace string fields in `ExternalIPAttachmentSpec` oneof. |
| `external_ip_type.proto` | Add `ExternalIPPoolReference`. Replace `ExternalIPSpec.pool`. |
| `public_ip_attachment_type.proto` | Add `PublicIPLocalReference`, `ComputeInstanceLocalReference` (reuse). Replace string fields. |
| `public_ip_type.proto` | Add `PublicIPPoolReference`. Replace `PublicIPSpec.pool`. |
| `nat_gateway_type.proto` | Add references for VirtualNetwork and ExternalIP. Replace string fields. |
| `cluster_type.proto` | Add `ClusterTemplateReference`, `ClusterCatalogItemReference`, `BareMetalInstanceTypeReference`, and `SubnetLocalReference` usage in the canonical `ClusterNetworkAttachment`. Replace string fields in `ClusterSpec`, `ClusterNodeSet`, and the cluster attachment. The effective NetworkACL is resolved from the attachment's Subnet. |
| `baremetal_instance_type.proto` | Add `BareMetalInstanceCatalogItemReference` and `BareMetalInstanceTypeReference` to `BareMetalInstanceSpec`, plus `SubnetLocalReference` usage in the canonical `BareMetalNetworkAttachment`. Replace the corresponding string fields. The effective NetworkACL is resolved from the attachment's Subnet. |
| `role_binding_type.proto` | Add `RoleReference`, `UserReference`. Replace string fields. |
| `project_membership_type.proto` | Add `ProjectReference`, `UserReference` (reuse). Replace string fields. |
| `catalog_item_type.proto` (cluster, compute, baremetal) | Add template references. Replace string fields. |
| `instance_type_type.proto` | Add `InstanceTypeLocalReference` for deprecation replacement. |

**Private API:** Each private API `_type.proto` file mirrors the corresponding
public API changes. Private full references are a superset of public full
references: they include all public fields (`id`, `name`, `project`, `shared`)
plus an additional `string tenant` field. Private-only status-level references
(hub, pool mirrors) are addressed in the Implementation Details section.

**Shared reference messages:** When multiple resources reference the same
target type (e.g., both `ComputeNetworkAttachment` and
`PublicIPAttachmentSpec` reference `ComputeInstance`), the reference message
is defined once in the target type's `_type.proto` file and imported where
needed. This prevents duplicate message definitions.

**Canonical networking attachment messages:** The shared `NetworkAttachment`
message is not a supported public or private resource-spec field. Networking
attachments use the resource-specific messages defined by Unified Networking:

| Resource | Canonical field | Canonical message | Typed reference fields |
|---|---|---|---|
| ComputeInstance | `spec.network_attachments` | repeated `ComputeNetworkAttachment` (zero or one supported) | `subnet: SubnetLocalReference`; effective NetworkACL is inherited from the Subnet |
| Cluster | `spec.network_attachment` | `ClusterNetworkAttachment` (singular) | `subnet: SubnetLocalReference`; effective NetworkACL is inherited from the Subnet |
| BaremetalInstance | `spec.network_attachments` | repeated `BareMetalNetworkAttachment` (zero or one supported) | `BareMetalInstanceSpec.catalog_item: BareMetalInstanceCatalogItemReference`; `BareMetalInstanceSpec.instance_type: BareMetalInstanceTypeReference`; attachment `subnet: SubnetLocalReference`; effective NetworkACL is inherited from the Subnet |

The resource-specific messages retain the API shapes required by the service
contracts, but all reference-bearing fields use the typed messages above. The
service designs define the additional `primary` and physical-interface rules;
they do not reintroduce the shared attachment type.

The names in the `Canonical field` column are API field names, not message
type names. In particular, `spec.network_attachment` carries a
`ClusterNetworkAttachment`, while `spec.network_attachments` carries repeated
`ComputeNetworkAttachment` values for ComputeInstance and repeated
`BareMetalNetworkAttachment` values for BaremetalInstance. The API does not define
`cluster_network_attachment` or `bare_metal_network_attachments` fields.

**Operational impact:** None. This is a schema change with no new controllers,
webhooks, or runtime components beyond the interceptor (which replaces existing
inline validation logic).

## UX Alignment

The UI `@temp-api` files pass reference values as plain strings. After this
enhancement, the REST/JSON wire format changes from flat strings to nested
objects. The following table maps the affected UI code to the new proto
structure.

| UI code location | Current wire format | New wire format | Notes |
|---|---|---|---|
| `networking.ts` `CreateVirtualNetworkInput` | `spec: { network_class: networkClass, ipv4_cidr: cidr }` | `spec: { ipv4_cidr: cidr }` | NetworkClass is deployment-resolved; the tenant supplies only the CIDR |
| `networking.ts` `CreateSubnetInput.virtualNetworkId` | `spec: { virtual_network: virtualNetworkId }` (string) | `spec: { virtual_network: { name: vnetName } }` | Rename variable from `Id` to name-based |
| `networking.ts` `CreateNetworkACLInput.virtualNetworkName` | `spec: { virtual_network: virtualNetworkName }` (string) | `spec: { virtual_network: { name: vnetName }, subnets: [{ name: subnetName }] }` | NetworkACL associations use typed local Subnet references; workload attachments do not reference NetworkACLs |
| `networking.ts` `virtualNetworkFilterForSubnetList` | `this.spec.virtual_network == "${id}"` | `this.spec.virtual_network.name == "${name}"` | CEL filter path change |
| `ip-management.ts` `useCreatePublicIP` body | `spec: { pool: string }` | `spec: { pool: { name: poolName } }` | |
| `ip-management.ts` `useCreateExternalIP` body | `spec: { pool: string }` | `spec: { pool: { name: poolName } }` | |
| `ip-management.ts` `useCreatePublicIPAttachment` body | `spec: { publicIp: string, target: { case, value } }` | `spec: { public_ip: { name: ipName }, compute_instance: { name: vmName } }` | Oneof becomes separate fields with reference messages |
| `ip-management.ts` `useCreateExternalIPAttachment` body | `spec: { externalIp: string, target: { case, value } }` | `spec: { external_ip: { name: ipName }, compute_instance: { name: vmName } }` | Same oneof pattern |
| `cluster.ts` `CreateClusterInput.spec.catalogItem` | `spec: { catalogItem: string }` | `spec: { catalog_item: { name: catalogName } }` | |
| `compute-instance-wire.ts` `buildComputeInstanceCreateBody` | `spec: { template: "id", catalog_item: "id", subnet: "id" }` | `spec: { template: { name: "tpl" }, catalog_item: { name: "ci" }, network_attachments: [{ subnet: { name: "s" } }] }` | Most complex change; wire builder must wrap strings; the effective NetworkACL is inherited from the Subnet |

**Known deviation:** The `@temp-api` attachment types
(`useCreatePublicIPAttachment`, `useCreateExternalIPAttachment`) use a
`target: { case, value }` pattern that does not map to proto oneof wire
format. The correct proto oneof wire format sets only the chosen field at the
top level of the spec. This is an existing UI deviation, not introduced by
this enhancement.

After the backend ships and `pnpm gen-types` is run in osac-ux, the UI
migration diff is limited to wrapping string values in `{ name: value }`
objects at each call site, plus updating CEL filter expressions to use the
`.name` sub-path.

### Implementation Details/Notes/Constraints

#### Reference Message Schema

Three reference message patterns are defined per referenceable type. Public
and private APIs use different full reference shapes:

```protobuf
// Public full reference — tenant users use `project` to scope within their
// tenant, and `shared` to target the shared tenant. Defined in the target's
// public _type.proto file.
message ClusterTemplateReference {
  option (buf.validate.message).cel = {
    id: "name_required",
    message: "name must be provided",
    expression: "this.name != ''"
  };

  string id = 1;
  string name = 2;
  string project = 3;
  bool shared = 4;
}

// Private full reference — Cloud Provider Admins use explicit tenant/project.
// Contains all public fields plus `tenant`. Defined in the target's private
// _type.proto file.
message ClusterTemplateReference {
  option (buf.validate.message).cel = {
    id: "name_required",
    message: "name must be provided",
    expression: "this.name != ''"
  };

  string id = 1;
  string name = 2;
  string project = 3;
  bool shared = 4;
  string tenant = 5;
}

// Local reference — used when the target is always in the same tenant/project.
// Shared between public and private APIs.
message SubnetLocalReference {
  option (buf.validate.message).cel = {
    id: "name_required",
    message: "name must be provided",
    expression: "this.name != ''"
  };

  string id = 1;
  string name = 2;
}
```

**Public vs. private full references.** Tenant users and tenant admins should
not see or provide arbitrary tenant names. The public API exposes `string
project` and `bool shared` instead of `string tenant`: when `shared = true`,
the interceptor resolves the reference against the `shared` tenant; when
`false` (default), it resolves against the caller's own tenant. The `project`
field scopes the lookup within the tenant — when empty, the resource is
resolved as global to the tenant (i.e., the default project). The private API
is a superset of the public API per the
[API Guidelines](https://github.com/osac-project/fulfillment-service/blob/main/docs/API.md#public-and-private-apis):
it includes all public fields (`id`, `name`, `project`, `shared`) plus an
additional `tenant` field for Cloud Provider Admins who manage cross-tenant
resources.

All reference types (full and local) require `name` in a request. The optional
`id` is a resolved/output field; when a caller supplies it together with
`name`, the interceptor verifies that both identify the same resource. An
identifier cannot replace the name.

1. **Name only** (the normal form): The interceptor resolves the resource by name
   within the caller's tenant (or the `shared` tenant if `shared = true` in
   public API, or the explicit `tenant` in private API). The `id` field in the
   stored reference is auto-populated with the resolved resource's identifier.
2. **Both provided**: The interceptor resolves by `name` and verifies that an
   optional supplied `id` identifies the same resource. If they disagree, it
   returns `InvalidArgument`.

The interceptor rejects a request that supplies only `id`, rather than
silently preserving the old identifier-only request format. After name
resolution it mutates the request via protoreflect to fill in the resolved
`id` and any scope fields before the handler runs. The stored JSON therefore
contains a fully-qualified reference.

Local references omit `tenant` and `project` because the target is always in
the same scope as the referencing resource. The interceptor derives tenant and
project from the owning resource's metadata, not from the caller's auth
context. The `id` field may be populated after the named resource is resolved,
but it is not a standalone input form.

#### Which fields use local vs. full references

The choice between local and full reference depends on whether the target
resource can be in a different tenant or project from the referencing resource:

| Field | Reference Type | Rationale |
|-------|---------------|-----------|
| `SubnetSpec.virtual_network` | `VirtualNetworkLocalReference` | Subnet is always in the same tenant/project as its parent VirtualNetwork |
| `NetworkACLSpec.virtual_network` | `VirtualNetworkLocalReference` | The NetworkACL belongs to the same VirtualNetwork as its associated Subnets |
| `ComputeNetworkAttachment.subnet` | `SubnetLocalReference` | ComputeInstance and Subnet are in the same tenant/project |
| `NetworkACLSpec.subnets` | `repeated SubnetLocalReference` | NetworkACL associations are explicit, same-scope Subnet references |
| `NATGatewaySpec.virtual_network` | `VirtualNetworkLocalReference` | Same tenant/project |
| `NATGatewaySpec.external_ip` | `ExternalIPLocalReference` | Same tenant/project |
| `ExternalIPAttachmentSpec.external_ip` | `ExternalIPLocalReference` | Same tenant/project |
| `ExternalIPAttachmentSpec.compute_instance` | `ComputeInstanceLocalReference` | Same tenant/project |
| `ExternalIPAttachmentSpec.cluster` | `ClusterLocalReference` | Same tenant/project |
| `ExternalIPAttachmentSpec.baremetal_instance` | `BareMetalInstanceLocalReference` | Same tenant/project |
| `PublicIPAttachmentSpec.public_ip` | `PublicIPLocalReference` | Same tenant/project |
| `PublicIPAttachmentSpec.compute_instance` | `ComputeInstanceLocalReference` | Same tenant/project |
| `InstanceTypeDeprecation.replacement` | `InstanceTypeLocalReference` | Same scope |
| `ClusterSpec.template` | `ClusterTemplateReference` | Templates may be shared across tenants |
| `ClusterSpec.catalog_item` | `ClusterCatalogItemReference` | Catalog items may be shared across tenants |
| `ClusterNodeSet.baremetal_instance_type` | `BareMetalInstanceTypeReference` | BareMetalInstanceTypes are platform-scoped |
| `ComputeInstanceSpec.template` | `ComputeInstanceTemplateReference` | Templates may be shared |
| `ComputeInstanceSpec.catalog_item` | `ComputeInstanceCatalogItemReference` | Catalog items may be shared |
| `ComputeInstanceSpec.instance_type` | `InstanceTypeReference` | InstanceTypes may be shared |
| `ExternalIPSpec.pool` | `ExternalIPPoolReference` | Pools are provider/deployment-scoped, not tenant-local |
| `PublicIPSpec.pool` | `PublicIPPoolReference` | Pools are platform-scoped |
| `BareMetalInstanceSpec.catalog_item` | `BareMetalInstanceCatalogItemReference` | Catalog items may be shared |
| `BareMetalInstanceSpec.instance_type` | `BareMetalInstanceTypeReference` | BareMetalInstanceTypes are platform-scoped |
| `ClusterCatalogItem.template` | `ClusterTemplateReference` | Cross-tenant template reference |
| `ComputeInstanceCatalogItem.template` | `ComputeInstanceTemplateReference` | Cross-tenant template reference |
| `BareMetalInstanceCatalogItem.template` | `BareMetalInstanceTemplateReference` | Cross-tenant template reference |
| `ClusterTemplateNodeSet.baremetal_instance_type` | `BareMetalInstanceTypeReference` | Platform-scoped |
| `ComputeInstanceTemplateSpecDefaults.instance_type` | `InstanceTypeReference` | May be shared |
| `RoleBindingSpec.role` | `RoleReference` | Roles may be platform-scoped |
| `RoleBindingSpec.users` | `repeated UserReference` | Users may be cross-project |
| `ProjectMembershipSpec.project` | `ProjectReference` | Cross-project by definition |
| `ProjectMembershipSpec.user` | `UserReference` | Cross-project |

#### Concrete before/after example

**Before (current):** `subnet_type.proto`

```protobuf
message SubnetSpec {
  // Parent VirtualNetwork ID. Required and immutable after creation.
  string virtual_network = 1 [
    (google.api.field_behavior) = REQUIRED,
    (google.api.field_behavior) = IMMUTABLE
  ];
  string ipv4_cidr = 2 [
    (google.api.field_behavior) = REQUIRED,
    (google.api.field_behavior) = IMMUTABLE
  ];
}
```

**After:** `subnet_type.proto`

```protobuf
// Local reference to a VirtualNetwork.
// Used when the VirtualNetwork is always in the same tenant/project.
message VirtualNetworkLocalReference {
  string id = 1;
  string name = 2;
}

message SubnetSpec {
  // Parent VirtualNetwork. Required and immutable after creation.
  VirtualNetworkLocalReference virtual_network = 1 [
    (google.api.field_behavior) = REQUIRED,
    (google.api.field_behavior) = IMMUTABLE
  ];
  string ipv4_cidr = 2 [
    (google.api.field_behavior) = REQUIRED,
    (google.api.field_behavior) = IMMUTABLE
  ];
}
```

**Before (current):** `external_ip_attachment_type.proto`

```protobuf
message ExternalIPAttachmentSpec {
  string external_ip = 1 [...];
  oneof target {
    string compute_instance = 2;
    string cluster = 3;
    string baremetal_instance = 4;
  }
  ExternalIPAttachmentEndpoint target_endpoint = 5 [...];
}
```

**After:** `external_ip_attachment_type.proto`

```protobuf
message ExternalIPAttachmentSpec {
  ExternalIPLocalReference external_ip = 1 [...];
  oneof target {
    ComputeInstanceLocalReference compute_instance = 2;
    ClusterLocalReference cluster = 3;
    BareMetalInstanceLocalReference baremetal_instance = 4;
  }
  ExternalIPAttachmentEndpoint target_endpoint = 5 [...];
}
```

**REST/JSON wire format change:**

Before:
```json
{
  "spec": {
    "external_ip": "019728a4-3f5c-7def-8abc-1234567890ab",
    "compute_instance": "01972f1b-a4e9-7c82-9def-abcdef123456"
  }
}
```

After:
```json
{
  "spec": {
    "external_ip": { "name": "my-external-ip" },
    "compute_instance": { "name": "my-vm" }
  }
}
```

#### gRPC Reference Validation Interceptor

The interceptor is a unary server interceptor registered in the gRPC
interceptor chain after authentication and transaction management (so that
tenant context and a database transaction are available).

```go
// ReferenceValidator validates and resolves resource references in incoming
// gRPC requests. It validates that referenced resources exist and
// auto-populates missing fields (id, tenant, project) via protoreflect
// mutation before the handler runs.
type ReferenceValidator struct {
    registry map[protoreflect.FullName]ReferenceLookupFunc
}

// ResolvedRef is the result of resolving a reference.
type ResolvedRef struct {
    ID      string
    Tenant  string
    Project string
    Name    string
}

// ReferenceLookupFunc resolves a resource by the required name and optionally
// verifies an id within a tenant/project scope. Returns the fully-resolved
// reference or dao.ErrNotFound.
type ReferenceLookupFunc func(
    ctx context.Context,
    tenant, project, id, name string,
) (*ResolvedRef, error)

// Validate walks a proto message, resolves all reference-typed fields, and
// mutates the request to fill in missing fields. Returns a
// google.rpc.BadRequest with FieldViolation entries for each invalid
// reference, or nil if all references are valid and resolved.
func (v *ReferenceValidator) Validate(
    ctx context.Context,
    msg proto.Message,
) error
```

**Tenant and project scope resolution.** For public API full references, the
interceptor translates `shared = true` to `tenant = "shared"` and
`shared = false` (or unset) to the caller's tenant from auth context. The
`project` field is passed through directly — when empty, it resolves as
global to the tenant (default project). For private API full references, the
interceptor uses the explicit `tenant` field, falling back to the caller's
tenant when empty. If `shared = true` is set in the private API, it takes
precedence over the `tenant` field (maps to `tenant = "shared"`). The lookup
function always receives a resolved `tenant` and `project` string.

**Resolution modes.** The interceptor supports two resolution modes for full
references, determined by which fields the caller provides:

| Mode | Input | Behavior |
|------|-------|----------|
| Name only | `name` set, `id` empty | Look up by name within tenant scope and auto-populate `id` in the request. |
| Both | `name` and `id` both set | Look up by name and verify the supplied `id` identifies the same resource. Return `InvalidArgument` if they disagree. |

For local references (`LocalReference` messages), the same two resolution
modes apply. The tenant is normally the owning resource's effective tenant.
There is one trusted private exception for the current CaaS worker flow:
CaaS creates the destination BareMetalInstance in the builtin `system`
tenant, while its Subnet and effective NetworkACL belong to the tenant that
owns the Cluster. The authenticated CaaS controller passes that source
tenant/project as reference-resolution context, and BMaaS must resolve the
Subnet there and inherit its effective NetworkACL rather than reject the
request because the destination BMI has different metadata. This exception
is limited to the private CaaS worker create path; it does not change
tenant-facing local-reference semantics.

The lookup function uses the existing `List` + CEL filter pattern already
established in the codebase (e.g., `lookupCatalogItem`, `lookupTemplate`) to
resolve the required name within scope. When an input `id` is also present,
the resolved object's identifier is compared with it. This avoids adding a new
DAO method.

**Request mutation.** After resolution, the interceptor writes the resolved
values back into the request message via `protoreflect.Message.Set()`. This
ensures the handler and stored JSON always contain fully-qualified references
regardless of how the caller specified them. For example, a public API client
that sends `{ "name": "my-template", "shared": true }` gets the stored reference
expanded to
`{ "id": "abc-123", "name": "my-template", "project": "", "shared": true }`.
A private API client that sends `{ "name": "my-template" }` gets
`{ "id": "abc-123", "name": "my-template", "project": "", "shared": false, "tenant": "infra-templates" }`.

**Reference detection.** The interceptor identifies reference fields by
checking whether a field's message type ends with `Reference` or
`LocalReference`. This naming convention is enforced by the proto schema and
does not require manual registration of individual fields -- only the lookup
functions per referenced type need to be registered. If the interceptor
discovers a reference field whose message type has no registered lookup
function, it returns `Internal` -- this is a programming error (fail closed).
A startup-time check validates that all known reference message types have
registered lookups, preventing deployment of misconfigured servers.

**Message walking.** The interceptor uses `protoreflect.Message.Range()` to
iterate over set fields. For message-typed fields, it checks whether the
message type matches a registered reference type. For repeated fields, it
iterates each element. For oneof fields, it inspects the populated variant.
For nested messages (like `ComputeNetworkAttachment` inside
`ComputeInstanceSpec`),
it recurses.

**Tenant and project context.** For `LocalReference` messages, the interceptor
derives tenant and project from the **request's resource metadata** (the
object being created or updated), not from the caller's auth context. This
ensures local references resolve within the owning resource's scope — e.g., a
Subnet in project `team-a` resolves its VirtualNetwork local reference within
`team-a`, even if the caller (a Cloud Provider Admin via the private API) is
not in that project. The resource metadata fields are always set by the server
before the interceptor runs (via `determineAssignedTenant` and the request's
`metadata.project`). For public full `Reference` messages, `shared = true`
maps to the `shared` tenant; otherwise the caller's tenant is used. The
`project` field is used directly; when empty, the lookup targets the default
project (tenant-global scope). For private full `Reference` messages, the
explicit `tenant` field is used, falling back to the caller's context when
empty. If `shared = true`, it overrides `tenant` to `"shared"`. The `project`
field behaves the same as in public references.

**Error aggregation.** The interceptor collects all invalid references before
returning, so the user sees every problem in a single error response. It
constructs a `google.rpc.BadRequest` status detail with one `FieldViolation`
per invalid reference, where the `field` is the proto field path (e.g.,
`spec.network_attachments[0].subnet.name`) and the `description` is a
human-readable message.

**Provider/deployment-scoped resources.** Resources like NetworkClass,
ExternalIPPool, and PublicIPPool are provider/deployment-scoped and not
filtered by tenant. BareMetalInstanceType is platform-scoped and likewise is
not filtered by tenant. The
lookup function registered for these types omits tenant filtering.

**Interceptor registration in the chain:**

```
Panic Recovery -> Metrics -> Logging -> Protovalidate -> Transaction -> Auth -> Authz -> JIT Provisioning -> Reference Validation -> Handler
```

The interceptor runs after Auth (tenant context for scoped lookups) and after
Transaction (DAO lookups share the request's database transaction). Validation
failures cause a transaction rollback, which is the desired behavior (no
partial state changes).

#### Database Trigger Changes

Resources are stored as JSON-serialized protobuf in a `data` column. Existing
PL/pgSQL triggers serve two purposes:

1. **Forward reference checks (Z0002):** On insert/update, verify the
   referenced resource exists using `SELECT ... FOR SHARE` (which also
   serializes concurrent inserts and deletes). The interceptor now handles
   the existence check, but whether to keep or remove these triggers depends
   on the locking strategy — see Open Question 2.

2. **Reverse reference checks (Z0003):** On delete, verify no other resource
   still references the deleted one (e.g., prevent deleting a VirtualNetwork
   that has Subnets). The interceptor does not cover deletes — these triggers
   are kept but updated to use the new JSON paths.

**All triggers require JSON path updates** to reflect the new nested
reference structure. This is a semantic shift: triggers currently match on
resource IDs (primary keys), but will switch to matching on resource names
(unique within a tenant). This aligns with the name-based resolution model
introduced by this EP.

**Tenant scoping.** Because names are unique per tenant (not globally like
IDs), trigger queries must add tenant predicates when switching from ID-based
to name-based matching. The scoping rule depends on the reference type:

- **Same-tenant local references** (Subnet→VN, CI→Subnet, SG→VN,
  CI→InstanceType): Currently match on `id` with no tenant filter. After
  migration, add `tenant = new.tenant` (forward triggers) or
  `tenant = old.tenant` (reverse triggers) to scope lookups within the
  correct tenant.
- **Cross-tenant/shared references** (Cluster→CatalogItem,
  CI→CatalogItem): Already have tenant scoping via
  `(tenant = new.tenant OR tenant = 'shared')`. After migration, drop the
  ID match alternative and update JSON paths to nested `->>'name'`.
- **Platform-scoped references** (VN→NetworkClass): No triggers exist
  today. If added, no tenant filter is needed — platform-scoped names are
  globally unique.

Associated indexes must include `tenant` as a leading column for
same-tenant triggers to keep queries efficient.

Example path changes:

| Trigger function | Table | Path change | Tenant scoping |
|---|---|---|---|
| `check_virtual_network_not_in_use()` (Z0003) | virtual_networks | `= old.id` → `data->'spec'->'virtual_network'->>'name'` | Add `tenant = old.tenant` |
| `check_subnet_not_in_use()` (Z0003) | subnets | `->>'subnet'` → `->'subnet'->>'name'` | Add `tenant = old.tenant` |
| `check_instance_type_not_in_use()` (Z0003) | instance_types | `->>'instance_type'` → `->'instance_type'->>'name'` | Add `tenant = old.tenant` |
| `check_subnet_virtual_network_ref()` (Z0002) | subnets | `id = vn_id` → `name = vn_name` | Add `tenant = new.tenant` |
| `check_compute_instance_subnet_refs()` (Z0002) | compute_instances | `id = subnet_id` → `name = subnet_name` | Add `tenant = new.tenant` |
| `check_cluster_catalog_item_ref()` (Z0002) | clusters | Drop `id =` alternative | Already scoped |
| `check_ci_catalog_item_ref()` (Z0002) | compute_instances | Drop `id =` alternative | Already scoped |

#### CEL Filter Expression Changes

Users and the UI use CEL filter expressions in List operations. With nested
references, filter paths change:

| Before | After |
|--------|-------|
| `this.spec.virtual_network == "vnet-id"` | `this.spec.virtual_network.name == "prod-net"` |
| `this.spec.template == "tpl-id"` | `this.spec.template.name == "standard"` |
| `this.spec.pool == "pool-id"` | `this.spec.pool.name == "default-pool"` |

The `FilterTranslator` in `internal/database/dao/` translates CEL expressions
to SQL WHERE clauses. It already supports nested field access for JSON paths.
No changes to the translator are needed -- the new paths map naturally to
JSON traversal (`data->'spec'->'virtual_network'->'name'`).

Existing saved or hardcoded filters using the old path format will break.
This is acceptable per D1 (no backward compatibility). The UI and CLI update
their filter expressions as part of the same delivery chunk.

#### CLI Changes

The CLI currently accepts reference values as string flags (e.g.,
`--template my-template`, `--subnet my-subnet`). After the change, the CLI
constructs typed reference messages from flag values. Networking workload
commands use the canonical compound `--network-attachment` option defined by
Unified Networking; the option remains singular at the CLI even when the VM
or BM API field is a repeated `network_attachments` field.

**For local references (by name):**

```bash
# By name (common case):
osac create computeinstance --name my-vm --template ocp_virt_vm \
  --network-attachment subnet=app-subnet

# The CLI internally constructs:
# network_attachments[0].subnet: { name: "app-subnet" }
# the effective NetworkACL is inherited from "app-subnet"
```

**For full references with project or shared scope:**

```bash
# Reference in a specific project:
osac create cluster --name my-cluster \
  --template team-template --template-project team-a.staging

# The CLI internally constructs:
# template: { name: "team-template", project: "team-a.staging" }

# Reference in the shared tenant:
osac create cluster --name my-cluster \
  --template shared-template --template-shared

# The CLI internally constructs:
# template: { name: "shared-template", shared: true }
```

For each reference field, the CLI accepts `--<field>` (name) and
`--<field>-id` (identifier) as a consistency check alongside the name. The
`--<field>-id` form is not a standalone reference; ID-only input is rejected
because every reference requires `name`. For full reference fields,
`--<field>-project` scopes within a project and `--<field>-shared` targets the
shared tenant; both may be supplied together to scope a lookup to a project
within the shared tenant.

The CLI's `describe` output displays references with their resolved names:

```
Spec:
  Virtual Network: prod-net
  IPv4 CIDR:       10.0.1.0/24
```

For full references, `describe` also displays the resolved tenant, project, or
shared scope when that scope is meaningful. A shared reference with an
explicit project is shown as a project within the shared tenant. Local
references show their resolved resource name and do not expose tenant/project
selectors.

#### Private API and Status-Level References

Private API `_type.proto` files mirror the public API changes for all
spec-level reference fields. Private full reference messages are a superset
of public ones: they contain all public fields plus `tenant`. Both APIs must
be updated in lockstep.

Status-level references in the private API fall into two categories:

1. **System-managed `hub` fields** (13 fields across resource statuses):
   These reference the Hub resource and are set by controllers, not users. They
   use `HubLocalReference` for consistency, but the interceptor does not
   validate them (status fields are not present in Create/Update requests).

2. **Status mirror fields** (pool mirrors in ExternalIP/PublicIP status, users
   sync in RoleBindingStatus): These duplicate spec-level references in status
   for read convenience. They use the same reference message type as the spec
   field. Controllers populate them during reconciliation.

#### Incremental Delivery Plan

Delivery is organized into functional chunks. Each chunk migrates a group of
related resources, updates all layers (proto, server, interceptor registration,
database triggers, CLI, UI), and leaves the system fully functional.
[Locked: D6]

| Chunk | Resources | Reference Fields | Rationale |
|-------|-----------|-----------------|-----------|
| 1 - Interceptor + Networking | VirtualNetwork, Subnet, NetworkACL, NetworkClass | `virtual_network`, `subnets` | Foundation: build interceptor with the local networking reference graph. NetworkClass is deployment-resolved and has no tenant reference field. |
| 2 - Compute | ComputeInstance, ComputeInstanceTemplate, ComputeInstanceCatalogItem, InstanceType | `template`, `catalog_item`, `instance_type`, `subnet`, `replacement` | Highest user-facing impact. Depends on networking references from Chunk 1; the effective NetworkACL is resolved from the Subnet. |
| 3 - IP Management | ExternalIP, ExternalIPPool, ExternalIPAttachment, PublicIP, PublicIPPool, PublicIPAttachment, NATGateway | `pool` (x2), `external_ip` (x2), `public_ip`, `virtual_network`, `compute_instance`, `cluster`, `baremetal_instance` | IP resources have complex oneof targets. |
| 4 - Clusters + Bare Metal | Cluster, ClusterTemplate, ClusterCatalogItem, BareMetalInstance, BareMetalInstanceCatalogItem, BareMetalInstanceTemplate, BareMetalInstanceType | `template` (x2), `catalog_item` (x2), `baremetal_instance_type` (x2) | CaaS and BMaaS services. |
| 5 - IAM | RoleBinding, ProjectMembership, Role, User, Project | `role`, `users`, `project`, `user` | IAM references are self-contained. |

Within each chunk, the implementation order is:
1. Define reference messages in `_type.proto` files (public + private).
2. Run `buf lint && buf generate`.
3. Register lookup functions in the interceptor for the new reference types.
4. Update server code: remove inline validation for fields now handled by the
   interceptor; keep business logic validation.
5. Update database triggers and run migration.
6. Update CLI flag handling and output formatting.
7. Update UI wire format and CEL filters.
8. Update `docs/API.md` reference conventions to reflect the new patterns.
9. Update tests (unit + integration).

### Security Considerations

This enhancement inherits the existing OSAC security model without changes.

**Authentication:** Reference validation runs after the authentication
interceptor, so all DAO lookups execute in an authenticated context with a
valid tenant identity.

**Authorization:** The interceptor validates that referenced resources exist
within the appropriate scope. For local references, lookups are scoped to the
owning resource's tenant and project (derived from the request's resource
metadata). For full references with an explicit tenant/project, the existing
OPA policies enforce whether the caller has cross-tenant access. No new
authorization rules are introduced.

**Input validation:** Reference messages have a constrained schema (string
fields for id, tenant, project, name). The protobuf deserialization layer
rejects malformed input. The interceptor validates that names are non-empty
and match existing resources. No SQL injection risk exists because lookups
use parameterized DAO queries, not string concatenation.

**Project-level access:** When a user provides a `project` field in a public
full reference, the interceptor resolves the resource within that project. If
the user does not have access to the specified project within their tenant, the
interceptor returns `NotFound` (not `PermissionDenied`) to avoid disclosing
whether the project or resource exists. This follows the same pattern as
cross-tenant references.

### Failure Handling and Recovery

**Interceptor lookup failure (database error).** If the DAO lookup fails due
to a database error (connection timeout, query error), the interceptor returns
`Internal` with a generic message. The transaction interceptor handles
rollback. The client retries the request.

**Partial reference validation failure.** The interceptor validates all
references in a single pass and returns all failures together. It does not
short-circuit on the first invalid reference. This minimizes round trips for
users correcting multiple references.

**Race condition: referenced resource deleted between validation and
persistence.** The interceptor validates references within the same database
transaction as the Create/Update operation. Under `READ COMMITTED`, a
concurrent delete of the referenced resource could commit after the
interceptor's existence check but before the child insert commits. The
current forward triggers use `SELECT ... FOR SHARE` on the parent row to
serialize this — see Open Question 2 for whether to retain them or move
the locking into the interceptor's DAO lookups.

**Interceptor panic.** The panic recovery interceptor is first in the chain
and catches panics from all downstream interceptors, including the reference
validator.

### RBAC / Tenancy

No RBAC or tenancy changes are required. The reference validation interceptor
reuses the existing tenant context from the authentication interceptor. Local
reference lookups are automatically scoped to the caller's tenant and project.
Full reference lookups with explicit tenant/project are subject to existing
OPA cross-tenant access policies.

This enhancement does not introduce new resources, so no new tenant isolation
metadata (`osac.openshift.io/tenant`, `osac.openshift.io/owner-reference`)
is needed.

### Observability and Monitoring

**Metrics:**

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `osac_reference_validation_total` | Counter | `resource_type`, `result` (`valid`, `invalid`, `error`) | Total reference validations performed by the interceptor. A sustained increase in `invalid` indicates user confusion or integration issues. |
| `osac_reference_validation_duration_seconds` | Histogram | `resource_type` | Latency of reference validation per request. Useful for detecting DAO lookup performance degradation. Alert if p99 exceeds 100ms. |

**Structured logging:** The interceptor logs at `DEBUG` level for each
reference validated (resource type, name, result). At `WARN` level for
validation failures (includes the field path and error). At `ERROR` level for
DAO lookup errors (database connectivity issues).

**No new Kubernetes events.** The interceptor operates at the gRPC layer, not
the controller layer. Existing controller events are unaffected.

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Proto field number reuse causes wire incompatibility during incremental rollout | Medium | High | Each delivery chunk updates all consumers (server, CLI, UI) atomically. No mixed-version deployments within a chunk. CI validates proto compatibility within each chunk. |
| Interceptor adds latency to every Create/Update request | Low | Medium | The interceptor replaces existing inline DAO lookups, not adding new ones. Net latency change is near zero. The `osac_reference_validation_duration_seconds` metric monitors this. [Locked: R2.Q4] |
| CEL filter breakage for existing API consumers | Medium | Medium | Breaking change is accepted per D1. Document the path changes in the API changelog. Each chunk's release notes list affected filter paths. |
| Cross-chunk dependency: Chunk 2 (Compute) depends on Chunk 1 (Networking) for SubnetLocalReference | Low | Medium | Chunk ordering is fixed. Chunk 1 must merge before Chunk 2. CI enforces proto import resolution. |

### Drawbacks

**API surface complexity increases.** Each referenceable type gains one or two
new message definitions. The public API adds approximately 25 new message
types (one `LocalReference` per locally-referenced type, one `Reference` per
cross-tenant-referenced type). This increases the proto file count and
generated code size. However, each message is small (1-4 fields) and follows
a predictable pattern, so the cognitive overhead is low.

**REST/JSON verbosity increases.** `"subnet": "my-subnet"` becomes
`"subnet": { "name": "my-subnet" }`. Every reference field gains one level
of nesting. For resources with many references (ComputeInstance has 4
reference fields), the JSON body grows. This is an acceptable trade-off for
type safety and is consistent with how other infrastructure APIs (Kubernetes,
AWS CloudFormation) represent structured references.

**Breaking change for all API consumers.** Every client that creates or
updates a resource with references must update its request format. With no
backward compatibility period [Locked: D1], all consumers must update per
delivery chunk. This is mitigated by incremental delivery [Locked: D6] and
by the fact that the REST/JSON change is mechanical (wrap string in object).

**Protobuf lacks generics.** Each reference type is a separate message because
protobuf has no parameterized types. A `ResourceReference<Subnet>` would be
ideal but is not possible. The per-type approach trades verbosity for
compile-time safety -- the Go compiler rejects assigning a
`SubnetLocalReference` to a `VirtualNetworkLocalReference` field.

## Alternatives (Not Implemented)

None -- alternatives (URI/ARN format, generic reference message, do nothing)
were evaluated during design and rejected. See the PRD PR #113 discussion for
details on the URI/ARN trade-off.

## Open Questions

1. **Should status-level references (hub, pool mirrors) use typed messages?**
   The design proposes they do for consistency, but they are system-managed and
   not user-facing. Using typed messages in status adds migration work for
   controllers but prevents the schema from diverging between spec and status.
   Feedback requested from controller maintainers.

2. **Should forward reference triggers (Z0002) be kept or removed?** The
   current forward triggers use `SELECT ... FOR SHARE` on the parent row,
   which serializes concurrent child inserts and parent deletes under
   `READ COMMITTED`. Without this lock, the interceptor's plain SELECT
   leaves a race window where both a child insert and parent delete can
   commit, creating a dangling reference. Options: (a) keep forward triggers
   and update their JSON paths — redundant with the interceptor but preserves
   the locking safety net, (b) remove forward triggers and add `FOR SHARE`
   to the interceptor's DAO lookup queries. Resolve during Epic 1
   implementation.

3. **How should CEL filter changes be communicated to API consumers?** The path
   change (`this.spec.virtual_network` to `this.spec.virtual_network.name`)
   breaks existing filters. Options: (a) document in release notes only,
   (b) add a deprecation warning in the List response when old-format filters
   are detected, (c) accept breakage per D1 with no mitigation. The design
   currently assumes option (c).

## Test Plan

**Unit tests (Ginkgo):**

- Reference message construction: verify that each reference type correctly
  serializes/deserializes in both proto binary and JSON formats.
- Interceptor reference detection: verify that the interceptor discovers all
  reference-typed fields in each request message, including nested messages
  (`ComputeNetworkAttachment` inside `ComputeInstanceSpec`), repeated fields
  (`NetworkACLSpec.subnets`), and oneof fields (`ExternalIPAttachmentSpec.target`).
- Interceptor validation logic: verify that the interceptor returns
  `InvalidArgument` with correct field paths for missing references, returns
  success for valid references, and aggregates multiple errors.
- Interceptor resolution modes (full and local references): verify name-only
  resolution (id auto-populated), missing-name/id-only rejection, both-match
  resolution, and both-mismatch rejection with `InvalidArgument` explaining
  the inconsistency.
- Request mutation: verify that after interceptor runs, the request message
  contains fully-qualified references (all fields populated) regardless
  of which fields the caller originally provided.
- Per-server validation removal: verify that servers no longer perform inline
  existence checks for fields handled by the interceptor, but continue to
  perform business logic validation.

**Integration tests (kind cluster):**

- End-to-end Create with valid local reference by name: Create a
  VirtualNetwork, then a Subnet referencing it by name. Verify the Subnet
  is created and the stored reference contains both `id` and `name`.
- End-to-end Create with a local reference missing `name`: Create a
  VirtualNetwork, then attempt to create a Subnet referencing it by `id` only.
  Verify `InvalidArgument` reports that `name` is required.
- End-to-end Create with invalid reference: Attempt to create a Subnet
  referencing a nonexistent VirtualNetwork. Verify `InvalidArgument` with
  the correct field path.
- Cross-tenant reference: Create a VirtualNetwork referencing a NetworkClass
  in platform scope. Verify resolution succeeds.
- Database trigger enforcement: Delete a VirtualNetwork that has Subnets.
  Verify the trigger prevents deletion (SQLSTATE Z0003).
- CEL filter with new path: List Subnets filtered by
  `this.spec.virtual_network.name == "prod-net"`. Verify correct results.
- Oneof reference target (Chunk 3): Create a PublicIPAttachment referencing a
  ComputeInstance by name via the oneof target field. Verify the interceptor
  resolves the correct oneof variant and persists the reference.
- Oneof invalid target (Chunk 3): Create an ExternalIPAttachment with a
  nonexistent target name. Verify `InvalidArgument` with the correct oneof
  field path.
- IAM reference (Chunk 5): Create a RoleBinding referencing a Role by name.
  Verify the reference is validated and persisted correctly.
- Cross-tenant catalog item (Chunk 2): Create a ComputeInstance referencing
  a CatalogItem in the shared tenant. Verify the full reference resolves
  across tenants.
- Both-match resolution in shared scope (Chunk 2): Create a CatalogItem in
  the `shared` tenant, then create a ComputeInstance providing both `id` and
  `name` with `shared = true`. Verify success and the resolved tenant is
  `shared`.
- Both-mismatch resolution (Chunk 2): Create two CatalogItems, then create
  a ComputeInstance providing `id` of one and `name` of the other. Verify
  `InvalidArgument` with a message explaining the inconsistency.
- Concurrent create/delete (Chunk 1): In parallel, create a Subnet
  referencing a VirtualNetwork and delete that VirtualNetwork. Verify the
  `FOR SHARE` serialization prevents both from committing — no dangling
  reference remains.
- Project-scoped full reference (Chunk 2): Create a CatalogItem in project
  `team-a`, then create a ComputeInstance referencing it with
  `project = "team-a"`. Verify the stored reference includes the resolved
  project.
- Project-scoped not found (Chunk 2): Create a CatalogItem in project
  `team-a`, then attempt to reference it with `project = "team-b"`. Verify
  `NotFound` (not `PermissionDenied`) is returned.

**E2E tests (osac-test-infra, pytest):**

- Full provisioning workflow: Create NetworkClass, VirtualNetwork, Subnet,
  NetworkACL associated with the Subnet, and ComputeInstance with all
  references by name. Verify the ComputeInstance reaches RUNNING state and
  inherits the Subnet's effective NetworkACL.
- Error scenario: Attempt to create a ComputeInstance with a nonexistent
  Subnet name. Verify the API returns a clear error message.

**CLI tests (osac-cli):**

**CLI unit tests:**

- Parse a local name-only reference such as `--subnet app-subnet` and verify
  the CLI emits the corresponding typed `{name: "app-subnet"}` message.
- Parse an ID-only reference such as `--subnet-id <id>` and verify the CLI
  rejects it because all references require the name. For a full reference,
  verify name-only and both-name-and-ID forms are accepted when valid, while
  ID-only is rejected before persistence.

**CLI integration tests:**

- Supply matching name and ID and verify the request is accepted and resolved;
  supply a conflicting name and ID and verify `InvalidArgument` identifies the
  reference field and no create occurs.
- Supply `--<field>-project` and verify project-scoped resolution; supply
  `--<field>-shared` and verify shared-tenant resolution. Verify local
  networking references reject project/shared selectors. When both full
  reference selectors are supplied, verify `shared=true` selects the shared
  tenant and `project` scopes the lookup within that tenant.
- Run the same cases for typed references nested in VM/BM attachments and the
  singular Cluster attachment, plus repeated typed Subnet references in a
  NetworkACL.

**CLI E2E tests:**

- Run `describe` on resources containing resolved references and verify it
  renders the resolved resource names and applicable tenant/project/shared
  scope rather than raw IDs only.
- Pass an unknown reference, malformed ID, empty name, unsupported flag, or
  malformed compound attachment key and verify a field-specific CLI error,
  no API call for parser errors, and no persisted resource for server-side
  reference errors.

Test plan details will be developed during implementation for each delivery
chunk. Each chunk's tests cover the specific resources migrated in that chunk.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages:
Dev Preview -> Tech Preview -> GA based on production deployment feedback.

Each delivery chunk is independently shippable. A chunk graduates when:
- All reference fields in the chunk's resources use typed messages.
- The interceptor validates all references in the chunk.
- CLI and UI support the new format for the chunk's resources.
- Unit, integration, and E2E tests pass.
- API documentation and OpenAPI specs are updated.

### Removing a deprecated feature

Not applicable. The old string-based format is removed immediately with no
deprecation period. [Locked: D1]

## Upgrade / Downgrade Strategy

OSAC does not currently support in-place upgrades. Deployments are fresh
installations. No data migration or backfill is needed — trigger functions
are defined with the correct JSON paths from the start.

## Version Skew Strategy

Version skew between fulfillment-service and osac-operator during upgrades is
handled by the delivery chunk model:

- Each chunk updates fulfillment-service proto definitions, server code, and
  database triggers as a single deployment unit.
- The osac-operator communicates with fulfillment-service via gRPC using
  generated client types. When fulfillment-service updates its proto
  definitions, the operator must be rebuilt with the new generated types.
  This is coordinated within each delivery chunk.
- During the transition between chunks, some resources use typed references
  and some still use strings. This is acceptable because the interceptor only
  validates reference types it recognizes -- string fields pass through
  unchanged.

No CRD version migration is required. The osac-operator CRDs do not include
reference fields (references exist in the fulfillment-service proto layer).

## Support Procedures

**Detecting reference validation failures:**

- **Metrics:** A spike in `osac_reference_validation_total{result="invalid"}`
  indicates widespread reference errors, possibly from a misconfigured client
  or a breaking change that was not communicated.
- **Logs:** Search for `WARN` level entries with `reference_validation` in the
  structured log output. Each entry includes the resource type, field path,
  and the invalid reference name.
- **Client errors:** Clients receive `InvalidArgument` (gRPC code 3) with
  `google.rpc.BadRequest` details listing each invalid field. If clients
  report opaque errors, check whether they are parsing the error details
  correctly.

**Detecting interceptor performance degradation:**

- **Metrics:** The `osac_reference_validation_duration_seconds` histogram
  tracks per-request validation latency. If p99 exceeds 100ms, investigate
  DAO query performance (missing indexes, database load).

**Debugging reference resolution failures:**

If a reference that should be valid is rejected:
1. Check that the referenced resource exists: `osac <type> list --filter "this.metadata.name == \"<name>\""`.
2. Check tenant context: the caller's token must include the correct tenant.
   For full references with explicit tenant, verify cross-tenant access is
   permitted by OPA policy.
3. Check the interceptor registry: verify that the lookup function for the
   reference type is registered. The interceptor fails closed — an
   unregistered reference type returns `Internal`, not a silent pass-through.
   If the server started successfully, all reference types have registered
   lookups (validated at startup).

## Infrastructure Needed

None. All changes are within existing repositories (fulfillment-service,
osac-ux) and use existing CI infrastructure.
