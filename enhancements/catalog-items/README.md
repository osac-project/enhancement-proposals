---
title: catalog-items
authors:
  - mhrivnak
creation-date: 2026-01-12
last-updated: 2026-03-19
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
see-also:
replaces:
superseded-by:
---

# Template Inheritance

## Summary

Today there is a 1:1 mapping between templates and Ansible roles. This document
proposes extending the existing `ClusterTemplate` and
`ComputeInstanceTemplate` types with an inheritance mechanism that enables
admins and tenants to derive new templates from existing ones. A derived
template can override default values and _seal_ parameters so that users cannot
change them. This removes the need for a new Ansible role every time a
variation of an existing template is needed, and it allows tenant admins to
curate their own catalog of templates without any Ansible work at all.

## Motivation

Today if the Cloud Provider Admin or Tenant Admin wants to make a new template
appear that is even just a small variation of an existing template, the only
option is to create a new Ansible role. That's a lot of overhead to just create
a variation of a template.

For example, if an admin wants to have a RHEL 10 VM in sizes small, medium, and
large, they would probably create a base Ansible role that can deploy RHEL 10,
and then three small stub roles that just pass pre-determined size parameters
into the primary role.

Meanwhile the Tenant Admin is not able to create templates at all, because they
don't have the ability to add or modify Ansible roles.

### User Stories

* As a Cloud Provider Admin, I want to publish multiple templates that are
  similar to each other.
* As a Cloud Provider Admin, I want to publish multiple templates without
  having to create a new Ansible role for each one.
* As a Cloud Provider Admin, I want to offer templates to my users that
  pre-define the values for certain fields.
* As a Cloud Provider Admin, I want to offer templates to my users that prevent
  them from changing certain fields.
* As a Tenant Admin, I want to create new templates that are derived from
  existing ones, customizing default values and restricting parameters, without
  needing access to Ansible roles.
* As a Tenant Admin, I want to offer templates to my users that pre-define the
  values for certain fields.
* As a Tenant Admin, I want to offer templates to my users that prevent them
  from changing certain fields.

### Goals

* Enable provider and tenant admins to make templates available for use without
  requiring new Ansible roles.
* Reuse the existing `ClusterTemplate` and `ComputeInstanceTemplate` types
  rather than introducing new API types.

### Non-Goals

* Enable the use of templates that don't use Ansible at all.

## Proposal

This proposal extends the existing `ClusterTemplate` and
`ComputeInstanceTemplate` types with template inheritance. Both template types
will be extended in the same way, so the description below uses
`ClusterTemplate` as the running example, but the same applies to
`ComputeInstanceTemplate`.

The key ideas are:

1. **Template inheritance via a `parent` field.** A new `parent` field is added
   to `ClusterTemplate`. When set, the template inherits all parameter
   definitions from the referenced parent. This forms a tree of templates where
   the root template is one that has no parent and is typically backed by an
   Ansible role.

2. **Sealed parameters.** A child template can override the `default` value of
   a parameter inherited from its parent and mark it as `sealed`. A sealed
   parameter's value is fixed and cannot be changed by users when creating a
   cluster. The child template only needs to specify the fields it overrides
   (`default`, `sealed`); the `type`, `title`, and `description` are
   automatically inherited from the parent.

3. **Ansible role resolution.** Currently, the Ansible role name is derived
   directly from the template name. With inheritance, the Ansible role name is
   taken from the root of the inheritance tree. For example, if
   `ocp_17_small_with_gpu` inherits from `ocp_17_small`, then clusters created
   with either template will use the `ocp_17_small` Ansible role. In addition,
   an `ansible_role` field (or alternatively an `osac/ansible_role` annotation)
   can be used to override this default resolution when needed.

4. **Effective view.** An `effective` query parameter is added to the list and
   get template endpoints. When set to `true`, the response contains the
   _flattened_ representation of the template with all inherited parameter
   definitions merged in. When `false` (the default), only the raw fields of
   the template itself are returned.

5. **Tenant template creation.** To allow tenants to create their own derived
   templates, the Authorino authorization configuration is updated to permit
   the operation. The existing visibility mechanism already ensures that
   tenants only see the templates assigned to them.

### Workflow Description

**Tenant Users** will provision clusters or compute instances by:

1. List the available templates (optionally with `effective=true` to see the
   full parameter definitions) and pick one.
2. Create a cluster (or compute instance) referencing the chosen template and
   providing values for the non-sealed parameters.

