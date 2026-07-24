---
title: catalog-items
authors:
  - mhrivnak
creation-date: 2026-01-12
last-updated: 2026-07-23
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

#### Cloud Provider Admin — Catalog Item Creation

* As a Cloud Provider Admin, I need to create a catalog item by selecting a resource type and choosing an existing template for that type, so the catalog item is backed by a known, working template.

* As a Cloud Provider Admin, I need to configure which resource fields are pre-set vs. editable when creating a catalog item. The system presents all fields from the resource spec (e.g., ComputeInstanceSpec or ClusterSpec), and I configure each one — I do not need to manually specify field paths. By default, fields are non-editable except for `ssh_public_key` and `pull_secret`, which default to editable. Default values are pre-populated from the selected template when they exist.

* As a Cloud Provider Admin, for each editable field I need to optionally provide a default value and define validation constraints, so I can guide tenant input while enforcing guardrails. Validation constraints are specified as a JSON Schema (draft 2020-12) object stored in the field definition's `validation_schema` field. Constraint types and examples:

  **Scalar constraints:**
  - **Numeric bounds** (`minimum`, `maximum`): restrict numeric fields to a range.
    Example: `node_sets.workers.size` with `{"minimum": 3, "maximum": 12}` limits worker node count to 3–12.
  - **Allowed values** (`enum`): restrict a field to a fixed set of choices.
    Example: `run_strategy` with `{"enum": ["Always", "RerunOnFailure", "Halted"]}` limits the VM run strategy to approved options.
  - **String length** (`minLength`, `maxLength`): constrain text field lengths.
    Example: `user_data` with `{"maxLength": 65536}` to enforce a size limit on cloud-init user data.
  - **Pattern** (`pattern`): enforce format with a regular expression.
    Example: `ssh_public_key` with `{"pattern": "^ssh-(rsa|ed25519) "}` to require a valid SSH public key prefix.
  - **Combinations**: multiple constraints can be combined in a single schema.
    Example: `boot_disk.size_gib` with `{"minimum": 50, "maximum": 500}` combined with a default of 100.

  **Resource reference fields:**
  - Fields that reference backend resources (such as `instance_type` referencing an InstanceType, or `image_type` referencing an ImageType) do not have validation constraints in the catalog item creation UI. Instead, the admin selects a default value from a dropdown of existing resources fetched from the corresponding API endpoint. The backend validates that the selected value is a valid, existing resource at provisioning time.
    Example: `instance_type` — the UI fetches available InstanceType resources and presents them as a dropdown for the admin to select a default value.
    Example: `image_type` — the UI fetches available ImageType resources for default value selection.

  **List and map constraints:**
  - **Item count** (`minItems`, `maxItems`): control whether users can add or remove entries in repeated fields. Setting `minItems` and `maxItems` to the same value locks the list length, preventing users from adding or removing items while still allowing edits to each item's fields.
    Example: `network_attachments` with `{"minItems": 1, "maxItems": 1}` locks a VM to exactly one network attachment — the user can choose which subnet and security groups but cannot add a second NIC.
    Example: `network_attachments` with `{"minItems": 1, "maxItems": 4}` allows 1–4 network attachments.
    Example: `additional_disks` with `{"maxItems": 0}` prevents users from adding any additional disks beyond the boot disk.
  - **Map entry count** (`minProperties`, `maxProperties`): same pattern for map fields.
    Example: `node_sets` with `{"minProperties": 2, "maxProperties": 2}` locks a cluster to exactly two node sets (e.g., control-plane + workers) — the user can edit each node set's `size` but cannot add or remove node sets.

  The UI provides structured form controls for supported simple constraint types (numeric bounds, allowed values, string length, pattern, item count). If a field has an existing validation schema that uses keywords beyond what the UI supports (e.g., `if/then/else`, `oneOf`, nested properties, item schemas), the UI displays a read-only message indicating that this validation cannot be edited through the UI and must be managed via the OSAC CLI. Admins who need full JSON Schema expressiveness use the CLI directly.

