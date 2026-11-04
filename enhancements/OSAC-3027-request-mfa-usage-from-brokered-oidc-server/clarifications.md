# Clarification Log — OSAC-3027

## Status

- Rounds completed: 5
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — MFA request policy and sign-in experience

### R1.Q1: Request trigger and authority

The feature says OSAC should request MFA “when MFA should be used,” but does
not say who decides or how broadly that decision applies. Should the request be
made for every brokered OIDC sign-in, only for selected tenants or identity
providers, or only when a compliance profile applies? Which persona should
control that choice?

#### Answer

Global policy: request MFA for all brokered OIDC sign-ins. Setting ownership
was clarified in R2.Q1.

#### Impact

The PRD will describe one deployment-wide policy rather than a per-tenant or
compliance-profile-specific choice.

#### Decision (D1)

The MFA request policy is global across brokered OIDC sign-ins.

---

### R1.Q2: Requested authentication outcome

Should the request represent any MFA, a defined assurance level, or particular
authentication methods? Please describe the minimum user-visible outcome
expected from a compatible tenant-managed identity provider.

#### Answer

The request should ask for generic MFA. No particular assurance level or
authentication method is required.

#### Impact

Defines what the sign-in experience is asking the identity provider to provide;
the protocol-specific representation belongs in the design document.

#### Decision (D2)

Request generic MFA and leave the method and assurance outcome to the
tenant-managed identity provider's policy.

---

### R1.Q3: Identity provider does not honor the request

If the tenant-managed identity provider cannot or does not apply MFA, should
sign-in continue according to that provider’s normal policy, or should OSAC
prevent sign-in? The Jira issue says OSAC requests MFA but does not guarantee
or enforce it, so this boundary needs confirmation.

#### Answer

Continue sign-in according to the tenant-managed identity provider's own policy
if it cannot or does not apply MFA.

#### Impact

Determines the user-visible fallback and whether the behavior remains a request
or becomes a sign-in enforcement requirement.

#### Decision (D3)

OSAC does not block sign-in when the identity provider does not apply MFA; the
identity provider's own policy determines the sign-in outcome.

---

### R1.Q4: Admin workflow and visibility

What should Cloud Provider Admins and Tenant Admins be able to configure or
verify, and through which user-facing surfaces: the console UI, CLI, public
API, or documentation/sign-in guidance? Should either admin be able to see
whether a particular sign-in request was made or honored?

#### Answer

Requiring MFA should be set at installation time (for example, through an OSAC
chart setting) and should also be changeable after installation, possibly
manually. No OSAC UI or CLI is needed to set or change it.

#### Impact

Determines the admin-facing capabilities, interface scope, and information
visibility needed in the PRD. Because installer chart settings flow into the
schema-driven Enclave Wizard, whether to include that generated UI needed
clarification; R2.Q2 resolved this. The authorized persona and expected
post-install change behavior were clarified in R2.Q1 and R2.Q3.

#### Decision (D4)

The policy is configured at installation and should be changeable after
installation. No separate OSAC UI or CLI is required for configuration.

---

### R1.Q5: Evidence of the MFA request

The Cloud Infrastructure Admin story asks to verify that OSAC sends the
request, while the Tenant Admin story asks to know when it is requested. Is it
enough for OSAC to document that it made the request, or should admins also be
able to inspect per-sign-in evidence? Should OSAC report only that a request was
sent, or also whether MFA was actually performed by the tenant-managed server?

#### Answer

Admins need to know that OSAC sends the request, but do not need per-sign-in
evidence. OSAC should not claim that MFA was performed.

#### Impact

Clarifies the observable success criteria while preserving the stated boundary
that the tenant-managed identity provider determines whether MFA is performed.

#### Decision (D5)

OSAC documentation or verification may state that it sends the MFA request; no
per-sign-in evidence or claim that MFA was performed is required.

---

## Round 2 — Installation ownership and configuration lifecycle

### R2.Q1: Ownership of the global setting

The global policy is set during OSAC installation. Which persona should own
choosing, setting, and changing this deployment-wide value?

#### Answer

Cloud Infrastructure Admin owns the setting.

#### Impact

Identifies who may configure the global behavior and whose workflow the PRD
must describe.

#### Decision (D6)

The Cloud Infrastructure Admin owns and maintains the global MFA-request
setting.

---

### R2.Q2: Enclave Wizard control

