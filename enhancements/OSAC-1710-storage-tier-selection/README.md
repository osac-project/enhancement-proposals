---
title: computeinstance-storage-tier-selection
authors:
  - Carlo Lobrano
creation-date: 2026-07-22
last-updated: 2026-07-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1710
prd:
  - "prd.md"
see-also:
  - "/enhancements/tenant-specific-storageclasses"
  - "/enhancements/storage-tier-OSAC-1110"
  - "/enhancements/storage-backend-osac-1111"
replaces:
  - N/A
superseded-by:
  - N/A
---

# ComputeInstance StorageTier Selection

## Summary

This enhancement adds a `storage_tier` field to `ComputeInstanceDisk` across the full OSAC stack -- proto definitions, fulfillment-service validation/defaults, CRD types, operator pre-provisioning validation, and AAP roles -- enabling per-disk storage tier selection with a mandatory resolution chain (user input > CatalogItem defaults > Template defaults). See [PRD](prd.md) for detailed requirements.

## Motivation

The ComputeInstance provisioning flow currently treats all disks identically from a storage perspective. The `DiskSpec` carries only `SizeGiB`, and the AAP playbook reads a single `STORAGE_REQUESTED_TIER` environment variable to select one StorageClass for every DataVolume -- boot disk and additional disks alike.

This means a database VM that needs high-IOPS storage and a log-archive VM that could use cold storage both receive the same tier. The storage tier model already exists in the system: OSAC-1110 defines StorageTier resources, the tenant controller resolves tiers to per-tenant StorageClasses via `Tenant.Status.StorageClasses`, and the AAP `tenant_storage_class` role can filter by tier name. The missing piece is a per-disk field in the ComputeInstance data model that carries the tier selection through the stack.

This design adds `storage_tier` to `ComputeInstanceDisk`, making it a required field with a well-defined default resolution chain. The field flows from the proto API through the fulfillment-service reconciler to the CRD, where the operator validates it against the tenant's resolved StorageClasses before dispatching to AAP. The AAP role resolves each disk's tier to a StorageClass independently, replacing the single-tier `STORAGE_REQUESTED_TIER` environment variable.

### Goals

- Reuse the existing FieldDefinition and SpecDefaults mechanisms for tier default resolution rather than introducing new defaulting infrastructure.
- Validate tier existence at two levels: fulfillment-service (tier name exists in the StorageTier API) and operator (tier has a resolved StorageClass for the tenant).
- Preserve immutability semantics already enforced on `bootDisk` and `additionalDisks` via CRD XValidation rules.
- Remove the `STORAGE_REQUESTED_TIER` environment variable from AAP, shifting the tier source to the CR payload.

### Non-Goals

- Tier discovery for tenant users (OSAC-1110 scope).
- CaaS cluster template tier selection. [Locked: D3]
- Storage quota or capacity management per tier.
- Auto-scaling or cross-tier migration of existing disks.

## Proposal

The change adds a single field -- `storage_tier` (proto) / `StorageTier` (CRD) -- to the disk specification at every layer: proto definitions (private and public), CRD types, fulfillment-service validation and defaults merging, reconciler mapping, operator pre-provisioning validation, and AAP per-disk StorageClass resolution. The `STORAGE_REQUESTED_TIER` environment variable is removed.

The tier is mandatory. After applying the resolution chain (user input, CatalogItem FieldDefinition defaults, Template SpecDefaults), every disk must have a non-empty `storage_tier`. If resolution fails, the fulfillment-service returns a clear error and does not create the ComputeInstance.

### Workflow Description

#### Actors

- **Cloud Provider Admin / Cloud Infrastructure Admin**: Configures StorageTier resources (OSAC-1110) and CatalogItems with tier defaults.
- **Tenant Admin**: Creates tenant-scoped CatalogItems with pre-configured tier values.
- **Tenant User**: Creates ComputeInstances, optionally specifying per-disk tiers.

#### Starting State

StorageTier resources exist (OSAC-1110). StorageClasses are labeled with `osac.openshift.io/storage-tier` and `osac.openshift.io/tenant`. The tenant controller has resolved `Tenant.Status.StorageClasses` for the tenant.

#### Happy Path: Tenant User Creates a ComputeInstance with Explicit Tiers

1. Tenant User sends `POST /api/public/v1/compute_instances` with `boot_disk.storage_tier: "fast"` and `additional_disks[0].storage_tier: "archive"`.
2. Fulfillment-service applies FieldDefinitions from the CatalogItem (no override needed since user provided values).
3. Fulfillment-service applies Template SpecDefaults (no override needed since user provided values).
4. Fulfillment-service validates that `"fast"` and `"archive"` exist as StorageTier resources via the private StorageTier API.
5. Fulfillment-service persists the ComputeInstance with the validated tiers.
6. Reconciler maps proto fields to CRD: `spec.bootDisk.storageTier: "fast"`, `spec.additionalDisks[0].storageTier: "archive"`.
7. Operator validates that both `"fast"` and `"archive"` appear in `tenant.Status.StorageClasses`.
8. AAP receives the CR payload. For the boot disk, the `tenant_storage_class` role resolves `"fast"` to a StorageClass name. For the additional disk, it resolves `"archive"` to a different StorageClass name. Each DataVolume uses its own StorageClass.