**Cloud Provider Admins** will publish templates by:

1. Curate a collection of Ansible roles that provision cloud-native assets,
   resulting in root templates.
2. Optionally create child templates that inherit from a root template, setting
   defaults and sealing parameters as needed.
3. Assign templates to tenants using the existing visibility mechanism.

**Tenant Admins** will publish templates to their organization by:

1. Review the templates available to them.
2. Create new child templates that inherit from an available template, setting
   defaults and sealing parameters to present a curated selection to their
   users.

For example, a CSP Admin could provide a `ComputeInstanceTemplate` called
`fedora_vm` that creates a Fedora virtual machine. It has parameters
`version` and `selinux`. A Tenant Admin could then create a child template
`fedora_43_vm` that inherits from `fedora_vm`, sets the `version` parameter
default to `43`, and seals it. Users creating a compute instance with the
`fedora_43_vm` template can still set `selinux` but cannot change the
Fedora version.

### API Extensions

**Changes to `ClusterTemplate` and `ComputeInstanceTemplate`:**

Add a `parent` field containing the identifier of the parent template. When
this is empty the template is a root template.

Add a `sealed` boolean field to `ClusterTemplateParameterDefinition` (and the
equivalent `ComputeInstanceTemplateParameterDefinition`). When `true`, the
parameter value is locked to its `default` and cannot be overridden by users
when creating a resource.

Add an `ansible_role` field to `ClusterTemplate` (and
`ComputeInstanceTemplate`). This is optional; when set it explicitly specifies
the Ansible role to use for provisioning, overriding the default resolution
based on the root template name.

**Changes to list/get template endpoints:**

Add an `effective` query parameter. When `true`, the returned templates
include all parameters inherited from parent templates, with overrides applied.

**Changes to `Cluster` and `ComputeInstance` creation:**

When a cluster or compute instance is created, the server validates that
sealed parameters are not provided by the user (or, if provided, match the
sealed default). The server resolves the full chain of inherited parameter
definitions before passing the information to the operator.

**Changes to the operator:**

The operator currently receives only the `Cluster` (or `ComputeInstance`)
object. It will now also need to receive information about the template
hierarchy, at a minimum the resolved Ansible role name and the effective
parameter definitions.

### Implementation Details/Notes/Constraints

**Parameter inheritance rules:**

A child template's `parameters` list contains only the parameters it wants to
override. Each entry must reference by `name` a parameter that exists in the
parent. The child can set `sealed` to `true` and provide a new `default`
value. Fields like `type`, `title`, and `description` are inherited from the
parent and should not be repeated in the child (the server will ignore them
if provided).

**Validation on template creation:**

When a new template is created the server verifies:

* If `parent` is set, the referenced template must exist and be visible to the
  creator.
* Each parameter in the child must reference a parameter that exists in the
  parent.
* A child cannot un-seal a parameter that was sealed in the parent.
* The `default` value of an overridden parameter must match the parameter's
  `type` as declared in the parent.

**Ansible role resolution algorithm:**

1. If the template has an explicit `ansible_role` field (or `osac/ansible_role`
   annotation), use that value.
2. Otherwise, walk up the inheritance chain to the root template and use the
   root template's name as the Ansible role.

**Effective view computation:**

When `effective=true` is requested, the server walks the inheritance chain
from root to leaf, merging parameter definitions at each level. Parameters in
child templates override fields of the same-named parameter from the parent.
The result is a flat list of all parameters with their effective `title`,
`description`, `type`, `default`, `sealed`, and `required` values.

For example, given a root template `fedora_vm` with parameters:

```json
[
  {
    "name": "version",
    "title": "Fedora version",
    "description": "Fedora major version, for example 43.",
    "type": "type.googleapis.com/google.protobuf.Int32Value",
    "required": false,
    "default": 42
  },
  {
    "name": "selinux",
    "title": "SELinux mode",
    "description": "SELinux mode: 'enabled', 'disabled' or 'permissive'.",
    "type": "type.googleapis.com/google.protobuf.StringValue",
    "required": false,
    "default": "enabled"
  }
]
```

And a child template `fedora_43_vm` with `parent` set to `fedora_vm` and
parameters:

```json
[
  {
    "name": "version",
    "sealed": true,
    "default": 43
  }
]
```

The effective view of `fedora_43_vm` would be:

