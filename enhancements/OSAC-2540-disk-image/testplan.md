# Testplan — OSAC-2540

## Overview

- **Feature:** OSAC-2540 — DiskImage resource for disk image metadata management
- **Total test cases:** 32
- **Requirements covered:** 14 of 15 in scope (FR-1 through FR-13, NFR-2; NFR-1 pending OSAC-2921)

## Test Cases

### FR-1: DiskImage CRUD (create, list, get, update, delete) via UI, CLI, API

#### TC-FR1-01: Create DiskImage with required fields

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-1, AC-2 | critical | automated |

##### Preconditions

- Authenticated as Cloud Provider Admin
- fulfillment-service running

##### Steps

1. Call `DiskImages/Create` with source_type=REGISTRY, source_ref="quay.io/containerdisks/fedora:41", guest_os_family=LINUX, architecture=[AMD64]
2. Verify response contains system-generated id and metadata

##### Expected Results

- Response status 200 OK
- Response contains DiskImage with non-empty `id`, `metadata.creation_timestamp` set, `spec.lifecycle` = AVAILABLE, `spec.guest_os_family` = LINUX

#### TC-FR1-02: List DiskImages

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-6 | high | automated |

##### Preconditions

- At least one DiskImage exists

##### Steps

1. Call `DiskImages/List` with no filter
2. Verify response contains the created DiskImage

##### Expected Results

- Response contains a list including the previously created DiskImage
- OBSOLETE images are excluded from results

#### TC-FR1-03: Get DiskImage by ID

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-1 | high | automated |

##### Preconditions

- DiskImage exists with known ID

##### Steps

1. Call `DiskImages/Get` with the DiskImage ID

##### Expected Results

- Response contains the DiskImage with all fields matching what was created (source_type, source_ref, guest_os_family, architecture, lifecycle)

#### TC-FR1-04: Update DiskImage mutable fields

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-3 | high | automated |

##### Preconditions

- DiskImage exists in AVAILABLE state

##### Steps

1. Call `DiskImages/Update` changing architecture to [AMD64, ARM64]
2. Call `DiskImages/Get` to verify update

##### Expected Results

- Response status 200 OK
- Architecture updated to [AMD64, ARM64]
- source_type, source_ref, guest_os_family unchanged

#### TC-FR1-05: Delete unreferenced DiskImage

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-5 | high | automated |

##### Preconditions

- DiskImage exists with no referencing ComputeInstances, Templates, or CatalogItems

##### Steps

1. Call `DiskImages/Delete` with the DiskImage ID
2. Call `DiskImages/Get` with the same ID

##### Expected Results

- Delete returns success
- Subsequent Get returns NotFound

#### TC-FR1-06: CLI create and list DiskImage

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3719 | AC-1, AC-2 | high | automated |

##### Preconditions

- Authenticated via `osac login`
- fulfillment-service running

##### Steps

1. Run `osac disk-images create --source-type registry --source-ref "quay.io/containerdisks/fedora:41" --guest-os-family linux --architecture amd64`
2. Run `osac disk-images list`
3. Run `osac disk-images get <id>` using the ID from step 1

##### Expected Results

- Step 1: DiskImage created, ID printed
- Step 2: Table output includes the created DiskImage with columns: name, guest OS family, architecture, lifecycle
- Step 3: Full DiskImage details printed including source_ref and guest_os_family

### FR-2: DiskImage metadata: guest_os_family (required enum), architecture (required repeated enum)

#### TC-FR2-01: Create DiskImage validates required metadata

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-2 | critical | automated |

##### Preconditions

- Authenticated as Cloud Provider Admin

##### Steps

1. Call `DiskImages/Create` with empty source_ref
2. Call `DiskImages/Create` with empty architecture list
3. Call `DiskImages/Create` with valid fields

##### Expected Results

- Step 1: InvalidArgument error mentioning source_ref
- Step 2: InvalidArgument error mentioning architecture
- Step 3: DiskImage created with guest_os_family defaulted to LINUX

### FR-3: DiskImage wraps OCI artifact reference, immutable after creation

#### TC-FR3-01: Immutable fields rejected on update

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-3 | critical | automated |

##### Preconditions

- DiskImage exists with source_type=REGISTRY, source_ref="quay.io/test:v1", guest_os_family=LINUX

