# Default Catalog Items

| Field       | Value   |
|-------------|---------|
| Author(s)   | Daniel Erez |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1531 |
| Date        | 2026-07-19 |

## Problem Statement

OSAC supports catalog items for clusters and virtual machines, but ships no defaults. After deploying the platform, a Cloud Provider Admin must manually define every catalog item before tenants can order any resources. This creates friction for new deployments and slows evaluation, demos, and onboarding. Without defaults, tenants see an empty catalog and cannot self-service until an admin has authored catalog items from scratch.

## In Scope

- A set of example YAML files defining default catalog items, shipped in the fulfillment-service repository under `examples/catalog-items/`
- A README documenting how to load catalog items using `osac create -f`, with command examples and authentication instructions
- Default cluster catalog items: Single Node OpenShift (SNO) and compact (three-node) OpenShift, using a current version of OpenShift
- Default compute instance (VM) catalog items: RHEL 10 (no GPU), RHEL 10 (with one NVIDIA GPU), Windows Server, and Windows 11 — each with suggested resource defaults (e.g., 8 CPUs, 64 GiB RAM)
- All default catalog items are globally published and visible to all tenants via the public API once loaded `[Clarify: R1.Q4]`
- **Services:** CaaS (cluster catalog items), VMaaS (VM catalog items)
- **Target milestone:** 0.2

## Out of Scope

- Bare metal catalog items — these depend on installation-specific inventory and are not generalizable as defaults `[Clarify: R1.Q1]`
- OpenShift AI cluster catalog item (OSAC-1555) — a separate feature that builds on the defaults defined here `[Clarify: R1.Q5]`
- Automated loading during installation — admins load defaults manually via `osac create -f` `[Clarify: R1.Q3]`
- Catalog item versioning — updating YAML files when new OpenShift versions are released `[Clarify: R2.Q3]`
- Per-tenant catalog item assignment — defaults are globally published; tenant-scoped catalogs are existing platform capability, not part of this feature `[Clarify: R1.Q4]`

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to load a curated set of default cluster and VM catalog items from YAML files using `osac create -f` so that tenants can immediately browse and order resources after platform deployment.
- As a Cloud Provider Admin, I want clear documentation (a README with examples) explaining how to load the default catalog items, including authentication setup and the exact commands to run, so that I can complete the setup without guesswork.
- As a Cloud Provider Admin, I want the default catalog items to be globally published upon creation so that all tenants can see them without additional per-tenant configuration.

### Tenant User

- As a Tenant User, I want to see default cluster options — such as a single-node or compact OpenShift cluster — when browsing the catalog so that I can order a cluster sized for my workload without waiting for an admin to define custom catalog items.
- As a Tenant User, I want to see default VM options — such as a Linux VM, a GPU-enabled Linux VM, or a Windows VM — when browsing the catalog so that I can provision a virtual machine matching my workload requirements.
- As a Tenant User, I want each default catalog item to include editable fields (e.g., disk size, network CIDR) with sensible defaults and validation so that I can customize the order while staying within supported configurations.

### Acceptance Criteria

- [ ] YAML example files exist in `examples/catalog-items/` for each defined default catalog item (2 cluster, 4 VM) `[Clarify: R2.Q4]`
- [ ] A README in `examples/catalog-items/` documents loading instructions, authentication setup, and command examples `[Clarify: R2.Q4]`
- [ ] Each YAML file can be loaded via `osac create -f` and the resulting catalog item is globally published (no tenant scope) and visible to all tenants via the public List endpoint, CLI, and UI `[Clarify: R2.Q4]`
- [ ] Tenant Users can discover and select loaded catalog items through the public API, CLI, and UI without admin intervention beyond initial loading
- [ ] Each catalog item includes field definitions with display names, editable/read-only designation, default values for user-configurable fields, and a validation schema that constrains input to values supported by the provisioning flow

## Dependencies

- **VM images:** Default VM catalog items reference container disk images (e.g., RHEL 10, Windows). These images must be available in the target registry before the VM catalog items are useful. Image availability is tracked separately from this feature. `[Clarify: R1.Q2]`
- **OpenShift artifacts:** Default cluster catalog items reference cluster templates that depend on OpenShift release artifacts being available in the deployment environment. These artifacts are a prerequisite for cluster provisioning, tracked separately. `[Clarify: R1.Q2]`
- **Cluster and compute instance templates:** Each catalog item references a template (e.g., `osac.templates.ocp_4_17_small`). The referenced templates must exist in the fulfillment service before the catalog items can be created.

## Open Questions

### 8.1 Image pre-loading strategy

**Owner:** VMaaS team / Cloud Infrastructure Admin stakeholders
**Impact:** Dependencies section; may require additional documentation or tooling

How should VM images and OpenShift artifacts be pre-loaded into a fresh deployment? Options include a separate seeding script, documentation-only guidance, or integration with the installer. This feature documents the dependency but does not solve the pre-loading problem. This question does not block the 0.2 milestone — catalog items can be loaded and are visible in the catalog regardless of whether the underlying images and artifacts are available; provisioning will only succeed once the prerequisites are in place.
