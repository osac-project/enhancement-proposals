---
title: catalog-items
authors:
  - mhrivnak
creation-date: 2026-01-12
last-updated: 2026-04-25
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
see-also:
replaces:
superseded-by:
---

# Published Templates

## Summary

Today there is a 1:1 mapping between templates and ansible roles. A user sees a
list of templates and selects one to provision. This document proposes a new
"Catalog" concept that becomes the way to present templates to users. A new
catalog API enables a single ansible role to be used as the basis for multiple
catalog items that are presented to users. That enables a CSP to define a small
number of ansible roles based on their infrastructure and use case needs, but
expose many variations of curated catalog items to users.

## Motivation

Today if the Cloud Provider Admin or Tenant Admin wants to make a new template
appear that is even just a small variation of an existing template, the only
option is to create a new ansible role. That's a lot of overhead to just create
a variation of a template.

For example, if an admin wants to have a RHEL 10 VM in sizes small, medium, and
large, they would probably create a base ansible role that can deploy RHEL 10,
and then three small stub roles that just pass pre-determined size parameters
into the primary role.

Meanwhile the Tenant Admin is not able to create templates at all, because they
don't have the ability to add or modify ansible roles.

### User Stories

* As a Cloud Provider Admin, I want to publish multiple catalog item that are similar to each other.
* As a Cloud Provider Admin, I want to publish multiple catalog item without having to create a new ansible role.
* As a Cloud Provider Admin, I want to offer catalog item to my users that pre-define the values for certain fields.
* As a Cloud Provider Admin, I want to offer catalog item to my users that prevent them from setting certain fields.

* As a Tenant Admin, I want to offer catalog item to my users that pre-define the values for certain fields.
* As a Tenant Admin, I want to offer catalog item to my users that prevent them from setting certain fields.

### Goals

* Enable provider and tenant admins to make templates available for use without requiring new ansible roles.

### Non-Goals

* Enable the use of templates that don't use ansible at all.

## Proposal

ComputeInstanceTemplate and ClusterTemplate continue to be auto-populated by the
system based on discovered ansible roles. But they will no longer be directly
usable by tenant users.

New APIs called ClusterCatalogItem and ComputeInstanceCatalogItem will be
created. Both will have similar properties, so we'll use Cluster as an example:

ClusterCatalogItem
* references an existing ClusterTemplate by ID
* includes a list of field definitions, each of which specifies a field by dot-notation path, whether it is editable by the user, an optional default value, and an optional JSON Schema validation rule
* includes a new selector field `published` that takes values TRUE and FALSE
* includes a tenant identifier that defines which tenant this CatalogItem is visible to. Defaults to all tenants if not set.

The field definitions use dot-notation paths to reference fields in the
underlying resource spec.

Cluster and ComputeInstance resources will replace the TemplateID field with a
reference to the CatalogItem. Both will have validations on create that apply
the catalog item's field definitions: non-editable fields are set to their
pre-defined values regardless of user input, and editable fields are validated
against the field's validation schema.

The osac CLI will need to be updated to use the new CatalogItem API.

### Workflow Description

Tenant Users will provision by:
#. View the list of available CatalogItems that correspond to a type of CNA (Cloud Native Asset), such as ClusterCatalogItems, and pick the one they want.
#. Create an instance of the corresponding type of CNA, such as Cluster, referencing the CatalogItem and including required fields as input.

Cloud Provider Admins will publish templates to a global catalog by:
#. curate a small collection of ansible roles that provision CNAs, including creation of all corresponding k8s resources and management of the provider's relevant infrastructure.
#. create *CatalogItems to present templates to users, specifying which fields are pre-set vs available for the user to provide.

Tenant Admins will publish templates to their organization by:
#. review the collection of templates that provision CNAs.
#. create *CatalogItems to present templates to users, specifying which fields are pre-set vs available for the user to provide.

