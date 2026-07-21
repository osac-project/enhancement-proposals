# Base OS Management for Bare Metal Instances

| Field     | Value                                                        |
|-----------|--------------------------------------------------------------|
| Author(s) | Adrien Gentil                                                |
| Jira      | https://redhat.atlassian.net/browse/OSAC-1270                |
| Date      | 2026-07-21                                                   |

## Problem Statement

This PRD covers the integration of the DiskImage resource (defined in [OSAC-2540](https://redhat.atlassian.net/browse/OSAC-2540)) into BMaaS. It does not change DiskImage behavior — that is fully specified in OSAC-2540.

Bare metal instances can reference a custom OS image today, but only as a raw URL string with no discoverability, metadata, or governance. Tenants must know the exact image URL to use it; there is no curated catalog to browse, no lifecycle management to signal when an image is deprecated or unsupported, and no scoping to control which images are available per tenant. Cloud Provider Admins and Tenant Admins have no structured surface to publish and manage OS images independently. If unaddressed, bare metal provisioning remains opaque and error-prone, with tenants unable to discover what images are available and no guard against use of stale or unsupported images.

## In Scope

- Tenants can browse the list of available OS images with metadata (title, description, guest OS family, architecture) via the UI and API.
- A DiskImage reference is mandatory when creating a BaremetalInstance; the instance is provisioned with the OS from that image.
- Deprecated DiskImages display a warning when selected; obsolete DiskImages are hidden from the default image list (accessible via explicit filter) and cannot be used for new bare metal instances.
- Cloud Provider Admins can register, update, deprecate, obsolete, reactivate, and delete global DiskImages available to all tenants for bare metal provisioning.
- Tenant Admins can register, update, deprecate, obsolete, reactivate, and delete tenant-scoped DiskImages visible only within their organization. Deletion is blocked when active BaremetalInstances or BaremetalInstanceCatalogItems reference the image.
- UI support for the full DiskImage lifecycle (image list, image picker in BaremetalInstance creation, image detail, and lifecycle management controls) for all affected personas.
- DiskImages for bare metal use the same resource, metadata schema, image source format, and two-tier visibility model (global + tenant-scoped) as defined in OSAC-2540.

## Out of Scope

- Custom OS image upload by tenants — images are curated and published by Cloud Provider Admins or Tenant Admins only.
- In-place OS upgrade (package-level) — OS image selection applies at provision time only.
- OS configuration management beyond initial boot (e.g., configuration drift detection).
- BaremetalInstanceTemplate — no DiskImage field on the template.
- BaremetalInstanceCatalogItem schema changes — the catalog item's existing parameter model is sufficient to accept a DiskImage reference without structural changes.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a BaremetalInstanceCatalogItem that references a default DiskImage so that bare metal instances created from it are provisioned with an approved OS image by default.
- As a Cloud Provider Admin, I want DiskImage deletion to be blocked when active BaremetalInstances or BaremetalInstanceCatalogItems reference it, so that I do not inadvertently break running workloads or catalog offerings.

### Tenant Admin

- As a Tenant Admin, I want to create a BaremetalInstanceCatalogItem that references a default DiskImage so that bare metal instances created from it are provisioned with an approved OS image by default.
- As a Tenant Admin, I want DiskImage deletion to be blocked when active BaremetalInstances or BaremetalInstanceCatalogItems reference it, so that I do not inadvertently break running workloads or catalog offerings.

### Tenant User

- As a Tenant User, I want to select a DiskImage when creating a bare metal instance so that the instance is provisioned with my chosen OS.

## Dependencies

- **OSAC-2540 — DiskImage resource:** Defines and implements the DiskImage API resource, metadata schema, two-tier visibility (global + tenant-scoped), image lifecycle (active → deprecated → obsolete, reactivation), and image source format. This feature extends DiskImage to BaremetalInstance and must land after OSAC-2540.
- **OSAC-1118 — Baremetal OSAC API:** Closed. Provides the BaremetalInstance lifecycle foundation (create → provisioning → ready → deprovision → deleted) that this feature extends with OS image selection.

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ aac0f8e

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"aac0f8e","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
