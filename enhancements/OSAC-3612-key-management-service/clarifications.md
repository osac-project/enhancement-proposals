# Clarification Log — OSAC-3612

## Status

- Rounds completed: 3
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Scope and user behavior

### R1.Q1: Supported interfaces

Should key lifecycle management be available through both the API and CLI, with no UI in scope?

#### Answer

Keep the API and CLI interfaces, with no UI for now.

#### Impact

The PRD will require user-observable key lifecycle behavior through the API and CLI and identify a key-management UI as outside this feature's scope.

#### Decision (D1)

Key lifecycle management is available through the API and CLI; a UI is not included.

---

### R1.Q2: Administrative permissions

Can Tenant Admins manage only keys belonging to their tenant, while Cloud Provider Admins can manage configuration across tenants? What key access should Cloud Infrastructure Admins have?

#### Answer

Tenant Admins should manage only keys for their own tenant. Cloud Provider Admins care about enabling tenants to manage keys, but their other needs are uncertain. A possible need is configuring storage backends that expose keys which all tenants may consume. Cloud Infrastructure Admin access was not determined.

#### Impact

The PRD will require strict tenant-scoped administration for Tenant Admins. Cloud Provider Admin and Cloud Infrastructure Admin capabilities remain open and require clarification, including whether shared platform-managed keys are part of this feature.

#### Decision (D2)

Tenant Admins can manage only keys belonging to their tenant.

---

### R1.Q3: Destruction safeguards

Must key destruction be rejected while the key is bound to resources, or may an administrator explicitly force destruction after a warning?

#### Answer

Err on the side of preventing deletion when resources remain attached.

#### Impact

The PRD will require destruction to fail safely while consumers remain associated with the key and to provide an actionable explanation to the administrator.

#### Decision (D3)

A key cannot be destroyed while resources or consumers remain attached to it.

---

### R1.Q4: Rotation behavior

Should rotation create a new active key version while retaining prior versions for existing consumers? What status should users observe during rotation?

#### Answer

Yes. Promote as much transparency in interim states as possible.

#### Impact

The PRD will require rotation to preserve prior key versions needed by existing consumers, promote a new active version, and expose meaningful intermediate and resulting states through supported interfaces.

#### Decision (D4)

Rotation creates and promotes a new active key version, retains earlier versions needed by existing consumers, and exposes interim rotation states transparently.

---

### R1.Q5: Generic binding boundary

Should OSAC-3612 provide a consumer-neutral way to associate keys with downstream services, while OSAC-2389 owns all storage-resource and KMIP-specific binding behavior?

#### Answer

Yes. This feature should be the backbone and remain largely consumer-neutral.

#### Impact

The PRD will cover a generic association capability and exclude storage-resource and KMIP-specific binding behavior, which belongs to OSAC-2389.

#### Decision (D5)

OSAC-3612 provides the consumer-neutral key-management backbone and generic consumer association; storage-resource and KMIP-specific binding behavior belongs to OSAC-2389.

---

## Round 2 — Administration, observability, and failures

### R2.Q1: Cloud Provider Admin responsibilities

Should the Cloud Provider Admin configure platform key backends and policies but not manage tenant-owned keys? Should shared platform-managed keys be in scope now or remain an open requirement?

#### Answer

For now, the Cloud Provider Admin configures backends and policies, while key management is largely left to tenants. This raises an unresolved question about default behavior: whether every tenant must configure key management or whether Cloud Provider Admins configure defaults or fallbacks.

#### Impact

The PRD will assign platform backend and policy configuration to Cloud Provider Admins and tenant-owned key lifecycle management to Tenant Admins. Default and fallback behavior requires one more clarification; shared platform-managed keys are not yet established as a requirement.

#### Decision (D6)

Cloud Provider Admins configure platform key backends and policies but do not ordinarily manage tenant-owned keys; Tenant Admins manage their tenant-owned keys.

---

### R2.Q2: Cloud Infrastructure Admin responsibilities

Should the Cloud Infrastructure Admin have read-only visibility into key health and audit history, while managing platform KMS availability but not tenant key lifecycles?

#### Answer

Yes, that role division makes sense.

#### Impact

The PRD will separate operational oversight of the platform KMS from tenant-owned key lifecycle authority.

#### Decision (D7)

Cloud Infrastructure Admins have read-only visibility into key health and audit history and manage platform KMS availability, but do not manage tenant key lifecycles.

---

### R2.Q3: Revoke versus destroy

Should revocation prevent new use while preserving the key for recovery or existing consumers, with destruction being permanent and allowed only after all attachments are removed?

#### Answer

Yes.

#### Impact

The PRD will distinguish reversible access prevention from irreversible key removal and will require clear lifecycle states and safeguards.

#### Decision (D8)

Revocation applies to the complete logical key and blocks normal infrastructure encryption, decryption, and new consumer associations across all retained versions. Associated data becomes inaccessible to consumers, while the key material remains retained for an explicit authorized recovery process. Unsupported operations return an actionable failure through the API and CLI. Destruction permanently removes the key material, prevents recovery, and is allowed only after all attachments are removed. This product-level behavior does not prescribe internal version-selection or recovery mechanics.

