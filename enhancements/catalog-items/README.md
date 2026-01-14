---
title: catalog-items
authors:
  - mhrivnak
creation-date: 2026-01-12
last-updated: 2026-01-17
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
see-also:
replaces:
superseded-by:
---

# Published Templates

## Summary

Today there is a 1:1 mapping between templates and ansible roles. This document
proposes an API that enables a single ansible role to be used as the basis for
multiple catalog items that are published for users. That enables a CSP to
define a small number of ansible roles based on their infrastructure and use
case needs, but expose many variations of curated catalog items to users.

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

* As a Cloud Provider Admin, I want to publish multiple templates that are similar to each other.
* As a Cloud Provider Admin, I want to publish multiple templates without having to create a new ansible role.
* As a Cloud Provider Admin, I want to offer templates to my users that pre-define the values for certain fields.
* As a Cloud Provider Admin, I want to offer templates to my users that prevent them from setting certain fields.

* As a Tenant Admin, I want to offer templates to my users that pre-define the values for certain fields.
* As a Tenant Admin, I want to offer templates to my users that prevent them from setting certain fields.

### Goals

* Enable provider and tenant admins to make templates available for use without requiring new ansible roles.

### Non-Goals

* Enable the use of templates that don't use ansible at all.

## Proposal

ComputeInstanceTemplate and ClusterTemplate stay the same. They contiue to be
auto-populated by the system based on discovered ansible roles.

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

The fulfillment-cli will need to be updated to use the new CatalogItem API.

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

Add:
* ClusterCatalogItem
* ComputeInstanceCatalogItem

Change:
* Cluster references a ClusterCatalogItem instead of a ClusterTemplate
* ComputeInstance references a ComputeInstanceCatalogItem instead of a ComputeInstanceTemplate


### Implementation Details/Notes/Constraints

TO DO from here down

What are some important details that didn't come across above in the
**Proposal**? Go in to as much detail as necessary here. This might be
a good place to talk about core concepts and how they relate. While it is useful
to go into the details of the code changes required, it is not necessary to show
how the code will be rewritten in the enhancement.

### Risks and Mitigations

What are the risks of this proposal and how do we mitigate. Think broadly. For
example, consider both security and how this will impact the larger OKD
ecosystem.

How will security be reviewed and by whom?

How will UX be reviewed and by whom?

Consider including folks that also work outside your immediate sub-project.

### Drawbacks

The idea is to find the best form of an argument why this enhancement should
_not_ be implemented.

What trade-offs (technical/efficiency cost, user experience, flexibility,
supportability, etc) must be made in order to implement this? What are the reasons
we might not want to undertake this proposal, and how do we overcome them?

Does this proposal implement a behavior that's new/unique/novel? Is it poorly
aligned with existing user expectations?  Will it be a significant maintenance
burden?  Is it likely to be superceded by something else in the near future?

## Alternatives (Not Implemented)

Similar to the `Drawbacks` section the `Alternatives` section is used
to highlight and record other possible approaches to delivering the
value proposed by an enhancement, including especially information
about why the alternative was not selected.

## Open Questions [optional]

This is where to call out areas of the design that require closure before deciding
to implement the design.  For instance,
 > 1. This requires exposing previously private resources which contain sensitive
  information.  Can we do this?

## Test Plan

**Note:** *Section not required until targeted at a release.*

Consider the following in developing a test plan for this enhancement:
- Will there be e2e and integration tests, in addition to unit tests?
- How will it be tested in isolation vs with other components?
- What additional testing is necessary to support managed OpenShift service-based offerings?

No need to outline all of the test cases, just the general strategy. Anything
that would count as tricky in the implementation and anything particularly
challenging to test should be called out.

All code is expected to have adequate tests (eventually with coverage
expectations).

## Graduation Criteria

**Note:** *Section not required until targeted at a release.*

Define graduation milestones.

These may be defined in terms of API maturity, or as something else. Initial proposal
should keep this high-level with a focus on what signals will be looked at to
determine graduation.

Consider the following in developing the graduation criteria for this
enhancement:

- Maturity levels
  - [`alpha`, `beta`, `stable` in upstream Kubernetes][maturity-levels]
  - `Dev Preview`, `Tech Preview`, `GA` in OpenShift
- [Deprecation policy][deprecation-policy]

