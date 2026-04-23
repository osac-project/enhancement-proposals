---
title: tenant-storage-tiers
authors:
  - akshaynadkarni
creation-date: 2026-03-26
last-updated: 2026-04-22
tracking-link:
  - https://redhat.atlassian.net/browse/MGMT-23669
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
alongside slower HDD storage for archival. This proposal adds a **required**
`osac.openshift.io/storage-tier` label to StorageClasses, introduces a new
`tenant.status.storageClasses` list (replacing the singular
`tenant.status.storageClass` field), and updates the `tenant_storage_class`
Ansible role to **require** a storage tier parameter so that consumers
explicitly select the appropriate StorageClass for a given workload.

Since OSAC is pre-release with no deployed consumers, this proposal takes a
clean-slate approach: tier labels are required (not optional), there is no
implicit "Default" fallback, and the singular `status.storageClass` field is
removed rather than deprecated. A migration path is provided for existing
development and test environments.

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

As an **OSAC Contributor**, I want to ship VM templates that work out of the
box on any OSAC deployment, so that CSPs can use them without needing to fork
and customize each template for their storage tier names.

As a **CSP Admin**, I want to customize or extend OSAC-shipped templates to
use specialized storage tiers (e.g., `fast` for database templates) that match
my infrastructure, so that my tenants get the right storage for each workload
type.

### Goals

* Enable CSPs to offer multiple storage tiers per tenant using labels on
  StorageClasses.
* Expose all resolved storage tiers in the Tenant status so that any consumer
  (VM templates, Ansible roles, future API fields) can select the appropriate
  StorageClass by tier.
* Keep the Tenant controller as the single source of truth for StorageClass
  resolution, so that osac-operator and osac-aap do not each implement the
  same resolution logic. Consumers use `status.storageClasses` to determine
  which StorageClass to use for a given tier.