---

### R2.Q4: Tenant-visible usage

Should Tenant Admins see associated consumer names, consumer types, key versions, lifecycle state, and last-used time?

#### Answer

Yes, those details are reasonable.

#### Impact

The PRD will enumerate the key and consumer usage information visible to Tenant Admins within their tenant.

#### Decision (D9)

Tenant Admins can view associated consumer names and types, key versions, lifecycle state, and last-used time for keys in their tenant.

---

### R2.Q5: Failures and audit

Which lifecycle events must be auditable, and what should users observe when the KMS backend is unavailable or an operation fails?

#### Answer

That specificity may belong in the design rather than the PRD and may not be necessary at this stage.

#### Impact

The PRD will avoid prescribing detailed failure handling or audit implementation. A final clarification will seek only the minimum user-observable product behavior needed to keep the requirements testable.

---

## Round 3 — Defaults and minimum guarantees

### R3.Q1: Tenant defaults

Should Cloud Provider Admins configure a default backend and policy that tenants inherit automatically, allowing Tenant Admins to create keys without configuring KMS infrastructure? If tenant-specific configuration is later supported, should it override that default?

#### Answer

Tenants should never need to consider KMS infrastructure in that way. Tenant-specific default behavior can be deferred for now.

#### Impact

The PRD will require backend and policy infrastructure to be transparent to tenants. Cloud Provider Admins remain responsible for platform configuration; detailed default selection, fallback behavior, and tenant-specific infrastructure choices are not prescribed by this PRD and can be resolved during design without exposing infrastructure concerns to tenants.

#### Decision (D10)

Tenants do not configure or select KMS infrastructure. Cloud Provider Admin configuration is applied transparently when tenants manage keys; tenant-specific infrastructure defaults are not required by this PRD.

---

### R3.Q2: Minimum failure behavior

Without prescribing design details, may the PRD require lifecycle operations to report success or an actionable failure, never leave users with an ambiguous reported state, and make create, rotate, revoke, and destroy operations visible in audit history?

#### Answer

Yes.

#### Impact

The PRD will include testable, user-observable failure and audit guarantees without specifying their implementation.

#### Decision (D11)

Key lifecycle operations report success or an actionable failure, do not leave users with an ambiguous reported state, and make create, rotate, revoke, and destroy operations visible in audit history.

---

## Remaining Gaps

None. Detailed platform default selection, fallback mechanics, and audit implementation belong in the design while preserving the locked user-facing decisions above.

## Post-Review Decisions — 2026-09-11

### Decision (D12): Tenant lifecycle authority

Key lifecycle management remains limited to Tenant Admins for this feature. Tenant Users do not receive direct key lifecycle authority. This reaffirms D2.

### Decision (D13): Stable consumer associations

Consumers associate with a stable logical key rather than a specific key version. Successful rotation promotes a new active version without requiring consumers to update their association, while prior versions remain available where needed for existing encrypted data. This refines D4 and D5.

### Decision (D14): Association visibility

Tenant Admins can see a key's lifecycle state and active version. Proactive visibility into associated consumers, detailed consumer names and types, and last-used timestamps is not required. Safe destruction is enforced by rejecting destruction with an actionable explanation when the key remains in use. This supersedes D9.

### Decision (D15): Audit scope

Explicit audit-history requirements are removed from this feature because the platform does not currently provide the required audit-log capability. Cloud Infrastructure Admin health and availability responsibilities from D7 remain; the audit-history portion of D7 and D11 is superseded. The success, actionable-failure, and unambiguous-state guarantees from D11 remain.

## Post-Review Decisions — 2026-09-15

### Decision (D16): Cloud Provider Admin key lifecycle authority

Cloud Provider Admins are users of the KMS and can manage the complete lifecycle of provider-owned keys used by platform infrastructure. They do not manage tenant-owned keys, and provider-managed shared or default keys for tenant consumption remain outside this feature. This supersedes the portion of D6 that limited Cloud Provider Admins to backend and policy configuration while preserving the separation between provider-owned and tenant-owned keys.

### Decision (D17): Cloud Infrastructure Admin availability scope

Cloud Infrastructure Admins have read-only visibility into platform KMS health and availability but do not manage tenant-owned or provider-owned key lifecycles. The concrete operational mechanisms used to maintain availability belong to the design rather than the PRD. This refines D7.

### Decision (D18): Preserve existing Cloud Provider Admin access

This feature does not introduce a new restriction preventing Cloud Provider Admins from accessing tenant-owned keys. Cloud Provider Admins can manage provider-owned keys, while their broader access continues to follow the platform's existing administrative authorization model. This supersedes the Cloud Provider Admin restriction introduced by D16 and the portion of D6 that implied Cloud Provider Admins cannot manage tenant-owned keys. The additional ownership and inheritance patterns under consideration for secrets are not added to this feature pending further clarification.
