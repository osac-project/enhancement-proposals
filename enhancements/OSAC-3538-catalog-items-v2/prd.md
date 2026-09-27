# Catalog Items v2 — Field Governance Redesign

| Field       | Value   |
|-------------|---------|
| Author(s)   | Avishay Traeger, Ilya Skornyakov |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3538 |
| Date        | 2026-08-06 |

## Problem Statement

OSAC Catalog Items let Cloud Provider Admins and Tenant Admins define curated offerings for virtual machines, clusters, and bare metal instances. An offering can fix some provisioning inputs while leaving others editable by the tenant — for example, fixing the instance type while letting the tenant choose an image.

Catalog Items are a curation layer on top of Templates: a Template defines how a resource is provisioned, and a Catalog Item builds on a Template to present a governed offering.

Today these rules are expressed through free-form field paths and generic values. Because the system does not know the meaning or type of each governed field, it cannot reliably validate governed values or present editable fields to tenants using field-appropriate inputs.

Catalog Items also reference other OSAC objects. Today those objects can be deleted while a Catalog Item still references them, silently breaking an offering.

A Catalog Item is meant to shape how a resource is provisioned, not to become an ongoing policy over that resource after it is created.

## In Scope

- Catalog Items govern a supported subset of resource fields during provisioning. Fields that a Catalog Item does not govern keep their normal creation behavior.

- Each governed field is either **locked** or **editable**:

  - **Locked:** the field uses the value defined by the Catalog Item. A tenant-supplied value for that field is rejected.
  - **Editable:** the tenant may supply a value. If no value is supplied, the Catalog Item's default is used when one is defined; otherwise the field follows its normal resource creation behavior. If the field is required and no value can be resolved, provisioning is rejected.

- Governed fields are configured using supported resource fields rather than free-form field paths and values. Values are validated as well-formed values for the selected field (for example, a real image or a valid numeric value), allowing editable fields to use field-appropriate tenant inputs. Admin-defined constraints such as allowed-value lists or numeric ranges are out of scope.

- Cloud Provider Admins and Tenant Admins can update governed field values and behavior on Catalog Items within their respective scopes. Changes affect only future provisioning.

- Template parameters can be governed with the same locked and editable behavior as resource fields. Parameter names and values that are invalid for the referenced Template's parameter definitions are rejected.

- After creation, a resource does not depend on its Catalog Item remaining available. It follows the normal resource lifecycle, and later changes to the Catalog Item do not affect it.

- Objects directly referenced by a Catalog Item, such as images, instance types, Templates, and ClusterVersions, cannot be deleted while the reference exists. This applies whether or not the Catalog Item is published.

- Catalog Items are optional for API provisioning. All three resource types can be provisioned either from a Catalog Item or directly without one.

- The initial UI provisioning flow remains Catalog Item-based.

- Cloud Provider Admins can control whether a Catalog Item is published.

- Tenant Admins can create, update, publish, unpublish, and delete Catalog Items scoped to their own organization, using the same locked and editable field behavior as global Catalog Items.

- This redesign applies to:

  - `ComputeInstanceCatalogItem`
  - `ClusterCatalogItem`
  - `BareMetalInstanceCatalogItem`

## Out of Scope

- Constraints on editable fields, such as allowed-value lists or numeric ranges.

- Hidden fields whose values are set by an administrator but not visible to tenants.

- Day-2 Catalog Item governance, or any Catalog-aware lifecycle management of resources after provisioning.

- Catalog Item versioning and additional lifecycle states such as deprecated or retired.

- Catalog Items that provision multiple resources as one composed offering.

- Cost metadata, metering, usage tracking, categories, and tags.

- Budget enforcement and approval workflows.

- Tenant Admin override mechanisms covered by OSAC-2539.

- Assigning Catalog Items to specific tenants. Tenant-level targeting needs broader architectural alignment and is deferred.

- Creating tenant-provided images is covered by a separate proposal. Catalog Items may reference tenant-provided images once they are available.

- Governance of nested or structured Template parameters.

- Unifying the three Catalog Item types into a single `CatalogItem` type.

- Migration of existing Catalog Items. OSAC is pre-GA, so existing Catalog Items can be recreated using the new model.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to define Catalog Items that prescribe input for only some fields, while allowing the remaining fields to retain their original behavior, so that I can affect only the fields I care about without having to redefine behavior for other fields.

- As a Cloud Provider Admin, I want to lock supported fields such as the image or instance type, so that I can define concrete offerings whose fixed values tenants cannot change.

- As a Cloud Provider Admin, I want editable fields to support default values, so that I can provide recommended values while still allowing tenants to make their own choices.

- As a Cloud Provider Admin, I want to configure Catalog Item fields using field-specific inputs instead of free-form paths and values, so that I can create valid offerings using the resource concepts I understand.

- As a Cloud Provider Admin, I want to update governed field values and behavior on an existing Catalog Item, so that I can maintain an offering without recreating it. Changes should apply only to future provisioning.

- As a Cloud Provider Admin, I want to govern Template parameters in the same way as resource fields, so that I can control which Template inputs tenants may change.

- As a Cloud Provider Admin, I want to be prevented from deleting an object that a Catalog Item still references, so that a published offering does not silently stop working.

- As a Cloud Provider Admin, I want to control whether a Catalog Item is published, so that I can decide whether it is available for provisioning.

### Tenant Admin

- As a Tenant Admin, I want to create, update, and delete Catalog Items for my organization using the same locked and editable field behavior as global Catalog Items, so that I can tailor offerings for my users.

- As a Tenant Admin, I want to publish and unpublish my organization's Catalog Items, so that I can control which offerings are available to my users.

### Tenant User

- As a Tenant User, I want to see the full resource configuration when provisioning from a Catalog Item, with locked values clearly identified, editable values showing any defaults, and ungoverned fields behaving normally, so that I understand what I can and cannot change.

- As a Tenant User, I want editable fields presented as typed, field-appropriate inputs that reject invalid values, so that invalid configuration is caught before provisioning.

- As a Tenant User, I want a resource created from a Catalog Item to follow the normal resource lifecycle after provisioning, so that I can manage it in the same way as a resource created without a Catalog Item.

- As a Tenant User, I want to provision resources through the API without requiring a Catalog Item, so that I can use direct API workflows when a curated offering is not needed.

## Assumptions

- For this iteration, each resource type has a single applicable Template, so which Template to use is unambiguous. Discovering and selecting among multiple Templates is deferred to a later iteration.

## Dependencies

- **DiskImage (OSAC-2540):** Image fields can use this governance model only after the DiskImage resource is available. Other governed fields are not blocked on this dependency.
