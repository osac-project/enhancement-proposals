---
prd_id: OSAC-1270
title: Base OS Management for Bare-Metal Instances
jira_key: OSAC-1270
status: Draft
---
# Base OS Management for Bare-Metal Instances

| Field       | Value                                                        |
|-------------|--------------------------------------------------------------|
| Author(s)   | Adrien Gentil                                                |
| Jira        | [OSAC-1270](https://redhat.atlassian.net/browse/OSAC-1270)   |
| Date        | 2026-07-26                                                   |

## Problem Statement

This PRD covers the integration of the DiskImage resource (defined in [OSAC-2540](https://redhat.atlassian.net/browse/OSAC-2540)) into BMaaS. It does not change DiskImage behavior — that is fully specified in OSAC-2540.

Bare metal instances can reference a custom OS image today, but only as a raw URL string with no discoverability, metadata, or governance. Tenants must know the exact image URL to use it; there is no curated catalog to browse, no lifecycle management to signal when an image is deprecated or unsupported, and no scoping to control which images are available per tenant. Cloud Provider Admins and Tenant Admins have no structured surface to publish and manage OS images independently. If unaddressed, bare metal provisioning remains opaque and error-prone, with tenants unable to discover what images are available and no guard against use of stale or unsupported images.

## In Scope

- A BaremetalInstance must have an effective DiskImage reference at creation time — either explicitly selected by the user or defaulted from the BaremetalInstanceCatalogItem. Creation is rejected when neither provides a reference. The instance is provisioned with the OS from that image.
- DiskImage deletion is blocked when any BaremetalInstance (in any non-deleted state) or any BaremetalInstanceCatalogItem references it — applied to both global and tenant-scoped DiskImages.
- UI/API support for selecting and resolving eligible DiskImages during bare-metal instance creation; DiskImage browsing, lifecycle management, and lifecycle UI are defined by OSAC-2540.
- E2E test coverage for DiskImage selection at bare-metal instance provision time, added to the existing bare-metal test suite.
- DiskImages for bare-metal instances reuse the same resource, metadata schema, image source format, and two-tier visibility model (global + tenant-scoped) as defined in OSAC-2540.

## Out of Scope

- Custom OS image upload by tenants — images are curated and published by Cloud Provider Admins or Tenant Admins only.
- In-place OS upgrade (package-level) — OS image selection applies at provision time only.
- OS configuration management beyond initial boot (e.g., configuration drift detection).
- BaremetalInstanceTemplate — no DiskImage field on the template.
- BaremetalInstanceCatalogItem schema changes — the catalog item's existing parameter model is sufficient to accept a DiskImage reference without structural changes.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a BaremetalInstanceCatalogItem that references a global DiskImage as default so that all tenants provisioning bare-metal instances from it receive a platform-approved OS image without having to select one.
- As a Cloud Provider Admin, I want DiskImage deletion to be blocked when any BaremetalInstance or BaremetalInstanceCatalogItem references it, so that I do not inadvertently break running workloads or catalog offerings.

### Cloud Infrastructure Admin

Not affected by this feature. Cloud Infrastructure Admins manage core infrastructure (network, storage, compute backends) and are not involved in OS image selection or catalog management for bare-metal instances.

### Tenant Admin

- As a Tenant Admin, I want to create a BaremetalInstanceCatalogItem that references one of my organization's DiskImages as default so that my users' bare-metal instances are provisioned with our approved OS image without requiring manual selection.
- As a Tenant Admin, I want DiskImage deletion to be blocked when any BaremetalInstance or BaremetalInstanceCatalogItem references it, so that I do not inadvertently break running workloads or catalog offerings.

### Tenant User

- As a Tenant User, I want to select a DiskImage when creating a bare metal instance so that the instance is provisioned with my chosen OS.

## Dependencies

- **OSAC-2540 (DiskImage resource):** Defines and implements the DiskImage API resource, metadata schema, two-tier visibility (global + tenant-scoped), image lifecycle (active, deprecated, obsolete, reactivation), and image source format. This feature extends DiskImage to BaremetalInstance and must land after OSAC-2540.
- **OSAC-1118 (Baremetal OSAC API):** Provides the BaremetalInstance lifecycle foundation (create, provisioning, ready, deprovision, deleted) that this feature extends with OS image selection.

## Acceptance Criteria

- [ ] A Tenant User can select a DiskImage when creating a BaremetalInstance and the instance is provisioned with that OS image.
- [ ] BaremetalInstance creation fails with a clear error when no DiskImage is specified and the BaremetalInstanceCatalogItem provides no default.
- [ ] A Cloud Provider Admin can create a BaremetalInstanceCatalogItem that references a global DiskImage as default.
- [ ] A Tenant Admin can create a BaremetalInstanceCatalogItem that references a tenant-scoped DiskImage as default.
- [ ] Deleting a DiskImage that is referenced by any BaremetalInstance or BaremetalInstanceCatalogItem is rejected.
- [ ] E2E tests cover DiskImage selection during bare-metal instance provisioning.
