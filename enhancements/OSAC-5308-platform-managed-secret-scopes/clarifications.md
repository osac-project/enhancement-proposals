# Clarification Log — OSAC-5308

## Status

| Measure | State |
| --- | --- |
| Rounds completed | 1 |
| Open gaps | 0 |
| Exit criteria met | Yes |

## Round 1 — Platform-managed object scope

### R1.Q1 — Object types and baseline permissions

Which object types need platform-managed scope in 0.6, and which authorization policy should govern Secrets?

#### Answer

The user confirmed that platform-managed scope can apply to other OSAC object types and that Secrets are the object type required for 0.6, as scoped in OSAC-5308. The existing Secrets policy must inform the requirements for Secrets. [OSAC-5308](https://redhat.atlassian.net/browse/OSAC-5308)

#### Impact

Define the ownership and tenant visibility rules for OSAC objects. Specify 0.6 permissions and acceptance criteria for Secrets, using the existing policy for operations, access to values, and type-specific restrictions for service-account credentials and break-glass Secrets.

#### Decision (D1)

Platform-managed scope is a general OSAC object concept. The existing Secrets authorization policy is the baseline for Secrets.

#### Decision (D2)

Secrets are the object type required to support the platform-managed scope in 0.6.

---

### R1.Q2 — Controller permissions

Should authorized controllers be able to create, update, and delete Secrets in the new tenant-associated scope, in addition to retrieving their values?

#### Answer

Yes. The user confirmed that authorized controllers need both retrieval and write access for Secrets in the new scope.

#### Impact

Cover authorized controller create, read, update, and delete in the 0.6 requirements. The same controller can serve several tenants. The tenant association identifies which tenant each Secret belongs to. The existing Secrets policy is the authorization baseline, and StorageBackend and hub integrations are follow-up work.

#### Decision (D3)

Authorized platform controllers can create, retrieve, update, and delete Secrets in the tenant-associated platform-managed scope in 0.6.

---

### R1.Q3 — Tenant visibility

The public API currently retains system-tenant references with their identifying details removed. Should tenant-facing resources be allowed to show that a protected Secret is configured with the same redaction rule for both protected scopes?

#### Answer

Yes. The user confirmed the same public redaction behavior for platform-global and tenant-associated platform-managed Secrets.

#### Impact

A tenant viewing a resource they can access may see an indication that a credential is configured. The requirements restrict the protected Secret’s identity, ownership, and value to authorized platform identities.

#### Decision (D4)

Both protected scopes permit tenant-facing references that indicate a Secret is configured with its identifying details redacted.

---

### R1.Q4 — Tenant offboarding

Should deleting a tenant automatically remove its tenant-associated platform-managed Secrets before offboarding completes?

#### Answer

Yes. The user agreed to extend the existing tenant offboarding behavior to the new Secret scope.

#### Impact

Current offboarding waits for project Secret cleanup and removes the tenant's Vault namespace when Vault lifecycle management is configured. For the new scope, the explicit tenant association identifies the protected Secrets to remove. Acceptance criteria cover successful cleanup and a cleanup failure that keeps tenant deletion pending.

#### Decision (D5)

OSAC automatically removes platform-managed Secrets associated with the tenant being deleted. Tenant deletion completes after that cleanup succeeds.

---

### R1.Q5 — Admin interfaces

Should 0.6 require Cloud Provider Admins to manage protected Secrets through the private admin API and the `osac` CLI, with web console support deferred?

#### Answer

The user asked to include web console support in 0.6 and confirmed that all three interfaces are in scope.

#### Impact

Extend the Cloud Provider Admin’s Secret management workflows to support the new scope and its owning tenant. The web console, CLI, and API must enforce the same authorization and redaction rules.

#### Decision (D6)

Cloud Provider Admins can manage protected Secrets through the web console, `osac` CLI, and private admin API in 0.6.

## Dependencies

- Vault is the existing Secret store for this feature. The design phase will evaluate the Vault hierarchy and cleanup mechanism.
- OSAC-5425 provides the baseline for Cloud Provider Admin management of system-tenant Secrets through the private API. [OSAC-5425](https://redhat.atlassian.net/browse/OSAC-5425)
- OSAC-5424 is the complementary work on tenant-aware object references and redaction. [OSAC-5424](https://redhat.atlassian.net/browse/OSAC-5424)
