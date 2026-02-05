---
title: vm-api-fields
authors:
  - mhrivnak
creation-date: 2026-01-27
last-updated: 2026-02-05
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
  - TBD
see-also:
replaces:
superseded-by:
---

# New API Fields for VMs

## Summary

The API for creating VMs leaves the definition of input fields up to the author
of each template. This change adds several standardized fields that are
available for all VM templates to use.

## Motivation

By defining specific fields with standard names, the project can:
* measure utilization
* collect and preserve specific evidence for compliance
* apply quotas
* improve usability by giving users and automation a standard set of fields to reuse
* give template authors guidance on what fields should be accounted for and are commonly used

### User Stories

As a Cloud Admin, I want guidance on what fields should be included in VM templates.

As a Tenant User, I want a standard set of fields to use when deploying VMs from templates.

### Goals

* define specific fields with names and descriptions that should be added to the VM API

### Non-Goals

* add fields to other template APIs
* replace the ability to pass additional input values that are defined by the template

## Proposal

The fulfillment API will add standardized template fields to its ComputeInstance
spec, and the corresponding CRD will add them as well. All values are optional.
Values will be passed to the selected template.

### Workflow Description

Users of the compute instance API will be able to start using these new fields
in their existing workflow.

Template authors will be able to start using these fields in their templates.

### API Extensions

CompueInstance in the Fulfillment API will add these fields to its spec:

| Name | Type | Mutable | Description |
| --- | --- | --- | --- |
| Image.SourceType | String | no | One of the source types from the kubevirt [DataVolumeSource](https://kubevirt.io/api-reference/main/definitions.html#_v1beta1_datavolumesource) API. "registry" will be the only supported value for now. |
| Image.SourceRef | String | no | Image reference in the context of the SourceType. For type "registry", this should be a standard OCI image reference. |
| Cores | Int32 | no | Number of CPU Cores |
| MemoryGiB | Int32 | no | Memory in GiB |
| SSHKey | String | no | SSH Key that should have access to the VM |
| BootDisk | Disk | no | Details for the boot disk |
| AdditionalDisks | repeated Disk | no | Array of details for additional disks that should be created and attached |
| RunStrategy | String | yes | "Always" or "Halted". This is a subset of kubevirt's [runStrategy](https://kubevirt.io/user-guide/compute/run_strategies/) values. |
| UserDataSecretRef | String or LocalObjectReference | no | In fulfillment-API, a string. In CRD, a reference to a Secret in the same namespace that contains user-data. |

The Disk struct will include:

| Name | Type | Mutable | Description |
| --- | --- | --- | --- |
| SizeGiB | Int32 | no | Size in GiB |

The CRD will look like this:

```
apiVersion: cloudkit.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: vm-example
  namespace: tenant1
  labels:
    osac.openshift.io/tenant-id: tenant1
spec:
  templateID: "rhel10-desktop"
  image:
    sourceType: registry
    sourceRef: mylocalregistry.mydomain.io/redhat/rhel10-desktop:latest
  cores: 8
  memoryGiB: 32
  bootDisk:
    sizeGiB: 50
  additionalDisks:
    - sizeGiB: 250
  runStrategy: Always
  userDataSecretRef:
    name: vm-example-user-data
```

### Implementation Details/Notes/Constraints


### Risks and Mitigations

#### Losing Flexibility

Specific API choices could limit our ability to add additional capabilities or
options in the future.

We'll mitigate that by:
* following API best practices, like modeling the Disk struct to accept more fields in the future
* making these fields optional
* continuing to allow templates to define their own additional fields that have meaning to their context
* taking inspiration from the KubeVirt API and following its established conventions

### Drawbacks

None

## Alternatives (Not Implemented)

We could try to surface most of the kubevirt API and just "get out of the way".
However, that would undermine the value of having templates. Templates enable
the CSP to utilize the full capabilities of their infrastructure to compose a
valuable set of curated offerings, and then make their offerings available with
a limited set of tenant-facing choices that are focused on the use case and
prevent the tenant from overstepping their boundaries in terms of resource
utilization or isolation.

## Open Questions

### How to attach pre-existing volumes?

There may be a use case for attaching one or more pre-existing volumes. That
would require a system to exist that enables tenants to have volumes independely
of VMs or clusters. Such system has not yet been designed.

A likely solution would be to add a new field where pre-existing volumes can be
listed. Something like:

```
existingVolumes:
  - type: nfs
  - ref: ...
  - accessMode: RO
```

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
