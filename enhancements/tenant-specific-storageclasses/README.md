---
title: tenant-specific-storageclasses
authors:
  - mhrivnak
creation-date: 2026-02-15
last-updated: 2026-02-15
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
  - TBD
see-also:
replaces:
superseded-by:
---

# Tenant-specific StorageClasses

## Summary

When creating VMs or other cloud-native assets for tenants, it can be desirable
to use storage that has been configured for that tenant. Many storage solutions
have the ability to dedicate a portion of storage for a specific tenant, which
can enable quota enforcement, QoS, and encryption. This proposal uses labels on
StorageClasses to identify which StorageClasses in a cluster correspond to a
particular tenant. 

## Motivation

CSPs have the ability to configure dedicated storage per tenant in their
storage solution, but there is not a standardized way for OSAC to discover and
use that storage on a per-tenant basis.

### User Stories

As a CSP Admin, I want to offer per-tenant storage configuration that could
include encryption, QoS and quota enforcement.

As a CSP Admin, I want a source of truth for designating that a StorageClass in
a CSP-owned cluster corresponds to a specific tenant.

As a tenant, I want the storage I use to be isolated from other tenants.

As an OSAC template author, I want the ability to use storage that is specific
to the tenant for whom I am provisioning.

### Goals

* Enable the use of tenant-specific storage when provisioning cloud-native assets into a cluster owned by the CSP.
* Provide a source of truth in the data model for how to know which storage class corresponds to which tenant.

### Non-Goals

* Create new management capabilities for storage.
* Establish a process for differentiating multiple classes of storage (speed, redundancy, etc.) for individual tenants.

## Proposal

The CSP Admin will continue to be responsible for configuring their storage
solution for specific tenants and for creating the corresponding StorageClasses
in clusters that should use such storage.

When creating a StorageClass, the CSP Admin will add a label whose value
identifies the tenant who should exclusively have access to that storage.

### Workflow Description

When a CSP Admin onboards a new tenant, they will configure dedicated storage in
their chosen storage solution. (presumably this can be automated)

The CSP Admin will then create a corresponding StorageClass in each cluster
that needs to provision storage on behalf of that tenant. The StorageClass will
include the label proposed in this document.

When OSAC provisions resources for that tenant, it will find the correct
StorageClass to use by searching for the label with the tenant's identifier.

### API Extensions

A label with key `osac.openshift.com/tenant-id` will be used to designate the
tenant to whom a StorageClass belongs.

```
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: netapp-tenant123
  labels:
    osac.openshift.com/tenant-id: tenant123
provisioner: csi.trident.netapp.io
reclaimPolicy: Delete
allowVolumeExpansion: true
parameters:
  backendType: "ontap-nas"
  media: "ssd"
  provisioningType: "thin"
```

### Implementation Details/Notes/Constraints

Ansible roles that implement templates will need the ability to determine which
StorageClass to use. Either they can perform a normal query from ansible, or
the controller could do that up-front and inject the chosen StorageClass as
context.

### Risks and Mitigations

It is essential that a tenant not be able to access storage that does not
belong to them. Thus tenants must not have any ability to affect the part of
the data model designates which storage is theirs. Storing it on StorageClasses
accomplishes that.

### Drawbacks


## Alternatives (Not Implemented)

We could store a list of StorageClasses on the Tenant CRD. That would add a
level of indirection and de-normalization that does not add value.

Some CSPs may be happy using a single default StorageClass to provision VMs and
other CNAs for their tenants. For them, no change is required. But that won't
meet the needs of enough use cases.

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
