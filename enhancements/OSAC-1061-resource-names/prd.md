# Enforce Mandatory, Unique, and Immutable Resource Names

| Field       | Value   |
|-------------|---------|
| Author(s)   | Crystal Chun |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1061 |
| Milestone   | 0.2 |
| Date        | 2026-07-21 |

## Problem Statement

OSAC does not enforce naming discipline on resources. Resources can be created without names, names can be changed after creation, and duplicate names are accepted within the same tenant and project. This makes resources difficult to identify, reference, and manage — users cannot rely on names as stable identifiers, and automation that references resources by name is fragile. Without enforcement, naming collisions go undetected until they cause operational confusion or data integrity issues.

## In Scope

- Mandatory name validation on all resource creation endpoints (tenant-scoped and platform-scoped)
- Immutability enforcement — reject update requests that attempt to change a resource's name, tenant, or project
- Uniqueness enforcement for tenant-scoped resources within (Tenant, Project, ResourceType, Name) and for platform-scoped resources within (ResourceType, Name) globally
- DNS/Kubernetes name format validation (RFC 1123 DNS labels) on all resource creation endpoints, including existing paths that currently accept names without validation
- Kubernetes-style error messages for all validation failures
- Reliable uniqueness enforcement — when concurrent requests attempt to create resources with the same name, at most one succeeds and all others receive the duplicate-name error
- Blocking name reuse for resources in pending-deletion state

## Out of Scope

- UI enforcement of name validation — deferred beyond 0.2; API-level enforcement only
- Data migration or cleanup of existing resources with name violations — to be tracked as a separate feature
- Display name (human-readable, mutable label) — planned as a separate feature

## User Stories

### All Personas

- As any OSAC user, I want every resource to have a unique, valid, and immutable name so that I can unambiguously identify and reference resources, and rely on those references in automation, audits, and reports.
- As any OSAC user, I want to receive a clear, Kubernetes-style error message when I attempt to create a resource without a name, with an invalid name, or with a name that is already taken so that I can correct the issue and retry without confusion.
- As any OSAC user, I want resource names to follow a predictable format (DNS/Kubernetes conventions) so that I can use them reliably in scripts and automation.
- As any OSAC user, I want the system to prevent name reuse for resources that are pending deletion so that I do not accidentally reference a resource that is being torn down.

### Cloud Provider Admin / Cloud Infrastructure Admin

- As a Cloud Provider Admin, I want tenant names to be globally unique so that I do not accidentally create a tenant that conflicts with an existing one.
- As a Cloud Provider Admin or Cloud Infrastructure Admin, I want platform-scoped resources (such as network classes and IP pools) to have globally unique names so that I can configure and reference infrastructure without naming collisions.

### Tenant Admin

- As a Tenant Admin, I want resource names to be unique within my tenant and project scope so that my team can reference resources by name without ambiguity.
- As a Tenant Admin, I want project names to be unique within their parent tenant (or parent project, for nested projects) so that project references are unambiguous.
- As a Tenant Admin, I want the system to reject requests that attempt to change a resource's name, tenant, or project after creation so that resource identity remains stable and auditable.

### Tenant User

- As a Tenant User, I want every resource I provision to have a unique, valid, and immutable name so that I can reference my clusters, VMs, and networks by name in scripts and automation without ambiguity.
- As a Tenant User, I want a clear error message when I try to create a resource with a missing, invalid, or duplicate name so that I can fix the problem and retry immediately.

## User-Facing Behavior

### Resource Types

Name enforcement applies to all OSAC resource types across all services (BMaaS, CaaS, VMaaS, MaaS, Enclave) — enforcement is at the API layer.

**Tenant-scoped resources:** VirtualNetwork, Subnet, SecurityGroup, ComputeInstance, ClusterOrder, PublicIP, PublicIPPool, Project.

**Platform-scoped resources:** NetworkClass, PublicIPPool.

**Globally-scoped resources:** Tenant (Organization).

Some resource types (e.g., PublicIPPool) can be created at both tenant scope and platform scope. Each scope enforces uniqueness independently — a tenant-scoped PublicIPPool and a platform-scoped PublicIPPool with the same name can coexist.

### Uniqueness Boundaries

| Resource scope | Uniqueness boundary | Example |
|----------------|---------------------|---------|
| Tenant-scoped | (Tenant, Project, ResourceType, Name) | Two VirtualNetworks named "prod-net" can exist if they are in different projects within the same tenant |
| Platform-scoped | (ResourceType, Name) globally | Only one NetworkClass named "high-perf" can exist across the platform |
| Tenant (Organization) | Globally unique | No two tenants can share the same name |
| Project | Unique within parent Tenant | No two projects under the same tenant can share the same name |
| Nested Project | Unique within parent Project | Sibling projects under different parents can share a name |

### Name Format

Resource names must conform to RFC 1123 DNS label rules:

- Lowercase alphanumeric characters and hyphens only
- Must start and end with an alphanumeric character
- Maximum 63 characters
- Names must be lowercase; uppercase characters are rejected at creation time

### Immutability Rules

The following fields are immutable after resource creation:

- **Name** — update requests that specify a name different from the current value are rejected with a validation error
- **Tenant association** — resources cannot be reassigned to a different tenant
- **Project membership** — resources cannot be moved between projects

### Error Behavior

Validation errors follow Kubernetes conventions:

- Duplicate name: the error states that a resource of the given type with that name already exists (no distinction between active and pending-deletion resources)
- Missing name: the error states that a name is required
- Invalid name format: the error states the format violation
- Name change on update: the error states that the name field is immutable
- Tenant/project change: the error states that the field is immutable

The error experience is consistent across all personas. Platform-scoped resource errors omit tenant/project context but are otherwise identical.

## Cross-Cutting Dimensions

- **Documentation:** API error message examples and name format rules should be documented. In scope for 0.2.
- **E2E Testing:** E2E coverage for name validation, uniqueness rejection, and immutability enforcement via the fulfillment-service gRPC API. In scope for 0.2.
- **UI:** Deferred beyond 0.2 (see Out of Scope).

## Dependencies

- **OSAC-760 (Projects API & OpenShift mapping):** Project membership forms part of the uniqueness boundary. This dependency is resolved — OSAC-760 is Closed.
- **Data migration for existing name violations:** Existing resources may violate the new naming rules. Cleanup and migration must be handled as a separate feature before or alongside enforcement rollout.

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ 1ab6ac7

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"1ab6ac7","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
