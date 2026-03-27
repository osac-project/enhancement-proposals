---
title: tenant-storage-tiers
authors:
  - akshaynadkarni
creation-date: 2026-03-26
last-updated: 2026-03-26
tracking-link:
  - TBD
see-also:
  - "/enhancements/tenant-specific-storageclasses"
replaces:
superseded-by:
---

# Tenant Storage Tiers

## Summary

This proposal extends the tenant-specific StorageClass mechanism introduced in
[tenant-specific-storageclasses](/enhancements/tenant-specific-storageclasses) to
support multiple storage tiers per tenant. A CSP may need to offer different
classes of storage to each tenant, for example fast NVMe storage for databases
alongside slower HDD storage for archival. This proposal adds an optional
`osac.openshift.io/storage-tier` label to StorageClasses, evolves
`tenant.status.storageClass` (string) to `tenant.status.storageClasses` (list),
and updates the `tenant_storage_class` Ansible role to accept a storage tier
parameter so that consumers can select the appropriate StorageClass for a given
workload.

This proposal focuses on the infrastructure layer: tier labeling, resolution,
and selection. How the tier value reaches the Ansible role (whether from a VM
template or a user-facing API field) is a consumption pattern that this proposal
describes at a high level but does not prescribe.

## Motivation

The current implementation supports exactly one StorageClass per tenant (or a
shared Default). As OSAC matures, CSPs will need to differentiate storage
offerings within a single tenant. For example, a tenant running a database
workload needs fast SSD-backed storage, while the same tenant's archival VMs
can use cheaper, slower storage. Without storage tiers, CSPs would need to
either over-provision expensive storage for all workloads or maintain manual
workarounds outside of OSAC.

### User Stories

As a **CSP Admin**, I want to configure multiple StorageClasses for a single
tenant with different performance characteristics (fast, standard, archival) so
that tenants can run diverse workloads at appropriate cost points.

As a **CSP Admin**, I want to provide shared Default StorageClasses at different
tiers so that tenants without dedicated storage still have access to tiered
storage options.

As a **Tenant Admin**, I want to create VM templates that automatically select
the right storage tier for their workload type (e.g., a database template uses
fast storage, an archival template uses standard storage) so that my users do
not need to think about storage infrastructure.

As a **CSP Admin**, I want the system to be backward compatible so that existing
single-StorageClass-per-tenant configurations continue working without any
changes.

### Goals

* Enable CSPs to offer multiple storage tiers per tenant using labels on
  StorageClasses.
* Expose all resolved storage tiers in the Tenant status so that any consumer
  (VM templates, Ansible roles, future API fields) can select the appropriate
  StorageClass by tier.
* Maintain full backward compatibility with the existing single StorageClass
  per tenant model.
* Keep the Tenant controller as the single source of truth for StorageClass
  resolution. Consumers (Ansible, CI controller) read from Tenant status, not
  from StorageClass labels directly.

### Non-Goals

* Storage quota enforcement per tier. Quota is a separate concern that may be
  addressed by a future enhancement.
* Automated StorageClass provisioning. The CSP Admin remains responsible for
  creating StorageClasses and their backing storage.
* Dynamic tier negotiation. Tiers are static labels; the CSP defines what tiers
  are available.
* Prescribing the mechanism by which the tier value reaches the provisioning
  layer. This proposal builds the infrastructure; the consumption pattern
  (template-driven, user-facing, or hybrid) is discussed but not mandated.

## Proposal

This proposal adds a second, optional label axis to the StorageClass labeling
convention. The existing `osac.openshift.io/tenant` label identifies *which
tenant* owns a StorageClass. The new `osac.openshift.io/storage-tier` label
identifies *what kind* of storage it provides.

Each StorageClass is identified by a composite key: `(tenant, storage-tier)`.
The `tenant` axis retains its existing fallback behavior (tenant-specific, then
shared `Default`). The `storage-tier` axis is an exact match that defaults to
`Default` when absent.

