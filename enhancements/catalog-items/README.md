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
* includes the same fields as the ClusterTemplate API, giving the admin an opportunity to pre-define values.
* includes an exclusive list of fields that the user can specify.
* includes a new selector field `published` that takes values TRUE and FALSE
* includes a tenant identifier that defines which tenant this CatalogItem is visible to. Defaults to all tenants if not set.

The exclusive list of fields that the user can specify will use dot-notation
if necessary to reference nested fields.

Cluster and ComputeInstance resources will replace the TemplateID field with a
reference to the CatalogItem. Both will have validations on create that ensure
the user did not provide any fields that are not in the CatalogItem's list of
allowed fields.

The osac-cli will need to be updated to use the new CatalogItem API.

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

Two new message types will be added to the proto definitions in `fulfillment-service`, following the existing patterns for `ClusterTemplate` and `ComputeInstanceTemplate`.

`ClusterCatalogItem`:
- `id` (string) - unique identifier, assigned by the server
- `metadata` - standard metadata (creation_timestamp, labels, annotations, etc.)
- `title` (string) - human-friendly short name for display in UIs and CLIs
- `description` (string) - markdown-formatted long description
- `template` (string) - references a `ClusterTemplate` by ID
- `template_parameters` (map<string, Any>) - pre-defined parameter values using the same type encoding as `ClusterSpec.template_parameters`
- `node_sets` (map<string, ClusterCatalogItemNodeSet>) - pre-defined node set configuration; entries here override defaults from the template
- `allowed_fields` (repeated string) - dot-notation list of fields the user is permitted to provide when creating a Cluster; fields not in this list will be rejected if provided by the user
- `published` (bool) - when false (the default), the item is hidden from Tenant Users; Cloud Provider Admins and Tenant Admins can see unpublished items
- `tenant` (string) - optional tenant ID that scopes visibility to a single tenant organization; when empty the item is visible to all tenants

`ComputeInstanceCatalogItem`:
- Same structure as `ClusterCatalogItem` but references a `ComputeInstanceTemplate` and carries fields from `ComputeInstanceSpec` (image, cores, memory_gib, boot_disk, run_strategy, etc.) as pre-definable values

Both types will have corresponding `ClusterCatalogItemsService` and
`ComputeInstanceCatalogItemsService` gRPC services with `List`, `Get`, `Create`,
`Update`, and `Delete` RPCs.

#### API Behavior

The dot-notation for allowed fields may use a wildcard to include nested fields.

Dot-notation does not differentiate between fields that are a singular value, a
map, or a list.

Map and List values are all-or-nothing. User-provided values will not be merged
with those provided by the Catalog Item.

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
is retained because the CatalogItem's `allowed_fields` may permit the user to
supply additional parameter values. The same change applies to
`ComputeInstanceSpec`.

#### Validation on Create

When a Tenant User creates a Cluster or ComputeInstance, the
`ClustersServer.Create` method (or its private equivalent) will perform these
additional steps before writing the object:

1. Fetch the referenced `CatalogItem` by ID. Return `NOT_FOUND` if it does not exist or is not visible to the caller's tenant.
2. Verify `published == true`. Return `NOT_FOUND` if the item is not published.
3. Enumerate every field set by the user in the request (using proto reflection, similar to how `GenericMapper` already walks fields). Return `INVALID_ARGUMENT` if any field is not present in `allowed_fields`.
4. Merge the `CatalogItem`'s pre-defined field values into the request data, with user-provided values taking precedense.
5. Store the merged object as the Cluster or ComputeInstance spec.

#### Tenancy and Authorization

The `tenant` field on `CatalogItem` is enforced at two layers:

1. **Read**: The public `CatalogItems_List` and `CatalogItems_Get` operations filter by `tenant = "" OR tenant = <caller_tenant>` and `published = true`. This is implemented in the public server before delegating to the private server, using the same filter-injection mechanism the other public servers use for tenancy.
2. **Write**: Only Cloud Provider Admins may create CatalogItems with `tenant = ""` (global items). Tenant Admins may only create CatalogItems with `tenant` set to their own tenant. This is enforced via policy rules consistent with the rest of the authorization model.

A tenant with a CNA that was published from a Catalog Item that has since been
unpublished should still be able to read that Catalog Item through a direct GET
operation.

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

Catalog items should not be deleted. They should be set to unpublished, but
preserved so that existing CNAs deployed with that catalog item can maintain a
reference to it.

### Risks and Mitigations

**API change**: Replacing `ClusterSpec.template` with `ClusterSpec.catalog_item` changes the create path for Clusters and ComputeInstances. All first-party consumers (CLI, operator) must be updated in the same release.

**Validation complexity**: The `allowed_fields` allow-list introduces new validation logic that must work correctly with proto field names including nested paths using dot notation. Any mistake here could silently allow users to override pre-defined values. Mitigation: use proto reflection to enumerate fields set in a request, and write thorough unit tests covering edge cases (empty allow-list, nested fields, map fields).

**Tenant filter injection**: The public catalog item server must inject tenant and publication filters before delegating to the private server. If this filtering is incomplete, a user could see or use catalog items intended for another tenant. Mitigation: reuse the existing tenancy filter injection patterns from other public servers; add integration tests that verify cross-tenant isolation.

### Drawbacks

Adding a catalog layer between users and templates increases conceptual complexity. Admins now manage two related resources (templates and catalog items) instead of one. The main argument against implementing this is that the same goal — presenting curated options to users — could be achieved more simply by adding a `published` flag and a pre-defined-parameters map directly to the existing template types. The counter-argument is that multiple catalog items per template are genuinely useful (e.g., S/M/L size variants from a single role), and that keeping templates as a backend concept cleanly separates infrastructure concerns (how provisioning works) from presentation concerns (what users see).

The `allowed_fields` mechanism also adds ongoing maintenance: every new field added to `ClusterSpec` or `ComputeInstanceSpec` must be considered for inclusion as an allow-listable field, increasing the surface area of the API.

## Alternatives (Not Implemented)

**Add `published` and parameter overrides directly to templates**: The simplest path would be to add `published`, `allowed_fields`, and `preset_parameters` fields directly to `ClusterTemplate` and `ComputeInstanceTemplate`. This avoids a new resource type and the 1:many template→catalog-item relationship. It was not selected because it does not allow a single template to be exposed in multiple curated configurations, and it conflates the infrastructure definition (ansible role and its parameters) with the presentation layer (what users see and can control).

**Use Kubernetes CRDs for catalog items**: CRDs would make catalog items visible to Kubernetes-native tooling and consistent with the osac-operator's CRD-based resources. This was not selected because catalog items are a global presentation layer that is not specific to any management cluster. The CRDs are infrastructure concerns while catalog items are presentation/policy concerns managed by admins through the fulfillment-service API.

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
