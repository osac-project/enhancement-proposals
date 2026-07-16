# DiskImage Resource

| Field       | Value   |
|-------------|---------|
| Author(s)   | Marc Sluiter |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2540 |
| Service     | VMaaS |
| Date        | 2026-07-15 |

## Problem Statement

ComputeInstances reference images via raw OCI URLs, with no discoverability, no metadata, and no governance. Users must know exact OCI image references and registry tooling to create VMs. There is no curated list of available images, no access control over which images tenants can use, and no human-readable context for image selection. OS type is set per-instance rather than per-image, requiring users to specify it on every VM creation. The API and Kubernetes resource representations of OS type use different formats, creating inconsistency.

## In Scope

- DiskImage resource with CRUD operations (create, list, get, update, delete) via UI, CLI, and API
- DiskImage metadata: display name (required), description (optional), guest OS family (required, enum: linux, windows), architecture (required, enum: amd64, arm64)
- DiskImage wraps an existing OCI artifact reference (source_type + source_ref), both immutable after creation
- Two-tier visibility: provider-global images (available to all tenants) and tenant-scoped images (visible only within a tenant)
- Image lifecycle management: deprecation to warn users, obsolescence to block new VM creation, and reactivation
- ComputeInstance requires a DiskImage reference for image selection
- ComputeInstanceTemplate requires a DiskImage reference for image selection
- Inline image fields removed from ComputeInstance and ComputeInstanceTemplate — all image metadata lives on DiskImage
- OS type specified as an enum (linux, windows) replacing the current boolean Windows flag — consistent naming across API and Kubernetes resources
- Deletion protection: DiskImage deletion blocked when referenced by active ComputeInstances
- UI views: image list page, image picker in VM creation flow, image detail page, and lifecycle management controls
- API and CLI documentation for DiskImage operations

## Out of Scope

- Image upload API (binary upload through OSAC)
- Image caching or performance optimization
- VM snapshot/export
- Image scanning or CVE detection
- Image versioning/tagging
- os_version field (deferred)
- Minimum resource requirements field (deferred)
- BareMetalInstance integration (follow-up under OSAC-1270)
- Installation changes

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register an existing OCI image as a globally available DiskImage with display name, guest OS family, and architecture so that all tenants can discover and select it.
- As a Cloud Provider Admin, I want to list all registered images — both global and tenant-scoped — so that I can audit what is available across the platform.
- As a Cloud Provider Admin, I want to update mutable metadata (display name, description) of a global image so that I can keep the catalog accurate.
- As a Cloud Provider Admin, I want to deprecate a global image so that tenants are warned to migrate before the image becomes unavailable.
- As a Cloud Provider Admin, I want to mark a global image as obsolete so that new VM creation with that image is blocked while existing VMs remain unaffected.
- As a Cloud Provider Admin, I want to reactivate a previously deprecated or obsolete image so that tenants can resume using it if circumstances change.
- As a Cloud Provider Admin, I want to delete a global image that is no longer needed, with the system preventing deletion if active ComputeInstances reference it.
- As a Cloud Provider Admin, I want to reference a DiskImage in a ComputeInstanceTemplate so that VMs created from the template use approved images by default.
- As a Cloud Provider Admin, I want to manage DiskImages through the UI console so that I can register, update, deprecate, and delete images without CLI or API tooling.

### Cloud Infrastructure Admin

- Not affected by this feature.

### Tenant Admin

- As a Tenant Admin, I want to register tenant-scoped DiskImages for my organization so that my users can select from our approved images.
- As a Tenant Admin, I want to update mutable metadata and delete my tenant's images, with the system preventing deletion if active ComputeInstances reference them.
- As a Tenant Admin, I want to deprecate, obsolete, and reactivate my tenant's images so that I can manage my organization's image lifecycle.
- As a Tenant Admin, I want to reference a DiskImage in a ComputeInstanceTemplate so that VMs created from the template use my organization's approved images by default.
- As a Tenant Admin, I want to manage my tenant's DiskImages through the UI console so that I can register, update, and delete images without CLI or API tooling.

### Tenant User

- As a Tenant User, I want to see only images available to my tenant (global and my tenant's own) so that I cannot access other tenants' images.
- As a Tenant User, I want to browse available images with metadata (display name, description, guest OS family, architecture) so that I can choose the right image for my VM.
- As a Tenant User, I want to search and filter images by guest OS family, architecture, or name so that I can quickly find what I need.
- As a Tenant User, I want to reference a DiskImage when creating a ComputeInstance so that image source and OS type are resolved automatically.
- As a Tenant User, I want to see a deprecation warning when selecting a deprecated image so that I know to choose a different image.
- As a Tenant User, I want to browse and select DiskImages in the UI when creating a ComputeInstance so that I can choose the right image visually.

## Assumptions

- OSAC does not currently support upgrades, so backward compatibility for existing ComputeInstances using the current boolean Windows flag is not a concern.

## Related Features

- **[OSAC-979](https://redhat.atlassian.net/browse/OSAC-979): VM Image Management** — broader vision including upload, caching, and performance optimization. This feature is a prerequisite building block.
- **[OSAC-1270](https://redhat.atlassian.net/browse/OSAC-1270): Base OS management for bare metal instances** — follow-up: add DiskImage reference to BareMetalInstance. The DiskImage resource is named to be service-neutral for this reason.

---

## Provenance

Authored: draft @ prd 0.5.0 - 883316f, workspace main @ 7ea4384
Final: respond @ prd 0.5.0 - 883316f, workspace main @ 777ba84 (2 behind origin/main)

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"883316f","source_repo":"777ba84","source_repo_branch":"main","commits_behind_main":2,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","revise","respond"],"authoring_modes":["skill"],"context_changed":true} -->