```json
[
  {
    "name": "version",
    "title": "Fedora version",
    "description": "Fedora major version, for example 43.",
    "type": "type.googleapis.com/google.protobuf.Int32Value",
    "required": false,
    "sealed": true,
    "default": 43
  },
  {
    "name": "selinux",
    "title": "SELinux mode",
    "description": "SELinux mode: 'enabled', 'disabled' or 'permissive'.",
    "type": "type.googleapis.com/google.protobuf.StringValue",
    "required": false,
    "sealed": false,
    "default": "enabled"
  }
]
```

### Risks and Mitigations

**Deep inheritance chains.** Deeply nested template hierarchies could become
hard to understand and debug. This can be mitigated by documenting best
practices (e.g. keeping hierarchies shallow) and potentially enforcing a
maximum depth.

**Circular references.** The server must validate that the `parent` chain does
not contain cycles. This is a straightforward check at template creation time.

**Sealed parameter enforcement.** The server must consistently enforce sealed
parameters during cluster and compute instance creation. This is a validation
step in the existing creation flow.

**Operator changes.** The operator needs to receive template information in
addition to the cluster or compute instance object. The scope of this change
needs to be carefully defined to keep the interface clean.

### Drawbacks

The inheritance model adds complexity to the template system. Users and admins
need to understand the parent-child relationship and how parameter overrides
and sealing work. However, this complexity is justified by the flexibility it
provides and is preferable to introducing entirely new API types.

## Alternatives (Not Implemented)

**New `ClusterCatalogItem` and `ComputeInstanceCatalogItem` types.** An
earlier version of this proposal suggested introducing dedicated catalog item
types that would reference existing templates, pre-define parameter values,
and include an exclusive list of fields the user can set. Clusters and compute
instances would reference catalog items instead of templates. This approach
was rejected because it would leave the existing template types without a
clear purpose and add unnecessary API surface. The inheritance-based approach
achieves the same goals by extending the existing types.

**Annotations instead of a dedicated `ansible_role` field.** Using an
`osac/ansible_role` annotation instead of a first-class field would reduce
coupling between the API server and Ansible. This is a viable alternative
that may be reconsidered during implementation. Both mechanisms are described
in this proposal.

## Open Questions [optional]

1. Should there be a maximum depth for template inheritance chains?
2. Should the `ansible_role` override be a first-class field or an annotation?
   Using an annotation (`osac/ansible_role`) reduces coupling between the API
   server and Ansible, but a field is more discoverable.
3. What is the minimal set of template information that needs to be passed to
   the operator? Passing the full effective template representation is the most
   flexible option, but passing just the resolved Ansible role and effective
   parameters may suffice.

## Test Plan

**Note:** *Section not required until targeted at a release.*

The test strategy should cover:

* Unit tests for the inheritance resolution logic (parameter merging, sealed
  enforcement, cycle detection).
* Unit tests for the effective view computation.
* Integration tests for template CRUD operations with parent references.
* Integration tests for cluster and compute instance creation with inherited
  templates, verifying sealed parameter enforcement.
* End-to-end tests validating the full workflow from template creation through
  resource provisioning.

## Graduation Criteria

**Note:** *Section not required until targeted at a release.*

To be defined during implementation planning.

## Upgrade / Downgrade Strategy

The `parent`, `sealed`, and `ansible_role` fields are additive. Existing
templates without a parent continue to work as root templates. No migration is
needed for existing clusters or compute instances.

On downgrade, templates with inheritance would lose their parent relationship,
but since the fields are simply ignored by older versions, no data is lost.
Clusters already created from child templates continue to function because the
provisioning information was resolved at creation time.

## Version Skew Strategy

During an upgrade, older components that are unaware of template inheritance
will treat all templates as root templates. This is safe because:

* The API server resolves the effective template at cluster/compute instance
  creation time. Older operators receiving resolved parameters will work
  correctly.
* The new `parent`, `sealed`, and `ansible_role` fields are ignored by
  components that do not understand them.

## Support Procedures

* If template inheritance resolution fails, the API server will return an
  error on the template get/list endpoint (with `effective=true`) or during
  cluster/compute instance creation. The error message will identify the
  broken link in the inheritance chain.
* Admins can inspect the raw template (without `effective=true`) to see the
  direct parent reference and parameter overrides, making it straightforward
  to diagnose misconfigured inheritance.

## Infrastructure Needed [optional]

No new infrastructure is needed. The changes are to the existing API server,
operator, and authorization configuration.
