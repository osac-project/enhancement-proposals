# Default Catalog Items

| Field       | Value   |
|-------------|---------|
| Author(s)   | Daniel Erez |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1531 |
| Date        | 2026-07-22 |

## Problem Statement

OSAC automatically publishes infrastructure templates during installation via the `publish_templates` AAP job, but catalog items (the curated offerings tenants actually browse and order from) must be created manually by a Cloud Provider Admin after deployment. This means that after a fresh install, tenants see an empty catalog and cannot self-service until an admin has hand-crafted catalog items via the API or CLI. There is no code-driven mechanism to define, version, or automatically publish default catalog items, creating friction for new deployments, demos, and onboarding.

## In Scope

- A catalog item metadata format (`meta/catalog.yaml`) colocated with existing template roles in `osac-aap/collections/ansible_collections/osac/templates/roles/<role>/`, following the same pattern as `meta/osac.yaml` for templates
- An `enumerate_catalog_items` service role that discovers `meta/catalog.yaml` files across template role directories, similar to how `enumerate_templates` discovers `meta/osac.yaml`
- A `publish_catalog_items` service role that upserts catalog items to the fulfillment-service private API, following the same GET/PATCH/POST pattern used by `publish_templates`
- A `publish_catalog_items` playbook in `osac.service` that chains enumeration and publishing, analogous to the existing `publish_templates.yaml` playbook
- An AAP job template (`osac-publish-catalog-items`) registered via config-as-code
- A Helm post-install/post-upgrade hook in `osac-installer` that triggers the catalog item publishing job after templates are published (higher `hook-weight` than `publish-templates`)
- Default catalog item definitions for:
  - **Cluster:** Single Node OpenShift (SNO) and compact (three-node) OpenShift, referencing existing cluster templates
  - **Compute Instance (VM):** Linux VM (general purpose) and GPU-enabled Linux VM, referencing the `ocp_virt_vm` template
- All default catalog items are globally published (no tenant scope) and visible to all tenants via the public API
- **Services:** CaaS (cluster catalog items), VMaaS (VM catalog items)
- **Target milestone:** 0.2

## Out of Scope

- Bare metal catalog items: these depend on installation-specific inventory and are not generalizable as defaults
- Windows VM catalog items: container disk image availability for Windows is not established; can be added as a follow-up catalog item definition once images are available
- OpenShift AI cluster catalog item (OSAC-1555): a separate feature that builds on the infrastructure defined here
- Catalog item versioning or lifecycle management: updating definitions when new OpenShift versions are released
- Per-tenant catalog item assignment: defaults are globally published; tenant-scoped catalogs are existing platform capability, not part of this feature
- Modifications to the fulfillment-service private API: the existing catalog item endpoints are sufficient for publishing
- Instance type definitions: default instance types (e.g., `u1-small`, `u1-medium`, `u1-large`) are a prerequisite tracked separately

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want default catalog items to be automatically published during platform installation so that tenants can browse and order resources immediately after deployment without manual catalog configuration.
- As a Cloud Provider Admin, I want to define custom catalog items as code in Ansible role metadata (`meta/catalog.yaml`) so that I can version-control, review, and customize the catalog offerings alongside the template definitions they reference.
- As a Cloud Provider Admin, I want the catalog item publishing to be idempotent (upsert semantics) so that rerunning the installer or upgrading the platform updates existing catalog items without creating duplicates.

### Tenant User

- As a Tenant User, I want to see default cluster options (such as a single-node or compact OpenShift cluster) when browsing the catalog so that I can order a cluster sized for my workload without waiting for an admin to define custom catalog items.
- As a Tenant User, I want to see default VM options (such as a general-purpose Linux VM or a GPU-enabled Linux VM) when browsing the catalog so that I can provision a virtual machine matching my workload requirements.
- As a Tenant User, I want each default catalog item to include field definitions with display names, default values, and validation so that I can customize the order while staying within supported configurations.

### Acceptance Criteria

