# Clarification Log — OSAC-5137

## Status

- Rounds completed: 3.
- Open gaps: 0. Rotation grace duration and Keycloak compatibility are design-time details, not unresolved scope choices.
- Exit criteria met: Yes.

## Round 1 — Scope, personas, interfaces, and credential rotation

### R1.Q1: Target milestone

Jira has a tentative comment targeting 0.4 and says this is not required for Dev Preview. Should the PRD set a target milestone?

#### Answer

Recommendation: set target milestone 0.4 as a planning target. Jira notes that this is not a Dev Preview requirement.

#### Impact

The PRD metadata records target milestone 0.4.

#### Decision (D1)

Set the target milestone to 0.4.

---

### R1.Q2: CSP Admin audit and tenant quotas

Should cross-tenant CSP Admin audit and tenant quotas be part of initial delivery, later in this feature, or separate work?

#### Answer

Recommendation: defer provider-wide service-account inventory and audit, along with tenant service-account quotas. The Definition of Done omits both; existing code has no service-account audit-history or query surface and no count-quota enforcement. Consider them as separate Features if needed later.

#### Impact

No tenant-quota API or enforcement path was found. OSAC-4500 has a quota-foundation PRD for resource dimensions, but service-account counts are not listed. No service-account change-history or audit-query surface was found; existing gRPC request logging is debug diagnostics, not an audit history. Provider-wide inventory, historical audit logging, and quotas are deferred from this Feature.

#### Decision (D2)

Defer provider-wide inventory/audit capabilities and service-account quotas.

---

### R1.Q3: Canonical persona mapping

Jira uses CSP Admin and Tenant User / Developer. Should these map to OSAC's canonical personas, and should Cloud Infrastructure Admin have a story?

#### Answer

Recommendation: use OSAC's canonical persona names. Keep Tenant Admin as the primary manager and map Tenant User / Developer to Tenant User. With provider-wide inventory deferred, CSP Admin / Cloud Provider Admin is not an affected persona; Cloud Infrastructure Admin is also out of scope because this Feature manages tenant identities rather than infrastructure.

#### Impact

Use OSAC's required persona names: Tenant User / Developer maps to Tenant User. Tenant Admin remains the primary manager. Cloud Infrastructure Admin has no story because the feature manages tenant identities rather than core infrastructure. Cloud Provider Admin has no story because provider-wide inventory is deferred.

---

### R1.Q4: CLI coverage

Should CLI cover create/list/get/update/delete, role grants/revocations, and secret rotation in addition to the API and UI?

#### Answer

Recommendation: include a scriptable `osac` CLI with full lifecycle parity: create, get, list, update, delete, role grants and revocations, and secret rotation. This keeps the CLI focused on the same API capability and follows existing command patterns.

#### Impact

CLI is part of the requested scope. The existing `osac` CLI has scriptable create/get/edit/delete command patterns; this Feature will provide full lifecycle coverage through the CLI, including role grants/revocations and secret rotation.

---

### R1.Q5: Secret rotation overlap

Should the old client secret stop working immediately when a new one is issued, or overlap for a grace period?

#### Answer

Recommendation: allow bounded overlap so automation can adopt the new secret without interruption. Expire the old secret automatically at the end of a design-defined grace period and support emergency revocation before then. Confirm compatibility with the deployed Keycloak version before setting the duration.

#### Impact

Use bounded overlap so automation can adopt the new credential without interruption. The old credential expires automatically after a design-defined grace period, and an emergency revoke path invalidates it sooner. The OSAC chart currently defaults to Keycloak 26.6.4, whose documentation labels dual-secret rotation experimental; Keycloak 26.8 promotes it to supported. Validate the deployed version and supported mechanism during design. See [Keycloak 26.6.4 rotation guidance](https://www.keycloak.org/docs/26.6.4/server_admin/index.html) and [Keycloak 26.8 release notes](https://www.keycloak.org/2026/10/keycloak-2680-released).

## Round 2 — Confirm recommended scope

### R2.Q1: Provider inventory and quotas

Should the PRD defer provider-wide inventory/audit capabilities and service-account quotas, or include one or both?

#### Answer

Recommendation: defer both provider-wide inventory/audit capabilities and service-account quotas. Neither is required by the Definition of Done; quota enforcement and audit history would need separate scope and supporting work.

#### Impact

Provider-wide inventory/audit and service-account quotas are out of scope. Quotas need new enforcement and are not part of the OSAC-4500 quota-foundation proposal.

This confirms Decision D2.

---

### R2.Q2: CLI breadth

Should the CLI support the full API lifecycle (CRUD, role grants/revocations, and secret rotation), or core account management only?

#### Answer

Recommendation: provide full CLI lifecycle parity over the same API, including CRUD, role grants and revocations, and secret rotation.

#### Impact

The CLI requirement covers every service-account operation in scope.

#### Decision (D3)

Provide full lifecycle CLI parity.

---

### R2.Q3: Secret rotation behavior

Should old and new secrets both work during a bounded grace period, after which the old secret expires automatically, with an emergency revoke path?

#### Answer

Recommendation: use bounded secret overlap, automatically expire the old secret when the grace period ends, and provide an emergency revocation path. Set the grace duration during design after validating support in the deployed Keycloak version.

#### Impact

This supports credential rollout without an avoidable interruption. The exact grace duration and Keycloak support level can be resolved in design.

#### Decision (D4)

Use bounded secret overlap, automatic expiry, and emergency revocation.

#### Status

Superseded by D5 following PR review. This Feature now includes immediate secret replacement; dual-secret overlap and independent revocation of the previous secret are deferred.

## Round 3 — PR review resolution

### R3.Q1: Bound initial secret-rotation scope

A reviewer suggested removing bounded secret rotation from the initial requirement because it would be difficult to implement. Should the initial Feature retain bounded overlap, or provide immediate secret replacement and defer overlap?

#### Answer

Recommendation: retain secret regeneration with immediate invalidation of the previous secret for new token requests. Defer simultaneous validity, automatic expiry of the previous secret, and separate early revocation of that secret. This is the scope applied in this revision.

#### Impact

The PRD keeps a basic way to replace a credential while removing the dual-secret grace-period behavior from this Feature. The prior bounded-overlap decision is superseded.

#### Decision (D5)

Provide immediate secret replacement in this Feature. Defer bounded overlap, automatic expiry, and separate revocation of the previous secret.

### R3.Q2: One-time secret disclosure

Should creation and secret regeneration disclose each generated secret only once, with later reads and ordinary updates redacting it?

#### Answer

Yes. Creation discloses the initial secret once, and regeneration discloses the replacement once. Get, list, and updates that do not regenerate a secret redact it.

#### Impact

Tenant Admins can retrieve newly generated credentials when needed, while later account reads and ordinary updates do not expose secret values.

#### Decision (D6)

Disclose each secret only in the response that creates or regenerates it. Redact secrets from get, list, and other update responses.

## Remaining Gaps

No unresolved scope clarifications. Revisit dual-secret overlap if a supported Keycloak baseline that provides this capability is adopted.