* As a Cloud Provider Admin, I need the system to provide sensible default validation schemas for common field types when I create a catalog item, so I can configure validation quickly without manually constructing JSON Schema for every field. For example:
  - `ssh_public_key` and `pull_secret` should have default pattern-based validation (the admin can accept the default or customize it)
  - `user_data` should have a default maximum length constraint
  - `node_sets.<name>.size` should default to a minimum/maximum integer constraint
  - Fields referencing backend resources (`instance_type`, `image_type`) should present available resources as a selectable dropdown for default value selection
  The backend is responsible for providing these defaults based on the field type; the admin can override or tighten them.

* As a Cloud Provider Admin, I need to provide identifying information for the catalog item, so tenants can understand what the offering provides when browsing the catalog.

* As a Cloud Provider Admin, I need to choose the scope of the catalog item — either General (visible to all tenants) or Organization (scoped to a specific tenant) — so I can create targeted offerings for specific organizations. When publishing or unpublishing, the action applies only within the selected scope.

#### Cloud Provider Admin — Catalog Item Lifecycle

* As a Cloud Provider Admin, I need to publish or unpublish a catalog item to control whether tenant users can see and provision from it. Unpublished items are excluded from Tenant User listing and browsing; however, a Tenant User can still retrieve an unpublished item via a direct `Get` if it is referenced by one of their existing CNAs.

* As a Cloud Provider Admin, I need to edit an existing catalog item to update its configuration and publication status. The backing template cannot be changed after creation.

* As a Cloud Provider Admin, I need to view a catalog item's full configuration and see which resources have been provisioned from it.

* As a Cloud Provider Admin, I need to delete a catalog item that is no longer needed. If resources have been provisioned from it, deletion must be blocked and I should unpublish it instead, so existing resources retain their catalog item reference.

* As a Cloud Provider Admin, I need to see all catalog items across all tenants (both published and unpublished), so I can manage the full catalog.

#### Tenant Admin — Catalog Item Creation

* As a Tenant Admin, I need to create organization-scoped or project-scoped catalog items by selecting a resource type and choosing an existing template, using the same creation flow as a Cloud Provider Admin.

* As a Tenant Admin, I need to configure which resource fields are pre-set vs. editable when creating a catalog item, using the same field definitions editor as a Cloud Provider Admin.

* As a Tenant Admin, I need to provide identifying information for the catalog item, so my organization's users can distinguish it from other offerings in the catalog.

* As a Tenant Admin, I need to choose the scope of the catalog item — either Organization (visible to all projects within my tenant) or Project (scoped to a specific project) — so I can create targeted offerings at the right level. The tenant assignment is automatic; I control whether the item is organization-wide or project-specific.

#### Tenant Admin — Catalog Item Lifecycle

* As a Tenant Admin, I need to publish or unpublish catalog items scoped to my organization or project to control whether my users can see and provision from them. Publication applies only within the configured scope.

* As a Tenant Admin, I need to edit organization-scoped and project-scoped catalog items to update their name, description, publication status, and field definitions. I cannot modify general (global) catalog items created by Cloud Provider Admins.

* As a Tenant Admin, I need to view a catalog item's full configuration and see which resources in my organization have been provisioned from it.

* As a Tenant Admin, I need to delete an organization-scoped or project-scoped catalog item that is no longer needed, subject to the same provisioned-resource blocking as general items.

* As a Tenant Admin, I need to see my organization's catalog items alongside general (global) items, with a clear distinction between general (read-only), organization-scoped (manageable), and project-scoped (manageable) items.

#### Tenant User — Catalog Browsing and Provisioning

* As a Tenant User, I need to browse published catalog items so I can find the right offering for my needs.

* As a Tenant User, when I provision from a catalog item, I need to see the full resource configuration — both the pre-set values I cannot change and the editable values I need to provide — so I understand what I am getting.

