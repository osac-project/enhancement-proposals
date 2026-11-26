---
title: platform-managed-secret-scopes
authors:
  - htayrie@redhat.com
creation-date: 2026-11-26
last-updated: 2026-11-26
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-5308
prd:
  - prd.md
---

# Platform-managed Secret scopes

## Summary

OSAC keeps the tenant as the Secret's owner and adds a private `platform_managed` flag to restrict access to the platform. See the [PRD](prd.md) for requirements.

## Motivation

Fulfillment uses `metadata.tenant` for both ownership and visibility. The `system` scope provides platform-only access and has no regular tenant owner for filtering, reference checks, or offboarding. [OSAC-5425](https://redhat.atlassian.net/browse/OSAC-5425)

CaaS storage is the first use case. Acme's delegated credentials for the `vast-east` backend belong to Acme and are used by the platform to provision its storage. [User]

### Goals

- Separate ownership from visibility in the existing Secret resource.
- Enforce scope at the API, reference, and storage boundaries.
- Reuse the private Secrets API and tenant finalizer.

### Non-Goals

- StorageBackend credentials and hub kubeconfig integrations are separate work.
- Per-Secret permission grants and new storage backends are outside release 0.6.

## Proposal

For a regular tenant, `platform_managed: true` gives its Secret the same privacy as a `system` Secret. The owner stays in `metadata.tenant`. PostgreSQL stores the flag and Vault holds the values behind a platform-only policy. The ownership and visibility model can apply to other OSAC objects. Release 0.6 applies it to all supported Secret types. [Locked: D1, D2]

### Workflow Description

1. A Cloud Provider Admin stores `config.yaml` as an opaque, platform-managed Secret named `vast-east` in Acme's `storage` project. The console, CLI, and private API all support finding it by owner. [User] [Locked: D6]
2. In the CaaS storage follow-up, the selected tier points to `vast-east`. The authorized storage controller finds the Secret by name under `acme/storage` and reads it for Acme. [User] [Locked: D3]
3. A tenant viewing a resource that shows a protected reference sees only **Configured**. [Locked: D4]
4. Tenant deletion waits for OSAC to remove the owner's protected Secrets and values. [Locked: D5]

### API Extensions

The Secrets REST collections are `/api/private/v1/secrets` and `/api/fulfillment/v1/secrets`. Requirement IDs refer to the [clarification log](clarifications.md).

| ID | Interface change | Requirements |
| --- | --- | --- |
| IC-1 | Private `Secrets/{Create,List,Get,Update,Delete}` accepts the new scope, returns owner metadata, and allows CEL selection by `this.platform_managed` and `this.metadata.tenant`. Public Secrets excludes the new scope from results and totals. | R1.Q1, R1.Q2, R1.Q3, R1.Q5 |
| IC-2 | An authorized controller finds a tenant-associated platform-managed Secret by exact tenant, project, name, and scope through private `Secrets/List`. Private `Secrets/Get` requires `expected_tenant` for controller reads in this scope. | R1.Q2, R1.Q3 |
| IC-3 | Public resource responses and `Events/Watch` redact protected references. Public Watch omits Secret objects in the new scope. A metadata update preserves a stored protected reference. | R1.Q3 |
| IC-4 | The existing tenant deletion state remains pending while owned protected Secrets or Vault entries remain. | R1.Q4 |
| IC-5 | In a private CLI session, `osac --tenant acme create secret --platform-managed …` creates the new scope. Existing `get`, `describe`, `edit`, and `delete secret` verbs use the private endpoint. `get secret --filter` selects scope and owner. | R1.Q5 |
| IC-6 | The provider-admin Secrets page selects scope and owner for create and list, and uses private Connect bindings for detail, edit, and delete. Tenant pages retain the public client and render protected references as **Configured** where shown. | R1.Q3, R1.Q5 |
| IC-7 | Vault provisioning configures protected KV v2 storage and grants Fulfillment access to its values and metadata. Mount placement is an [open question](#2-vault-mount-placement). | R1.Q3, R1.Q4 |

### Implementation Details/Notes/Constraints

**Secret fields.** Add private `bool platform_managed = 7` to `Secret` and private `string expected_tenant = 2` to `SecretsGetRequest` using `cleanapi.field`. The flag defaults to `false`. Setting it requires an explicit, existing regular tenant and the Vault backend. Invalid scope or backend, and attempts to change the flag or owner, return `InvalidArgument`. Existing project and type rules apply, including those for user data, service-account credentials, and break-glass Secrets. [Locked: D1, D2] [Secret proto](https://github.com/osac-project/osac/blob/6c883aa9f/proto/private/osac/private/v1/secret_type.proto)

**PostgreSQL.** Store the flag in the existing Secret JSONB and treat missing values as `false`. The migration enforces immutability and replaces the name index with a unique index on `(tenant, project, name, coalesce((data->>'platform_managed')::boolean, false))`. This lets tenants use the same name in their own scope without discovering a protected Secret. A duplicate within a scope returns `AlreadyExists`. [Current name index migration](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/internal/database/migrations/100_add_name_uniqueness_and_immutability.up.sql)

**References.** Match the exact tenant, project, name, and `platform_managed=true` with private `Secrets/List`. Require one match and use its ID and the consuming resource's tenant for private Get. For a resource field that accepts a protected reference, the authorized private writer resolves the name in the field's scope and stores the canonical name and ID. Validate type, lifecycle, and ownership before accepting the reference. Default reference resolution and public lookups exclude tenant-associated protected targets. [User] [Local references](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/docs/API.md#local-references), [OSAC-5424](https://redhat.atlassian.net/browse/OSAC-5424)

**Public output.** Look up reference targets by ID using metadata only, once per distinct ID in a response. For either protected scope, return an empty reference in public responses and events. Public resource lists filter on redacted fields before counting results. Metadata updates preserve the stored reference when the client sends the empty message. Only authorized platform writers can change a protected reference or settings that determine where its credential is sent. [Locked: D4] [Public mapper](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/internal/servers/generic_mapper.go)

**Vault.** Give Fulfillment's protected storage identity access to the values and metadata. Derive the storage address from the Secret's owner and ID. Protect key names as well as values because KV v2 lists key names without per-key filtering. The [mount placement](#2-vault-mount-placement) determines the path and policy. [Vault KV v2 API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2), [OpenBao KV v2](https://openbao.org/docs/secrets/kv/kv-v2/)

**Offboarding.** Hold the tenant row lock through protected Create or Update until Vault returns. A write for a deleting tenant returns `FailedPrecondition`. Project cleanup removes the Secret records after consuming resources release their references. The tenant reconciler verifies that all protected Vault entries for the owner, including any orphans and older versions, are gone before releasing the finalizer. [Locked: D5] [Existing tenant lock](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/internal/servers/networking_lifecycle_guards.go#L307), [Project Secret cleanup](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/internal/controllers/project/project_reconciler_function.go#L599)

### Security Considerations

- Apply scope checks before type-specific permissions. Omit tenant-associated platform-managed Secrets from public List results and totals, Watch, lookups, and selectors. Public Get, Update, and Delete return `NotFound` for these IDs. Existing policy authorizes platform admins to list and read `system` Secrets on the public API. Private RPCs deny tenant identities with `PermissionDenied`.
- Require `expected_tenant` only when an authorized controller reads a tenant-associated platform-managed Secret. In 0.6, verify the Fulfillment controller's authenticated Keycloak client and service-account subject. It passes the tenant from the stored consuming resource. Omitting it returns `InvalidArgument`, and a mismatch returns `NotFound`. Provider admins use Get by ID for management. Controllers use Get by ID for the existing scopes. The storage follow-up grants its controller access explicitly.
- Keep identifiers and values out of public errors, conditions, and telemetry. A failed metadata lookup stops public delivery.

### Failure Handling and Recovery

| Failure | Result and recovery |
| --- | --- |
| Vault is unavailable or the mount is missing | Return `Unavailable` or `FailedPrecondition` respectively and roll back the database write. |
| Secret still in use | Delete returns `FailedPrecondition`. Offboarding waits for the reference to clear. |
| Partial cleanup or controller restart | Deletion stays pending until a retry verifies that the owner's protected keys or Vault namespace are gone. |

### RBAC / Tenancy

Existing tenant, project, and type policy applies, including to tenant-managed service accounts. Protected operations distinguish provider-admin management from the explicit Fulfillment controller grant. [Locked: D1, D3]

| Scope | Create, update, delete | List | Read values | Set a reference | Resolve for use |
| --- | --- | --- | --- | --- | --- |
| Tenant-managed | Tenant/project policy | Tenant/project policy | Tenant/project policy | Resource writers on eligible fields | Runtime permitted by the field |
| Shared | Provider admin or authorized platform controller | Shared metadata policy | Provider admin or authorized platform controller | Platform writers through supported shared defaults | Runtime permitted by the resource |
| Platform-global | Provider admin or authorized platform controller | Same actors | Same actors | Platform writers on eligible fields | Explicitly authorized controller on eligible fields |
| Tenant-associated platform-managed | Provider admin or authorized Fulfillment controller | Same actors, with owner filtering | Admin Get by ID or controller Get with matching owner | Authorized private writer for the same tenant | Authorized Fulfillment controller with matching owner |

### Observability and Monitoring

Platform logs record the owner tenant and a coarse error code for mount and cleanup failures. Tenant-facing status uses a generic error for protected references.

### Risks and Mitigations

Protected identifiers can leak through lookups, filters, or events. Deployed tests cover Secret access and watch visibility. Component tests cover reference redaction, filtering, and updates.

### Drawbacks

The flag adds a visibility check. Protected Vault storage adds provisioning and cleanup verification.

## Alternatives (Not Implemented)

| Alternative | Trade-off |
| --- | --- |
| Store protected rows under `system` with an owner tag | Reuses system visibility and requires a second owner field with separate project and name scoping. |
| Use a four-value scope enum | Names each scope directly and requires migration of the built-in scopes. |
| Redact using a flag on the reference, or add a Resolve RPC | Redaction would depend on a copy of the Secret's flag. The existing List and Get support a scoped name lookup and read. |
| A prefix in the ordinary Vault mount | The existing wildcard grants cover the prefix and can expose key names to identities that list the mount. A protected prefix needs changes to the data and metadata policy. |

## Open Questions

### 1. Settlement of timed-out Vault writes

Can a timed-out Vault write land after the owner lock is released and the reconciler verifies cleanup? **Owner** — Core. **Impact** — The chosen layout may need a way to wait for the write or block it before releasing the finalizer.

### 2. Vault mount placement

Should protected values use a dedicated mount in each owning tenant's Vault namespace or one dedicated mount in `system`? **Owner** — Core. **Impact** — A mount in the tenant namespace can use existing namespace deletion, with Vault namespace administration held by the platform. A mount in `system` is provisioned once and needs cleanup for each tenant's keys. [Vault namespace deletion](https://developer.hashicorp.com/vault/docs/ui/namespaces#delete-a-namespace), [OSAC tenant cleanup](https://github.com/osac-project/osac/blob/6c883aa9f/fulfillment-service/internal/controllers/tenant/tenant_reconciler_function.go#L1083)

## Test Plan

See the [detailed test plan](testplan.md) for requirement mappings, fixtures, and commands.

### Unit Tests

Cover scope validation, owner checks, redaction, and cleanup retries.

### Integration Tests

Exercise private API and CLI access, tenant denial, watch visibility, Vault permissions, and offboarding against the deployed stack. Exercise reference redaction in the Fulfillment server suite.

### E2E Tests

Use Playwright to verify provider-admin Secret management and tenant visibility in the Secrets view.

## Graduation Criteria

Release 0.6 requires passing deployed checks for all three admin interfaces, authorization, and offboarding, plus passing component checks for reference redaction. Publish the four-scope permission matrix and admin workflow.

## Upgrade / Downgrade Strategy

Provision protected storage before accepting protected writes. Migrated rows default to `false` and keep their Vault paths. Before reverting to a binary that predates the flag, clear protected references, delete protected Secrets, and verify that the protected inventory and Vault data are gone.

## Version Skew Strategy

An older Fulfillment replica can ignore the flag. Upgrade every serving replica and the controller before accepting protected writes. Release the CLI and console after the private API, with matching versioned UI bindings. [UI generated bindings](https://github.com/osac-project/osac/blob/6c883aa9f/osac-ui/AGENTS.md#generated-api-bindings)

## Support Procedures

For a protected operation failure or pending deletion, check the mount and service policy. Restore access so the reconciler can retry.

## Infrastructure Needed

Provision protected storage and its service policy through Vault bootstrap. Apply the [chosen placement](#2-vault-mount-placement) in bundled OpenBao and externally managed Vault.

---

## Provenance

Authored: revise @ design 0.15.0 - 760cf64, workspace main @ f0a8211
Phases: draft, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"760cf64","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