For example, a CSP Admin could make available a ComputeInstanceTemplate that
creates a VM and takes all standard fields as input, including image reference,
memory, and vCPU. A Tenant Admin could then create three
ComputeInstanceCatalogItems that all specify a RHEL 10 image, and each has
different values for memory and vCPU. The catalog item would enable users to
provide certain other fields, but would prevent them from overriding the image,
memory and vCPU values.

### API Extensions

The catalog API exists only within the gRPC API service. It does not exist at
the k8s layer as CRDs.

Add:
* ClusterCatalogItem
* ComputeInstanceCatalogItem

Change:
* Cluster references a ClusterCatalogItem instead of a ClusterTemplate
* ComputeInstance references a ComputeInstanceCatalogItem instead of a ComputeInstanceTemplate

### Implementation Details/Notes/Constraints

#### Protobuf Message Types

This design is inspired by the [DCM project's catalog item schema](https://github.com/dcm-project/enhancements/blob/main/enhancements/catalog-item-schema/catalog-item-schema.md#catalog-item),
which defines catalog items as a list of field definitions rather than a typed
message that mirrors the underlying resource's fields. Each field definition
specifies a dot-notation path, whether the field is user-editable, an optional
default value, and an optional validation schema. This approach is
service-type-agnostic and avoids having to mirror every resource field inside
the catalog item message type.

Two new message types will be added to the proto definitions in
`fulfillment-service`, following the existing patterns for `ClusterTemplate` and
`ComputeInstanceTemplate`.

`ClusterCatalogItem`:
- `id` (string) - unique identifier, assigned by the server
- `metadata` - standard metadata (creation_timestamp, labels, annotations, etc.)
- `title` (string) - human-friendly short name for display in UIs and CLIs
- `description` (string) - markdown-formatted long description
- `template` (string) - references a `ClusterTemplate` by ID
- `fields` (repeated FieldDefinition) - ordered list of field definitions that
  specify which resource spec fields are pre-defined by the admin and which are
  editable by the user
- `published` (bool) - when false (the default), the item is hidden from Tenant
  Users; Cloud Provider Admins and Tenant Admins can see unpublished items
- `tenant` (string) - optional tenant ID that scopes visibility to a single
  tenant organization; when empty the item is visible to all tenants

`ComputeInstanceCatalogItem`:
- Same top-level structure as `ClusterCatalogItem` but references a
  `ComputeInstanceTemplate`

`FieldDefinition`:
- `path` (string) - dot-notation path of the field within the resource spec
  (e.g., `template_parameters.cpu_count`, `node_sets.workers.size`)
- `display_name` (string) - optional human-readable label for UIs and CLIs;
  derived from `path` if not set
- `editable` (bool) - when true the user may provide a value for this field;
  when false (the default) the field uses the `default` value and the user
  cannot override it
- `default` (google.protobuf.Value) - optional default value; applied as the
  fixed value for non-editable fields, or as the fallback for editable fields
  when the user does not supply a value
- `validation_schema` (google.protobuf.Struct) - optional JSON Schema object
  (draft 2020-12) constraining what values are valid for this field; only
  meaningful when `editable` is true

Both types will have corresponding `ClusterCatalogItemsService` and
`ComputeInstanceCatalogItemsService` gRPC services with `List`, `Get`, `Create`,
`Update`, and `Delete` RPCs.

#### API Behavior

The `fields` list defines the complete contract between the admin and the user
for a given catalog item. Fields not listed in `fields` are neither editable
nor pre-defined; the admin is responsible for ensuring that every field required
by the underlying template is covered by a field definition.

The dot-notation `path` references fields within the resource spec. Nested
fields and map entries are supported. For example:
- `template_parameters.cpu_count` - a specific template parameter
- `node_sets.workers.size` - the size of a named node set
- `image.name` - a sub-field of a complex field

Wildcards are not supported in paths; each field must be listed individually.

Map and list values are all-or-nothing. User-provided values for editable map
or list fields replace the entire field and are not merged with the catalog
item's `default`.

The `validation_schema` field follows
[JSON Schema (draft 2020-12)](https://json-schema.org/draft/2020-12/json-schema-validation),
supporting numeric constraints (`minimum`, `maximum`), string constraints
(`pattern`, `minLength`, `maxLength`), enumerations (`enum`), and conditional
logic (`if/then/else`). The server always validates; UIs may also use the schema
for early feedback, since users can bypass the UI via the CLI or API directly.

#### Public vs. Private API Split

Following the existing public/private server pattern:

- **Private API** (`osac/private/v1`): full CRUD over catalog items with no filtering based on `published` or `tenant`. Used by Cloud Provider Admins and Tenant Admins, and by the server internally when validating a user's create request.
- **Public API** (`osac/public/v1`): read-only for Tenant Users (`List` and `Get` only). The public server filters results to items where `published == true` and where `tenant` is empty or matches the caller's tenant. Cloud Provider Admins and Tenant Admins interact with catalog items through the private API.

The public `List` endpoint must filter by `published = true` and the caller's
tenant, so the public `CatalogItemsServer` will not simply delegate to the
private server unchanged — it must inject a tenancy and publication filter
before delegating.

#### Changes to ClusterSpec and ComputeInstanceSpec

The `template` field in `ClusterSpec` will be replaced with `catalog_item`, a
string reference to a `ClusterCatalogItem` ID. The `template_parameters` field
is retained because the catalog item's `fields` list may mark certain template
parameters as editable, allowing the user to supply values for them. The same
change applies to `ComputeInstanceSpec`.

#### Validation on Create

When a Tenant User creates a Cluster or ComputeInstance, the
`ClustersServer.Create` method (or its private equivalent) will perform these
additional steps before writing the object:

1. Fetch the referenced `CatalogItem` by ID. Return `NOT_FOUND` if it does not
   exist or is not visible to the caller's tenant.
2. Verify `published == true`. Return `NOT_FOUND` if the item is not published.
3. For each field definition in `fields`:
   - If `editable` is false: ignore any user-provided value for the field and
     apply the catalog item's `default`.
   - If `editable` is true and the user provided a value: validate the value
     against `validation_schema` if one is present. Return `INVALID_ARGUMENT`
     with a descriptive message if validation fails.
   - If `editable` is true and the user did not provide a value: apply the
     `default` if one is present.
4. Store the resulting object as the Cluster or ComputeInstance spec.

#### Tenancy and Authorization

The `tenant` field on `CatalogItem` is enforced at two layers:

1. **Read**: The public `CatalogItems_List` and `CatalogItems_Get` operations filter by `tenant = "" OR tenant = <caller_tenant>` and `published = true`. This is implemented in the public server before delegating to the private server, using the same filter-injection mechanism the other public servers use for tenancy.
2. **Write**: Only Cloud Provider Admins may create CatalogItems with `tenant = ""` (global items). Tenant Admins may only create CatalogItems with `tenant` set to their own tenant. This is enforced via policy rules consistent with the rest of the authorization model.

A tenant with a CNA that was published from a Catalog Item that has since been
unpublished should still be able to read that Catalog Item through a direct GET
request.

#### Database Migrations

Two new SQL migration files will be added under `internal/database/migrations/`:

```sql
-- cluster_catalog_items
create table cluster_catalog_items (
  id text not null primary key,
  creation_timestamp timestamp with time zone not null default now(),
  deletion_timestamp timestamp with time zone not null default 'epoch',
  name text not null default '',
  finalizers text[] not null default '{}',
  creators text[] not null default '{}',
  tenants text[] not null default '{}',
  labels jsonb not null default '{}',
  annotations jsonb not null default '{}',
  version integer not null default 0,
  data jsonb not null
);

-- compute_instance_catalog_items (identical structure)
```

#### CLI Changes

The `osac` CLI's `create cluster` and `create computeinstance` commands will be updated:

- The `--template` flag is replaced with `--catalog-item`.
- A new `get cluster-catalog-items` and `get compute-instance-catalog-items` subcommand will be added to list available catalog items so users can discover what is available to them.
- The `describe cluster` and `describe computeinstance` commands will show the referenced catalog item name/title instead of (or in addition to) the template.

#### Updates to Catalog Items

When a catalog item is changed or updated, those changes do not affect CNAs that
were previously deployed using the same catalog item.

#### Deletion

Catalog items should not be deleted if there are existing CNAs created from it.
Such catalog items should be set to unpublished, but preserved so that existing
CNAs deployed with that catalog item can maintain a reference to it.

### Risks and Mitigations

**API change**: Replacing `ClusterSpec.template` with `ClusterSpec.catalog_item` changes the create path for Clusters and ComputeInstances. All first-party consumers (CLI, operator) must be updated in the same release.

**Validation complexity**: The field-definition approach requires the server to
resolve dot-notation paths against the resource spec at request time, validate
values against JSON Schema, and apply defaults. Path resolution errors (e.g., a
typo in `path`) are not caught at CatalogItem creation time and will only
surface at request time. Mitigation: implement path resolution with clear error
messages, and write thorough unit tests covering edge cases (nested fields, map
fields, missing defaults). Require that path strings are validated against the
resource spec schema when a CatalogItem is created.

**Tenant filter injection**: The public catalog item server must inject tenant and publication filters before delegating to the private server. If this filtering is incomplete, a user could see or use catalog items intended for another tenant. Mitigation: reuse the existing tenancy filter injection patterns from other public servers; add integration tests that verify cross-tenant isolation.

### Drawbacks

Adding a catalog layer between users and templates increases conceptual
complexity. Admins now manage two related resources (templates and catalog
items) instead of one. The main argument against implementing this is that the
same goal — presenting curated options to users — could be achieved more simply
by adding a `published` flag and a pre-defined-parameters map directly to the
existing template types. The counter-argument is that multiple catalog items per
template are genuinely useful (e.g., S/M/L size variants from a single role),
and that keeping templates as a backend concept cleanly separates infrastructure
concerns (how provisioning works) from presentation concerns (what users see).

Using `google.protobuf.Value` for defaults and `google.protobuf.Struct` for
validation schemas sacrifices compile-time type safety. A typo in a path string
or a type mismatch in a default value is not caught when the CatalogItem is
created. Server-side path validation at write time partially mitigates this, but
the API does not provide the same guarantees as a fully typed proto message.

## Alternatives (Not Implemented)

**Add `published` and parameter overrides directly to templates**: The simplest
path would be to add `published` and `preset_parameters` fields directly to
`ClusterTemplate` and `ComputeInstanceTemplate`. This avoids a new resource type
and the 1:many template→catalog-item relationship. It was not selected because
it does not allow a single template to be exposed in multiple curated
configurations, and it conflates the infrastructure definition (ansible role and
its parameters) with the presentation layer (what users see and can control).

**Use Kubernetes CRDs for catalog items**: CRDs would make catalog items visible
to Kubernetes-native tooling and consistent with the osac-operator's CRD-based
resources. This was not selected because catalog items are a global presentation
layer that is not specific to any management cluster. The CRDs are
infrastructure concerns while catalog items are presentation/policy concerns
managed by admins through the fulfillment-service API.

### Alternative field-definition representations

The three alternatives below differ from the chosen approach only in how field
definitions represent types, defaults, and validation constraints within the
gRPC/protobuf layer. All three remain at the gRPC API layer and do not use CRDs.

**Typed `oneof` per field kind**: Each `FieldDefinition` uses a `oneof` to
select a type-specific sub-message carrying typed defaults and typed constraints:

```proto
message FieldDefinition {
  string path         = 1;
  string display_name = 2;
  bool   editable     = 3;
  oneof kind {
    IntegerField integer      = 4;
    StringField  string_value = 5;
    BoolField    bool_value   = 6;
  }
}
message IntegerField {
  optional int32 default = 1;
  optional int32 minimum = 2;
  optional int32 maximum = 3;
}
message StringField {
  optional string  default = 1;
  repeated string  enum    = 2;
  optional string  pattern = 3;
}
```

This gives compile-time type safety: the proto compiler rejects a string where
an int32 is expected. It was not selected because adding a new primitive type
(float, duration, complex sub-message) requires a proto schema change and
regeneration, the `oneof` is verbose for API consumers, and it cannot naturally
represent complex object defaults such as a full image sub-message.

**Extend OSAC's existing `Any`-based pattern**: OSAC already uses
`google.protobuf.Any` with a type URL string in `ClusterTemplateParameterDefinition`.
The same pattern could be applied to `FieldDefinition`, with a `type` string
declaring the expected type and an `Any` carrying the default, plus a typed
`FieldConstraints` message with named constraint fields:

```proto
message FieldDefinition {
  string              path              = 1;
  string              display_name      = 2;
  bool                editable          = 3;
  string              type              = 4; // e.g. "type.googleapis.com/google.protobuf.Int32Value"
  google.protobuf.Any default           = 5;
  FieldConstraints    constraints       = 6;
}
message FieldConstraints {
  optional double               minimum = 1;
  optional double               maximum = 2;
  optional string               pattern = 3;
  repeated google.protobuf.Any  enum    = 4;
}
```

This is consistent with the existing OSAC convention and supports any proto-typed
default including complex sub-messages. It was not selected because the `Any`
type URL ceremony is unfamiliar to API consumers, the `type` and `constraints`
fields can be set inconsistently (e.g., a `minimum` on a string field), and
`enum` as `repeated Any` is still weakly typed at the proto level.

**`google.protobuf.Value` for defaults with a typed constraint message**: This
uses `google.protobuf.Value` (a JSON-compatible scalar or object, without the
type URL of `Any`) for defaults, paired with a typed `FieldConstraints` proto
message that covers common constraint kinds as named fields:

```proto
message FieldDefinition {
  string                 path              = 1;
  string                 display_name      = 2;
  bool                   editable          = 3;
  google.protobuf.Value  default           = 4;
  FieldConstraints       constraints       = 5;
}
message FieldConstraints {
  optional double                  minimum   = 1;
  optional double                  maximum   = 2;
  optional string                  pattern   = 3;
  repeated google.protobuf.Value   enum      = 4;
}
```

The constraint message is typed and self-documenting in the proto schema,
avoiding the need for a JSON Schema library. It was not selected because adding
a new constraint keyword (e.g., `minLength`, `if/then/else`) requires a proto
schema change, and `enum` as `repeated Value` is still weakly typed. The chosen
approach (Option 4) accepts a freeform `google.protobuf.Struct` for the
validation schema, trading proto-level constraint typing for full JSON Schema
expressiveness without requiring proto changes to support new constraint kinds.

## Open Questions [optional]

## Test Plan

Standard unit and integration tests.

## Graduation Criteria

The feature will be considered complete when:

- All new API endpoints (ClusterCatalogItems, ComputeInstanceCatalogItems) are implemented and tested.
- The Cluster and ComputeInstance create path validates against the referenced catalog item.
- The CLI is updated to use `--catalog-item` in place of `--template`.
- Cloud Provider Admin and Tenant Admin workflows are documented.
- The `template` field is removed from ClusterSpec/ComputeInstanceSpec and replaced with `catalog_item`.

## Upgrade / Downgrade Strategy

Not applicable; there are no deployed instances or stored data to migrate.

## Version Skew Strategy

Not applicable at this stage.

## Support Procedures

## Infrastructure Needed [optional]

None.