#### Happy Path: Tenant User Creates a ComputeInstance with One Additional Disk

1. Tenant User sends `POST /api/public/v1/compute_instances` with `boot_disk.storage_tier: "standard"` and one additional disk: `additional_disks[0]: {size_gib: 500, storage_tier: "archive"}`.
2. The user must provide `storage_tier` on the additional disk -- no default mechanism applies (see [§ Why additional disks require explicit tiers](#why-additional-disks-require-explicit-tiers)).
3. Fulfillment-service validates both tiers exist.
4. Provisioning proceeds with two DataVolumes, each using its own StorageClass.

#### Happy Path: Tenant User Creates a ComputeInstance with Multiple Additional Disks

1. Tenant User sends `POST /api/public/v1/compute_instances` with `boot_disk.storage_tier: "fast"`, `additional_disks[0]: {size_gib: 200, storage_tier: "archive"}`, and `additional_disks[1]: {size_gib: 100, storage_tier: "fast"}`.
2. Each additional disk carries its own explicit `storage_tier`. The user chose different tiers for each disk based on workload needs.
3. Fulfillment-service validates that `"fast"` and `"archive"` exist as StorageTier resources.
4. Reconciler maps all three disks to CRD: `spec.bootDisk.storageTier: "fast"`, `spec.additionalDisks[0].storageTier: "archive"`, `spec.additionalDisks[1].storageTier: "fast"`.
5. Operator validates all three tiers against `tenant.Status.StorageClasses`.
6. AAP resolves each disk's tier independently: boot disk and second additional disk both resolve `"fast"` to the same StorageClass; first additional disk resolves `"archive"` to a different StorageClass. Three DataVolumes are created, each with the correct StorageClass.

#### Happy Path: Boot Disk Tier Resolved from CatalogItem Defaults

1. Tenant User sends `POST /api/public/v1/compute_instances` with `boot_disk.size_gib: 100` (no `storage_tier`) and no additional disks.
2. Fulfillment-service applies FieldDefinitions: `boot_disk.storage_tier` has a default of `"standard"`, which is applied.
3. Fulfillment-service validates `"standard"` exists.
4. Provisioning proceeds.

#### Happy Path: Boot Disk Tier Resolved from Template Defaults

1. Tenant User sends `POST /api/public/v1/compute_instances` with no `boot_disk` at all and no additional disks.
2. Fulfillment-service merges Template SpecDefaults: the template's `boot_disk` carries `storage_tier: "standard"` and `size_gib: 50`.
3. Fulfillment-service validates the resolved tier.
4. Provisioning proceeds.

#### Why Additional Disks Require Explicit Tiers

The boot disk and additional disks follow different defaulting rules:

- **Boot disk** supports tier defaults through CatalogItem FieldDefinitions (`boot_disk.storage_tier` path) and Template SpecDefaults (`boot_disk` field). This works because the boot disk is a known, single, always-present disk -- an admin can meaningfully pre-select a tier for it.

- **Additional disks** have no default mechanism. Unlike the boot disk, additional disks are optional, variable in count, and serve purposes that the admin cannot predict at template or catalog item authoring time. Additionally, the FieldDefinition path resolver uses dot-notation (e.g., `boot_disk.storage_tier`) and does not support array element addressing (e.g., `additional_disks[0].storage_tier`), nor does `ComputeInstanceTemplateSpecDefaults` carry an `additional_disks` field. The existing defaulting infrastructure is designed around singular, well-known fields -- extending it to repeated collections would require new path resolution logic for an unclear benefit, since the admin would only be able to assign the same tier to every additional disk regardless of its intended use.

Therefore, every additional disk must carry an explicit `storage_tier` from the user. Omitting it is a validation error.

#### Error Path: Boot Disk Tier Not Resolved

1. Tenant User sends a request with no `storage_tier` on the boot disk.
2. Neither the CatalogItem FieldDefinitions nor the Template SpecDefaults provide a tier.
3. Fulfillment-service returns `INVALID_ARGUMENT`: `"boot_disk.storage_tier is required but was not provided by user input, catalog item defaults, or template defaults"`. [Locked: D1]

#### Error Path: Additional Disk Missing Tier

1. Tenant User sends a request with `boot_disk.storage_tier: "fast"` and `additional_disks[0]: {size_gib: 200}` (no `storage_tier`).
2. No default mechanism applies to additional disks. The tier must be provided by the user.
3. Fulfillment-service returns `INVALID_ARGUMENT`: `"additional_disks[0].storage_tier is required"`.

#### Error Path: Tier Does Not Exist

1. Tenant User specifies `boot_disk.storage_tier: "nonexistent"`.
2. Fulfillment-service queries the StorageTier API -- no match found.
3. Fulfillment-service returns `INVALID_ARGUMENT`: `"storage tier \"nonexistent\" does not exist"`.

#### Error Path: Tier Not Available for Tenant

1. Fulfillment-service validation passes (the tier exists globally).
2. Operator checks `tenant.Status.StorageClasses` -- no entry for the requested tier.
3. Operator sets `Provisioned=False` condition with reason `StorageTierUnavailable` and message: `"storage tier \"fast\" is not available for tenant \"tenant-abc\"; available tiers: standard, archive"`.

```mermaid
sequenceDiagram
    participant User as Tenant User
    participant FS as Fulfillment Service
    participant DB as PostgreSQL
    participant Reconciler as FS Reconciler
    participant K8s as Kubernetes API
    participant Op as CI Controller
    participant AAP as AAP Provider
    participant Role as tenant_storage_class

    User->>FS: POST /compute_instances<br/>{boot_disk: {size_gib: 100, storage_tier: "fast"},<br/>additional_disks: [{size_gib: 200, storage_tier: "archive"}]}
    FS->>FS: Apply CatalogItem FieldDefinitions
    FS->>FS: Apply Template SpecDefaults
    FS->>FS: Validate storage_tier exists (StorageTier API)
    FS->>DB: Persist ComputeInstance
    FS-->>User: 200 OK

    Reconciler->>DB: Watch ComputeInstance
    Reconciler->>K8s: Create/Update ComputeInstance CR<br/>{bootDisk: {sizeGiB: 100, storageTier: "fast"},<br/>additionalDisks: [{sizeGiB: 200, storageTier: "archive"}]}

    Op->>K8s: Watch ComputeInstance CR
    Op->>K8s: Get Tenant (StorageClasses)
    Op->>Op: Validate tiers in tenant.Status.StorageClasses
    Op->>AAP: Launch job (CR payload + tenant_storage_classes)

    AAP->>Role: Resolve "fast" for boot disk
    Role-->>AAP: StorageClass "netapp-fast-tenant-abc"
    AAP->>Role: Resolve "archive" for additional disk
    Role-->>AAP: StorageClass "netapp-archive-tenant-abc"
    AAP->>K8s: Create DataVolumes with per-disk StorageClasses
```

The diagram shows the full flow from API request through the four-layer stack. The key change is that `storage_tier` travels per-disk from the API through to AAP, where each disk's tier is resolved to a StorageClass independently.

### API Extensions

This enhancement modifies existing API surfaces. No new CRDs, admission webhooks, or finalizers are introduced.

**Proto API (private + public):** `ComputeInstanceDisk` message gains `string storage_tier = 2`. Existing CRUD operations on ComputeInstances, Templates, and CatalogItems carry the new field without RPC changes.

**CRD (osac-operator):** `DiskSpec` gains `StorageTier string`. The existing `XValidation:rule="self == oldSelf"` on `bootDisk` and `additionalDisks` enforces immutability for the new field automatically. [Locked: D6]

**AAP extra_vars:** No structural change to `ansible_eda.event`. The CR payload already contains the full ComputeInstance spec, which now includes `storageTier` per disk. The `tenant_storage_classes` sibling field is unchanged.

If the operator controller is down, ComputeInstance CRs will queue in Kubernetes and be reconciled when the controller recovers. No data loss occurs -- the CR is the source of truth. [Codebase: osac-operator/internal/controller/computeinstance_controller.go]

### Implementation Details/Notes/Constraints

#### 1. Proto Schema Changes

Add `storage_tier` as field 2 to `ComputeInstanceDisk` in both private and public proto files.

```protobuf
// In both private and public compute_instance_type.proto
message ComputeInstanceDisk {
  // Disk size in GiB.
  int32 size_gib = 1;
  // Storage tier name. Must reference an existing StorageTier resource.
  string storage_tier = 2;
}
```

No `optional` qualifier -- the field uses proto3 implicit presence. An empty string is treated as "not provided" during defaults merging and validated as missing after the full resolution chain. [Locked: D2]

`ComputeInstanceTemplateSpecDefaults` inherits the new field through its existing `optional ComputeInstanceDisk boot_disk = 4` reference. No change to the template proto is needed. [Codebase: fulfillment-service/proto/private/osac/private/v1/compute_instance_template_type.proto]

#### 2. Spec Defaults Merging

Extend `mergeBootDiskDefaults()` in `fulfillment-service/internal/utils/spec_defaults.go` to handle `storage_tier`:

```go
func mergeBootDiskDefaults(spec *privatev1.ComputeInstanceSpec, defaults *privatev1.ComputeInstanceTemplateSpecDefaults) {
    if !defaults.HasBootDisk() {
        return
    }
    if !spec.HasBootDisk() {
        spec.SetBootDisk(proto.Clone(defaults.GetBootDisk()).(*privatev1.ComputeInstanceDisk))
        return
    }
    disk := spec.GetBootDisk()
    defDisk := defaults.GetBootDisk()
    if disk.GetSizeGib() <= 0 && defDisk.GetSizeGib() > 0 {
        disk.SetSizeGib(defDisk.GetSizeGib())
    }
    // Merge storage_tier: apply template default only if user did not provide one
    if disk.GetStorageTier() == "" && defDisk.GetStorageTier() != "" {
        disk.SetStorageTier(defDisk.GetStorageTier())
    }
}
```

The merging follows the same pattern as `size_gib`: if the user provided a value, it is preserved; otherwise the template default is applied. When the spec has no `boot_disk` at all, the entire default disk (including `storage_tier`) is cloned, which is the existing behavior.

Template SpecDefaults only cover `boot_disk`. There is no `additional_disks` field in `ComputeInstanceTemplateSpecDefaults`, so additional disk tiers cannot be defaulted through templates. Additional disk tiers must come from the user or from CatalogItem FieldDefinitions. This is consistent with the existing template model -- templates default single-value spec fields, not repeated collections.

#### 3. CatalogItem FieldDefinition Support

CatalogItem FieldDefinitions support the path `boot_disk.storage_tier` through the existing dot-notation path resolution mechanism in `applyFieldDefinitions()`. No code changes are needed -- the `getNestedValue` and `setNestedValue` helpers already walk arbitrary dot-notation paths after marshaling the spec to JSON. [Codebase: fulfillment-service/internal/servers/catalog_item_validation.go]

Example FieldDefinition for a CatalogItem that pre-selects a boot disk tier:

```json
{
  "path": "boot_disk.storage_tier",
  "display_name": "Boot Disk Storage Tier",
  "editable": true,
  "default": "standard"
}
```

Additional disk tiers cannot be defaulted through FieldDefinitions. The path resolution mechanism uses dot-notation (e.g., `boot_disk.storage_tier`) and does not support array element addressing (e.g., `additional_disks[0].storage_tier`). This is not a limitation: additional disks are optional, user-defined, and variable in count -- an admin cannot predict how many additional disks a user will add or what tier each should use. Boot disk tier defaults are the meaningful use case, and they work through both the FieldDefinition path (`boot_disk.storage_tier`) and the Template SpecDefaults mechanism. [Locked: D2]

#### 4. Fulfillment-Service Validation

Extend `ValidateRequiredSpecFields()` and the disk validation functions to check `storage_tier`:

```go
func validateBootDisk(disk *privatev1.ComputeInstanceDisk) error {
    if disk == nil {
        return nil
    }
    if disk.GetSizeGib() <= 0 {
        return grpcstatus.Errorf(grpccodes.InvalidArgument, "boot_disk.size_gib must be greater than 0")
    }
    if disk.GetStorageTier() == "" {
        return grpcstatus.Errorf(grpccodes.InvalidArgument,
            "boot_disk.storage_tier is required but was not provided by user input, catalog item defaults, or template defaults")
    }
    return nil
}
```

Add a new `validateAdditionalDisks()` function (no additional disk validation exists today):

```go
func validateAdditionalDisks(disks []*privatev1.ComputeInstanceDisk) error {
    for i, disk := range disks {
        if disk.GetSizeGib() <= 0 {
            return grpcstatus.Errorf(grpccodes.InvalidArgument,
                "additional_disks[%d].size_gib must be greater than 0", i)
        }
        if disk.GetStorageTier() == "" {
            return grpcstatus.Errorf(grpccodes.InvalidArgument,
                "additional_disks[%d].storage_tier is required", i)
        }
    }
    return nil
}
```

Both functions are called from `ValidateRequiredSpecFields()` after defaults merging, so the validation runs against the fully resolved spec.

Add a tier existence check that queries the private StorageTier API to confirm each referenced tier name is a known resource. This runs at request time in the Create RPC handler, after validation but before persisting:

```go
func validateStorageTierExists(ctx context.Context, tierName string, storageTierClient StorageTierQuerier) error {
    exists, err := storageTierClient.Exists(ctx, tierName)
    if err != nil {
        return grpcstatus.Errorf(grpccodes.Internal, "failed to check storage tier %q: %v", tierName, err)
    }
    if !exists {
        return grpcstatus.Errorf(grpccodes.InvalidArgument, "storage tier %q does not exist", tierName)
    }
    return nil
}
```

The server calls this for `boot_disk.storage_tier` and each `additional_disks[*].storage_tier`.

#### 5. Reconciler Mapping (Proto to CRD)

Extend `addExplicitFields()` in `fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function.go` to map `storage_tier`:

```go
if ciSpec.HasBootDisk() {
    spec.BootDisk = osacv1alpha1.DiskSpec{
        SizeGiB:     ciSpec.GetBootDisk().GetSizeGib(),
        StorageTier: ciSpec.GetBootDisk().GetStorageTier(),
    }
}
if len(ciSpec.GetAdditionalDisks()) > 0 {
    disks := make([]osacv1alpha1.DiskSpec, 0, len(ciSpec.GetAdditionalDisks()))
    for _, disk := range ciSpec.GetAdditionalDisks() {
        disks = append(disks, osacv1alpha1.DiskSpec{
            SizeGiB:     disk.GetSizeGib(),
            StorageTier: disk.GetStorageTier(),
        })
    }
    spec.AdditionalDisks = disks
}
```

#### 6. CRD Type Changes

Add `StorageTier` to `DiskSpec` in `osac-operator/api/v1alpha1/computeinstance_types.go`:

```go
type DiskSpec struct {
    // SizeGiB is the size of the disk in gibibytes
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:Minimum=1
    SizeGiB int32 `json:"sizeGiB"`

    // StorageTier is the name of the storage tier for this disk.
    // Must match an entry in the tenant's resolved StorageClasses.
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:MinLength=1
    // +kubebuilder:validation:MaxLength=63
    // +kubebuilder:validation:Pattern=`^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$`
    StorageTier string `json:"storageTier"`
}
```

The `Pattern` validation matches the tier label regex used by `groupByTier()` in `storage_tier_resolution.go`, ensuring consistency between tier names in the CRD and the StorageClass label values. [Codebase: osac-operator/internal/controller/storage_tier_resolution.go]

Immutability is inherited: `bootDisk` uses `XValidation:rule="self == oldSelf"` which compares the entire `DiskSpec` struct. Adding `StorageTier` to the struct means it is automatically covered by the immutability check. No additional XValidation rules are needed. [Locked: D6]

#### 7. Operator Pre-Provisioning Validation

Add tier validation in the ComputeInstance controller's `handleUpdate()` path, after fetching the Tenant and before calling `handleProvisioning()`:

```go
func validateDiskTiers(instance *v1alpha1.ComputeInstance, tenant *v1alpha1.Tenant) error {
    availableTiers := make(map[string]bool, len(tenant.Status.StorageClasses))
    for _, sc := range tenant.Status.StorageClasses {
        availableTiers[sc.Tier] = true
    }

    bootTier := instance.Spec.BootDisk.StorageTier
    if !availableTiers[bootTier] {
        return fmt.Errorf("storage tier %q is not available for tenant %q; available tiers: %s",
            bootTier, tenant.Name, formatAvailableTiers(tenant.Status.StorageClasses))
    }

    for i, disk := range instance.Spec.AdditionalDisks {
        if !availableTiers[disk.StorageTier] {
            return fmt.Errorf("additional disk [%d]: storage tier %q is not available for tenant %q; available tiers: %s",
                i, disk.StorageTier, tenant.Name, formatAvailableTiers(tenant.Status.StorageClasses))
        }
    }
    return nil
}
```

On failure, the controller sets the `Provisioned` condition to `False` with reason `StorageTierUnavailable` and requeus. This validation catches the case where a tier exists in the global StorageTier API but the tenant has no StorageClass mapped for it -- a race condition that the fulfillment-service cannot detect. [Locked: D3 decision from design session]

#### 8. AAP Changes

##### 8a. Remove `STORAGE_REQUESTED_TIER` Environment Variable

Remove the `_requested_storage_tier` variable from `playbook_osac_create_compute_instance.yml`:

```yaml
# BEFORE
_requested_storage_tier: "{{ lookup('env', 'STORAGE_REQUESTED_TIER') | default('default', true) }}"

# AFTER: removed entirely
```

The tier is no longer a global setting. Each disk carries its own tier in the CR payload. [Locked: D4 from design session]

##### 8b. Per-Disk StorageClass Resolution

Refactor `create_resources.yaml` in the `ocp_virt_vm` role. Instead of resolving one StorageClass for all disks, resolve per-disk:

```yaml
# Resolve StorageClass for boot disk tier
- name: Resolve StorageClass for boot disk
  ansible.builtin.include_role:
    name: osac.service.tenant_storage_class
  vars:
    tenant_storage_class_storage_tier: >-
      {{ ansible_eda.event.payload.spec.bootDisk.storageTier }}

- name: Set boot disk storage class
  ansible.builtin.set_fact:
    boot_disk_storage_class: "{{ tenant_storage_class_name }}"

# Resolve StorageClass for each additional disk
- name: Resolve StorageClass for additional disks
  ansible.builtin.include_role:
    name: osac.service.tenant_storage_class
  vars:
    tenant_storage_class_storage_tier: "{{ item.storageTier }}"
  loop: "{{ ansible_eda.event.payload.spec.additionalDisks | default([]) }}"
  loop_control:
    index_var: disk_index
  register: additional_disk_sc_results

- name: Build additional disk storage class list
  ansible.builtin.set_fact:
    additional_disk_storage_classes: >-
      {{ additional_disk_storage_classes | default([]) + [tenant_storage_class_name] }}
  loop: "{{ ansible_eda.event.payload.spec.additionalDisks | default([]) }}"
  loop_control:
    index_var: disk_index
```

The boot disk DataVolume uses `boot_disk_storage_class`. Each additional disk DataVolume uses `additional_disk_storage_classes[disk_index]`.

The `tenant_storage_class` role itself requires no changes -- it accepts `tenant_storage_class_storage_tier` as input and returns `tenant_storage_class_name`. The role is simply called once per disk instead of once per ComputeInstance.

##### 8c. DataVolume Template Updates

Update the DataVolume templates in `create_resources.yaml` to use per-disk StorageClass references:

```yaml
# Boot disk DataVolume
storageClassName: "{{ boot_disk_storage_class }}"

# Additional disk DataVolumes (looped)
storageClassName: "{{ additional_disk_storage_classes[disk_index] }}"
```

#### 9. Resolution Precedence Summary

The tier resolution chain for boot disk:

```mermaid
flowchart TD
    A[User provides boot_disk.storage_tier?] -->|Yes| B[Use user value]
    A -->|No| C[CatalogItem FieldDefinition has default?]
    C -->|Yes| D[Apply FieldDefinition default]
    C -->|No| E[Template SpecDefaults has boot_disk.storage_tier?]
    E -->|Yes| F[Apply Template default]
    E -->|No| G[Fail: INVALID_ARGUMENT]
    B --> H[Validate tier exists]
    D --> H
    F --> H
    H -->|Exists| I[Persist and reconcile]
    H -->|Not found| J[Fail: tier does not exist]
```

The diagram shows the three-layer precedence chain and the validation gate. User input takes priority, followed by CatalogItem defaults, then Template defaults. If none provides a tier, the request fails. After resolution, the tier is validated against the StorageTier API.

For additional disks, the chain is simpler: user input only (no Template or FieldDefinition defaults apply to repeated collections). Every additional disk must have an explicit `storage_tier` from the user or be omitted entirely.

### Security Considerations

This enhancement inherits the existing security model without changes. Storage tier selection does not introduce new authentication or authorization surfaces.

- **Input validation**: The `storage_tier` field is validated against the `^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$` pattern at the CRD level and against the StorageTier API at the fulfillment-service level. This prevents injection of arbitrary strings into the AAP payload.
- **Tenant isolation**: The operator validates tiers against `tenant.Status.StorageClasses`, which is populated by the tenant controller using labeled StorageClasses. Tenants cannot access tiers mapped to other tenants' StorageClasses because the `osac.openshift.io/tenant` label on StorageClasses is controlled by the Cloud Infrastructure Admin, not the tenant.
- **OPA policies**: Existing OPA policies enforce that ComputeInstance operations are scoped to the authenticated tenant. The `storage_tier` field is part of the ComputeInstance spec and inherits this enforcement.

### Failure Handling and Recovery

**Missing tier after resolution chain**: The fulfillment-service returns `INVALID_ARGUMENT` with a message identifying which disk is missing a tier and which resolution layers were checked. The ComputeInstance is not created. No recovery action needed -- the user corrects the request.

**Tier does not exist in StorageTier API**: The fulfillment-service returns `INVALID_ARGUMENT` identifying the unknown tier name. The user or admin must either use a valid tier name or the Cloud Infrastructure Admin must create the missing StorageTier.

**Tier not available for tenant (operator-level)**: The operator sets `Provisioned=False` with reason `StorageTierUnavailable`. The condition message lists the requested tier and the available tiers for the tenant. The controller requeues. Recovery: the Cloud Infrastructure Admin creates and labels a StorageClass for the missing tier, the tenant controller updates `Tenant.Status.StorageClasses`, and the next reconciliation succeeds.

**AAP job failure (tier cannot be resolved to StorageClass)**: The `tenant_storage_class` role fails if no StorageClass matches. The AAP job reports failure, and the operator sets the provisioning condition accordingly. This path should be rare because the operator pre-validates tiers against `tenant.Status.StorageClasses`. It can occur if a StorageClass is deleted between operator validation and AAP execution. Recovery: the Cloud Infrastructure Admin recreates the StorageClass.

**Controller restart mid-reconciliation**: The CRD is the source of truth. On restart, the controller re-reads the ComputeInstance CR (with `storageTier` fields intact) and resumes reconciliation. The tier validation and provisioning steps are idempotent.

### RBAC / Tenancy

No RBAC or tenancy changes are required. The `storage_tier` field is part of the ComputeInstance spec, which inherits the existing tenant isolation enforced by OPA policies, the `osac.openshift.io/tenant` annotation, and namespace scoping. StorageTier resources are managed exclusively through the private API by Cloud Infrastructure Admins.

### Observability and Monitoring

No new observability changes. Existing monitoring mechanisms apply:

- Fulfillment-service validation errors are returned as gRPC status codes and logged by the request handler.
- The operator's `Provisioned` condition with reason `StorageTierUnavailable` is visible through `kubectl describe computeinstance` and Kubernetes events.
- AAP job success/failure is tracked through existing provisioning job status on `ComputeInstance.Status.ProvisioningJobs`.

### Risks and Mitigations

**Templates and CatalogItems must be updated**: Adding `storage_tier` as required means existing Templates and CatalogItems that lack a tier default will cause ComputeInstance creation to fail until updated. Since OSAC is pre-GA (CRDs are `v1alpha1`, no production tenants depend on backwards compatibility), this is an expected part of the upgrade rather than a breaking change. The rollout must include updating deployed Templates and CatalogItems with `storage_tier` values, and installation documentation must list tier configuration as a prerequisite.

**Version skew during rolling deployment**: If the fulfillment-service is updated before the operator, the operator will receive CRs with `storageTier` fields that the old operator CRD schema does not recognize. Mitigation: deploy the CRD update (operator) first, then the fulfillment-service. The new CRD field is additive and does not break old operator code that ignores it -- but the operator must be updated to validate tiers before AAP jobs run with the new payload structure.

**StorageClass deletion race**: A StorageClass could be deleted between operator validation and AAP execution. Mitigation: operator validation reduces the window but does not eliminate it. The AAP role fails cleanly with an error message identifying the missing StorageClass. This is an operational concern, not a design flaw -- administrators should not delete StorageClasses while provisioning is active.

### Drawbacks

Adding `storage_tier` as a mandatory field increases the minimum information required to create a ComputeInstance. Every Template and CatalogItem must be updated, and every additional disk must carry an explicit tier. This trades simplicity-of-use for explicitness: there is no implicit "just use whatever storage is available" path.

The trade-off is justified because implicit storage selection produced unpredictable behavior -- tenants could not reason about what storage their VMs would receive. Making the tier explicit aligns with the broader OSAC principle that Templates are fully parameterized and deterministic.

## Alternatives (Not Implemented)

### Global default tier with opt-in override

Instead of making `storage_tier` mandatory, define a system-wide default tier (e.g., via a ConfigMap or operator setting) that applies when no tier is specified. Per-disk overrides would be optional.

Pros: simpler migration, fewer changes to existing Templates/CatalogItems, lower barrier to ComputeInstance creation.

Cons: reintroduces implicit behavior that the team explicitly rejected in the design session. The name "default" was also rejected for tier naming (D7). A global default means tenants cannot predict which tier they get unless they read operator configuration, defeating the purpose of per-disk selection.

Rejected because: the team reached consensus that storage tier selection should be explicit, with no fallback to a default. [Locked: D1]

### Per-disk tier as optional with fallback to boot disk tier

Make `storage_tier` required only on the boot disk. Additional disks without a tier inherit the boot disk's tier.

Pros: reduces the number of fields a user must specify when all disks use the same tier.

Cons: introduces implicit cross-field dependency (additional disk behavior depends on boot disk configuration). Users who want different tiers per disk must understand the inheritance rule. The inheritance rule is non-obvious and would need documentation.

Rejected because: explicit is better than implicit. The additional typing cost (one field per additional disk) is low relative to the confusion prevented.

### Storage tier as an enum rather than a string

Define tier names as a proto enum (`STORAGE_TIER_FAST`, `STORAGE_TIER_ARCHIVE`, etc.) instead of a free-form string.

Pros: compile-time validation of tier names, IDE autocomplete, no typos.

Cons: tier names are deployment-specific -- a CSP defines their own tiers via StorageTier resources (OSAC-1110). An enum would require a proto change every time a new tier is created, breaking the declarative model. The existing StorageTier API already validates names at runtime.

Rejected because: tier names are data, not code. Runtime validation against the StorageTier API is the correct approach.

## Test Plan

**Unit tests (fulfillment-service, Ginkgo):**
- `mergeBootDiskDefaults()` with and without `storage_tier` in template defaults.
- `validateBootDisk()` and `validateAdditionalDisks()` for missing and empty `storage_tier`.
- `validateStorageTierExists()` with mock StorageTier client (tier found, tier not found, client error).
- `addExplicitFields()` mapping `storage_tier` from proto to CRD for boot disk and additional disks.
- CatalogItem FieldDefinition with `boot_disk.storage_tier` path: default application, editability, JSON Schema validation.

**Unit tests (osac-operator, Ginkgo):**
- `validateDiskTiers()` with matching tiers, missing tiers, and empty `Tenant.Status.StorageClasses`.
- CRD validation: `StorageTier` required, pattern validation, immutability via XValidation.

**Integration tests (fulfillment-service, Kind cluster):**
- End-to-end ComputeInstance creation with explicit tiers, template defaults, and CatalogItem defaults.
- Validation error for nonexistent tier.
- Validation error when tier is missing after full resolution chain.

**E2E tests (osac-test-infra, pytest):**
- ComputeInstance provisioning with different tiers per disk.
- Verify DataVolumes use the correct per-disk StorageClasses.
- Error scenario: tier not available for tenant.

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages: Dev Preview -> Tech Preview -> GA based on production deployment feedback.

GA readiness signals:
- All unit, integration, and E2E tests pass.
- At least one CSP deployment has used per-disk tier selection for production tenants.
- Documentation covers storage tier setup as a provisioning prerequisite.

## Upgrade / Downgrade Strategy

**Upgrade**: This adds a required field (`storageTier`) to the `DiskSpec` CRD. Existing ComputeInstance CRs created before this change will not have the field. These CRs are immutable (the spec does not change after creation), so they will continue to function with the AAP playbook using the pre-existing single-tier resolution path until they are deleted.

New ComputeInstance CRs must include `storageTier`. All Templates and CatalogItems must be updated with tier values before or during the upgrade.

The upgrade sequence is:
1. Deploy updated CRDs (operator) -- adds the new field to the schema.
2. Update Templates and CatalogItems with `storage_tier` values.
3. Deploy updated fulfillment-service -- begins requiring and validating the field.
4. Deploy updated AAP roles -- begins per-disk tier resolution.

**Downgrade**: Reverting requires removing `storageTier` from CRDs. ComputeInstance CRs created with the new field must be deleted before downgrading the CRD, or the field will be silently stripped. The `STORAGE_REQUESTED_TIER` environment variable must be re-added to the AAP configuration.

## Version Skew Strategy

During a rolling upgrade, the fulfillment-service and operator may be at different versions:

- **Operator updated first (recommended)**: The new CRD accepts `storageTier`. The old fulfillment-service does not set it. Existing provisioning continues to work because the old AAP code still uses `STORAGE_REQUESTED_TIER`. New CRs created by the old fulfillment-service will lack `storageTier` but the CRD marks it as required -- CRD validation will reject them. Therefore, the fulfillment-service must be updated promptly after the CRD update.
- **Fulfillment-service updated first (not recommended)**: The new fulfillment-service sets `storageTier` in the proto, but the reconciler maps it to a CRD field that does not yet exist. The field is silently dropped. Provisioning falls back to the old `STORAGE_REQUESTED_TIER` path, which may select the wrong tier.

To minimize skew risk, deploy in this order: CRDs, operator, fulfillment-service, AAP roles.

## Support Procedures

**Detecting tier validation failures:**
- Fulfillment-service logs: gRPC error responses with `INVALID_ARGUMENT` mentioning `storage_tier`.
- Operator: `kubectl get computeinstance -o jsonpath='{.status.conditions}'` -- look for `Provisioned=False` with reason `StorageTierUnavailable`.
- AAP: job failure logs from the `tenant_storage_class` role when no StorageClass matches the requested tier.

**Verifying tenant StorageClass resolution:**
- `kubectl get tenant <name> -o jsonpath='{.status.storageClasses}'` shows resolved tiers.
- `kubectl get storageclass -l osac.openshift.io/tenant=<name>` shows tenant-specific StorageClasses.
- `kubectl get storageclass -l osac.openshift.io/storage-tier=<tier>` shows all StorageClasses for a given tier.

**Disabling the feature:**
The `storage_tier` field cannot be disabled independently -- it is part of the `DiskSpec` schema. To revert to the old single-tier behavior, downgrade all components following the downgrade strategy above.

Consequences of a partial deployment (e.g., CRD updated but fulfillment-service not yet updated): existing ComputeInstances continue to function. New ComputeInstance creation will fail if the fulfillment-service does not yet populate `storageTier` but the CRD requires it. This is a transient state during upgrade, not a failure mode.

## Infrastructure Needed

None.

---

## Provenance

Committed: commit @ design 0.3.0 - 92734a2, workspace main @ 0921467 (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"design","workflow_version":"0.3.0","ai_workflows":"92734a2","source_repo":"0921467 (dirty)","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false} -->