The `Default` sentinel value follows the same convention established for the
`osac.openshift.io/tenant` label: real values are lowercase (`fast`,
`standard`, `archival`), and the sentinel/fallback value is capitalized
(`Default`). This keeps the labeling convention predictable across both axes.

### Workflow Description

#### Personas

| Persona | Role | Relevant actions |
|---|---|---|
| **CSP Admin** | Cloud Provider Admin (infrastructure) | Creates StorageClasses with tenant and tier labels |
| **Tenant Admin** | Tenant organization administrator | Creates and configures VM templates for their users |
| **Tenant User** | End user within a tenant organization | Creates ComputeInstances using available templates |

#### Workflow 1: CSP Admin configures tiered storage for a tenant

**Actors:** CSP Admin

**Starting state:** A tenant `tenant-acme` exists. The CSP has provisioned
fast and standard storage pools in their storage solution.

1. The CSP Admin creates two StorageClasses on the virtualization cluster,
   each labeled with the tenant and the appropriate tier:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-acme-fast
  labels:
    osac.openshift.io/tenant: tenant-acme
    osac.openshift.io/storage-tier: fast
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: acme-ssd-pool
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-acme-standard
  labels:
    osac.openshift.io/tenant: tenant-acme
    osac.openshift.io/storage-tier: standard
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: acme-hdd-pool
```

2. The Tenant controller detects the new StorageClasses via its watch,
   reconciles, and populates `tenant.status.storageClasses` with both
   resolved entries.

3. The Tenant phase remains `Ready` because at least one StorageClass is
   available.

**Expected result:** `tenant-acme` has two resolved storage tiers in its
status. VM templates and provisioning roles can now select either `fast` or
`standard` storage.

#### Workflow 2: Backward-compatible single StorageClass (no storage-tier label)

**Actors:** CSP Admin

**Starting state:** The CSP has a single StorageClass per tenant, labeled with
only `osac.openshift.io/tenant` (no `storage-tier` label). This is the
configuration that exists today.

1. The existing StorageClass has no `osac.openshift.io/storage-tier` label:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-acme
  labels:
    osac.openshift.io/tenant: tenant-acme
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: acme-pool
```

2. The Tenant controller treats the missing `storage-tier` label as
   `storage-tier: Default`.

3. `tenant.status.storageClasses` contains a single entry with
   `storageTier: "Default"`. The backward-compatible
   `tenant.status.storageClass` field also contains the StorageClass name.

**Expected result:** The tenant continues to work exactly as before. No
configuration changes are required. Consumers that do not specify a tier
automatically use the `Default` tier.

#### Workflow 3: CSP Admin configures shared Default storage tiers

**Actors:** CSP Admin

**Starting state:** The CSP wants to provide shared storage tiers that any
tenant without a dedicated StorageClass can use.

1. The CSP Admin creates shared Default StorageClasses with tier labels:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-shared-fast
  labels:
    osac.openshift.io/tenant: Default
    osac.openshift.io/storage-tier: fast
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: shared-ssd-pool
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-shared-standard
  labels:
    osac.openshift.io/tenant: Default
    osac.openshift.io/storage-tier: standard
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: shared-hdd-pool
```

2. For tenants that have no dedicated StorageClass for a given tier, the
   Tenant controller falls back to the shared Default StorageClass for that
   tier. The fallback is applied independently per tier.

**Expected result:** Tenants without dedicated storage still have access to
tiered storage options through the shared Defaults.

**Note:** A shared Default StorageClass without a `storage-tier` label is
treated as `(tenant: Default, storage-tier: Default)`, following the same
rule as Workflow 2. This is the configuration that exists today and continues
to work without changes.

#### Workflow 4: Mixed tenant-specific and shared Default tiers

**Actors:** CSP Admin

**Starting state:** The CSP has a shared Default StorageClass (no tier label)
for all tenants, and has configured tenant-specific `fast` and `slow`
StorageClasses for `tenant-acme`.

StorageClasses on the cluster:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-shared-default
  labels:
    osac.openshift.io/tenant: Default
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: shared-pool
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-acme-fast
  labels:
    osac.openshift.io/tenant: tenant-acme
    osac.openshift.io/storage-tier: fast
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: acme-ssd-pool
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-acme-slow
  labels:
    osac.openshift.io/tenant: tenant-acme
    osac.openshift.io/storage-tier: slow
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: acme-hdd-pool
```

