# Public SSH Key Registry

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ygal Blum |
| Jira        | https://redhat.atlassian.net/browse/OSAC-51 |
| Date        | 2026-09-25 |

## Problem Statement

When creating a ComputeInstance, tenant users must paste their full SSH public key on every VM — there is no way to name, save, or reuse a key across VMs. This forces repetitive manual entry and raises the risk that a mistyped or otherwise invalid key derails VM creation. Other platforms (AWS EC2 key pairs, GCP, GitHub) let users register a key once and reference it by name at creation time; OSAC has no equivalent today.

## In Scope

- SSH public key registration, listing, retrieval, and deletion are available through the existing Secret API and CLI.
- Selecting a registered key when creating a supported ComputeInstance or BareMetalInstance is available through the API and CLI, with the key injected during the instance's initial access configuration.
- Registered keys are tenant-scoped, visible to authorized users in that tenant, and named uniquely within the tenant.
- SSH public key validation requires a well-formed OpenSSH public key to register successfully
- Registered key names must be unique within a tenant, across all of that tenant's users

## Out of Scope

- Private key storage
- Multiple SSH keys attached to a single ComputeInstance
- Updating the SSH key already injected into a running ComputeInstance
- Renaming a registered key — changing a name requires deleting and re-registering it
- Generic secret types such as passwords or tokens, and secret rotation
- Integration with external secret managers (e.g. Vault), and automated secret syncing into tenant namespaces via an external secrets operator
- A limit on the number of SSH keys a tenant may register
- SSH key injection into ComputeInstances that do not support cloud-init-based first-boot configuration (e.g., Windows guests, or Linux instances configured with non-cloud-init user data)

## User Stories

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to register an SSH public key with a name, so that I can reference it by name instead of pasting the full key every time I create a VM.
- As a Tenant Admin or Tenant User, I want to list the SSH public keys registered in my tenant, so that I can see what keys are available before creating a VM.
- As a Tenant Admin or Tenant User, I want to delete a registered SSH public key I no longer use, so that my tenant's key registry stays current.
- As a Tenant Admin or Tenant User, I want to select one registered SSH public key by name when creating a ComputeInstance, so that it is automatically injected into the VM on first boot instead of me pasting the key manually.
- As a Tenant Admin or Tenant User, I want to select one registered SSH public key by name when creating a BareMetalInstance, so that it is automatically applied during initial host provisioning.
- As a Tenant Admin or Tenant User, I want key registration to fail with a clear error message when the key I provide is invalid, so that I immediately know to fix or replace it. [User]

---

## Provenance

Authored: draft @ prd 0.9.0 - f7f8c6d, workspace main @ 4bfc214
Final: respond @ prd 0.9.0 - f7f8c6d, workspace main @ 4a8ac6c

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"f7f8c6d","source_repo":"4a8ac6c","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
