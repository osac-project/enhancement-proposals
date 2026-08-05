# Testplan — OSAC-1710

## Overview

- **Feature:** OSAC-1710 — ComputeInstance StorageTier Selection
- **Total test cases:** 18
- **Requirements covered:** 8 of 8 (FR-1 through FR-7, NFR-1)

## Test Cases

### FR-1: Storage tier selection for ComputeInstance disks (boot disk and additional disks)

#### TC-FR1-01: Create ComputeInstance with explicit boot disk tier

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.01 | AC-1 | critical | automated |

##### Preconditions

- StorageTier "fast" exists
- Tenant has a StorageClass mapped to tier "fast"
- A CatalogItem or Template is available for the tenant

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "fast"}` and no additional disks

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` set to `"fast"`
- The boot disk DataVolume uses the StorageClass mapped to tier "fast" for the tenant

#### TC-FR1-02: Create ComputeInstance with explicit additional disk tiers

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.01 | AC-1 | critical | automated |

##### Preconditions

- StorageTiers "fast" and "archive" exist
- Tenant has StorageClasses mapped to both tiers

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "fast"}` and `additional_disks: [{size_gib: 200, storage_tier: "archive"}]`

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` = `"fast"` and `additional_disks[0].storage_tier` = `"archive"`
- Boot disk DataVolume uses the StorageClass for "fast"; additional disk DataVolume uses the StorageClass for "archive"

### FR-2: Storage tier is mandatory — provisioning fails if no tier is resolved

#### TC-FR2-01: Boot disk tier missing after full resolution chain

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-3 | critical | automated |

##### Preconditions

- A CatalogItem exists with no FieldDefinition for `boot_disk.storage_tier`
- The associated Template has `boot_disk: {size_gib: 50}` (no `storage_tier`)

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100}` (no `storage_tier`)

##### Expected Results

- API returns gRPC status `INVALID_ARGUMENT`
- Error message is `"boot_disk.storage_tier is required but was not provided by user input, catalog item defaults, or template defaults"`
- No ComputeInstance is created

#### TC-FR2-02: Additional disk tier missing

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-4 | critical | automated |

##### Preconditions

- StorageTier "fast" exists
- Tenant has a StorageClass mapped to tier "fast"

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "fast"}` and `additional_disks: [{size_gib: 200}]` (no `storage_tier` on the additional disk)

##### Expected Results

- API returns gRPC status `INVALID_ARGUMENT`
- Error message is `"additional_disks[0].storage_tier is required"`
- No ComputeInstance is created

### FR-3: Boot disk and each additional disk can use different tiers independently

#### TC-FR3-01: Different tiers per disk resolve to different StorageClasses

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.04 | AC-2, AC-3 | critical | automated |

##### Preconditions

- StorageTiers "fast", "standard", and "archive" exist
- Tenant has StorageClasses mapped to all three tiers

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "fast"}` and `additional_disks: [{size_gib: 200, storage_tier: "standard"}, {size_gib: 500, storage_tier: "archive"}]`
2. Wait for provisioning to complete
3. Inspect the created DataVolumes

##### Expected Results

- Three DataVolumes are created
- Boot disk DataVolume has `storageClassName` matching the "fast" tier StorageClass for the tenant (e.g., `netapp-fast-tenant-abc`)
- First additional disk DataVolume has `storageClassName` matching the "standard" tier StorageClass
- Second additional disk DataVolume has `storageClassName` matching the "archive" tier StorageClass

### FR-4: Validation that the requested tier exists at request time

#### TC-FR4-01: Nonexistent tier is rejected at request time

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-5 | critical | automated |

##### Preconditions

- No StorageTier named "nonexistent" exists in the system

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "nonexistent"}`

##### Expected Results

- API returns gRPC status `INVALID_ARGUMENT`
- Error message is `"storage tier \"nonexistent\" does not exist"`
- No ComputeInstance is created

#### TC-FR4-02: Tier exists globally but not available for tenant

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-2, AC-3 | high | automated |

##### Preconditions

- StorageTier "premium" exists globally
- Tenant does NOT have a StorageClass mapped to tier "premium" (no entry in `tenant.Status.StorageClasses`)

##### Steps

1. Create a ComputeInstance with `boot_disk: {size_gib: 100, storage_tier: "premium"}`
2. Wait for the operator to process the ComputeInstance CR

##### Expected Results

- ComputeInstance is created (passes fulfillment-service validation since the tier exists)
- Operator sets `Provisioned=False` condition with a message identifying that tier "premium" has no StorageClass for the tenant
- No AAP job is triggered

### FR-5: Tier resolution precedence (user > CatalogItem > Template)

#### TC-FR5-01: Boot disk tier resolved from CatalogItem default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-6 | high | automated |

##### Preconditions

- A CatalogItem with FieldDefinition: `path: "boot_disk.storage_tier"`, `default: "standard"`
- StorageTier "standard" exists

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100}` (no `storage_tier`)

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` set to `"standard"` (from CatalogItem default)

#### TC-FR5-02: Boot disk tier resolved from Template default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-1, AC-2 | high | automated |

##### Preconditions

- A CatalogItem with no FieldDefinition for `boot_disk.storage_tier`
- Associated Template with `boot_disk: {size_gib: 50, storage_tier: "standard"}`
- StorageTier "standard" exists

##### Steps