##### Steps

1. Call `DiskImages/Update` attempting to change source_ref to "quay.io/test:v2"
2. Call `DiskImages/Update` attempting to change guest_os_family to WINDOWS
3. Call `DiskImages/Update` attempting to change source_type

##### Expected Results

- All three updates return InvalidArgument with message identifying the immutable field
- DiskImage remains unchanged

### FR-4: Two-tier visibility: provider-global and tenant-scoped

#### TC-FR4-01: Global DiskImage visible to all tenants

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3720 | AC-1, AC-3 | critical | automated |

##### Preconditions

- Global DiskImage created by Cloud Provider Admin (metadata.tenant empty)
- Users in Tenant A and Tenant B exist

##### Steps

1. List DiskImages as Tenant A user
2. List DiskImages as Tenant B user

##### Expected Results

- Both users see the global DiskImage in their list results

#### TC-FR4-02: Tenant-scoped DiskImage isolated to its tenant

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3720 | AC-3, AC-4, AC-5 | critical | automated |

##### Preconditions

- Tenant-scoped DiskImage created in Tenant A

##### Steps

1. List DiskImages as Tenant A user — verify DiskImage visible
2. List DiskImages as Tenant B user — verify DiskImage not visible
3. Get DiskImage by ID as Tenant B user

##### Expected Results

- Tenant A user sees the DiskImage
- Tenant B user does not see it in list results
- Tenant B Get returns NotFound

### FR-5: Tenant Users can create, update, and delete tenant-scoped DiskImages

#### TC-FR5-01: Tenant User CRUD on tenant-scoped DiskImage

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3720 | AC-6 | high | automated |

##### Preconditions

- Authenticated as Tenant User (not admin) in Tenant A

##### Steps

1. Create a tenant-scoped DiskImage
2. Update mutable metadata on the created DiskImage
3. Delete the DiskImage

##### Expected Results

- Create succeeds, DiskImage has metadata.tenant set to Tenant A
- Update succeeds
- Delete succeeds (no references exist)

### FR-6: Lifecycle management: deprecation, obsolescence, reactivation

#### TC-FR6-01: Deprecation with auto-set timestamp

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-4 | critical | automated |

##### Preconditions

- DiskImage exists in AVAILABLE state

##### Steps

1. Call `DiskImages/Update` setting lifecycle to DEPRECATED
2. Get the DiskImage

##### Expected Results

- Lifecycle is DEPRECATED
- `spec.deprecation.deprecation_timestamp` is set to approximately current time
- `spec.deprecation.obsolescence_timestamp` is not set

#### TC-FR6-02: Obsolescence with auto-set timestamp

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-4 | critical | automated |

##### Preconditions

- DiskImage in DEPRECATED state with deprecation_timestamp set

##### Steps

1. Call `DiskImages/Update` setting lifecycle to OBSOLETE
2. Get the DiskImage

##### Expected Results

- Lifecycle is OBSOLETE
- `spec.deprecation.obsolescence_timestamp` is set to approximately current time
- `spec.deprecation.deprecation_timestamp` remains set

#### TC-FR6-03: Reactivation clears deprecation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-4 | high | automated |

##### Preconditions

- DiskImage in OBSOLETE state with both timestamps set

##### Steps

1. Call `DiskImages/Update` setting lifecycle to AVAILABLE
2. Get the DiskImage

##### Expected Results

- Lifecycle is AVAILABLE
- `spec.deprecation` field is cleared (both timestamps gone)

### FR-7: ComputeInstance references DiskImage instead of inline image fields

#### TC-FR7-01: Create ComputeInstance with DiskImage reference

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-1, AC-2 | critical | automated |

##### Preconditions

- AVAILABLE DiskImage exists with guest_os_family=LINUX, source_ref="quay.io/containerdisks/fedora:41"
- ComputeInstanceTemplate exists

##### Steps

1. Create ComputeInstance with spec.disk_image set to the DiskImage ID
2. Get the created ComputeInstance

##### Expected Results

- ComputeInstance created with spec.disk_image set to the DiskImage ID
- No inline image or is_windows fields on the ComputeInstance

#### TC-FR7-02: ComputeInstance creation fails without disk_image

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-1 | critical | automated |

##### Preconditions

- ComputeInstanceTemplate exists without disk_image default

