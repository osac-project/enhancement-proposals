# Secret Management

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dakota Crowder |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1567 |
| Date        | 2026-07-02 |

## Problem Statement

Credentials across OSAC services — cluster kubeconfigs, identity provider secrets, storage credentials, SSH keys — are stored unencrypted alongside the resources that use them. Cloud Infrastructure Admins cannot meet data-at-rest security and compliance requirements because credential data is exposed to anyone with database access. Tenant users cannot revoke or rotate a credential without modifying the resource it belongs to, and retrieving credentials requires learning a different method for each resource type. There is no single place for a tenant to see what credentials exist or who has access to them.

## Solution Overview

Introduce a dedicated secret management subsystem that gives all OSAC personas a single, uniform interface for storing and retrieving credentials. Secrets are encrypted at rest, decoupled from the resources that use them, and organized under pluggable backends so cloud providers can match storage to their infrastructure requirements.

## In Scope

- Uniform secret management across all OSAC services (CLI and API)
- Pluggable secret backends, starting with two:
  - **OpenBao** for encrypted storage. OpenBao is a Linux Foundation backed, open-source fork of HashiCorp Vault. Vault's BSL license prohibits embedding it in a commercial platform without an enterprise agreement, which would impose licensing obligations on OSAC and its downstream customers. OpenBao provides Vault API compatibility under a permissive license, giving OSAC an open-source encrypted backend while keeping Vault available as a future pluggable option for customers who already have an enterprise agreement.
  - **Hub** for on-demand Kubernetes credential retrieval
- Self-service secret creation for tenants (e.g., SSH keys, custom credentials)
- Automatic secret creation during resource provisioning (e.g., cluster kubeconfigs)
- Deprecation of per-resource credential retrieval methods in favor of the unified secret interface

## Out of Scope

- HashiCorp Vault integration — OpenBao provides Vault API compatibility, making future Vault support feasible without redesign
- Secret rotation automation — users can manually update secrets, but automated rotation workflows are not in scope
- UI support — secret management is CLI and API only for 0.2

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want secrets encrypted at rest, so that database access does not expose sensitive credentials.
- As a Cloud Infrastructure Admin, I want to declare available secret backends, so that the platform knows where to store and retrieve secrets for different use cases.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to choose from pluggable secret backends, so that I can match secret storage to my infrastructure and compliance requirements.

### Tenant Admin

- As a Tenant Admin, I want to create and manage secrets within my organization, so that my team's credentials are centrally managed.
- As a Tenant Admin, I want to control which users can access secrets through RBAC, so that I can enforce credential access policies consistent with other OSAC resources.

### Tenant User

- As a Tenant User, I want to create secrets and reference them when provisioning resources so that I can manage my credentials in one place.
- As a Tenant User, I want to retrieve credentials for provisioned resources (e.g., cluster kubeconfigs, admin passwords) through the same secret interface I use for my own secrets, so that credential access is consistent regardless of how the secret was created.
- As a Tenant User, I want to list my secrets and see metadata without exposing the actual secret data, so that I can browse credentials safely.

## Assumptions

- OpenBao's Vault-compatible API is stable and sufficient for OSAC's secret storage needs.
- Hub cluster nodes are reachable from the fulfillment-service for on-demand credential retrieval.

## Dependencies

- **OpenBao** — provides encrypted secret storage. Deployed as part of the OSAC installation.
