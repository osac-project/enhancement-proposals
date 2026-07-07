# Secret Management

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dakota Crowder |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1567 |
| Date        | 2026-07-02 |

## Problem Statement

Credentials across OSAC services — cluster kubeconfigs, identity provider secrets, storage credentials, SSH keys — are stored unencrypted alongside the resources that use them. Cloud Infrastructure Admins cannot meet data-at-rest security and compliance requirements because credential data is exposed to anyone with database access. Tenant users cannot revoke or rotate a credential without modifying the resource it belongs to, and retrieving credentials requires learning a different method for each resource type. There is no single place for a tenant to see what credentials exist or who has access to them.

## In Scope

- Applies to all OSAC services (BMaaS, CaaS, VMaaS, MaaS, Enclave) — any service that creates or consumes credentials
- Uniform secret management across all OSAC services (CLI and API)
- Pluggable secret backends, so cloud providers can bring their own secret store
- Encrypted storage of tenant and platform credentials at rest
- On-demand credential retrieval for provisioned resources (e.g., cluster kubeconfigs, admin passwords)
- Self-service secret creation for tenants (e.g., SSH keys, OIDC client secrets, cloud-init credentials)
- Automatic secret creation during resource provisioning (e.g., cluster kubeconfigs)
- Tenant-scoped privilege isolation — OSAC limits its access to only a tenant's secrets when operating on that tenant's behalf
- Installation — cloud provider must deploy and configure a Vault-compatible secret store as a prerequisite
- E2E testing — secret CRUD, automatic secret creation during provisioning, and tenant isolation require coverage
- Documentation — user guides for secret management CLI/API workflows per persona; API reference

## Out of Scope

- Secret rotation automation — users can manually update secrets, but automated rotation workflows are not in scope
- UI — secret management is CLI and API only for 0.2

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want secrets encrypted at rest, so that database access does not expose sensitive credentials.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want tenant secrets securely managed and isolated per tenant, so that the platform meets data-at-rest compliance requirements.

### Tenant Admin

- As a Tenant Admin, I want to create and manage secrets within my organization (e.g., OIDC client secrets for identity provider integration), so that my team's credentials are centrally managed.
- As a Tenant Admin, I want to control which users can access secrets through RBAC, so that I can enforce credential access policies consistent with other OSAC resources.

### Tenant User

- As a Tenant User, I want to create secrets (e.g., SSH key pairs, cloud-init credentials) and reference them when provisioning resources so that I can manage my credentials in one place.
- As a Tenant User, I want to retrieve credentials for provisioned resources (e.g., cluster kubeconfigs, admin passwords) through the same secret interface I use for my own secrets, so that credential access is consistent regardless of how the secret was created.
- As a Tenant User, I want to list my secrets and see metadata without exposing the actual secret data, so that I can browse credentials safely.
- As a Tenant User, I want to update the value of a secret I own so that I can rotate credentials without recreating resource references.
- As a Tenant User, I want to delete a secret I no longer need so that stale credentials do not persist in the system.

## Assumptions

- The Vault-compatible API is a stable and widely supported interface for secret storage.
- Credentials for provisioned resources (e.g., cluster kubeconfigs) can be retrieved on demand from the management cluster.

## Dependencies

- **Vault-compatible secret store** — the cloud provider deploys and operates a Vault-compatible secret store and provides OSAC access to use it.