* As a Tenant User, I need to provision resources through catalog items without needing to understand templates, Ansible roles, or the underlying field definitions.

* As a Tenant User, I do not have access to catalog item management — I only interact with published catalog items to browse and provision.

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
* includes a list of field definitions, each of which specifies a field by dot-notation path, whether it is editable by the user, an optional default value, and an optional JSON Schema validation rule. The UI always includes all fields from the resource spec, but the API accepts partial field lists (e.g., CLI-created items may include only a subset).
* includes a new selector field `published` that takes values TRUE and FALSE
* includes a tenant identifier that defines which tenant this CatalogItem is visible to. Defaults to all tenants if not set.
* uses the existing `metadata.project` field (available on all OSAC resources) to optionally scope visibility to a specific project within the tenant. When `metadata.project` is empty, the item is visible to all projects within the tenant.

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
1. View the list of available CatalogItems that correspond to a type of CNA (Cloud Native Asset), such as ClusterCatalogItems, and pick the one they want.
2. Create an instance of the corresponding type of CNA, such as Cluster, referencing the CatalogItem and including required fields as input.

Cloud Provider Admins will publish templates to a global catalog by:
1. curate a small collection of ansible roles that provision CNAs, including creation of all corresponding k8s resources and management of the provider's relevant infrastructure.
2. create *CatalogItems to present templates to users, specifying which fields are pre-set vs available for the user to provide.

Tenant Admins will publish templates to their organization by:
1. review the collection of templates that provision CNAs.
2. create *CatalogItems to present templates to users, specifying which fields are pre-set vs available for the user to provide.

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
  editable by the user. The UI includes all resource spec fields; the API
  accepts partial lists for CLI and programmatic use
- `published` (bool) - when false (the default), the item is hidden from Tenant
  Users; Cloud Provider Admins and Tenant Admins can see unpublished items
- `tenant` (string) - internal field, not exposed through the public API. Scopes
  visibility to a single tenant organization; when empty the item is visible to
  all tenants. Set automatically by the server for Tenant Admin creates.
Note: Project-level scoping uses the existing `metadata.project` field (field 10
  on `Metadata`, available on all OSAC resources). When `metadata.project` is set
  alongside `tenant`, the item is visible only within that project. When empty
  (with `tenant` set), the item is visible to all projects within the tenant.
  Set by the Tenant Admin during creation; CSP Admins do not create
  project-scoped items.

`ComputeInstanceCatalogItem`:
- Same top-level structure as `ClusterCatalogItem` but references a
  `ComputeInstanceTemplate`

`FieldDefinition`:
- `path` (string) - dot-notation path of the field within the resource spec
  (e.g., `template_parameters.ocp_release_version`, `node_sets.workers.size`)
- `display_name` (string) - optional human-readable label for UIs and CLIs;
  derived from `path` if not set
- `editable` (bool) - when true the user may provide a value for this field;
  when false (the default) the field uses the `default` value and the user
  cannot override it
- `default` (google.protobuf.Value) - default value for the field. Required
  when `editable` is false (the server rejects catalog items where a
  non-editable field has no default, since omitting both editability and a
  default would leave a required template field unpopulated). Optional when
  `editable` is true, where it serves as the fallback when the user does not
  supply a value
- `validation_schema` (google.protobuf.Struct) - optional JSON Schema object
  (draft 2020-12) constraining what values are valid for this field; only
  meaningful when `editable` is true

Both types will have corresponding `ClusterCatalogItemsService` and
`ComputeInstanceCatalogItemsService` gRPC services with `List`, `Get`, `Create`,
`Update`, and `Delete` RPCs.

#### API Behavior

##### Template defaults and node sets

When a resource is created from its corresponding catalog item, the server
first applies structural data from the referenced template before processing
field definitions. This is necessary because templates may define data that cannot
be expressed as individual field definitions - most notably, node sets.