1. The Tenant controller resolves each tier independently for `tenant-acme`:
   - `fast`: tenant-specific SC found (`ceph-acme-fast`).
   - `slow`: tenant-specific SC found (`ceph-acme-slow`).
   - `Default`: no tenant-specific SC without a tier label. Falls back to the
     shared Default SC (`ceph-shared-default`).

2. The resulting Tenant status:

```yaml
status:
  phase: Ready
  storageClass: "ceph-shared-default"
  storageClasses:
    - storageClassName: "ceph-shared-default"
      storageTier: "Default"
    - storageClassName: "ceph-acme-fast"
      storageTier: "fast"
    - storageClassName: "ceph-acme-slow"
      storageTier: "slow"
```

**Expected result:** `tenant-acme` has three resolved tiers. The `fast` and
`slow` tiers use tenant-specific StorageClasses. The `Default` tier falls back
to the shared Default StorageClass. `status.storageClass` (singular) contains
the shared Default SC name, so backward-compatible consumers continue to work.

#### Workflow 5: Template-driven tier selection during provisioning (Strategy A)

**Actors:** Tenant Admin (creates the template), Tenant User (creates the CI)

**Starting state:** `tenant-acme` has `fast` and `standard` tiers resolved.
The Tenant Admin has created a `database_vm` template that is configured to
use `fast` storage for boot disks.

1. The Tenant User creates a ComputeInstance using the database template:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: db-server-01
spec:
  templateID: osac.templates.database_vm
  cores: 4
  memoryGiB: 16
  bootDisk:
    sizeGiB: 100
  image:
    sourceType: registry
    sourceRef: "quay.io/containerdisks/fedora:latest"
  runStrategy: Always
```

2. The CI controller triggers provisioning. The `tenant_storage_class` Ansible
   role receives the full `tenant.status.storageClasses` list.

3. The `database_vm` template role requests tier `fast` from the
   `tenant_storage_class` role, which resolves it to `ceph-acme-fast`.

4. The template creates the DataVolume with `storageClassName: ceph-acme-fast`.

**Expected result:** The user did not need to specify a storage tier. The
template knew which tier to use for a database workload. The
`tenant_storage_class` role resolved the tier to the correct StorageClass.

#### Workflow 6: Default tier selection (no tier specified)

**Actors:** Tenant User

**Starting state:** `tenant-acme` has at least a `Default` tier resolved.

1. The Tenant User creates a ComputeInstance using a generic template that does
   not specify a storage tier:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: web-server-01
spec:
  templateID: osac.templates.ocp_virt_vm
  cores: 2
  memoryGiB: 4
  bootDisk:
    sizeGiB: 20
  image:
    sourceType: registry
    sourceRef: "quay.io/containerdisks/fedora:latest"
  runStrategy: Always
```

2. The `tenant_storage_class` role defaults to tier `"Default"` when no tier
   is specified and resolves it from `tenant.status.storageClasses`.

**Expected result:** All disks use the `Default` tier StorageClass. This is
identical to the current single-StorageClass behavior.

#### Workflow 7: Requested storage tier is not available

**Actors:** Tenant User (indirectly, via a template that requests an
unavailable tier)

**Starting state:** `tenant-acme` has only `Default` and `standard` tiers.
A template requests `fast` storage.