- [ ] A `meta/catalog.yaml` schema is defined and documented, supporting catalog item fields: `name`, `title`, `description`, `published`, and `field_definitions` (with `name`, `title`, `description`, `type`, `default`, `editable`, and `validation`)
- [ ] All four default catalog items (SNO cluster, compact OpenShift cluster, general-purpose Linux VM, GPU-enabled Linux VM) are defined via `meta/catalog.yaml` in their respective template roles
- [ ] An `enumerate_catalog_items` role discovers `meta/catalog.yaml` files from template role directories and produces typed catalog item objects (cluster, compute instance)
- [ ] A `publish_catalog_items` role upserts catalog items to the fulfillment-service private API with the same idempotent pattern as `publish_templates`
- [ ] A `publish_catalog_items.yaml` playbook chains enumeration and publishing
- [ ] An AAP job template (`osac-publish-catalog-items`) is registered via config-as-code
- [ ] A Helm post-install/post-upgrade hook triggers catalog item publishing after template publishing completes
- [ ] Default catalog items are globally published and visible via the public List endpoint, CLI, and UI after installation
- [ ] Rerunning the publishing job updates existing catalog items (upsert) without creating duplicates
- [ ] The `enumerate_catalog_items` filter plugin validates `meta/catalog.yaml` against a Pydantic model, consistent with the template enumeration pattern

## Assumptions

- The fulfillment-service private catalog item API endpoints (`/api/private/v1/cluster_catalog_items`, `/api/private/v1/compute_instance_catalog_items`) already support the GET/PATCH/POST pattern needed for upsert publishing; no API changes are required.
- The `template-publisher` ServiceAccount (or a similarly scoped account) has sufficient RBAC to create and update catalog items via the private API.
- Default instance types (e.g., `u1-small`, `u1-medium`, `u1-large`) referenced by VM catalog item field definitions will exist in the system before catalog items are published. If instance types are also seeded automatically, that mechanism is a separate feature.

## Dependencies

- **Templates must be published first:** Catalog items reference templates by ID (e.g., `osac.templates.ocp_virt_vm`). The `publish_catalog_items` Helm hook must run after `publish_templates` completes successfully.
- **VM images:** Default VM catalog items reference container disk images (e.g., Fedora). These images must be available in the target registry before the VM catalog items are useful for provisioning. Image availability is tracked separately.
- **OpenShift artifacts:** Default cluster catalog items reference cluster templates that depend on OpenShift release artifacts. These are a prerequisite for cluster provisioning, tracked separately.
- **Instance types:** VM catalog items that expose an `instance_type` field in their field definitions depend on instance types being seeded in the system.

## Open Questions

### 1. Prerequisite artifact loading

**Owner:** VMaaS / CaaS / Installer teams
**Impact:** Dependencies, installation workflow, usability on fresh deployments

Default catalog items reference VM container disk images and OpenShift release artifacts that must exist in the deployment environment before provisioning can succeed. Catalog items can be published and browsed without these artifacts, but ordering will fail until they are in place. How should these prerequisite artifacts be loaded into a fresh deployment? Options include a separate seeding job (similar to `publish_catalog_items`), documentation-only guidance, or integration with the installer. This feature documents the dependency but does not solve the preloading problem; the mechanism is tracked separately.

### 2. Catalog item publishing ServiceAccount

**Owner:** Platform / Installer team
**Impact:** Helm hook configuration, RBAC

Should catalog item publishing reuse the existing `template-publisher` ServiceAccount, or should a dedicated `catalog-publisher` ServiceAccount be created? Reusing the existing account simplifies configuration but broadens its permissions.

### 3. Catalog item field definitions source

**Owner:** VMaaS / CaaS teams
**Impact:** `meta/catalog.yaml` schema, template role metadata

Should field definitions in `meta/catalog.yaml` be self-contained (fully specified in the catalog metadata), or should they be derived from the template's `parameters` in `meta/osac.yaml` with catalog-level overrides (e.g., marking certain parameters as non-editable or changing defaults)? The former is simpler; the latter reduces duplication when templates and catalog items share parameter definitions.

### 4. Multiple catalog items per template role

**Owner:** CaaS / VMaaS teams
**Impact:** `meta/catalog.yaml` schema

A single template role (e.g., `ocp_virt_vm`) may back multiple catalog items (e.g., "Linux VM" and "GPU Linux VM") with different field definition defaults. Should `meta/catalog.yaml` support a list of catalog item definitions, or should each catalog item be defined in a separate role directory? The list approach keeps related offerings together; separate roles give each catalog item its own task files.

---

## Provenance

Committed: commit @ prd 0.5.0 - 92734a2, workspace prd/OSAC-1531 @ a92eb0a (dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"a92eb0a (dirty)","source_repo_branch":"prd/OSAC-1531","commits_behind_main":0,"commits_ahead_main":4,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false} -->