You said no OSAC UI or CLI is needed. However, a new installer chart setting is
automatically surfaced by the schema-driven Enclave Wizard as an installation
form control. Is that standard Wizard control in scope, or should the setting
be limited to configuration outside the Wizard?

#### Answer

Include the standard Enclave Wizard control. No separate OSAC console UI or
CLI control is needed.

#### Impact

Clarifies whether the feature includes installation-time Wizard support, in
addition to avoiding a separate control in the OSAC console or CLI.

#### Decision (D7)

Include the schema-generated Enclave Wizard setting; do not add a separate
configuration control to osac-ui or the CLI.

---

### R2.Q3: Post-install change expectation

The setting should be changeable after installation, possibly manually. Is it
enough for an authorized admin to update and reapply deployment configuration,
with the new behavior applying to subsequent sign-ins, or must the change take
effect without a redeployment or restart?

#### Answer

The PRD should promise only that the setting remains changeable after
installation. Leave its timing and operational details to design.

#### Impact

Defines the post-install user capability and the timing of its effect without
prescribing the implementation mechanism.

#### Decision (D8)

The setting is changeable after installation. The PRD does not guarantee
immediate application or a no-redeployment/no-restart change.

---

## Round 3 — Default behavior

### R3.Q1: Behavior when the setting is disabled

When the global setting is disabled, should OSAC omit the MFA request entirely
and otherwise leave brokered OIDC sign-in unchanged?

#### Answer

Yes. When disabled, OSAC omits the MFA request and otherwise leaves brokered
OIDC sign-in unchanged.

#### Impact

Defines the off state and the boundary between this feature and existing
authentication behavior.

#### Decision (D9)

When disabled, no MFA request is sent and existing brokered OIDC sign-in
behavior is unchanged.

---

### R3.Q2: Default for new installations

Should a new installation enable the MFA request by default, or should the
Cloud Infrastructure Admin explicitly enable it?

#### Answer

Disabled by default; the Cloud Infrastructure Admin must explicitly enable the
request for a new installation.

#### Impact

Determines the default sign-in behavior for new deployments.

#### Decision (D10)

New installations default to no MFA request until the Cloud Infrastructure
Admin enables the setting.

---

### R3.Q3: Default for existing installations

When an existing installation receives this feature, should it preserve its
current sign-in behavior until the Cloud Infrastructure Admin enables the
setting, or should the setting become enabled by default?

#### Answer

Preserve existing sign-in behavior until the Cloud Infrastructure Admin
explicitly enables the setting.

#### Impact

Determines whether enabling the feature changes sign-in behavior for existing
deployments without an explicit administrator choice.

#### Decision (D11)

Existing installations preserve their current sign-in behavior until the Cloud
Infrastructure Admin explicitly enables the setting.

---

## Round 4 — Per-tenant MFA request setting

### R4.Q1: Revised scope after review

After review, should MFA request behavior remain deployment-wide, or should
each tenant have its own setting? Which admins may change it, and what default
preserves existing sign-in behavior?

#### Answer

The setting is per tenant and is disabled by default for backward compatibility.
Cloud Provider Admins and Tenant Admins can change it within their tenant
administration scope. It is part of Tenant configuration; there is no
deployment-wide chart setting or Enclave Wizard change.

#### Impact

The PRD now describes per-tenant configuration and defaults, with no
installation-time global control or Wizard work.

#### Decision (D12)

The MFA request setting is disabled by default for each tenant. Cloud Provider
Admins can change it for tenants they administer; Tenant Admins can change it
for their own tenant. Existing tenants preserve current sign-in behavior until
the setting is enabled. This supersedes D1, D4, D6, and D7, and applies the
disabled-default decisions D10 and D11 per tenant rather than deployment-wide.

---

## Round 5 — OSAC console support

### R5.Q1: Admin UI for tenant setting

Should Cloud Provider Admins and Tenant Admins be able to change the
per-tenant MFA request setting in the tracked OSAC console, or is API/CLI-only
management sufficient?

#### Answer

Include OSAC console support for both Admin personas.

#### Impact

The PRD includes user-facing configuration in the OSAC console, and the
bootstrap epic needs UX Design and UI Design gate tasks.

#### Decision (D13)

The OSAC console must let Cloud Provider Admins change the setting per tenant
and Tenant Admins change it for their own tenant. Enclave Wizard work remains
out of scope.

---

## Remaining Gaps

None for PRD drafting. The protocol-specific request value and operational
details for applying tenant-level changes are design decisions.