1. The `tenant_storage_class` role attempts to resolve tier `fast` from
   `tenant.status.storageClasses` but finds no matching entry.

2. The role fails with a descriptive error:

   > Storage tier "fast" is not available for tenant "tenant-acme".
   > Available tiers: Default, standard.

3. The ComputeInstance transitions to `Failed` with a descriptive message.

**Expected result:** The provisioning fails with a clear error identifying the
missing tier and listing the available alternatives.

### API Extensions

#### StorageClass labels

A new optional label is added alongside the existing tenant label:

| Label key | Required | Values | Default if absent |
|---|---|---|---|
| `osac.openshift.io/tenant` | Yes | `<tenantName>` or `Default` | N/A (required) |
| `osac.openshift.io/storage-tier` | No | Any lowercase alphanumeric string (e.g., `fast`, `standard`, `archival`, `nvme`) | `Default` |

Both label axes use the same sentinel convention: real values are lowercase,
and the sentinel/fallback value is `Default` (capitalized). This is consistent
with the `osac.openshift.io/tenant: Default` convention established in the
predecessor proposal, where capitalization prevents collisions with actual
resource names (which are always lowercase in Kubernetes).

Storage tier values are freeform. OSAC does not define a fixed vocabulary.
CSPs choose tier names that make sense for their storage offering. Tier values
must conform to Kubernetes label value syntax: alphanumeric, dashes, dots, and
underscores, up to 63 characters, beginning and ending with an alphanumeric
character.

**Example: Tenant-specific StorageClass with a storage tier**

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: netapp-tenant123-fast
  labels:
    osac.openshift.io/tenant: tenant123
    osac.openshift.io/storage-tier: fast
provisioner: csi.trident.netapp.io
parameters:
  backendType: "ontap-nas"
  media: "ssd"
```

**Example: Shared Default StorageClass with a storage tier**

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: netapp-shared-standard
  labels:
    osac.openshift.io/tenant: Default
    osac.openshift.io/storage-tier: standard
provisioner: csi.trident.netapp.io
parameters:
  backendType: "ontap-nas"
  media: "hdd"
```

**Example: StorageClass without a storage-tier label (treated as `Default`)**

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: netapp-tenant123
  labels:
    osac.openshift.io/tenant: tenant123
provisioner: csi.trident.netapp.io
parameters:
  backendType: "ontap-nas"
```

#### Tenant CRD status changes

The singular `status.storageClass` field (string) is replaced by a
`status.storageClasses` list that captures all resolved StorageClass mappings
for the tenant:

```yaml
status:
  phase: Ready
  namespace: "tenant-acme-ns"
  storageClass: "ceph-acme-default"       # Default tier (= storageClasses entry with storageTier: Default)
  storageClasses:
    - storageClassName: "ceph-acme-default"    # tenant-specific
      storageTier: "Default"
    - storageClassName: "ceph-acme-fast"       # tenant-specific
      storageTier: "fast"
    - storageClassName: "ceph-acme-standard"   # tenant-specific
      storageTier: "standard"
    - storageClassName: "ceph-shared-archival" # resolved from shared Default fallback
      storageTier: "archival"