* Require all StorageClasses to declare their tier explicitly. No implicit
  fallback behavior.

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
* Backward compatibility with the singular `status.storageClass` field. OSAC is
  pre-release; see [Migration Path](#migration-path) for upgrade guidance.

### Assumptions

This proposal assumes the following:

1. **An external system maintains the source of truth for valid storage tier
   names.** The Tenant controller does not define, validate, or discover which
   tiers are available in the underlying storage infrastructure. Some external
   process (CSP onboarding tooling, storage vendor integration, or manual CSP
   Admin action) is responsible for knowing what storage tiers the data center
   can provide (e.g., which pools exist on the Ceph/NetApp/Pure Storage cluster)
   and mapping those to tier names used in OSAC labels.

2. **An external system is responsible for creating and maintaining Tenant
   StorageClasses with the correct labels.** This proposal defines how the
   Tenant controller *consumes* labeled StorageClasses, not how they are
   *created*. Whether StorageClass creation is automated (e.g., as part of
   tenant onboarding via the OSAC API) or manual (CSP Admin runs `oc apply`)
   is outside the scope of this proposal. Automation for tier discovery and
   StorageClass lifecycle management will be addressed in a subsequent proposal.

3. **The set of available tiers is relatively static.** Tiers represent
   categories of storage capability (e.g., fast, standard, archival), not
   individual storage pools or volumes. Tier names are expected to change
   infrequently, on the order of storage infrastructure changes.

## Proposal

This proposal adds a second label axis to the StorageClass labeling convention.
The existing `osac.openshift.io/tenant` label identifies *which tenant* owns a
StorageClass. The new `osac.openshift.io/storage-tier` label identifies *what
kind* of storage it provides.

Each StorageClass is identified by a composite key: `(tenant, storage-tier)`.
The two axes have different resolution rules. The `tenant` axis retains its
existing fallback behavior (tenant-specific, then shared `Default`), and this
fallback is applied independently per tier. The `storage-tier` axis is an exact
match with no inter-tier fallback: a request for tier `fast` never silently
resolves to `standard`. Both labels are required on every StorageClass that
participates in OSAC storage resolution.

Tier names are freeform: CSPs choose values that make sense for their storage
offering (e.g., `fast`, `standard`, `archival`, `default`). OSAC does not
define a fixed vocabulary or treat any tier name as special. A CSP that wants a
general-purpose tier can label it `default` (lowercase, by convention), but the
controller does not assign it any magic behavior.

### Workflow Description

#### Personas

| Persona | Role | Relevant actions |
|---|---|---|
| **OSAC Contributor** | OSAC project developer | Creates and maintains OSAC-shipped VM templates |
| **CSP Admin** | Cloud Provider Admin (infrastructure) | Creates StorageClasses with tenant and tier labels; customizes templates for specialized tiers |
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

#### Workflow 2: CSP Admin configures storage tiers on shared Default StorageClasses

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
  name: ceph-shared-default
  labels:
    osac.openshift.io/tenant: Default
    osac.openshift.io/storage-tier: default
provisioner: rook-ceph.rbd.csi.ceph.com
parameters:
  pool: shared-hdd-pool
```

2. For tenants that have no dedicated StorageClass for a given tier, the
   Tenant controller falls back to the shared Default StorageClass for that
   tier. The fallback is applied independently per tier.

**Expected result:** Tenants without dedicated storage still have access to
tiered storage options through the shared Defaults.

#### Workflow 3: Mixed tenant-specific and shared Default tiers

**Actors:** CSP Admin

**Starting state:** The CSP has shared Default StorageClasses labeled with
tiers, and has configured tenant-specific `fast` and `slow` StorageClasses
for `tenant-acme`.

StorageClasses on the cluster:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-shared-default
  labels:
    osac.openshift.io/tenant: Default
    osac.openshift.io/storage-tier: default
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
   - `default`: no tenant-specific SC for this tier. Falls back to the
     shared Default SC (`ceph-shared-default`).

2. The resulting Tenant status:

```yaml
status:
  phase: Ready
  storageClasses:
    - name: "ceph-shared-default"
      tier: "default"
    - name: "ceph-acme-fast"
      tier: "fast"
    - name: "ceph-acme-slow"
      tier: "slow"
```

**Expected result:** `tenant-acme` has three resolved tiers. The `fast` and
`slow` tiers use tenant-specific StorageClasses. The `default` tier falls back
to the shared Default StorageClass.

#### Workflow 4: Template-driven tier selection during provisioning

**Actors:** CSP Admin (customizes the template), Tenant User (creates the CI)

**Starting state:** `tenant-acme` has `fast` and `default` tiers resolved.
The CSP Admin has customized the `database_vm` template to use `fast` storage
for boot disks.

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

#### Workflow 5: Requested storage tier is not available

**Actors:** Tenant User (indirectly, via a template that requests an
unavailable tier)

**Starting state:** `tenant-acme` has `default` and `standard` tiers.
A template requests `fast` storage.

1. The `tenant_storage_class` role attempts to resolve tier `fast` from
   `tenant.status.storageClasses` but finds no matching entry.

2. The role fails with a descriptive error:

   > `tenant_storage_class_storage_tier` parameter is required.
   > Storage tier "fast" is not available for tenant "tenant-acme".
   > Available tiers: default, standard.

3. The ComputeInstance transitions to `Failed` with a descriptive message.

**Expected result:** The provisioning fails with a clear error identifying the
missing tier and listing the available alternatives.

#### Workflow 6: Tier parameter not specified in template

**Actors:** CSP Admin or OSAC Contributor (creates a template without specifying a tier)

**Starting state:** `tenant-acme` has `fast` and `default` tiers resolved.

1. A template invokes the `tenant_storage_class` role without setting
   `tenant_storage_class_storage_tier`.

2. The role fails immediately with:

   > `tenant_storage_class_storage_tier` parameter is required.
   > Available tiers for tenant "tenant-acme": default, fast.

3. The ComputeInstance transitions to `Failed`.

**Expected result:** The template author is forced to be explicit about which
storage tier the workload needs. There is no silent fallback to a default tier.

### API Extensions

#### StorageClass labels

Both the tenant label and the storage-tier label are required on every
StorageClass that participates in OSAC storage resolution. The Tenant
controller ignores StorageClasses that are missing either label.

| Label key | Required | Values | Behavior when absent |
|---|---|---|---|
| `osac.openshift.io/tenant` | Yes | `<tenantName>` or `Default` | StorageClass ignored |
| `osac.openshift.io/storage-tier` | Yes | Lowercase Kubernetes label value (e.g., `fast`, `standard`, `archival`, `nvme-1`, `default`) | StorageClass ignored |

The `osac.openshift.io/tenant` label retains the `Default` (capitalized)
sentinel convention for shared StorageClasses. The `osac.openshift.io/tenant`
axis is the only axis that uses a capitalized sentinel.

Storage tier values are currently freeform. OSAC does not define a fixed
vocabulary or treat any tier name as special. CSPs choose tier names that make
sense for their storage offering. Recommended conventions include `fast`,
`standard`, `archival`, and `default`, but these are documentation guidance,
not enforced constraints. As noted in [Assumptions](#assumptions), an external
system will own the source of truth for valid tier names. A future proposal
addressing tier discovery and StorageClass lifecycle management may introduce
validation of tier names against that registry. Tier values must be lowercase and conform to Kubernetes label
value syntax:
alphanumeric, dashes, dots, and underscores, up to 63 characters, beginning
and ending with an alphanumeric character.

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

#### Tenant CRD status changes

The singular `status.storageClass` field (string) is **removed** and replaced
by a `status.storageClasses` list that captures all resolved StorageClass
mappings for the tenant:

```yaml
status:
  phase: Ready
  namespace: "tenant-acme-ns"
  storageClasses:
    - name: "ceph-acme-default"
      tier: "default"
    - name: "ceph-acme-fast"
      tier: "fast"
    - name: "ceph-acme-standard"
      tier: "standard"
    - name: "ceph-shared-archival"
      tier: "archival"
```

Each entry in `storageClasses` is either a tenant-specific StorageClass or a
shared Default StorageClass resolved via fallback. A tenant only sees its own
StorageClasses and the shared Defaults; it never sees StorageClasses belonging
to other tenants.

Go type:

```go
type ResolvedStorageClass struct {
    // Name is the name of the resolved StorageClass.
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:MinLength=1
    Name string `json:"name"`

    // Tier is the storage tier this StorageClass provides,
    // taken from the osac.openshift.io/storage-tier label.
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:MinLength=1
    // +kubebuilder:validation:MaxLength=63
    // +kubebuilder:validation:Pattern=`^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$`
    Tier string `json:"tier"`
}
```

The `tenant` value is NOT included in `ResolvedStorageClass` because the Tenant
CR itself is the tenant context. The tenant-to-Default fallback has already been
applied by the time the resolved list is populated.

The singular `status.storageClass` field is removed entirely. See
[Migration Path](#migration-path) for upgrade guidance.

### Implementation Details/Notes/Constraints

#### Resolution algorithm

The Tenant controller resolves **all available tier combinations** for each
tenant at reconciliation time. The controller considers only StorageClasses
labeled with `osac.openshift.io/tenant=<tenantName>` or
`osac.openshift.io/tenant=Default`. StorageClasses belonging to other tenants
are never visible.

StorageClasses missing the `osac.openshift.io/storage-tier` label are ignored
entirely and are not included in resolution.

For each distinct `storage-tier` value `T` found across StorageClasses labeled
with `osac.openshift.io/tenant=<tenantName>` or
`osac.openshift.io/tenant=Default`:

1. Find StorageClasses labeled `osac.openshift.io/tenant=<tenantName>` AND
   `osac.openshift.io/storage-tier=T`.
   - Exactly one: use it.
   - More than one: duplicate error for this tier (same as the existing
     behavior for the single-tier case).
   - None: proceed to step 2.

2. Find StorageClasses labeled `osac.openshift.io/tenant=Default` AND
   `osac.openshift.io/storage-tier=T`.
   - Exactly one: use it (shared Default fallback for this tier).
   - More than one: duplicate error for this tier.
   - None: tier `T` is not available for this tenant (not an error at
     the Tenant level; individual provisioning requests that ask for this
     tier will fail at the Ansible role level).

The resolved list is stored in `tenant.status.storageClasses`. Consumers never
implement fallback logic; they look up the requested tier in the pre-resolved
list.

#### Data flow: operator to Ansible

The resolved `storageClasses` list is passed to Ansible as part of the job
context (extra_vars) when the CI controller triggers a provisioning job.
The CI controller already fetches the Tenant CR to verify readiness before
triggering; it reads `tenant.status.storageClasses` at that point and injects
the list into the extra_vars alongside the ComputeInstance payload. This
eliminates the need for Ansible to make a separate K8s API call to fetch the
Tenant CR, since Ansible has no informer cache and every `k8s_info` call is a
direct API server hit.

#### Tier selection at provisioning time

The `tenant_storage_class` Ansible role is the selection interface. It
**requires** a `tenant_storage_class_storage_tier` input parameter (no default
value) and resolves it against the `storageClasses` list injected via
extra_vars.

If the parameter is not provided, the role fails immediately with a descriptive
error listing the available tiers for the tenant. This forces template authors
to be explicit about which storage tier their workload needs.

**Who provides the `storage_tier` value** is a separate concern from how the
role resolves it. The initial implementation uses **template-driven**
selection. Each VM template hardcodes which tier its disks need. The tenant
user selects a template when creating a ComputeInstance and does not need to
know about storage tiers.

#### OSAC-shipped templates and the `default` tier convention

OSAC-shipped templates (written by OSAC contributors) must work out of the box
on any OSAC deployment without requiring CSPs to fork or customize them for
their specific tier names. To achieve this, OSAC-shipped templates use the
conventional tier name `default`:

```yaml
# Inside osac.templates.ocp_virt_vm/tasks/create.yaml (OSAC-shipped)
- name: Resolve boot disk StorageClass
  ansible.builtin.include_role:
    name: osac.service.tenant_storage_class
  vars:
    tenant_storage_class_storage_tier: "default"
```

For this to work, every VMaaS cluster must have at least one shared
StorageClass with `osac.openshift.io/tenant: Default` and
`osac.openshift.io/storage-tier: default`. This is the baseline that ensures
OSAC-shipped templates resolve a StorageClass for any tenant through the
existing shared Default fallback. CSPs can override it per-tenant by creating
a StorageClass with `tenant: <tenantName>, storage-tier: default`.

CSPs that want specialized templates (e.g., a `database_vm` template that uses
`fast` storage) customize or extend OSAC-shipped templates for their
environment:

```yaml
# Inside a CSP-customized database_vm template
- name: Resolve boot disk StorageClass
  ansible.builtin.include_role:
    name: osac.service.tenant_storage_class
  vars:
    tenant_storage_class_storage_tier: "fast"
```

If user-specified tiers are needed in the future, a `storageTier` field on the
ComputeInstance `DiskSpec` or a hybrid approach (template default, user
override) can be added as a separate enhancement. These strategies would
require proto changes, fulfillment-service updates, and API versioning.

#### StorageClassReady condition and Tenant readiness

A Tenant cannot reach `Ready` phase without at least one StorageClass that
carries **both** required labels (`osac.openshift.io/tenant` and
`osac.openshift.io/storage-tier`). If a CSP creates a StorageClass for a
tenant but omits the `storage-tier` label (or the `tenant` label), the
controller ignores it entirely. The Tenant remains in `Progressing` phase and
the `StorageClassReady` condition is `False`, signaling that storage is not
configured correctly.

This approach uses **status reflection** rather than admission webhooks. The
controller does not actively prevent the creation of incorrectly labeled
StorageClasses. Instead, the misconfiguration is surfaced through the Tenant
CR's status, which operators and monitoring systems can observe. Admission
webhooks were considered but rejected due to the operational complexity of
managing webhooks for a resource type (StorageClass) that is not owned by OSAC.

The existing `StorageClassReady` condition is extended:

- `Ready` requires at least one tier to resolve successfully.
- If **no tier resolves successfully** (all tiers have duplicates,
  MultipleDefaultsFound, or no StorageClass with both required labels exists
  for the tenant), the Tenant `phase` is set to `Progressing` and the
  `StorageClassReady` condition is `False` with a message listing all tier
  resolution failures.
- Duplicate detection applies per tier. Two StorageClasses for `(tenantX,
  fast)` produces a `MultipleFound` condition, but does not affect
  `(tenantX, standard)`.
- The condition message lists which tiers resolved successfully and which
  had errors.

#### Ansible role changes

The `tenant_storage_class` role currently queries the K8s API for the Tenant CR
and reads `tenant.status.storageClass` (a single string). It will be updated
to read the resolved `storageClasses` list from the injected extra_vars
instead of querying the K8s API:

1. Read the `storageClasses` list from extra_vars (injected by the CI
   controller at job creation time).
2. **Require** the `tenant_storage_class_storage_tier` input parameter (no
   default value). Fail immediately if the parameter is not provided, with an
   error message listing available tiers.
3. Find the entry in the list whose `tier` matches the request.
4. Set `tenant_storage_class_name` to the matching `name`.
5. Fail with a descriptive error if the requested tier is not in the list,
   including the available tiers.

#### Changes per repository

**osac-operator:**

- Evolve `getTenantStorageClass()` to `getTenantStorageClasses()`: group
  StorageClasses by `(tenant, storage-tier)` combination and resolve each
  independently. Ignore StorageClasses missing the `storage-tier` label.
- Add `ResolvedStorageClass` Go type to the Tenant CRD API.
- Add `tenant.status.storageClasses` (list of `ResolvedStorageClass`).
- Remove `status.storageClass` (singular) from the Tenant CRD API.
- Update `StorageClassReady` condition with per-tier resolution detail.
- Update the CI controller to read the resolved `storageClasses` list from
  the Tenant status and inject it into the extra_vars when launching the
  provisioning job.
- Update unit tests for multi-tier scenarios (multiple tiers resolved,
  duplicate within one tier, missing tier, fallback to shared Default per
  tier, StorageClass without tier label is ignored).

**osac-aap:**

- Update `tenant_storage_class` role to read the `storageClasses` list from
  extra_vars (injected by the CI controller) instead of querying the K8s API
  for the Tenant CR. **Require** a `tenant_storage_class_storage_tier` input
  parameter (no default).
- Update all template roles to explicitly pass the appropriate tier to
  `tenant_storage_class` when invoking it.
- Update tests for tier-aware lookup and for the missing-parameter failure
  case.

**fulfillment-service:**

- No changes expected. The fulfillment-service remains a pass-through.
  If user-specified tiers are added in the future (via a `storageTier` field
  on `DiskSpec`), the proto message will need updating.

**osac-installer:**

- No changes expected.

### Risks and Mitigations

**Risk: Label sprawl.** CSPs could create an unbounded number of tier labels,
making the Tenant status large and hard to reason about.

**Mitigation:** Documentation will recommend a small, well-defined set of tiers
(e.g., `fast`, `standard`, `archival`, `default`). The system does not enforce
a fixed vocabulary, but operational guidance will discourage excessive
granularity.

**Risk: Breaking change for existing dev/test environments.** Existing
StorageClasses may lack the `storage-tier` label, and existing code may read
`status.storageClass` (singular).

**Mitigation:** OSAC is pre-release with no production deployments. A one-time
migration is documented in the [Migration Path](#migration-path) section.

**Risk: Duplicate detection complexity.** With multiple tiers, the number of
potential duplicate scenarios increases.

**Mitigation:** Duplicate detection is per-tier. Each `(tenant, tier)` pair is
resolved independently. The existing duplicate detection logic is reused at
each resolution step.

### Drawbacks

This design introduces a breaking change to the Tenant CRD status API. The
singular `status.storageClass` field is removed and all StorageClasses must
carry a `storage-tier` label. For CSPs that only need a single StorageClass per
tenant, the required `storage-tier` label is additional configuration overhead.
However, the label is a single key-value pair, and the explicit-over-implicit
approach prevents the ambiguity that an optional label with a magic fallback
would create.

## Migration Path

This section describes the one-time migration from the current single-tier
system to the multi-tier system. OSAC is pre-release with no production
deployments, so this migration applies only to development and test
environments.

### Step 1: Label existing StorageClasses

Add the `osac.openshift.io/storage-tier` label to every existing StorageClass
that has an `osac.openshift.io/tenant` label. For StorageClasses that serve as
the general-purpose tier, use the conventional value `default`.

The script below only labels StorageClasses that do not already have a
`storage-tier` label, so it is safe to run multiple times:

```bash
# Label OSAC-managed StorageClasses that are missing a storage-tier label
for sc in $(oc get storageclass \
  -l osac.openshift.io/tenant,\!osac.openshift.io/storage-tier \
  -o jsonpath='{.items[*].metadata.name}'); do
  echo "Labeling $sc with storage-tier=default"
  oc label storageclass "$sc" osac.openshift.io/storage-tier=default
done
```

After this step, the Tenant controller will include these StorageClasses in its
resolution. Before this step, the updated controller ignores them (missing
required label).

### Step 2: Update osac-operator

Deploy the updated osac-operator that:

- Requires the `osac.openshift.io/storage-tier` label on all StorageClasses.
- Populates `tenant.status.storageClasses` (list).
- No longer populates `tenant.status.storageClass` (singular).

After the operator is updated and the StorageClasses are labeled, the Tenant
status will contain the new `storageClasses` list.

### Step 3: Update osac-aap

Deploy the updated osac-aap that:

- Reads `tenant.status.storageClasses` instead of `tenant.status.storageClass`.
- Requires `tenant_storage_class_storage_tier` on all role invocations.

All template roles must be updated to pass `tenant_storage_class_storage_tier`
explicitly (e.g., `default` for general-purpose templates, `fast` for database
templates).

### Step 4: Remove the singular field from the CRD

Once all consumers have been updated, the `status.storageClass` field can be
removed from the CRD schema. Since osac-operator and osac-aap are deployed
together in practice, Steps 2-4 can be combined into a single deployment.

### Ordering

Steps 1 and 2 can be applied in either order. If the operator is updated first,
existing StorageClasses without tier labels will be ignored until they are
labeled. If StorageClasses are labeled first, the old operator will ignore the
new label (it does not read it).

The recommended order is: label StorageClasses (Step 1), then deploy the
updated operator and AAP together (Steps 2-4).

## Design Decisions

The following questions were raised during review and resolved before this
proposal was finalized.

### 1. Should the Tenant require a `default` tier to be Ready?

**Decision: No.** The only requirement is that at least one tier resolves
successfully. Which tier(s) exist is the CSP's choice.

**Rationale:** Requiring a specific tier name couples the controller to naming
conventions. A CSP that only provides specialized tiers (`fast`, `gpu`) should
not be forced to also create a `default` tier. Templates must specify which
tier they need; there are no assumptions about which tiers exist.

### 2. Should tier names be validated against a predefined vocabulary?

**Decision: No, for now. Tier names are freeform.** Values must follow
Kubernetes label value syntax, but OSAC does not enforce a fixed list in this
proposal.

**Rationale:** Different CSPs have different storage offerings. Hardcoding tier
names in the controller is inflexible and would require controller updates as
storage technology evolves (e.g., `nvme-gen5`, `persistent-memory`). Instead,
the proposal documents recommended conventions (`fast`, `standard`, `archival`,
`default`) without enforcing them. Once the external system that owns the
source of truth for valid tier names is built (see
[Assumptions](#assumptions)), tier validation may be introduced at that layer.

### 3. Should tenant users be able to specify storage tiers?

**Decision: Template-driven only.** Templates encode the storage requirement.
Users select templates based on workload type, not infrastructure details.
OSAC-shipped templates use the conventional tier name `default`; CSPs customize
templates for specialized tiers.

**Rationale:** Templates are the right abstraction layer for storage decisions.
OSAC contributors write base templates that work on any deployment by using the
`default` tier. CSPs customize templates for specialized tiers (e.g.,
`database_vm` uses `fast`). Users do not need to think about storage. Adding
user-specified tiers (e.g., a `storageTier` field on `DiskSpec`) introduces
complexity: proto changes, fulfillment-service updates, API versioning, and two
paths to the same outcome. If tenant feedback shows a need for user-specified
tiers, a hybrid approach (template default, user override) can be added as a
future enhancement.

### 4. Should `status.storageClass` (singular) be deprecated or removed?

**Decision: Removed.** The field is deleted from the CRD, not deprecated.

**Rationale:** OSAC is pre-release with zero deployed consumers. Retaining a
deprecated field perpetuates the idea that a single tier is special and creates
permanent API surface that is unlikely to ever be removed. A clean break is
simpler and aligns with the explicit-tier-selection philosophy. See
[Migration Path](#migration-path) for upgrade guidance.

### 5. Should the `storage-tier` label be required or optional?

**Decision: Required.** The Tenant controller ignores StorageClasses missing
the `osac.openshift.io/storage-tier` label.

**Rationale:** An optional label with an implicit "Default" fallback creates
ambiguity: is `Default` a real tier name or an internal sentinel? Making the
label required eliminates this confusion. CSPs that want a general-purpose tier
label it `default` (lowercase, by convention), but the controller assigns no
magic behavior to any tier name. Since OSAC is pre-release, there is no
backward-compatibility cost to making this required.

## Alternatives (Not Implemented)

**Alternative 1: Use a map instead of a list in Tenant status.** The resolved
tiers could be stored as `map[string]string` (tier to StorageClass name)
instead of a list of structs. This was considered but rejected because:

- A list of structs is more extensible. If additional metadata per tier is
  needed later (e.g., quota, capacity information), it can be added to the
  struct without changing the container type.
- Kubernetes CRD validation works better with lists than with maps of
  arbitrary keys.

**Alternative 2: Optional storage-tier label with implicit "Default" fallback.**
The original proposal made the `storage-tier` label optional, with missing
labels treated as a capitalized `Default` sentinel. This was rejected during
review because:

- The capitalized `Default` sentinel creates confusion: is it a real tier name
  or an internal marker?
- Implicit fallback behavior is harder to reason about and debug.
- OSAC is pre-release, so backward compatibility is not a constraint.
- Making the label required eliminates an entire class of ambiguity.

**Alternative 3: Deprecate `status.storageClass` instead of removing it.** The
singular field could be deprecated and retained for backward compatibility.
This was rejected because:

- OSAC is pre-release with zero deployed consumers reading this field.
- Retaining the field perpetuates the idea that a single "default" tier is
  special, contradicting the explicit-tier-selection philosophy.
- A deprecated field that is never removed becomes permanent API surface.

## Test Plan

**Unit tests (osac-operator):**

- Tenant controller: resolve multiple tiers per tenant, duplicate detection
  per tier, fallback to shared Default per tier, mixed (some tiers from tenant,
  some from Default).
- StorageClass without `storage-tier` label is ignored entirely.
- Verify `status.storageClasses` list is populated correctly.
- Verify `status.storageClass` (singular) is NOT populated.
- All tiers fail to resolve: Tenant is Progressing, StorageClassReady is
  False with message listing all failures.

**Unit tests (osac-aap):**

- `tenant_storage_class` role with `tenant_storage_class_storage_tier`
  parameter: resolve `fast` tier, resolve `default` tier.
- Fail when `tenant_storage_class_storage_tier` is not provided (verify error
  message includes available tiers).
- Fail when requested tier is not in the list (verify error message includes
  available tiers).

**E2E tests:**

- Tenant with `fast` and `standard` tiers: verify both resolve correctly in
  Tenant status.
- Template requests `fast` tier: verify the DataVolume uses the `fast`
  StorageClass.
- Template requests `default` tier: verify the DataVolume uses the `default`
  StorageClass.
- Shared Default fallback per tier: tenant has no dedicated `fast` SC, verify
  the shared Default `fast` SC is used.
- Tier not available: template requests `fast` but only `standard` is
  configured. Verify descriptive error with available tier list.
- Duplicate detection per tier: two SCs for `(tenantX, fast)` produces
  `MultipleFound` for that tier, but `(tenantX, standard)` is unaffected.
- StorageClass without tier label: verify it is ignored by the controller.
- All tiers fail: verify Tenant is Progressing with StorageClassReady=False.

**Upgrade scenario test:**

- Deploy Tenant with the old controller (single SC, no tier label,
  `status.storageClass` populated).
- Label the existing StorageClass with `osac.openshift.io/storage-tier=default`.
- Upgrade to the new controller.
- Verify:
  - `status.storageClasses` (list) is populated with one entry:
    `{name: "...", tier: "default"}`.
  - `status.storageClass` (singular) is no longer present.
  - Templates updated to pass `tenant_storage_class_storage_tier: "default"`
    continue to provision successfully.

## Graduation Criteria

N/A. OSAC is in active development and has not been released to customers.
Initial implementation targets Dev Preview.

## Upgrade / Downgrade Strategy

See [Migration Path](#migration-path) for upgrade guidance. Since OSAC is
pre-release, there is no downgrade path. The migration is a one-time breaking
change applied during development.

## Version Skew Strategy

N/A. OSAC is in active development and has not been released to customers.

## Support Procedures

N/A. OSAC is in active development and has not been released to customers.

## Infrastructure Needed

No new infrastructure is required. This enhancement extends existing CRDs and
controller logic.
