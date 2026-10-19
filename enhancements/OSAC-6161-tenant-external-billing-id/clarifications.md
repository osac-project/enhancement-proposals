# Clarification Log — OSAC-6161

## Status

- Rounds completed: 2
- Open gaps: 0
- Exit criteria met: Yes

---

## Round 1 — Scope, interfaces, and UI

### R1.Q1: Metering pipeline scope

The Definition of Done includes "Consumption reported to the external billing system can be attributed to the correct external account for every metered resource type," but the Out of Scope says "how the association is carried from the tenant to the external billing system belongs to design." Is the metering pipeline change in scope for this Feature, or does this Feature deliver only the storage and read-back of the identifier on the Tenant?

#### Answer

The metering pipeline change is in scope as a user-facing outcome. The PRD states what: consumption must be attributable to the correct external account. How that is achieved (e.g., what osac-metering does) is a design-time decision, not a PRD concern.

#### Impact

The DoD item "consumption can be attributed to the correct external account for every metered resource type" is a valid in-scope requirement. The PRD states it as a user-observable outcome. The implementation mechanism belongs in the design document.

#### Decision (D1)

Attribution of consumption to the correct external billing account is an in-scope user-facing requirement. The metering implementation details are left to design.

---

### R1.Q2: Interfaces for set and read

Which interfaces are in scope for 0.5: Fulfillment API, osac CLI, or Enclave Wizard?

#### Answer

Fulfillment API (gRPC/REST). Enclave Wizard and console UI are not in scope. There is no CLI flag to add: a Cloud Provider Admin creates a tenant with osac create -f and a YAML definition, so the identifier is a field in the tenant definition and reaches the CLI path automatically.

#### Impact

PRD describes the user experience via the Fulfillment API only. CLI and any UI surfaces are out of scope for this Feature.

#### Decision (D2)

In-scope interface: Fulfillment API (gRPC/REST) only. CLI, Enclave Wizard, and console UI are out of scope for this Feature.

---

### R1.Q3: "Observable" meaning

What does observability look like from the Cloud Provider Admin's perspective?

#### Answer

Sufficient to read the field on the Tenant resource. Present = associated with an external billing account, absent = not associated. No status condition, list column, or dashboard indicator required. The field is optional and should not be enforced.

#### Impact

The PRD states observability as: a Cloud Provider Admin can read the external identifier field on a tenant via API. No additional observability surface is in scope.

#### Decision (D3)

Observability is field-presence on the Tenant resource (read via API). No status condition or list-level indicator is in scope.

---

### R1.Q4: UI labels vs. API/CLI scope

The issue carries osac-ui and osac-ux labels. Are those labels intentional?

#### Answer

Ignore them. No UI is in scope.

#### Impact

The osac-ui and osac-ux labels are not reflected in the PRD. UI is out of scope per D2.

---

## Round 2 — CLI tenant creation

### R2.Q1: How is a tenant created through the CLI?

A Cloud Provider Admin creates a tenant using `osac create -f` and a YAML definition. There is no dedicated `osac create tenant` subcommand; `osac tenant` only selects the active tenant for later CLI operations.

#### Answer

A Cloud Provider Admin creates a tenant with `osac create -f` and a YAML definition. There is no dedicated `osac create tenant` subcommand; `osac tenant` selects the tenant for later CLI commands.

#### Impact

No CLI-specific work is required for this feature. The external billing identifier is a field in the tenant definition and flows through `osac create -f` automatically once added to the schema. D2 stands — no CLI flag or command change is needed.

#### Decision (D4)

No CLI-specific work is required. The identifier is a field in the tenant definition, so it flows through `osac create -f` without a command or flag change. D2 stands.

---

## Remaining Gaps

None. Exit criteria met.