##### Steps

1. Create ComputeInstance without spec.disk_image and without template providing a default

##### Expected Results

- InvalidArgument error indicating disk_image is required

#### TC-FR7-03: Reconciler resolves DiskImage to CRD fields

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3724 | AC-1, AC-2, AC-3 | critical | automated |

##### Preconditions

- DiskImage exists with source_type=REGISTRY, source_ref="quay.io/containerdisks/fedora:41", guest_os_family=LINUX
- ComputeInstance created referencing this DiskImage

##### Steps

1. Wait for reconciler to process the ComputeInstance
2. Inspect the resulting Kubernetes CR

##### Expected Results

- CR has ImageSpec.SourceType matching DiskImage source_type
- CR has ImageSpec.SourceRef = "quay.io/containerdisks/fedora:41"
- CR has GuestOSFamily = "linux"

### FR-8: ComputeInstanceTemplate references DiskImage for defaults

#### TC-FR8-01: Template disk_image default applied to ComputeInstance

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-6 | high | automated |

##### Preconditions

- DiskImage exists
- ComputeInstanceTemplate created with spec_defaults.disk_image set to the DiskImage ID

##### Steps

1. Create ComputeInstance from template without specifying disk_image

##### Expected Results

- ComputeInstance created with spec.disk_image set to the template's default DiskImage ID

#### TC-FR8-02: Template Create rejects nonexistent DiskImage reference

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3727 | AC-1 | high | automated |

##### Preconditions

- No DiskImage with ID "nonexistent-id" exists

##### Steps

1. Create ComputeInstanceTemplate with spec_defaults.disk_image = "nonexistent-id"

##### Expected Results

- InvalidArgument or NotFound error indicating the referenced DiskImage does not exist
- Template not created

### FR-9: ComputeInstanceCatalogItem references DiskImage for image defaults

#### TC-FR9-01: CatalogItem disk_image field_definition applied

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3728 | AC-1 | high | automated |

##### Preconditions

- DiskImage exists
- CatalogItem created with field_definition for spec.disk_image with default set to DiskImage ID

##### Steps

1. Create ComputeInstance from catalog item without specifying disk_image

##### Expected Results

- ComputeInstance created with spec.disk_image set to the CatalogItem's default DiskImage ID

#### TC-FR9-02: CatalogItem rejects cross-tenant DiskImage reference

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3728 | AC-3 | high | automated |

##### Preconditions

- DiskImage exists in Tenant A
- Creating CatalogItem in Tenant B

##### Steps

1. Create CatalogItem in Tenant B with field_definition referencing Tenant A's DiskImage

##### Expected Results

- InvalidArgument error indicating cross-tenant reference not allowed

### FR-10: Inline image fields removed from ComputeInstance and ComputeInstanceTemplate

#### TC-FR10-01: Old image and is_windows fields not present

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3722 | AC-1 | medium | automated |

##### Preconditions

- Updated proto definitions compiled

##### Steps

1. Verify ComputeInstanceSpec proto no longer has `image` (field 4) or `is_windows` (field 16) — fields are reserved
2. Verify ComputeInstanceTemplateSpecDefaults proto no longer has `image` (field 3) or `is_windows` (field 7) — fields are reserved

##### Expected Results

- Fields 4, 16 on ComputeInstanceSpec are reserved
- Fields 3, 7 on ComputeInstanceTemplateSpecDefaults are reserved
- New disk_image field (field 18 / field 8) present on each

### FR-12: Deletion protection when referenced by active resources

#### TC-FR12-01: Cannot delete DiskImage referenced by ComputeInstance

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-5 | critical | automated |

##### Preconditions

- DiskImage created
- ComputeInstance created referencing this DiskImage

##### Steps

1. Attempt to delete the DiskImage

##### Expected Results

- FailedPrecondition error with message identifying the referencing ComputeInstance

#### TC-FR12-02: Cannot delete DiskImage referenced by Template

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3727 | AC-3 | high | automated |

##### Preconditions

- DiskImage created
- ComputeInstanceTemplate created with disk_image default referencing this DiskImage

##### Steps

1. Attempt to delete the DiskImage

##### Expected Results

- FailedPrecondition error with message identifying the referencing Template

#### TC-FR12-03: Cannot delete DiskImage referenced by CatalogItem

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-5 | high | automated |