1. Create a ComputeInstance using this CatalogItem with no `boot_disk` (field omitted entirely)

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` set to `"standard"` (from Template default) and `boot_disk.size_gib` set to `50`

#### TC-FR5-03: User-provided tier overrides CatalogItem default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-1 | high | automated |

##### Preconditions

- A CatalogItem with FieldDefinition: `path: "boot_disk.storage_tier"`, `default: "standard"`, `editable: true`
- StorageTiers "standard" and "fast" exist

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100, storage_tier: "fast"}`

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` set to `"fast"` (user value preserved, CatalogItem default ignored)

#### TC-FR5-04: Additional disks defaulted from CatalogItem

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-6 | high | automated |

##### Preconditions

- A CatalogItem with FieldDefinition: `path: "additional_disks"`, `default: [{size_gib: 500, storage_tier: "fast"}]`
- StorageTiers "standard" and "fast" exist

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100, storage_tier: "standard"}` and no `additional_disks` (field omitted)

##### Expected Results

- ComputeInstance is created with `boot_disk.storage_tier` = `"standard"` and `additional_disks: [{size_gib: 500, storage_tier: "fast"}]` (from CatalogItem default)

#### TC-FR5-05: User-provided additional disks replace CatalogItem default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-6 | medium | automated |

##### Preconditions

- A CatalogItem with FieldDefinition: `path: "additional_disks"`, `default: [{size_gib: 500, storage_tier: "fast"}]`
- StorageTiers "standard" and "archive" exist

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100, storage_tier: "standard"}` and `additional_disks: [{size_gib: 200, storage_tier: "archive"}]`

##### Expected Results

- ComputeInstance is created with `additional_disks: [{size_gib: 200, storage_tier: "archive"}]` (user value replaces CatalogItem default entirely)

#### TC-FR5-06: Empty additional disks array opts out of CatalogItem default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.02 | AC-6 | medium | automated |

##### Preconditions

- A CatalogItem with FieldDefinition: `path: "additional_disks"`, `default: [{size_gib: 500, storage_tier: "fast"}]`
- StorageTier "standard" exists

##### Steps

1. Create a ComputeInstance using this CatalogItem with `boot_disk: {size_gib: 100, storage_tier: "standard"}` and `additional_disks: []` (explicit empty array)

##### Expected Results

- ComputeInstance is created with no additional disks (empty array overrides CatalogItem default)

### FR-6: Tier assignment immutability after ComputeInstance creation

#### TC-FR6-01: Storage tier cannot be changed after creation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.01 | AC-4 | high | automated |

##### Preconditions

- A ComputeInstance exists with `boot_disk.storage_tier: "standard"`

##### Steps

1. Attempt to update the ComputeInstance's `boot_disk.storage_tier` to `"fast"`

##### Expected Results

- The update is rejected by CRD validation with a message indicating that `bootDisk` is immutable (via `XValidation:rule="self == oldSelf"`)
- The ComputeInstance's `boot_disk.storage_tier` remains `"standard"`

### FR-7: UI support for tier selection

#### TC-FR7-01: UI tier selector displays available tiers

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-1, AC-3 | high | automated |

##### Preconditions

- StorageTiers "fast", "standard", and "archive" exist
- User is on the ComputeInstance creation form

##### Steps

1. Navigate to the ComputeInstance creation form
2. Locate the boot disk storage tier selector
3. Open the tier dropdown

##### Expected Results

- The dropdown shows three options: "fast", "standard", "archive"
- Options are populated from the StorageTier API

#### TC-FR7-02: UI displays API validation errors for invalid tier

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-6 | medium | automated |

##### Preconditions

- User is on the ComputeInstance creation form

##### Steps

1. Fill in the ComputeInstance creation form with a valid boot disk size but manipulate the request to include a nonexistent tier (e.g., via browser dev tools or by deleting the tier after form validation)
2. Submit the form

##### Expected Results

- The form displays an inline error message on the boot disk tier field indicating the tier does not exist
- No ComputeInstance is created

### NFR-1: Documentation updates

#### TC-NFR1-01: Documentation covers tier resolution precedence

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.06 | AC-1, AC-2 | medium | manual |

##### Preconditions

- Documentation has been published

##### Steps

1. Read the storage tier selection documentation
2. Locate the section on tier resolution precedence

##### Expected Results

- Documentation describes the three-level precedence chain: user input > CatalogItem defaults > Template defaults
- Documentation includes examples of configuring tier defaults in Templates and CatalogItems

#### TC-NFR1-02: Documentation covers troubleshooting

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.06 | AC-4 | medium | manual |

##### Preconditions

- Documentation has been published

##### Steps

1. Read the storage tier selection documentation
2. Locate the troubleshooting section

##### Expected Results

- Documentation describes how to diagnose tier validation failures at the fulfillment-service level (gRPC error responses mentioning `storage_tier`)
- Documentation describes how to diagnose operator-level failures (`Provisioned=False` condition)
- Documentation includes commands: `kubectl get tenant <name> -o jsonpath='{.status.storageClasses}'`, `kubectl get storageclass -l osac.openshift.io/storage-tier=<tier>`

## Gaps

All covered requirements have test cases and all story ACs are mapped to test cases.

Note: Tier validation is two-layered. TC-FR4-01 tests fulfillment-service validation (tier does not exist globally, rejected at API level). TC-FR4-02 tests operator-level validation (tier exists globally but has no StorageClass for the tenant, detected after CR creation). These are distinct error paths at different layers.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 18 |
| Critical | 6 |
| High | 7 |
| Medium | 5 |
| Low | 0 |
| Automated | 16 |
| Manual | 2 |
| Requirements with test cases | 8 / 8 |
| Requirements without test cases | 0 |
