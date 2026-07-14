# Type-Safe Resource References

| Field       | Value   |
|-------------|---------|
| Author(s)   | Haim Tayrie |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1330 |
| Date        | 2026-07-12 |

## Problem Statement

When users create or update OSAC resources that reference other resources — a compute instance referencing a subnet, a cluster order referencing a template, an external IP attachment referencing a target — they provide raw identifier strings. The system cannot distinguish a subnet reference from a security group reference at the schema level; both are opaque strings. Users discover invalid or mismatched references only at runtime through downstream failures that may not clearly indicate which reference was wrong or why. References also carry no context about tenant or project, so users cannot reference shared resources (such as global cluster templates) without out-of-band knowledge of the target's identifier.

## In Scope

- Users reference resources by name instead of opaque identifiers, across all services (BMaaS, CaaS, VMaaS, MaaS, Enclave) and all resource types. [Clarify: R1.Q2]
- When a referenced resource does not exist or the reference is malformed, the system rejects the request immediately with a clear, unambiguous error message identifying which reference failed and why. [Clarify: R1.Q3]
- Users can reference resources within the same tenant and project using only the resource name (local reference).
- Users can reference resources in a different tenant or project by specifying tenant, project, and name (full reference) — for example, referencing shared cluster templates managed by the cloud provider.
- When users provide a resource identifier, the system resolves the corresponding name, and vice versa, ensuring references are never ambiguous.
- The new reference format replaces the current string-based format with no backward-compatible transition period. [Clarify: R1.Q1]
- UI, CLI, and API all support the new reference format with corresponding tasks for each. [Clarify: R1.Q4]
- Delivery is incremental — each delivered chunk leaves the system fully functional. [Clarify: R2.Q3]
- API documentation and OpenAPI specifications reflect the new reference format.
- Test coverage is updated to validate reference resolution and error behavior.

## Out of Scope

- Migration from identifier-based to (tenant, project, name)-based resource identification. Reference types prepare the foundation, but the migration is a separate initiative. [Clarify: R1.Q5]
- Backward compatibility with the previous string-based reference format. [Clarify: R1.Q1]
- Changes to how resources are identified internally (primary keys, database schema).

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to create a cluster catalog item that references a cluster template by name so that I can configure catalog entries without looking up template identifiers.
- As a Cloud Provider Admin, I want to create a bare metal instance catalog item that references a template by name so that catalog management uses human-readable names.
- As a Cloud Provider Admin, I want to reference resources across tenants (e.g., shared templates in a global tenant) by specifying tenant, project, and name so that I can manage cross-tenant configurations without identifier lookup.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to manage external IP pools and network classes using name-based references so that infrastructure configuration is human-readable and auditable.
- As a Cloud Infrastructure Admin, I want to receive a clear error message when I reference a nonexistent resource so that I can correct the reference immediately rather than debugging downstream failures.

### Tenant Admin

- As a Tenant Admin, I want to create subnets and security groups that reference their parent virtual network by name so that I can set up networking using readable, meaningful names.
- As a Tenant Admin, I want the system to reject a subnet creation request immediately with a clear message when the referenced virtual network does not exist so that I discover the error at request time, not during provisioning.

### Tenant User

- As a Tenant User, I want to create a compute instance that references subnets and security groups by name in its network attachments so that I can provision VMs without looking up resource identifiers.
- As a Tenant User, I want to create a compute instance that references a catalog item or template by name so that I can order resources from the catalog using human-readable names.
- As a Tenant User, I want to create an external IP attachment that references the external IP and target resource (compute instance, cluster, or bare metal instance) by name so that I can manage IP bindings without identifier lookup.
- As a Tenant User, I want to receive a clear, immediate error when I reference a resource that doesn't exist or that I don't have access to so that I can fix my request without debugging downstream failures.

### All Personas

- As any user, I want references displayed in the UI to show the referenced resource's name rather than an opaque identifier so that I can understand resource relationships at a glance. [Clarify: R1.Q4]
- As any user, I want the CLI to accept resource names in reference fields and display resolved references with names so that CLI workflows are human-readable. [Clarify: R1.Q4]
- As any user, I want the system to resolve references consistently — if I provide an identifier, the system resolves and returns the name, and vice versa — so that I always see a complete, unambiguous reference regardless of what I originally provided.

## Dependencies

- **(Tenant, project, name) migration:** The reference format includes a transitional identifier field to support the current identifier-based system. Once the separate (tenant, project, name) migration completes, this transitional field is removed. Reference types must land before that migration begins. [Clarify: R1.Q5]