##### Preconditions

- DiskImage created
- CatalogItem created with field_definition referencing this DiskImage

##### Steps

1. Attempt to delete the DiskImage

##### Expected Results

- FailedPrecondition error with message identifying the referencing CatalogItem

#### TC-FR12-04: DiskImage deletion succeeds after references removed

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-5 | high | automated |

##### Preconditions

- DiskImage referenced by ComputeInstance
- Deletion previously blocked

##### Steps

1. Delete the referencing ComputeInstance
2. Retry deleting the DiskImage

##### Expected Results

- ComputeInstance deletion succeeds
- DiskImage deletion succeeds

### FR-13: Obsolete images hidden from default list, available via filter

#### TC-FR13-01: OBSOLETE images excluded from default list

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-6 | high | automated |

##### Preconditions

- DiskImage A in AVAILABLE state
- DiskImage B in OBSOLETE state

##### Steps

1. Call `DiskImages/List` with no filter

##### Expected Results

- Response includes DiskImage A
- Response does not include DiskImage B

#### TC-FR13-02: OBSOLETE images visible with explicit filter

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3718 | AC-6 | medium | automated |

##### Preconditions

- DiskImage in OBSOLETE state

##### Steps

1. Call `DiskImages/List` with filter `this.spec.lifecycle == 3`

##### Expected Results

- Response includes the OBSOLETE DiskImage

#### TC-FR7-06: Cross-tenant DiskImage reference rejected on ComputeInstance creation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-3 | critical | automated |

##### Preconditions

- DiskImage exists in Tenant A (tenant-scoped)
- Authenticated as Tenant User in Tenant B

##### Steps

1. Create ComputeInstance in Tenant B with spec.disk_image referencing Tenant A's DiskImage

##### Expected Results

- NotFound error (Tenant B cannot resolve Tenant A's DiskImage)
- No ComputeInstance created

### FR-7 (continued): OBSOLETE and DEPRECATED DiskImage behavior on ComputeInstance creation

#### TC-FR7-04: OBSOLETE DiskImage blocks ComputeInstance creation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-4 | critical | automated |

##### Preconditions

- DiskImage in OBSOLETE state

##### Steps

1. Create ComputeInstance with spec.disk_image referencing the OBSOLETE DiskImage

##### Expected Results

- FailedPrecondition error: "cannot create compute instance: disk image is obsolete"

#### TC-FR7-05: DEPRECATED DiskImage allows creation with warning

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3723 | AC-5 | high | automated |

##### Preconditions

- DiskImage in DEPRECATED state

##### Steps

1. Create ComputeInstance with spec.disk_image referencing the DEPRECATED DiskImage

##### Expected Results

- ComputeInstance created
- Response warnings list contains "disk image '<id>' is deprecated"

### NFR-1: Display name and description inherited from shared Metadata

No standalone test case — OSAC-2921 dependency. DiskImage uses Metadata fields when available. Verified by inspecting DiskImage responses in FR-1 test cases.

### NFR-2: Consistent OS type naming across API and Kubernetes resources

#### TC-NFR2-01: GuestOSFamily mapping consistency

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| OSAC-3724 | AC-3 | high | automated |

##### Preconditions

- DiskImage with guest_os_family=WINDOWS exists
- ComputeInstance referencing this DiskImage

##### Steps

1. Wait for reconciler to process
2. Inspect the resulting CR's GuestOSFamily field

##### Expected Results

- CRD GuestOSFamily = "windows" (matching the proto enum GUEST_OS_FAMILY_WINDOWS)
- No is_windows boolean present on the CR

## Gaps

- **NFR-1:** No standalone test case — dependent on OSAC-2921 (shared Metadata display_name/description). DiskImage uses standard Metadata fields; validation occurs naturally in FR-1 CRUD tests once OSAC-2921 lands.
- **FR-14 (UI views):** Out of scope for this decomposition.
- **FR-15 (Documentation):** Out of scope for this decomposition.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 32 |
| Critical | 13 |
| High | 17 |
| Medium | 2 |
| Low | 0 |
| Automated | 32 |
| Manual | 0 |
| Requirements with test cases | 14 / 15 in scope |
| Requirements without test cases | 1 (NFR-1 — pending OSAC-2921; FR-14 and FR-15 out of scope) |