```

Each entry in `storageClasses` is either a tenant-specific StorageClass or a
shared Default StorageClass resolved via fallback. A tenant only sees its own
StorageClasses and the shared Defaults; it never sees StorageClasses belonging
to other tenants.

Go type:

```go
type ResolvedStorageClass struct {
    // StorageClassName is the name of the resolved StorageClass
    StorageClassName string `json:"storageClassName"`

    // StorageTier is the storage tier this StorageClass provides.
    // Set to "Default" when the StorageClass has no
    // osac.openshift.io/storage-tier label.
    StorageTier string `json:"storageTier"`
}
```

The `tenant` value is NOT included in `ResolvedStorageClass` because the Tenant
CR itself is the tenant context. The tenant-to-Default fallback has already been
applied by the time the resolved list is populated.

**Backward compatibility:** The existing `status.storageClass` (string) field
is kept as a convenience accessor for the `Default` tier. When a StorageClass
resolves with tier `Default` (either explicitly labeled or with no tier label),
`status.storageClass` contains its name. This allows consumers that are not yet
tier-aware to continue working without changes.

If no `Default` tier resolves for a tenant (neither a tenant-specific SC
without a tier label, nor a shared Default SC without a tier label),
`status.storageClass` will be empty, even if other tiers (`fast`, `standard`)
resolved successfully. Consumers that are not tier-aware would fail in this
case, which is the correct signal: the CSP must configure a `Default` tier
(tenant-specific or shared) for backward compatibility. This edge case is
related to Open Question #1 (whether the Tenant should require a `Default`
tier to be `Ready`).

### Implementation Details/Notes/Constraints

#### Resolution algorithm

The Tenant controller resolves **all available tier combinations** for each
tenant at reconciliation time. For each distinct `storage-tier` value `T` found
across all StorageClasses labeled with `osac.openshift.io/tenant`:

1. Find StorageClasses labeled `osac.openshift.io/tenant=<tenantName>` AND
   `osac.openshift.io/storage-tier=T` (or no `storage-tier` label when
   `T` is `Default`).
   - Exactly one: use it.
   - More than one: duplicate error for this tier (same as the existing
     behavior for the single-tier case).
   - None: proceed to step 2.

2. Find StorageClasses labeled `osac.openshift.io/tenant=Default` AND
   `osac.openshift.io/storage-tier=T` (or no `storage-tier` label when
   `T` is `Default`).
   - Exactly one: use it (shared Default fallback for this tier).
   - More than one: duplicate error for this tier.
   - None: tier `T` is not available for this tenant (not an error at
     the Tenant level; individual provisioning requests that ask for this
     tier will fail at the Ansible role level).

The resolved list is stored in `tenant.status.storageClasses`. Downstream
consumers never implement fallback logic; they look up the requested tier in
the pre-resolved list.

#### Tier selection at provisioning time

The `tenant_storage_class` Ansible role is the selection interface. It accepts
a `storage_tier` input parameter (defaulting to `"Default"`) and resolves it
against the tenant's `status.storageClasses` list.

**Who provides the `storage_tier` value** is a separate concern from how the
role resolves it. This proposal identifies three strategies:

**Strategy A: Template-driven (recommended initial approach).** The VM template
role (e.g., `osac.templates.database_vm`) hardcodes which tier each disk needs.
The template author chooses the tier based on the workload type. The tenant
user selects a template when creating a ComputeInstance and does not need to
know about storage tiers.

```yaml
# Inside osac.templates.database_vm/tasks/create.yaml
- name: Resolve boot disk StorageClass
  ansible.builtin.include_role:
    name: osac.service.tenant_storage_class
  vars:
    tenant_storage_class_storage_tier: "fast"