A cluster template defines which node sets exist (e.g., a control-plane node set
with 3 replicas on host-type-A, a workers node set with 5 replicas on
host-type-B). These node sets are structural: they define the shape of the
cluster, not just individual field values. The server populates the cluster spec
with this structural data from the template so that field definitions can then
override individual properties within it.

Specifically, the server:

1. Applies the template's spec defaults to the cluster spec.
2. Copies node sets from the template into the cluster spec, then applies the
   catalog item's field definitions to node set properties. For each node set
   property covered by a field definition:
   - Non-editable properties receive the admin's fixed default value.
   - Editable properties accept user-provided values (validated against
     `validation_schema` if present), fall back to the admin's default when
     the user does not provide a value, and otherwise retain the
     template-applied value.
   - User-provided node sets whose name is not declared by the template are
     rejected (`INVALID_ARGUMENT`).
   - Template-defined properties not covered by field definitions are
     preserved as-is.

##### Field definitions

The `fields` list defines the contract between the admin and the user for a
given catalog item. The UI includes all fields from the resource spec (e.g.,
all fields in `ComputeInstanceSpec` for a `ComputeInstanceCatalogItem`), but
the API accepts partial field lists — not all fields need to be included.
Fields not listed in `fields` are not managed by the catalog item. The server
rejects catalog items that reference fields not defined in the resource spec.

Networking fields (`network_attachments`) are not shown in the catalog item
creation wizard. Instead, the UI automatically includes `network_attachments`
in the API payload as an editable field with no default value and no validation
schema. This allows the tenant user to configure network attachments during
provisioning without requiring the admin to explicitly manage them.

The dot-notation `path` references fields within the resource spec. Nested
fields and map entries are supported. For example:
- `template_parameters.ocp_release_version` - a specific template parameter
- `node_sets.workers.size` - the size of a node set named `workers` (defined by the template)
- `image.name` - a sub-field of a complex field

Wildcards are not supported in paths; each field must be listed individually.

Map and list values are all-or-nothing. User-provided values for editable map
or list fields replace the entire field and are not merged with the catalog
item's `default`.