Clearly define what graduation means by either linking to the [API doc definition](https://kubernetes.io/docs/concepts/overview/kubernetes-api/#api-versioning),
or by redefining what graduation means.

In general, we try to use the same stages (alpha, beta, GA), regardless how the functionality is accessed.

[maturity-levels]: https://git.k8s.io/community/contributors/devel/sig-architecture/api_changes.md#alpha-beta-and-stable-versions
[deprecation-policy]: https://kubernetes.io/docs/reference/using-api/deprecation-policy/

**If this is a user facing change requiring new or updated documentation in [openshift-docs](https://github.com/openshift/openshift-docs/),
please be sure to include in the graduation criteria.**

**Examples**: These are generalized examples to consider, in addition
to the aforementioned [maturity levels][maturity-levels].

### Removing a deprecated feature

- Announce deprecation and support policy of the existing feature
- Deprecate the feature

## Upgrade / Downgrade Strategy

If applicable, how will the component be upgraded and downgraded? Make sure this
is in the test plan.

Consider the following in developing an upgrade/downgrade strategy for this
enhancement:
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to keep previous behavior?
- What changes (in invocations, configurations, API use, etc.) is an existing
  cluster required to make on upgrade in order to make use of the enhancement?

Upgrade expectations:
- Each component should remain available for user requests and
  workloads during upgrades. Ensure the components leverage best practices in handling [voluntary
  disruption](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/). Any exception to
  this should be identified and discussed here.
- Micro version upgrades - users should be able to skip forward versions within a
  minor release stream without being required to pass through intermediate
  versions - i.e. `x.y.N->x.y.N+2` should work without requiring `x.y.N->x.y.N+1`
  as an intermediate step.
- Minor version upgrades - you only need to support `x.N->x.N+1` upgrade
  steps. So, for example, it is acceptable to require a user running 4.3 to
  upgrade to 4.5 with a `4.3->4.4` step followed by a `4.4->4.5` step.
- While an upgrade is in progress, new component versions should
  continue to operate correctly in concert with older component
  versions (aka "version skew"). For example, if a node is down, and
  an operator is rolling out a daemonset, the old and new daemonset
  pods must continue to work correctly even while the cluster remains
  in this partially upgraded state for some time.

Downgrade expectations:
- If an `N->N+1` upgrade fails mid-way through, or if the `N+1` cluster is
  misbehaving, it should be possible for the user to rollback to `N`. It is
  acceptable to require some documented manual steps in order to fully restore
  the downgraded cluster to its previous state. Examples of acceptable steps
  include:
  - Deleting any CVO-managed resources added by the new version. The
    CVO does not currently delete resources that no longer exist in
    the target version.

## Version Skew Strategy

How will the component handle version skew with other components?
What are the guarantees? Make sure this is in the test plan.

Consider the following in developing a version skew strategy for this
enhancement:
- During an upgrade, we will always have skew among components, how will this impact your work?
- Does this enhancement involve coordinating behavior in the control plane and
  in the kubelet? How does an n-2 kubelet without this feature available behave
  when this feature is used?
- Will any other components on the node change? For example, changes to CSI, CRI
  or CNI may require updating that component before the kubelet.

## Support Procedures

Describe how to
- detect the failure modes in a support situation, describe possible symptoms (events, metrics,
  alerts, which log output in which component)

  Examples:
  - If the webhook is not running, kube-apiserver logs will show errors like "failed to call admission webhook xyz".
  - Operator X will degrade with message "Failed to launch webhook server" and reason "WehhookServerFailed".
  - The metric `webhook_admission_duration_seconds("openpolicyagent-admission", "mutating", "put", "false")`
    will show >1s latency and alert `WebhookAdmissionLatencyHigh` will fire.

- disable the API extension (e.g. remove MutatingWebhookConfiguration `xyz`, remove APIService `foo`)

  - What consequences does it have on the cluster health?

    Examples:
    - Garbage collection in kube-controller-manager will stop working.
    - Quota will be wrongly computed.
    - Disabling/removing the CRD is not possible without removing the CR instances. Customer will lose data.
      Disabling the conversion webhook will break garbage collection.

  - What consequences does it have on existing, running workloads?

    Examples:
    - New namespaces won't get the finalizer "xyz" and hence might leak resource X
      when deleted.
    - SDN pod-to-pod routing will stop updating, potentially breaking pod-to-pod
      communication after some minutes.

  - What consequences does it have for newly created workloads?

    Examples:
    - New pods in namespace with Istio support will not get sidecars injected, breaking
      their networking.

- Does functionality fail gracefully and will work resume when re-enabled without risking
  consistency?

  Examples:
  - The mutating admission webhook "xyz" has FailPolicy=Ignore and hence
    will not block the creation or updates on objects when it fails. When the
    webhook comes back online, there is a controller reconciling all objects, applying
    labels that were not applied during admission webhook downtime.
  - Namespaces deletion will not delete all objects in etcd, leading to zombie
    objects when another namespace with the same name is created.

## Infrastructure Needed [optional]

Use this section if you need things from the project. Examples include a new
subproject, repos requested, github details, and/or testing infrastructure.