```

**Strategy B: User-facing DiskSpec field.** A `storageTier` field is added to
the ComputeInstance `DiskSpec`. The CI controller or Ansible role reads the
field from the CI spec and passes it to the `tenant_storage_class` role. This
gives users direct control over storage selection but exposes infrastructure
details.

**Strategy C: Hybrid.** The template sets a default tier, and a user-facing
field can override it. This provides flexibility while keeping the common case
simple.

All three strategies use the same underlying infrastructure: the
`tenant_storage_class` role receives a `storage_tier` parameter and resolves it
from `tenant.status.storageClasses`. The initial implementation targets
Strategy A.

#### StorageClassReady condition updates

The existing `StorageClassReady` condition is extended:

- `Ready` requires at least one tier to resolve successfully.
- Duplicate detection applies per tier. Two StorageClasses for `(tenantX,
  fast)` produces a `MultipleFound` condition, but does not affect
  `(tenantX, standard)`.
- The condition message lists which tiers resolved successfully and which
  had errors.

#### Ansible role changes

The `tenant_storage_class` role currently reads `tenant.status.storageClass`
(a single string) and sets `tenant_storage_class_name`. It will be updated to:

1. Read `tenant.status.storageClasses` (the resolved list).
2. Accept a `tenant_storage_class_storage_tier` input parameter (defaulting to
   `"Default"`).
3. Find the entry in the list whose `storageTier` matches the request.
4. Set `tenant_storage_class_name` to the matching `storageClassName`.
5. Fail with a descriptive error if the requested tier is not in the list,
   including the available tiers.

For backward compatibility, if `tenant.status.storageClasses` is not present
(older Tenant controller), the role falls back to reading
`tenant.status.storageClass` and treats it as the `Default` tier.

#### Changes per repository

**osac-operator:**

- Evolve `getTenantStorageClass()` to `getTenantStorageClasses()`: group
  StorageClasses by `(tenant, storage-tier)` combination and resolve each
  independently.
- Add `ResolvedStorageClass` Go type to the Tenant CRD API.
- Add `tenant.status.storageClasses` (list of `ResolvedStorageClass`). Keep
  `status.storageClass` as a convenience field for the `Default` tier.
- Update `StorageClassReady` condition with per-tier resolution detail.
- Update unit tests for multi-tier scenarios (multiple tiers resolved,
  duplicate within one tier, missing tier, fallback to shared Default per
  tier).

**osac-aap:**

- Update `tenant_storage_class` role to read `tenant.status.storageClasses`
  and accept a `tenant_storage_class_storage_tier` input parameter.
- Update template roles to pass the appropriate tier to
  `tenant_storage_class` when invoking it.
- Update tests for tier-aware lookup.

**fulfillment-service:**

- No changes expected in the initial implementation (Strategy A). The
  fulfillment-service remains a pass-through. If Strategy B is adopted later,
  the `DiskSpec` proto message will need a `storage_tier` field.

**osac-installer:**

- No changes expected.

### Risks and Mitigations

**Risk: Label sprawl.** CSPs could create an unbounded number of tier labels,
making the Tenant status large and hard to reason about.

**Mitigation:** Documentation will recommend a small, well-defined set of tiers
(e.g., `fast`, `standard`, `archival`). The system does not enforce a fixed
vocabulary, but operational guidance will discourage excessive granularity.

**Risk: Backward compatibility during upgrade.** Existing deployments have
`tenant.status.storageClass` (string). If the field is removed, consumers
that have not been updated will break.

**Mitigation:** The singular `status.storageClass` field is retained as a
convenience accessor that points to the `Default` tier. Consumers are migrated
to read from `status.storageClasses` but are not immediately broken.

**Risk: Duplicate detection complexity.** With multiple tiers, the number of
potential duplicate scenarios increases.

**Mitigation:** Duplicate detection is per-tier. Each `(tenant, tier)` pair is
resolved independently. The existing duplicate detection logic is reused at
each resolution step.

### Drawbacks

This design adds a dimension of complexity to the StorageClass selection
process. For CSPs that only need a single StorageClass per tenant, the new
`storage-tier` label is unnecessary overhead. The backward-compatible defaults
(omitted label = `Default` tier, omitted parameter = `Default` tier) ensure
these CSPs are not burdened by the feature, but the Tenant controller must
still handle the multi-tier resolution path.

## Alternatives (Not Implemented)

**Alternative 1: Use a map instead of a list in Tenant status.** The resolved
tiers could be stored as `map[string]string` (tier to StorageClass name)
instead of a list of structs. This was considered but rejected because:

- A list of structs is more extensible. If additional metadata per tier is
  needed later (e.g., quota, capacity information), it can be added to the
  struct without changing the container type.
- Kubernetes CRD validation works better with lists than with maps of
  arbitrary keys.

## Open Questions

1. Should the Tenant require a `Default` tier to be `Ready`, or is it
   sufficient to have any tier resolve? If a tenant only has `fast` storage
   and a template requests `Default`, should the system error?

2. Should tier names be validated against a predefined vocabulary, or remain
   freeform? Freeform is more flexible but risks inconsistency across tenants.

3. **Should tenant users be able to specify storage tiers?** In Strategy A,
   the template author (Tenant Admin) decides which tier each disk uses and
   the user has no control. If user-specified tiers are desired, there are
   two mechanisms: a configurable template that reads the tier from
   `templateParameters`, or a dedicated `storageTier` field on the
   ComputeInstance `DiskSpec` (Strategy B). Both achieve the same result
   (user provides the tier value), but differ in scope: a template parameter
   is scoped to templates that opt in, while a DiskSpec field is available
   on every ComputeInstance. If Strategy B is adopted, the proto/public API
   would also need a `storage_tier` field, requiring buf regeneration and
   fulfillment-service proto updates.

## Test Plan

**Unit tests (osac-operator):**

- Tenant controller: resolve multiple tiers per tenant, duplicate detection
  per tier, fallback to shared Default per tier, mixed (some tiers from tenant,
  some from Default), backward-compatible single SC with no tier label.
- Verify `status.storageClasses` list is populated correctly.
- Verify `status.storageClass` (singular) still contains the `Default` tier.

**Unit tests (osac-aap):**

- `tenant_storage_class` role with `tenant_storage_class_storage_tier`
  parameter: resolve `fast` tier, resolve `Default` tier, resolve when no
  tier parameter is provided (defaults to `Default`), fail when requested
  tier is not in the list (verify error message includes available tiers),
  backward-compatible fallback to `status.storageClass` when
  `status.storageClasses` is absent.

**E2E tests:**

- Tenant with `fast` and `standard` tiers: verify both resolve correctly in
  Tenant status.
- Template requests `fast` tier: verify the DataVolume uses the `fast`
  StorageClass.
- Template requests no tier (Default): verify the DataVolume uses the
  `Default` StorageClass.
- Shared Default fallback per tier: tenant has no dedicated `fast` SC, verify
  the shared Default `fast` SC is used.
- Tier not available: template requests `fast` but only `standard` is
  configured. Verify descriptive error with available tier list.
- Backward compatibility: existing single-SC tenant (no `storage-tier` label)
  continues to work without any changes.
- Duplicate detection per tier: two SCs for `(tenantX, fast)` produces
  `MultipleFound` for that tier, but `(tenantX, standard)` is unaffected.

## Graduation Criteria

**Note:** *Section not required until targeted at a release.*

This enhancement would follow the same maturity progression as the broader OSAC
project. Initial implementation targets Dev Preview with the expectation that
the label vocabulary and API fields will stabilize through operational
experience before GA.

[maturity-levels]: https://git.k8s.io/community/contributors/devel/sig-architecture/api_changes.md#alpha-beta-and-stable-versions
[deprecation-policy]: https://kubernetes.io/docs/reference/using-api/deprecation-policy/

## Upgrade / Downgrade Strategy

**Upgrade from single-tier to multi-tier:**

- Existing StorageClasses without the `osac.openshift.io/storage-tier` label
  continue to work. The Tenant controller treats them as tier `Default`.
- Existing `tenant.status.storageClass` (string) is retained for backward
  compatibility. Consumers that read the old field continue to get the
  `Default` tier StorageClass name.
- The new `tenant.status.storageClasses` (list) is additive. Old consumers
  that do not read it are unaffected.
- Templates and roles that do not specify a tier parameter continue to use
  the `Default` tier.

## Version Skew Strategy

N/A. OSAC is in active development and has not been released to customers.

## Support Procedures

N/A. OSAC is in active development and has not been released to customers.

## Infrastructure Needed

No new infrastructure is required. This enhancement extends existing CRDs and
controller logic.