The `validation_schema` field accepts any valid
[JSON Schema (draft 2020-12)](https://json-schema.org/draft/2020-12/json-schema-validation)
object. The server validates user-provided field values against the full schema
at provisioning time using a standard JSON Schema validator — no keywords are
restricted. The UI provides structured form controls for simple constraint
types (numeric bounds, enum, string length, pattern, item count). For schemas
that use keywords beyond the UI's supported set, the UI displays a read-only
message directing the admin to use the OSAC CLI.

#### Public vs. Private API Split

Following the existing public/private server pattern:

- **Private API** (`osac/private/v1`): full CRUD over catalog items with no filtering based on `published` or `tenant`. Used by Cloud Provider Admins, and by the server internally when validating a user's create request.
- **Public API** (`osac/public/v1`): used by Tenant Admins and Tenant Users. The `tenant` field is not exposed to either role — it is stripped from all responses and ignored on writes. Tenant Admins have full CRUD over their own organization-scoped catalog items and can see all catalog items scoped to their tenant (published or not); on create the server automatically sets `tenant` to the caller's tenant. Tenant Users have read-only access (`List` and `Get` only) and only see items where `published == true` and `tenant` is empty or matches the caller's tenant. Exception: a Tenant User can always `Get` a catalog item referenced by one of their existing CNAs, even if that item is unpublished.

The public `List` endpoint always filters by the caller's tenant; for Tenant
User callers it additionally filters by `published = true`. The public
`CatalogItemsServer` therefore cannot simply delegate to the private server
unchanged — it must inject filters based on the caller's role before
delegating.

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
3. Fetch the template referenced by the catalog item (`ClusterTemplate` for
   Clusters, `ComputeInstanceTemplate` for ComputeInstances). Return
   `INVALID_ARGUMENT` if the template does not exist or has been deleted.
4. Apply template structural data to the resource spec:
   a. Apply the template's spec defaults.
   b. Populate node sets from the template, merging with any user-provided
      overrides. Reject any user-provided node set whose name is not declared
      by the template (`INVALID_ARGUMENT`). For recognized node sets, validate
      that user-provided host types are defined in the template.
5. For each field definition in `fields`:
   - If `editable` is false and the user provided a value: return
     `INVALID_ARGUMENT`. Non-editable fields cannot be overridden.
   - If `editable` is false and the user did not provide a value: apply the
     catalog item's `default`. A non-editable field must have a `default`;
     the server returns an error if one is missing.
   - If `editable` is true and the user provided a value: validate the value
     against `validation_schema` if one is present. Return `INVALID_ARGUMENT`
     with a descriptive message if validation fails.
   - If `editable` is true and the user did not provide a value: apply the
     `default` if one is present; otherwise retain the template-applied value.
6. Store the resulting object as the Cluster or ComputeInstance spec.

#### Tenancy and Authorization

The `tenant` field and `metadata.project` on `CatalogItem` are enforced at two layers:

1. **Read**: The public `CatalogItems_List` and `CatalogItems_Get` operations always filter by `tenant = "" OR tenant = <caller_tenant>`. When `metadata.project` is set on a catalog item, visibility is further restricted to users within that project. When the caller is a Tenant User, the public server additionally injects `published = true`, with one exception: a Tenant User may `Get` a catalog item referenced by one of their existing CNAs even if that item is unpublished. Tenant Admins see all items in their tenant regardless of publication status. This is implemented in the public server before delegating to the private server, using the same filter-injection mechanism the other public servers use for tenancy.
2. **Write**: Cloud Provider Admins set `tenant` explicitly; `tenant = ""` creates a general (global) item. CSP Admins choose between General (global) or Organization (tenant-scoped). For Tenant Admins, the public server injects `tenant` from the caller's identity — the field is not accepted from the caller. Tenant Admins set `metadata.project` explicitly to create project-scoped items, or leave it empty for organization-scoped items. Tenant Admins can only Update or Delete catalog items scoped to their own tenant; they cannot modify general items (`tenant = ""`) or items belonging to another tenant. The server validates that a specified `project` belongs to the caller's tenant.

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

Templates referenced by one or more catalog items must also be protected from
deletion. If a template is referenced by any catalog item (published or
unpublished), the server must reject the delete request. This prevents orphaned
catalog items that reference a non-existent template. Admins must delete or
reassign all catalog items referencing a template before the template itself
can be deleted.

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

**Tenant filter injection**: The public catalog item server must inject a tenant filter before delegating to the private server; for Tenant User callers, it must additionally inject a `published = true` filter. If this filtering is incomplete, a user could see or use catalog items intended for another tenant, or unpublished items they should not see. Mitigation: reuse the existing tenancy filter injection patterns from other public servers; add integration tests that verify cross-tenant isolation and that Tenant Users cannot see unpublished items.

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

Standard unit and integration tests. Integration tests must cover:

- Cross-tenant isolation: a Tenant User cannot see catalog items belonging to another tenant.
- Publication filtering: a Tenant User cannot list or get unpublished items they do not already reference via a CNA.
- CNA reference exception: a Tenant User can `Get` a catalog item referenced by one of their existing CNAs even after that item is unpublished, but cannot list or get unrelated unpublished items.
- Tenant Admin visibility: a Tenant Admin can see all catalog items in their tenant regardless of publication status.
- Tenant field injection: the `tenant` field is absent from public API responses and auto-set on Tenant Admin creates.
- Tenant Admin write isolation: a Tenant Admin cannot create, update, or delete catalog items scoped to another tenant.
- Post-create response: `Create` returns the new catalog item ID so clients can redirect to the detail page or confirm success.

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
